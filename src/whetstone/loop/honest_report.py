"""The honest-number report door — compose the sealed evidence, refuse every half-truth render.

`PREREGISTRATION.md` § 4 fixes the P4 report's shape, the writer
(`report.build_honest_number_report`) renders it, and the sealed evidence documents own
every figure in it. This module is the **door** — the only place those documents may be
composed (`docs/planning/honest-number-report/report-door/`): it reads the § 3 baseline
artifact fail-closed (`read_baseline_document`), the promotion record fail-closed
(`read_promotion_record`), re-hashes both checkpoints (`verify_checkpoint`), verifies
that the record, the checkpoints and the baseline belong to one series — a delta
across a changed pinned input is not a delta (`PREREGISTRATION.md:92-94`) — and
refuses every half-truth render by name, nothing written, exit 2, no fifth exit code.
The writer pair is composed **by identity**; the provenance the record lacks — the
generation contract, the seeds and the task set — comes from the run's ledger
(`runs/<run-id>/ledger.json`, located from the record's own home), and source A's
funnel comes from the committed filter ledger. `--heldout` is a pointer the door never
parses.

The decision semantics are the gate's and the writer's, passed through verbatim:
promoted → the candidate is final; rejected → the incumbent is final with the candidate
disclosed as the rejected attempt; UNVERIFIED → no headline and no delta, the decision
and both sides' counts, "no comparison was made".

The door reads documents and renders only: no scoring, no model calls, no `mlx` import
anywhere. `recorded_on` is an input, never the clock.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from whetstone.bakeoff import report as bakeoff_report
from whetstone.bakeoff.report import GenerationContract, HonestNumberInput
from whetstone.bakeoff.stratum import OutUnderLocalCorpus
from whetstone.loop.baseline import read_baseline_document
from whetstone.loop.gate import _checkpoint_base, read_promotion_record
from whetstone.loop.heldout import refuse_committed_out
from whetstone.loop.ledger import LedgerUnreadable
from whetstone.loop.ledger import read as read_ledger
from whetstone.loop.sft import CheckpointUnverified, verify_checkpoint

#: The committed source-A funnel ledger the report renders beside source B, at its fixed
#: committed path — the four-gate filter is a committed document, never a flag.
FUNNEL_DOCUMENT = Path(__file__).resolve().parents[3] / "tasks" / "public" / "ineligible.json"

#: What the run ledger is called inside a run directory — the sibling of the record's
#: own `runs/promotions/` home.
LEDGER_FILE = "ledger.json"

#: The writer pair, by identity — the door renders and writes through the bake-off's
#: own functions, never a copy, so the committed document and the writer cannot
#: disagree about what was rendered.
build_honest_number_report = bakeoff_report.build_honest_number_report
write_honest_number_report = bakeoff_report.write_honest_number_report


class BaselineUnmeasured(ValueError):
    """A declaration-state baseline has no counts to delta against — refused by name."""


class SeriesMismatch(ValueError):
    """The promotion record or a checkpoint names a different series than the baseline.

    A delta computed across a change to any pinned input is not a delta
    (`PREREGISTRATION.md:92-94`): the held-out document digest and the candidate's
    base identity must each equal the baseline series', or the render is refused by
    name, never rendered past.
    """


class BaseMismatch(ValueError):
    """The candidate and incumbent checkpoints declare different bases.

    Two nights on different bases means the gate compared incomparables — refused by
    name, never published as a delta.
    """


class RunIdentityMismatch(ValueError):
    """`--run-id` is not the promotion record's own `run_id`.

    The flag exists to pin the record's identity: a record whose run id differs from
    the one the operator named is not the record the command was about.
    """


class HonestNumberAlreadyMeasured(ValueError):
    """A same-series report already sits at `--out` — the measured-once posture.

    The report is a pure function of its sealed evidence, so a second render of the
    same series would be the first render wearing a second date. A **changed** pinned
    input is a legitimate new series, rendered beside it, never refused.
    """


class FunnelUnreadable(ValueError):
    """The committed funnel ledger cannot be read — a broken checkout is refused, never
    rendered past."""


#: Every refusal this module raises that is an **operator's error** rather than a
#: finding: an `--out` under a gitignored root, a baseline that cannot be read or is a
#: declaration, a promotion record that cannot be read, a checkpoint that cannot be
#: re-hashed, a run id that is not the record's, a series that disagrees (the held-out
#: document digest or the candidate's base), an incumbent on a different base, a
#: same-series artifact already at `--out`, the run ledger that cannot be read, and
#: the funnel ledger that cannot be read. Collected here so the door maps them to the
#: usage code without a chain of per-module excepts; `ValueError` closes the tuple —
#: the named refusals first, and a door that crashes on an unforeseen `ValueError`
#: with a traceback is worse than a named exit-2.
REFUSALS: tuple[type[Exception], ...] = (
    OutUnderLocalCorpus,
    CheckpointUnverified,
    LedgerUnreadable,
    BaselineUnmeasured,
    SeriesMismatch,
    BaseMismatch,
    RunIdentityMismatch,
    HonestNumberAlreadyMeasured,
    FunnelUnreadable,
    ValueError,
)


def _counts(side_counts: Any) -> dict[str, int]:
    """One source's six fields as plain JSON types — the shape the writer reads."""
    return {
        "denominator": side_counts.denominator,
        "solved": side_counts.solved,
        "unverified": side_counts.unverified,
        "covered": side_counts.covered,
        "failed": side_counts.failed,
        "weaker_wins": side_counts.weaker_wins,
    }


def _read_funnel() -> Mapping[str, Any]:
    """The committed four-gate filter, in the writer's funnel shape.

    The filter is a committed document at a fixed path — the eligibility and the
    refusals by gate, every count over its own denominator — never a flag and never a
    hand-typed copy. A broken checkout is refused by name, never rendered past.
    """
    try:
        raw: Any = json.loads(FUNNEL_DOCUMENT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FunnelUnreadable(
            f"the committed funnel ledger {str(FUNNEL_DOCUMENT)!r} could not be read: "
            f"{exc}"
        ) from exc
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("counts"), dict)
        or not isinstance(raw.get("eligible"), list)
        or not isinstance(raw.get("execution_order"), list)
    ):
        raise FunnelUnreadable(
            f"the committed funnel ledger {str(FUNNEL_DOCUMENT)!r} is not the "
            "four-gate shape; a filter this door cannot read is a denominator nobody "
            "can check"
        )
    counts = raw["counts"]
    return {
        "considered": counts["input"],
        "eligible": list(raw["eligible"]),
        "refused": counts["ineligible"],
        "by_gate": [
            (gate, counts[gate])
            for gate in raw["execution_order"]
            if isinstance(counts.get(gate), int) and counts[gate] > 0
        ],
    }


def _existing_series(out: Path) -> tuple[tuple[str, str, str], str] | None:
    """The series an artifact already at `out/report.json` declares, or None.

    `None` covers both "no artifact" and "a declaration artifact" — a declaration
    carries no series and is not a measurement, so a render overwrites it, never
    refuses it. An artifact that exists but cannot be read is refused by name, never
    treated as absent: the unreadable case and the absent case exit identically and
    are opposite facts.
    """
    artifact = Path(out) / "report.json"
    if not artifact.is_file():
        return None
    try:
        raw: Any = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"the honest-number artifact {str(artifact)!r} could not be read: {exc}"
        ) from exc
    series_block = raw.get("series") if isinstance(raw, dict) else None
    if not isinstance(series_block, dict):
        return None
    repo_id = series_block.get("repo_id")
    revision = series_block.get("revision")
    heldout_digest = series_block.get("heldout_digest")
    recorded_on = raw.get("recorded_on")
    if (
        not isinstance(repo_id, str)
        or not isinstance(revision, str)
        or not isinstance(heldout_digest, str)
        or not isinstance(recorded_on, str)
    ):
        raise ValueError(
            f"the honest-number artifact {str(artifact)!r} carries an unreadable "
            "series or recorded_on; a half-parsed artifact is refused, never treated "
            "as absent"
        )
    return (repo_id, revision, heldout_digest), recorded_on


def _input(
    document: Any,
    promotion: Any,
    ledger_document: Mapping[str, Any],
    series: Any,
    funnel: Mapping[str, Any],
    recorded_on: str,
) -> HonestNumberInput:
    """The writer's input, composed from the sealed documents and the run ledger.

    The baseline-side figures are the sealed artifact's own counts, fed through — the
    loader-by-identity exception the one-home guard admits. The candidate's and
    incumbent's are the promotion record's own. The decision is the record's exit
    verbatim — whose counts are "final" is the writer's, decided by that value. The
    provenance the record lacks comes from the run ledger: the generation contract in
    the bake-off's own shape, the declared run seed with the applied seeds, and the
    task set the night drew against. The § 7.3-open base sentence is the baseline
    artifact's own, verbatim.
    """
    contract_block = ledger_document["generation_contract"]
    contract = GenerationContract(
        prompt_sha256=contract_block["prompt_sha256"],
        sampler=contract_block["sampler"],
        max_tokens=contract_block["max_tokens"],
        extractor_version=contract_block["extractor_version"],
        dev_subset=tuple(contract_block["dev_subset"]),
        retry_budget=contract_block["retry_budget"],
        retry_template_sha256=contract_block["retry_template_sha256"],
        diagnosis_vocabulary_version=contract_block["diagnosis_vocabulary_version"],
        retrieval=contract_block["retrieval"],
    )
    task_set = ledger_document["task_set"]
    return HonestNumberInput(
        sides={
            "baseline": {
                "source-b": dict(document.sides["source-b"]),
                "source-a": dict(document.sides["source-a"]),
            },
            "candidate": {
                "source-b": _counts(promotion.sides["candidate"].private),
                "source-a": _counts(promotion.sides["candidate"].public),
            },
            "incumbent": {
                "source-b": _counts(promotion.sides["incumbent"].private),
                "source-a": _counts(promotion.sides["incumbent"].public),
            },
        },
        decision=promotion.decision["exit"],
        funnel=funnel,
        series={
            "repo_id": series.repo_id,
            "revision": series.revision,
            "heldout_digest": series.heldout_digest,
        },
        provenance={
            "seeds": (
                f"run seed {ledger_document['run_seed']} with "
                f"{len(ledger_document['seeds'])} per-attempt seeds applied"
            ),
            "task_set": (
                f"{task_set['private']} source-B tasks and {task_set['public']} "
                "source-A instance(s), scored in full"
            ),
            "tool_versions": dict(promotion.tool_versions),
            "base_sentence": document.base["sentence"],
            "retry_count": promotion.retry_count,
            "retries": [
                {
                    "task_id": one["task_id"],
                    "before": one["before"],
                    "after": one["after"],
                    "retries_used": one["retries_used"],
                }
                for one in promotion.retries
            ],
            "contract": contract,
        },
        recorded_on=recorded_on,
    )


def render(
    *,
    baseline_path: Path,
    record_path: Path,
    candidate_path: Path,
    incumbent_path: Path,
    out: Path,
    recorded_on: str,
    run_id: str,
) -> tuple[Path, Path, Path]:
    """Render the three artifacts from the sealed evidence, or refuse by name.

    Every refusal happens before anything is written: `--out` under a gitignored root
    (`refuse_committed_out` by identity, before anything is loaded); a baseline that
    cannot be read or is a declaration; a promotion record that cannot be read; a
    checkpoint that cannot be re-hashed (candidate and incumbent alike); a promotion
    record whose run id is not the one the command named; a held-out document digest
    that differs from the baseline series'; a candidate whose base identity differs
    from the series'; an incumbent on a different base than the candidate; a
    same-series artifact already at `--out` (the measured-once posture — a **changed**
    pinned input is a new series, rendered); a run ledger that cannot be read; and a
    funnel ledger that cannot be read. The series is the key, never the clock.
    """
    refuse_committed_out(out)
    document = read_baseline_document(baseline_path)
    if not document.measured:
        raise BaselineUnmeasured(
            f"baseline artifact {str(baseline_path)!r} is a declaration "
            f"(measured: false): it carries no counts, no series and no sides, and a "
            "delta against it would be a delta against nothing. The § 3 baseline must "
            "be measured before any final score can be reported against it"
        )
    if document.series is None:
        raise BaselineUnmeasured(
            f"baseline artifact {str(baseline_path)!r} carries no series; a measured "
            "baseline always names its base and its held-out document"
        )
    series = document.series
    promotion = read_promotion_record(record_path)
    if promotion.run_id != run_id:
        raise RunIdentityMismatch(
            f"the promotion record {str(record_path)!r} declares run id "
            f"{promotion.run_id!r}, and the command line named {run_id!r}; a record "
            "that is not this run's is not the evidence this render was about"
        )
    candidate_checkpoint = verify_checkpoint(candidate_path)
    incumbent_checkpoint = verify_checkpoint(incumbent_path)
    if promotion.heldout_digest != series.heldout_digest:
        raise SeriesMismatch(
            f"the promotion record {str(record_path)!r} carries held-out document "
            f"digest {promotion.heldout_digest!r}, and the baseline series was "
            f"measured over {series.heldout_digest!r}; a delta across a changed "
            "pinned input is not a delta, and none is rendered"
        )
    candidate_base = _checkpoint_base(candidate_checkpoint)
    incumbent_base = _checkpoint_base(incumbent_checkpoint)
    if (candidate_base["repo_id"], candidate_base["revision"]) != (
        series.repo_id,
        series.revision,
    ):
        raise SeriesMismatch(
            f"the candidate checkpoint {str(candidate_path)!r} declares base "
            f"{candidate_base['repo_id']!r} at {candidate_base['revision']!r}, and "
            f"the baseline series is {series.repo_id!r} at {series.revision!r}; a "
            "delta across a changed pinned input is not a delta, and none is rendered"
        )
    if candidate_base != incumbent_base:
        raise BaseMismatch(
            f"the incumbent checkpoint {str(incumbent_path)!r} declares base "
            f"{incumbent_base['repo_id']!r} at {incumbent_base['revision']!r}, and "
            f"the candidate declares {candidate_base['repo_id']!r} at "
            f"{candidate_base['revision']!r}; two nights on different bases compared "
            "incomparables, and the gate's decision is not a delta"
        )
    existing = _existing_series(out)
    if existing is not None and existing[0] == (
        series.repo_id,
        series.revision,
        series.heldout_digest,
    ):
        raise HonestNumberAlreadyMeasured(
            f"series (base {series.repo_id} at {series.revision}, held-out document "
            f"{series.heldout_digest}) at {str(Path(out) / 'report.json')!r} was "
            f"already rendered on {existing[1]}; the report is a pure function of its "
            "sealed evidence, so a second render would be the first render wearing a "
            "second date. A changed pinned input is a new series, never a second "
            "render"
        )
    ledger_document = read_ledger(
        Path(record_path).parent.parent / promotion.run_id / LEDGER_FILE
    )
    funnel = _read_funnel()
    report_document = build_honest_number_report(
        _input(
            document=document,
            promotion=promotion,
            ledger_document=ledger_document,
            series=series,
            funnel=funnel,
            recorded_on=recorded_on,
        )
    )
    return write_honest_number_report(report_document, out)


def render_declaration(*, out: Path, recorded_on: str) -> tuple[Path, Path, Path]:
    """Write the declaration-only state — the committed artifacts before any render.

    The state *before* the operator chain produces a decision: `measured=False`
    through the writer, holding the "No count is measured here" sentence and no figure
    in any spelling. This is the pre-run state, committed once, so the measured-once
    refusal is deliberately NOT applied — the declaration is not a measurement, and
    re-running it rewrites the same declaration, never a second measurement wearing
    the name of a first. `out` under a gitignored root is refused by identity: the
    declaration is a committed artifact, and one git cannot see is one git cannot
    prove predated the measurement.
    """
    refuse_committed_out(out)
    document = build_honest_number_report(
        HonestNumberInput(
            sides={},
            decision="",
            funnel={},
            series={},
            provenance={},
            recorded_on=recorded_on,
        ),
        measured=False,
    )
    return write_honest_number_report(document, out)


# --------------------------------------------------------------------------------------------
# The module door — `python -m whetstone.loop.honest_report`. A clean render exits 0; a
# refusal exits 2 with the reason named, never a traceback; argparse's own error path
# supplies the usage code for a mistyped or incomplete command line. The parser is a
# single module-level `build_parser()` so the aspect-5 runbook guard can pin the
# runbook's flags against it by identity.
# --------------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """The door's argument surface — the one the aspect-5 runbook guard pins by identity.

    The spec's full flag set (`report-door/spec.md` AC 9): the two render modes, the
    evidence pointers (the sealed baseline artifact, the promotion record, both
    checkpoints, and `--heldout` — a pointer the door never parses, on the
    comparison.py `--stratum-doc` precedent), `--out`, `--recorded-on` (required in
    every mode — an input, never a default from the clock) and `--run-id` (the
    promotion record's identity — a record that is not this run's is refused). There
    is no retry knob, no seed flag, no scoring flag: the door reads documents and
    renders, and the runbook can pin nothing else against it.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.loop.honest_report",
        description=(
            "Render the P4 honest-number report from the sealed evidence: the § 3 "
            "baseline artifact, the promotion record and both checkpoints, through "
            "the writer; or write the declaration-only state (--render-declaration "
            "OUT). Every refusal is by name, nothing written, exit 2 — no scoring, "
            "no model calls: the door reads documents and renders."
        ),
    )
    parser.add_argument(
        "--baseline", type=Path, help="the sealed § 3 baseline artifact (report.json)"
    )
    parser.add_argument(
        "--record",
        type=Path,
        help="the promotion record (runs/promotions/<run-id>.json)",
    )
    parser.add_argument(
        "--checkpoint-candidate",
        type=Path,
        help="the candidate checkpoint directory, re-hashed before anything renders",
    )
    parser.add_argument(
        "--checkpoint-incumbent",
        type=Path,
        help="the incumbent checkpoint directory, re-hashed before anything renders",
    )
    parser.add_argument(
        "--heldout",
        type=Path,
        help=(
            "the committed held-out document (tasks/heldout/source-b.json) — a "
            "pointer the door never parses: the series check runs on the documents' "
            "own digests"
        ),
    )
    parser.add_argument(
        "--out", type=Path, help="where the three artifacts are written"
    )
    parser.add_argument(
        "--recorded-on",
        required=True,
        help="the date the operator declares — an input, never the clock",
    )
    parser.add_argument(
        "--run-id",
        help="the promotion record's run id — the record's identity",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help=(
            "render the three artifacts from the sealed evidence; mutually exclusive "
            "with --render-declaration"
        ),
    )
    parser.add_argument(
        "--render-declaration",
        dest="render_declaration",
        type=Path,
        metavar="OUT",
        help=(
            "write the declaration-only state — the committed artifacts before any "
            "render — to OUT; mutually exclusive with --render"
        ),
    )
    return parser


def _render_main(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """The render-mode command line: every pointer present, one render, exit 0."""
    missing = [
        name
        for name, value in (
            ("--baseline", args.baseline),
            ("--record", args.record),
            ("--checkpoint-candidate", args.checkpoint_candidate),
            ("--checkpoint-incumbent", args.checkpoint_incumbent),
            ("--heldout", args.heldout),
            ("--out", args.out),
            ("--run-id", args.run_id),
        )
        if value is None
    ]
    if missing:
        parser.error(f"{', '.join(missing)} is required with --render")
    try:
        rendered = render(
            baseline_path=args.baseline,
            record_path=args.record,
            candidate_path=args.checkpoint_candidate,
            incumbent_path=args.checkpoint_incumbent,
            out=args.out,
            recorded_on=args.recorded_on,
            run_id=args.run_id,
        )
    except REFUSALS as refusal:
        print(f"whetstone honest-report: {refusal}", file=sys.stderr)
        return 2
    for path in rendered:
        print(path)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """The runbook door: `python -m whetstone.loop.honest_report`.

    Parses and dispatches the two modes the parser admits. Rendering exits 0 and
    prints the artifact paths; declaring writes the committed pre-run state and exits
    0. Every named refusal is exit 2 with the reason named on stderr, never a
    traceback; argparse's own error path supplies the usage code for a mistyped or
    incomplete command line, and naming both modes is refused with the same code —
    the modes are mutually exclusive.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.render and args.render_declaration is not None:
        parser.error(
            "--render and --render-declaration are mutually exclusive; name one mode"
        )
    if args.render:
        return _render_main(parser, args)
    if args.render_declaration is not None:
        try:
            rendered = render_declaration(
                out=args.render_declaration, recorded_on=args.recorded_on
            )
        except REFUSALS as refusal:
            print(f"whetstone honest-report: {refusal}", file=sys.stderr)
            return 2
        for path in rendered:
            print(path)
        return 0
    parser.error("one of --render or --render-declaration is required")


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FUNNEL_DOCUMENT",
    "LEDGER_FILE",
    "REFUSALS",
    "BaseMismatch",
    "BaselineUnmeasured",
    "FunnelUnreadable",
    "HonestNumberAlreadyMeasured",
    "RunIdentityMismatch",
    "SeriesMismatch",
    "build_parser",
    "main",
    "render",
    "render_declaration",
]