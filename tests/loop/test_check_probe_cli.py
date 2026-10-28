"""The door: `whetstone check-probe --run <runs/id>`, its flag surface, and its exits.

`docs/planning/p2-rollouts/night-door/runbook.md:78-80` pre-commits the go/no-go rule — the
night proceeds iff the probe completes with the control arm `PASS` on every draw and a
non-empty seed map — and the declared-input pins narrow it further: the ledger's draws must be
`sampling.K`, and, when `--heldout` is passed, its held-out digest must be the committed
document's. The exit code is the deliverable and it is asserted at the process boundary, not
only against the core: `cli.main(["check-probe", "--run", <dir>])` reads one probe run
directory's ledger and returns the code an operator's sheet can branch on.

The codes are the CLI's existing four-code contract (`cli.py:64-84`), no fifth: the rule
holds → 0, a named violation → 1 (a draw whose harness is not `PASS`, an empty seed map, a
declared budget that is not `sampling.K`, or — with `--heldout` — a mismatched digest or no
held-out record — the night does not run behind it, and that is a finding, not a mistyped
command), and a refusal an operator can fix by retyping — a directory that is not a probe run,
a ledger that cannot be read, an incomplete run, a `--heldout` document that cannot be read —
→ 2. There is no `UNVERIFIED` exit here: the command reads documents rather than running
anything, so it either answers or refuses.

No model, no `mlx`, no network: the fixtures are the `check-core` suite's own real `Ledger`
documents, shared by import.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from loop.test_check_probe import _TORCH_BACKEND, _probe_run
from whetstone import cli
from whetstone.loop import night, sampling
from whetstone.verify.verdict import Status


def _argv(run: Path, *extra: str) -> list[str]:
    """The command line, in the order the runbook writes it."""
    return ["check-probe", "--run", str(run), *extra]


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


def test_the_backend_pins_pass_through(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The three pins reach the core and the disclosure shows both sides of the comparison.

    This is the § 10.25 form of the command: a Torch/MPS/float16 probe is only GO when the
    ledger says it ran that way.
    """
    run = _probe_run(tmp_path / "runs" / "probe-001", backend_record=_TORCH_BACKEND)

    code = cli.main(
        _argv(
            run,
            "--runtime",
            "torch",
            "--device",
            "mps",
            "--precision",
            "float16",
        )
    )
    out = capsys.readouterr().out

    assert code == 0, out
    assert "PROCEED" in out, out
    assert "pins: runtime=torch, device=mps, precision=float16" in out, out
    assert "backend: torch (torch 2.14.1, mps, float16)" in out, out


def test_a_backend_mismatch_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pin mismatch is a finding (1), not a usage error (2) and not a pass."""
    run = _probe_run(tmp_path / "runs" / "probe-001", backend_record=_TORCH_BACKEND)

    code = cli.main(_argv(run, "--device", "cpu"))
    captured = capsys.readouterr()

    assert code == 1, captured.out
    assert captured.err == "", captured.err
    assert "DO NOT PROCEED" in captured.out, captured.out
    assert "mps" in captured.out and "cpu" in captured.out, captured.out


def test_the_check_probe_flag_surface() -> None:
    """The parser exposes `--run`, the `--heldout` document pin, and the three backend pins.

    The flag surface is pinned because the operator's sheet will spell the command out. No
    flag may set a budget, a seed, a timeout or a pass bar: a second flag that narrowed the
    draw set or relaxed the fold would let a failing probe be turned green at the command
    line, which is the one thing a go/no-go must not allow. `--heldout` names the document
    the split pin compares against, and `--runtime`/`--device`/`--precision` name the
    backend pins; every one of them can only add a violation.
    """
    probe = _check_probe_parser()
    offered = sorted(
        option
        for action in probe._actions
        for option in action.option_strings
        if option.startswith("--")
    )

    assert offered == [
        "--device",
        "--heldout",
        "--help",
        "--precision",
        "--run",
        "--runtime",
    ], offered


def test_heldout_is_not_required_and_the_budget_pin_still_decides(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without `--heldout` the door still reads the ledger and the budget pin still decides.

    The flag is optional at this level: a caller that only wants the budget check may omit it,
    and a probe at the wrong budget is still a named violation rather than a pass.
    """
    valid = _probe_run(tmp_path / "valid")
    code = cli.main(_argv(valid))
    out = capsys.readouterr().out
    assert code == 0, out
    assert "PROCEED" in out, out

    short = _probe_run(tmp_path / "short", draws=sampling.K - 1)
    code = cli.main(_argv(short))
    captured = capsys.readouterr()
    assert code == 1, captured.out
    assert f"sampling.K = {sampling.K}" in captured.out, captured.out
    assert str(sampling.K - 1) in captured.out, captured.out


def test_an_unreadable_heldout_document_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """M3 at the door: an unreadable `--heldout` is a refusal an operator can fix by retyping."""
    run = _probe_run(tmp_path)
    unreadable = tmp_path / "heldout.json"
    unreadable.write_text("not json", encoding="utf-8")

    code = cli.main([*_argv(run), "--heldout", str(unreadable)])
    captured = capsys.readouterr()

    assert code == 2, captured.out
    assert captured.out == "", captured.out
    assert "whetstone check-probe:" in captured.err, captured.err
    assert str(unreadable) in captured.err, captured.err


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