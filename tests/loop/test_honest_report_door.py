"""The honest-number report door — the only place the sealed evidence may be composed.

`src/whetstone/loop/honest_report.py` is the module door behind the P4 report
(`docs/planning/honest-number-report/report-door/`): it reads the sealed § 3 baseline
artifact, the promotion record and both checkpoints, verifies the series, and refuses
every half-truth render by name — nothing written, exit 2, no fifth exit code. The door
composes the fail-closed readers and the writer **by identity** (never copied), supplies
what the sealed documents lack (the run ledger's generation contract, the committed
funnel ledger), and renders the gate decision's semantics end-to-end: promoted → the
candidate is final; rejected → the incumbent is final with the candidate disclosed as
the rejected attempt; UNVERIFIED → no headline and no delta, "no comparison was made".

Nothing here runs a model, a sandbox, a verifier, or the network. Every fixture
baseline artifact is a measured, sealed document built through the writer — never
hand-typed — and every fixture promotion record through the gate's own writer, so the
door is exercised over the real bytes the operator chain will produce.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from whetstone.bakeoff import report as bakeoff_report
from whetstone.bakeoff.report import build_baseline_report, write_baseline_report
from whetstone.loop import baseline, gate, heldout, ledger, sft
from whetstone.verify.verdict import Status

#: The repository root — the committed funnel ledger and the subprocess half live here.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The guarded module under test, walked over its own bytes rather than this process's
#: `sys.modules` — the loop package's rule is about what executing the module loads.
MODULE = REPO_ROOT / "src" / "whetstone" / "loop" / "honest_report.py"

#: The import roots that may appear only inside function bodies in `honest_report.py`.
FORBIDDEN_IMPORT_ROOTS = frozenset({"mlx", "mlx_lm"})

#: The one base the fixture evidence names — the series every clean fixture agrees on.
_BASE = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"

#: The revision the fixture baseline and checkpoints declare.
_REVISION = "main"

#: The held-out document digest the fixture baseline and record share.
_HELDOUT_DIGEST = "h" * 64

#: The fixture record's run id — the value `--run-id` must carry.
_RUN_ID = "eval-001"

#: The operator-declared date — an input, never the clock.
_RECORDED_ON = "2026-08-27"

#: The held-out split's size in these fixtures.
HELDOUT = 12

#: The tool versions both sealed documents carry.
_TOOLS = {"python": "3.12.7", "uv": "0.5.18"}


def _tally(
    candidate: str, *, solved: int, denominator: int, unverified: int, weaker_wins: int
) -> bakeoff_report.Tally:
    """One side's counts as the report's own `Tally`, over the invariant the report checks."""
    return bakeoff_report.Tally(
        candidate=candidate,
        denominator=denominator,
        solved=solved,
        covered=denominator - unverified,
        unverified=unverified,
        failed=denominator - unverified - solved,
        weaker_wins=weaker_wins,
        no_diff=0,
        not_applied=0,
        out_of_scope=0,
        not_solved=0,
    )


def _baseline_artifact(
    root: Path, *, revision: str = _REVISION, heldout_digest: str = _HELDOUT_DIGEST
) -> Path:
    """A measured, sealed § 3 baseline artifact, built through the writer — never hand-typed.

    The fixture's "before": the baseline solves 2 of 12 with 1 unverified and `N = 1`,
    source A's single instance not solved — the figures every headline assertion is read
    against.
    """
    document = build_baseline_report(
        series=baseline.SeriesIdentity(
            repo_id=_BASE, revision=revision, heldout_digest=heldout_digest
        ),
        heldout_tally=_tally(
            "baseline", solved=2, denominator=HELDOUT, unverified=1, weaker_wins=1
        ),
        public_tally=_tally("baseline", solved=0, denominator=1, unverified=0, weaker_wins=0),
        retries=(),
        retry_count=0,
        evidence_digest="e" * 64,
        recorded_on="2026-08-26",
        tool_versions=_TOOLS,
    )
    return write_baseline_report(document, root / "baseline")[1]


def _side_counts(
    *,
    solved: int,
    denominator: int = HELDOUT,
    unverified: int = 0,
    weaker_wins: int,
    status: Status = Status.PASS,
) -> gate.SideCounts:
    """One source's counts in the gate's own shape, over the record's invariant."""
    return gate.SideCounts(
        denominator=denominator,
        solved=solved,
        unverified=unverified,
        covered=denominator - unverified,
        failed=denominator - unverified - solved,
        weaker_wins=weaker_wins,
        status=status,
    )


def _side(*, solved: int, weaker_wins: int, status: Status = Status.PASS) -> gate.Side:
    """One checkpoint's counts over both sources: the held-out split and source A."""
    return gate.Side(
        private=_side_counts(solved=solved, weaker_wins=weaker_wins, status=status),
        public=_side_counts(solved=0, denominator=1, weaker_wins=0, status=Status.FAIL),
    )


def _record(
    root: Path,
    *,
    run_id: str = _RUN_ID,
    heldout_digest: str = _HELDOUT_DIGEST,
    decision: gate.Exit = gate.Exit.PROMOTED,
    candidate_solved: int = 3,
    incumbent_solved: int = 2,
    candidate_weaker_wins: int = 2,
    incumbent_weaker_wins: int = 1,
    decision_unverified: int = 0,
) -> Path:
    """A promotion record through the gate's own writer — the real bytes the reader reads.

    The promoted fixture's candidate solves 3 of 12 (the baseline's 2, plus one) with
    `N = 2`; the incumbent is the previous night's candidate, at the baseline's 2.
    """
    path = root / "runs" / "promotions" / f"{run_id}.json"
    gate.write_promotion_record(
        path=path,
        run_id=run_id,
        recorded_on=_RECORDED_ON,
        candidate_digest="c" * 64,
        incumbent_digest="i" * 64,
        heldout_digest=heldout_digest,
        candidate=_side(solved=candidate_solved, weaker_wins=candidate_weaker_wins),
        incumbent=_side(solved=incumbent_solved, weaker_wins=incumbent_weaker_wins),
        decision=gate.GateDecision(
            exit=decision,
            denominator=HELDOUT,
            solved_new=candidate_solved,
            solved_old=incumbent_solved,
            regressed=1 if candidate_solved < incumbent_solved else 0,
            unverified=decision_unverified,
            detail="fixture",
        ),
        retries=(),
        retryable=(),
        retry_count=3,
        tool_versions=_TOOLS,
    )
    return path


def _checkpoint(root: Path, label: str, *, revision: str = _REVISION) -> sft.Checkpoint:
    """A night-shaped checkpoint over a stub adapter, hashed by `sft.write_checkpoint`.

    The same seam the night itself uses, so a door test's checkpoints are the real
    artefact `verify_checkpoint` will re-hash — never a hand-written directory beside it.
    """
    directory = root / "checkpoints" / label
    directory.mkdir(parents=True, exist_ok=True)
    (directory / sft.ADAPTER_FILE).write_bytes(
        f"not a tensor, deliberately ({label})".encode()
    )
    (directory / sft.ADAPTER_CONFIG).write_text('{"lora_parameters": {}}', encoding="utf-8")
    return sft.write_checkpoint(
        directory,
        repo_id=_BASE,
        revision=revision,
        dataset_digest="d" * 64,
        run_seed=20260827,
        args=sft.TrainingArgs(),
        tool_versions=_TOOLS,
        valid_split="",
        capacity=sft.CapacityProbe(iters=1, headroom_bytes=0, peak_bytes=0, seconds=0.0),
    )


def _ledger(root: Path, *, run_id: str = _RUN_ID) -> Path:
    """A schema-valid run ledger the door reads for the generation contract.

    `ledger.read` validates the schema and nothing else, so the fixture carries the
    fields the door reads — the generation contract, the task set, the run seed and the
    applied seeds — in the ledger's own shape.
    """
    path = root / "runs" / run_id / "ledger.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": "whetstone-run/1",
                "run_id": run_id,
                "recorded_on": _RECORDED_ON,
                "run_seed": 20260827,
                "draws": 8,
                "model": {"repo_id": _BASE, "revision": _REVISION},
                "generation_contract": {
                    "prompt_sha256": "p" * 64,
                    "sampler": "categorical: temperature 0.8, top-p 0.95, seeded per attempt",
                    "max_tokens": 8192,
                    "extractor_version": "extractor-v1",
                    "dev_subset": ["dev-a", "dev-b", "dev-c", "dev-d", "dev-e"],
                    "retry_budget": 3,
                    "retry_template_sha256": "r" * 64,
                    "diagnosis_vocabulary_version": "v" * 64,
                    "retrieval": "oracle",
                },
                "task_set": {
                    "private": 10,
                    "public": 1,
                    "roots": 2,
                    "dev_subset": ["dev-a"],
                    "probe": None,
                    "heldout": {
                        "document_digest": _HELDOUT_DIGEST,
                        "membership_count": HELDOUT,
                    },
                },
                "tool_versions": _TOOLS,
                "seeds": [{"task_id": "t-01", "attempt": 1, "seed": 111111}],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _fixtures(root: Path) -> dict[str, Path]:
    """The full fixture pair plus the checkpoints and the ledger, in their real homes.

    `out` sits beside the real home's name — `reports/honest-number` — inside the test
    root, so the committed-root discipline (gitignored roots refused) is exercised
    against real root names, and `heldout` points at the committed document the door
    never parses.
    """
    return {
        "baseline": _baseline_artifact(root),
        "record": _record(root),
        "candidate": _checkpoint(root, "candidate").directory,
        "incumbent": _checkpoint(root, "incumbent").directory,
        "ledger": _ledger(root),
        "out": root / "reports" / "honest-number",
        "heldout": REPO_ROOT / "tasks" / "heldout" / "source-b.json",
    }


def _argv(
    fixtures: Mapping[str, Path],
    *,
    out: Path | None = None,
    baseline_path: Path | None = None,
    record: Path | None = None,
    candidate: Path | None = None,
    incumbent: Path | None = None,
    heldout: Path | None = None,
    run_id: str = _RUN_ID,
    recorded_on: str = _RECORDED_ON,
) -> list[str]:
    """The render-mode command line over the fixture evidence, with its pointers."""
    return [
        "--render",
        "--baseline",
        str(baseline_path or fixtures["baseline"]),
        "--record",
        str(record or fixtures["record"]),
        "--checkpoint-candidate",
        str(candidate or fixtures["candidate"]),
        "--checkpoint-incumbent",
        str(incumbent or fixtures["incumbent"]),
        "--heldout",
        str(heldout or fixtures["heldout"]),
        "--out",
        str(out or fixtures["out"]),
        "--recorded-on",
        recorded_on,
        "--run-id",
        run_id,
    ]


# --------------------------------------------------------------------------------------------
# Phase 1: the parser surface and the primary refusals — each by name, nothing written.
# --------------------------------------------------------------------------------------------


def test_the_parser_surface_is_exactly_the_render_modes_and_evidence_pointers(
    tmp_path: Path,
) -> None:
    """AC 9: the flag set is fixed — render modes, evidence pointers, `--out`,
    `--recorded-on`, `--run-id` — and no retry, seed or scoring flag exists on it.

    The runbook guard (aspect 5) pins the sheet's flags against this parser by identity,
    so the surface is asserted exactly: a flag the parser does not define fails the
    guard, and a retry knob, a seed flag or a scoring flag would let a render choose its
    own evidence.
    """
    from whetstone.loop import honest_report

    parser = honest_report.build_parser()
    flags = {
        name for name in parser._option_string_actions if name.startswith("--")
    } - {"--help"}
    assert flags == {
        "--render",
        "--render-declaration",
        "--baseline",
        "--record",
        "--checkpoint-candidate",
        "--checkpoint-incumbent",
        "--heldout",
        "--out",
        "--recorded-on",
        "--run-id",
    }, flags

    parsed = parser.parse_args(_argv(_fixtures(tmp_path)))
    assert parsed.render is not None
    assert parsed.baseline is not None
    assert parsed.record is not None
    assert parsed.checkpoint_candidate is not None
    assert parsed.checkpoint_incumbent is not None
    assert parsed.heldout is not None
    assert parsed.out is not None
    assert parsed.recorded_on == _RECORDED_ON
    assert parsed.run_id == _RUN_ID


def test_render_and_render_declaration_are_mutually_exclusive(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The two modes cannot share one command line — the parser's usage exit, by name."""
    from whetstone.loop import honest_report

    with pytest.raises(SystemExit) as refused:
        honest_report.main(
            ["--render", "--render-declaration", "y", "--recorded-on", _RECORDED_ON]
        )
    assert refused.value.code == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_render_refuses_a_gitignored_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2: `--out` under a gitignored root is refused by identity, nothing written.

    The report is a committed artifact, and one git cannot see is one git cannot prove
    predated the render — the `refuse_committed_out` posture, before anything is loaded.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)
    out = tmp_path / "runs" / "out"

    code = honest_report.main(_argv(fixtures, out=out))

    assert code == 2
    assert "runs" in capsys.readouterr().err
    assert not out.exists(), (
        "WHY THIS IS A FAILURE: a refused render wrote artifacts — nothing may be "
        "rendered into a home git cannot see"
    )


def test_render_refuses_an_unmeasured_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2: a declaration-state baseline has no counts to delta against — refused by name.

    The `measured: false` artifact carries no sides, no series and no counts; a delta
    against it would be a delta against nothing, rendered as though a number existed.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)
    declaration = tmp_path / "declaration-baseline"
    assert (
        baseline.main(["--render-declaration", str(declaration), "--recorded-on", "2026-08-26"])
        == 0
    )

    code = honest_report.main(
        _argv(fixtures, baseline_path=declaration / "report.json")
    )

    assert code == 2
    assert "measured" in capsys.readouterr().err
    assert not fixtures["out"].exists()


def test_render_refuses_a_missing_baseline_artifact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2: a baseline artifact that cannot be read is refused by name — never a delta
    from nothing."""
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)
    missing = tmp_path / "missing" / "report.json"

    code = honest_report.main(_argv(fixtures, baseline_path=missing))

    assert code == 2
    assert "report.json" in capsys.readouterr().err
    assert not fixtures["out"].exists()


def test_render_refuses_a_missing_promotion_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2: a promotion record that cannot be read is refused by name — the final side
    has no on-disk source, so no comparison can be rendered."""
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)
    missing = tmp_path / "missing" / "eval-001.json"

    code = honest_report.main(_argv(fixtures, record=missing))

    assert code == 2
    assert "promotion record" in capsys.readouterr().err
    assert not fixtures["out"].exists()


def test_render_refuses_a_checkpoint_whose_bytes_moved(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2: a checkpoint whose bytes are not the bytes the night wrote is refused by
    name, candidate and incumbent alike.

    The re-hash is `sft.verify_checkpoint` by identity on both sides: a candidate that
    cannot be demonstrated to be the scored bytes is not a candidate, and an incumbent
    nobody re-reads renders in a review exactly like a checked one.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)
    moved = fixtures["candidate"] / sft.ADAPTER_FILE
    moved.write_bytes(b"tampered bytes, not the night's adapter")

    code = honest_report.main(_argv(fixtures))

    assert code == 2
    message = capsys.readouterr().err
    assert str(moved) in message and ("sha256" in message or "bytes" in message), message
    assert not fixtures["out"].exists()

    second = _fixtures(tmp_path / "two")
    moved_incumbent = second["incumbent"] / sft.ADAPTER_FILE
    moved_incumbent.write_bytes(b"tampered bytes, not the night's adapter")

    code = honest_report.main(_argv(second))

    assert code == 2
    message = capsys.readouterr().err
    assert str(moved_incumbent) in message and (
        "sha256" in message or "bytes" in message
    ), message
    assert not second["out"].exists()


def test_render_writes_the_three_artifacts_from_the_fixture_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 1: a clean render of the agreeing fixture pair exits 0 and writes the shape.

    The sealed baseline artifact and the promotion record agree on the series, both
    checkpoints re-hash, and the door composes them into the writer's three-artifact
    shape — the "0 clean" half of `main`'s contract.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)

    code = honest_report.main(_argv(fixtures))

    assert code == 0, capsys.readouterr().err
    for name in ("report.md", "report.json", "cost.json"):
        assert (fixtures["out"] / name).is_file(), name
    payload = json.loads((fixtures["out"] / "report.json").read_text(encoding="utf-8"))
    assert payload["schema"] == bakeoff_report.HONEST_NUMBER_REPORT_SCHEMA, payload
    assert payload["measured"] is True, payload


def test_honest_report_module_imports_no_inference_library_at_module_scope() -> None:
    """AC 8: the door reads documents and renders — no `mlx` import anywhere, at any scope.

    The walk forbids an import whose root is `mlx` or `mlx_lm` outside a function body;
    this door has none even inside one, because it never touches the machine. The
    anti-vacuity half demands `build_parser` and `main` at module scope, so an empty
    module fails rather than passing by containing no imports at all.
    """
    tree = ast.parse(MODULE.read_bytes(), filename=str(MODULE))

    assert any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in ("build_parser", "main")
        for node in tree.body
    ), "honest_report.py defines no build_parser/main — this walk has nothing to guard"

    function_local: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if isinstance(inner, (ast.Import, ast.ImportFrom)):
                    function_local.add(inner.lineno)

    at_module_scope = [
        f"line {node.lineno}: " + ", ".join(alias.name for alias in node.names)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and node.lineno not in function_local
        and any(alias.name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS for alias in node.names)
    ]
    assert not at_module_scope, (
        "honest_report.py imports an inference library: " + "; ".join(at_module_scope)
        + "\n\nWHY THIS IS A FAILURE: the door reads documents and renders only. A "
        "module-scope import would put an inference library on the loop's import graph "
        "unconditionally, and any import at all would mean the door touches the machine"
    )


# --------------------------------------------------------------------------------------------
# Phase 3: composition by identity, and the series / incumbent / measured-once refusals.
# --------------------------------------------------------------------------------------------


def test_the_door_composes_the_readers_and_writer_by_identity() -> None:
    """AC 4: every composed seam is the owning module's own object, imported, never copied.

    `read_baseline_document`, `read_promotion_record`, `verify_checkpoint`, the writer
    pair and `refuse_committed_out` are the spec's five; the run-ledger reader and the
    checkpoint-base read ride the same discipline, on the baseline door's own precedent
    (`baseline._checkpoint_base = gate_module._checkpoint_base`). A second spelling of
    any of these would be a second answer to what the same bytes mean.
    """
    from whetstone.loop import honest_report

    assert honest_report.read_baseline_document is baseline.read_baseline_document, (
        "WHY THIS IS A FAILURE: the door does not read the baseline artifact through "
        "the fail-closed loader by identity"
    )
    assert honest_report.read_promotion_record is gate.read_promotion_record, (
        "WHY THIS IS A FAILURE: the door does not read the promotion record through "
        "the fail-closed reader by identity"
    )
    assert honest_report.verify_checkpoint is sft.verify_checkpoint, (
        "WHY THIS IS A FAILURE: the door does not re-hash checkpoints through "
        "`sft.verify_checkpoint` by identity"
    )
    assert (
        honest_report.build_honest_number_report
        is bakeoff_report.build_honest_number_report
    ), "WHY THIS IS A FAILURE: the door does not render through the writer by identity"
    assert (
        honest_report.write_honest_number_report
        is bakeoff_report.write_honest_number_report
    ), "WHY THIS IS A FAILURE: the door does not write through the writer by identity"
    assert honest_report.refuse_committed_out is heldout.refuse_committed_out, (
        "WHY THIS IS A FAILURE: the door does not refuse a gitignored --out through "
        "`refuse_committed_out` by identity"
    )
    assert honest_report.read_ledger is ledger.read, (
        "WHY THIS IS A FAILURE: the door does not read the run ledger through "
        "`ledger.read` by identity"
    )
    assert honest_report._checkpoint_base is gate._checkpoint_base, (
        "WHY THIS IS A FAILURE: the door does not read a checkpoint's base through "
        "the gate's own read by identity"
    )


def test_render_refuses_a_heldout_document_digest_disagreement(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2: the promotion record's held-out digest must equal the baseline series'.

    A delta computed across a change to any pinned input is not a delta
    (`PREREGISTRATION.md:92-94`): the final side scored over a different held-out
    document is a different measurement, refused by name with the digest pair.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path / "one")
    record = _record(tmp_path / "one", heldout_digest="x" * 64)

    code = honest_report.main(_argv(fixtures, record=record))

    assert code == 2
    message = capsys.readouterr().err
    assert _HELDOUT_DIGEST in message and "x" * 64 in message, message
    assert not fixtures["out"].exists(), (
        "WHY THIS IS A FAILURE: a refused render wrote artifacts — a non-delta must "
        "not be published as one"
    )


def test_render_refuses_a_candidate_on_a_different_base(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2: the candidate checkpoint's base identity must equal the baseline series'.

    The candidate's own provenance names the base it was trained on; a candidate from
    a different base than the series measured is a delta across a changed pinned
    input, refused by name with the base pair.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)
    candidate = _checkpoint(tmp_path, "candidate-other", revision="other-rev").directory

    code = honest_report.main(_argv(fixtures, candidate=candidate))

    assert code == 2
    message = capsys.readouterr().err
    assert "other-rev" in message and _REVISION in message, message
    assert not fixtures["out"].exists()


def test_render_refuses_an_incumbent_on_a_different_base_than_the_candidate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2, PRD gate-resolution 5: the incumbent's base is checked too.

    Two nights on different bases means the gate compared incomparables — the
    candidate's base and the incumbent's base must be one, or the decision is not a
    delta and nothing renders.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)
    incumbent = _checkpoint(tmp_path, "incumbent-other", revision="other-rev").directory

    code = honest_report.main(_argv(fixtures, incumbent=incumbent))

    assert code == 2
    message = capsys.readouterr().err
    assert "other-rev" in message and _REVISION in message, message
    assert not fixtures["out"].exists()


def test_render_refuses_a_run_id_that_is_not_the_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--run-id` pins the record's identity — a record that is not this run's is refused.

    The flag exists so the operator names the run the record belongs to; a record
    whose `run_id` differs is not the evidence this render was about, refused by name
    with both ids.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)

    code = honest_report.main(_argv(fixtures, run_id="other-run"))

    assert code == 2
    message = capsys.readouterr().err
    assert "other-run" in message and _RUN_ID in message, message
    assert not fixtures["out"].exists()


def test_a_same_series_render_at_out_is_refused_but_a_different_series_renders(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2: the measured-once posture keys on the series, never the clock.

    A second render of the same series is the first render wearing a second date —
    refused by name, naming the artifact already there. A **changed** pinned input is
    a legitimate new series, rendered beside it: the series is the key, never the
    clock (`PREREGISTRATION.md:133-135`).
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path / "one")
    assert honest_report.main(_argv(fixtures)) == 0
    first_bytes = (fixtures["out"] / "report.json").read_bytes()

    code = honest_report.main(_argv(fixtures))
    assert code == 2
    message = capsys.readouterr().err
    assert "already" in message and "report.json" in message, message
    assert (fixtures["out"] / "report.json").read_bytes() == first_bytes, (
        "WHY THIS IS A FAILURE: the refused second render rewrote the first — the "
        "measured-once refusal must fire before anything is written"
    )

    second = tmp_path / "two"
    second_fixtures = {
        "baseline": _baseline_artifact(second, revision="other-rev"),
        "record": _record(second),
        "candidate": _checkpoint(second, "candidate", revision="other-rev").directory,
        "incumbent": _checkpoint(second, "incumbent", revision="other-rev").directory,
        "ledger": _ledger(second),
        "out": fixtures["out"],
        "heldout": fixtures["heldout"],
    }
    code = honest_report.main(_argv(second_fixtures))
    assert code == 0, capsys.readouterr().err
    payload = json.loads((fixtures["out"] / "report.json").read_text(encoding="utf-8"))
    assert payload["series"]["revision"] == "other-rev", payload


# --------------------------------------------------------------------------------------------
# Phase 4: the decision semantics end-to-end — promoted, rejected, UNVERIFIED — and the
# declaration mode's re-runnability.
# --------------------------------------------------------------------------------------------


def test_a_promoted_decision_renders_the_candidate_as_final(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PRD gate-resolution 4: promoted → the candidate's counts are final, end-to-end.

    The door passes the record's decision and counts through to the writer; the
    fixture candidate solves 3 of 12 (the baseline's 2 plus one) with `N = 2`, so the
    § 4 headline instantiates exactly — `+a of b held-out tasks (baseline c of b,
    final d of b) / coverage e of b / N: f at baseline, g at final` — with `e` the
    final side's covered count (gate-resolution 6), and the provenance carries what
    the door read from the run ledger and the baseline artifact.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)

    code = honest_report.main(_argv(fixtures))
    assert code == 0, capsys.readouterr().err
    markdown = (fixtures["out"] / "report.md").read_text(encoding="utf-8")

    assert "+1 of 12 held-out tasks (baseline 2 of 12, final 3 of 12)" in markdown, (
        "WHY THIS IS A FAILURE: the promoted decision does not render the § 4 headline "
        "with the candidate as the final side — the door must pass the record's "
        "decision and counts through"
    )
    assert "coverage 12 of 12     N: 1 at baseline, 2 at final" in markdown, (
        "WHY THIS IS A FAILURE: the headline's coverage is not the final side's "
        "covered count, or the `N` pair is not the baseline's and candidate's "
        "`weaker_wins`"
    )
    assert "candidate (final)" in markdown, (
        "WHY THIS IS A FAILURE: the comparison table does not label the candidate as "
        "final"
    )

    payload = json.loads((fixtures["out"] / "report.json").read_text(encoding="utf-8"))
    assert payload["decision"] == "promoted", payload
    assert payload["headline"] == {
        "delta": 1,
        "denominator": HELDOUT,
        "baseline_solved": 2,
        "final_solved": 3,
        "coverage": HELDOUT,
        "final_side": "candidate",
    }, payload["headline"]
    assert payload["n"]["baseline"]["count"] == 1, payload["n"]
    assert payload["n"]["final"]["count"] == 2, payload["n"]
    ledger_raw = json.loads(fixtures["ledger"].read_text(encoding="utf-8"))
    assert (
        payload["provenance"]["generation_contract"]["sampler"]
        == ledger_raw["generation_contract"]["sampler"]
    ), payload["provenance"]["generation_contract"]
    artifact = json.loads(fixtures["baseline"].read_text(encoding="utf-8"))
    assert (
        payload["provenance"]["base_sentence"] == artifact["base"]["sentence"]
    ), payload["provenance"]["base_sentence"]


def test_a_rejected_decision_renders_the_incumbent_as_final_with_the_candidate_disclosed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PRD gate-resolution 4: rejected → the incumbent's counts are final; the candidate
    is disclosed as the rejected attempt.

    Nothing shipped under a rejection, so the headline's "final" is the incumbent's
    counts — the delta against the baseline is the honest zero — and the candidate's
    counts render beside them labelled as the rejected attempt, never "final".
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path / "one")
    record = _record(
        tmp_path / "one",
        decision=gate.Exit.REJECTED,
        candidate_solved=1,
        candidate_weaker_wins=0,
    )

    code = honest_report.main(_argv(fixtures, record=record))
    assert code == 0, capsys.readouterr().err
    markdown = (fixtures["out"] / "report.md").read_text(encoding="utf-8")

    assert "+0 of 12 held-out tasks (baseline 2 of 12, final 2 of 12)" in markdown, (
        "WHY THIS IS A FAILURE: a rejected decision must render the incumbent as "
        "final — the delta is the incumbent's against the baseline"
    )
    assert "candidate (rejected attempt)" in markdown, (
        "WHY THIS IS A FAILURE: the candidate's counts are not labelled as the "
        "rejected attempt"
    )
    assert "incumbent (final)" in markdown, (
        "WHY THIS IS A FAILURE: the incumbent's counts are not labelled as final"
    )
    payload = json.loads((fixtures["out"] / "report.json").read_text(encoding="utf-8"))
    assert payload["headline"]["final_side"] == "incumbent", payload["headline"]
    assert payload["n"]["final"]["count"] == 1, payload["n"]


def test_an_unverified_decision_renders_no_headline_and_no_delta(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PRD gate-resolution 4: UNVERIFIED → no headline, no delta, "no comparison was made".

    No comparison was actually made (`PREREGISTRATION.md:111-114`), so the document
    holds no `+a of b held-out tasks` line, no coverage line, no `N at
    baseline/at final` line, and no reading of either side as "final".
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path / "one")
    record = _record(
        tmp_path / "one",
        decision=gate.Exit.UNVERIFIED,
        decision_unverified=1,
        candidate_solved=2,
        incumbent_solved=2,
        candidate_weaker_wins=1,
    )

    code = honest_report.main(_argv(fixtures, record=record))
    assert code == 0, capsys.readouterr().err
    markdown = (fixtures["out"] / "report.md").read_text(encoding="utf-8")

    assert "UNVERIFIED" in markdown, (
        "WHY THIS IS A FAILURE: the decision is not stated — a reader could not tell "
        "this document from one that made a comparison"
    )
    assert "no comparison was made" in markdown.lower(), (
        "WHY THIS IS A FAILURE: the document does not state that no comparison was "
        "made — the sentence is the whole reason the headline is absent"
    )
    assert not re.search(r"\+?\s*-?\d+\s+of\s+\d+\s+held-out tasks", markdown), (
        "WHY THIS IS A FAILURE: the document renders a headline for an evaluation "
        "that never compared anything. A delta is a comparison, and none was made"
    )
    assert not re.search(r"coverage\s+\d+\s+of\s+\d+", markdown), (
        "WHY THIS IS A FAILURE: the headline's coverage line renders where the "
        "headline is forbidden"
    )
    assert "at baseline" not in markdown and "at final" not in markdown, (
        "WHY THIS IS A FAILURE: the headline's `N: f at baseline, g at final` line "
        "renders — but without a comparison there is no final side and no paired `N`"
    )
    for banned in ("final counts", "final side", "(final)", "at final"):
        assert banned not in markdown, (
            "WHY THIS IS A FAILURE: "
            f"{banned!r} appears in a document whose evaluation made no comparison"
        )
    assert "candidate" in markdown and "incumbent" in markdown, (
        "WHY THIS IS A FAILURE: the decision's counts — both sides' — are not rendered"
    )


def test_render_declaration_writes_the_pre_run_state_and_is_rerunnable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 3: the declaration writes the writer's pre-run state and re-running it
    rewrites the same declaration — a declaration is not a measurement.

    The committed artifacts hold the "No count is measured here" sentence and no
    figure in any spelling; a second invocation exits 0 and rewrites the same bytes
    (the measured-once refusal is deliberately not applied), and a gitignored `--out`
    is refused by name.
    """
    from whetstone.loop import honest_report

    out = tmp_path / "declaration"
    code = honest_report.main(
        ["--render-declaration", str(out), "--recorded-on", _RECORDED_ON]
    )
    assert code == 0, capsys.readouterr().err
    for name in ("report.md", "report.json", "cost.json"):
        assert (out / name).is_file(), name
    text = "\n".join(
        (out / name).read_text(encoding="utf-8")
        for name in ("report.md", "report.json", "cost.json")
    )
    assert "No count is measured here: the report has not run." in text, text
    assert not re.search(r"\d+ of \d+", text), (
        "WHY THIS IS A FAILURE: the declaration renders a figure, but no measurement "
        "exists — a count here would be a restated figure from another home or an "
        "invented one"
    )
    payload = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert payload["measured"] is False, payload
    for name in ("sides", "headline", "n", "funnel", "series", "provenance"):
        assert name not in payload, (
            f"WHY THIS IS A FAILURE: the declaration carries {name}, but no "
            "measurement exists"
        )

    first_bytes = {
        name: (out / name).read_bytes()
        for name in ("report.md", "report.json", "cost.json")
    }

    second = honest_report.main(
        ["--render-declaration", str(out), "--recorded-on", _RECORDED_ON]
    )
    assert second == 0
    for name, bytes_before in first_bytes.items():
        assert (out / name).read_bytes() == bytes_before, (
            "WHY THIS IS A FAILURE: re-running the declaration changed its bytes — "
            "the declaration is not a measurement, and re-running it must rewrite the "
            "same declaration"
        )

    runs_out = tmp_path / "runs" / "declaration"
    code = honest_report.main(
        ["--render-declaration", str(runs_out), "--recorded-on", _RECORDED_ON]
    )
    assert code == 2
    assert "runs" in capsys.readouterr().err
    assert not runs_out.exists()


# --------------------------------------------------------------------------------------------
# Phase 5: the harness-reproduces-the-number check — P4 exit criterion 3, at the count
# level, proven end-to-end through the real door.
# --------------------------------------------------------------------------------------------


def test_the_render_is_byte_identical_across_invocations_and_subprocesses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 7: one fixture pair renders the same bytes every time, in this process and in
    fresh ones under different hash seeds.

    The report is a pure, deterministic function of the sealed evidence — a reader who
    regenerates it and gets different bytes cannot tell a re-render from a
    re-measurement. The subprocess half is not ceremony: mapping and set iteration
    order are the two things that vary across processes and not within one, and
    `PYTHONHASHSEED` is what makes that variation actually happen.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path / "one")
    assert honest_report.main(_argv(fixtures)) == 0
    first = {
        name: (fixtures["out"] / name).read_bytes()
        for name in ("report.md", "report.json", "cost.json")
    }

    second = _fixtures(tmp_path / "two")
    assert honest_report.main(_argv(second)) == 0
    for name, bytes_before in first.items():
        assert (second["out"] / name).read_bytes() == bytes_before, (
            f"WHY THIS IS A FAILURE: {name} differs between two renders of the same "
            "fixture pair in this process"
        )

    for seed, out in (("0", tmp_path / "sub-0"), ("1", tmp_path / "sub-1")):
        program = (
            f"import sys; sys.path.insert(0, {str(REPO_ROOT)!r});"
            "from whetstone.loop import honest_report;"
            f"sys.exit(honest_report.main({_argv(fixtures, out=out)!r}))"
        )
        run = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": seed},
        )
        assert run.returncode == 0, run.stderr
        for name, bytes_before in first.items():
            assert (out / name).read_bytes() == bytes_before, (
                f"WHY THIS IS A FAILURE: {name} depends on the process that produced "
                f"it (hash seed {seed}) — some mapping or set is serialised in "
                "iteration order"
            )


def test_the_baseline_side_figures_are_the_sealed_artifacts_own_byte_for_byte(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 6: the report's baseline-side figures equal the sealed artifact's figures —
    the loader-by-identity exception, proven end-to-end through the real door.

    The door feeds the writer the artifact's own counts — never a copy, never a
    re-derivation — so the rendered figures cannot disagree with the artifact that
    owns them: the one-home guard admits exactly these figures.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)
    assert honest_report.main(_argv(fixtures)) == 0

    artifact = json.loads(fixtures["baseline"].read_text(encoding="utf-8"))
    payload = json.loads((fixtures["out"] / "report.json").read_text(encoding="utf-8"))
    markdown = (fixtures["out"] / "report.md").read_text(encoding="utf-8")

    assert payload["sides"]["baseline"] == artifact["sides"], (
        "WHY THIS IS A FAILURE: the report's baseline-side counts are not the sealed "
        "artifact's own — the loader-by-identity exception admits exactly the "
        "artifact's figures, nothing else"
    )
    source_b = artifact["sides"]["source-b"]
    for field in ("solved", "covered", "unverified", "failed", "weaker_wins"):
        assert f"{source_b[field]} of {source_b['denominator']}" in markdown, (
            f"WHY THIS IS A FAILURE: source B's {field} figure does not render as the "
            "artifact's own, over its own denominator"
        )
    source_a = artifact["sides"]["source-a"]
    assert f"{source_a['solved']} of {source_a['denominator']}" in markdown, (
        "WHY THIS IS A FAILURE: source A's solved figure does not render as the "
        "artifact's own"
    )
    assert f"baseline {source_b['solved']} of {source_b['denominator']}" in markdown, (
        "WHY THIS IS A FAILURE: the headline's baseline term is not the artifact's "
        "solved count"
    )
    assert f"N: {source_b['weaker_wins']} at baseline" in markdown, (
        "WHY THIS IS A FAILURE: the headline's baseline `N` is not the artifact's "
        "`weaker_wins`"
    )


def test_a_doctored_record_is_refused_on_read_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 2: a record whose counts no longer sum is refused on read — the reader's
    consistency assertions hold end-to-end through the real door.

    A moved count is the one edit nobody checks: the record's counts are the final
    side of the delta, and the reader's `solved + failed + unverified == denominator`
    check refuses it by name, nothing written.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path / "one")
    record = _record(tmp_path / "one")
    raw = json.loads(record.read_text(encoding="utf-8"))
    raw["sides"]["candidate"]["private"]["solved"] += 1
    record.write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    code = honest_report.main(_argv(fixtures))

    assert code == 2
    message = capsys.readouterr().err
    assert "do not sum" in message, message
    assert not fixtures["out"].exists(), (
        "WHY THIS IS A FAILURE: a refused render wrote artifacts — a record that "
        "cannot be trusted is not evidence"
    )


def test_the_heldout_pointer_is_never_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--heldout` is a pointer, never parsed — the comparison.py `--stratum-doc`
    precedent.

    The series check runs on the documents' own digests, so a held-out path that does
    not even exist cannot refuse the render: the pointer is for the operator's
    command line, never for the door's reads.
    """
    from whetstone.loop import honest_report

    fixtures = _fixtures(tmp_path)

    code = honest_report.main(
        _argv(fixtures, heldout=tmp_path / "does-not-exist.json")
    )

    assert code == 0, capsys.readouterr().err
    assert (fixtures["out"] / "report.json").is_file()