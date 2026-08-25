"""One night, end to end: draw, select, record, train — and never exit 0 without a candidate.

This is the door `docs/ROADMAP.md:399-400` names — *"`uv run whetstone run --night` produces
`runs/<id>/` with a ledger and a candidate under `checkpoints/<id>/`"* — and it is composition
only. Every honesty control it relies on was built and tested somewhere else and is used here by
identity: the frozen contract and its seal (`run.freeze`, `run.Sealed`), the dev-subset partition
(`run._partition`), the held-out exclusion and its loader (`heldout.exclude_heldout`,
`heldout.read_document` — aspect 1 of the promotion gate, consumed by identity), the weights
re-hash (`weights.load_weights`), the control arm (`sweep.rankable`), the single definition of
*solved* (`dataset.TRAINABLE`, which is `report.tally`'s `Outcome.SOLVED`), and the capacity
probe that may stop the training.

**One candidate per night, refused rather than resolved.** A night produces *a* checkpoint; two
candidates would produce two, or one trained on a dataset drawn from both, and neither has a
meaning P3's gate could act on. `--only` narrows, exactly as the bake-off's does, and a weights
provenance holding several with no `--only` is a usage error.

**Locality, in the form that is coherent here.** The bake-off refuses a transcript under `--out`
because `--out` is a *published* directory. A night publishes nothing — no report, no figure about
a model (P4) — so its counterpart is stronger and simpler: the run root and the checkpoint root
must not resolve inside a committed `reports/` directory, and the refusal raises
`run.TranscriptNotPrivate` **imported by identity**, so this repository has one vocabulary for
"private evidence was pointed at a published path" rather than two.

**A night with no candidate can never exit 0.** The exit code is `cli.py`'s existing 0/1/2/3
contract: a checkpoint is 0; anything else reduces through `whetstone.verify.verdict.reduce` and
is floored at FAIL, because "the loop ran and produced nothing to promote" is a finding, never a
success. An unproven harness is 3 — nothing could be concluded.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from whetstone.bakeoff.diffcheck import diagnosis_vocabulary_sha256
from whetstone.bakeoff.mlx_runtime import DEFAULT_MAX_TOKENS
from whetstone.bakeoff.report import _UNCOVERED, GenerationContract
from whetstone.bakeoff.retry import RETRY_BUDGET, retry_template_sha256
from whetstone.bakeoff.run import (
    HF_HUB_OFFLINE,
    Contract,
    Engine,
    TranscriptNotPrivate,
    UnknownCandidate,
    UnknownDevSubset,
    _extractor_version,
    _partition,
    freeze,
    load_task_roots,
    select_candidates,
)
from whetstone.bakeoff.scoring import Interpreters, Rollout
from whetstone.bakeoff.sweep import HarnessNotProven, rankable
from whetstone.bakeoff.transcript import Transcript
from whetstone.bakeoff.weights import (
    ProvenanceUnreadable,
    Weights,
    WeightsUnverified,
    load_weights,
)
from whetstone.loop import dataset as training
from whetstone.loop import ledger as run_ledger
from whetstone.loop import sft
from whetstone.loop.draws import Drawn, sample
from whetstone.loop.heldout import (
    EmptyHeldout,
    Heldout,
    HeldoutDigestMismatch,
    HeldoutSchemaError,
    UnknownHeldoutId,
    document_digest_of,
    exclude_heldout,
    read_document,
)
from whetstone.loop.sampling import (
    SAMPLER,
    Applied,
    K,
    Seeder,
    attempt_seed,
    mlx_seeder,
    sampling_engine,
)
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.verdict import Status, Verdict, reduce

#: The directory inside a run holding the per-draw journals and transcripts.
EVIDENCE_DIR = "draws"

#: The directory inside a run holding mlx-lm's local dataset format.
DATA_DIR = "data"

#: The dataset's own record document, beside the ledger.
DATASET_FILE = "dataset.json"

#: The committed report home whose name a private root may not be written under. A directory
#: name rather than a path, because the check is about where an operator pointed the run and the
#: repository may be checked out anywhere.
PUBLISHED = "reports"

#: How a source is named in every record this module writes. Both are always present, because
#: both sources always publish together (`PREREGISTRATION.md:142-147`) — a night that drew
#: against one alone would produce a dataset a reader could not place.
PRIVATE = "private"
PUBLIC = "public"


class ManyCandidates(ValueError):
    """A night was pointed at more than one candidate, so it would produce more than one answer.

    Refused rather than resolved. A checkpoint is *the* night's candidate; two of them trained on
    two datasets is two experiments in one run directory, and one trained on a pooled dataset is a
    checkpoint whose base nobody can name. Narrow with `--only`.
    """


class EmptyTaskSet(ValueError):
    """The overlays (dev-subset, held-out) left no source-B task to draw against.

    Named rather than a bare `ValueError`, and refused **before** the contract is frozen. Left
    alone the night would draw against source A alone, spend hours doing it, and produce a dataset
    a reader could not place — both sources always publish together.
    """


@dataclass(frozen=True)
class Night:
    """What one night produced, so a caller can assert on it without re-reading the disk."""

    #: The operator-declared id, which is also the run directory's name.
    run_id: str

    #: `runs/<id>/`, holding the ledger, the dataset document, the data directory and the
    #: per-draw evidence.
    directory: Path

    #: The written ledger.
    ledger: Path

    #: The frozen question every draw was asked.
    contract: Contract

    #: One record per draw index.
    drawn: tuple[Drawn, ...]

    #: The selected training set.
    dataset: training.Dataset

    #: What the valid-split rule decided; the verbatim degenerate sentence when there is none.
    valid_split: str

    #: The night's candidate, or `None` when it produced none. `None` is a published outcome.
    checkpoint: sft.Checkpoint | None

    #: Why there is no candidate, or empty when there is one.
    checkpoint_absent: str

    #: The night's reduced verdict over its task set. Never rendered as a score about a base.
    status: Status

    #: The held-out exclusion this night applied (`--heldout`), or `None` for a plain night.
    #: The digest and the membership count, never the membership — the ledger's discipline —
    #: so the disclosure can name the document without reopening the file that is its home.
    heldout: run_ledger.HeldoutRecord | None = None


def run_night(
    *,
    tasks: Sequence[Path],
    public: Path,
    pool: Path,
    weights: Path,
    runs: Path,
    checkpoints: Path,
    workspace: Path,
    timeout: float,
    recorded_on: str,
    run_id: str,
    run_seed: int,
    dev_subset: Sequence[str] = (),
    heldout: Path | None = None,
    draws: int = K,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    only: Sequence[str] = (),
    probe: int | None = None,
    retries: bool = True,
    engine: Engine = sampling_engine,
    trainer: sft.Trainer = sft.mlx_trainer,
    seeder: Seeder = mlx_seeder,
) -> Night:
    """Run a night and return what it produced. The order below is the design.

    Private roots are refused first, before anything is loaded, so an operator who pointed the run
    at a published directory learns it in a second rather than after the generation is paid for.
    The weights are re-hashed before a question is frozen; the question is frozen before an engine
    exists; the control arm is run before the draws it controls for; and the training happens last,
    behind a capacity probe that may refuse it.

    `retries` defaults **on**, unlike the bake-off's. The hardened contract is what the larger-base
    arm measured and what `PREREGISTRATION.md` § 10.4 discloses, and a night is not a comparison
    against the baseline's contract — it is the loop, running under the contract the evidence was
    produced with. It is still a flag, and the contract records what it was.

    `probe` narrows the private source to its first `N` tasks and writes **no checkpoint**: it
    exists so the whole chain can be validated cheaply before a real night, and a probe that
    trained would produce a candidate from a self-chosen sample.

    `heldout` is the promotion gate's pinned input: aspect 1's committed
    `whetstone-heldout/1` document at `tasks/heldout/source-b.json`. Its membership is
    excluded at the partition seam, before the contract is frozen, so both audit trails cover
    the exclusion automatically — `freeze` digests the prompts of the tasks it is handed, and
    the dataset is selected from the draws over the filtered set. The document is **consumed,
    never recomputed**, and the loader is aspect 1's, by identity. The dev overlay applies on
    top: a declared dev id inside the held-out band is exclusion, never a refusal, so the
    membership resolves against the full loaded corpus while the exclusion itself applies to
    the post-overlay set. Absent, the night is today's night, byte for byte.
    """
    _refuse_published_root(runs, "--runs")
    _refuse_published_root(checkpoints, "--checkpoints")
    os.environ[HF_HUB_OFFLINE] = "1"

    private_root_tasks = load_task_roots(tasks)
    heldout_record: run_ledger.HeldoutRecord | None = None
    heldout_membership: frozenset[str] = frozenset()
    if heldout is not None:
        heldout_document, document_digest = _read_heldout(heldout)
        heldout_record = run_ledger.HeldoutRecord(
            document_digest=document_digest,
            membership_count=len(heldout_document.membership),
        )
        # Resolve the membership against the FULL loaded corpus, never the post-overlay set:
        # a declared dev id inside the held-out band is removed by the overlay first, and
        # dev ∩ held-out is exclusion, never refusal. The exclusion itself then applies to
        # the post-overlay set below, keeping the overlay on top.
        exclude_heldout(heldout_document.membership, private_root_tasks)
        heldout_membership = frozenset(heldout_document.membership)
    private_tasks, public_tasks, declared = _partition(
        private_root_tasks, load_tasks(public), dev_subset
    )
    if heldout_membership:
        private_tasks = tuple(
            task for task in private_tasks if task.task_id not in heldout_membership
        )
    if probe is not None:
        private_tasks = private_tasks[:probe]
    if not private_tasks:
        overlays = (
            "the dev-subset overlay and the held-out exclusion"
            if heldout_record is not None
            else "the dev-subset overlay"
        )
        raise EmptyTaskSet(
            f"no source-B task survived {overlays}, so this night would draw against "
            "source A alone. Both sources always publish together; refused here, before the "
            "contract is frozen or anything is generated"
        )

    contract = freeze((*private_tasks, *public_tasks), pool=pool, retry=retries)
    fetched = select_candidates(load_weights(weights), only)
    if len(fetched) != 1:
        raise ManyCandidates(
            f"a night trains one candidate and this weights root offers {len(fetched)}: "
            f"{', '.join(one.repo_id for one in fetched)}. Narrow it with --only. Two candidates "
            "would produce two checkpoints in one run directory, or one checkpoint trained on a "
            "pooled dataset whose base nobody could name"
        )
    candidate: Weights = fetched[0]

    directory = runs / run_id
    directory.mkdir(parents=True, exist_ok=True)
    drawn = sample(
        candidate=candidate.repo_id,
        sources={PRIVATE: private_tasks, PUBLIC: public_tasks},
        engine=engine(candidate, max_tokens),
        contract=contract,
        run_seed=run_seed,
        draws=draws,
        evidence=directory / EVIDENCE_DIR,
        sandbox_root=workspace / "sandbox",
        timeout=timeout,
        interpreters=Interpreters(workspace=workspace / "environments"),
        pool=pool,
        seeder=seeder,
        retries=retries,
    )

    texts, denominator, unverified = _select(drawn, run_seed=run_seed)
    selected = training.build(texts, denominator=denominator, unverified=unverified)
    chosen = training.split(texts, run_seed=run_seed)
    training.write_local(directory / DATA_DIR, chosen)
    training.write_document(directory / DATASET_FILE, selected)

    checkpoint, absent, capacity = _train(
        candidate=candidate,
        selected=selected,
        chosen=chosen,
        directory=directory,
        checkpoints=checkpoints / run_id,
        run_seed=run_seed,
        probe=probe,
        trainer=trainer,
    )

    ledger = run_ledger.Ledger(
        run_id=run_id,
        recorded_on=recorded_on,
        run_seed=run_seed,
        draws=draws,
        model=run_ledger.Model(repo_id=candidate.repo_id, revision=candidate.revision),
        contract=_contract(contract, max_tokens=max_tokens, declared=declared, retries=retries),
        task_set=run_ledger.TaskSet(
            private=len(private_tasks),
            public=len(public_tasks),
            roots=len(tasks),
            dev_subset=declared,
            probe=probe,
            heldout=heldout_record,
        ),
        tool_versions=run_ledger.tool_versions(),
        seeds=_seeds(drawn),
        draws_recorded=_records(drawn),
        dataset=selected,
        valid_split=chosen.reason,
        checkpoint_digest=None if checkpoint is None else checkpoint.digest,
        checkpoint_absent=absent,
        capacity=None if capacity is None else capacity.recorded(),
    )
    written = run_ledger.write(directory / run_ledger.LEDGER_FILE, ledger)

    return Night(
        run_id=run_id,
        directory=directory,
        ledger=written,
        contract=contract,
        drawn=drawn,
        dataset=selected,
        valid_split=chosen.reason,
        checkpoint=checkpoint,
        checkpoint_absent=absent,
        status=_status(drawn),
        heldout=heldout_record,
    )


def disclosure(night: Night) -> tuple[str, ...]:
    """The lines a night prints: the training-set size **with** the unverified count beside it.

    Never the size alone. It grows with the number of draws and says nothing about how much of the
    task set was actually graded, so a bare example count is the flattering half of a measurement
    — `docs/ROADMAP.md:430-435` requires coverage and the unverified rate to be reported from the
    first run onward, and this is that requirement at the smallest surface it has.

    A held-out night adds its own line: the document (by its digest) and the size of the
    membership it excluded. The ledger is the record `check-leakage` reads; the terminal is what
    the operator sees at the end of a night, and a run that excluded ten tasks must say so to the
    person who ran it — absent the line, an unflagged night's output is today's output, byte for
    byte.
    """
    lines = [
        f"run {night.run_id}: {len(night.dataset.examples)} strict-PASS training examples "
        f"from {night.dataset.denominator} rollout records "
        f"(coverage {night.dataset.coverage}, unverified {night.dataset.unverified})",
        f"dataset digest {night.dataset.digest}",
    ]
    if night.heldout is not None:
        lines.append(
            f"held out {night.heldout.membership_count} source-B tasks under document digest "
            f"{night.heldout.document_digest}"
        )
    if night.valid_split:
        lines.append(f"validation: {night.valid_split}")
    if night.checkpoint is None:
        lines.append(f"no candidate: {night.checkpoint_absent}")
    else:
        lines.append(
            f"candidate {night.checkpoint.directory} digest {night.checkpoint.digest}"
        )
    lines.append(f"ledger {night.ledger}")
    return tuple(lines)


def _read_heldout(path: Path) -> tuple[Heldout, str]:
    """Load the held-out document by identity and return it with the digest its payload seals.

    The loader validates and deliberately does not carry the digest (`heldout.py:243-247`):
    a consumer that re-checked it would be a second answer to "is this document trustworthy".
    Recording it is different — the ledger carries it so `check-leakage` can name the document
    the night excluded — so the digest is read back from the file the loader just accepted and
    recomputed through the module's own function rather than trusted from the file.

    A plain `ValueError` (an unreadable file) is wrapped as the loader's own schema error, the
    `run.py:563-576` shape: a document that half-parses names a membership the night cannot
    attribute, and a pinned input that cannot be read is refused rather than defaulted.
    """
    location = Path(path)
    try:
        loaded = read_document(location)
    except ValueError as exc:
        if isinstance(exc, (HeldoutSchemaError, HeldoutDigestMismatch, EmptyHeldout)):
            raise
        raise HeldoutSchemaError(
            f"the held-out document {str(location)!r} could not be read as a run input: "
            f"{exc}. A document that half-parses names a membership the night cannot "
            "attribute, and a pinned input that cannot be read is refused rather than "
            "defaulted"
        ) from exc
    raw = json.loads(location.read_text(encoding="utf-8"))
    return loaded, document_digest_of(raw)


def _select(
    drawn: Sequence[Drawn], *, run_seed: int
) -> tuple[tuple[training.TrainingText, ...], int, int]:
    """Turn every draw's rollouts into training texts, and count what they were selected out of.

    `rankable` gates each (draw, source) by identity: a draw whose control arm proved nothing
    raises `HarnessNotProven` here, before any of its rollouts can become an example. That is the
    whole of requirement 7 — nothing trainable comes out of an unproven harness — and it is
    enforced by the bake-off's own door rather than by a second check.

    The completion is read from that draw's transcript. A verified rollout with no stored
    completion is a defect rather than an absence: `score` generated it, so a transcript missing it
    means the recorder was not composed, and training on a reconstructed string would train on
    something no base ever wrote.
    """
    texts: list[training.TrainingText] = []
    denominator = 0
    unverified = 0
    for draw in drawn:
        recorded = Transcript(path=draw.transcript).replay()
        seeds = {(one.task_id, one.attempt): one.seed for one in draw.seeds}
        for source, run in draw.runs.items():
            records: tuple[Rollout, ...] = rankable(run)
            counts = run_ledger.counts_of(records)
            denominator += counts[0]
            unverified += counts[1]
            for record in records:
                if not training.trainable(record):
                    continue
                stored = recorded.get((record.candidate, record.task_id))
                if stored is None:
                    raise training.NotTrainable(
                        f"{record.task_id!r} draw {draw.attempt} is a verified win with no stored "
                        f"completion in {str(draw.transcript)!r}. The text a checkpoint trains on "
                        "must be the text the base actually wrote; there is nothing here to "
                        "reconstruct it from and nothing this module would invent"
                    )
                texts.append(
                    training.TrainingText(
                        example=training.example_of(
                            record,
                            source=source,
                            attempt=draw.attempt,
                            # The recorded seed when this draw generated, and the derivation when
                            # it replayed from a checkpoint — the two are the same value, because
                            # the derivation is pure, and a resumed night must produce the records
                            # an uninterrupted one would have.
                            seed=seeds.get(
                                (record.task_id, draw.attempt),
                                attempt_seed(run_seed, record.task_id, draw.attempt),
                            ),
                            completion=stored.completion,
                            control=run.status,
                        ),
                        prompt=stored.prompt,
                        completion=stored.completion,
                    )
                )
    return tuple(texts), denominator, unverified


def _train(
    *,
    candidate: Weights,
    selected: training.Dataset,
    chosen: training.Split,
    directory: Path,
    checkpoints: Path,
    run_seed: int,
    probe: int | None,
    trainer: sft.Trainer,
) -> tuple[sft.Checkpoint | None, str, sft.CapacityProbe | None]:
    """Probe capacity, train, and hash the result — or say, in one sentence, why none of that ran.

    Three ways there is no candidate, and each is a *stated* outcome rather than a silence: the
    night was a probe, the night selected nothing, or the capacity probe measured a peak above the
    declared headroom. The third is a published capacity finding, which is why it is caught and
    recorded here rather than allowed to abort the ledger — a night that discovered its own
    machine cannot train is a night whose evidence is worth keeping.
    """
    if probe is not None:
        return None, (
            f"this was a --probe {probe} run: a declared sample of the private source, drawn to "
            "validate the chain. A probe that trained would produce a candidate from a "
            "self-chosen subset"
        ), None
    if not selected.examples:
        return None, (
            "this night selected no strict-PASS rollout, so there is nothing to train on. The "
            "response is to raise the number of draws, never to loosen what counts as a win"
        ), None

    request = sft.TrainingRequest(
        model_path=candidate.local_dir,
        revision=candidate.revision,
        data=directory / DATA_DIR,
        adapters=checkpoints,
        args=sft.TrainingArgs(),
    )
    capacity = sft.probe_capacity(request, trainer=trainer)
    try:
        sft.train(request, trainer=trainer, capacity=capacity, examples=len(selected.examples))
    except sft.CapacityExceeded as exceeded:
        return None, str(exceeded), capacity

    checkpoint = sft.write_checkpoint(
        checkpoints,
        repo_id=candidate.repo_id,
        revision=candidate.revision,
        dataset_digest=selected.digest,
        run_seed=run_seed,
        args=request.args,
        tool_versions=run_ledger.tool_versions(),
        valid_split=chosen.reason,
        capacity=capacity,
    )
    # Re-read what was just written. The gate that later compares checkpoints will re-hash them,
    # and a checkpoint that cannot survive its own verification an instant after being written is
    # one nobody should discover is broken three weeks later.
    sft.verify_checkpoint(checkpoints)
    return checkpoint, "", capacity


def _contract(
    contract: Contract, *, max_tokens: int, declared: Sequence[str], retries: bool
) -> GenerationContract:
    """The night's contract in the bake-off's own published shape, so the two are comparable.

    Constructed through `GenerationContract` rather than a shape of this module's own: a new
    contract type would be a § 10 amendment, never something a loop invented on its way to a
    ledger.
    """
    return GenerationContract(
        prompt_sha256=contract.sha256,
        sampler=SAMPLER,
        max_tokens=max_tokens,
        extractor_version=_extractor_version(),
        dev_subset=tuple(declared),
        retry_budget=RETRY_BUDGET if retries else 0,
        retry_template_sha256=retry_template_sha256() if retries else "",
        diagnosis_vocabulary_version=diagnosis_vocabulary_sha256() if retries else "",
        retrieval="oracle",
    )


def _seeds(drawn: Sequence[Drawn]) -> tuple[Applied, ...]:
    """Every applied seed across every draw, in draw order then application order."""
    return tuple(one for draw in drawn for one in draw.seeds)


def _records(drawn: Sequence[Drawn]) -> tuple[run_ledger.DrawRecord, ...]:
    """One ledger record per draw index: the harness's verdict and this run's own counts."""
    return tuple(
        run_ledger.DrawRecord(
            attempt=draw.attempt,
            harness={source: run.status for source, run in draw.runs.items()},
            counts={
                source: run_ledger.counts_of(run.rollouts)
                for source, run in draw.runs.items()
            },
        )
        for draw in drawn
    )


def _status(drawn: Sequence[Drawn]) -> Status:
    """The night's reduced verdict, per task across every draw, worst-status-wins.

    A task is a PASS when **any** draw solved it — that is what rejection sampling means. It is
    UNVERIFIED when no draw reached a verdict at all, which is the direction an unknown has to
    fall. Otherwise it is a FAIL: draws happened, were graded, and none of them fixed the bug.

    Reduced through `whetstone.verify.verdict.reduce` rather than a local maximum, because the
    ordering that puts UNVERIFIED above PASS is the honesty contract and it is defined in exactly
    one place.
    """
    per_task: dict[tuple[str, str], list[Rollout]] = {}
    for draw in drawn:
        for source, run in draw.runs.items():
            for record in run.rollouts:
                per_task.setdefault((source, record.task_id), []).append(record)

    verdicts: list[Verdict] = []
    for (source, task_id), records in sorted(per_task.items()):
        if any(training.trainable(record) for record in records):
            status = Status.PASS
        elif all(record.outcome in _UNCOVERED for record in records):
            status = Status.UNVERIFIED
        else:
            status = Status.FAIL
        verdicts.append(
            Verdict(
                kind="task",
                status=status,
                observed=f"{source}:{task_id}",
                expected=None,
                message=f"{task_id} reduced to {status.value} over {len(records)} draws",
            )
        )
    return reduce(verdicts)


def _refuse_published_root(root: Path, flag: str) -> None:
    """Refuse a private root pointed inside a committed report directory, before anything runs.

    Resolved rather than compared as written, because `reports/../reports/x` and a symlinked
    scratch directory both name a path inside `reports/` while comparing unequal to it — and the
    check has to hold against the path that gets written, not the one that got typed.
    `strict=False` throughout: neither directory exists on the first night, and a check that
    required them to would refuse every honest invocation.

    Raises the bake-off's own `TranscriptNotPrivate`, imported by identity, so this repository has
    one name for "private evidence was pointed at a published path". A night's evidence is the
    user's own donor code — completions quote it back verbatim — and the reason `reports/` is the
    named home is that it is the one directory in this tree an outside reader is expected to read.
    """
    if PUBLISHED in root.resolve().parts:
        raise TranscriptNotPrivate(
            f"{flag} points at {str(root)!r}, which is inside a {PUBLISHED}/ directory — the one "
            "place in this tree an outside reader is expected to read. A night writes prompts, "
            "completions and an adapter trained on them, and a source-B completion quotes the "
            "user's own private donor code back verbatim. Point it at a gitignored root "
            "(`runs/`, `checkpoints/`). Refused rather than warned about, because a warning at "
            "the top of a night's run is read after the files already exist"
        )


#: Every refusal a night raises that is an **operator's error** rather than a finding: a private
#: root pointed at a published directory, a weights provenance that does not match the disk, a
#: `--only` that matches nothing or several, a dev-subset id that excludes nothing, a held-out
#: document that cannot be read or whose membership resolves nowhere, an empty task set.
#: Collected here so `cli.py` — a guarded root, which may hold exactly one function-local
#: import into this package — can map them to the documented usage code without importing five
#: modules of the bake-off to name them.
REFUSALS: tuple[type[Exception], ...] = (
    TranscriptNotPrivate,
    ManyCandidates,
    UnknownCandidate,
    UnknownDevSubset,
    UnknownHeldoutId,
    HeldoutSchemaError,
    HeldoutDigestMismatch,
    EmptyHeldout,
    EmptyTaskSet,
    ProvenanceUnreadable,
    WeightsUnverified,
)

#: The refusals that mean *nothing could be concluded* rather than *you invoked me wrongly*: a
#: control arm that never proved this harness grades anything, and a verified rollout whose
#: completion is not in the evidence. Both reduce to UNVERIFIED at the process boundary, which is
#: deliberately neither 0 nor the usage code — see `cli.py`'s exit-code contract.
UNPROVEN: tuple[type[Exception], ...] = (HarnessNotProven, training.NotTrainable)


__all__ = [
    "DATASET_FILE",
    "DATA_DIR",
    "EVIDENCE_DIR",
    "PRIVATE",
    "PUBLIC",
    "PUBLISHED",
    "REFUSALS",
    "UNPROVEN",
    "EmptyTaskSet",
    "ManyCandidates",
    "Night",
    "UnknownCandidate",
    "disclosure",
    "run_night",
]
