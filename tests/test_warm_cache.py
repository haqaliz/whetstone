"""Warming a machine's uv cache before the first mine — the precondition, made executable.

**The defect this closes.** `tasks/environment.py` provisions every task environment with
`--offline`, deliberately: a donor whose wheels cannot be answered from uv's cache or a
`--find-links` directory fails loudly rather than resolving against whatever an index served at
3am. That is the right design and it worked exactly as designed — on a second machine with a
cold cache it rejected **all 45** candidates it was offered, minting nothing. The remedy was
written in a module docstring and nowhere an operator setting up a machine would meet it, so the
first mine on any new host fails wholesale with a message about network connectivity, which reads
like a fault rather than a documented precondition (#41).

**Why this is a command and not a shell script in a runbook.** The warm was first done by hand,
and that is the same mistake as the portability arm's driver living off-repo (#34): a procedure
nobody can execute from the repository is a procedure that gets re-derived, differently, by
whoever needs it next. The dedupe below is the part most likely to be re-derived wrongly —
warming per *commit* is hundreds of syncs where warming per *distinct lockfile* is dozens.

**The injected runner is the reason these tests exist at all.** Warming is the one operation in
this project that must reach the network, so a test that really warmed would be a test that needs
an index, takes minutes, and passes or fails on someone's wifi. `warm` takes the runner as an
argument, so what is asserted here is the decision — which locks, how many, in what order, with
which flags — and never uv's behaviour, which is uv's to test.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from whetstone.tasks.warm import (
    LockedCommit,
    WarmReport,
    materialise,
    unique_locks,
    warm,
)

#: Three distinct lockfiles across the history built below. The bytes differ; nothing else about
#: them matters, because `unique_locks` hashes content and never parses it.
LOCK_A = 'version = 1\n\n[[package]]\nname = "one"\n'
LOCK_B = 'version = 1\n\n[[package]]\nname = "two"\n'
LOCK_C = 'version = 1\n\n[[package]]\nname = "three"\n'

MANIFEST = '[project]\nname = "donor"\nversion = "{version}"\n'


def _git(args: list[str], *, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _commit(donor: Path, *, lock: str | None, version: str, message: str) -> str:
    """One commit. `lock=None` writes no lockfile, which is the pre-uv era of a real donor."""
    (donor / "pyproject.toml").write_text(MANIFEST.format(version=version))
    if lock is None:
        (donor / "uv.lock").unlink(missing_ok=True)
    else:
        (donor / "uv.lock").write_text(lock)
    _git(["add", "-A"], cwd=donor)
    _git(["commit", "--quiet", "-m", message], cwd=donor)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(donor),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def donor(tmp_path: Path) -> Path:
    """A real repository whose history repeats a lockfile — the shape the dedupe is for.

    Six commits, four distinct states: no lock at all, then A, A again (a commit that touched
    only source), B, B again, then C. A donor's history looks like this — most commits do not
    move dependencies, which is the entire reason warming per lock rather than per commit turns
    hundreds of syncs into dozens.
    """
    repo = tmp_path / "donor"
    repo.mkdir()
    _git(["init", "--quiet", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "fixture@example.invalid"], cwd=repo)
    _git(["config", "user.name", "Fixture"], cwd=repo)
    _commit(repo, lock=None, version="0.1.0", message="before uv")
    _commit(repo, lock=LOCK_A, version="0.2.0", message="adopt uv")
    _commit(repo, lock=LOCK_A, version="0.2.1", message="source only, lock untouched")
    _commit(repo, lock=LOCK_B, version="0.3.0", message="bump a dependency")
    _commit(repo, lock=LOCK_B, version="0.3.1", message="source only again")
    _commit(repo, lock=LOCK_C, version="0.4.0", message="bump another")
    return repo


def test_unique_locks_returns_one_commit_per_distinct_lockfile(donor: Path) -> None:
    """Three distinct locks across six commits, and the commit with no lock is not one of them.

    The count is the point of the whole unit. Measured on the real donors this was written for,
    664 commits carried 36 distinct locks and a second donor carried 6 — so warming per commit
    would be an order of magnitude more work for an identical cache.
    """
    found = unique_locks(donor)

    assert len(found) == 3, f"expected one commit per distinct lock, got {found}"
    assert len({one.digest for one in found}) == 3, "a lock was represented twice"
    assert len({one.sha for one in found}) == 3


def test_unique_locks_walks_newest_first(donor: Path) -> None:
    """The representative of each lock is the newest commit carrying it, and C comes first.

    Newest-first matters on an interrupted warm: the locks a mine is most likely to draw from
    are the recent ones, so a run that dies halfway has still warmed the half that gets used.
    """
    found = unique_locks(donor)
    contents = [
        subprocess.run(
            ["git", "show", f"{one.sha}:uv.lock"],
            cwd=str(donor),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        for one in found
    ]

    assert contents == [LOCK_C, LOCK_B, LOCK_A]


def test_unique_locks_skips_the_commits_that_carry_no_lockfile(donor: Path) -> None:
    """A pre-uv commit is not a warmable state, and it is skipped rather than failing the walk.

    Every real donor has a prehistory. Refusing the whole warm because the repository once
    predated its own lockfile would make the command useless on exactly the repositories it was
    written for.
    """
    found = unique_locks(donor)
    first = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        cwd=str(donor),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert first not in {one.sha for one in found}


def test_materialise_writes_the_lock_and_the_manifest_of_the_same_commit(
    donor: Path, tmp_path: Path
) -> None:
    """Both files come from one commit, which is the only thing that makes the sync meaningful.

    A lock from one commit beside a manifest from another is not a state the donor was ever in,
    and `uv sync --frozen` would either refuse it or — worse — warm a resolution that never
    existed. They are read from the same tree for that reason and the pairing is asserted here
    rather than trusted to the order of two statements.
    """
    oldest = unique_locks(donor)[-1]

    where = materialise(donor, oldest, tmp_path / "work")

    assert (where / "uv.lock").read_text() == LOCK_A
    assert (where / "pyproject.toml").read_text() == MANIFEST.format(version="0.2.1")


def test_warm_syncs_each_distinct_lock_exactly_once(donor: Path, tmp_path: Path) -> None:
    """The report counts locks, not commits, and every one of them was handed to the runner."""
    seen: list[Path] = []

    report = warm(donor, work=tmp_path / "work", run=lambda project: seen.append(project) or True)

    assert isinstance(report, WarmReport)
    assert report.unique == 3
    assert report.warmed == 3
    assert report.failed == ()
    assert len(seen) == 3
    assert len({one.resolve() for one in seen}) == 3, "two locks warmed into one directory"


def test_warm_names_the_locks_that_failed_rather_than_only_counting_them(
    donor: Path, tmp_path: Path
) -> None:
    """A failure has to be actionable, and a count is not.

    Anti-vacuity for the test above: with every sync succeeding, a `warm` that never inspected
    the runner's answer would pass it. Here one lock fails and the report has to say which.
    """
    doomed = unique_locks(donor)[1].digest

    report = warm(
        donor,
        work=tmp_path / "work",
        run=lambda project: project.name != doomed,
    )

    assert report.unique == 3
    assert report.warmed == 2
    assert [one.digest for one in report.failed] == [doomed]


def test_warm_continues_past_a_failure(donor: Path, tmp_path: Path) -> None:
    """One donor commit that cannot resolve must not cost the operator the other thirty-five.

    The warm is the slow part of bringing up a machine; abandoning it on the first failure would
    mean re-running the whole thing to make progress, which is how a documented precondition
    becomes one people skip.
    """
    report = warm(donor, work=tmp_path / "work", run=lambda project: False)

    assert report.unique == 3
    assert report.warmed == 0
    assert len(report.failed) == 3


def test_the_default_runner_does_not_pass_offline() -> None:
    """The one command in this project that MUST reach the network.

    `tasks/environment.py` puts `--offline` on every installing command it runs, and this module
    sits next to it. Copying that flag here would produce a warm that reads as though it worked —
    exit 0, every lock "warmed" — while filling the cache with nothing, and the next mine would
    fail exactly as it does today with the remedy apparently already applied. `--frozen` and
    `--no-install-project` are asserted for a smaller reason: the donor's own package is not
    what a task environment needs, and resolving instead of reading the lock would warm a
    resolution the donor never recorded.
    """
    from whetstone.tasks.warm import UV_SYNC

    assert "--offline" not in UV_SYNC
    assert "--frozen" in UV_SYNC
    assert "--no-install-project" in UV_SYNC


def test_the_digest_is_of_the_lockfile_and_an_operator_can_recompute_it(donor: Path) -> None:
    """The digest is in the record because it is what the dedupe decided on, and it is checkable.

    Reporting commits alone would leave an operator unable to say why 664 commits became 36 and
    unable to check the claim. Recomputed here from the bytes git holds, so the assertion is
    about the digest actually reported and not about a second implementation of it.
    """
    found = unique_locks(donor)

    for one in found:
        raw = subprocess.run(
            ["git", "show", f"{one.sha}:uv.lock"],
            cwd=str(donor),
            check=True,
            capture_output=True,
        ).stdout
        assert one.digest == hashlib.sha256(raw).hexdigest()[: len(one.digest)]

    assert isinstance(found[0], LockedCommit)


def test_an_offline_cache_miss_names_the_warm_command() -> None:
    """The failure an operator actually meets has to point at the remedy, not just the symptom.

    This is the third and least obvious half of #41. The precondition can be documented in
    `CONTRIBUTING.md` and made executable as a command, and the operator will still meet it as
    "Network connectivity is disabled, but the requested data wasn't found in the cache" —
    forty-five times, once per rejected candidate — which reads like a broken machine. Nobody
    reads a setup guide *after* a command has already failed; they read the error. So the error
    carries the remedy.
    """
    from whetstone.tasks.environment import explain_failure

    message = explain_failure(
        ("sync", "--frozen", "--offline"),
        "error: Failed to download `cryptography==49.0.0`\n"
        "  Caused by: Network connectivity is disabled, but the requested data wasn't found "
        "in the cache",
    )

    assert "warm-cache" in message
    assert "cryptography==49.0.0" in message, "the original failure must survive the remedy"


def test_a_failure_that_is_not_a_cache_miss_gets_no_remedy() -> None:
    """Anti-vacuity, and it matters more than it looks.

    A remedy stapled to every uv failure is worse than none: the operator learns to skip the
    sentence, and the one time it was the actual cause it reads like boilerplate. So the message
    is only extended for the signature it can actually explain.
    """
    from whetstone.tasks.environment import explain_failure

    message = explain_failure(
        ("sync", "--frozen", "--offline"),
        "error: The lockfile at `uv.lock` needs to be updated, but `--frozen` was provided",
    )

    assert "warm-cache" not in message
    assert "needs to be updated" in message


def test_the_warm_is_a_command_in_this_repository(donor: Path, tmp_path: Path) -> None:
    """The #34 lesson, applied: a procedure that lives in a runbook gets re-derived, differently.

    This warm was first done as a shell script written on the machine that needed it, which is
    exactly how the portability arm's driver came to live off-repo. Asserted through `main` and
    not through `warm` so that the argument parsing, the exit code and the summary are covered
    too — those are the parts an operator actually touches.
    """
    from whetstone.cli import main

    code = main(["warm-cache", "--donor", str(donor), "--work", str(tmp_path / "w"), "--dry-run"])

    assert code == 0


def test_a_dry_run_reports_the_work_without_doing_any(
    donor: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The number an operator needs before committing a machine to it, without the wait.

    A warm on a real donor is dozens of syncs over a possibly slow link. Being able to ask "how
    many, and is the dedupe finding what I expect?" first is the difference between running it
    and skipping it.
    """
    from whetstone.cli import main

    code = main(["warm-cache", "--donor", str(donor), "--work", str(tmp_path / "w"), "--dry-run"])
    printed = capsys.readouterr().out

    assert code == 0
    assert "3 distinct" in printed, f"the distinct-lock count is not in the summary: {printed!r}"
    assert not (tmp_path / "w").exists() or not any((tmp_path / "w").iterdir())


def test_the_command_exits_nonzero_when_a_lock_could_not_be_warmed(
    donor: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partly warmed cache is not a warmed cache, and the exit code has to say so.

    Otherwise the setup script that calls this passes, mining starts, and the failure resurfaces
    as the wall of rejections this whole unit exists to prevent — one step later and further from
    its cause.
    """
    import whetstone.cli as cli

    monkeypatch.setattr(cli.warm_cache, "_uv_sync", lambda project: False)

    code = cli.main(["warm-cache", "--donor", str(donor), "--work", str(tmp_path / "w")])

    assert code == 1
