"""What a commit actually did to its tests: `fail_to_pass`, `pass_to_pass`, and what to discard.

A commit does not state which tests it fixed. It *did* something, and the only honest way to
know what is to run the tests at the parent with the child's test files in place, run them again
with the fix applied, and diff the outcomes. That is what this module does, three times.

**The tree the first run happens in is exactly the tree STRICT verifies in.** `base_commit` is
the parent; the child's versions of the held test files are laid over it; and STRICT's
unconditional restore (`strict.py:180-183`) reproduces that same overlay from `test_blobs` before
every reward run. The overlay **is** the test patch (PRD § 5.4). There is no separate test-patch
mechanism here and none should be built.

**Ids are minted through `strict.py`'s own `read_report`, never hand-built and never through
`--collect-only`.** A second implementation drifts in exactly the ways `node_id` exists to
prevent — where a module path ends and a class begins, whether a parametrised `[1-2]` suffix
survives — and the drift does not present as a bug in this file. It presents as every ingested
task failing the executed-set check with nothing about the task to explain it. `--collect-only`
is refused for a different reason: it reports what pytest *would* run, and a task's declaration
has to be what pytest *did* run.

**D-A: each run covers only the held test files, never the donor's whole suite.** Two full-suite
runs per candidate across 60 to 80 tasks is the difference between minutes and many hours (belay
alone reports 832 tests; contig has 224 mintable candidates). The cost is stated rather than
hidden: `pass_to_pass` means "the other tests in these same files", so a regression elsewhere in
the donor's suite is not something the resulting task would catch. Every minted task records
`pass_to_pass_scope: "held-files"` in its provenance so no future reader mistakes the corpus for
something broader. It does not weaken the reward — STRICT still asserts the executed set exactly
— it bounds what the task is *about*.

**A flaky id is discarded, not recorded.** An id whose outcome is not reproducible makes a task
whose verdict is a coin toss, and a coin toss in the corpus is a number the report cannot stand
behind. Measured on the synthetic donor: without the third run, a test that fails-passes-fails
across successive runs is recorded as a perfectly ordinary `fail_to_pass`.

No model, no network. The one step that executes code runs inside the Seatbelt sandbox.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from whetstone.tasks.donor import Candidate, run_git
from whetstone.tasks.held import held_paths
from whetstone.verify.repo import apply_patch
from whetstone.verify.sandbox import run_confined
from whetstone.verify.strict import _JUNIT_FAMILY, _PYTEST_CONFIG, read_report
from whetstone.verify.verdict import Status

#: What `pass_to_pass` is scoped to, recorded in every minted task's provenance (D-A). A corpus
#: whose `pass_to_pass` is narrower than a reader assumes is a corpus that overstates itself, and
#: the fix for that is a field, not a footnote.
PASS_TO_PASS_SCOPE = "held-files"

_CHECKOUT_NAME = "repo"
_CONFIG_NAME = "whetstone-pytest.ini"

#: The three runs, in order: the red one at the parent, the green one after the gold patch, and
#: the repeat of the green one that catches an id whose outcome is not reproducible.
_BEFORE, _AFTER, _REPEAT = "before", "after", "repeat"

#: The two exit statuses that mean pytest ran the suite and reached a conclusion — the same pair
#: `strict.py:275-295` reads. Anything else (interrupted, internal error, usage error, nothing
#: collected) means it did not, and a derivation built on a run that concluded nothing would be
#: inventing a task out of an accident.
_CONCLUSIVE = frozenset({0, 1})


class NotDerivable(ValueError):
    """This candidate cannot become a task, with the reason named.

    Raised rather than returning an empty `Derived`, because "nothing flipped" and "the run never
    completed" are different facts and only the first is a finding about the commit. The caller
    records the reason and moves on to the next candidate; nothing is dropped silently.
    """


@dataclass(frozen=True)
class Derived:
    """What the three runs concluded about one candidate.

    `discarded` is carried rather than dropped so the mint can record it in provenance. An id
    that was thrown away for being non-reproducible is evidence about the donor's suite, and a
    corpus that quietly shrank is one whose denominator nobody chose.
    """

    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    discarded: tuple[str, ...]


def derive(
    donor: Path,
    candidate: Candidate,
    *,
    scratch: Path,
    timeout: float,
    interpreter: Path | str | None = None,
    import_roots: Sequence[str] = (),
    checkout: Path | None = None,
) -> Derived:
    """Run the candidate red, then green, then green again, and diff the outcomes.

    `timeout` has no default, matching `run_confined` and `verify_strict`: a limit inherited from
    somewhere else turns every slow donor into an unexplained refusal. `interpreter` is the python
    the donor's tests run under; `None` means this process's own, which is right for a donor whose
    dependencies are already installed and wrong for one that needs provisioning — that is Phase
    4's job, and this function takes the answer rather than resolving it.

    `import_roots` is where inside the checkout the donor keeps the code its tests import, and it
    is taken rather than inferred for the same reason. It matters here and not only in the reward
    because the provisioned venv deliberately carries **no** copy of the donor's project
    (`environment.capture`): a `src`-layout donor whose roots were not passed would import
    nothing at all, and the derivation would refuse the candidate with a collection error that
    says nothing about the commit.

    `checkout` is an existing tree at the candidate's parent, handed down by a caller that
    already made one. `None` means clone a fresh one. The miner passes its own, so that
    provisioning and derivation happen in **one** checkout: two of them is how the reward came to
    be decided by a directory that was not the one under test, and the cheapest way not to
    reintroduce that is to have only one directory.

    The held set is computed first, before any run, so a candidate that would mint a permanently
    unpassable task (`held.OverDeclaration`) is refused for the price of one git call rather than
    three pytest runs.

    `scratch` is **resolved** before anything is written into it, and that is not tidiness. macOS
    hands out `/var/...` paths that resolve to `/private/var/...`; pytest resolves them and then
    reports every test file relative to an unresolved `--rootdir` as a `../../../..` path, out of
    which no node id can be reconstructed at all. Observed, not anticipated: every derivation
    against an unresolved scratch directory failed with "the reported classname does not sit under
    the reported file", which reads like a broken report and is really a symlink.
    """
    held_paths(donor, candidate)

    workspace = Path(scratch)
    workspace.mkdir(parents=True, exist_ok=True)
    workspace = workspace.resolve()

    if checkout is None:
        checkout = workspace / _CHECKOUT_NAME
        run_git(
            ["clone", "--quiet", "--no-checkout", "--no-hardlinks", str(donor), str(checkout)],
            cwd=workspace,
        )
    checkout = checkout.resolve()
    run_git(["checkout", "--quiet", "--detach", candidate.parent], cwd=checkout)
    # The overlay, and it is the test patch. `git checkout <child> -- <paths>` writes the child's
    # bytes exactly, with no round trip through Python's text handling to translate a line ending
    # the manifest will later compare byte-for-byte.
    run_git(["checkout", candidate.sha, "--", *candidate.held_tests], cwd=checkout)

    run = partial(
        _run,
        candidate.held_tests,
        checkout=checkout,
        workspace=workspace,
        timeout=timeout,
        interpreter=interpreter,
        import_roots=import_roots,
    )

    before = run(attempt=_BEFORE)
    apply_patch(gold_patch(donor, candidate), checkout)
    after = run(attempt=_AFTER)
    repeat = run(attempt=_REPEAT)

    # An id missing from one of the two green runs is as non-reproducible as one that changed its
    # answer, so the union is compared rather than the intersection.
    flaky = {
        node_id
        for node_id in set(after) | set(repeat)
        if after.get(node_id) != repeat.get(node_id)
    }

    fail_to_pass = _flipped(before, after, flaky, from_outcome="failed")
    if not fail_to_pass:
        raise NotDerivable(
            f"commit {candidate.sha} ({candidate.subject!r}) has an empty fail_to_pass: no id in "
            f"{list(candidate.held_tests)} went from failed to passed across its own gold patch"
            + (f", and {sorted(flaky)} were discarded as non-reproducible" if flaky else "")
            + ". A task with no test that must go green rewards a patch that changed nothing"
        )
    return Derived(
        fail_to_pass=fail_to_pass,
        pass_to_pass=_flipped(before, after, flaky, from_outcome="passed"),
        discarded=tuple(sorted(flaky)),
    )


def gold_patch(donor: Path, candidate: Candidate) -> str:
    """The commit's diff with its test files taken out — the reference patch a task is proved by.

    The test files are excluded because the restore already applies them. A gold patch carrying
    them would touch a held path, which STRICT refuses outright before anything runs
    (`strict.py:168-169`), so the task's own reference patch would be rejected as a cheat.

    `--binary` because `other_paths` may hold anything a repository holds, and a patch that
    silently dropped a binary file would be a reference patch that does not reproduce the commit.
    """
    paths = [*candidate.source_paths, *candidate.other_paths]
    return run_git(
        ["diff", "--binary", "--no-color", candidate.parent, candidate.sha, "--", *paths],
        cwd=Path(donor),
    )


def _flipped(
    before: Mapping[str, str],
    after: Mapping[str, str],
    flaky: set[str],
    *,
    from_outcome: str,
) -> tuple[str, ...]:
    """Ids that ended `passed` and started `from_outcome`, minus anything non-reproducible.

    `passed` is required rather than "not failed": an `error` is not a pass, and an id absent from
    the before-run has no starting outcome to have flipped from. Sorted, so the manifest a
    re-mint produces is byte-identical to the first one.
    """
    return tuple(
        sorted(
            node_id
            for node_id, outcome in after.items()
            if outcome == "passed" and before.get(node_id) == from_outcome and node_id not in flaky
        )
    )


def _run(
    paths: Sequence[str],
    *,
    checkout: Path,
    workspace: Path,
    attempt: str,
    timeout: float,
    interpreter: Path | str | None,
    import_roots: Sequence[str],
) -> Mapping[str, str]:
    """One pytest run over the held files, confined, returning node id -> outcome.

    The flags mirror `strict.py`'s reward run and the two constants are **imported** from it
    rather than restated: an empty `-c` config so nothing in the donor configures the run, an
    explicit `--rootdir` so reported paths are repository-relative, `no:cacheprovider`, and the
    xunit1 junit family — which is the only family carrying the `file` attribute a node id is
    rebuilt from. Two spellings of that pair would be two things to keep in step, and the one
    that drifted would produce ids the reward compares against and never matches.

    `PYTHONPATH` is composed the same way for the same reason, and the sameness is the point: the
    ids this run mints are the ids the reward will compare against, so it has to be importing the
    same tree the reward will. A derivation that resolved the donor's package differently from
    the reward would mint a task nothing could ever pass, with nothing in the task to say why.

    Confined for the same reason the reward is: this is the only step in the whole source-B path
    that executes code, and running a donor's suite unconfined would let a `conftest.py` reach
    the network on a path whose defining claim is that it does not.
    """
    config = workspace / _CONFIG_NAME
    config.write_text(_PYTEST_CONFIG)
    report = workspace / f"report-{attempt}.xml"

    sandbox = run_confined(
        [
            str(interpreter) if interpreter else sys.executable,
            "-m",
            "pytest",
            "-c",
            str(config),
            "--rootdir",
            str(checkout),
            "-p",
            "no:cacheprovider",
            "-o",
            f"junit_family={_JUNIT_FAMILY}",
            f"--junit-xml={report}",
            "-q",
            *paths,
        ],
        scope=workspace,
        timeout=timeout,
        cwd=checkout,
        python_path=tuple(str((checkout / root).resolve()) for root in import_roots),
    )
    if sandbox.verdict.status is not Status.PASS:
        raise NotDerivable(f"the {attempt} run did not complete: {sandbox.verdict.message}")
    if sandbox.rc not in _CONCLUSIVE:
        raise NotDerivable(
            f"pytest exited {sandbox.rc} on the {attempt} run, so it reached no conclusion and "
            f"there is nothing to derive from it"
        )
    try:
        cases = read_report(report)
    except RuntimeError as exc:
        # `_ReportUnreadable` is private to the reward path on purpose — the message is the
        # public part of it, and it already names what could not be read.
        raise NotDerivable(f"the {attempt} run's report could not be read: {exc}") from exc
    return {case.node_id: case.outcome for case in cases}


__all__ = ["PASS_TO_PASS_SCOPE", "Derived", "NotDerivable", "derive", "gold_patch"]
