"""The door: `whetstone check-leakage`, its flag surface, and its exits.

`docs/ROADMAP.md:459-460` names the command and its success condition — *"`uv run whetstone
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

from loop.test_check_leakage import (
    _MEMBERS,
    _SURVIVOR,
    _heldout_document,
    _id,
    _run,
    _run_digest,
)
from loop.test_check_leakage_checkpoint import (
    OTHER_DIGEST,
    RUN_DIGEST,
    _as_v1,
    _fixture,
    _trained,
)
from loop.test_gate import _heldout_document as _gate_heldout_document
from whetstone import cli
from whetstone.loop import check_leakage, dataset, night, sft


def _argv(run: Path, document: Path) -> list[str]:
    """The command line, in the order the runbook writes it."""
    return ["check-leakage", "--run", str(run), "--heldout", str(document)]


def test_a_disjoint_run_exits_zero_and_discloses_both_sources(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC1 and the roadmap's own criterion: exit 0, with every count over its denominator."""
    run = _run(
        tmp_path / "runs" / "night-1",
        private=(_SURVIVOR, _SURVIVOR),
        public=("pallets__flask-4045",),
    )
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    code = cli.main(_argv(run, document))
    out = capsys.readouterr().out

    assert code == 0, out
    assert "clean" in out
    assert "0 of 2 training examples" in out, out
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
    run = _run(tmp_path / "runs" / "night-1", private=(_MEMBERS[0], _SURVIVOR))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    code = cli.main(_argv(run, document))
    out = capsys.readouterr().out

    assert code == 1, out
    assert "LEAKED" in out
    assert _MEMBERS[0] in out, (
        "WHY THIS IS A FAILURE: the command exited nonzero without naming the leaked task. "
        "The fix for a leak is in the night that produced it, and the id is how it is found"
    )
    # Two causes, neither asserted: a seam failure or a split derived after the night ran.
    assert "partition seam failed to exclude" in out
    assert "re-derived after the night ran" in out
    assert "This is a regression" not in out


def test_a_directory_that_is_not_a_run_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC3/AC4: refusals are 2 and name what was wrong — never a traceback, never a verdict.

    CHANGED: a missing ledger alone no longer refuses (PRD requirement 2); a directory with
    neither dataset nor ledger does.
    """
    run = tmp_path / "loose"
    run.mkdir()
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    code = cli.main(_argv(run, document))
    captured = capsys.readouterr()

    assert code == 2
    assert "whetstone check-leakage:" in captured.err
    assert "dataset.json" in captured.err


def test_a_ledger_without_a_dataset_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ledger and no dataset exits 2 naming the dataset, never a verdict."""
    run = _run(tmp_path / "ledgered")
    (run / night.DATASET_FILE).unlink()
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    code = cli.main(_argv(run, document))
    captured = capsys.readouterr()

    assert code == 2 and "dataset.json" in captured.err
    assert "nothing identifies" not in captured.err and "clean" not in captured.out


def test_a_run_without_a_ledger_is_checked_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PRD requirement 2: exit 0 on a clean ledger-less run, with the notice on stdout."""
    run = _run(tmp_path / "loose", private=(_SURVIVOR,), ledger=False)
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    code = cli.main(_argv(run, document))
    out = capsys.readouterr().out

    assert code == 0, out
    assert "ledger.json" in out and "absent" in out


def test_a_night_001_shaped_run_exits_one_naming_both_ids(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC6: the real night's shape, through the door, is a named leak."""
    ids = ("legacy-a-c6e4d4c4de87",) * 4 + ("legacy-a-34daf85182d5", "legacy-b-c3e132b7469b")
    run = _run(tmp_path / "runs" / "night-001", private=ids, ledger=False)
    members = ("donor-a-c6e4d4c4de87", *_MEMBERS[:9])
    document = _gate_heldout_document(
        tmp_path / "doc",
        members,
        corpus_ids=(*members, "donor-a-34daf85182d5", "donor-b-c3e132b7469b"),
    )

    code = cli.main(_argv(run, document))
    out = capsys.readouterr().out

    assert code == 1, out
    assert "legacy-a-c6e4d4c4de87" in out and "donor-a-c6e4d4c4de87" in out


def test_a_doctored_held_out_document_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A digest mismatch refuses at the door, and is never reported as a clean check."""
    run = _run(tmp_path / "runs" / "night-1", private=(_MEMBERS[0],))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)
    raw = json.loads(document.read_text(encoding="utf-8"))
    raw["membership"] = [_SURVIVOR if one == _MEMBERS[0] else one for one in raw["membership"]]
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


def test_the_door_offers_exactly_the_three_flags_the_runbook_pins() -> None:
    """`--run`, `--heldout` and the optional `--checkpoint`; nothing that changes what is compared.

    The flag surface is pinned because the operator's sheet spells the command out. A flag that
    narrowed the training set or the membership would let a failing check be turned green at the
    command line, which is the one thing a leakage proof must not allow. `--checkpoint` is the
    third and is optional: it narrows neither set and cannot turn a failing check green (a leaked
    run with a matching checkpoint still exits 1; a mismatching one exits 2, never 0).
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

    assert offered == ["--checkpoint", "--heldout", "--help", "--run"], offered


def test_the_sources_the_door_reports_are_the_nights_own() -> None:
    """Anti-drift: the two source names come from the night that writes them, by identity."""
    from whetstone.loop import check_leakage

    assert check_leakage.SOURCES == (night.PRIVATE, night.PUBLIC)
    assert check_leakage.SOURCES[0] is night.PRIVATE
    assert check_leakage.SOURCES[1] is night.PUBLIC


def test_a_re_minted_leak_exits_one_and_an_unrecognised_id_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The adversarial leak is exit 1 naming both ids; an id with no identity is exit 2."""
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    leaked = _run(tmp_path / "runs" / "leaked", private=(_id(1, "legacy-a"),))
    assert cli.main(_argv(leaked, document)) == 1
    out = capsys.readouterr().out
    assert _id(1, "legacy-a") in out and _MEMBERS[0] in out

    unnamed = _run(tmp_path / "runs" / "unnamed", private=("t-07",))
    assert cli.main(_argv(unnamed, document)) == 2
    assert "t-07" in capsys.readouterr().err


def test_the_help_says_a_run_with_no_dataset_exits_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The help names the real refusal (no dataset.json), not 'cannot be identified'."""
    cli.main(["check-leakage", "--help"])
    text = " ".join(capsys.readouterr().out.split())

    assert "no dataset.json" in text, text
    assert "cannot be identified" not in text, text


def test_a_source_a_only_run_exits_two_because_nothing_was_compared(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Amendment 2 (gate-leakage-guard PRD): this asserted exit 0 until then. A run that
    # compared nothing is a refusal on stderr, with no verdict on stdout.
    run = _run(tmp_path / "runs" / "night-1", public=("pallets__flask-4045",))
    document = _heldout_document(tmp_path / "doc", _MEMBERS)

    code = cli.main(_argv(run, document))
    captured = capsys.readouterr()

    assert code == 2, captured
    assert "nothing was compared" in captured.err and "no verdict" in captured.err, captured.err
    assert "leakage:" not in captured.out, captured.out


def test_the_help_says_a_run_that_compared_nothing_exits_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.main(["check-leakage", "--help"])
    text = " ".join(capsys.readouterr().out.split())

    assert "a run that compared nothing" in text, text


def test_the_description_states_the_identity_only_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.main(["check-leakage", "--help"])
    text = " ".join(capsys.readouterr().out.split())

    assert "12-hex" in text and "near-duplicate" in text, text
    assert "an id it cannot read" in text, text


def _with_checkpoint(run: Path, document: Path, checkpoint: Path) -> list[str]:
    return [*_argv(run, document), "--checkpoint", str(checkpoint)]


def test_a_matching_v2_checkpoint_on_a_clean_run_exits_zero_with_the_sealed_link(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if the flag is not parsed or `args.checkpoint` is not passed to `run_check`."""
    run, held = _fixture(tmp_path)
    cp = _trained(tmp_path / "cp")

    code = cli.main(_with_checkpoint(run, held, cp.directory))
    out = capsys.readouterr().out

    assert code == 0, out
    assert "dataset link:" in out and "sealed (whetstone-checkpoint/2)" in out, out
    assert RUN_DIGEST[:12] in out
    assert out.index(check_leakage._RESIDUAL) < out.index("dataset link:"), (
        "the link lines must follow the verdict and its residual, never precede them"
    )


def test_a_matching_checkpoint_cannot_make_a_leaked_run_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if a matching link short-circuits the verdict (exit 0) or drops the leak lines."""
    run, held = _fixture(tmp_path, leaked=True)
    cp = _trained(tmp_path / "cp", _run_digest(run))

    code = cli.main(_with_checkpoint(run, held, cp.directory))
    out = capsys.readouterr().out

    assert code == 1, out
    assert "LEAKED" in out and _MEMBERS[0] in out
    assert "dataset link:" in out


def test_a_matching_v1_checkpoint_is_recorded_not_sealed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if a v1 link is rendered as sealed or as verified."""
    for leaked, expected in ((False, 0), (True, 1)):
        base = tmp_path / str(leaked)
        base.mkdir()
        run, held = _fixture(base, leaked=leaked)
        cp = _as_v1(_trained(base / "cp", _run_digest(run)))

        code = cli.main(_with_checkpoint(run, held, cp.directory))
        out = capsys.readouterr().out

        assert code == expected, out
        assert "recorded, not sealed" in out, out
        link_lines = [line for line in out.splitlines() if "link" in line.lower()]
        assert link_lines
        assert not any("verified" in line.lower() for line in link_lines), link_lines


@pytest.mark.parametrize("leaked", [False, True], ids=["clean-run", "leaked-run"])
def test_a_mismatching_checkpoint_exits_two_with_nothing_on_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], leaked: bool
) -> None:
    """Fails if the comparison precedes the digest check, or the refusal leaves REFUSALS."""
    run, held = _fixture(tmp_path, leaked=leaked)
    cp = _trained(tmp_path / "cp", OTHER_DIGEST)

    code = cli.main(_with_checkpoint(run, held, cp.directory))
    captured = capsys.readouterr()

    assert code == 2, captured
    assert captured.out == "", captured.out
    assert captured.err.startswith("whetstone check-leakage: "), captured.err
    assert "not trained on this run" in captured.err


def test_a_tampered_v2_checkpoint_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if the checkpoint is read without verifying its seal."""
    run, held = _fixture(tmp_path)
    cp = _trained(tmp_path / "cp", OTHER_DIGEST)
    path = cp.directory / sft.CHECKPOINT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    document["dataset_digest"] = RUN_DIGEST
    path.write_text(json.dumps(document), encoding="utf-8")

    code = cli.main(_with_checkpoint(run, held, cp.directory))
    captured = capsys.readouterr()

    assert code == 2, captured
    assert captured.out == "" and captured.err.startswith("whetstone check-leakage: ")


def test_a_v1_checkpoint_with_a_malformed_files_entry_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if a malformed entry escapes as a ValueError, which exits 1 — the leak code.

    v1 is unsealed, so one hand edit reaches the entry: `bytes` set to a non-number.
    """
    run, held = _fixture(tmp_path)
    cp = _as_v1(_trained(tmp_path / "cp"))
    path = cp.directory / sft.CHECKPOINT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    document["files"][0]["bytes"] = "abc"
    path.write_text(json.dumps(document), encoding="utf-8")

    code = cli.main(_with_checkpoint(run, held, cp.directory))
    captured = capsys.readouterr()

    assert code == 2, captured
    assert captured.out == "", captured.out
    assert captured.err.startswith("whetstone check-leakage: "), captured.err
    assert "files entry 0" in captured.err, captured.err


def test_an_untrained_checkpoint_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if CheckpointHasNoDataset is not a refusal at the door."""
    run, held = _fixture(tmp_path)
    base = tmp_path / "base"
    sft.write_baseline_checkpoint(
        base, repo_id="m/x", revision="abc", tool_versions={"python": "3.12.0"}
    )

    code = cli.main(_with_checkpoint(run, held, base))
    captured = capsys.readouterr()

    assert code == 2, captured
    assert captured.out == "" and "no dataset to compare" in captured.err


@pytest.mark.parametrize("shape", ["missing", "no-provenance"])
def test_an_unusable_checkpoint_directory_exits_two_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], shape: str
) -> None:
    """Fails if sft.CheckpointUnverified escapes the handler."""
    run, held = _fixture(tmp_path)
    directory = tmp_path / "cp-missing"
    if shape == "no-provenance":
        directory.mkdir()

    code = cli.main(_with_checkpoint(run, held, directory))
    captured = capsys.readouterr()

    assert code == 2, captured
    assert captured.out == ""
    assert captured.err.startswith("whetstone check-leakage: ") and len(captured.err) > 30


def _module_scope_loop_imports(source: str) -> list[str]:
    """Imports of `whetstone.loop` at module scope, including under `if`/`try` (not in defs)."""
    import ast

    offenders: list[str] = []

    def walk(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("whetstone.loop") or (
                    module == "whetstone" and any(a.name == "loop" for a in node.names)
                ):
                    offenders.append(module)
            elif isinstance(node, ast.Import):
                offenders.extend(a.name for a in node.names if a.name.startswith("whetstone.loop"))
            elif isinstance(node, ast.If):
                walk(node.body)
                walk(node.orelse)
            elif isinstance(node, ast.Try):
                walk(node.body)
                walk(node.orelse)
                walk(node.finalbody)
                for handler in node.handlers:
                    walk(handler.body)

    walk(ast.parse(source).body)
    return offenders


def test_cli_has_no_module_scope_import_of_the_loop() -> None:
    """Fails if `--checkpoint` is wired by importing whetstone.loop at module scope."""
    assert _module_scope_loop_imports(Path(cli.__file__).read_text(encoding="utf-8")) == []


def test_the_module_scope_scan_sees_hidden_imports_and_ignores_function_bodies() -> None:
    hidden = "if TYPE_CHECKING:\n    from whetstone.loop import night\n"
    assert _module_scope_loop_imports(hidden) == ["whetstone.loop"]
    assert _module_scope_loop_imports("try:\n    from whetstone import loop\nexcept E:\n    pass\n")
    assert _module_scope_loop_imports("import whetstone.loop.night\n") == ["whetstone.loop.night"]
    assert _module_scope_loop_imports("def f():\n    from whetstone.loop import night\n") == []


def test_the_help_names_the_checkpoint_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """Fails if the flag lacks help or the description omits the new exit 2."""
    cli.main(["check-leakage", "--help"])
    text = " ".join(capsys.readouterr().out.split())

    assert "--checkpoint" in text, text
    assert "tampered, untrained or trained on another night" in text, text
    assert "dataset.json is not sealed" in text, text
