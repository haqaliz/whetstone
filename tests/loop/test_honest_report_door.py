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
from collections.abc import Mapping
from pathlib import Path

import pytest

from whetstone.bakeoff import report as bakeoff_report
from whetstone.bakeoff.report import build_baseline_report, write_baseline_report
from whetstone.loop import baseline, gate, sft
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