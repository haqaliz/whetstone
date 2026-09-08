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

from whetstone.loop.backend import MLX, TORCH
from whetstone.loop.backend import Backend as BackendRecord
from whetstone.loop.backend import family as backend_family
from whetstone.loop.dataset import NO_VALID_SPLIT

#: How many training steps the capacity probe runs. Declared before the probe, never after: a
#: step count chosen once a peak is known is a measurement designed around its own answer. Small
#: enough to cost minutes and large enough that the optimizer state, the gradients and at least
#: one accumulation cycle have all been allocated — which is where the peak actually lives.
CAPACITY_PROBE_ITERS = 8

#: The machine this project was first written on, in bytes. Kept as the **declared default only**
#: — see `headroom_for`, which is what a run that knows its own machine should use.
MACHINE_BYTES = 36 * 1024**3

#: The fraction of a machine's memory a probe must come in under. Not the whole machine: the run
#: is also holding the verifier's sandboxed subprocesses and the operating system, and a training
#: step that fits with nothing else running is a training step that swaps at three in the morning.
#: This fraction is the part that was ever a decision; the machine it applies to is a fact to be
#: read off the machine, not declared here.
HEADROOM_FRACTION = 0.85

#: The ceiling on the declared machine. A default, and increasingly a fallback: on any host whose
#: backend record names its memory, `headroom_for` supersedes it.
CAPACITY_HEADROOM_BYTES = int(HEADROOM_FRACTION * MACHINE_BYTES)

#: The longest a night's training may be projected to take. A night that trains past a full day
#: is no longer the thing this product claims to be — "train overnight" is the frame, and a run
#: still going when the next night starts cannot be part of a nightly loop. Declared here, ahead
#: of any projection, so it can never be a number chosen once a run's duration was known.
TRAINING_WALLCLOCK_CEILING_SECONDS = 24 * 60 * 60

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


class TrainingTooLong(RuntimeError):
    """The probe's measured rate projects a run past the declared wall-clock ceiling.

    This is the honest form of a refusal that used to be spelled as a fact about the device:
    `backend` once refused every non-CUDA Torch host on the grounds that a 32B base "does not
    finish there in any useful time". The worry was real and the test was wrong — it refused by
    asking *which chip*, when the thing feared was *how long*, and it consequently also refused
    the small-base portability arm, which finishes 200 steps on a CPU in about six hours.

    Measured rather than assumed, which is this repository's whole idiom: the capacity probe
    already runs the night's own arguments and times them, so the projection is an observation of
    this base on this machine, not a rule of thumb about a class of hardware.
    """


class UnknownMachine(RuntimeError):
    """The running machine's memory is unknown, so no ceiling can be derived for it.

    Raised rather than defaulted to `CAPACITY_HEADROOM_BYTES`, because that silent fallback is
    precisely the defect this exists to close. The portability arm's probe ran on a 15.5 GiB
    Linux box and was checked against 30.6 GiB — 0.85 x the author's 36 GiB Mac, compiled in — so
    the ceiling was nearly twice the machine's total RAM. That probe passed on luck: its measured
    peak was 6.84 GiB. A guard that would have approved a run twice the size of the machine is
    not a guard, and one that quietly substitutes another machine's number cannot be told from
    one that checked.
    """


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

    #: The adapter's inner dimension. Was a literal at the call site, which put a value that
    #: decides what the adapter *is* outside the record of what trained it.
    lora_rank: int = 8

    #: How hard the adapter's output is scaled into the frozen layer.
    lora_scale: float = 20.0

    #: Adapter dropout. Zero, and stated: the pinned library reads this key unconditionally, so
    #: an omitted default is a `KeyError` at the first training step rather than a library
    #: default. Night #1 died on exactly that, after every rollout had been generated.
    lora_dropout: float = 0.0

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
            lora_rank=self.lora_rank,
            lora_scale=self.lora_scale,
            lora_dropout=self.lora_dropout,
            grad_checkpoint=self.grad_checkpoint,
            grad_accumulation_steps=self.grad_accumulation_steps,
            adapter_file=self.adapter_file,
        )

    def lora_config(self) -> dict[str, Any]:
        """The adapter's shape, in the mapping `mlx_lm.tuner.utils.linear_to_lora_layers` reads.

        Built from the recorded fields rather than written as a literal beside the call. The
        literal it replaces (`{"rank": 8, "scale": 20.0}`) was wrong in both directions at once:
        it omitted `dropout`, which the pinned library subscripts unconditionally, and it kept
        rank and scale out of `recorded()` — so a checkpoint's provenance named every training
        hyper-parameter except the two that decide what the adapter is.
        """
        return {"rank": self.lora_rank, "scale": self.lora_scale, "dropout": self.lora_dropout}

    def recorded(self) -> dict[str, Any]:
        """The arguments as plain JSON types, for the checkpoint's provenance."""
        return {
            "batch_size": self.batch_size,
            "iters": self.iters,
            "max_seq_length": self.max_seq_length,
            "learning_rate": self.learning_rate,
            "lora_layers": self.lora_layers,
            "lora_rank": self.lora_rank,
            "lora_scale": self.lora_scale,
            "lora_dropout": self.lora_dropout,
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

    #: The runtime that trained this adapter, read back from its own provenance. `None` for an
    #: untrained base (nothing trained it) and for a checkpoint written before the field existed
    #: — in both cases an absence, which the gate treats as unknown rather than as a mismatch.
    #: Defaulted for the same reason `untrained` is; only `verify_checkpoint` populates it.
    backend: Mapping[str, Any] | None = None


def projected_seconds(capacity: CapacityProbe, *, iters: int) -> float:
    """How long the full run takes at the rate the probe measured.

    Linear in the step count, deliberately, and it will read a little high: the probe pays the
    model load and the first compile inside its handful of steps and the full run amortises them.
    Erring long is the right direction for a refusal — the failure it prevents is a run that is
    still going at noon.
    """
    if capacity.iters < 1:
        raise ValueError(
            f"the probe records {capacity.iters} steps, so it measured no rate and nothing can "
            "be projected from it"
        )
    return capacity.seconds / capacity.iters * iters


def headroom_for(device_memory_bytes: int) -> int:
    """The ceiling for *this* machine: the declared fraction of the memory it actually has.

    The fraction is the decision and stays declared; the machine is a fact and is read off the
    backend record, which `describe` fills from the device itself. Splitting them this way is
    what makes the same rule mean the same thing on a 15.5 GiB Linux box and a 36 GiB Mac,
    instead of meaning "0.85 x whatever machine the author had".
    """
    if device_memory_bytes <= 0:
        raise UnknownMachine(
            "the backend record names no device memory, so the fraction "
            f"{HEADROOM_FRACTION} has nothing to be a fraction *of*. Refused rather than falling "
            f"back to the declared {CAPACITY_HEADROOM_BYTES} bytes: that fallback is how a probe "
            "on a 15.5 GiB machine came to be checked against a 30.6 GiB ceiling and pass"
        )
    return int(HEADROOM_FRACTION * device_memory_bytes)


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
    projected = projected_seconds(capacity, iters=request.args.iters)
    if projected > TRAINING_WALLCLOCK_CEILING_SECONDS:
        raise TrainingTooLong(
            f"the capacity probe took {capacity.seconds:.1f}s over {capacity.iters} steps, which "
            f"projects {projected / 3600:.1f} hours for the night's {request.args.iters} — past "
            f"the declared ceiling of {TRAINING_WALLCLOCK_CEILING_SECONDS / 3600:.0f} hours. "
            "Refused before the first step rather than discovered at noon: a run still training "
            "when the next night starts is not a nightly loop. This is a finding about this base "
            "on this machine, so the responses are a smaller base or a faster machine — never a "
            "larger ceiling, which would be a threshold chosen from the run it has to judge"
        )
    return trainer(request)


def training_datasets(data: Path, tokenizer: Any) -> tuple[Any, Any]:
    """The night's train and validation sets, wrapped the way the library's trainer indexes them.

    `load_local_dataset` returns bare `TextDataset`s whose `__getitem__` hands back the raw
    record, while `iterate_batches` sorts by `len(dataset[idx][0])` — so an unwrapped set raises
    `KeyError: 0` on the first batch. `CacheDataset` is what applies `process()` and turns each
    record into the `(tokens, offset)` pair the trainer indexes, which is why `mlx_lm/lora.py`
    wraps both sets before calling `train`. Composing the library's parts by hand means composing
    that wrapper too; night #1 is what leaving it out costs.

    Extracted from `mlx_trainer` so the shape can be asserted without weights or a GPU. The
    trainer itself cannot be — it needs 18 GiB and an engine — so the seam is drawn exactly where
    the untestable part begins.

    `(train, valid, test)`; a subset whose file was never written comes back **empty**, and the
    library's own loop reads `if val_dataset and ...`. So a night below the valid-split floor
    wrote no `valid.jsonl`, gets an empty validation set here, and the trainer prints no
    validation loss at all — which is the honest rendering of "no valid split". Pointing it at
    the training set instead would print a number labelled `Val loss` that is not one.
    """
    from mlx_lm.tuner.datasets import CacheDataset, load_local_dataset

    datasets = load_local_dataset(data, tokenizer, {})
    return CacheDataset(datasets[0]), CacheDataset(datasets[1])


def mlx_trainer(request: TrainingRequest) -> TrainingResult:
    """`mlx_lm.lora.train` at the pinned version, with the declared arguments and nothing else.

    Every import is function-local, for the reason `mlx_runtime.py` gives. The dataset is loaded
    through the library's own local-directory loader rather than by handing it a list, so what
    trains is what `write_local` wrote — a second in-memory path would let the files and the
    training diverge with nothing comparing them.
    """
    import mlx.core as mx
    from mlx.optimizers import Adam
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
    linear_to_lora_layers(model, request.args.lora_layers, request.args.lora_config())

    train_dataset, val_dataset = training_datasets(request.data, tokenizer)
    # Reset before the step so the peak read afterwards belongs to THIS training run and not to
    # whatever the process allocated loading the weights in a previous one.
    mx.reset_peak_memory()
    started = time.perf_counter()
    lora_train(
        model=model,
        optimizer=Adam(learning_rate=request.args.learning_rate),
        train_dataset=train_dataset,
        val_dataset=val_dataset,
        args=MlxTrainingArgs(
            batch_size=request.args.batch_size,
            iters=request.args.iters,
            max_seq_length=request.args.max_seq_length,
            adapter_file=str(request.adapters / request.args.adapter_file),
            grad_checkpoint=request.args.grad_checkpoint,
            grad_accumulation_steps=request.args.grad_accumulation_steps,
        ),
    )
    return TrainingResult(
        peak_bytes=training_peak_bytes(mlx_peak=int(mx.get_peak_memory()), resident=peak_bytes()),
        seconds=time.perf_counter() - started,
    )


def adapter_config(args: TrainingArgs, *, repo_id: str, backend_name: str) -> dict[str, Any]:
    """The adapter's own configuration, in the vocabulary of the runtime that trained it.

    Night #1's checkpoint directory held one file — `adapters.safetensors` — and nothing else.
    `mlx_lm.tuner.utils.load_adapters` opens `adapter_config.json` unguarded (`utils.py:127`) and
    `gate.py` hands it a checkpoint directory, so the promotion gate raised `FileNotFoundError`
    on the first real candidate it was given. The never-regress mechanism could not load anything
    this project produced. The suite did not catch it because the gate's fixtures hand-write the
    file production never wrote. That is why this function exists.

    **It used to write both vocabularies into one file, and that was wrong (#31.)** The reasoning
    was that MLX and PEFT read disjoint keys from the same filename, so one document could serve
    both readers — an adapter the whole ecosystem could open rather than one only this repository
    could. The key sets really are disjoint. The conclusion still did not follow, because the
    config is not the only thing that differs, and every one of the others is independently fatal:

    | | MLX | PEFT |
    |---|---|---|
    | weights filename | `adapters.safetensors` | `adapter_model.safetensors` |
    | tensor key | `…q_proj.lora_a` | `base_model.model.…q_proj.lora_A.weight` |
    | shape of A | `(in, r)` — `(896, 8)` | `(r, in)` — `(8, 896)` |

    All three measured, not inferred: the filename by reading `load_adapters`, the PEFT names and
    shapes off this project's own checkpoint, the MLX ones by building a `LoRALinear` and
    flattening its parameters. So **neither loader could ever read the other's checkpoint**, both
    vocabularies present or not. The merged document bought nothing and cost a real thing: PEFT
    warns `Unexpected keyword arguments ['fine_tune_type', 'lora_parameters', 'num_layers']` and
    tells the reader to upgrade PEFT — advice that is wrong, for a problem that does not exist,
    on the first artifact a stranger loads.

    **The cross-runtime bridge is `fuse`, and it always was.** A fused model is a plain
    `Qwen2ForCausalLM` any runtime loads; the adapter is trainer-specific by construction. Making
    the config bilingual was an attempt to solve at the config layer a problem that lives in the
    tensors.

    **The alpha is derived, not guessed.** `mlx_lm/tuner/lora.py:98` applies
    `y + scale * (x @ lora_a @ lora_b)`; PEFT applies `y + (lora_alpha / r) * (x @ A @ B)`. So
    the equivalent alpha is `scale * r`. Published at any other value it is a different adapter
    from the one that trained.

    `target_modules` is deliberately absent from what this writer produces. MLX decides which
    modules get adapters from the model at load time (`linear_to_lora_layers` computes its own
    keys), so this writer cannot know them without the weights. PEFT's own `save_pretrained` does
    know them, and `write_checkpoint` merges over what the trainer already wrote rather than
    clobbering it, which is how a Torch adapter keeps them.
    """
    if backend_family(backend_name) == MLX:
        # What `mlx_lm.tuner.utils.load_adapters` dereferences, and nothing else.
        return {
            "fine_tune_type": "lora",
            "num_layers": args.lora_layers,
            "lora_parameters": args.lora_config(),
        }
    # What PEFT reads (https://huggingface.co/docs/peft/developer_guides/checkpoint).
    return {
        "peft_type": "LORA",
        "task_type": "CAUSAL_LM",
        "base_model_name_or_path": repo_id,
        "r": args.lora_rank,
        "lora_alpha": args.lora_scale * args.lora_rank,
        "lora_dropout": args.lora_dropout,
    }


#: What each runtime's `adapter_config.json` vocabulary consists of — the keys this writer owns
#: for that runtime, and therefore the keys it removes when sealing a checkpoint for the other.
#: Derived from the two loaders: MLX's from `mlx_lm.tuner.utils.load_adapters`, PEFT's from
#: `LoraConfig`'s accepted fields. `target_modules` is in neither, deliberately — the trainer owns
#: it and this writer never touches it.
_VOCABULARY: dict[str, frozenset[str]] = {
    MLX: frozenset({"fine_tune_type", "num_layers", "lora_parameters"}),
    TORCH: frozenset(
        {"peft_type", "task_type", "base_model_name_or_path", "r", "lora_alpha", "lora_dropout"}
    ),
}

_OTHER_VOCABULARY: dict[str, frozenset[str]] = {
    MLX: _VOCABULARY[TORCH],
    TORCH: _VOCABULARY[MLX],
}


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
    backend: BackendRecord,
) -> Checkpoint:
    """Record what produced this adapter, hash every file beside it, and return the checkpoint.

    Called **after** the trainer has written the adapter, never before: a provenance naming files
    that do not exist yet is a document that verifies successfully against nothing.

    `valid_split` is written verbatim. When it is `dataset.NO_VALID_SPLIT` the checkpoint states,
    in its own provenance, that it was trained without validation — which is the whole point of
    the degenerate rule. A checkpoint silent on the question reads exactly like a validated one.
    """
    # The refusal comes FIRST, before this function writes anything of its own. Writing the
    # adapter config up here instead would defeat the check outright: the directory would never
    # be empty, and a checkpoint holding no adapter at all would seal successfully. The suite
    # caught exactly that regression.
    if not _hash_directory(directory):
        raise CheckpointUnverified(
            f"{str(directory)!r} holds no files to record, so this provenance would verify "
            "nothing and succeed — which reads in a review exactly like a check that passed"
        )

    # Written BEFORE the digest, deliberately. Rank, scale and dropout are the difference
    # between two adapters, so a config outside the digest could be edited afterwards and the
    # checkpoint would still verify — the gate would re-hash successfully and then build a
    # different adapter from the one the night trained. The directory is re-hashed rather than
    # the first result reused, so the config is inside the digest that seals it.
    # MERGED over whatever the trainer already wrote, never overwritten. PEFT's
    # `save_pretrained` writes its own `adapter_config.json` carrying `target_modules` — which
    # modules actually got adapters — and that is knowledge only the trainer has: it resolves
    # them from the model's architecture, and `adapter_config` deliberately does not know them,
    # because knowing them would be knowing something about the base (§ 10.11). Clobbering would
    # strip that from every Torch-trained adapter and leave PEFT unable to rebuild it, so the
    # checkpoint would load under MLX and not under the runtime that produced it.
    #
    # The writer still wins on the keys it owns: the LoRA shape recorded here is the one from
    # `TrainingArgs`, because that is what the provenance publishes, and two sources for one
    # value is how a checkpoint comes to disagree with its own arguments.
    document: dict[str, Any] = {}
    existing = directory / ADAPTER_CONFIG
    if existing.is_file():
        try:
            written = json.loads(existing.read_text(encoding="utf-8"))
        except ValueError as error:
            raise CheckpointUnverified(
                f"{str(existing)!r} is not readable JSON ({error}), so what the trainer recorded "
                "about this adapter cannot be preserved. Refused rather than overwritten: the "
                "file names which modules were adapted, and replacing it would silently discard "
                "the only record of that"
            ) from error
        if isinstance(written, dict):
            document.update(written)
    ours = adapter_config(args, repo_id=repo_id, backend_name=backend.name)
    # The OTHER runtime's keys are stripped before ours are applied. A directory can already hold
    # a config written under the merged-vocabulary scheme this replaced (#31), or by a previous
    # night under a different backend; merging those forward would leave a Torch adapter still
    # carrying `num_layers` and still drawing PEFT's "upgrade the library" warning, which is the
    # whole thing that change removed. Only the keys this writer would have owned under the other
    # vocabulary are removed — anything the trainer knows and we do not, `target_modules` above
    # all, is untouched.
    for stale in _OTHER_VOCABULARY[backend_family(backend.name)]:
        document.pop(stale, None)
    document.update(ours)
    existing.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    files = _hash_directory(directory)
    digest = _digest_of(files)
    (directory / CHECKPOINT_FILE).write_text(
        json.dumps(
            {
                "schema": CHECKPOINT_SCHEMA,
                "digest": digest,
                "base": {"repo_id": repo_id, "revision": revision},
                "dataset_digest": dataset_digest,
                "run_seed": run_seed,
                # The runtime that produced this adapter. The gate loads two checkpoints and
                # scores one against the other; two from different backends differ by the
                # backend before they differ by anything the night did, so the provenance —
                # the only document that travels with the adapter — has to carry it.
                "backend": backend.recorded(),
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


def write_baseline_checkpoint(
    directory: Path,
    *,
    repo_id: str,
    revision: str,
    tool_versions: Mapping[str, str],
) -> Checkpoint:
    """Materialize the untrained open base as a checkpoint: a provenance over no adapter.

    The opposite sign of `write_checkpoint`'s empty-directory refusal. There, a directory with
    nothing to record would verify nothing and succeed; here, a directory that **already holds**
    files would record an adapter beside a base that never trained — the contradiction the
    `untrained` flag exists to exclude. No training-derived fields: this checkpoint never
    trained, so there is no dataset, seed, argument set, validation or capacity probe to record.
    """
    if _hash_directory(directory):
        raise CheckpointUnverified(
            f"{str(directory)!r} holds files, so a provenance declaring untrained: true would "
            "record an adapter beside a base that never trained — the contradiction the flag "
            "exists to exclude"
        )
    digest = _digest_of(())
    directory.mkdir(parents=True, exist_ok=True)
    (directory / CHECKPOINT_FILE).write_text(
        json.dumps(
            {
                "schema": CHECKPOINT_SCHEMA,
                "digest": digest,
                "base": {"repo_id": repo_id, "revision": revision},
                "untrained": True,
                "tool_versions": dict(sorted(tool_versions.items())),
                "files": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return Checkpoint(directory=directory, digest=digest, files=(), untrained=True)


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
    trained_by = raw.get("backend")
    recorded_backend = trained_by if isinstance(trained_by, dict) else None
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
    return Checkpoint(
        directory=directory,
        digest=digest,
        files=recorded,
        untrained=untrained,
        backend=recorded_backend,
    )


def training_peak_bytes(*, mlx_peak: int, resident: int) -> int:
    """The memory a training step actually held: the larger of the allocator's peak and RSS.

    `peak_bytes()` alone was the defect. It reads `ru_maxrss` — *resident* bytes — and MLX
    allocates through Metal, where the buffers are largely invisible to RSS. On the first real
    run of the fixed trainer `mlx_lm` reported a 22.994 GB peak while `peak_bytes()` returned
    8.83 GiB: the capacity guard was under-measuring the quantity it exists to bound by 2.6x, and
    writing that number into a checkpoint's provenance as a capacity finding.

    It answered `fits` correctly anyway, which is why nothing surfaced it — the guard was wrong
    and the decision was right. A wider adapter or a longer sequence would have had it answer
    `fits` on the way into swap.

    **An instrument correction, not a tuned threshold.** `CAPACITY_HEADROOM_BYTES` and
    `CAPACITY_PROBE_ITERS` are untouched and still declared before any run; only the quantity
    compared against them changes, to the one that was always meant.

    `max` rather than a sum: on unified memory both readings draw from the same pool, so adding
    them double-counts whatever part of the Metal buffers is also resident. The weights are
    themselves MLX arrays, so the allocator's peak dominates in practice.
    """
    return max(mlx_peak, resident)


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
    "HEADROOM_FRACTION",
    "MACHINE_BYTES",
    "NO_VALID_SPLIT",
    "TRAINING_WALLCLOCK_CEILING_SECONDS",
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
    "TrainingTooLong",
    "UnknownMachine",
    "headroom_for",
    "mlx_trainer",
    "peak_bytes",
    "probe_capacity",
    "projected_seconds",
    "train",
    "verify_checkpoint",
    "write_baseline_checkpoint",
    "write_checkpoint",
]
