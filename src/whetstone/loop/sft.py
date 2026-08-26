"""LoRA-SFT on the verified rollouts, and the capacity probe that is allowed to stop it.

Training a 32B-class base on this machine is **unmeasured**. The larger-base arm's D7 probe settled
*inference* fit and nothing else (`docs/planning/larger-base-arm/finding.md`); training adds
optimizer state, adapters and gradients, and none of that has ever been observed here. So this
module does what every arm in this repository has done with an unmeasured cost: it declares the
probe **before** the run — a named number of steps and a stated headroom, both constants below —
runs it, and treats a probe that exceeds the headroom as a **published capacity finding** rather
than as a knob to turn.

**The fallback is pre-committed, here, before the probe ever ran.** `GRAD_CHECKPOINT` is on and
`GRAD_ACCUMULATION_STEPS` is above one from the first step, because deciding those *after* seeing
a probe's peak is choosing a training configuration while looking at the outcome it produces. If
the probe still exceeds headroom the night halts and says so. It never falls back to a smaller
base: the candidate is the one the larger-base arm produced evidence for, and swapping it for a
cheaper one after a memory failure would answer a different question than the one asked.

**Everything that decides what is trained is fixed at construction and recorded in provenance.**
That is `mlx_runtime.py`'s anti-tuning discipline (M7b) applied to training hyper-parameters:
batch size, iterations, sequence length, learning rate and LoRA depth are module constants, not
per-night arguments, because a per-night knob is what somebody turns until the checkpoint looks
better — and there is no held-out set yet against which "better" could even be checked.

**The checkpoint is hashed weights-style.** `weights.verify()` re-hashes every file a provenance
names before a token is generated, because a gitignored directory can be re-fetched, truncated or
hand-edited and every one of those produces a run citing bytes it never loaded. A checkpoint is a
gitignored directory with exactly those properties, and P3's promotion gate will compare two of
them, so it gets the same treatment: a `provenance.json` naming every file with its digest, and a
`verify_checkpoint` that re-reads them.

**Every `mlx` import is function-local**, so this module imports, type-checks and is fully tested
on a machine with no extra — the `mlx_runtime.py` rule. The training call itself is behind a
`Trainer` seam, the same inversion `run.Engine` makes, so the whole aspect is exercised with no
weights, no GPU and no network.
"""

from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.loop.dataset import NO_VALID_SPLIT

#: How many training steps the capacity probe runs. Declared before the probe, never after: a
#: step count chosen once a peak is known is a measurement designed around its own answer. Small
#: enough to cost minutes and large enough that the optimizer state, the gradients and at least
#: one accumulation cycle have all been allocated — which is where the peak actually lives.
CAPACITY_PROBE_ITERS = 8

#: The machine this project runs on, in bytes. Stated rather than probed, because the headroom
#: below is a fraction of a declared number and a fraction of a number read from the OS would
#: move between machines while reading as the same rule.
MACHINE_BYTES = 36 * 1024**3

#: The ceiling a probe must come in under. Not the whole machine: the run is also holding the
#: verifier's sandboxed subprocesses and the operating system, and a training step that fits with
#: nothing else running is a training step that swaps at three in the morning.
CAPACITY_HEADROOM_BYTES = int(0.85 * MACHINE_BYTES)

#: The adapter file `mlx_lm`'s LoRA trainer writes, and the name `mlx_lm`'s loader looks for.
ADAPTER_FILE = "adapters.safetensors"

#: The adapter configuration `mlx_lm` writes beside it.
ADAPTER_CONFIG = "adapter_config.json"

#: The checkpoint's own provenance document and its schema, in the `weights.py` shape.
CHECKPOINT_FILE = "provenance.json"
CHECKPOINT_SCHEMA = "whetstone-checkpoint/1"

#: How much is read per digest step, matching `weights._CHUNK`: bound by the disk rather than by
#: the loop, and never resident in the process that is about to hold a model.
_CHUNK = 1 << 20


class CapacityExceeded(RuntimeError):
    """The capacity probe measured a peak above the declared headroom. A finding, not a retry.

    Raised rather than worked around. The pre-committed fallback (gradient checkpointing and
    accumulation) is already on from the first step, so a probe that still exceeds headroom has
    exhausted what was decided in advance — and the alternative, editing a constant until it
    fits, is choosing a training configuration by looking at its own outcome.
    """


class CheckpointUnverified(ValueError):
    """The disk does not hold what the checkpoint's provenance says it holds.

    Raised, never returned as a flag, for `weights.WeightsUnverified`'s reason: a gate that
    compared a checkpoint it could not demonstrate it had read would publish a promotion decision
    about bytes nobody can identify.
    """


class NothingToTrain(ValueError):
    """A night selected no verified rollout, so there is nothing to train and no candidate.

    A named refusal rather than an empty checkpoint. `UNVERIFIED` is not a win and neither is an
    untrained adapter: a directory that exists and holds a randomly-initialised adapter would be
    indistinguishable, to P3's gate, from one that learned something.
    """


@dataclass(frozen=True)
class TrainingArgs:
    """Every hyper-parameter, fixed at construction and recorded. None of them is a night's knob.

    A frozen record rather than loose arguments, so the thing that is passed to the trainer is
    also the thing that is written into provenance — one object, so the two cannot disagree about
    what the night actually ran.
    """

    #: Examples per step. One, because the sequences are whole prompts plus whole diffs and the
    #: memory question is exactly how many of those fit at once.
    batch_size: int = 1

    #: Optimizer steps. The night's training length, declared.
    iters: int = 200

    #: Tokens per example; longer examples are truncated by the library.
    max_seq_length: int = 2048

    #: LoRA learning rate.
    learning_rate: float = 1e-5

    #: How many transformer layers get adapters.
    lora_layers: int = 8

    #: Recompute activations instead of storing them. **Pre-committed on**, see the module
    #: docstring: turning it on after a probe failed would be tuning against the probe.
    grad_checkpoint: bool = True

    #: Accumulate this many micro-batches before stepping, so the effective batch is larger than
    #: what has to be resident. Pre-committed for the same reason.
    grad_accumulation_steps: int = 4

    #: What the adapter is written as.
    adapter_file: str = ADAPTER_FILE

    def replace_iters(self, iters: int) -> TrainingArgs:
        """The same arguments at a different step count — the one thing the probe may vary.

        Explicit and narrow rather than a general `replace`: the probe runs *these* arguments for
        fewer steps, which is what makes its peak a measurement of the night's own configuration.
        A probe free to vary anything else would measure a configuration nothing runs.
        """
        return TrainingArgs(
            batch_size=self.batch_size,
            iters=iters,
            max_seq_length=self.max_seq_length,
            learning_rate=self.learning_rate,
            lora_layers=self.lora_layers,
            grad_checkpoint=self.grad_checkpoint,
            grad_accumulation_steps=self.grad_accumulation_steps,
            adapter_file=self.adapter_file,
        )

    def recorded(self) -> dict[str, Any]:
        """The arguments as plain JSON types, for the checkpoint's provenance."""
        return {
            "batch_size": self.batch_size,
            "iters": self.iters,
            "max_seq_length": self.max_seq_length,
            "learning_rate": self.learning_rate,
            "lora_layers": self.lora_layers,
            "grad_checkpoint": self.grad_checkpoint,
            "grad_accumulation_steps": self.grad_accumulation_steps,
            "adapter_file": self.adapter_file,
        }


@dataclass(frozen=True)
class TrainingRequest:
    """One training invocation, whole. What goes to the trainer and what goes into provenance."""

    #: The local directory holding the base weights. Never a repo id — see `sampling.py`.
    model_path: Path

    #: The immutable commit sha those weights were verified against.
    revision: str

    #: mlx-lm's local dataset directory (`train.jsonl`, and `valid.jsonl` when there is one).
    data: Path

    #: Where the adapter is written.
    adapters: Path

    #: The declared hyper-parameters.
    args: TrainingArgs


@dataclass(frozen=True)
class TrainingResult:
    """What one invocation cost. Never what it achieved — nothing here evaluates anything."""

    #: Peak resident bytes of this process during the invocation. The capacity question.
    peak_bytes: int

    #: Wall-clock seconds.
    seconds: float


#: How training happens. Injected for the reason `run.Engine` is: every test of this module runs
#: with no `mlx`, no weights and no GPU, and the *construction* of the request is what the
#: declared-arguments assertions are about.
Trainer = Callable[[TrainingRequest], TrainingResult]


@dataclass(frozen=True)
class CapacityProbe:
    """What the declared probe measured, and the declaration it was measured against.

    The declared values travel **with** the measurement rather than being looked up beside it. A
    record carrying only a peak could be read against whatever headroom the reader happened to
    find in the code that day, which is how a number measured under one declaration ends up
    quoted under another.
    """

    #: The declared step count this probe ran.
    iters: int

    #: The declared ceiling it was checked against.
    headroom_bytes: int

    #: What it actually peaked at.
    peak_bytes: int

    #: Seconds the probe took.
    seconds: float

    @property
    def fits(self) -> bool:
        """Whether the measured peak came in under the declared headroom."""
        return self.peak_bytes <= self.headroom_bytes

    def recorded(self) -> dict[str, Any]:
        """The probe as plain JSON types, declaration included."""
        return {
            "iters": self.iters,
            "headroom_bytes": self.headroom_bytes,
            "peak_bytes": self.peak_bytes,
            "seconds": round(self.seconds, 3),
            "fits": self.fits,
        }


@dataclass(frozen=True)
class CheckpointFile:
    """One file inside a checkpoint, as it was written."""

    #: The path relative to the checkpoint directory.
    name: str

    #: Its size in bytes when written.
    bytes: int

    #: Hex SHA-256 of its bytes.
    sha256: str


@dataclass(frozen=True)
class Checkpoint:
    """The night's candidate: an adapter, its configuration, and the provenance over both."""

    #: The directory under `checkpoints/`.
    directory: Path

    #: A digest over the file digests, in sorted order. The value the run ledger records, and the
    #: one P3's gate will name when it says which two checkpoints it compared.
    digest: str

    #: Every file, with its own digest.
    files: tuple[CheckpointFile, ...]

    #: True when this checkpoint is the untrained base rather than a night's adapter. Defaulted so
    #: the night's and gate's constructors are untouched; only `verify_checkpoint` populates it.
    untrained: bool = False


def probe_capacity(
    request: TrainingRequest,
    *,
    trainer: Trainer,
    iters: int = CAPACITY_PROBE_ITERS,
    headroom_bytes: int = CAPACITY_HEADROOM_BYTES,
) -> CapacityProbe:
    """Run the declared number of steps and record what it peaked at, against the declared ceiling.

    Runs the night's own arguments at a shorter step count (`TrainingArgs.replace_iters`), because
    a probe of some other configuration measures a configuration nothing runs. It does not raise
    on a peak above the ceiling — the record is the finding, and the caller decides what a
    finding means; `train` is the caller that refuses.
    """
    started = time.perf_counter()
    result = trainer(
        TrainingRequest(
            model_path=request.model_path,
            revision=request.revision,
            data=request.data,
            adapters=request.adapters,
            args=request.args.replace_iters(iters),
        )
    )
    return CapacityProbe(
        iters=iters,
        headroom_bytes=headroom_bytes,
        peak_bytes=result.peak_bytes,
        seconds=result.seconds if result.seconds else time.perf_counter() - started,
    )


def train(
    request: TrainingRequest,
    *,
    trainer: Trainer,
    capacity: CapacityProbe,
    examples: int,
) -> TrainingResult:
    """Train, but only behind a probe that fits and a dataset that exists.

    Two refusals, both before the first step. A night that selected nothing has no candidate to
    produce (`NothingToTrain`), and a probe above the declared headroom is a capacity finding
    (`CapacityExceeded`) rather than an invitation to shrink something — the fallback was
    pre-committed and is already on.
    """
    if examples < 1:
        raise NothingToTrain(
            "this night selected no strict-PASS rollout, so there is nothing to train on and no "
            "candidate to emit. An empty checkpoint would be indistinguishable, to the promotion "
            "gate, from one that learned something. The response to a low yield is to raise the "
            "number of draws, never to loosen what counts as a win"
        )
    if not capacity.fits:
        raise CapacityExceeded(
            f"the capacity probe peaked at {capacity.peak_bytes} bytes over {capacity.iters} "
            f"steps, above the declared headroom of {capacity.headroom_bytes}. That is a "
            "published capacity finding about this machine and this base, not a configuration to "
            "adjust: gradient checkpointing and gradient accumulation were pre-committed and are "
            "already on, so nothing decided in advance remains to try"
        )
    return trainer(request)


def mlx_trainer(request: TrainingRequest) -> TrainingResult:
    """`mlx_lm.lora.train` at the pinned version, with the declared arguments and nothing else.

    Every import is function-local, for the reason `mlx_runtime.py` gives. The dataset is loaded
    through the library's own local-directory loader rather than by handing it a list, so what
    trains is what `write_local` wrote — a second in-memory path would let the files and the
    training diverge with nothing comparing them.
    """
    from mlx.optimizers import Adam
    from mlx_lm.tuner.datasets import load_local_dataset
    from mlx_lm.tuner.trainer import TrainingArgs as MlxTrainingArgs
    from mlx_lm.tuner.trainer import train as lora_train
    from mlx_lm.tuner.utils import linear_to_lora_layers
    from mlx_lm.utils import load

    request.adapters.mkdir(parents=True, exist_ok=True)
    # Indexed and annotated `Any` rather than unpacked, for two reasons that pull the same way.
    # `load` is typed as returning either a two- or a three-tuple selected by a default argument
    # mypy cannot narrow (`mlx_runtime._load`), and `load_local_dataset` is annotated against a
    # tokenizer type narrower than the wrapper `load` actually returns. A `# type: ignore` would
    # be the obvious fix and is the wrong one: `warn_unused_ignores` is on and CI type-checks
    # BOTH with and without the extra, so an ignore that is required in one environment is an
    # error in the other.
    loaded = load(str(request.model_path), revision=request.revision)
    model: Any = loaded[0]
    tokenizer: Any = loaded[1]

    model.freeze()
    linear_to_lora_layers(model, request.args.lora_layers, {"rank": 8, "scale": 20.0})

    # `(train, valid, test)`; a subset whose file was never written comes back **empty**, and the
    # library's own loop reads `if val_dataset and ...`. So a night below the valid-split floor
    # wrote no `valid.jsonl`, gets an empty validation set here, and the trainer prints no
    # validation loss at all — which is the honest rendering of "no valid split". Pointing it at
    # the training set instead would print a number labelled `Val loss` that is not one.
    datasets = load_local_dataset(request.data, tokenizer, {})
    started = time.perf_counter()
    lora_train(
        model=model,
        optimizer=Adam(learning_rate=request.args.learning_rate),
        train_dataset=datasets[0],
        val_dataset=datasets[1],
        args=MlxTrainingArgs(
            batch_size=request.args.batch_size,
            iters=request.args.iters,
            max_seq_length=request.args.max_seq_length,
            adapter_file=str(request.adapters / request.args.adapter_file),
            grad_checkpoint=request.args.grad_checkpoint,
            grad_accumulation_steps=request.args.grad_accumulation_steps,
        ),
    )
    return TrainingResult(peak_bytes=peak_bytes(), seconds=time.perf_counter() - started)


def write_checkpoint(
    directory: Path,
    *,
    repo_id: str,
    revision: str,
    dataset_digest: str,
    run_seed: int,
    args: TrainingArgs,
    tool_versions: Mapping[str, str],
    valid_split: str,
    capacity: CapacityProbe,
) -> Checkpoint:
    """Record what produced this adapter, hash every file beside it, and return the checkpoint.

    Called **after** the trainer has written the adapter, never before: a provenance naming files
    that do not exist yet is a document that verifies successfully against nothing.

    `valid_split` is written verbatim. When it is `dataset.NO_VALID_SPLIT` the checkpoint states,
    in its own provenance, that it was trained without validation — which is the whole point of
    the degenerate rule. A checkpoint silent on the question reads exactly like a validated one.
    """
    files = _hash_directory(directory)
    if not files:
        raise CheckpointUnverified(
            f"{str(directory)!r} holds no files to record, so this provenance would verify "
            "nothing and succeed — which reads in a review exactly like a check that passed"
        )
    digest = _digest_of(files)
    (directory / CHECKPOINT_FILE).write_text(
        json.dumps(
            {
                "schema": CHECKPOINT_SCHEMA,
                "digest": digest,
                "base": {"repo_id": repo_id, "revision": revision},
                "dataset_digest": dataset_digest,
                "run_seed": run_seed,
                "training_args": args.recorded(),
                "tool_versions": dict(sorted(tool_versions.items())),
                "validation": valid_split or "validated against the run's own valid split",
                "capacity_probe": capacity.recorded(),
                "files": [
                    {"name": one.name, "bytes": one.bytes, "sha256": one.sha256} for one in files
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return Checkpoint(directory=directory, digest=digest, files=files)


def verify_checkpoint(directory: Path) -> Checkpoint:
    """Re-hash every file the checkpoint's provenance names, or refuse naming the first that moved.

    The `weights.verify` argument, applied to the artefact P3 will compare: a recorded digest
    nobody re-reads renders in a review exactly like a checked one, and a gitignored directory can
    be rebuilt, truncated or hand-edited between the night that wrote it and the gate that reads
    it.
    """
    document = directory / CHECKPOINT_FILE
    if not document.is_file():
        raise CheckpointUnverified(
            f"no {CHECKPOINT_FILE} at {str(document)!r}, so there is no record of what this "
            "checkpoint is. An adapter with no provenance names no base, no dataset and no seed"
        )
    try:
        raw: Any = json.loads(document.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CheckpointUnverified(f"{str(document)!r} could not be read: {error}") from error
    if not isinstance(raw, dict) or raw.get("schema") != CHECKPOINT_SCHEMA:
        raise CheckpointUnverified(
            f"{str(document)!r} does not declare schema {CHECKPOINT_SCHEMA!r}"
        )

    recorded = tuple(
        CheckpointFile(name=str(one["name"]), bytes=int(one["bytes"]), sha256=str(one["sha256"]))
        for one in raw["files"]
    )
    untrained = raw.get("untrained") is True
    if not recorded and not untrained:
        raise CheckpointUnverified(
            f"{str(document)!r} records no files, so verifying it checks nothing and succeeds"
        )
    if untrained and recorded:
        raise CheckpointUnverified(
            f"{str(document)!r} declares untrained: true and records {len(recorded)} files — "
            "the label and the bytes disagree"
        )
    for one in recorded:
        path = directory / one.name
        if not path.is_file():
            raise CheckpointUnverified(
                f"{str(path)!r} is recorded in {CHECKPOINT_FILE} and is not on this disk"
            )
        size = path.stat().st_size
        if size != one.bytes:
            raise CheckpointUnverified(
                f"{str(path)!r} is {size} bytes and {CHECKPOINT_FILE} records {one.bytes}"
            )
        seen = _digest(path)
        if seen != one.sha256:
            raise CheckpointUnverified(
                f"{str(path)!r} has sha256 {seen} and {CHECKPOINT_FILE} records {one.sha256}. "
                "The bytes in this checkpoint are not the bytes the night wrote"
            )
    digest = _digest_of(recorded)
    if digest != raw["digest"]:
        raise CheckpointUnverified(
            f"{str(document)!r} records digest {raw['digest']!r} and its own file digests reduce "
            f"to {digest!r}. The document disagrees with itself, which a hand edit produces and a "
            "night does not"
        )
    return Checkpoint(directory=directory, digest=digest, files=recorded, untrained=untrained)


def peak_bytes() -> int:
    """Peak resident bytes of this process, in bytes on every platform this runs on.

    `ru_maxrss` is bytes on Darwin and kibibytes on Linux — the kind of difference that produces a
    capacity finding off by a factor of 1024. Taken from the same reading `run._peak_bytes` uses,
    restated here rather than imported because the driver's copy is private to a module this one
    must not depend on for a two-line arithmetic fact.
    """
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def _hash_directory(directory: Path) -> tuple[CheckpointFile, ...]:
    """Every file under `directory` except the provenance itself, with its digest, sorted by name.

    The provenance is excluded because it holds the digests: including it would make the document
    hash itself, and no writer can produce a fixed point of that.
    """
    return tuple(
        CheckpointFile(
            name=str(path.relative_to(directory)),
            bytes=path.stat().st_size,
            sha256=_digest(path),
        )
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != CHECKPOINT_FILE
    )


def _digest_of(files: Sequence[CheckpointFile]) -> str:
    """One digest over the file digests, in sorted name order."""
    material = "\n".join(f"{one.name}:{one.sha256}" for one in sorted(files, key=lambda x: x.name))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _digest(path: Path) -> str:
    """Hex SHA-256 of `path`, read in chunks so a large adapter is never resident."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "ADAPTER_CONFIG",
    "ADAPTER_FILE",
    "CAPACITY_HEADROOM_BYTES",
    "CAPACITY_PROBE_ITERS",
    "CHECKPOINT_FILE",
    "CHECKPOINT_SCHEMA",
    "MACHINE_BYTES",
    "NO_VALID_SPLIT",
    "CapacityExceeded",
    "CapacityProbe",
    "Checkpoint",
    "CheckpointFile",
    "CheckpointUnverified",
    "NothingToTrain",
    "Trainer",
    "TrainingArgs",
    "TrainingRequest",
    "TrainingResult",
    "mlx_trainer",
    "peak_bytes",
    "probe_capacity",
    "train",
    "verify_checkpoint",
    "write_checkpoint",
]
