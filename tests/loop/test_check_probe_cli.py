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

import argparse
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
    """AC3: refusals are 2 and name what an operator can fix — stdout stays silent, never a
    traceback."""
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


def _check_probe_parser() -> argparse.ArgumentParser:
    """The `check-probe` subparser, observed directly so a renamed door is caught."""
    parser = cli.build_parser()
    subparsers = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    return subparsers[0].choices["check-probe"]


def test_the_check_probe_flag_surface() -> None:
    """The parser exposes exactly `--run`, and nothing that could change the decision.

    The flag surface is pinned because the operator's sheet will spell the command out. A
    second flag that narrowed the draw set or relaxed the fold would let a failing probe be
    turned green at the command line, which is the one thing a go/no-go must not allow.
    """
    probe = _check_probe_parser()
    offered = sorted(
        option
        for action in probe._actions
        for option in action.option_strings
        if option.startswith("--")
    )

    assert offered == ["--help", "--run"], offered


def test_check_probe_imports_by_identity() -> None:
    """The handler's import is the shipped module — a second spelling would be a second answer.

    The `test_check_leakage_cli.py:161-167` source-identity precedent, asserted over the
    handler's own body: `run_check_probe_cli` imports `REFUSALS`, `disclosure` and
    `run_check` from `whetstone.loop.check_probe` and from nowhere else, function-locally —
    the module graph of `whetstone verify` never contains them, and the module object the
    name resolves to is the shipped one, never a copy.
    """
    import ast
    import sys

    import whetstone.loop.check_probe as shipped

    src = Path(__file__).resolve().parents[2] / "src" / "whetstone" / "cli.py"
    tree = ast.parse(src.read_bytes(), filename=str(src))
    handler = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "run_check_probe_cli"
    )
    imports = {
        (node.module, tuple(alias.name for alias in node.names))
        for node in ast.walk(handler)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert ("whetstone.loop.check_probe", ("REFUSALS", "disclosure", "run_check")) in imports, (
        "WHY THIS IS A FAILURE: the handler does not import the shipped check_probe module by "
        "identity. A second spelling of the decision would be a second answer to the go/no-go "
        "question, and the day they disagreed neither document would say so"
    )
    assert sys.modules["whetstone.loop.check_probe"] is shipped


def test_the_check_probe_no_fifth_code_contract() -> None:
    """No UNVERIFIED exit: the description states it — the command reads documents, it never runs.

    The four-code contract (`cli.py:64-84`) has no fifth code for this door. A verdict that
    nothing could be concluded does not exist here: `check-probe` runs nothing, so a refusal
    an operator can fix by retyping is the only way it fails to answer — and the description
    must say so, because a parser that promised an unverifiable outcome would be promising a
    code that never comes.
    """
    probe = _check_probe_parser()

    assert "no UNVERIFIED exit" in probe.description, probe.description