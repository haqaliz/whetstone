"""A finished night's failure partition, read off its own evidence and reconciled to its ledger.

A night's ledger records, per draw and per source, only `(denominator, unverified, solved)` and
the control arm's status. It records **no cause** for any rollout, and the per-rollout facts that
explain a zero — `outcome`, `strict`, `weak`, `verdict_kinds`, `detail`, `prompt_sha256` — live
only in the per-draw journals. `bakeoff.attribution` reads exactly one transcript and never a
night's journals or ledger; `bakeoff.autopsy` requires a `whetstone-attribution/1` sidecar no
night writes. So the question a zero forces — *why did this rollout become or not become a
training example* — is answered today by hand-joining transcripts to journals, which is how night
#1's patch-application failure was diagnosed and why the `NOT_APPLIED` reason field was added
only after the cost was paid. This module is that join as a command.

**It reads one complete night and explains it. It changes nothing and publishes no number about a
model.** The door is `python -m whetstone.bakeoff.night_autopsy`; it reads the ledger through
`ledger.read` (sealed v3), each declared draw's journal through `Journal.replay()` and its
transcript through `Transcript.replay()`, and emits a `whetstone-night-autopsy/1` document — the
night's failure partition, per draw and per task. No night is run, no model is loaded, and no
network is touched.

**Every reused fact is imported by identity, never re-spelled.** The coarse outcome vocabulary is
`scoring.Outcome`; the cause taxonomy is `attribution.Cause` with its `NO_DIFF_MARKERS`,
`attribute` and `extract_patch`; the fine patch shape is `autopsy.classify_completion`; the solved
predicate is `dataset.trainable`; the reconciliation definition is `ledger.counts_of`; the
evidence paths are `draws.evidence_paths` under `night.EVIDENCE_DIR`; the ledger document is
`ledger.LEDGER_FILE` through `ledger.read`; and the output-locality rule is
`autopsy.refuse_published_out`. A second definition of any of them would drift from the one the
run used, and the drift would be invisible while a confident partition described a night that
never happened.

**The reconciliation is by identity and is a refusal, never a smoother.** Per draw, the module
reconstructs the journal `Rollout`s and calls `run_ledger.counts_of` — the ledger's own
definition — requiring it to equal the sum across sources of the ledger's `DrawRecord.counts`;
globally the same must equal the ledger's `dataset` block, and the run's `dataset.json` is read and
reconciled when present. A disagreement is a named refusal naming the draw and both triples, exit
2, with no partial partition written: a missing measurement rendered as a measurement is how a
partial breakdown reads as a complete one.

**The causes come from the stored completion, in two layers.** For `NOT_APPLIED` and `NO_DIFF`,
`attribution.attribute` re-runs the run's own extractor against the stored text (the pure layer,
always) and, when `--tasks` names one or more corpus roots, against a **throwaway materialisation**
of the task's tree (the checkout layer, which answers *would not parse* vs *parsed and would not
apply*). With no `--tasks`, a located diff is `UNATTRIBUTED` **by name**, never guessed at, and the
document discloses why. A cause the taxonomy cannot name is `UNATTRIBUTED` too. `NO_ORACLE` and
`UNPROVISIONED` are recorded before generation, so they have a journal row and no transcript row;
they are counted in the partition, never treated as incompleteness.

**Nothing leaks.** The partition quotes stored completions, which carry the user's own private
code, so the document is written only under a documented gitignored root (`runs/`,
`reports/local/`, `checkpoints/`, `tasks/local/`, `_sandbox/`), enforced before anything is read.
Stdlib only; the document is unsealed (it is analysis, not a claim document) and byte-deterministic.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.bakeoff.attribution import (
    NO_DIFF_MARKERS,
    Cause,
    attribute,
    extract_patch,
)
from whetstone.bakeoff.autopsy import (
    IGNORED_OUT_ROOTS,
    OutNotPrivate,
    classify_completion,
    refuse_published_out,
)
from whetstone.bakeoff.journal import Journal, JournalUnreadable
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.bakeoff.transcript import Transcribed, Transcript, TranscriptUnreadable
from whetstone.loop import dataset as training
from whetstone.loop.dataset import trainable
from whetstone.loop.draws import evidence_paths
from whetstone.loop.ledger import LEDGER_FILE, LedgerUnreadable, counts_of
from whetstone.loop.ledger import read as ledger_read
from whetstone.loop.night import DATASET_FILE, EVIDENCE_DIR
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.repo import materialise
from whetstone.verify.verdict import Status

#: The document this module writes. Unsealed: it is analysis, not a claim document, and sealing is
#: for checkpoints, ledgers and datasets.
SCHEMA = "whetstone-night-autopsy/1"

#: The sentence a `LedgerUnreadable` is re-raised under, so a missing and an unreadable ledger are
#: one refusal naming the run rather than two shapes a caller has to tell apart.
_LEDGER_REFUSAL = (
    "a night's ledger is the completeness authority for its partition: without it there is no "
    "counts record to reconcile against, and a ledgerless run is refused rather than rendered as "
    "a partial partition"
)

#: The file a night's training set is written to, beside its ledger (`night.DATASET_FILE`). Read
#: by identity so a second spelling cannot disagree with the writer.
DATASET_FILE_NAME = DATASET_FILE

#: The schema-legal output roots, re-exported by identity from the autopsy's locality rule.
__all__ = [
    "DATASET_FILE_NAME",
    "EVIDENCE_DIR",
    "IGNORED_OUT_ROOTS",
    "LEDGER_FILE",
    "NO_DIFF_MARKERS",
    "SCHEMA",
    "Cause",
    "CountDisagreement",
    "DrawReconciliation",
    "DrawResult",
    "IncompleteRun",
    "NightAutopsy",
    "NotARun",
    "OutNotPrivate",
    "Outcome",
    "PublishedOut",
    "Row",
    "UnreadableEvidence",
    "attribute",
    "autopsy",
    "classify_completion",
    "counts_of",
    "document",
    "evidence_paths",
    "extract_patch",
    "ledger_read",
    "main",
    "refuse_published_out",
    "render_markdown",
    "trainable",
]


class NotARun(ValueError):
    """The run directory holds no readable ledger, so there is nothing to reconcile against."""


class IncompleteRun(ValueError):
    """A ledger-declared draw's journal or transcript is missing, or a task root cannot be read."""


class UnreadableEvidence(ValueError):
    """A journal, transcript or dataset line could not be read. Named, never skipped."""


class CountDisagreement(ValueError):
    """The partition does not reproduce the ledger's counts. Refused, never reconciled away."""


#: The refusal `refuse_published_out` raises, named for this module's own vocabulary. It is the
#: same object: the locality rule is reused by identity, not re-implemented.
PublishedOut = OutNotPrivate


def _triple_text(counts: tuple[int, int, int]) -> str:
    """`(denominator, unverified, solved)` as a sentence fragment an operator can read."""
    return f"(denominator={counts[0]}, unverified={counts[1]}, solved={counts[2]})"


@dataclass(frozen=True)
class Row:
    """One rollout, whole: the coarse outcome, its verdicts, and the cause the replay measured.

    `cause` is `None` for every outcome other than `NOT_APPLIED` and `NO_DIFF` — the two the
    attribution taxonomy explains — and the member itself otherwise, including `UNATTRIBUTED`
    when the question could not be asked. `shape` is the fine patch shape
    `autopsy.classify_completion` read off the stored completion, or `None` when no completion
    was ever generated.
    """

    attempt: int
    candidate: str
    task_id: str
    outcome: Outcome
    strict: Status | None
    weak: Status | None
    verdict_kinds: tuple[str, ...]
    detail: str
    trainable: bool
    cause: Cause | None
    cause_detail: str
    shape: str | None


@dataclass(frozen=True)
class DrawResult:
    """One draw's partition: the harness the ledger recorded and the rows the journal holds."""

    attempt: int
    harness: Mapping[str, str]
    counts: Mapping[str, Mapping[str, int]]
    rows: tuple[Row, ...]


@dataclass(frozen=True)
class DrawReconciliation:
    """One draw's check: what the journal's rollouts total, and what the ledger recorded."""

    attempt: int
    recomputed: tuple[int, int, int]
    recorded: tuple[int, int, int]


@dataclass(frozen=True)
class NightAutopsy:
    """A finished night, explained: the partition, the reconciliation and the disclosures."""

    run_id: str
    run: str
    draws: int
    per_draw: tuple[DrawResult, ...]
    outcomes: Mapping[Outcome, int]
    causes: Mapping[Cause, int]
    unattributed: int
    reconciliations: tuple[DrawReconciliation, ...]
    global_recomputed: tuple[int, int, int]
    global_recorded: tuple[int, int, int]
    dataset_recorded: tuple[int, int, int] | None
    disclosures: tuple[str, ...]


def _sum_sources(counts: Mapping[str, Mapping[str, int]]) -> tuple[int, int, int]:
    """The ledger's per-source counts, summed into the one triple `counts_of` produces.

    Summed because `source` is not recorded per rollout on disk: the journal `Step` and the
    transcript record are both keyed `(candidate, task_id)` and neither carries private/public, so
    the reconciliation is over totals and the document discloses the limit.
    """
    return (
        sum(int(one["denominator"]) for one in counts.values()),
        sum(int(one["unverified"]) for one in counts.values()),
        sum(int(one["solved"]) for one in counts.values()),
    )


def _checkouts(task_roots: Sequence[Path], scratch: Path) -> dict[str, Path]:
    """A throwaway checkout per task, from the `--tasks` roots, or an empty mapping.

    A task whose donor cannot be read is left without a checkout, which `attribute` records as
    `UNATTRIBUTED` by name rather than guessing a cause: a tree that could not be materialised is
    a measurement that could not be taken, and the two are different claims. The caller's own
    trees are never opened for writing — `attribution.attribute` applies into a copy.
    """
    checkouts: dict[str, Path] = {}
    for root in task_roots:
        try:
            tasks = load_tasks(root)
        except (OSError, ValueError) as exc:
            raise IncompleteRun(
                f"the task root at {str(root)!r} could not be loaded ({exc}), so the checkout "
                "layer cannot be asked and a located diff could not be told from one git would "
                "parse and refuse"
            ) from exc
        for task in tasks:
            destination = scratch / task.task_id
            try:
                materialise(task, destination)
            # A donor that cannot be read leaves the task without a checkout, which `attribute`
            # records as UNATTRIBUTED by name rather than guessing a cause.
            except (OSError, RuntimeError, ValueError):
                continue
            checkouts[task.task_id] = destination
    return checkouts


def _row(
    attempt: int,
    rollout: Rollout,
    transcribed: Mapping[tuple[str, str], Transcribed],
    checkouts: Mapping[str, Path],
) -> Row:
    """One rollout with its coarse cause and its fine shape, or `UNATTRIBUTED` when unaskable.

    The completion is looked up by `(candidate, task_id)` — the transcript's own key — and only
    for the two outcomes the taxonomy explains. A missing completion for such a rollout is
    `UNATTRIBUTED` by name, never a cause invented from the ledger's `detail`.
    """
    record = transcribed.get((rollout.candidate, rollout.task_id))
    shape = None if record is None else classify_completion(record.completion).cause.value

    cause: Cause | None = None
    cause_detail = ""
    if rollout.outcome in (Outcome.NOT_APPLIED, Outcome.NO_DIFF):
        if record is None:
            cause = Cause.UNATTRIBUTED
            cause_detail = (
                "no stored completion was found for this rollout, so the extractor could not be "
                "re-run and the cause is left unattributed rather than guessed"
            )
        else:
            attributed = attribute(record, checkouts.get(rollout.task_id))
            cause = attributed.cause
            cause_detail = attributed.detail

    return Row(
        attempt=attempt,
        candidate=rollout.candidate,
        task_id=rollout.task_id,
        outcome=rollout.outcome,
        strict=rollout.strict,
        weak=rollout.weak,
        verdict_kinds=rollout.verdict_kinds,
        detail=rollout.detail,
        trainable=trainable(rollout),
        cause=cause,
        cause_detail=cause_detail,
        shape=shape,
    )


def _disclosures(task_roots: Sequence[Path]) -> tuple[str, ...]:
    """What the partition cannot say, stated rather than left to be inferred."""
    stated = [
        "source (private/public) is not recorded on disk per rollout — neither the journal Step "
        "nor the transcript record carries it — so the partition is keyed by draw and task, and "
        "the ledger's per-source counts remain the source-level truth",
    ]
    if task_roots:
        stated.append(
            "the checkout layer was asked against a throwaway materialisation of each task from "
            "--tasks; the caller's own trees were never written to"
        )
    else:
        stated.append(
            "no --tasks root was given, so the checkout layer could not be asked: a located diff "
            "is reported UNATTRIBUTED by name, never guessed at, because whether git would parse "
            "or apply it cannot be told from the stored text alone"
        )
    return tuple(stated)


def autopsy(run: Path, *, task_roots: Sequence[Path] = ()) -> NightAutopsy:
    """Read one complete night and return its reconciled failure partition.

    Raises `NotARun`, `IncompleteRun`, `UnreadableEvidence` or `CountDisagreement` — each exit 2
    at the door — and renders no partial partition for any of them. `--tasks` is optional and its
    absence is disclosed, never silent.
    """
    run = Path(run)
    ledger_path = run / LEDGER_FILE
    if not ledger_path.is_file():
        raise NotARun(
            f"{str(run)!r} holds no {LEDGER_FILE!r}. {_LEDGER_REFUSAL}"
        )
    try:
        ledger = ledger_read(ledger_path)
    except LedgerUnreadable as exc:
        raise NotARun(
            f"the ledger at {str(ledger_path)!r} could not be read ({exc}). {_LEDGER_REFUSAL}"
        ) from exc

    dataset_recorded: tuple[int, int, int] | None = None
    with tempfile.TemporaryDirectory(prefix="whetstone-night-autopsy-") as scratch:
        checkouts = _checkouts(task_roots, Path(scratch))

        per_draw: list[DrawResult] = []
        reconciliations: list[DrawReconciliation] = []
        rows: list[Row] = []
        global_recomputed = (0, 0, 0)

        for record in ledger["draws_recorded"]:
            attempt = int(record["attempt"])
            harness = {str(source): str(status) for source, status in record["harness"].items()}
            counts: Mapping[str, Mapping[str, int]] = record["counts"]
            recorded = _sum_sources(counts)

            journal_path, transcript_path = evidence_paths(run / EVIDENCE_DIR, attempt)
            if not journal_path.is_file():
                raise IncompleteRun(
                    f"draw {attempt} was declared by the ledger but its journal "
                    f"{str(journal_path)!r} is not a file. A declared draw without its journal is "
                    "missing evidence, refused rather than rendered as an empty draw"
                )
            if not transcript_path.is_file():
                raise IncompleteRun(
                    f"draw {attempt} was declared by the ledger but its transcript "
                    f"{str(transcript_path)!r} is not a file. An empty transcript is valid — a "
                    "draw whose tasks all failed before generation — but an absent one is missing "
                    "evidence, refused rather than rendered as a clean draw"
                )

            try:
                steps = Journal(journal_path).replay()
            except JournalUnreadable as exc:
                raise UnreadableEvidence(
                    f"draw {attempt}: the journal at {str(journal_path)!r} could not be replayed "
                    f"({exc})"
                ) from exc
            try:
                transcribed = Transcript(transcript_path).replay()
            except TranscriptUnreadable as exc:
                raise UnreadableEvidence(
                    f"draw {attempt}: the transcript at {str(transcript_path)!r} could not be "
                    f"replayed ({exc})"
                ) from exc

            ordered = [steps[key] for key in sorted(steps)]
            draw_rollouts = [step.rollout for step in ordered]
            recomputed = counts_of(draw_rollouts)
            if recomputed != recorded:
                raise CountDisagreement(
                    f"draw {attempt}: the journal's rollouts total {_triple_text(recomputed)} but "
                    f"the ledger's DrawRecord records {_triple_text(recorded)} for the same draw "
                    "(summed across sources). The journal is the per-rollout record and the ledger "
                    "is the completeness authority; the partition is refused, not reconciled, "
                    "because a partition that does not reproduce the ledger describes a night that "
                    "did not run"
                )

            draw = DrawResult(
                attempt=attempt,
                harness=harness,
                counts=counts,
                rows=tuple(
                    _row(attempt, step.rollout, transcribed, checkouts) for step in ordered
                ),
            )
            per_draw.append(draw)
            rows.extend(draw.rows)
            reconciliations.append(
                DrawReconciliation(attempt=attempt, recomputed=recomputed, recorded=recorded)
            )
            global_recomputed = (
                global_recomputed[0] + recomputed[0],
                global_recomputed[1] + recomputed[1],
                global_recomputed[2] + recomputed[2],
            )

        dataset_block = ledger["dataset"]
        global_recorded = (
            int(dataset_block["denominator"]),
            int(dataset_block["unverified"]),
            int(dataset_block["examples"]),
        )
        if global_recomputed != global_recorded:
            raise CountDisagreement(
                f"the whole run's rollouts total {_triple_text(global_recomputed)} but the "
                f"ledger's dataset block records {_triple_text(global_recorded)} "
                "(denominator, unverified, examples). Refused rather than reconciled"
            )

        dataset_path = run / DATASET_FILE_NAME
        if dataset_path.is_file():
            dataset_recorded = _reconcile_dataset(dataset_path, global_recomputed, rows)

    outcomes: dict[Outcome, int] = {}
    for row in rows:
        outcomes[row.outcome] = outcomes.get(row.outcome, 0) + 1
    causes: dict[Cause, int] = {}
    for row in rows:
        if row.cause is not None:
            causes[row.cause] = causes.get(row.cause, 0) + 1
    unattributed = sum(1 for row in rows if row.cause is Cause.UNATTRIBUTED)

    return NightAutopsy(
        run_id=str(ledger["run_id"]),
        run=str(run),
        draws=len(per_draw),
        per_draw=tuple(per_draw),
        outcomes=outcomes,
        causes=causes,
        unattributed=unattributed,
        reconciliations=tuple(reconciliations),
        global_recomputed=global_recomputed,
        global_recorded=global_recorded,
        dataset_recorded=dataset_recorded,
        disclosures=_disclosures(task_roots),
    )


def _as_int(value: object, *, field: str, path: Path) -> int:
    """A field the dataset document claims is a count, or a refusal naming it.

    `read_document` returns plain JSON types (`Mapping[str, object]`), so the cast is narrowed here
    rather than trusted: a document whose `denominator` is a string is a document this module
    cannot reconcile, and the honest answer is to say so.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise UnreadableEvidence(
            f"the run's {DATASET_FILE_NAME!r} at {str(path)!r} names {field!r} as {value!r}, which "
            "is not a count, so its training set cannot be reconciled against the partition"
        )
    return value


def _reconcile_dataset(
    path: Path,
    global_recomputed: tuple[int, int, int],
    rows: Sequence[Row],
) -> tuple[int, int, int]:
    """Read the run's `dataset.json` and require it to match the partition, or refuse.

    Read through `dataset.read_document` by identity so the sealed document's claims are verified
    before its fields are trusted. The selected `examples` must equal the partition's `trainable`
    count, and the document's `denominator`/`unverified` must equal the global `counts_of` totals.
    A document that disagrees is `CountDisagreement`, not a nicer number.
    """
    try:
        recorded = training.read_document(path)
    except (OSError, ValueError) as exc:
        raise UnreadableEvidence(
            f"the run's {DATASET_FILE_NAME!r} at {str(path)!r} could not be read ({exc})"
        ) from exc
    examples = recorded["examples"]
    if not isinstance(examples, list):
        raise UnreadableEvidence(
            f"the run's {DATASET_FILE_NAME!r} at {str(path)!r} carries no 'examples' list, so its "
            "training set cannot be reconciled against the partition"
        )
    dataset_recorded = (
        _as_int(recorded["denominator"], field="denominator", path=path),
        _as_int(recorded["unverified"], field="unverified", path=path),
        len(examples),
    )
    trainable_count = sum(1 for row in rows if row.trainable)
    if dataset_recorded[0] != global_recomputed[0] or dataset_recorded[1] != global_recomputed[1]:
        raise CountDisagreement(
            f"the run's {DATASET_FILE_NAME!r} records "
            f"(denominator={dataset_recorded[0]}, unverified={dataset_recorded[1]}) but the "
            f"journal's rollouts total {_triple_text(global_recomputed)}. Refused rather than "
            "reconciled"
        )
    if dataset_recorded[2] != trainable_count:
        raise CountDisagreement(
            f"the run's {DATASET_FILE_NAME!r} holds {dataset_recorded[2]} example(s) but the "
            f"partition's trainable count is {trainable_count}. A selected example must be a "
            "verified win and nothing else, so a disagreement is refused rather than reconciled"
        )
    return dataset_recorded


def _counts_document(counts: Mapping[str, Mapping[str, int]]) -> dict[str, dict[str, int]]:
    """The ledger's own per-source counts, as plain JSON types, in sorted source order."""
    return {
        source: {
            "denominator": int(one["denominator"]),
            "unverified": int(one["unverified"]),
            "solved": int(one["solved"]),
        }
        for source, one in sorted(counts.items())
    }


def _triple_document(counts: tuple[int, int, int]) -> dict[str, int]:
    """One `(denominator, unverified, solved)` triple, as plain JSON types."""
    return {"denominator": counts[0], "unverified": counts[1], "solved": counts[2]}


def document(night: NightAutopsy) -> dict[str, Any]:
    """The `whetstone-night-autopsy/1` document, as plain JSON types.

    Deterministic by construction: every mapping is built in sorted order, so the same night
    serialises to the same bytes whatever the interpreter's hash seed.
    """
    return {
        "schema": SCHEMA,
        "run_id": night.run_id,
        "run": night.run,
        "draws": night.draws,
        "rollouts": sum(night.outcomes.values()),
        "outcomes": {
            outcome.value: count
            for outcome, count in sorted(night.outcomes.items(), key=lambda one: one[0].value)
        },
        "causes": {
            cause.value: count
            for cause, count in sorted(night.causes.items(), key=lambda one: one[0].value)
        },
        "unattributed": night.unattributed,
        "per_draw": [
            {
                "attempt": draw.attempt,
                "harness": {source: status for source, status in sorted(draw.harness.items())},
                "counts": _counts_document(draw.counts),
                "tasks": [
                    {
                        "task_id": row.task_id,
                        "candidate": row.candidate,
                        "outcome": row.outcome.value,
                        "strict": None if row.strict is None else row.strict.value,
                        "weak": None if row.weak is None else row.weak.value,
                        "verdict_kinds": list(row.verdict_kinds),
                        "detail": row.detail,
                        "trainable": row.trainable,
                        "cause": None if row.cause is None else row.cause.value,
                        "cause_detail": row.cause_detail,
                        "shape": row.shape,
                    }
                    for row in draw.rows
                ],
            }
            for draw in night.per_draw
        ],
        "reconciliation": {
            "draws": [
                {
                    "attempt": check.attempt,
                    "recomputed": _triple_document(check.recomputed),
                    "recorded": _triple_document(check.recorded),
                }
                for check in night.reconciliations
            ],
            "global": {
                "recomputed": _triple_document(night.global_recomputed),
                "recorded": _triple_document(night.global_recorded),
            },
            "dataset": (
                None
                if night.dataset_recorded is None
                else {
                    "denominator": night.dataset_recorded[0],
                    "unverified": night.dataset_recorded[1],
                    "examples": night.dataset_recorded[2],
                }
            ),
        },
        "disclosures": list(night.disclosures),
    }


#: The outcome classes the per-draw table renders, in the order the aspect spec fixes. Every
#: member is present even when its count is zero: a class dropped because it came out zero is a
#: failure mode the operator cannot see, and the point of the partition is to make the zero legible.
_RENDERED_OUTCOMES = (
    Outcome.SOLVED,
    Outcome.NOT_APPLIED,
    Outcome.NOT_SOLVED,
    Outcome.NO_DIFF,
    Outcome.NO_ORACLE,
    Outcome.UNVERIFIED,
    Outcome.UNPROVISIONED,
    Outcome.OUT_OF_SCOPE,
)


def _count_field(document: Mapping[str, object], field: str) -> int:
    """A count the document must carry, or a refusal naming the field the render needs."""
    value = document.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            f"the document carries no integer {field!r}, so the page cannot state it"
        )
    return value


def _dominant_cause(counts: Mapping[str, int]) -> str:
    """The most frequent named cause, ties broken by name, or `-` when the taxonomy named none.

    Only `NOT_APPLIED` and `NO_DIFF` rows carry a cause; for the rest the question was never
    asked, and the honest answer is `-`, never the most common outcome wearing a cause's name.
    """
    if not counts:
        return "-"
    return sorted(counts.items(), key=lambda one: (-one[1], one[0]))[0][0]


def render_markdown(document: Mapping[str, object]) -> str:
    """The partition as a page the operator reads at the morning — a pure function of the document.

    Deterministic, stdlib-only string building: the same document always renders the same string,
    with no templates, no format placeholders, no clock and no file reads. Every number is the
    document's own — the per-draw counts and the per-task rows are read straight off `per_draw`,
    the task count is the number of distinct tasks the partition carries, and no proportion is
    computed that the document does not hold. Every unflattering state renders as itself: all
    eight classes are columns, zero-filled where a draw recorded none, and the two limits the
    document discloses — that `source` is not per-rollout, and what the taxonomy could not name —
    are stated verbatim. A tie in the worst-first order is broken by task id, so the page is the
    same on every machine. A document that does not carry the shape the builder writes is refused
    by name.
    """
    schema = document.get("schema")
    if not isinstance(schema, str):
        raise ValueError("the document carries no 'schema' string, so the render cannot name it")
    run_id = document.get("run_id")
    if not isinstance(run_id, str):
        raise ValueError("the document carries no 'run_id' string, so the page cannot name the run")
    draws = _count_field(document, "draws")
    rollouts = _count_field(document, "rollouts")
    unattributed = _count_field(document, "unattributed")
    per_draw_raw = document.get("per_draw")
    if not isinstance(per_draw_raw, list):
        raise ValueError("the document carries no 'per_draw' list, so no partition can be rendered")
    disclosures_raw = document.get("disclosures")
    if not isinstance(disclosures_raw, list):
        raise ValueError(
            "the document carries no 'disclosures' list, so its limits cannot be stated"
        )

    #: One parsed draw: its attempt, its control-arm cell, its per-class counts, and its rows.
    parsed: list[tuple[int, str, dict[str, int], list[tuple[str, str, str | None]]]] = []
    for draw in per_draw_raw:
        if not isinstance(draw, Mapping):
            raise ValueError("the document's 'per_draw' carries a draw that is not an object")
        attempt = draw.get("attempt")
        if not isinstance(attempt, int) or isinstance(attempt, bool):
            raise ValueError(
                "a draw in the document's 'per_draw' carries no integer 'attempt', so its row "
                "cannot be placed"
            )
        harness_raw = draw.get("harness")
        control = (
            ", ".join(f"{source}={status}" for source, status in sorted(harness_raw.items()))
            if isinstance(harness_raw, Mapping)
            else ""
        )
        tasks_raw = draw.get("tasks")
        if not isinstance(tasks_raw, list):
            raise ValueError(
                "a draw in the document's 'per_draw' carries no 'tasks' list, so its partition "
                "cannot be rendered"
            )
        counts = {outcome.value: 0 for outcome in _RENDERED_OUTCOMES}
        rows: list[tuple[str, str, str | None]] = []
        for row in tasks_raw:
            if not isinstance(row, Mapping):
                raise ValueError("a draw's 'tasks' carries a task that is not an object")
            task_id = row.get("task_id")
            outcome = row.get("outcome")
            cause = row.get("cause")
            if not isinstance(task_id, str) or not isinstance(outcome, str):
                raise ValueError(
                    "a task row carries no string 'task_id' or 'outcome', so it cannot be placed"
                )
            if cause is not None and not isinstance(cause, str):
                raise ValueError("a task row's 'cause' is neither a string nor null")
            if outcome in counts:
                counts[outcome] += 1
            rows.append((task_id, outcome, cause))
        parsed.append((attempt, control, counts, rows))

    # The per-task table aggregates across draws: draws the task appears in, its solved count, and
    # the causes its rows carry. Sorted worst-first (most non-solved rows), ties by task id.
    task_draws: dict[str, set[int]] = {}
    task_solved: dict[str, int] = {}
    task_non_solved: dict[str, int] = {}
    task_causes: dict[str, dict[str, int]] = {}
    for attempt, _control, _counts, rows in parsed:
        for task_id, outcome, cause in rows:
            task_draws.setdefault(task_id, set()).add(attempt)
            task_solved.setdefault(task_id, 0)
            task_non_solved.setdefault(task_id, 0)
            task_causes.setdefault(task_id, {})
            if outcome == Outcome.SOLVED.value:
                task_solved[task_id] += 1
            else:
                task_non_solved[task_id] += 1
            if cause is not None:
                task_causes[task_id][cause] = task_causes[task_id].get(cause, 0) + 1
    ordered_tasks = sorted(task_draws, key=lambda task_id: (-task_non_solved[task_id], task_id))

    lines: list[str] = [
        f"# Night autopsy ({schema})",
        "",
        f"- Run: {run_id}",
        f"- Draws: {draws}",
        f"- Rollouts: {rollouts}",
        f"- Tasks: {len(task_draws)}",
        "",
        "## Per-draw partition",
        "",
    ]
    header = ["draw", "control"] + [outcome.value for outcome in _RENDERED_OUTCOMES]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for attempt, control, counts, _rows in parsed:
        cells = [str(attempt), control or "-"] + [
            str(counts[outcome.value]) for outcome in _RENDERED_OUTCOMES
        ]
        lines.append("| " + " | ".join(cells) + " |")

    lines.extend(["", "## Per-task partition (worst-first)", ""])
    lines.append("| task | draws | solved | dominant cause |")
    lines.append("| --- | --- | --- | --- |")
    for task_id in ordered_tasks:
        lines.append(
            f"| {task_id} | {len(task_draws[task_id])} | {task_solved[task_id]} | "
            f"{_dominant_cause(task_causes[task_id])} |"
        )

    lines.extend(["", "## Disclosures", ""])
    for disclosure in disclosures_raw:
        if not isinstance(disclosure, str):
            raise ValueError("the document's 'disclosures' carries an entry that is not a string")
        lines.append(f"- {disclosure}")
    lines.append(f"- UNATTRIBUTED: {unattributed} rollout(s) the taxonomy could not name.")
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Read one complete night offline and write its reconciled failure partition.

    `--out` is checked **before** anything is read, the `autopsy.refuse_published_out` discipline
    applied here: the partition quotes stored completions, which carry the user's own private code,
    so a path git would commit is refused, named, with nothing loaded — for both the JSON document
    and the markdown render written beside it. A run without a ledger, a declared draw missing its
    journal or transcript, an unparsable evidence line and a partition that disagrees with the
    ledger are each exit 2 with the artefact named; no partial partition is ever written. Exit 0
    means a partition was produced. There is no 1 or 3: this is a report, not a go/no-go.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.bakeoff.night_autopsy",
        description=(
            "Read one complete night run and write its failure partition, reconciled against the "
            "ledger. Offline: no model is loaded and no network is touched, and the document is "
            "written only under a documented gitignored root."
        ),
    )
    parser.add_argument("--run", required=True, type=Path, help="a complete night run directory")
    parser.add_argument(
        "--tasks",
        action="append",
        default=[],
        type=Path,
        metavar="DIR",
        help=(
            "a corpus root, repeatable. Needed only to answer whether git would parse or apply a "
            "located diff; without it those rollouts are UNATTRIBUTED by name, never guessed at"
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        help=(
            "where the JSON document is written; defaults to <run>/night-autopsy.json. The "
            "markdown render is written beside it, with the same stem and a .md suffix"
        ),
    )
    namespace = parser.parse_args(argv)

    run = namespace.run
    out = namespace.out if namespace.out is not None else run / "night-autopsy.json"
    markdown_out = out.with_suffix(".md")
    try:
        refuse_published_out(out)
        refuse_published_out(markdown_out)
    except OutNotPrivate as exc:
        print(f"whetstone night-autopsy: {exc}", file=sys.stderr)
        return 2

    try:
        night = autopsy(run, task_roots=tuple(namespace.tasks))
    except (NotARun, IncompleteRun, UnreadableEvidence, CountDisagreement) as exc:
        print(f"whetstone night-autopsy: {exc}", file=sys.stderr)
        return 2

    written = document(night)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(written, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(render_markdown(written), encoding="utf-8")

    for draw in night.per_draw:
        rendered = ", ".join(
            f"{outcome.value}={count}"
            for outcome, count in sorted(_outcomes_of(draw).items(), key=lambda one: one[0].value)
        )
        print(f"draw {draw.attempt}: {rendered}")
    print(f"\nwrote {out}")
    print(f"wrote {markdown_out}")
    return 0


def _outcomes_of(draw: DrawResult) -> dict[Outcome, int]:
    """One draw's coarse counts, for the operator's one-line summary."""
    counts: dict[Outcome, int] = {}
    for row in draw.rows:
        counts[row.outcome] = counts.get(row.outcome, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
