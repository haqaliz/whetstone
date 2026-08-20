"""Selection: which rollouts may be trained on, and the one rule that decides it.

This is the module the project's central claim rests on. The reward is deterministic
re-execution, so a policy cannot talk its way into the dataset — but only if *selection* reads
the verifier's own record and nothing else. Every failure mode this project exists to avoid ends
with a training set that contains something nobody verified.

**One definition of solved, imported rather than restated.** `whetstone.bakeoff.report.tally`
defines the published headline as `record.outcome is Outcome.SOLVED`, and this module applies
**that member**, by identity, to the same `Rollout` records. A re-derived notion here — "STRICT
said PASS", say, which is nearly the same thing — would be a second definition, and the moment the
two disagreed the disagreement would be invisible: both would look correct in isolation and the
dataset would be selected by whichever ran.

**`UNVERIFIED` is not training data, and neither is anything else.** The partition below is
enumerated in full and asserted complete against `Outcome`'s members, so a member added later
fails the build here rather than silently falling into whichever branch an `if` happened to end
in. `UNVERIFIED` in particular is the direction an unknown has to fall: a task the harness could
not grade is not a win, and a loop that trained on one would be training on its own inability to
measure.

**Two verdicts, not one.** An example must carry `Outcome.SOLVED` **and** a recorded strict
`Status.PASS`. Those are not redundant: `Outcome` is this project's tag for *which kind of result*
a rollout was, `Status` is the verifier's own reduced verdict, and requiring both means a record
whose two halves disagree — the shape a codec bug or a hand-edited journal produces — is refused
rather than trained on.

**Locality.** An example's *record* carries hashes and verdicts and never contents, exactly as
`tasks/ledger.py` does: it is the shape a committed document would take, so the discipline holds
even though this document is written under a gitignored root. The prompt and completion — the
user's own private donor code, quoted back — live in `TrainingText`, which is written only into
mlx-lm's local dataset directory under that same gitignored root and never into any document this
module digests.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.verify.verdict import Status

#: The one outcome a rollout may be trained on. The member itself, taken from the module that
#: defines the published headline, so that "trainable" and "solved" cannot drift apart.
TRAINABLE = Outcome.SOLVED

#: Every other outcome, enumerated rather than implied. Derived from `Outcome` so it cannot fall
#: behind the enum, and asserted to partition it exactly (`tests/loop/test_dataset.py`): a member
#: added later has to be classified by whoever adds it, in a diff, rather than inheriting a
#: branch by accident.
NOT_TRAINABLE = frozenset(member for member in Outcome if member is not TRAINABLE)

#: The document this module writes, as the schema string a reader checks before parsing. A schema
#: rather than a shape check because every field a partial read would default is a field that
#: makes the document verify nothing while returning successfully.
DATASET_SCHEMA = "whetstone-training-set/1"

#: What fraction of the strict-PASS examples are held back for the trainer's validation split.
#: Declared here, before any night, for the reason `sampling.K` is: a per-run split fraction is a
#: knob somebody turns after seeing a loss curve.
VALID_FRACTION = 0.1

#: The floor, in examples, below which there is **no valid split at all**. Pre-committed in the
#: SFT spec: a one-example validation set is not validation, it is a number that looks like
#: validation, and a checkpoint validated against it would carry a claim nobody could defend.
VALID_FLOOR = 2

#: What the checkpoint's provenance states, verbatim, when the floor was not met. A constant
#: because two spellings of it would be two claims, and a test asserts the checkpoint carries this
#: exact sentence rather than something that merely resembles it.
NO_VALID_SPLIT = "no valid split (strict-PASS set below floor)"

#: mlx-lm's local dataset filenames (`mlx_lm.tuner.datasets.load_local_dataset`). `test.jsonl` is
#: deliberately absent: there is no test split here. Held-out evaluation is P3's, and a file named
#: `test` written from training data is the exact confusion `PREREGISTRATION.md` § 7.1 forbids —
#: nothing trained on may later be quoted as held out.
TRAIN_FILE = "train.jsonl"
VALID_FILE = "valid.jsonl"


class NotTrainable(ValueError):
    """A record that is not a verified win was offered as training data. Refused, never dropped.

    Raised rather than filtered, because the two are different claims. Filtering says "the dataset
    holds only wins"; raising says "nothing that was not a win was ever offered", and only the
    second survives a caller that assembles its own record list. The exit criterion
    (`docs/ROADMAP.md:401-402`) is the second.
    """


@dataclass(frozen=True)
class Example:
    """One training example, as evidence: hashes and verdicts, never contents.

    The shape a *committed* document would take (`tasks/ledger.py`), used even though this one is
    written under a gitignored root — the discipline is what stops a completion, which quotes the
    user's own donor code back verbatim, from reaching a file somebody later decides to publish.
    """

    #: The task this rollout was for.
    task_id: str

    #: `"private"` (source B) or `"public"` (source A). Both are recorded because both are always
    #: published together (`PREREGISTRATION.md:142-147`) and a dataset drawn from one alone is a
    #: fact a reader has to be able to see.
    source: str

    #: Which draw of `K` produced it. One-based; with the run seed it recomputes the seed below.
    attempt: int

    #: The seed applied before this draw, as applied rather than as recomputed.
    seed: int

    #: The digest of the prompt the base was shown, tying the example to the frozen contract.
    prompt_sha256: str

    #: The digest of the completion, tying the example to the transcript record it came from.
    completion_sha256: str

    #: STRICT's reduced verdict — the reward. `PASS`, by construction; recorded so the exit
    #: criterion's test reads a field rather than trusting a filter.
    strict: Status

    #: This project's tag for the kind of result. `SOLVED`, by construction, recorded for the
    #: same reason.
    outcome: Outcome

    #: The control arm's verdict over the run this example came from. `PASS` means the harness was
    #: shown to discriminate on that run; nothing else may produce an example at all.
    control: Status


@dataclass(frozen=True)
class TrainingText:
    """The private half of an example: what the base was asked and what it wrote back.

    Kept apart from `Example` structurally rather than by convention. The record is digested,
    ledgered and read by people; this is the user's own code and goes to exactly one place — the
    mlx-lm dataset directory under the run's gitignored root.
    """

    #: The record this text belongs to.
    example: Example

    #: The prompt, verbatim.
    prompt: str

    #: The completion, verbatim — never normalised, for the reason `transcript.py` gives.
    completion: str

    @property
    def text(self) -> str:
        """The training string: the question and the answer, concatenated and nothing else.

        No separator token, no chat template, no instruction wrapper. The prompt is what the base
        was actually shown (`mlx_runtime.CHAT_TEMPLATE`: "none: the rendered prompt is passed to
        mlx_lm verbatim"), and inserting anything here would train the model on a format that
        nothing generates against.
        """
        return self.prompt + self.completion


@dataclass(frozen=True)
class Dataset:
    """The night's training set: the examples, the digest over them, and what they came out of.

    `denominator` and `unverified` travel with the examples deliberately. A training-set size on
    its own is a number that flatters — it grows with `K` and says nothing about coverage — and
    `docs/ROADMAP.md:430-435` requires the unverified count to be disclosed beside it from the
    first run onward.
    """

    #: Every selected example, in a fixed order (task id, then draw index).
    examples: tuple[Example, ...]

    #: sha256 over the canonical document. The pinned input a checkpoint's provenance names, so
    #: "which data was this adapter trained on" has an answer that is one value long.
    digest: str

    #: How many rollout records were considered. Every draw of every task, including the ones that
    #: reached no verdict: an example count over a filtered denominator is coverage-by-construction.
    denominator: int

    #: How many of those reached no verdict at all. Never removed from `denominator`.
    unverified: int

    @property
    def coverage(self) -> int:
        """Rollouts that reached a verdict. The honest complement of `unverified`."""
        return self.denominator - self.unverified


@dataclass(frozen=True)
class Split:
    """Train and validation, or train and the reason there is no validation.

    Two states and no third. `valid` empty *with* `reason` set is the declared degenerate case;
    `valid` empty with no reason cannot be constructed, which is what stops a checkpoint being
    silently unvalidated.
    """

    #: What the trainer sees.
    train: tuple[TrainingText, ...]

    #: What it validates against, possibly empty.
    valid: tuple[TrainingText, ...]

    #: `NO_VALID_SPLIT`, verbatim, when the floor was not met; empty when there is a valid split.
    reason: str

    def __post_init__(self) -> None:
        if not self.valid and self.reason != NO_VALID_SPLIT:
            raise ValueError(
                "a split with no validation examples must state why, verbatim: "
                f"{NO_VALID_SPLIT!r}. Got {self.reason!r}. A checkpoint whose provenance is "
                "silent about a missing validation split reads exactly like one that was "
                "validated"
            )
        if self.valid and self.reason:
            raise ValueError(
                f"a split with {len(self.valid)} validation examples also declares {self.reason!r}"
            )


def trainable(record: Rollout) -> bool:
    """Whether `record` is a verified win. The single predicate, and it reads two fields.

    `outcome is TRAINABLE` is `report.tally`'s own definition applied by identity. The strict
    status is required alongside it because the two are produced by different steps — the tag by
    `scoring._classify`, the verdict by the verifier — and a record whose halves disagree is
    evidence of a defect, not of a win.
    """
    return record.outcome is TRAINABLE and record.strict is Status.PASS


def example_of(
    record: Rollout,
    *,
    source: str,
    attempt: int,
    seed: int,
    completion: str,
    control: Status,
) -> Example:
    """Turn one verified rollout into a training record — or refuse it by name.

    Refuses rather than returns `None`: a caller that ignored a `None` would assemble a shorter
    dataset and report it as the whole one, which is the same silent-shortening failure the
    journal's raise-don't-skip rule exists to prevent one layer down.
    """
    if not trainable(record):
        raise NotTrainable(
            f"{record.task_id!r} draw {attempt} is not training data: outcome "
            f"{record.outcome.value}, strict "
            f"{None if record.strict is None else record.strict.value}. "
            f"Only {TRAINABLE.value} with a recorded strict {Status.PASS.value} may be trained on "
            "— every other outcome is either a loss or the absence of a measurement, and "
            "UNVERIFIED is never a win"
        )
    if control is not Status.PASS:
        raise NotTrainable(
            f"{record.task_id!r} draw {attempt} came from a run whose control arm reduced to "
            f"{control.value}. Nothing an unproven harness measured is evidence about a base, so "
            "nothing it produced is trainable either"
        )
    return Example(
        task_id=record.task_id,
        source=source,
        attempt=attempt,
        seed=seed,
        prompt_sha256=record.prompt_sha256,
        completion_sha256=hashlib.sha256(completion.encode("utf-8")).hexdigest(),
        strict=Status.PASS,
        outcome=TRAINABLE,
        control=control,
    )


def build(texts: Sequence[TrainingText], *, denominator: int, unverified: int) -> Dataset:
    """Order the examples, digest them, and record what they were selected out of.

    The order is `(task_id, attempt)` and nothing else — never insertion order, which depends on
    the order tasks happened to be loaded in, and never a score, which there is none of. The
    determinism criterion is a statement about these bytes.
    """
    ordered = tuple(
        text.example
        for text in sorted(texts, key=lambda one: (one.example.task_id, one.example.attempt))
    )
    return Dataset(
        examples=ordered,
        digest=_digest(ordered),
        denominator=denominator,
        unverified=unverified,
    )


def split(texts: Sequence[TrainingText], *, run_seed: int) -> Split:
    """Hold back a validation slice, deterministically — or declare that there is none.

    The order is a digest over `(run_seed, task_id, attempt)` rather than `random.shuffle`. Both
    are deterministic given a seed; only one of them is deterministic given a *stdlib version*,
    and only one can be recomputed by a reader with `shasum` and the ledger.

    Below `VALID_FLOOR` examples there is **no valid split**, stated verbatim rather than
    silently skipped — see `NO_VALID_SPLIT`. Note which way the floor cuts: it is a floor on the
    *validation* count, so a tiny strict-PASS set trains without validation and says so, which is
    the honest outcome for a first night that may yield very little.
    """
    ordered = sorted(texts, key=lambda one: _shuffle_key(run_seed, one.example))
    wanted = int(len(ordered) * VALID_FRACTION)
    if wanted < VALID_FLOOR:
        return Split(train=tuple(ordered), valid=(), reason=NO_VALID_SPLIT)
    return Split(train=tuple(ordered[wanted:]), valid=tuple(ordered[:wanted]), reason="")


def write_local(directory: Path, chosen: Split) -> tuple[Path, ...]:
    """Write mlx-lm's local dataset format, and return the files written.

    A directory of JSON Lines in the `text` shape `mlx_lm.tuner.datasets.load_local_dataset`
    reads. `valid.jsonl` is written **only** when there is a validation split: an empty file would
    load as a validation set of nothing and a trainer would report a validation loss over it,
    which is a number with no observations behind it.
    """
    directory.mkdir(parents=True, exist_ok=True)
    written = [_write_lines(directory / TRAIN_FILE, chosen.train)]
    if chosen.valid:
        written.append(_write_lines(directory / VALID_FILE, chosen.valid))
    return tuple(written)


def document(dataset: Dataset) -> str:
    """The dataset's own record, as the exact bytes that get written and digested.

    Text rather than an object, for the reason `report.Report.payload` is text: the artefact is
    the bytes, and a caller that re-serialised an object could write something that differed from
    what was digested while both looked right.
    """
    return json.dumps(_payload(dataset), indent=2, sort_keys=True) + "\n"


def write_document(path: Path, dataset: Dataset) -> Path:
    """Write `document(dataset)` to `path`, creating its parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document(dataset), encoding="utf-8")
    return path


def read_document(path: Path) -> Mapping[str, object]:
    """Read a dataset document back, refusing anything not written to the declared schema."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != DATASET_SCHEMA:
        raise ValueError(
            f"{str(path)!r} does not declare schema {DATASET_SCHEMA!r}. Refused rather than "
            "parsed optimistically: every field a partial read would default is one that makes "
            "this document verify nothing and return successfully"
        )
    return raw


def _payload(dataset: Dataset) -> dict[str, object]:
    """The document's plain-JSON body. Written field by field, deliberately.

    `dataclasses.asdict` would carry a field added later into the file with no reader for it, so a
    schema change would round-trip lossily rather than failing. Naming every field means a new one
    breaks this function first — the `journal.py` codec rule.
    """
    return {
        "schema": DATASET_SCHEMA,
        "digest": dataset.digest,
        "denominator": dataset.denominator,
        "unverified": dataset.unverified,
        "coverage": dataset.coverage,
        "examples": [_example(one) for one in dataset.examples],
    }


def _example(one: Example) -> dict[str, object]:
    """One record, as plain JSON types. Hashes and verdicts; no prompt, no completion, no diff."""
    return {
        "task_id": one.task_id,
        "source": one.source,
        "attempt": one.attempt,
        "seed": one.seed,
        "prompt_sha256": one.prompt_sha256,
        "completion_sha256": one.completion_sha256,
        "strict": one.strict.value,
        "outcome": one.outcome.value,
        "control": one.control.value,
    }


def _digest(examples: Sequence[Example]) -> str:
    """sha256 over the ordered records, excluding the digest field itself.

    Over the records rather than over the training text, and that is the load-bearing choice: the
    text lives only under a gitignored root, and a digest an outside reader cannot recompute
    without it would be a provenance field nobody can check. These records are the committed-shaped
    half, so the value is checkable from the run's own document alone.
    """
    material = json.dumps([_example(one) for one in examples], indent=2, sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _shuffle_key(run_seed: int, example: Example) -> str:
    """A stable pseudo-random ordering key. Pure, stdlib, and recomputable from the ledger."""
    material = f"{run_seed}\n{example.task_id}\n{example.attempt}".encode()
    return hashlib.sha256(material).hexdigest()


def _write_lines(path: Path, texts: Sequence[TrainingText]) -> Path:
    """One JSON object per line, in the `text` shape, in the order given."""
    path.write_text(
        "".join(json.dumps({"text": one.text}, sort_keys=True) + "\n" for one in texts),
        encoding="utf-8",
    )
    return path


__all__ = [
    "DATASET_SCHEMA",
    "NOT_TRAINABLE",
    "NO_VALID_SPLIT",
    "TRAINABLE",
    "TRAIN_FILE",
    "VALID_FILE",
    "VALID_FLOOR",
    "VALID_FRACTION",
    "Dataset",
    "Example",
    "NotTrainable",
    "Split",
    "TrainingText",
    "build",
    "document",
    "example_of",
    "read_document",
    "split",
    "trainable",
    "write_document",
    "write_local",
]
