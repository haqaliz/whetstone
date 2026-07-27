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

import sys
from pathlib import Path

import pytest
from fixtures.repos import CALC_FIXED, build_task, make_patch

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
