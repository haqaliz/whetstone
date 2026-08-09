"""Measure the retry-eligible ceiling over stored autopsy documents, before the arm spends.

The measured arm (`docs/planning/p2-format-hardening/measured-arm/spec.md`, D-arm1) is a GPU
pass with a halt condition that must be computed before any GPU spend: of the stored runs'
parse-refusal records, how many could a retry plausibly convert? This module is that
computation — offline, deterministic, stdlib-only. It reads the stored `whetstone-autopsy/1`
documents (`runs/diff-autopsy/{arm-a,budget-2048}.json`, read by absolute path from the primary
checkout, never copied), applies the validator's own trigger mapping to every record, and
writes the `whetstone-preanalysis/1` ceiling document under a documented gitignored root.

**The mapping is diffcheck's own, applied to stored strings.** The stored records carry
`cause`/`detail` strings, not `AutopsyResult` objects, so this module calls
`diffcheck.trigger_of_cause` — the pure function `diffcheck.trigger_of` delegates to, asserted
by identity in `tests/bakeoff/test_preanalysis.py` — and never reimplements the decision.
`header-without-hunk` stays a non-trigger here (the mapping's parameter stays off until the
arm's evidence flips it) and is counted by name as a *flippable candidate*: the number the
arm's decision about that shape has behind it.

**The ceiling definition (D-arm1), written before the run.** A record is **retry-eligible**
exactly when the validator's own trigger mapping fires on its `(cause, detail)`:
`hunk-count-mismatch`, and a first-hunk `hunk-dies-early` death on a bare line or the closing
fence. A retry-eligible record's death is **inferred truncation** when its detail names the
`end-of-output` death (`DeathKind.END_OF_OUTPUT`): the completion ended with hunk counts still
remaining — budget truncation *inferred from shape*, never a measured token cap
(`finding.md:81-84`) — and a fresh draw of the same budget would plausibly stop at the same
place, so a retry would spend its draw on missing content. **The ceiling is retry-eligible
minus inferred truncation**: the retry-eligible records a retry could plausibly convert. It is
a measurement of what is already on disk, a finding's property, never a promise about the arm;
a ceiling near zero halts the arm (PRD R5, spec D-arm1). The definition travels into the
document as `CEILING_DEFINITION`, so the report that quotes the ceiling quotes its definition
with it.

**The non-trigger remainder is a closed set of six named buckets.** `im-start-loop`,
`hunk-dies-early/end-of-output` (the first-hunk deaths the mapping refuses), `well-formed`,
`no-diff`, `header-without-hunk`, and `unrecognised-shape` — every record the mapping leaves
to be graded, counted per cause. Unlike a growing partition, this is the fixed non-trigger
vocabulary of the measurement, so zeros are written and read as "this shape was not observed".

**The document is local evidence, refused under any published path.** The pre-analysis reads
stored autopsy outputs, which quote the user's own private donor code back verbatim, and its
document is the analysis of that private material. `--out` must sit under one of the same
gitignored roots the autopsy's own document refuses to leave (`autopsy.py:727-745`: resolved
both sides, `is_relative_to`, refused before anything is read, exit 2 with the reason named).
Each run is keyed by the stem of its autopsy document's path — `arm-a` and `budget-2048` for
the stored corpus — and a stem collision is refused by name rather than fused.

No model, no network, no `mlx`, no `run.py` (its own AST walk in
`tests/bakeoff/test_preanalysis.py` refuses all of them).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from whetstone.bakeoff.autopsy import (
    AUTOPSY_SCHEMA,
    IGNORED_OUT_ROOTS,
    DeathKind,
    FineCause,
)
from whetstone.bakeoff.diffcheck import trigger_of_cause

#: The document this module writes.
PREANALYSIS_SCHEMA = "whetstone-preanalysis/1"

#: The ceiling definition (spec D-arm1): written before the run, carried by every document the
#: module writes, and the exact arithmetic `_analyze` performs. A retry-eligible record is one
#: the validator's own mapping retries; inferred truncation is a retry-eligible record whose
#: detail names the `end-of-output` death — the shape of a completion that ran out of budget,
#: inferred, never measured — and such a record is not plausibly convertible by a draw of the
#: same budget. The ceiling is retry-eligible minus inferred truncation.
CEILING_DEFINITION = (
    "The ceiling is the number of retry-eligible records a retry could plausibly convert: "
    "retry-eligible minus inferred truncation. A record is retry-eligible exactly when the "
    "validator's own trigger mapping fires on its (cause, detail) (hunk-count-mismatch, or a "
    "first-hunk death on a bare line or the closing fence). Inferred truncation is the subset "
    "of retry-eligible records whose detail names the end-of-output death — the completion "
    "ended with hunk counts still remaining, which is budget truncation inferred from shape, "
    "never a measured token cap. The ceiling is a measurement of what is already on disk, a "
    "finding's property, never a promise about the arm; a ceiling near zero halts the arm."
)

#: The non-trigger remainder's fixed, closed vocabulary: every cause the mapping leaves to be
#: graded, counted per candidate. Zeros are written and read as "this shape was not observed".
NON_TRIGGER_REMAINDER_KEYS = (
    "im-start-loop",
    "hunk-dies-early/end-of-output",
    "well-formed",
    "no-diff",
    "header-without-hunk",
    "unrecognised-shape",
)


class _Totals(TypedDict):
    records: int
    retry_eligible: int
    inferred_truncation: int
    ceiling: int
    flippable_candidates: int


class _CandidateBlock(TypedDict):
    cause_counts: dict[str, int]
    trigger_counts: dict[str, int]
    retry_eligible: int
    inferred_truncation: int
    ceiling: int
    non_trigger_remainder: dict[str, int]
    flippable_candidates: int


class _RunAnalysis(TypedDict):
    autopsy: str
    records: int
    per_candidate: dict[str, _CandidateBlock]
    totals: _Totals
    retry_eligible_task_ids: list[str]


class _Combined(TypedDict):
    per_candidate: dict[str, _CandidateBlock]
    totals: _Totals


class _Measured(TypedDict):
    records: int
    per_candidate: dict[str, _CandidateBlock]
    totals: _Totals
    retry_eligible_task_ids: list[str]


class _UsageError(ValueError):
    """An invocation mistake the CLI reports as exit 2: a document that does not parse."""


class OutNotPrivate(ValueError):
    """An `--out` path git would commit. Raised before anything is read or written."""


@dataclass(frozen=True)
class _Record:
    """One stored autopsy record, strictly parsed: the two verdict fields the mapping needs.

    `markers`, `recorded_cause` and `coarse_agrees` travel in the document but play no part in
    the retry decision — the mapping is a pure function of `(cause, detail)` (`prd.md` R3) —
    so only the four keyable fields survive the parse, by name, never by guess.
    """

    candidate: str
    task_id: str
    cause: FineCause
    detail: str


def is_inferred_truncation(detail: str) -> bool:
    """Does the detail name the `end-of-output` death — the inferred truncation shape?

    The death is named by the autopsy's own vocabulary (`DeathKind.END_OF_OUTPUT`), never by
    a guessed string: `end-of-output` verbatim for a first-hunk death, `hunk N dies early:
    end-of-output` for a later-hunk death inside a `hunk-count-mismatch`. Either spelling
    means the completion ended with hunk counts still remaining, and a retry of the same
    budget would plausibly stop at the same place.
    """
    return DeathKind.END_OF_OUTPUT.value in detail


@dataclass
class _Counts:
    """The mutable counting state behind one candidate's block, typed until it is rendered."""

    causes: dict[str, int]
    triggers: dict[str, int]
    retry_eligible: int
    inferred_truncation: int
    remainder: dict[str, int]

    @classmethod
    def empty(cls) -> _Counts:
        return cls({}, {}, 0, 0, {key: 0 for key in NON_TRIGGER_REMAINDER_KEYS})

    def render(self) -> _CandidateBlock:
        """The document-shaped block: the ceiling and flippable count derived at the end."""
        return {
            "cause_counts": self.causes,
            "trigger_counts": self.triggers,
            "retry_eligible": self.retry_eligible,
            "inferred_truncation": self.inferred_truncation,
            "ceiling": self.retry_eligible - self.inferred_truncation,
            "non_trigger_remainder": self.remainder,
            "flippable_candidates": self.causes.get(
                FineCause.HEADER_WITHOUT_HUNK.value, 0
            ),
        }


def _analyze(records: Iterable[_Record]) -> _Measured:
    """The ceiling arithmetic: retry-eligible, inferred truncation, ceiling, remainders.

    Per candidate: every trigger that fired (`trigger_counts`, only fired triggers are listed),
    every cause that appeared (`cause_counts`), retry-eligible, inferred truncation among the
    retry-eligible, the ceiling, the closed non-trigger remainder, and the header-without-hunk
    flippable candidates. The totals sum the same numbers per run and, via `combine`, across
    runs. The ceiling definition is `CEILING_DEFINITION`, written before the run — this
    arithmetic is its code shape, and a mismatch between the two is a defect, not a tune.
    """
    parsed = tuple(records)
    per_candidate: dict[str, _Counts] = {}
    retry_eligible_ids: set[str] = set()

    for record in parsed:
        counts = per_candidate.setdefault(record.candidate, _Counts.empty())
        counts.causes[record.cause.value] = counts.causes.get(record.cause.value, 0) + 1

        trigger = trigger_of_cause(record.cause, record.detail)
        if trigger is not None:
            counts.triggers[trigger.value] = counts.triggers.get(trigger.value, 0) + 1
            counts.retry_eligible += 1
            if is_inferred_truncation(record.detail):
                counts.inferred_truncation += 1
            retry_eligible_ids.add(record.task_id)
            continue
        remainder_key = (
            "hunk-dies-early/end-of-output"
            if record.cause is FineCause.HUNK_DIES_EARLY
            else record.cause.value
        )
        counts.remainder[remainder_key] += 1

    return {
        "records": len(parsed),
        "per_candidate": {
            candidate: counts.render() for candidate, counts in per_candidate.items()
        },
        "totals": {
            "records": len(parsed),
            "retry_eligible": sum(
                counts.retry_eligible for counts in per_candidate.values()
            ),
            "inferred_truncation": sum(
                counts.inferred_truncation for counts in per_candidate.values()
            ),
            "ceiling": sum(
                counts.retry_eligible - counts.inferred_truncation
                for counts in per_candidate.values()
            ),
            "flippable_candidates": sum(
                counts.causes.get(FineCause.HEADER_WITHOUT_HUNK.value, 0)
                for counts in per_candidate.values()
            ),
        },
        "retry_eligible_task_ids": sorted(retry_eligible_ids),
    }


def _parse_autopsy_document(path: Path) -> tuple[_Record, ...]:
    """The stored autopsy document, parsed strictly — a row that does not parse is an error.

    The document must declare the autopsy's own schema (`AUTOPSY_SCHEMA`, imported by
    identity) and carry a `records` list; every row must be keyable: candidate, task id, and a
    cause string the taxonomy actually has a member for. A row that cannot be keyed is refused
    by name rather than matched by a guess — the alternative is an unknown cause drifting into
    whichever bucket happens to match, which is the invented-taxonomy failure this whole slice
    exists to refuse (`prd.md` § 8).
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise _UsageError(
            f"the autopsy document at {str(path)!r} could not be read as JSON "
            f"({type(exc).__name__}: {exc})"
        ) from exc
    except OSError as exc:
        raise _UsageError(
            f"the autopsy document at {str(path)!r} could not be read: {exc}"
        ) from exc
    if not isinstance(raw, dict) or raw.get("schema") != AUTOPSY_SCHEMA:
        raise _UsageError(
            f"the autopsy document at {str(path)!r} does not declare schema "
            f"{AUTOPSY_SCHEMA!r}, so its records cannot be trusted as the fine causes the "
            "autopsy named"
        )
    rows = raw.get("records")
    if not isinstance(rows, list):
        raise _UsageError(
            f"the autopsy document at {str(path)!r} carries no 'records' list, so there is "
            "nothing for the trigger mapping to measure"
        )

    parsed: list[_Record] = []
    for number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise _UsageError(
                f"autopsy record {number} of {str(path)!r} is not an object, so the trigger "
                "mapping cannot key it"
            )
        try:
            candidate = row["candidate"]
            task_id = row["task_id"]
            detail = row["detail"]
        except KeyError as exc:
            raise _UsageError(
                f"autopsy record {number} of {str(path)!r} is missing {exc.args[0]!r}, which "
                "is part of the verdict — a record that cannot be keyed is refused, not "
                "matched by a guess"
            ) from exc
        if not isinstance(candidate, str) or not isinstance(task_id, str):
            raise _UsageError(
                f"autopsy record {number} of {str(path)!r} names its candidate or task with "
                "a non-string, so the trigger mapping cannot key it"
            )
        if not isinstance(detail, str):
            raise _UsageError(
                f"autopsy record {number} of {str(path)!r} carries a non-string detail, so "
                "the death shape cannot be read from it"
            )
        try:
            cause = FineCause(row["cause"])
        except (KeyError, ValueError, TypeError) as exc:
            raise _UsageError(
                f"autopsy record {number} of {str(path)!r} names cause {row.get('cause')!r}, "
                f"which is not one of the taxonomy's fine causes "
                f"({', '.join(cause.value for cause in FineCause)})"
            ) from exc
        parsed.append(_Record(candidate, task_id, cause, detail))
    return tuple(parsed)


def analyze_document(path: Path) -> _RunAnalysis:
    """One stored autopsy document, whole: parsed, measured, and keyed by its path's stem.

    The run's key is the document's path stem — `arm-a` for `…/arm-a.json` — deterministic
    for the stored corpus. The caller refuses duplicate stems before this is consulted, so a
    key collision can never fuse two runs' numbers.
    """
    measured = _analyze(_parse_autopsy_document(path))
    return _RunAnalysis(
        autopsy=str(path),
        records=measured["records"],
        per_candidate=measured["per_candidate"],
        totals=measured["totals"],
        retry_eligible_task_ids=measured["retry_eligible_task_ids"],
    )


def combine(analyses: Iterable[_RunAnalysis]) -> _Combined:
    """The per-candidate and total sums across runs, candidates unioned.

    The same arithmetic shape as one run's analysis, summed: a candidate that appears in only
    one run keeps its own numbers, and the totals are the per-candidate sums.
    """
    merged: dict[str, _Counts] = {}
    records = 0
    for analysis in analyses:
        records += analysis["records"]
        for candidate, block in analysis["per_candidate"].items():
            counts = merged.setdefault(candidate, _Counts.empty())
            for key, value in block["cause_counts"].items():
                counts.causes[key] = counts.causes.get(key, 0) + value
            for key, value in block["trigger_counts"].items():
                counts.triggers[key] = counts.triggers.get(key, 0) + value
            counts.retry_eligible += block["retry_eligible"]
            counts.inferred_truncation += block["inferred_truncation"]
            for key, value in block["non_trigger_remainder"].items():
                counts.remainder[key] += value
    return {
        "per_candidate": {candidate: counts.render() for candidate, counts in merged.items()},
        "totals": {
            "records": records,
            "retry_eligible": sum(counts.retry_eligible for counts in merged.values()),
            "inferred_truncation": sum(
                counts.inferred_truncation for counts in merged.values()
            ),
            "ceiling": sum(
                counts.retry_eligible - counts.inferred_truncation
                for counts in merged.values()
            ),
            "flippable_candidates": sum(
                counts.causes.get(FineCause.HEADER_WITHOUT_HUNK.value, 0)
                for counts in merged.values()
            ),
        },
    }


def dev_subset_candidates(analyses: Iterable[_RunAnalysis]) -> tuple[str, ...]:
    """The task ids every stored run would retry: the ids the runbook's dev subset may pick from.

    A task the arm excludes via `--dev-subset` (spec D-arm2) is one whose prompts the retry
    template was tuned against — a task both stored runs' retry-eligible records carry. The
    intersection is over runs, and a run's set is the union across its candidates: the
    exclusion is per task, and a task retried by any candidate of a run is retried by that run.
    Sorted, so the same runs always name the same ids in the same order.
    """
    runs = tuple(analyses)
    if not runs:
        return ()
    common = set(runs[0]["retry_eligible_task_ids"])
    for analysis in runs[1:]:
        common &= set(analysis["retry_eligible_task_ids"])
    return tuple(sorted(common))


def refuse_published_out(out: Path) -> None:
    """Refuse an `--out` that does not sit under a documented gitignored root.

    The autopsy's own rule, `autopsy.py:727-745`, applied to this module's document: resolved
    rather than compared as written, and compared with `is_relative_to`, because
    `out/../out/x.json` and a symlinked scratch directory both name a path inside `out` while
    comparing unequal to it — the check has to hold against the path that gets written, not the
    one that got typed. `resolve()` never requires the path to exist, so an honest first run
    into a not-yet-created directory is not refused. The roots are the autopsy's own
    (`IGNORED_OUT_ROOTS`, imported by identity), so the two doors cannot drift apart about
    what is private.
    """
    if any(out.resolve().is_relative_to(Path(root).resolve()) for root in IGNORED_OUT_ROOTS):
        return
    raise OutNotPrivate(
        f"the document at {str(out)!r} does not sit under one of the documented gitignored "
        f"roots ({', '.join(IGNORED_OUT_ROOTS)}). The pre-analysis reads stored autopsy "
        "outputs, which quote the user's own private donor code back verbatim, and its ceiling "
        "document is local evidence for a halt decision — never a published figure. Point "
        "--out under one of those roots; this is refused rather than warned about because a "
        "warning is read after the file already exists"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Read the stored autopsy documents, measure the ceiling, and write the document.

    The door of the measured arm's Phase 1: `python -m whetstone.bakeoff.preanalysis
    --autopsy PATH [--autopsy PATH ...] --out PATH`. `--out` is checked **before** anything is
    loaded — the refusal is the autopsy's own locality discipline (`autopsy.py:727-745`)
    applied to this module's document — and a missing document, a document that does not parse,
    a cause the taxonomy has no member for, or two documents with the same path stem are each
    exit 2 with the reason named. A ceiling computed over documents that are not there would
    measure a run nobody made; a run key that collides would fuse two runs' numbers.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.bakeoff.preanalysis",
        description=(
            "Measure the retry-eligible ceiling over stored whetstone-autopsy/1 documents "
            "before the format-hardening arm spends: the validator's own trigger mapping "
            "applied to every stored record, per candidate, per run, and combined. Offline: "
            "no model is loaded and no network is touched, and the document is written only "
            "under a documented gitignored root."
        ),
    )
    parser.add_argument(
        "--autopsy",
        action="append",
        required=True,
        type=Path,
        help="a stored whetstone-autopsy/1 document (repeatable)",
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="where the document is written"
    )
    namespace = parser.parse_args(argv)

    out = namespace.out
    try:
        refuse_published_out(out)
    except OutNotPrivate as exc:
        print(f"whetstone preanalysis: {exc}", file=sys.stderr)
        return 2

    stems: dict[str, Path] = {}
    runs: dict[str, _RunAnalysis] = {}
    decisions: dict[str, list[dict[str, object]]] = {}
    for path in namespace.autopsy:
        if not path.is_file():
            print(
                f"whetstone preanalysis: {str(path)!r} is not a file. A ceiling computed over "
                "documents that are not there would measure a run nobody made — no records, no "
                "ceiling — which reads as 'every rollout measured and none found'",
                file=sys.stderr,
            )
            return 2
        stem = path.stem
        if stem in stems:
            print(
                f"whetstone preanalysis: the autopsy documents {str(stems[stem])!r} and "
                f"{str(path)!r} share the path stem {stem!r}, which is the key the document "
                "names the run under — that key is named twice, so the run is refused rather "
                "than fused with itself",
                file=sys.stderr,
            )
            return 2
        stems[stem] = path
        try:
            records = _parse_autopsy_document(path)
        except _UsageError as exc:
            print(f"whetstone preanalysis: {exc}", file=sys.stderr)
            return 2
        measured = _analyze(records)
        runs[stem] = _RunAnalysis(
            autopsy=str(path),
            records=measured["records"],
            per_candidate=measured["per_candidate"],
            totals=measured["totals"],
            retry_eligible_task_ids=measured["retry_eligible_task_ids"],
        )
        rows: list[dict[str, object]] = []
        for record in records:
            trigger = trigger_of_cause(record.cause, record.detail)
            rows.append(
                {
                    "candidate": record.candidate,
                    "task_id": record.task_id,
                    "cause": record.cause.value,
                    "detail": record.detail,
                    "trigger": None if trigger is None else trigger.value,
                    "inferred_truncation": (
                        trigger is not None and is_inferred_truncation(record.detail)
                    ),
                }
            )
        decisions[stem] = rows

    combined = combine(runs.values())
    candidates = dev_subset_candidates(runs.values())

    document = {
        "schema": PREANALYSIS_SCHEMA,
        "ceiling_definition": CEILING_DEFINITION,
        "autopsy_documents": [str(path) for path in namespace.autopsy],
        "runs": runs,
        "combined": combined,
        "dev_subset_candidates": list(candidates),
        "decisions": decisions,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for stem, analysis in runs.items():
        for candidate, block in sorted(analysis["per_candidate"].items()):
            print(
                f"{stem} {candidate}: retry-eligible={block['retry_eligible']}, "
                f"inferred-truncation={block['inferred_truncation']}, ceiling={block['ceiling']}"
            )
    print(
        f"combined: retry-eligible={combined['totals']['retry_eligible']}, "
        f"inferred-truncation={combined['totals']['inferred_truncation']}, "
        f"ceiling={combined['totals']['ceiling']}"
    )
    print(f"dev-subset candidates: {', '.join(candidates)}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CEILING_DEFINITION",
    "NON_TRIGGER_REMAINDER_KEYS",
    "PREANALYSIS_SCHEMA",
    "OutNotPrivate",
    "analyze_document",
    "combine",
    "dev_subset_candidates",
    "is_inferred_truncation",
    "main",
    "refuse_published_out",
    "trigger_of_cause",
]
