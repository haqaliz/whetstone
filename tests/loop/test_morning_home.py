"""Where a morning report may be written, and the one carve-out that makes it possible.

A morning report is the user's own data — counts and digests derived from private donor code —
and its home was pre-declared before the loop existed: `.gitignore` reserves `/reports/local/`
with a comment naming *"the morning reports"*.

That creates a tension the night does not have. `night._refuse_published_root` refuses **any**
path with a `reports` component, and `reports/local/` is inside `reports/`, so importing the
night's predicate by identity would refuse this unit's own documented home. The rule here is its
narrower sibling — and the carve-out is not invented by this file. It is already recognised twice
in the tree: by `.gitignore` itself, and by the one-home guard, which filters `reports/local/`
out of the published-artifact list with the argument that *"`.gitignore` reserves it for the
user's own nightly output, which is their data and never ours to assert on"*
(`tests/bakeoff/test_report.py:2076-2077`).

The assertions that would actually catch a regression are the last two: a `.gitignore` edit is
the single change that turns every private artefact in this project into a commit, and the
end-to-end one catches the case where the ignore rule exists but a path shape dodges it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from whetstone.bakeoff.run import TranscriptNotPrivate
from whetstone.loop import morning
from whetstone.loop.night import PUBLISHED

#: The repository root, reached from `tests/loop/`.
REPO_ROOT = Path(__file__).resolve().parents[2]


def _check_ignore(path: str) -> subprocess.CompletedProcess[str]:
    """`git check-ignore -v`, run against the real repository.

    Trailing-slash form at the call sites, deliberately: `/reports/local/` is a directory-only
    pattern, and `git check-ignore reports/local` answers "not ignored" whenever the directory
    does not exist — a false alarm rather than a finding.
    """
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-v", path],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_published_root_outside_the_carve_out_is_refused(tmp_path: Path) -> None:
    """`reports/` is the one directory in this tree an outside reader is expected to read."""
    with pytest.raises(TranscriptNotPrivate) as refused:
        morning.refuse_published_out(tmp_path / PUBLISHED / "nightly", "--out")
    assert "--out" in str(refused.value) and PUBLISHED in str(refused.value), refused.value


def test_the_carve_out_is_accepted(tmp_path: Path) -> None:
    """The control, without which a predicate that refused everything would pass every test here.

    `reports/local/` is the documented home. A rule that refused it would be perfectly safe and
    completely useless, and every other assertion in this file would still be green.
    """
    accepted = tmp_path / PUBLISHED / morning.LOCAL / "nightly" / "night-001"
    morning.refuse_published_out(accepted, "--out")


def test_a_gitignored_root_outside_reports_is_accepted(tmp_path: Path) -> None:
    """The predicate is about `reports/`, not about being fussy: an ordinary path is fine."""
    morning.refuse_published_out(tmp_path / "runs" / "night-001", "--out")


def test_the_check_is_on_the_resolved_path(tmp_path: Path) -> None:
    """`reports/local/../baseline` names a path inside a published home while comparing unequal.

    The check has to hold against the path that gets written, not the one that got typed — the
    `night.py:620-622` argument, which is why the night resolves too.
    """
    dodge = tmp_path / PUBLISHED / morning.LOCAL / ".." / "baseline" / "x"
    with pytest.raises(TranscriptNotPrivate):
        morning.refuse_published_out(dodge, "--out")


def test_a_symlink_into_a_published_directory_is_refused(tmp_path: Path) -> None:
    """A scratch directory that is a symlink into `reports/` resolves to a published path."""
    published = tmp_path / PUBLISHED / "baseline"
    published.mkdir(parents=True)
    link = tmp_path / "scratch"
    link.symlink_to(published, target_is_directory=True)

    with pytest.raises(TranscriptNotPrivate):
        morning.refuse_published_out(link / "night-001", "--out")


def test_a_symlink_into_the_carve_out_is_accepted(tmp_path: Path) -> None:
    """The symlink control: resolving is not itself a refusal."""
    home = tmp_path / PUBLISHED / morning.LOCAL / "nightly"
    home.mkdir(parents=True)
    link = tmp_path / "scratch"
    link.symlink_to(home, target_is_directory=True)

    morning.refuse_published_out(link / "night-001", "--out")


def test_the_refusal_and_the_published_name_are_reused_by_identity() -> None:
    """One name in this repository for "private evidence was pointed at a published path".

    Two exception classes meaning the same thing is how a caller ends up catching one of them.
    """
    assert morning.TranscriptNotPrivate is TranscriptNotPrivate
    assert morning.PUBLISHED is PUBLISHED


def test_the_documented_home_is_gitignored() -> None:
    """The assertion that would actually catch the regression.

    A `.gitignore` edit is the one change that turns every private artefact in this project into a
    commit, and it would look entirely innocent in a diff.
    """
    ignored = _check_ignore("reports/local/")
    assert ignored.returncode == 0, (
        "WHY THIS IS A FAILURE: reports/local/ is not gitignored. It is the morning report's "
        f"documented home and holds the user's own nightly output. git said: {ignored.stderr!r}"
    )
    assert "reports/local" in ignored.stdout, ignored.stdout


def test_the_gitignore_check_can_fail() -> None:
    """Anti-vacuity: a broken `check-ignore` invocation would pass the test above silently.

    A typo in the argument list, a `git` that is not on PATH, a `-C` pointing somewhere without a
    repository — each returns non-zero or empty output, and the assertion above would then be
    proving something about a subprocess rather than about this repository.
    """
    not_ignored = _check_ignore("README.md")
    assert not_ignored.returncode != 0, (
        "WHY THIS IS A FAILURE: git reported README.md as ignored, which it is not. The "
        "check-ignore invocation is not measuring what the test above thinks it measures"
    )


def test_the_one_home_guard_still_carves_out_reports_local() -> None:
    """This unit's home exists only because the published-figure guard excludes it by name.

    Asserted rather than assumed: a later tightening that dropped the carve-out would make every
    morning report a published figure the guard demands be listed, and the failure would surface
    in the guard rather than here — where the reason lives.
    """
    guard = (REPO_ROOT / "tests" / "bakeoff" / "test_report.py").read_text(encoding="utf-8")
    assert 'startswith("reports/local/")' in guard, (
        "WHY THIS IS A FAILURE: the one-home guard no longer filters reports/local/ out of the "
        "published-artifact list. The morning report writes there precisely because that guard "
        "declares it the user's own data and not ours to assert on; without the carve-out, this "
        "unit's home is a published home and the argument for it is gone"
    )


def test_a_report_written_to_the_carve_out_does_not_reach_git(tmp_path: Path) -> None:
    """End to end, against the real repository: the ignore rule and the path shape agree.

    The gitignore assertion above proves a pattern matches a string. This proves the file the
    writer would actually produce is invisible to `git status` — which is the property that
    matters, and the one that a pattern matching a differently-shaped path would not give.
    """
    home = REPO_ROOT / PUBLISHED / morning.LOCAL / "nightly" / "canary-run"
    artifact = home / "report.md"
    try:
        home.mkdir(parents=True, exist_ok=True)
        artifact.write_text("# canary\n", encoding="utf-8")
        status = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "canary-run" not in status.stdout, (
            "WHY THIS IS A FAILURE: a morning report written to its documented home showed up as "
            f"an untracked file. git status said:\n{status.stdout}"
        )
    finally:
        artifact.unlink(missing_ok=True)
        for directory in (home, home.parent):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
