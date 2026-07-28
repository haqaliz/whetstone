"""The honesty contract at the process boundary: what `whetstone verify` exits with.

Everything inside the verifier reduces UNVERIFIED above PASS, and none of that survives a
CLI that maps every non-failure to 0. A caller — a shell script, a nightly loop, CI — reads a
process exit status, so the distinction between "the patch is good", "the patch is wrong" and
"nothing could be checked" has to be legible there or it does not exist for the caller at all.

Hence the two-sided assertions below. UNVERIFIED is asserted to be 3, and separately asserted
NOT to be 0 (which would report an unchecked run as a win) and NOT to be 2 (which would make
"the eval could not be completed" indistinguishable from "you typed the command wrong"). The
same holds for what is printed: a caller reading stdout must not find a result that says PASS
when nothing was verified.

Real fixtures, real git, real pytest in a real sandbox — `tests/fixtures/repos` — so an exit
code here is one the whole reward path actually produced, not one a stub agreed to return.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from fixtures.repos import BROKEN_ADDER, CALC_FIXED, RepoSpec, build_task, make_patch

from whetstone.cli import FAIL_EXIT, PASS_EXIT, UNVERIFIED_EXIT, USAGE_ERROR, main
from whetstone.verify.sandbox import UnsupportedPlatform

#: The three tests that reach the reward run the Seatbelt sandbox, which is macOS-only. The
#: argument-handling tests below deliberately carry no such marker: they must run everywhere.
requires_sandbox = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="the reward runs inside the Seatbelt sandbox, which is macOS-only",
)


def _write_patch(tmp_path: Path, diff: str) -> Path:
    path = tmp_path / "patch.diff"
    path.write_text(diff)
    return path


@requires_sandbox
def test_a_genuinely_fixing_patch_exits_zero_and_says_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The anti-vacuity control: a CLI that exited non-zero always would satisfy the rest."""
    fixture = build_task(tmp_path)
    patch = _write_patch(tmp_path, make_patch(fixture.origin, {"calc.py": CALC_FIXED}))

    returncode = main(["verify", "--task", str(tmp_path / "task.json"), "--patch", str(patch)])

    captured = capsys.readouterr()
    assert returncode == PASS_EXIT, captured
    assert returncode == 0
    assert "PASS" in captured.out


@requires_sandbox
def test_a_non_fixing_patch_exits_one_and_names_the_failing_sub_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A wrong answer is 1, and the output says WHICH check refused it, not merely that one did."""
    fixture = build_task(tmp_path)
    patch = _write_patch(
        tmp_path,
        make_patch(fixture.origin, {"calc.py": "def add(a, b):\n    return a - b  # hm\n"}),
    )

    returncode = main(["verify", "--task", str(tmp_path / "task.json"), "--patch", str(patch)])

    captured = capsys.readouterr()
    assert returncode == FAIL_EXIT, captured
    assert returncode == 1
    assert "FAIL" in captured.out
    assert "fail-to-pass" in captured.out, "the output does not say which check refused the patch"


@requires_sandbox
def test_an_unverifiable_run_exits_three_and_does_not_read_as_a_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A task whose own golden path is absent from the checkout: nothing could be checked.

    The patch is the genuinely fixing one, so the only reason this is not a PASS is that the
    task is malformed — which is exactly the case a caller must not read as a win.
    """
    fixture = build_task(tmp_path, extra_blobs={"tests/test_not_in_the_repo.py": b"# absent\n"})
    patch = _write_patch(tmp_path, make_patch(fixture.origin, {"calc.py": CALC_FIXED}))

    returncode = main(["verify", "--task", str(tmp_path / "task.json"), "--patch", str(patch)])

    captured = capsys.readouterr()
    assert returncode == UNVERIFIED_EXIT, captured
    assert returncode == 3
    assert "UNVERIFIED" in captured.out
    assert "task-blobs" in captured.out
    assert "PASS" not in captured.out, "an unverified run printed something that reads as a pass"


@requires_sandbox
def test_unverified_never_exits_zero_and_never_exits_the_usage_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The honesty contract, asserted as its two failure modes rather than as its value.

    `== 3` alone would still pass if 3 were later redefined; these two say what 3 is FOR. 0
    would pay a reward for a run nobody checked, and 2 would fold "could not evaluate" into
    argparse's "you invoked me wrongly", which is a different fact with a different remedy.
    """
    fixture = build_task(tmp_path, extra_blobs={"tests/test_not_in_the_repo.py": b"# absent\n"})
    patch = _write_patch(tmp_path, make_patch(fixture.origin, {"calc.py": CALC_FIXED}))

    returncode = main(["verify", "--task", str(tmp_path / "task.json"), "--patch", str(patch)])

    capsys.readouterr()
    assert returncode != 0, "an unverified run exited 0; every caller reads that as a win"
    assert returncode != USAGE_ERROR, (
        "an unverified run exited with the usage code; 'could not evaluate' and 'you typed "
        "the command wrong' must stay distinguishable"
    )


def test_a_missing_task_file_is_a_usage_failure_not_an_unverified_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing was verified here either, but nothing was ATTEMPTED — that is a usage error.

    Collapsing it into UNVERIFIED would put "the operator gave me a path that is not there"
    into the same bucket as "the reward ran and could not conclude", and the second is a
    finding about a task while the first is a typo.
    """
    patch = _write_patch(tmp_path, "irrelevant\n")

    returncode = main(
        ["verify", "--task", str(tmp_path / "no-such-task.json"), "--patch", str(patch)]
    )

    captured = capsys.readouterr()
    assert returncode == USAGE_ERROR, captured
    assert returncode != UNVERIFIED_EXIT
    assert "no-such-task.json" in captured.err
    assert "PASS" not in captured.out


def test_a_malformed_task_file_is_a_usage_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unreadable and unparseable are the same class of problem, and `load_task` says which."""
    manifest = tmp_path / "task.json"
    manifest.write_text("{not json")
    patch = _write_patch(tmp_path, "irrelevant\n")

    returncode = main(["verify", "--task", str(manifest), "--patch", str(patch)])

    captured = capsys.readouterr()
    assert returncode == USAGE_ERROR, captured
    assert "task.json" in captured.err


def test_a_missing_patch_file_is_a_usage_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An absent patch file is not an empty patch, and must not be verified as one."""
    fixture = build_task(tmp_path)
    assert fixture.task.task_id

    returncode = main(
        [
            "verify",
            "--task",
            str(tmp_path / "task.json"),
            "--patch",
            str(tmp_path / "no-such-patch.diff"),
        ]
    )

    captured = capsys.readouterr()
    assert returncode == USAGE_ERROR, captured
    assert returncode != UNVERIFIED_EXIT
    assert "no-such-patch.diff" in captured.err


def test_a_platform_with_no_sandbox_is_unverified_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Off macOS the reward cannot run at all, and that is a verdict, not a traceback.

    The condition is injected rather than provoked because this suite runs on the one platform
    where it cannot happen. What is under test is the CLI's translation — an environment that
    cannot contain a run is UNVERIFIED, never a usage error and never a pass — not the
    sandbox's own refusal, which `test_sandbox.py` already pins.
    """
    fixture = build_task(tmp_path)
    assert fixture.task.task_id
    patch = _write_patch(tmp_path, "irrelevant\n")

    def refuse(*args: object, **kwargs: object) -> object:
        raise UnsupportedPlatform("the Seatbelt sandbox is macOS-only")

    monkeypatch.setattr("whetstone.cli.verify_strict", refuse)

    returncode = main(["verify", "--task", str(tmp_path / "task.json"), "--patch", str(patch)])

    captured = capsys.readouterr()
    assert returncode == UNVERIFIED_EXIT, captured
    assert returncode not in (0, USAGE_ERROR)
    assert "UNVERIFIED" in captured.out
    assert "PASS" not in captured.out


def test_verify_without_its_required_flags_is_a_usage_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """argparse's own refusal, translated — `verify` with no task cannot mean anything."""
    assert main(["verify"]) == USAGE_ERROR
    capsys.readouterr()


def test_the_four_exit_codes_are_four_distinct_values() -> None:
    """The table in the PRD is only a contract if no two rows collide."""
    codes = (PASS_EXIT, FAIL_EXIT, USAGE_ERROR, UNVERIFIED_EXIT)
    assert codes == (0, 1, 2, 3)
    assert len(set(codes)) == len(codes)


# --------------------------------------------------------------------------------------------
# A directory of tasks. The honesty contract does not weaken when the denominator grows: the
# set reduces worst-status-wins through the same `verdict.reduce` a single task does, so one
# unverified task among passes exits 3. There is deliberately no fifth exit code — "some of
# them passed" is not a fourth kind of outcome, it is a PASS the caller has not earned.
# --------------------------------------------------------------------------------------------

_SHOUTER_BUGGY = "def shout(text):\n    return text\n"

_SHOUTER_TEST = """\
from shouter import shout


def test_shout_upper_cases():
    assert shout("hi") == "HI"
"""

#: A second task in the same corpus, about a DIFFERENT bug. Its `calc.py` is byte-identical to
#: `BROKEN_ADDER`'s, so the adder's patch applies cleanly and fixes the adder's own test — and
#: then leaves this task's other declared test failing, because `shouter.py` is untouched. That
#: is what makes the mixed-verdict run below honest: one patch, correct for one task and a wrong
#: answer for another, rather than a patch rigged to fail or one that never applied.
SECOND_BUG = RepoSpec(
    files={
        **BROKEN_ADDER.files,
        "shouter.py": _SHOUTER_BUGGY,
        "tests/test_shout.py": _SHOUTER_TEST,
    },
    fail_to_pass=(*BROKEN_ADDER.fail_to_pass, "tests/test_shout.py::test_shout_upper_cases"),
    pass_to_pass=BROKEN_ADDER.pass_to_pass,
    held=(*BROKEN_ADDER.held, "tests/test_shout.py"),
    problem_statement="add() subtracts, and shout() does not shout.",
)


def _build_suite(
    tmp_path: Path,
    entries: tuple[tuple[str, RepoSpec, dict[str, bytes] | None], ...],
) -> tuple[Path, Path]:
    """Materialise one manifest per entry into a shared directory.

    Returns the directory and the first entry's origin, which is what the patch is generated
    against. Each task gets its own root because `build_task` writes a fixed `task.json`; the
    manifests are then copied in under their task ids, which is the shape ingestion will emit.
    """
    directory = tmp_path / "suite"
    directory.mkdir()
    first_origin: Path | None = None
    for task_id, spec, extra_blobs in entries:
        fixture = build_task(tmp_path / task_id, spec, task_id=task_id, extra_blobs=extra_blobs)
        shutil.copyfile(tmp_path / task_id / "task.json", directory / f"{task_id}.json")
        first_origin = first_origin or fixture.origin
    assert first_origin is not None, "an empty suite proves nothing; pass at least one entry"
    return directory, first_origin


@requires_sandbox
def test_a_directory_of_passing_tasks_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The anti-vacuity control for the two mixed runs below: a whole directory CAN pass."""
    directory, origin = _build_suite(
        tmp_path,
        (
            ("adder-a", BROKEN_ADDER, None),
            ("adder-b", BROKEN_ADDER, None),
            ("adder-c", BROKEN_ADDER, None),
        ),
    )
    patch = _write_patch(tmp_path, make_patch(origin, {"calc.py": CALC_FIXED}))

    returncode = main(["verify", "--task", str(directory), "--patch", str(patch)])

    captured = capsys.readouterr()
    assert returncode == PASS_EXIT, captured
    for task_id in ("adder-a", "adder-b", "adder-c"):
        assert f"{task_id}: PASS" in captured.out, "a task in the directory went unreported"


@requires_sandbox
def test_one_unverifiable_task_among_passes_exits_three(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Worst-status-wins across the set: two passes cannot outvote one unchecked task.

    This is the honesty contract at the only scale that matters for a corpus. A directory is
    how the nightly loop will be pointed at its tasks, and a reduction that let the majority
    decide would pay a reward for a set containing a task nobody could check.
    """
    directory, origin = _build_suite(
        tmp_path,
        (
            ("adder-a", BROKEN_ADDER, None),
            ("adder-b", BROKEN_ADDER, None),
            ("malformed", BROKEN_ADDER, {"tests/test_not_in_the_repo.py": b"# absent\n"}),
        ),
    )
    patch = _write_patch(tmp_path, make_patch(origin, {"calc.py": CALC_FIXED}))

    returncode = main(["verify", "--task", str(directory), "--patch", str(patch)])

    captured = capsys.readouterr()
    assert returncode == UNVERIFIED_EXIT, captured
    assert returncode != PASS_EXIT
    assert "malformed: UNVERIFIED" in captured.out
    assert "task-blobs" in captured.out, "the UNVERIFIED does not say which check could not run"
    assert "malformed: PASS" not in captured.out, (
        "the unverified task was rendered as a pass; UNVERIFIED is never a win"
    )


@requires_sandbox
def test_one_failing_task_among_passes_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A wrong answer for one task is a wrong answer for the set — and it is FAIL, not UNVERIFIED.

    The distinction is the whole reason UNVERIFIED exists: everything here was checked, and one
    task's declared test did not pass. Collapsing that into "could not conclude" would hide a
    real refusal behind an abstention.
    """
    directory, origin = _build_suite(
        tmp_path,
        (
            ("adder-a", BROKEN_ADDER, None),
            ("adder-b", BROKEN_ADDER, None),
            ("shouter", SECOND_BUG, None),
        ),
    )
    patch = _write_patch(tmp_path, make_patch(origin, {"calc.py": CALC_FIXED}))

    returncode = main(["verify", "--task", str(directory), "--patch", str(patch)])

    captured = capsys.readouterr()
    assert returncode == FAIL_EXIT, captured
    assert "shouter: FAIL" in captured.out
    assert "fail-to-pass" in captured.out, (
        "the FAIL is not grounded in the declared test; a patch that failed to APPLY would "
        "also exit 1, and that would be a different fact"
    )
    assert "UNVERIFIED" not in captured.out, (
        "nothing here was unverifiable; an UNVERIFIED in the output means the FAIL above was "
        "reached for the wrong reason"
    )


def test_an_empty_task_directory_is_a_usage_error_not_a_vacuous_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Zero tasks is a malformed invocation, not a verdict — and above all not a green one.

    An empty set that reduces to success is the vacuous-green lie, and it is the cheapest way
    to fake a perfect night: point the loop at a directory holding nothing and every task in it
    passed. It is a usage error rather than UNVERIFIED for the reason the module already draws
    that line — nothing was attempted, and the operator gave a path with nothing behind it.
    """
    directory = tmp_path / "empty"
    directory.mkdir()
    patch = _write_patch(tmp_path, "irrelevant\n")

    returncode = main(["verify", "--task", str(directory), "--patch", str(patch)])

    captured = capsys.readouterr()
    assert returncode == USAGE_ERROR, captured
    assert returncode != PASS_EXIT
    assert "no task manifests" in captured.err, (
        f"the refusal does not say what was wrong with the directory: {captured.err!r}"
    )
    assert "PASS" not in captured.out


@pytest.mark.parametrize("intruder", ["notes.txt", "leftovers/"])
def test_a_directory_entry_that_is_not_a_task_is_a_usage_error_naming_it(
    tmp_path: Path, intruder: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """No silent skipping: a task quietly dropped from the run is a missing denominator.

    Skipping the stray file would make the set smaller than the operator believes it is, and
    every rate computed over it — the verified-gain number this project exists to publish —
    would have a denominator nobody chose. Refusing loudly costs one message; skipping silently
    costs the number its meaning.
    """
    directory, _ = _build_suite(tmp_path, (("adder-a", BROKEN_ADDER, None),))
    if intruder.endswith("/"):
        (directory / intruder.rstrip("/")).mkdir()
    else:
        (directory / intruder).write_text("not a manifest\n")
    patch = _write_patch(tmp_path, "irrelevant\n")

    returncode = main(["verify", "--task", str(directory), "--patch", str(patch)])

    captured = capsys.readouterr()
    assert returncode == USAGE_ERROR, captured
    assert intruder.rstrip("/") in captured.err, (
        f"the refusal does not name what it refused: {captured.err!r}"
    )
    assert "PASS" not in captured.out
