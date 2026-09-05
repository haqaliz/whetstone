"""The door: `whetstone check-probe --run <runs/id>`, its flag surface, and its exits.

`docs/planning/p2-rollouts/night-door/runbook.md:78-80` pre-commits the go/no-go rule — the
night proceeds iff the probe completes with the control arm `PASS` on every draw and a
non-empty seed map — so the exit code is the deliverable and it is asserted at the process
boundary, not only against the core: `cli.main(["check-probe", "--run", <dir>])` reads one
probe run directory's ledger and returns the code an operator's sheet can branch on.

The codes are the CLI's existing four-code contract (`cli.py:64-84`), no fifth: the rule
holds → 0, a named violation → 1 (a draw whose harness is not `PASS`, or an empty seed map —
the night does not run behind it, and that is a finding, not a mistyped command), and a
refusal an operator can fix by retyping — a directory that is not a probe run, a ledger that
cannot be read, an incomplete run — → 2. There is no `UNVERIFIED` exit here: the command
reads documents rather than running anything, so it either answers or refuses.

No model, no `mlx`, no network: the fixtures are the `check-core` suite's own real `Ledger`
documents, shared by import.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loop.test_check_probe import _probe_run
from whetstone import cli
from whetstone.loop import night
from whetstone.verify.verdict import Status


def _argv(run: Path) -> list[str]:
    """The command line, in the order the runbook writes it."""
    return ["check-probe", "--run", str(run)]


def test_check_probe_exits_zero_for_a_valid_probe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC1: the pre-committed rule holds — exit 0, with the decision on stdout."""
    run = _probe_run(tmp_path / "runs" / "probe-001")

    code = cli.main(_argv(run))
    out = capsys.readouterr().out

    assert code == 0, out
    assert "PROCEED" in out, out


def test_check_probe_exits_one_naming_the_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC2: a doctored fold exits 1 — the violation is a finding on stdout, never a usage error."""
    run = _probe_run(
        tmp_path / "runs" / "probe-001",
        harness={night.PRIVATE: Status.PASS, night.PUBLIC: Status.FAIL},
    )

    code = cli.main(_argv(run))
    captured = capsys.readouterr()

    assert code == 1, captured.out
    assert "DO NOT PROCEED" in captured.out, captured.out
    assert "draw 1 (public)" in captured.out, captured.out
    assert captured.err == "", captured.err


def test_check_probe_exits_two_on_a_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC3: refusals are 2 and name what an operator can fix — stdout stays silent, never a traceback."""
    full_night = _probe_run(tmp_path / "runs" / "night-001", probe=None)
    not_a_run = _probe_run(tmp_path / "loose", ledger=False)

    code = cli.main(_argv(full_night))
    captured = capsys.readouterr()
    assert code == 2, captured.out
    assert captured.out == "", captured.out
    assert "whetstone check-probe:" in captured.err
    assert "not a probe run" in captured.err

    code = cli.main(_argv(not_a_run))
    captured = capsys.readouterr()
    assert code == 2, captured.out
    assert captured.out == "", captured.out
    assert "whetstone check-probe:" in captured.err
    assert "ledger.json" in captured.err