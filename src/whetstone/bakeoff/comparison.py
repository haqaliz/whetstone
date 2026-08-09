"""The before/after breakdown: stored runs' journals and autopsies against the pre-analysis.

The measured arm's post-run chain (`docs/planning/format-hardening-measurement/prd.md` D3, D4,
D6) is the deterministic read that turns the stored runs' journals, the stored
`whetstone-autopsy/1` documents, and the `whetstone-preanalysis/1` ceiling document into the
`whetstone-comparison/1` before/after breakdown: per run, per candidate, the cause counts from
the autopsy analysis, the rollout tallies from the journal (`report.tally` by identity — the
single place each published figure is defined), the summed generation seconds, and both
denominators side by side.

**The determinism contract (D-arm3).** The arm is operator-executed; everything after it is
this module — deterministic, offline, stdlib-only. The same inputs write byte-identical bytes
(`json.dumps(indent=2, sort_keys=True) + "\\n"`), and the module imports no model and no
`run.py` (its own no-inference AST walk in `tests/bakeoff/test_comparison.py` refuses all of
them).

**The mapping is asserted, never reconciled (D4).** The pre-analysis document's `decisions`
rows record the trigger the mapping fired for every stored record when the ceiling was
measured. This module re-derives `diffcheck.trigger_of_cause` and
`preanalysis.is_inferred_truncation` from the autopsy documents' own records — by identity,
never reimplemented — and asserts agreement per record, in index order. A contradiction is a
named violation in the document and the CLI exits nonzero; nonzero `mapping_violations` in an
input autopsy document are surfaced the same way. Nothing is reconciled (`autopsy.py:644-667`).
A decisions list whose length disagrees with the autopsy records is refused: the pre-analysis
CLI writes exactly one decisions row per record in order (`preanalysis.py:510-525`), so a
different length means the two documents were not written over the same record set.

**The denominators are disclosed, never fused (D6).** A run's journal step count and its
autopsy classified-completion count measure different things about the same run; the document
reports both side by side, and the tallies are counted over the journal's rollouts alone. The
ceiling is carried from the pre-analysis document's own `combined.totals.ceiling`, never
recomputed.

**The run keys.** A run is keyed by its autopsy document's path stem (`arm-a` for
`…/arm-a.json`, the pre-analysis precedent) and matched to a journal by the journal's parent
directory's name (`arm-a` for `…/arm-a/journal.jsonl`) — the stored corpus names its journals
that way, and `path.stem` would be `journal` for both. A duplicate key is refused by name,
never fused. The before/after names `arm-a` as the `before` run (`BEFORE_RUN`); each run's
cause counts are rendered per candidate side by side with the delta against it, never pooled
(`autopsy.py:676-677`).

Exit codes: 0 — the document was written clean; 1 — the document was written carrying
assertion violations; 2 — an invocation mistake (locality, missing input, stem collision,
unparseable document, unproven control), nothing written.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TypedDict

from whetstone.bakeoff import preanalysis
from whetstone.bakeoff.autopsy import AUTOPSY_SCHEMA, FineCause
from whetstone.bakeoff.control import Control
from whetstone.bakeoff.diffcheck import trigger_of_cause
from whetstone.bakeoff.journal import Journal, JournalUnreadable, Key, Step
from whetstone.bakeoff.preanalysis import (
    PREANALYSIS_SCHEMA,
    OutNotPrivate,
    analyze_document,
    is_inferred_truncation,
    refuse_published_out,
)
from whetstone.bakeoff.report import tally
from whetstone.bakeoff.scoring import Rollout

#: The document this module writes.
COMPARISON_SCHEMA = "whetstone-comparison/1"

#: The run the before/after deltas are computed against: the stored arm-a, the run the
#: ceiling was measured over first (`runs/diff-autopsy/arm-a.json`). Named here, documented,
#: and carried into every document's `before_after.before`.
BEFORE_RUN = "arm-a"

#: The D6 denominator disclosure, written into every document: the journal's step count and
#: the autopsy's classified-completion count are different measurements of the same run and
#: are never fused into one denominator.
DENOMINATOR_DISCLOSURE = (
    "rollout_records counts the journal's steps; autopsy_records counts the autopsy "
    "document's classified completions. They are different measurements of the same run, "
    "reported side by side and never fused into one denominator."
)


class _UsageError(ValueError):
    """An invocation mistake the CLI reports as exit 2: nothing is written."""


@dataclass(frozen=True)
class _Record:
    """One stored autopsy record, as the assertion re-derives the mapping from it.

    Only the two fields the mapping needs survive the read — `cause` and `detail` — plus the
    two the violation rows name, `candidate` and `task_id`. The read is strict: a row that
    cannot be keyed is refused by name, never matched by a guess.
    """

    candidate: str
    task_id: str
    cause: FineCause
    detail: str


@dataclass(frozen=True)
class _AutopsyDocument:
    """The comparison's own read of one `whetstone-autopsy/1` document.

    `preanalysis.analyze_document` provides the counts (by identity); this is the read the
    assertion re-derives from — the whole point is that the assertion does not trust the
    pre-analysis's parse of the same bytes, or it would verify the pre-analysis against
    itself. The autopsy's own fine→coarse `mapping_violations` rows travel with it and are
    surfaced as violations.
    """

    records: tuple[_Record, ...]
    mapping_violations: tuple[dict[str, object], ...]


class _Preanalysis(TypedDict):
    """The pre-analysis document, strictly parsed: the ceiling and the per-record decisions."""

    ceiling: int
    decisions: dict[str, list[dict[str, object]]]


class _Document(TypedDict):
    schema: str
    preanalysis_document: str
    ceiling: int
    runs: dict[str, dict[str, object]]
    before_after: dict[str, object]
    assertion: dict[str, object]
    violations: list[dict[str, object]]
    disclosures: dict[str, object]


def _journal_key(path: Path) -> str:
    """The run key a journal is filed under: its parent directory's name.

    The stored corpus names its journals `runs/{arm-a,budget-2048}/journal.jsonl`, so the
    key that matches the autopsy document's stem (`arm-a`, `budget-2048`) is the parent
    directory's name — `path.stem` would be `journal` for both.
    """
    return path.parent.name


def _read_autopsy(path: Path) -> _AutopsyDocument:
    """The comparison's own strict read of one `whetstone-autopsy/1` document.

    Strict about everything the assertion needs: the schema (imported by identity), a
    `records` list, rows keyable as (candidate, task_id, cause, detail) with a `cause` the
    taxonomy actually has a member for, and a `mapping_violations` list. A row that cannot be
    keyed is refused by name rather than matched by a guess.
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
            "nothing for the trigger mapping to assert over"
        )
    raw_violations = raw.get("mapping_violations", [])
    if not isinstance(raw_violations, list):
        raise _UsageError(
            f"the autopsy document at {str(path)!r} carries a non-list 'mapping_violations'"
        )
    violations: list[dict[str, object]] = []
    for one in raw_violations:
        if not isinstance(one, dict):
            raise _UsageError(
                f"the autopsy document at {str(path)!r} carries a mapping violation that is "
                "not an object"
            )
        violations.append(one)

    records: list[_Record] = []
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
        records.append(_Record(candidate, task_id, cause, detail))
    return _AutopsyDocument(tuple(records), tuple(violations))


def _parse_preanalysis(path: Path) -> _Preanalysis:
    """The pre-analysis document, parsed strictly: schema, totals, and decisions.

    The document must declare the pre-analysis's own schema (`PREANALYSIS_SCHEMA`, imported
    by identity), carry `combined.totals` — where the ceiling lives — with an integer
    `ceiling`, and carry a `decisions` object of per-run row lists. A document that does not
    is refused by name: the assertion cannot trust decisions a document does not declare.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise _UsageError(
            f"the pre-analysis document at {str(path)!r} could not be read as JSON "
            f"({type(exc).__name__}: {exc})"
        ) from exc
    except OSError as exc:
        raise _UsageError(
            f"the pre-analysis document at {str(path)!r} could not be read: {exc}"
        ) from exc
    if not isinstance(raw, dict) or raw.get("schema") != PREANALYSIS_SCHEMA:
        raise _UsageError(
            f"the pre-analysis document at {str(path)!r} does not declare schema "
            f"{PREANALYSIS_SCHEMA!r}, so its decisions cannot be trusted as the trigger rows "
            "the ceiling was measured under"
        )
    combined = raw.get("combined")
    if not isinstance(combined, dict):
        raise _UsageError(
            f"the pre-analysis document at {str(path)!r} carries no 'combined' object"
        )
    totals = combined.get("totals")
    if not isinstance(totals, dict):
        raise _UsageError(
            f"the pre-analysis document at {str(path)!r} carries no 'combined.totals' object "
            "— the ceiling lives there"
        )
    ceiling = totals.get("ceiling")
    if not isinstance(ceiling, int):
        raise _UsageError(
            f"the pre-analysis document at {str(path)!r} carries a non-integer "
            "'combined.totals.ceiling'"
        )
    decisions = raw.get("decisions")
    if not isinstance(decisions, dict):
        raise _UsageError(
            f"the pre-analysis document at {str(path)!r} carries no 'decisions' object"
        )
    parsed: dict[str, list[dict[str, object]]] = {}
    for stem, rows in decisions.items():
        if not isinstance(rows, list):
            raise _UsageError(
                f"the pre-analysis document at {str(path)!r} carries non-list decisions for "
                f"run {stem!r}"
            )
        row_objects: list[dict[str, object]] = []
        for number, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise _UsageError(
                    f"decisions row {number} of run {stem!r} in {str(path)!r} is not an object"
                )
            row_objects.append(row)
        parsed[stem] = row_objects
    return _Preanalysis(ceiling=ceiling, decisions=parsed)


def assert_trigger_mapping(
    stem: str,
    records: Sequence[_Record],
    decision_rows: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    """Re-derive the mapping over `records` and assert agreement with `decision_rows`.

    The assertion contract (D4): the comparison re-derives `diffcheck.trigger_of_cause` and
    `preanalysis.is_inferred_truncation` — imported by identity — for every autopsy record,
    in index order, and compares against the pre-analysis document's decisions rows, which
    the pre-analysis CLI wrote one per record in the same order (`preanalysis.py:510-525`).
    A disagreement on the trigger value or on `inferred_truncation` is a named violation,
    never reconciled. The decision's `inferred_truncation` semantics are the pre-analysis's
    own (`preanalysis.py:520-522`): only a record whose trigger fired can be truncation-
    inferred. A length disagreement between records and decisions is refused: the two
    documents were not written over the same record set, so nothing between them may be
    compared.
    """
    if len(records) != len(decision_rows):
        raise _UsageError(
            f"the pre-analysis document's decisions for run {stem!r} carry "
            f"{len(decision_rows)} rows, but the autopsy document for {stem!r} carries "
            f"{len(records)} records. The pre-analysis CLI writes exactly one decisions row "
            "per autopsy record in order, so a different length means the two documents were "
            "not written over the same record set — nothing between them may be compared"
        )

    violations: list[dict[str, object]] = []
    for index, (record, row) in enumerate(zip(records, decision_rows, strict=True)):
        trigger = trigger_of_cause(record.cause, record.detail)
        expected_trigger = None if trigger is None else trigger.value
        try:
            actual_trigger = row["trigger"]
            actual_inferred = row["inferred_truncation"]
        except KeyError as exc:
            raise _UsageError(
                f"decisions row {index} of run {stem!r} is missing {exc.args[0]!r}, so the "
                "pre-analysis document's decision for that record cannot be compared"
            ) from exc
        expected_inferred = trigger is not None and is_inferred_truncation(record.detail)
        if actual_trigger != expected_trigger or actual_inferred != expected_inferred:
            violations.append(
                {
                    "kind": "trigger-mismatch",
                    "stem": stem,
                    "index": index,
                    "candidate": record.candidate,
                    "task_id": record.task_id,
                    "cause": record.cause.value,
                    "detail": record.detail,
                    "expected_trigger": expected_trigger,
                    "actual_trigger": actual_trigger,
                    "expected_inferred_truncation": expected_inferred,
                    "actual_inferred_truncation": actual_inferred,
                }
            )
    return tuple(violations)


def _per_candidate_blocks(
    steps: Mapping[Key, Step], analysis: preanalysis._RunAnalysis
) -> dict[str, dict[str, object]]:
    """One run's per-candidate blocks: autopsy cause counts, journal tally, generation seconds.

    The candidates are the union of the two measurements' candidates — a candidate the
    autopsy never saw has empty cause counts (absent causes absent, `autopsy.py:670-683`),
    and a candidate with no rollouts has an empty tally. The tallies come from
    `report.tally` by identity, counted over the journal's rollouts alone; the generation
    seconds are summed over the same rollouts.
    """
    rollouts_by_candidate: dict[str, list[Rollout]] = {}
    for key in sorted(steps):
        rollout = steps[key].rollout
        rollouts_by_candidate.setdefault(rollout.candidate, []).append(rollout)

    candidates = set(rollouts_by_candidate) | set(analysis["per_candidate"])
    blocks: dict[str, dict[str, object]] = {}
    for candidate in sorted(candidates):
        rollouts = rollouts_by_candidate.get(candidate, [])
        block = analysis["per_candidate"].get(candidate)
        blocks[candidate] = {
            "cause_counts": {} if block is None else block["cause_counts"],
            "tally": asdict(tally(candidate, rollouts)),
            "generation_seconds": sum(
                rollout.generation_seconds for rollout in rollouts
            ),
        }
    return blocks


def _before_after(
    analyses: Mapping[str, preanalysis._RunAnalysis],
) -> dict[str, object]:
    """The before/after block: per candidate, each run's cause counts and the deltas.

    Never pooled (`autopsy.py:676-677`): per candidate, per run, the cause counts sit side by
    side, and each run's delta is computed per cause against the named `BEFORE_RUN` — the
    before run's own delta is zero by construction. A candidate appears only in the runs
    whose autopsy analysis carries it. When the named before run is not among the inputs,
    `delta_vs_before` is empty and `before` still names what was asked for.
    """
    candidates = sorted(
        {
            candidate
            for analysis in analyses.values()
            for candidate in analysis["per_candidate"]
        }
    )
    per_candidate: dict[str, dict[str, object]] = {}
    for candidate in candidates:
        counts_per_stem = {
            stem: analysis["per_candidate"][candidate]["cause_counts"]
            for stem, analysis in analyses.items()
            if candidate in analysis["per_candidate"]
        }
        if BEFORE_RUN in counts_per_stem:
            before_counts = counts_per_stem[BEFORE_RUN]
            causes = sorted(
                {cause for counts in counts_per_stem.values() for cause in counts}
            )
            deltas = {
                stem: {
                    cause: counts.get(cause, 0) - before_counts.get(cause, 0)
                    for cause in causes
                }
                for stem, counts in counts_per_stem.items()
            }
        else:
            deltas = {}
        per_candidate[candidate] = {"runs": counts_per_stem, "delta_vs_before": deltas}
    return {"before": BEFORE_RUN, "per_candidate": per_candidate}


def build_document(
    journals: Sequence[Path],
    autopsies: Sequence[Path],
    preanalysis_path: Path,
) -> _Document:
    """Read everything and assemble the `whetstone-comparison/1` document.

    The refusals, in fixed order: a missing file (an arm that has not run must not read as
    zero rollouts); a duplicate run key (a collision is refused, never fused); a journal /
    autopsy stem mismatch (every run needs both halves); an unparseable document (journals
    via `JournalUnreadable`, autopsies via `preanalysis.analyze_document`'s errors and the
    comparison's own strict read, the pre-analysis via its strict parse); and a run whose
    journal carries no `INTACT` control probe (`control.py:492` — nothing from such a run
    may become a count). Each raises `_UsageError`, which the CLI reports as exit 2.

    The assertion's violations are not refusals: they land in the document and the caller
    decides the exit code.
    """
    for path in (*journals, *autopsies, preanalysis_path):
        if not path.is_file():
            raise _UsageError(
                f"{str(path)!r} is not a file. The breakdown is assembled from the runs' own "
                "journals, autopsy documents and the pre-analysis document — a missing one "
                "would read as a run nobody made, which is not the same as a measured zero"
            )

    journal_stems: dict[str, Path] = {}
    for path in journals:
        stem = _journal_key(path)
        if stem in journal_stems:
            raise _UsageError(
                f"the journals {str(journal_stems[stem])!r} and {str(path)!r} share the run "
                f"key {stem!r} (a journal is keyed by its parent directory's name) — that "
                "key is named twice, so the run is refused rather than fused with itself"
            )
        journal_stems[stem] = path

    autopsy_stems: dict[str, Path] = {}
    for path in autopsies:
        stem = path.stem
        if stem in autopsy_stems:
            raise _UsageError(
                f"the autopsy documents {str(autopsy_stems[stem])!r} and {str(path)!r} share "
                f"the path stem {stem!r}, which is the key the document names the run under "
                "— that key is named twice, so the run is refused rather than fused with "
                "itself"
            )
        autopsy_stems[stem] = path

    missing_autopsies = sorted(set(journal_stems) - set(autopsy_stems))
    missing_journals = sorted(set(autopsy_stems) - set(journal_stems))
    if missing_autopsies or missing_journals:
        raise _UsageError(
            "the journal and autopsy runs do not match: "
            + "; ".join(
                [f"journal {stem!r} has no autopsy document" for stem in missing_autopsies]
                + [f"autopsy {stem!r} has no journal" for stem in missing_journals]
            )
        )

    steps_by_stem: dict[str, dict[Key, Step]] = {}
    for stem, path in journal_stems.items():
        try:
            steps_by_stem[stem] = Journal(path).replay()
        except JournalUnreadable as exc:
            raise _UsageError(str(exc)) from exc

    analyses: dict[str, preanalysis._RunAnalysis] = {}
    autopsy_documents: dict[str, _AutopsyDocument] = {}
    for stem, path in autopsy_stems.items():
        try:
            analyses[stem] = analyze_document(path)
            autopsy_documents[stem] = _read_autopsy(path)
        except (preanalysis._UsageError, _UsageError) as exc:
            raise _UsageError(str(exc)) from exc

    pre = _parse_preanalysis(preanalysis_path)

    for stem in sorted(steps_by_stem):
        observed = sorted({step.probe.control.value for step in steps_by_stem[stem].values()})
        if not any(step.probe.control is Control.INTACT for step in steps_by_stem[stem].values()):
            raise _UsageError(
                f"the run {stem!r} carries no INTACT control probe — its journal's probes are "
                f"{observed} — so nothing measured in it is proven to be about the base "
                f"(`control.py:492`). A run whose harness was never shown intact yields no "
                "counts"
            )

    violations: list[dict[str, object]] = []
    assertions: dict[str, dict[str, int]] = {}
    for stem in autopsy_stems:
        records = autopsy_documents[stem].records
        decisions = pre["decisions"].get(stem)
        if decisions is None:
            raise _UsageError(
                f"the pre-analysis document at {str(preanalysis_path)!r} carries no decisions "
                f"for run {stem!r}, so the trigger mapping cannot be asserted for it"
            )
        mismatches = assert_trigger_mapping(stem, records, decisions)
        assertions[stem] = {"records_checked": len(records), "mismatches": len(mismatches)}
        violations.extend(mismatches)
        for one in autopsy_documents[stem].mapping_violations:
            violations.append(
                {
                    "kind": "autopsy-mapping-violation",
                    "stem": stem,
                    "candidate": one.get("candidate"),
                    "task_id": one.get("task_id"),
                    "fine_cause": one.get("fine_cause"),
                    "recorded_cause": one.get("recorded_cause"),
                }
            )

    runs: dict[str, dict[str, object]] = {}
    for stem, path in autopsy_stems.items():
        analysis = analyses[stem]
        runs[stem] = {
            "autopsy": str(path),
            "journal": str(journal_stems[stem]),
            "control_proven": True,
            "rollout_records": len(steps_by_stem[stem]),
            "autopsy_records": analysis["records"],
            "per_candidate": _per_candidate_blocks(steps_by_stem[stem], analysis),
        }

    return _Document(
        schema=COMPARISON_SCHEMA,
        preanalysis_document=str(preanalysis_path),
        ceiling=pre["ceiling"],
        runs=runs,
        before_after=_before_after(analyses),
        assertion={"stems": assertions},
        violations=violations,
        disclosures={"denominators": DENOMINATOR_DISCLOSURE},
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Read the journals, autopsy documents, and the pre-analysis document; write the breakdown.

    The door of the measured arm's Phase 3: `python -m whetstone.bakeoff.comparison
    --journal PATH [--journal ...] --autopsy PATH [--autopsy ...] --preanalysis PATH
    --out PATH`. `--out` is checked **before** anything is loaded — the refusal is
    `preanalysis.refuse_published_out` by identity — and every other refusal is exit 2 with
    the reason named. The assertion's violations do not refuse: the document is still written
    with them listed and the CLI exits 1 — reported, never reconciled. A clean run writes
    byte-identical output across invocations.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.bakeoff.comparison",
        description=(
            "Assemble the before/after breakdown over stored runs: journals, autopsy "
            "documents and the pre-analysis ceiling document, per run per candidate, with "
            "the trigger mapping asserted against the pre-analysis document's decisions. "
            "Offline: no model is loaded and no network is touched, and the document is "
            "written only under a documented gitignored root."
        ),
    )
    parser.add_argument(
        "--journal",
        action="append",
        required=True,
        type=Path,
        help="a run's journal file (repeatable; the run key is the parent directory's name)",
    )
    parser.add_argument(
        "--autopsy",
        action="append",
        required=True,
        type=Path,
        help="a stored whetstone-autopsy/1 document (repeatable)",
    )
    parser.add_argument(
        "--preanalysis",
        required=True,
        type=Path,
        help="the whetstone-preanalysis/1 ceiling document",
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="where the document is written"
    )
    namespace = parser.parse_args(argv)

    out = namespace.out
    try:
        refuse_published_out(out)
    except OutNotPrivate as exc:
        print(f"whetstone comparison: {exc}", file=sys.stderr)
        return 2

    try:
        document = build_document(namespace.journal, namespace.autopsy, namespace.preanalysis)
    except _UsageError as exc:
        print(f"whetstone comparison: {exc}", file=sys.stderr)
        return 2

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for stem in sorted(document["runs"]):
        block = document["runs"][stem]
        print(
            f"{stem}: rollouts={block['rollout_records']} "
            f"autopsy-records={block['autopsy_records']}"
        )
    violations = document["violations"]
    if violations:
        print(
            f"assertion: {len(violations)} violation(s) — the document carries them",
            file=sys.stderr,
        )
        for violation in violations:
            print(f"assertion: {violation}", file=sys.stderr)
    else:
        print("assertion: clean")
    print(f"\nwrote {out}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BEFORE_RUN",
    "COMPARISON_SCHEMA",
    "DENOMINATOR_DISCLOSURE",
    "assert_trigger_mapping",
    "build_document",
    "is_inferred_truncation",
    "main",
    "refuse_published_out",
    "trigger_of_cause",
]
