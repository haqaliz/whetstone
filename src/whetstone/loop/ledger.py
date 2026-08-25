"""The run ledger: what the night pinned, what it drew, and what came of it — hashes and verdicts.

`docs/ROADMAP.md:403` makes this an exit criterion: *"the run ledger records pinned seeds, model
revision, task set, and tool versions"*. Those are four of the five pinned inputs
`PREREGISTRATION.md:131-132` fixes, and the fifth — the environment pins — is per task and already
committed in the manifests, so it is recorded here as the sentence that names where it lives
rather than as a copy that can go stale.

**Hashes and verdicts, never contents.** `tasks/ledger.py` established that discipline for the
committed mining evidence and this document keeps it even though it is written under a gitignored
root. The reason is not symmetry: a training set is drawn from the user's own private donor code,
the failure mode is a file that gets published later because it looked like evidence, and the only
defence that survives a future decision to publish is a document that never held the code in the
first place. A canary in the test suite plants donor source text and asserts none of it can reach
these bytes.

**The seed map is the determinism claim, written down.** Every applied `(task_id, attempt, seed)`
is recorded, in application order. The derivation is pure — a reader can recompute it from the run
seed with `shasum` — but a document that carried only the recipe could not tell a night that
followed it from one that skipped the seeding entirely, and the P2 determinism criterion is about
what the run *did*.

**It records; it does not decide.** Nothing here selects, counts differently from
`whetstone.loop.dataset`, or renders a report. Every figure in it is handed in by the caller that
derived it from the verifier's own records, from one place.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.bakeoff import report as bakeoff_report
from whetstone.bakeoff import run as bakeoff_run
from whetstone.bakeoff.report import GenerationContract
from whetstone.bakeoff.scoring import Rollout
from whetstone.loop.dataset import TRAINABLE, Dataset
from whetstone.loop.sampling import Applied
from whetstone.verify.verdict import Status

#: The document's own version, checked on read. A schema string rather than a shape check for the
#: reason `weights.PROVENANCE_SCHEMA` gives: every field this reader needs is one an optimistic
#: parse would default, and a defaulted seed map or task set records nothing while succeeding.
LEDGER_SCHEMA = "whetstone-run/1"

#: What the ledger is called inside a run directory.
LEDGER_FILE = "ledger.json"

#: How the fifth pinned input is recorded. A sentence rather than a dump: the pins are per task,
#: they are already in the manifests, and a copy here is a second version of them that can drift.
#: Taken from the bake-off's own wording **by identity**, so the two documents cannot describe the
#: same mechanism in two ways.
ENVIRONMENT_PINS = bakeoff_run._ENVIRONMENT_PINS


class LedgerUnreadable(ValueError):
    """The ledger is absent, malformed, or written to a schema this cannot read."""


@dataclass(frozen=True)
class HeldoutRecord:
    """The held-out exclusion a run applied: the document's digest and its membership count.

    Counts and digests only, never membership — the ledger's discipline is hashes and verdicts
    (`ledger.py:9-15`), and a reader holding the digest can open the committed document to see
    the ids. The digest is recomputed from the document's own payload rather than trusted from
    the file, but only after the loader has accepted it — the loader's checks are the gate, and
    this record is evidence about the run, never a second gate.
    """

    #: The digest the document's payload seals (`heldout.document_digest_of`).
    document_digest: str

    #: How many tasks the document holds out. Not the post-overlay count: the exclusion's
    #: size as the document declares it, so a reader can check the night against the document.
    membership_count: int


@dataclass(frozen=True)
class TaskSet:
    """Which tasks the night actually drew against — the pinned input, as counts and ids.

    Counts for the corpus, ids for the exclusions. The private manifests are the user's own code
    and their ids are theirs; the *dev subset* ids are this project's own declaration and are
    already published in `PREREGISTRATION.md` § 10.4, so recording them names nothing new.
    """

    #: How many source-B tasks were drawn against, after every exclusion.
    private: int

    #: How many source-A tasks. Always scored in full; both sources always publish together.
    public: int

    #: How many corpus directories source B was unioned from. Counted, never named: they live
    #: under `tasks/local/` and an absolute path from this machine discloses a private
    #: repository's name and a home directory while telling a reader nothing they can use.
    roots: int

    #: The declared dev-subset ids, excluded from both sources before anything was drawn.
    dev_subset: tuple[str, ...]

    #: `None` for a full night; the declared sample size when `--probe N` limited it.
    probe: int | None

    #: The held-out exclusion (`--heldout`), or `None` when none was applied. Older ledgers
    #: carry no such record; `read` tolerates the absence, and the default keeps every
    #: construction written before the field existed compiling.
    heldout: HeldoutRecord | None = None


@dataclass(frozen=True)
class Model:
    """The candidate, as the weights provenance verified it. One of the five pinned inputs."""

    #: The HuggingFace repository the weights came from, verbatim.
    repo_id: str

    #: The **immutable commit sha** the bytes were verified against — never a moving tag.
    revision: str


@dataclass(frozen=True)
class DrawRecord:
    """One draw index's outcome, per source: the harness's verdict and the counts under it.

    The harness status is first because it gates everything else: a draw whose control arm proved
    nothing contributes no training data, and its counts are recorded only so a reader debugging
    the night can see them — never as evidence about the base.
    """

    #: Which draw of `K`.
    attempt: int

    #: Source name to the control arm's reduced status over that source in this draw.
    harness: Mapping[str, Status]

    #: Source name to `(denominator, unverified, solved)`. Counts over this run's own records,
    #: in this run's own gitignored directory, which is their only home.
    counts: Mapping[str, tuple[int, int, int]]


@dataclass(frozen=True)
class Ledger:
    """Everything the night pinned and everything it produced. The document, before it is bytes."""

    #: The run's identifier, which is also its directory name under `runs/`.
    run_id: str

    #: The date the operator declared. An input, never the clock — the arms' rule.
    recorded_on: str

    #: The night's single declared seed. Every per-attempt seed descends from it.
    run_seed: int

    #: How many draws each task got. `sampling.K` unless a probe narrowed the night.
    draws: int

    #: The candidate.
    model: Model

    #: The frozen generation contract, recorded in full so a reader can tell which contract this
    #: night ran under without opening any other file.
    contract: GenerationContract

    #: The task set, after the dev overlay.
    task_set: TaskSet

    #: The versions a figure is only interpretable against.
    tool_versions: Mapping[str, str]

    #: Every seed applied, in application order.
    seeds: tuple[Applied, ...]

    #: One record per draw index.
    draws_recorded: tuple[DrawRecord, ...]

    #: The training set this night selected.
    dataset: Dataset

    #: What the valid-split rule decided — empty when there is a validation split, and the
    #: verbatim `dataset.NO_VALID_SPLIT` sentence when there is not.
    valid_split: str

    #: The checkpoint's digest, or `None` when the night wrote none. `None` is a **published
    #: outcome** rather than an omission: a night that produced no verified rollout produces no
    #: candidate, and the reason travels with it.
    checkpoint_digest: str | None

    #: Why there is no checkpoint, or empty when there is one.
    checkpoint_absent: str

    #: What the capacity probe measured, or `None` when it was not reached (nothing to train).
    capacity: Mapping[str, Any] | None


def document(ledger: Ledger) -> str:
    """The ledger as the exact bytes that get written. Text, because the artefact is the bytes."""
    return json.dumps(_payload(ledger), indent=2, sort_keys=True) + "\n"


def write(path: Path, ledger: Ledger) -> Path:
    """Write `document(ledger)` to `path`, creating its parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document(ledger), encoding="utf-8")
    return path


def read(path: Path) -> Mapping[str, Any]:
    """Read a ledger back, refusing anything not written to the declared schema."""
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise LedgerUnreadable(f"{str(path)!r} could not be read as JSON: {error}") from error
    if not isinstance(raw, dict) or raw.get("schema") != LEDGER_SCHEMA:
        raise LedgerUnreadable(
            f"{str(path)!r} does not declare schema {LEDGER_SCHEMA!r}; it declares "
            f"{raw.get('schema') if isinstance(raw, dict) else type(raw).__name__!r}. Refused "
            "rather than parsed optimistically: a defaulted seed map or task set records nothing "
            "and returns successfully"
        )
    return raw


def tool_versions() -> dict[str, str]:
    """The versions a figure is only interpretable against, from the bake-off's own function.

    Imported by identity rather than restated. A second list of tool versions is a second answer
    to "what was this measured under", and the day they disagreed neither document would say so.
    """
    return bakeoff_run._tool_versions()


def _payload(ledger: Ledger) -> dict[str, Any]:
    """The document's plain-JSON body, written field by field.

    `dataclasses.asdict` would carry a field added later into the file with no reader for it, so a
    schema change would round-trip lossily rather than failing — the `journal.py` codec rule.
    """
    return {
        "schema": LEDGER_SCHEMA,
        "run_id": ledger.run_id,
        "recorded_on": ledger.recorded_on,
        "run_seed": ledger.run_seed,
        "draws": ledger.draws,
        "model": {"repo_id": ledger.model.repo_id, "revision": ledger.model.revision},
        "generation_contract": {
            "prompt_sha256": ledger.contract.prompt_sha256,
            "sampler": ledger.contract.sampler,
            "max_tokens": ledger.contract.max_tokens,
            "extractor_version": ledger.contract.extractor_version,
            "dev_subset": list(ledger.contract.dev_subset),
            "retry_budget": ledger.contract.retry_budget,
            "retry_template_sha256": ledger.contract.retry_template_sha256,
            "diagnosis_vocabulary_version": ledger.contract.diagnosis_vocabulary_version,
            "retrieval": ledger.contract.retrieval,
        },
        "task_set": {
            "private": ledger.task_set.private,
            "public": ledger.task_set.public,
            "roots": ledger.task_set.roots,
            "dev_subset": list(ledger.task_set.dev_subset),
            "probe": ledger.task_set.probe,
            "heldout": None
            if ledger.task_set.heldout is None
            else {
                "document_digest": ledger.task_set.heldout.document_digest,
                "membership_count": ledger.task_set.heldout.membership_count,
            },
        },
        "environment_pins": ENVIRONMENT_PINS,
        "tool_versions": dict(sorted(ledger.tool_versions.items())),
        "seeds": [
            {"task_id": one.task_id, "attempt": one.attempt, "seed": one.seed}
            for one in ledger.seeds
        ],
        "draws_recorded": [_draw(one) for one in ledger.draws_recorded],
        "dataset": {
            "digest": ledger.dataset.digest,
            "examples": len(ledger.dataset.examples),
            "denominator": ledger.dataset.denominator,
            "unverified": ledger.dataset.unverified,
            "coverage": ledger.dataset.coverage,
            "valid_split": ledger.valid_split,
        },
        "checkpoint": {
            "digest": ledger.checkpoint_digest,
            "absent": ledger.checkpoint_absent,
        },
        "capacity": None if ledger.capacity is None else dict(sorted(ledger.capacity.items())),
    }


def _draw(one: DrawRecord) -> dict[str, Any]:
    """One draw index's record, as plain JSON types."""
    return {
        "attempt": one.attempt,
        "harness": {source: status.value for source, status in sorted(one.harness.items())},
        "counts": {
            source: {
                "denominator": counts[0],
                "unverified": counts[1],
                "solved": counts[2],
            }
            for source, counts in sorted(one.counts.items())
        },
    }


def counts_of(records: Sequence[Rollout]) -> tuple[int, int, int]:
    """`(denominator, unverified, solved)` over a draw's rollouts, using the one definition.

    `solved` is `whetstone.loop.dataset.TRAINABLE` — which is `report.tally`'s `Outcome.SOLVED`,
    imported rather than restated — so the ledger's count and the dataset's selection cannot
    disagree about what a win is. `unverified` reads `report._UNCOVERED`, the same frozen set
    `tally` reduces coverage against, for the identical reason: two spellings of "reached no
    verdict" would be two coverage figures. It is never removed from the denominator — coverage
    is reported, never silently excluded (`docs/ROADMAP.md:430-435`).
    """
    return (
        len(records),
        sum(1 for record in records if record.outcome in bakeoff_report._UNCOVERED),
        sum(1 for record in records if record.outcome is TRAINABLE),
    )


__all__ = [
    "ENVIRONMENT_PINS",
    "LEDGER_FILE",
    "LEDGER_SCHEMA",
    "DrawRecord",
    "HeldoutRecord",
    "Ledger",
    "LedgerUnreadable",
    "Model",
    "TaskSet",
    "counts_of",
    "document",
    "read",
    "tool_versions",
    "write",
]
