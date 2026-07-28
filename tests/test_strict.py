"""Pins the reward: what it pays for, and — mostly — what it refuses to pay for.

The failure this file prevents is a reward that reads a clean exit status and calls it a
win. Every test below is a way for pytest to exit 0 while nothing the task asked for actually
happened, and the one that matters most is
``test_deselection_is_caught_by_the_executed_set_and_not_by_the_exit_status``: a patch that
touches no test file, produces no skip, and exits 0, having quietly removed the failing test
from the run. An exit status answers *"did anything fail?"* and cannot answer *"were these
the tests?"* — so the executed node-id set is compared against the task's declaration, and
that comparison is the thing standing between the loop and a reward it invented.

The other axis is honesty about absence. A run the sandbox killed, a report that could not be
read, a task whose own golden paths are missing — none of those are wrong answers, and none
of them may reduce to PASS or to FAIL. They are UNVERIFIED, asserted here rather than assumed.

Real ``sandbox-exec``, real git, real pytest-in-a-subprocess. The repositories are synthetic
and built at test time (``tests/fixtures/repos``).
"""

from __future__ import annotations

import dataclasses
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fixtures.repos import (
    BROKEN_ADDER,
    CALC_FIXED,
    DESELECTING_CONFTEST,
    EXITING_CONFTEST,
    HANGING_CONFTEST,
    SKIPPING_CONFTEST,
    RepoSpec,
    build_task,
    make_patch,
    rename_patch,
)

from whetstone.verify.strict import (
    StrictResult,
    _held_among,
    _ReportUnreadable,
    read_report,
    verify_strict,
)
from whetstone.verify.verdict import Status

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="the reward runs inside the Seatbelt sandbox, which is macOS-only",
)

#: Generous enough that a slow machine is not reported as an unverifiable task, short enough
#: that a genuinely hung run does not hold the suite. The fixture suites run in milliseconds.
_TIMEOUT = 120.0


def _status_of(result: StrictResult, kind: str) -> Status:
    """The sub-verdict a named check produced, so a test can assert WHY, not just what."""
    matching = [verdict for verdict in result.verdicts if verdict.kind == kind]
    assert matching, f"no {kind!r} verdict in {[v.kind for v in result.verdicts]}"
    return matching[0].status


@pytest.fixture(scope="session")
def alternate_interpreter(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A second, real Python installation with its own ``pytest``, on its own path.

    A *real* venv rather than a wrapper script, because the claim being tested is that a task
    can run under an interpreter that is not the verifier's — an installation with its own
    prefix and its own ``site-packages``, which a shell shim re-execing the verifier's own
    python would not be. It is built from ``sys.executable``, so no interpreter is ever
    downloaded and the fixture cannot drift on whichever pythons a machine happens to have;
    what differs is the installation, not the version, and the installation is the part
    ``sys.executable`` in the argv decides.

    ``--offline`` is not a nicety. Every test in this suite runs without the network, and a
    fixture that reached PyPI would make the reward's own test suite depend on what an index
    served that morning — the precise failure the ``environment`` contract exists to refuse.
    ``uv sync`` puts pytest in uv's cache before pytest ever runs, here and in CI, so the
    cache is warm by construction.

    Session-scoped: it costs about a tenth of a second, and paying that once is the difference
    between a fixture worth having and one a future reader deletes.
    """
    if shutil.which("uv") is None:
        raise RuntimeError(
            "uv is not on PATH, so a second interpreter cannot be built. This suite is run as "
            "`uv run pytest`; raising rather than skipping, because a silently skipped test of "
            "the interpreter seam is a green suite that proves nothing about it."
        )

    venv = tmp_path_factory.mktemp("alternate-interpreter") / "venv"
    _uv(["venv", "--quiet", "--python", sys.executable, str(venv)])
    python = venv / "bin" / "python"
    _uv(["pip", "install", "--quiet", "--offline", "--python", str(python), "pytest"])

    assert list(venv.glob("lib/python*/site-packages/pytest")), (
        f"{venv} has no pytest of its own, so it is not a second installation and any test "
        f"passing through it would be proving nothing"
    )
    return python


def _uv(args: list[str]) -> None:
    """uv, with its failure surfaced in full — a half-built venv fails later and opaquely."""
    completed = subprocess.run(["uv", *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"uv {' '.join(args)} failed: {completed.stderr.strip()}")


def _interpreter_probe_repo(expected: Path) -> RepoSpec:
    """A repository whose one test passes only when run by the installation at ``expected``.

    This is how "the argv changed" is asserted rather than assumed: a test that merely accepted
    the ``interpreter`` keyword would pass whether or not the value ever reached the command
    line. Here the *interpreter under which pytest is running* is the thing under assertion, so
    the only way to green is for that path to have been exec'd.

    **``sys.prefix``, deliberately, and not ``Path(sys.executable).resolve()``** — the obvious
    spelling, which was written first and silently passed under both interpreters. A venv's
    ``bin/python`` is a symlink to the interpreter it was built from, and this fixture builds
    from ``sys.executable``, so resolving collapses the alternate venv and the verifier's own
    venv onto the same base binary and compares it against itself. ``sys.prefix`` is the venv
    directory and survives that, which makes it the thing that actually distinguishes one
    installation from another. Both sides are still resolved, for the unrelated reason that
    macOS hands out symlinked temp roots (``/var`` -> ``/private/var``).
    """
    prefix = str(expected.parent.parent)
    source = (
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def test_runs_under_the_nominated_interpreter():\n"
        f"    assert Path(sys.prefix).resolve() == Path({prefix!r}).resolve()\n"
    )
    return RepoSpec(
        files={"noop.py": "VALUE = 1\n", "tests/test_interpreter.py": source},
        fail_to_pass=("tests/test_interpreter.py::test_runs_under_the_nominated_interpreter",),
        pass_to_pass=(),
        held=("tests/test_interpreter.py",),
    )


def test_a_patch_that_genuinely_fixes_the_bug_is_a_pass(tmp_path: Path) -> None:
    """The anti-vacuity control for every rejection test below: a real fix does earn a PASS.

    Without it, a verifier that rejected everything unconditionally would satisfy the whole
    rest of this file.
    """
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"calc.py": CALC_FIXED})

    result = verify_strict(
        fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=_TIMEOUT
    )

    assert result.status is Status.PASS, result.verdicts


def test_a_patch_that_does_not_fix_the_bug_is_a_fail(tmp_path: Path) -> None:
    """An edit that leaves the failing test failing is a wrong answer, not an unverified one."""
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"calc.py": "def add(a, b):\n    return a - b  # hm\n"})

    result = verify_strict(
        fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=_TIMEOUT
    )

    assert result.status is Status.FAIL, result.verdicts


def test_a_patch_touching_an_operator_held_test_is_rejected_before_pytest_runs(
    tmp_path: Path,
) -> None:
    """AC 10: the rejection is a distinct outcome, not "the tests failed afterwards".

    Asserted by the absence of a report: if no junit XML was written anywhere under the run
    directory, no pytest process got as far as finishing, so the rejection cannot have been a
    test result in disguise.
    """
    fixture = build_task(tmp_path)
    patch = make_patch(
        fixture.origin,
        {"tests/test_addition.py": "def test_add_is_addition():\n    assert True\n"},
    )

    sandbox_root = tmp_path / "sandbox"
    result = verify_strict(fixture.task, patch, sandbox_root=sandbox_root, timeout=_TIMEOUT)

    assert result.status is Status.FAIL, result.verdicts
    assert _status_of(result, "patch-scope") is Status.FAIL
    assert not list(sandbox_root.rglob("*.xml")), "a report exists, so pytest was run anyway"


def test_deselection_is_caught_by_the_executed_set_and_not_by_the_exit_status(
    tmp_path: Path,
) -> None:
    """Cheat 7, and the reason step 6 of the reward exists.

    The patch adds a root ``conftest.py`` that deselects the failing test. It touches no path
    in ``test_blobs``, so the scope check passes it; deselection is not skipping, so the
    skipped count is zero; and the tests that remain all pass, so **pytest exits 0**. Every
    check the roadmap listed is satisfied and the bug is still there.

    The assertion is deliberately two-sided: the executed-set verdict must be FAIL *and* the
    exit-status verdict must not be, because if the exit status had caught it this test would
    pass while proving nothing about the check it was written for.
    """
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"conftest.py": DESELECTING_CONFTEST})

    result = verify_strict(
        fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=_TIMEOUT
    )

    assert result.status is Status.FAIL, result.verdicts
    assert _status_of(result, "executed-set") is Status.FAIL
    assert _status_of(result, "pytest") is not Status.FAIL, (
        "the exit status caught this, so the test no longer demonstrates that the "
        "executed-set assertion is load-bearing"
    )


def test_a_patch_that_renames_an_operator_held_test_away_is_also_refused(tmp_path: Path) -> None:
    """The pre-apply check alone does not see this, which is why there is a second one.

    ``git apply --numstat`` reports a rename by its DESTINATION path only — verified against
    git on this machine — so a patch that moves ``tests/test_addition.py`` somewhere else
    declares only the new path and slips past the check that runs before anything touches the
    disk. Asking git what actually differs after the patch lands catches it.
    """
    fixture = build_task(tmp_path)
    patch = rename_patch(fixture.origin, "tests/test_addition.py", "tests/moved_aside.py")

    sandbox_root = tmp_path / "sandbox"
    result = verify_strict(fixture.task, patch, sandbox_root=sandbox_root, timeout=_TIMEOUT)

    assert result.status is Status.FAIL, result.verdicts
    assert _status_of(result, "patch-scope") is Status.FAIL
    assert not list(sandbox_root.rglob("*.xml")), "a report exists, so pytest was run anyway"


def test_a_patch_that_does_not_apply_is_a_fail_and_not_unverified(tmp_path: Path) -> None:
    """A policy that emitted an unusable diff produced a wrong answer, not an unreadable one.

    Both shapes, because they take different routes through the code: one is a well-formed
    diff whose context does not match the checkout, the other is not a diff at all.
    """
    fixture = build_task(tmp_path)
    stale = (
        "diff --git a/calc.py b/calc.py\n"
        "--- a/calc.py\n"
        "+++ b/calc.py\n"
        "@@ -1 +1 @@\n"
        "-this line was never in calc.py\n"
        "+def add(a, b): return a + b\n"
    )
    gibberish = "I am confident this fixes it.\n"

    for patch in (stale, gibberish):
        result = verify_strict(
            fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=_TIMEOUT
        )
        assert result.status is Status.FAIL, (patch, result.verdicts)
        assert _status_of(result, "patch-apply") is Status.FAIL


def test_an_operator_held_path_missing_from_the_checkout_is_unverified(tmp_path: Path) -> None:
    """The task is malformed, not the patch — so it is neither a pass nor a failure.

    A golden path with nothing to restore it over means the run would have measured whatever
    the patch left there, which is the one thing the restore exists to prevent.
    """
    fixture = build_task(tmp_path, extra_blobs={"tests/test_not_in_the_repo.py": b"# absent\n"})
    patch = make_patch(fixture.origin, {"calc.py": CALC_FIXED})

    result = verify_strict(
        fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=_TIMEOUT
    )

    assert result.status is Status.UNVERIFIED, result.verdicts
    assert result.status is not Status.PASS
    assert _status_of(result, "task-blobs") is Status.UNVERIFIED


def test_a_declared_test_that_was_skipped_is_a_fail(tmp_path: Path) -> None:
    """Step 5. Two-sided like the deselection test: pytest still exits 0 here.

    A skip is pytest telling us it did not run the test. Reading the exit status alone, that
    is indistinguishable from having run it and been satisfied.
    """
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"conftest.py": SKIPPING_CONFTEST})

    result = verify_strict(
        fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=_TIMEOUT
    )

    assert result.status is Status.FAIL, result.verdicts
    assert _status_of(result, "skipped") is Status.FAIL
    assert _status_of(result, "pytest") is not Status.FAIL, (
        "the exit status caught this, so the test no longer demonstrates that the "
        "skipped-count assertion is load-bearing"
    )


def test_a_run_the_sandbox_could_not_finish_is_unverified_and_never_fail(tmp_path: Path) -> None:
    """A task we could not run is not a task the patch got wrong."""
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"conftest.py": HANGING_CONFTEST})

    result = verify_strict(fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=1.0)

    assert result.status is Status.UNVERIFIED, result.verdicts
    assert result.status is not Status.FAIL
    assert result.executed is None


def test_an_exit_status_with_no_report_behind_it_is_unverified_not_a_pass(tmp_path: Path) -> None:
    """The purest form of the lie this file exists to refuse.

    The patch adds a conftest that calls ``os._exit(0)`` during collection: the process ends
    with a **zero exit status** and no test has run, so there is no report to read. Read from
    the exit status alone this is a clean pass. The assertion on the ``pytest`` sub-verdict is
    the point — it *is* PASS, and the missing report overrules it through the reduction, which
    is UNVERIFIED outranking PASS doing its job on a real run rather than in a unit test.
    """
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"conftest.py": EXITING_CONFTEST})

    result = verify_strict(
        fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=_TIMEOUT
    )

    assert _status_of(result, "pytest") is Status.PASS
    assert _status_of(result, "report") is Status.UNVERIFIED
    assert result.status is Status.UNVERIFIED, result.verdicts
    assert result.executed is None


def test_the_verdict_is_identical_across_repeated_runs(tmp_path: Path) -> None:
    """M10. Same task, same patch, different run directory — the same verdict, field for field.

    Compared as whole results rather than by status: a `StrictResult` that carried a path, a
    duration or captured output would make "identical" a claim nobody could check, and this
    equality is what keeps those out.
    """
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"conftest.py": DESELECTING_CONFTEST})

    results = [
        verify_strict(
            fixture.task,
            patch,
            sandbox_root=tmp_path / "sandbox",
            timeout=_TIMEOUT,
            run_id=f"run-{attempt}",
        )
        for attempt in range(3)
    ]

    assert results[0] == results[1] == results[2], results


def test_no_outcome_is_reached_with_an_empty_verdict_set(tmp_path: Path) -> None:
    """Every path out of the reward carries its grounding.

    ``reduce([])`` is UNVERIFIED by design, which is the right floor — but a verifier that
    reached it would be returning "we could not check" with no record of what it tried, and
    nothing downstream could tell that apart from a genuine abstention.
    """
    fixture = build_task(tmp_path)
    patches = {
        "fixing": make_patch(fixture.origin, {"calc.py": CALC_FIXED}),
        "refused": make_patch(fixture.origin, {"tests/test_addition.py": "def test_x(): pass\n"}),
        "unusable": "not a diff\n",
        "deselecting": make_patch(fixture.origin, {"conftest.py": DESELECTING_CONFTEST}),
    }

    for label, patch in patches.items():
        result = verify_strict(
            fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=_TIMEOUT
        )
        assert result.verdicts, f"{label} produced a verdict-free result"


def test_a_report_that_cannot_be_read_is_refused_rather_than_interpreted(tmp_path: Path) -> None:
    """Unit-level probe of the parser, because "unparseable" must never degrade into a guess.

    Reaching for a private is deliberate: each of these reports is reachable only by a run
    that overwrites the report file, and the claim being pinned — that none of them is read
    generously — is about the parser rather than about any one way of provoking it.
    """
    cases = {
        "a testcase with no file attribute": (
            '<testsuite><testcase classname="tests.test_a" name="test_x"/></testsuite>'
        ),
        "a classname that does not sit under the file": (
            '<testsuite><testcase file="tests/test_a.py" classname="somewhere.else" '
            'name="test_x"/></testsuite>'
        ),
        "not well-formed at all": "<testsuite><testcase>",
        "an entity declaration pytest never emits": (
            '<!DOCTYPE t [<!ENTITY a "x">]><testsuite><testcase file="tests/test_a.py" '
            'classname="tests.test_a" name="test_x"/></testsuite>'
        ),
    }

    for label, xml in cases.items():
        report = tmp_path / f"{abs(hash(label))}.xml"
        report.write_text(xml)
        with pytest.raises(_ReportUnreadable):
            read_report(report)

    with pytest.raises(_ReportUnreadable):
        read_report(tmp_path / "never-written.xml")


def test_the_parser_reconstructs_node_ids_including_classes_and_parameters(
    tmp_path: Path,
) -> None:
    """Anti-vacuity for the test above: a well-formed report IS read, and read exactly.

    Without this, a parser that raised unconditionally would satisfy every unreadable case
    while making the executed-set comparison permanently UNVERIFIED — which reads as caution
    and is actually a reward that never pays.
    """
    report = tmp_path / "report.xml"
    report.write_text(
        '<testsuite>'
        '<testcase file="tests/test_a.py" classname="tests.test_a" name="test_plain"/>'
        '<testcase file="tests/test_a.py" classname="tests.test_a.TestC" name="test_method"/>'
        '<testcase file="tests/test_a.py" classname="tests.test_a" name="test_param[1-2]"/>'
        '<testcase file="tests/test_a.py" classname="tests.test_a" name="test_skipped">'
        '<skipped/></testcase>'
        '<testcase file="tests/test_a.py" classname="tests.test_a" name="test_failed">'
        '<failure/></testcase>'
        '</testsuite>'
    )

    cases = read_report(report)

    assert [case.node_id for case in cases] == [
        "tests/test_a.py::test_plain",
        "tests/test_a.py::TestC::test_method",
        "tests/test_a.py::test_param[1-2]",
        "tests/test_a.py::test_skipped",
        "tests/test_a.py::test_failed",
    ]
    assert [case.outcome for case in cases] == [
        "passed",
        "passed",
        "passed",
        "skipped",
        "failed",
    ]


def test_a_held_test_addressed_by_a_different_casing_is_still_held(tmp_path: Path) -> None:
    """macOS is case-insensitive, so ``Tests/Test_Addition.py`` IS ``tests/test_addition.py``.

    Verified against git on this machine: a patch spelling the path that way applies cleanly
    and rewrites the operator-held file, while ``git apply --numstat`` reports back the
    spelling the *patch* used. An exact match on that spelling therefore misses it.

    Asserted at the unit level deliberately. End to end the patch is refused either way,
    because after it lands git reports the tree's own canonical spelling and the second check
    catches it — so an end-to-end assertion would stay green with this comparison removed and
    would be pinning the wrong check.
    """
    fixture = build_task(tmp_path)

    assert _held_among(("Tests/Test_Addition.py",), fixture.task) == ("Tests/Test_Addition.py",)
    assert _held_among(("tests/test_addition.py",), fixture.task) == ("tests/test_addition.py",)
    assert _held_among(("calc.py",), fixture.task) == ()


def test_a_patch_addressing_a_held_test_by_a_different_casing_is_refused(tmp_path: Path) -> None:
    """The same bypass end to end: refused, and refused before pytest was invoked."""
    fixture = build_task(tmp_path)
    patch = (
        "diff --git a/Tests/Test_Addition.py b/Tests/Test_Addition.py\n"
        "--- a/Tests/Test_Addition.py\n"
        "+++ b/Tests/Test_Addition.py\n"
        "@@ -1,5 +1,2 @@\n"
        "-from calc import add\n"
        "-\n"
        "-\n"
        " def test_add_is_addition():\n"
        "-    assert add(2, 3) == 5\n"
        "+    assert True\n"
    )

    sandbox_root = tmp_path / "sandbox"
    result = verify_strict(fixture.task, patch, sandbox_root=sandbox_root, timeout=_TIMEOUT)

    assert result.status is Status.FAIL, result.verdicts
    assert _status_of(result, "patch-scope") is Status.FAIL
    assert not list(sandbox_root.rglob("*.xml")), "a report exists, so pytest was run anyway"


def test_a_task_declaring_a_held_test_non_canonically_cannot_be_built_at_all(
    tmp_path: Path,
) -> None:
    """A held path spelled ``./tests/…`` used to fall out of the rejection set. Now it is refused.

    **What was demonstrated before the loader was fixed**, with this exact fixture and a patch
    rewriting ``tests/test_addition.py``: ``verify_strict`` produced no ``patch-scope`` verdict
    whatsoever — the verdicts were ``pytest, skipped, executed-set, fail-to-pass``, meaning the
    patch reached the sandbox and pytest actually ran. ``_held_among`` compares the manifest's
    raw key against the path git reports, git reports ``tests/test_addition.py``, and
    ``./tests/test_addition.py`` matches it neither exactly nor case-folded. The unconditional
    restore still wrote the golden bytes back, so the run reported FAIL on the merits rather
    than rewarding the cheat — that is why this was a defence-in-depth hole and not a live
    reward hole. But the refusal is a separate guarantee from the restore, and it should not
    have a spelling-shaped hole in it.

    Closed at the door instead: the task can no longer be constructed, so there is no patch to
    refuse. Asserted end to end through ``build_task`` rather than at the loader — the loader's
    own cases live in ``tests/test_task_contract.py``, and what this pins is that the shape
    which reached the reward is now unreachable from a manifest.
    """
    with pytest.raises(ValueError, match="non-canonical"):
        build_task(
            tmp_path, dataclasses.replace(BROKEN_ADDER, held=("./tests/test_addition.py",))
        )


def test_omitting_the_interpreter_leaves_the_reward_exactly_as_it_was(tmp_path: Path) -> None:
    """The regression guard for the seam below: saying nothing must still mean ``sys.executable``.

    Asserted two ways, because either alone is weak. The verdict kinds and the PASS pin the
    result a caller got before the parameter existed; the equality against an *explicitly*
    nominated ``sys.executable`` pins that the default and the nomination take the same route,
    so a default that quietly resolved to something else — a venv, a version string, whatever a
    later reader is tempted to make it — fails here rather than in a training run.
    """
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"calc.py": CALC_FIXED})

    default = verify_strict(
        fixture.task,
        patch,
        sandbox_root=tmp_path / "sandbox",
        timeout=_TIMEOUT,
        run_id="unnominated",
    )
    nominated = verify_strict(
        fixture.task,
        patch,
        sandbox_root=tmp_path / "sandbox",
        timeout=_TIMEOUT,
        run_id="nominated",
        interpreter=sys.executable,
    )

    assert default.status is Status.PASS, default.verdicts
    assert [verdict.kind for verdict in default.verdicts] == [
        "pytest",
        "skipped",
        "executed-set",
        "fail-to-pass",
    ]
    assert default == nominated


def test_a_nominated_interpreter_is_the_one_the_declared_tests_run_under(
    tmp_path: Path, alternate_interpreter: Path
) -> None:
    """The seam itself, asserted through the running process rather than through the signature.

    The repository's single ``fail_to_pass`` test asserts which interpreter is executing it, so
    the two runs below differ in exactly one thing and reach opposite verdicts. The second half
    is the load-bearing one: **without** the nomination the same task, patch and fixture FAIL,
    which is what makes the first half evidence that the value reached the command line instead
    of merely being accepted by the function.
    """
    fixture = build_task(tmp_path, _interpreter_probe_repo(alternate_interpreter))
    patch = make_patch(fixture.origin, {"noop.py": "VALUE = 2\n"})

    nominated = verify_strict(
        fixture.task,
        patch,
        sandbox_root=tmp_path / "sandbox",
        timeout=_TIMEOUT,
        run_id="nominated",
        interpreter=alternate_interpreter,
    )
    default = verify_strict(
        fixture.task,
        patch,
        sandbox_root=tmp_path / "sandbox",
        timeout=_TIMEOUT,
        run_id="unnominated",
    )

    assert nominated.status is Status.PASS, nominated.verdicts
    assert default.status is Status.FAIL, default.verdicts
    assert _status_of(default, "fail-to-pass") is Status.FAIL


def test_an_interpreter_that_cannot_run_is_unverified_and_never_a_failure(
    tmp_path: Path,
) -> None:
    """A harness that could not start is not a patch that got the answer wrong.

    The patch is the genuine fix, so every one of these runs would be a PASS under a working
    interpreter. That is the point: a FAIL here would be Whetstone charging the policy for a
    broken nomination, and a PASS would be worse. Three shapes, because they leave by three
    different doors — the first two never reach a child at all and surface through the
    sandbox's own verdict, while the third exits with a status outside ``{0, 1}`` and no report
    behind it, which is ``_exit_status_verdict``'s "pytest reached no conclusion".
    """
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"calc.py": CALC_FIXED})

    unrunnable = tmp_path / "not-executable"
    unrunnable.write_text("#!/bin/sh\nexit 0\n")
    unrunnable.chmod(0o644)
    stub = tmp_path / "broken-stub"
    stub.write_text("#!/bin/sh\nexit 3\n")
    stub.chmod(0o755)

    # The `kind` is asserted too, so this pins the ROUTE and not merely the answer. A later
    # change that reached UNVERIFIED by some other door — swallowing an OSError, say — would
    # satisfy a status-only assertion while meaning something quite different.
    interpreters = {
        "absent": (tmp_path / "no-such-interpreter", "sandbox-run"),
        "not-executable": (unrunnable, "sandbox-run"),
        "broken-stub": (stub, "pytest"),
    }

    for label, (interpreter, kind) in interpreters.items():
        result = verify_strict(
            fixture.task,
            patch,
            sandbox_root=tmp_path / "sandbox",
            timeout=_TIMEOUT,
            run_id=label,
            interpreter=interpreter,
        )
        assert result.status is Status.UNVERIFIED, (label, result.verdicts)
        assert result.status is not Status.FAIL, label
        assert result.status is not Status.PASS, label
        assert result.executed is None, label
        assert _status_of(result, kind) is Status.UNVERIFIED, (label, result.verdicts)


def test_an_interpreter_outside_the_sandboxs_write_scope_is_still_usable(
    tmp_path: Path, alternate_interpreter: Path
) -> None:
    """The containment claim this feature leans on, asserted rather than assumed.

    ``sandbox.py`` says ``file-read*`` is allowed wholesale and the profile denies only
    ``network*`` and ``file-write*``, so an interpreter the run can neither write to nor create
    is still readable and executable. Nothing in the suite pinned that, and it is the whole
    reason a per-task interpreter can live wherever the ingester provisioned it rather than
    having to be copied into the run directory — which would be the sandbox quietly dictating
    the layout of a directory it was only ever asked to confine writes to.

    Anti-vacuity, in three parts, because a naive version of this test passes without the
    feature existing at all. The repository is the ``sys.prefix`` probe, so a PASS is only
    reachable by having actually run under the out-of-scope installation — with the ordinary
    adder fixture this test would go green even if ``interpreter`` were accepted and thrown
    away. The two assertions before the run then pin the other halves: that the venv is outside
    the write scope, and that it is not the verifier's own interpreter under another name.
    """
    sandbox_root = tmp_path / "sandbox"
    fixture = build_task(tmp_path, _interpreter_probe_repo(alternate_interpreter))
    patch = make_patch(fixture.origin, {"noop.py": "VALUE = 3\n"})

    assert not alternate_interpreter.is_relative_to(sandbox_root), (
        f"{alternate_interpreter} is inside the write scope, so this proves nothing about "
        f"reading one from outside it"
    )
    assert alternate_interpreter != Path(sys.executable)

    result = verify_strict(
        fixture.task,
        patch,
        sandbox_root=sandbox_root,
        timeout=_TIMEOUT,
        interpreter=alternate_interpreter,
    )

    assert result.status is Status.PASS, result.verdicts
