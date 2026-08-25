"""The door: `whetstone check-leakage`, its flag surface, and its exits.

`docs/ROADMAP.md:449-450` names the command and its success condition — *"`uv run whetstone
check-leakage` exits 0 — zero overlap between the training set and the held-out set"* — so
the exit code is the deliverable and it is asserted at the process boundary, not only
against the core.

The codes are the CLI's existing four-code contract (`cli.py:64-84`), no fifth: disjoint →
0, a named overlap → 1 (a leak is a failure, not a usage error), and a refusal an operator
can fix by retyping — a directory that is not a run, an unreadable dataset, a doctored
held-out document — → 2. There is no `UNVERIFIED` here: the check reads two documents and
compares two id sets, so it either answers or refuses.

No model, no `mlx`, no network: the fixtures are JSON documents on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop.test_check_leakage import _run
from loop.test_gate import _MEMBERS, _heldout_document
from whetstone import cli
from whetstone.loop import dataset, night


def _argv(run: Path, document: Path) -> list[str]:
    """The command line, in the order the runbook writes it."""
    return ["check-leakage", "--run", str(run), "--heldout", str(document)]


def test_a_disjoint_run_exits_zero_and_discloses_both_sources(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC1 and the roadmap's own criterion: exit 0, with every count over its denominator."""
    run = _run(tmp_path / "runs" / "night-1", private=("t-11", "t-11"), public=("pub-1",))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    code = cli.main(_argv(run, document))
    out = capsys.readouterr().out

    assert code == 0, out
    assert "clean" in out
    assert "0 of 3 training examples" in out, out
    assert "source B (private)" in out and "source A (public)" in out, (
        "WHY THIS IS A FAILURE: the output names one source. Both sources are always "
        "published together (PREREGISTRATION.md:142-147), and a check that reported only "
        "the one it expected to matter would never notice the other going wrong"
    )
    assert "%" not in out and "percent" not in out


def test_a_leaked_run_exits_nonzero_and_names_the_task(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC2: a leak is a failure with a name on it, not a count and not a usage error."""
    run = _run(tmp_path / "runs" / "night-1", private=(_MEMBERS[0], "t-11"))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    code = cli.main(_argv(run, document))
    out = capsys.readouterr().out

    assert code == 1, out
    assert "LEAKED" in out
    assert _MEMBERS[0] in out, (
        "WHY THIS IS A FAILURE: the command exited nonzero without naming the leaked task. "
        "The fix for a leak is in the night that produced it, and the id is how it is found"
    )
    assert "partition seam" in out


def test_a_directory_that_is_not_a_run_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC3: refusals are 2 and name what was wrong — never a traceback, never a leak verdict."""
    run = _run(tmp_path / "loose", private=("t-11",), ledger=False)
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    code = cli.main(_argv(run, document))
    captured = capsys.readouterr()

    assert code == 2
    assert "whetstone check-leakage:" in captured.err
    assert "ledger.json" in captured.err


def test_a_doctored_held_out_document_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A digest mismatch refuses at the door, and is never reported as a clean check."""
    run = _run(tmp_path / "runs" / "night-1", private=(_MEMBERS[0],))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)
    raw = json.loads(document.read_text(encoding="utf-8"))
    raw["membership"] = ["t-11" if one == _MEMBERS[0] else one for one in raw["membership"]]
    document.write_text(json.dumps(raw), encoding="utf-8")

    code = cli.main(_argv(run, document))
    captured = capsys.readouterr()

    assert code == 2, captured.out
    assert "clean" not in captured.out, (
        "WHY THIS IS A FAILURE: a doctored held-out document produced a verdict. A check that "
        "attests to the disjointness of a set nobody wrote down is worse than no check"
    )


def test_an_unreadable_dataset_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unreadable training set exits 2, never 0 — it is not an empty training set."""
    run = _run(tmp_path / "runs" / "night-1", dataset_text=json.dumps({"examples": []}))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    code = cli.main(_argv(run, document))

    assert code == 2
    assert dataset.DATASET_SCHEMA in capsys.readouterr().err


def test_a_night_that_trained_on_nothing_exits_zero_and_says_why(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC4: disjoint by truth, disclosed as such rather than as an ordinary pass."""
    run = _run(tmp_path / "runs" / "night-1")
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    code = cli.main(_argv(run, document))
    out = capsys.readouterr().out

    assert code == 0
    assert "disjoint by truth" in out, out


def test_the_door_offers_exactly_the_two_flags_the_runbook_pins() -> None:
    """`--run` and `--heldout`, and nothing that could change what is compared.

    The flag surface is pinned because the operator's sheet spells the command out. A third
    flag that narrowed the training set or the membership would let a failing check be turned
    green at the command line, which is the one thing a leakage proof must not allow.
    """
    import argparse

    parser = cli.build_parser()
    subparsers = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    check = subparsers[0].choices["check-leakage"]
    offered = sorted(
        option
        for action in check._actions
        for option in action.option_strings
        if option.startswith("--")
    )

    assert offered == ["--heldout", "--help", "--run"], offered


def test_the_sources_the_door_reports_are_the_nights_own() -> None:
    """Anti-drift: the two source names come from the night that writes them, by identity."""
    from whetstone.loop import check_leakage

    assert check_leakage.SOURCES == (night.PRIVATE, night.PUBLIC)
    assert check_leakage.SOURCES[0] is night.PRIVATE
    assert check_leakage.SOURCES[1] is night.PUBLIC
