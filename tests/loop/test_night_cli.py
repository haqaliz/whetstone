"""The door: `whetstone run --night`, its flag surface, and the exit code it is allowed to return.

`docs/ROADMAP.md:399-400` names this command, and `cli.py:53-74` already fixes what a command in
this project may return: 0 for PASS, 1 for FAIL, 2 for a usage error, 3 for UNVERIFIED, and no
fifth. The night adds no new code and must not soften an existing one, so the assertions here are
about the mapping rather than about the loop — which `test_night.py` exercises end to end.

**The one that matters is the floor.** A night's task verdicts can reduce to PASS while no
candidate was written — a probe run, a capacity finding — and returning 0 for that would tell a
caller checking `rc == 0` that there is something to promote when there is not. So a night with
no checkpoint is floored at FAIL, and that is asserted directly rather than inferred from the
reduction.

The loop itself is substituted here. `cli.run_night` imports `whetstone.loop.night` **inside the
handler** (the single documented edge from a guarded root into an exempt package), so patching the
module's attribute is enough — and it is also a small proof that the import really is deferred: a
module-scope import would have been bound before the patch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from whetstone import cli
from whetstone.loop import night as loop_night
from whetstone.verify.verdict import Status

#: A complete, valid invocation. Kept here rather than inline so every test below differs from a
#: working command by exactly the thing it is about.
INVOCATION = [
    "run",
    "--night",
    "--tasks",
    "/tmp/tasks/belay",
    "--public",
    "/tmp/tasks/public",
    "--pool",
    "/tmp/tasks/public/pool.json",
    "--weights",
    "/tmp/weights",
    "--runs",
    "/tmp/runs",
    "--checkpoints",
    "/tmp/checkpoints",
    "--workspace",
    "/tmp/work",
    "--timeout",
    "900",
    "--recorded-on",
    "2026-08-20",
    "--run-id",
    "night-001",
    "--run-seed",
    "20260820",
]


@dataclass(frozen=True)
class _Night:
    """The shape `cli.run_night` reads from a night. Deliberately only the fields it reads."""

    run_id: str = "night-001"
    directory: Path = Path("/tmp/runs/night-001")
    ledger: Path = Path("/tmp/runs/night-001/ledger.json")
    checkpoint: Any = None
    checkpoint_absent: str = "this night selected no strict-PASS rollout"
    valid_split: str = ""
    status: Status = Status.FAIL
    dataset: Any = None
    heldout: Any = None


@dataclass(frozen=True)
class _Dataset:
    examples: tuple[()] = ()
    digest: str = "d" * 64
    denominator: int = 16
    unverified: int = 4
    coverage: int = 12


@dataclass(frozen=True)
class _Checkpoint:
    directory: Path = Path("/tmp/checkpoints/night-001")
    digest: str = "c" * 64


def _substitute(monkeypatch: pytest.MonkeyPatch, night: _Night) -> list[dict[str, Any]]:
    """Replace the loop with something that records what the door handed it and returns `night`."""
    calls: list[dict[str, Any]] = []

    def fake(**arguments: Any) -> _Night:
        calls.append(arguments)
        return night

    monkeypatch.setattr(loop_night, "run_night", fake)
    return calls


def test_the_help_for_the_night_door_exits_zero() -> None:
    """A `--help` advertising work the code cannot do is the failure `cli.py` exists to avoid."""
    assert cli.main(["run", "--help"]) == cli.PASS_EXIT


def test_run_without_night_is_a_usage_error() -> None:
    """`whetstone run` with nothing behind it would exit 0 having done nothing.

    Required rather than implied, so that a later `run --day` cannot silently inherit the meaning
    of this one — and so that the bare command is a usage error rather than a no-op success.
    """
    assert cli.main(["run", "--tasks", "/tmp/x"]) == cli.USAGE_ERROR


def test_an_unknown_flag_is_a_usage_error() -> None:
    """argparse's own code, unchanged: "you invoked me wrongly" is not a finding about a run."""
    assert cli.main([*INVOCATION, "--sample-more"]) == cli.USAGE_ERROR


def test_the_door_passes_every_declared_input_through_to_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Thin dispatch, asserted: the flags reach the loop with the names the loop declares.

    A door that dropped `--run-seed` would run a night at whatever the loop defaulted to and the
    ledger would record a seed the draws were not taken under — a reproducibility claim that is
    false in the one direction nobody checks.
    """
    calls = _substitute(monkeypatch, _Night(dataset=_Dataset(), checkpoint=_Checkpoint()))
    cli.main(INVOCATION)

    assert len(calls) == 1, calls
    passed = calls[0]
    assert passed["run_seed"] == 20260820 and passed["run_id"] == "night-001"
    assert passed["tasks"] == [Path("/tmp/tasks/belay")]
    assert passed["runs"] == Path("/tmp/runs") and passed["checkpoints"] == Path("/tmp/checkpoints")
    assert passed["recorded_on"] == "2026-08-20" and passed["timeout"] == 900.0
    assert passed["retries"] is True, (
        "WHY THIS IS A FAILURE: the night ran under the un-hardened contract by default. The "
        "hardened contract is the one the evidence for this candidate was produced under; "
        "--no-retries is the flag that opts out, and the ledger records which ran"
    )


def test_no_retries_reaches_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """The opt-out exists and is not merely documented."""
    calls = _substitute(monkeypatch, _Night(dataset=_Dataset(), checkpoint=_Checkpoint()))
    cli.main([*INVOCATION, "--no-retries"])
    assert calls[0]["retries"] is False


def test_a_night_that_wrote_a_candidate_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """The only way to exit 0: a checkpoint on disk. That is what the command exists to produce."""
    _substitute(
        monkeypatch,
        _Night(dataset=_Dataset(), checkpoint=_Checkpoint(), status=Status.FAIL),
    )
    assert cli.main(INVOCATION) == cli.PASS_EXIT


def test_a_night_with_no_candidate_never_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """The floor — asserted with the task verdicts reduced to PASS, which is the trap.

    A probe night, or one stopped by a capacity finding, can perfectly well have solved every task
    it drew against. Reducing those verdicts gives PASS, and returning it would tell a caller
    checking `rc == 0` that there is a candidate to promote.
    """
    _substitute(monkeypatch, _Night(dataset=_Dataset(), checkpoint=None, status=Status.PASS))
    assert cli.main(INVOCATION) == cli.FAIL_EXIT, (
        "WHY THIS IS A FAILURE: a night that produced no candidate exited 0 because its task "
        "verdicts happened to reduce to PASS. `run --night` exists to produce a candidate; "
        "'the loop ran and produced nothing to promote' is a finding, never a success"
    )


def test_an_unverified_night_exits_three(monkeypatch: pytest.MonkeyPatch) -> None:
    """UNVERIFIED is not 0 and not the usage code — the honesty contract at the process boundary."""
    _substitute(monkeypatch, _Night(dataset=_Dataset(), checkpoint=None, status=Status.UNVERIFIED))
    assert cli.main(INVOCATION) == cli.UNVERIFIED_EXIT


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (loop_night.ManyCandidates("two candidates, narrow with --only"), cli.USAGE_ERROR),
        (loop_night.EmptyTaskSet("no source-B task survived"), cli.USAGE_ERROR),
    ],
)
def test_an_operators_error_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, raised: Exception, expected: int
) -> None:
    """A refusal an operator can fix by retyping the command is 2, not a traceback.

    The distinction `cli.py` already draws: a traceback says the harness is broken and invites the
    same command again, while a usage error names what was wrong with the invocation.
    """

    def fake(**_: Any) -> _Night:
        raise raised

    monkeypatch.setattr(loop_night, "run_night", fake)
    assert cli.main(INVOCATION) == expected


def test_an_unproven_harness_is_unverified_rather_than_a_usage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"The control arm proved nothing" is a finding about a run, not a typo.

    Collapsing it into the usage code would put a broken verifier in the same bucket as a
    misspelled flag, and those have entirely different remedies.
    """
    from whetstone.bakeoff.sweep import HarnessNotProven

    def fake(**_: Any) -> _Night:
        raise HarnessNotProven("no probe reached INTACT")

    monkeypatch.setattr(loop_night, "run_night", fake)
    assert cli.main(INVOCATION) == cli.UNVERIFIED_EXIT


def test_the_disclosure_reaches_the_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Coverage and the unverified count are printed, not merely written into the ledger.

    `docs/ROADMAP.md:430-435` requires the unverified rate to be reported from the first eval
    onward. A number that exists only in a JSON file under a gitignored root is not reported to
    the person who ran the night.
    """
    _substitute(monkeypatch, _Night(dataset=_Dataset(), checkpoint=_Checkpoint()))
    cli.main(INVOCATION)

    printed = capsys.readouterr().out
    assert "unverified" in printed and "coverage" in printed, printed
    assert "c" * 64 in printed, (
        "WHY THIS IS A FAILURE: the candidate's digest was not printed, so the operator cannot "
        f"tell which checkpoint this night produced without opening the ledger. Got {printed!r}"
    )
