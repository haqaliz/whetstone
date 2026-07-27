"""THE REWARD. What a policy is paid for, and every way it is refused.

STRICT runs seven steps in this order, and the order is the design:

1. materialise `base_commit` into a fresh checkout inside the run directory;
2. **refuse the patch outright if it touches any path in `test_blobs`** — before anything
   runs, so the refusal is its own outcome and never "the tests failed afterwards";
3. restore every operator-held test from golden, always, after the patch;
4. run pytest over `fail_to_pass + pass_to_pass` inside the sandbox, environment pinned;
5. assert the skipped count is zero;
6. **assert the executed node-id set equals the task's declaration exactly**, and that every
   `fail_to_pass` id reports `passed`;
7. fold the exit status and the above into `Verdict`s and `reduce` them.

**Step 6 is the one that is easy to leave out, and the reward is defeatable without it.** An
exit status answers *"did anything fail?"*. It cannot answer *"were these the tests?"*, and
that second question is what the reward actually rests on. Deselection is not skipping: `-k`,
`-m` and `--deselect` remove tests from a run without producing a single skip, and they can
arrive from `pyproject.toml`, `pytest.ini`, `setup.cfg` or a `conftest.py` — **configuration,
not test files**. None of those are in `test_blobs`, so such a patch survives step 2's refusal
and step 3's restore untouched, leaves the skipped count at zero, and exits 0 with the failing
test simply absent. Step 5 alone leaves that open. Step 6 closes it by comparing what pytest
*ran* against what the task *declared*, read from pytest's own machine-readable report rather
than from its summary line.

Steps 4's `-c`, `-p no:cacheprovider` and the sandbox's `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` are
defence in depth for the same cheat, arriving through config, cache and installed plugins
respectively. They are not the defence — they are what makes the defence not the only one.

**Absence is never a pass and never a failure.** A killed run, an unreadable report, a task
whose own golden paths are not in the checkout: each is UNVERIFIED. Those fold through
`reduce`, where UNVERIFIED outranks PASS, so a run that half-happened cannot be reported clean
by the half that did.

No model is consulted anywhere here, and none may ever be: the reward is a set comparison and
a process exit status, which is the whole reason it cannot be talked out of its answer.
"""

from __future__ import annotations

import sys
import uuid
import xml.etree.ElementTree as ElementTree
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.verify.repo import (
    CheckoutError,
    PatchError,
    apply_patch,
    declared_paths,
    materialise,
    touched_paths,
)
from whetstone.verify.sandbox import run_confined
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status, Verdict, reduce

#: Inside the run directory, so the sandbox's write scope covers the checkout, the config and
#: the report in one subtree — and so nothing the run produces lands anywhere else.
_CHECKOUT_NAME = "repo"
_CONFIG_NAME = "whetstone-pytest.ini"
_REPORT_NAME = "report.xml"

#: An empty config, and empty is the point: passed with `-c`, it is what pytest reads INSTEAD
#: of any `pyproject.toml`/`pytest.ini`/`setup.cfg` the patch may have edited. Nothing
#: configures the reward run except this file, and this file configures nothing.
_PYTEST_CONFIG = "[pytest]\n"

#: `xunit1` is requested because it is the only family that carries the `file` attribute, and
#: without the file path a node id cannot be reconstructed exactly — `classname` alone cannot
#: say where the module path ends and a class name begins. Guessing there would put an
#: ambiguity inside the comparison the reward depends on.
_JUNIT_FAMILY = "xunit1"

#: A ceiling on the untrusted report, generous enough that a large real suite's failures fit
#: and small enough that a report grown to fill the disk is refused rather than parsed. See
#: `_read_report` for why this file is untrusted at all.
_MAX_REPORT_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class StrictResult:
    """The reward, its grounding, and what actually ran.

    Deliberately free of paths, durations and captured output: two runs of the same task and
    patch must compare equal (M10), and a run directory or a millisecond count in here would
    make "identical verdict" untestable. `verdicts` carries the sub-checks with their `kind`,
    so a caller can ask *why* — "the executed set did not match" is a different fact from "a
    test failed", and the adversarial corpus asserts on exactly that distinction. `executed`
    is the node-id set pytest reported running, or None when no report could be read.

    Its field names are disjoint from `WeakResult`'s, which is not an accident; see `weak`.
    """

    status: Status
    verdicts: tuple[Verdict, ...]
    executed: tuple[str, ...] | None


def verify_strict(
    task: Task,
    patch: str,
    *,
    sandbox_root: Path | str,
    timeout: float,
    run_id: str | None = None,
) -> StrictResult:
    """Verify `patch` against `task` and return the reward.

    `timeout` has no default, matching `sandbox.run_confined`: a default inherited from
    somewhere else turns every slow task into an UNVERIFIED nobody can explain. `run_id` names
    the directory the run happens in and nothing else — the verdict does not depend on it, and
    `test_the_verdict_is_identical_across_repeated_runs` is what holds that true.
    """
    run_directory = Path(sandbox_root) / (run_id or uuid.uuid4().hex)
    checkout = run_directory / _CHECKOUT_NAME
    run_directory.mkdir(parents=True, exist_ok=True)

    try:
        materialise(task, checkout)
    except CheckoutError as exc:
        return _only(
            "checkout",
            Status.UNVERIFIED,
            f"the task could not be materialised, so nothing was checked: {exc}",
        )

    absent = tuple(path for path in sorted(task.test_blobs) if not (checkout / path).is_file())
    if absent:
        return _only(
            "task-blobs",
            Status.UNVERIFIED,
            "the task declares operator-held tests that are not in the checkout, so there is "
            "nothing to restore them over; the task is malformed, not the patch",
            observed=absent,
            expected=(),
        )

    try:
        early = declared_paths(patch, checkout)
    except PatchError as exc:
        return _only("patch-apply", Status.FAIL, f"{exc}; an unusable patch is a wrong answer")

    held = _held_among(early, task)
    if held:
        return _refused(held)

    try:
        apply_patch(patch, checkout)
    except PatchError as exc:
        return _only("patch-apply", Status.FAIL, f"{exc}; an unusable patch is a wrong answer")

    held = _held_among(touched_paths(checkout), task)
    if held:
        return _refused(held)

    # Step 3. Always, and over the whole set — not only the paths the patch happened to name.
    # The restore is what makes the reward a statement about the OPERATOR'S tests.
    for path, golden in task.test_blobs.items():
        (checkout / path).write_bytes(golden)

    return _run_and_judge(task, checkout=checkout, run_directory=run_directory, timeout=timeout)


def _run_and_judge(
    task: Task, *, checkout: Path, run_directory: Path, timeout: float
) -> StrictResult:
    """Steps 4 to 7: run the declared tests confined, then judge what actually happened."""
    config = run_directory / _CONFIG_NAME
    config.write_text(_PYTEST_CONFIG)
    report = run_directory / _REPORT_NAME
    declared = (*task.fail_to_pass, *task.pass_to_pass)

    sandbox = run_confined(
        [
            sys.executable,
            "-m",
            "pytest",
            # Never the repository's own config: the patch may have edited it, and this is the
            # cheapest of cheat 7's several doors to lock.
            "-c",
            str(config),
            # With `-c` pointing outside the checkout, pytest would otherwise take the config's
            # directory as the rootdir and report every path with a `repo/` prefix, which no
            # task's node ids would ever match.
            "--rootdir",
            str(checkout),
            "-p",
            "no:cacheprovider",
            "-o",
            f"junit_family={_JUNIT_FAMILY}",
            f"--junit-xml={report}",
            "-q",
            *declared,
        ],
        scope=run_directory,
        timeout=timeout,
        cwd=checkout,
    )
    if sandbox.verdict.status is not Status.PASS:
        # The run did not complete. Reading a report or an exit status now would be reading
        # something no process produced.
        return StrictResult(
            status=reduce([sandbox.verdict]), verdicts=(sandbox.verdict,), executed=None
        )

    verdicts = [_exit_status_verdict(sandbox.rc)]
    try:
        cases = _read_report(report)
    except _ReportUnreadable as exc:
        verdicts.append(
            Verdict(
                kind="report",
                status=Status.UNVERIFIED,
                observed=None,
                expected=None,
                message=(
                    f"pytest's report could not be read, so what ran is unknown: {exc}. "
                    f"An exit status with no report behind it is not a pass"
                ),
            )
        )
        return StrictResult(status=reduce(verdicts), verdicts=tuple(verdicts), executed=None)

    executed = tuple(case.node_id for case in cases)
    outcomes = {case.node_id: case.outcome for case in cases}
    verdicts.append(_skipped_verdict(cases))
    verdicts.append(_executed_set_verdict(executed, declared))
    verdicts.append(_fail_to_pass_verdict(outcomes, task.fail_to_pass))
    return StrictResult(status=reduce(verdicts), verdicts=tuple(verdicts), executed=executed)


def _exit_status_verdict(rc: int | None) -> Verdict:
    """pytest's own answer to "did anything fail?" — the necessary half, never the sufficient one.

    0 and 1 are the two statuses that mean pytest ran the suite and reached a conclusion.
    Everything else — interrupted, internal error, usage error, nothing collected — means it
    did not, and a run that reached no conclusion is UNVERIFIED rather than a failure to
    attribute to the patch.
    """
    if rc == 0:
        status, detail = Status.PASS, "every test pytest ran passed"
    elif rc == 1:
        status, detail = Status.FAIL, "at least one test failed"
    else:
        status, detail = Status.UNVERIFIED, "pytest did not run the suite to a conclusion"
    return Verdict(
        kind="pytest",
        status=status,
        observed=rc,
        expected=0,
        message=f"pytest exited {rc}: {detail}",
    )


def _skipped_verdict(cases: Sequence[_Case]) -> Verdict:
    """Step 5. A skipped test is a test that did not run, and the task asked for it to run."""
    skipped = tuple(case.node_id for case in cases if case.outcome == "skipped")
    if not skipped:
        return Verdict(
            kind="skipped",
            status=Status.PASS,
            observed=0,
            expected=0,
            message="no declared test was skipped",
        )
    return Verdict(
        kind="skipped",
        status=Status.FAIL,
        observed=sorted(skipped),
        expected=0,
        message=(
            f"{len(skipped)} declared test(s) were skipped rather than run; a skipped test "
            f"proves nothing about the patch"
        ),
    )


def _executed_set_verdict(executed: Sequence[str], declared: Sequence[str]) -> Verdict:
    """Step 6. The check an exit status structurally cannot make.

    Set equality, plus a count, so a test that ran twice is a mismatch rather than a silent
    equality. The message names both halves of the difference, because "the executed set did
    not match" without saying how is a rejection nobody can act on.
    """
    missing = sorted(set(declared) - set(executed))
    unexpected = sorted(set(executed) - set(declared))
    if not missing and not unexpected and len(executed) == len(declared):
        return Verdict(
            kind="executed-set",
            status=Status.PASS,
            observed=sorted(executed),
            expected=sorted(declared),
            message="pytest ran exactly the tests the task declared",
        )
    return Verdict(
        kind="executed-set",
        status=Status.FAIL,
        observed=sorted(executed),
        expected=sorted(declared),
        message=(
            f"pytest did not run the tests the task declared: {len(missing)} never ran "
            f"({missing}) and {len(unexpected)} ran that were not declared ({unexpected}). "
            f"An exit status cannot see this"
        ),
    )


def _fail_to_pass_verdict(outcomes: Mapping[str, str], fail_to_pass: Sequence[str]) -> Verdict:
    """The tests the task exists for. Each must report `passed` — not merely "not failed"."""
    unpassed = sorted(
        node_id for node_id in fail_to_pass if outcomes.get(node_id, "absent") != "passed"
    )
    if not unpassed:
        return Verdict(
            kind="fail-to-pass",
            status=Status.PASS,
            observed=sorted(fail_to_pass),
            expected=sorted(fail_to_pass),
            message="every fail-to-pass test reported passed",
        )
    return Verdict(
        kind="fail-to-pass",
        status=Status.FAIL,
        observed={node_id: outcomes.get(node_id, "absent") for node_id in unpassed},
        expected="passed",
        message=f"{len(unpassed)} fail-to-pass test(s) did not report passed: {unpassed}",
    )


@dataclass(frozen=True)
class _Case:
    """One `<testcase>` from pytest's report: which node ran, and what it reported."""

    node_id: str
    outcome: str


class _ReportUnreadable(RuntimeError):
    """The report is absent, malformed, or missing what a node id is reconstructed from.

    Its own exception so the caller cannot mistake it for "nothing ran" — an empty report and
    an unreadable one are different facts, and only the first is a finding about the patch.
    """


def _read_report(path: Path) -> tuple[_Case, ...]:
    """Read pytest's junit XML into node ids and outcomes. Never guesses.

    The node id is rebuilt from `file` and `classname` rather than from `classname` alone:
    `tests.test_a.TestC` cannot be split into module and class without knowing the file, and a
    wrong split would quietly change which ids the executed-set comparison sees. A `testcase`
    with no `file` is therefore an unreadable report, not a case to interpret generously.

    **This XML is untrusted.** The report is written inside the sandbox's write scope, which
    is the one place the run under test *can* write — a patch's own `conftest.py` can overwrite
    it with anything at all. The usual answer to untrusted XML is `defusedxml`, and the reward
    path may not take a third-party dependency, so the two attacks stdlib ElementTree is open
    to are refused before the parser is handed anything: entity declarations (billion-laughs
    and friends) and sheer size. pytest emits neither a doctype nor an entity, so refusing them
    costs nothing and each refusal is UNVERIFIED — never a default pass.
    """
    if not path.is_file():
        raise _ReportUnreadable("pytest wrote no report at all")
    if path.stat().st_size > _MAX_REPORT_BYTES:
        raise _ReportUnreadable(
            f"the report is larger than {_MAX_REPORT_BYTES} bytes, which no run of a declared "
            f"test list produces; it was not parsed"
        )
    raw = path.read_bytes()
    for construct in (b"<!DOCTYPE", b"<!ENTITY"):
        if construct in raw:
            raise _ReportUnreadable(
                f"the report contains {construct.decode()}, which pytest never emits; it was "
                f"not parsed"
            )
    try:
        tree = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise _ReportUnreadable(f"the report is not well-formed XML: {exc}") from exc

    cases: list[_Case] = []
    for element in tree.iter("testcase"):
        file_path = element.get("file")
        name = element.get("name")
        classname = element.get("classname")
        if file_path is None or name is None or classname is None:
            raise _ReportUnreadable(
                f"a testcase entry lacks file/classname/name ({element.attrib!r}), so the node "
                f"id it reports cannot be reconstructed"
            )
        cases.append(_Case(node_id=_node_id(file_path, classname, name), outcome=_outcome(element)))
    return tuple(cases)


def _node_id(file_path: str, classname: str, name: str) -> str:
    """`tests/test_a.py` + `tests.test_a.TestC` + `test_x` -> `tests/test_a.py::TestC::test_x`."""
    dotted = file_path[: -len(".py")] if file_path.endswith(".py") else file_path
    dotted = dotted.replace("/", ".")
    if classname == dotted:
        enclosing: list[str] = []
    elif classname.startswith(f"{dotted}."):
        enclosing = classname[len(dotted) + 1 :].split(".")
    else:
        raise _ReportUnreadable(
            f"the reported classname {classname!r} does not sit under the reported file "
            f"{file_path!r}, so the node id cannot be reconstructed"
        )
    return "::".join([file_path, *enclosing, name])


def _outcome(element: ElementTree.Element) -> str:
    """What the case reported. `passed` only when nothing said otherwise."""
    for tag, outcome in (("skipped", "skipped"), ("failure", "failed"), ("error", "error")):
        if element.find(tag) is not None:
            return outcome
    return "passed"


def _held_among(paths: Sequence[str], task: Task) -> tuple[str, ...]:
    """Which of `paths` are operator-held tests.

    Compared case-insensitively as well as exactly. The reward runs on macOS, whose default
    filesystem is case-insensitive, so a patch aimed at `Tests/Test_Addition.py` would reach
    the very file `test_blobs` holds while comparing unequal to it. The restore would still
    put the golden bytes back, but the refusal is a separate guarantee and it should not have
    a spelling-shaped hole in it.
    """
    held = {path: path.casefold() for path in task.test_blobs}
    folded = set(held.values())
    return tuple(sorted({path for path in paths if path in held or path.casefold() in folded}))


def _refused(held: Sequence[str]) -> StrictResult:
    """Step 2's outcome: a distinct fact, reached before pytest was ever invoked."""
    return _only(
        "patch-scope",
        Status.FAIL,
        f"the patch touches operator-held test path(s) {list(held)}, so it was refused before "
        f"anything ran; the tests the reward is measured against are not the policy's to edit",
        observed=tuple(held),
        expected=(),
    )


def _only(kind: str, status: Status, message: str, **grounding: Any) -> StrictResult:
    """A result decided by a single sub-check. Never an empty verdict set — see `reduce`."""
    verdict = Verdict(
        kind=kind,
        status=status,
        observed=grounding.get("observed"),
        expected=grounding.get("expected"),
        message=message,
    )
    return StrictResult(status=reduce([verdict]), verdicts=(verdict,), executed=None)


__all__ = ["StrictResult", "verify_strict"]
