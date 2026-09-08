"""LoRA-SFT on Torch, so the loop is not Apple Silicon's alone.

`sft.Trainer` has always been a seam — a plain callable `run_night` accepts — so a second
implementation is additive code rather than a branch inside the loop. What it must not be is a
second *contract*: a night trained here and a night trained under MLX produce the same shaped
artefact, are recorded the same way, and are refused against each other by the gate
(`MismatchedBackend`). Two runtimes that were interchangeable in the loop but not comparable in
the gate would be the worst of both.

**The base is an input and its size is not this module's business.**
`PREREGISTRATION.md` § 10.11 opens the portability arm at the smallest base that trains on the
hardware to hand and commits it to growing from there, so it requires the trainer, the adapter
format and the gate to be indifferent to base size — scaling up is an amendment, never a
rewrite. Nothing here names a model, a parameter count or a quantisation, and a guard reads this
module's own source to keep it that way. The base arrives as `request.model_path` and its
identity is the caller's problem, exactly as it is under MLX.

**The device is probed and stated, never assumed.** The shape `sandbox.confinement()` uses, for
the same reason: a CPU fallback nobody chose is how a large training run silently becomes a job
that never finishes while looking like it is working. What was found is returned so the
checkpoint's provenance can record it beside the peak the capacity probe measured.

**Every engine import is function-local**, the `sft.py` rule. This module imports, type-checks
and is tested on a machine with neither Torch nor MLX installed — the reward path must not
acquire an inference stack by importing something near it.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from whetstone.bakeoff.mlx_runtime import (
    DEFAULT_MAX_TOKENS,
    MODEL_CONFIG,
    NotALocalModelDirectory,
)
from whetstone.loop.sampling import TEMPERATURE, TOP_P
from whetstone.loop.sft import TrainingArgs, TrainingRequest, TrainingResult, training_peak_bytes

#: The devices this runtime will train on, in the order it prefers them. A **declaration**: the
#: order is a decision somebody makes deliberately, not a consequence of whichever accelerator a
#: library happens to enumerate first. `cpu` is last and is never removed — a host with no
#: accelerator is exactly where the portability arm was designed to run.
DEVICE_ORDER: tuple[str, ...] = ("cuda", "mps", "cpu")

#: What each device trains in, stated beside the device that causes it. A CPU run in fp16 is
#: arithmetic that silently produces nothing useful; a CUDA run in fp32 spends memory the
#: capacity probe exists to bound. Both are decisions, so both are written down.
DEVICE_PRECISION: dict[str, str] = {
    "cuda": "bfloat16",
    "mps": "float16",
    "cpu": "float32",
}

#: The adapter PEFT writes, and the name its loader looks for. Distinct from MLX's
#: `adapters.safetensors`: the two runtimes hardcode different filenames, and a checkpoint that
#: means to be loadable by both carries both.
PEFT_ADAPTER_FILE = "adapter_model.safetensors"


class NoTorchDevice(RuntimeError):
    """Torch is installed and reports no device this runtime is willing to train on.

    Raised rather than defaulted, `sandbox.UnsupportedPlatform`'s reason: a run that started
    anyway on a device nobody chose looks like progress for as long as it takes somebody to
    notice.
    """


def torch_device() -> str:
    """The device this host trains on, probed in the declared order and named.

    Function-local import for the module rule. The probe asks Torch what it *has* rather than
    what it was built for: a CUDA build on a machine with no visible GPU reports no device, and
    training on the CPU because a wheel had CUDA compiled in is the silent fallback this refuses.
    """
    import torch

    for name in DEVICE_ORDER:
        if name == "cuda" and torch.cuda.is_available():
            return name
        if name == "mps" and torch.backends.mps.is_available():
            return name
        if name == "cpu":
            return name
    raise NoTorchDevice(
        f"none of the declared devices {DEVICE_ORDER} is available, which should be impossible "
        "while `cpu` is last. Raising rather than choosing one: a device nobody declared is a "
        "training run nobody can reproduce"
    )


def peft_lora_config(args: TrainingArgs) -> dict[str, Any]:
    """`TrainingArgs` in PEFT's vocabulary. Derived, never a second copy.

    `TrainingArgs` is the one record of what decides training and it is written into every
    checkpoint's provenance, so a second copy here would drift and the provenance would then
    describe the configuration that did not run.

    The alpha is a conversion, not a preference. MLX applies `scale * (x @ A @ B)`
    (`mlx_lm/tuner/lora.py:98`); PEFT applies `(lora_alpha / r) * (x @ A @ B)`. So the equivalent
    alpha is `scale * r` — the same value `sft.adapter_config` already publishes, derived the
    same way, so an adapter and its own recorded arguments cannot disagree.

    `target_modules` is left to PEFT. It resolves them from the model's architecture, which is
    the only place that knowledge lives; naming them here would be this module knowing something
    about the base, which is the thing § 10.11 forbids it to know.
    """
    return {
        "task_type": "CAUSAL_LM",
        "r": args.lora_rank,
        "lora_alpha": args.lora_scale * args.lora_rank,
        "lora_dropout": args.lora_dropout,
        "bias": "none",
    }


def torch_trainer(request: TrainingRequest) -> TrainingResult:
    """Train a LoRA adapter with PEFT and write it where the checkpoint writer expects it.

    The `sft.Trainer` signature exactly, so `run_night(trainer=torch_trainer)` needs no branch
    inside the loop. Every import is function-local.

    The dataset is the same `train.jsonl` the MLX path reads — one `{"text": ...}` record per
    line — so the two runtimes train on identical bytes and a difference between their adapters
    is a difference between the runtimes rather than between their inputs.
    """
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

    device = torch_device()
    dtype = getattr(torch, DEVICE_PRECISION[device])

    tokenizer = AutoTokenizer.from_pretrained(str(request.model_path), revision=request.revision)
    if tokenizer.pad_token is None:
        # Causal models frequently ship without one, and the collator needs *a* pad id. Reusing
        # EOS is the standard choice and is stated rather than silently defaulted, because the
        # padding token changes what the loss is computed over.
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        str(request.model_path), revision=request.revision, dtype=dtype
    )
    model = get_peft_model(model, LoraConfig(**peft_lora_config(request.args)))

    def tokenise(batch: dict[str, list[str]]) -> Any:
        encoded = tokenizer(
            batch["text"],
            truncation=True,
            max_length=request.args.max_seq_length,
            padding="max_length",
        )
        encoded["labels"] = [list(ids) for ids in encoded["input_ids"]]
        return encoded

    dataset = Dataset.from_json(str(request.data / "train.jsonl")).map(
        tokenise, batched=True, remove_columns=["text"]
    )

    request.adapters.mkdir(parents=True, exist_ok=True)
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(request.adapters / ".trainer"),
            per_device_train_batch_size=request.args.batch_size,
            gradient_accumulation_steps=request.args.grad_accumulation_steps,
            gradient_checkpointing=request.args.grad_checkpoint,
            max_steps=request.args.iters,
            learning_rate=request.args.learning_rate,
            logging_steps=max(1, request.args.iters // 10),
            save_strategy="no",
            report_to=[],
            use_cpu=device == "cpu",
        ),
        train_dataset=dataset,
    )

    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    trainer.train()
    seconds = time.perf_counter() - started

    model.save_pretrained(str(request.adapters))

    allocated = int(torch.cuda.max_memory_allocated()) if device == "cuda" else 0
    return TrainingResult(
        peak_bytes=training_peak_bytes(mlx_peak=allocated, resident=_resident_bytes()),
        seconds=seconds,
    )


def _resident_bytes() -> int:
    """Peak resident bytes, in bytes on every platform this runs on.

    `ru_maxrss` is bytes on Darwin and kibibytes on Linux — the kind of difference that produces
    a capacity finding off by a factor of 1024, and this runtime is the one that actually runs on
    both. On CPU and MPS it is the only reading there is, because neither has an allocator
    counter to ask.
    """
    import resource
    import sys

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


#: How this runtime decodes, in the shape `sampling.SAMPLER` uses and for the same reason:
#: "sampled" alone is a word, and a reader of a ledger has to be able to tell one sampled run
#: from another. **Deliberately not a copy of MLX's string.** The two runtimes do not implement
#: the same sampler — `transformers` renormalises after the top-p cut and applies temperature in
#: a different order from `mlx_lm.sample_utils.make_sampler` — so writing MLX's sentence here
#: would claim a parity nothing establishes. The temperature and the cut-off are shared by
#: identity (`sampling.TEMPERATURE`, `sampling.TOP_P`); the claim about what they mean is not.
TORCH_SAMPLER = (
    "multinomial: temperature {temperature}, top-p {top_p} "
    "(transformers.GenerationConfig do_sample=True), with torch.manual_seed("
    "attempt_seed(run_seed, task_id, attempt)) applied immediately before each draw"
)

#: Recorded so the absence of a chat template is a disclosed decision rather than an omission a
#: later reader infers, exactly as `mlx_runtime.CHAT_TEMPLATE` is. The prompt reaches the model
#: verbatim: templating it here would break the prompt hash's meaning and make a night partly a
#: comparison of templates.
TORCH_CHAT_TEMPLATE = "none: the rendered prompt is tokenised and passed verbatim"


def torch_seeder(seed: int) -> None:
    """Seed the global RNG `transformers` samples from, the `mlx_seeder` shape.

    `torch.manual_seed` rather than a `Generator` object handed to `generate`, because the seam
    is `sampling.Seeder = Callable[[int], None]` and `Draw` applies it immediately before asking
    — the seed depends on which task and which attempt, which the generator does not know.

    Function-local import for the module rule: this must import and type-check on a machine with
    no Torch at all, and CI is such a machine.
    """
    import torch

    torch.manual_seed(seed)


class TorchGenerator:
    """A model on this machine, decoding by sampling, optionally with an adapter stacked.

    The `Generator` protocol exactly — `generate(prompt) -> str` — so `sweep`, `score` and the
    gate learn nothing about which runtime is underneath. A sibling of
    `sampling.SampledMlxGenerator` rather than a subclass: they share the contract and nothing
    else, and the one thing they must **not** share is a pretence that their samplers agree.

    **The prompt is sliced back off, and this is the whole correctness argument.**
    `mlx_lm.generate.generate` returns the completion alone; `transformers.generate` returns the
    prompt's tokens followed by the completion's. Decoding the whole sequence would hand the
    extractor the task's own prompt back — which contains the failing test and frequently the
    fix — and the night would score a model that solved nothing as having solved everything. The
    slice is by *token count on the input ids*, never by string prefix: re-tokenising and
    trimming text would depend on the tokeniser round-tripping exactly, which it does not have
    to.

    Everything deciding what is generated is fixed at construction and disclosed through
    `provenance()`. Nothing varies per call — the anti-tuning discipline M7b names.
    """

    def __init__(
        self,
        model_path: Path | str,
        *,
        revision: str,
        draws: int,
        max_tokens: int,
        adapter_path: Path | None = None,
    ) -> None:
        """Validate the path, then load. The order is the guarantee, `SampledMlxGenerator`'s.

        The path is checked before `transformers` is imported at all, so a repo id is refused on
        a machine with no engine and with no possibility of a download having started:
        `from_pretrained` treats anything that is not an existing directory as a Hub id and
        fetches it.
        """
        if not revision.strip():
            raise ValueError(
                f"revision must name the snapshot these weights came from; got {revision!r}. A "
                "blank revision serialises into the run ledger as a filled-in field that "
                "identifies nothing, which is a reproducibility claim that cannot be falsified."
            )
        path = Path(model_path)
        if not path.is_dir():
            raise NotALocalModelDirectory(
                f"{str(model_path)!r} is not a directory on this machine, so it cannot be loaded "
                "offline. `transformers.AutoModelForCausalLM.from_pretrained` treats anything "
                "that does not exist on disk as a HuggingFace repo id and DOWNLOADS it at call "
                "time. Pass the directory holding the weights; fetch them yourself, once, as a "
                "separate and recorded step."
            )
        if not (path / MODEL_CONFIG).is_file():
            raise NotALocalModelDirectory(
                f"{str(path)!r} holds no {MODEL_CONFIG}, so it is a directory rather than a model."
            )
        if adapter_path is not None and not adapter_path.is_dir():
            raise NotALocalModelDirectory(
                f"{str(adapter_path)!r} is not a directory, so there is no adapter to stack. "
                "Refused rather than loaded without one: a candidate silently evaluated as its "
                "own base scores the comparison the gate exists to make as a tie."
            )

        self._model_path = path.resolve()
        self._revision = revision
        self._draws = draws
        self._max_tokens = max_tokens
        self._adapter_path = None if adapter_path is None else adapter_path.resolve()
        self._model, self._tokenizer, self._device = _load_torch(
            self._model_path, revision, self._adapter_path
        )

    @property
    def model_path(self) -> Path:
        """The resolved directory these weights were loaded from. Never a repo id."""
        return self._model_path

    @property
    def revision(self) -> str:
        """The snapshot the operator says is in `model_path`, recorded verbatim."""
        return self._revision

    def generate(self, prompt: str) -> str:
        """Return the model's completion, raw. The seed was applied by `Draw`, not here."""
        import torch

        encoded = self._tokenizer(prompt, return_tensors="pt").to(self._device)
        prompt_tokens = int(encoded["input_ids"].shape[-1])
        with torch.no_grad():
            produced = self._model.generate(
                **encoded,
                do_sample=self._draws > 1,
                temperature=TEMPERATURE if self._draws > 1 else None,
                top_p=TOP_P if self._draws > 1 else None,
                max_new_tokens=self._max_tokens,
                pad_token_id=self._tokenizer.pad_token_id,
            )
        # Sliced by token count on the input, never by string prefix. See the class docstring:
        # decoding the whole sequence returns the task's own prompt, which holds the failing test.
        completion = produced[0][prompt_tokens:]
        answer = self._tokenizer.decode(completion, skip_special_tokens=True)
        if not isinstance(answer, str):
            raise TypeError(
                f"the tokeniser returned {type(answer).__name__}, not str. Coercing it here "
                "would hand the extractor a repr, which holds no diff, and the night would "
                "record a version mismatch as a base that wrote no patch."
            )
        return answer

    def provenance(self) -> Mapping[str, str]:
        """Everything that decided what was generated, as read-only strings."""
        from importlib.metadata import version as installed_version

        return MappingProxyType(
            {
                "runtime": "torch",
                "torch": installed_version("torch"),
                "transformers": installed_version("transformers"),
                "model_path": str(self._model_path),
                "revision": self._revision,
                "adapter_path": "" if self._adapter_path is None else str(self._adapter_path),
                "sampler": (
                    TORCH_SAMPLER.format(temperature=TEMPERATURE, top_p=TOP_P)
                    if self._draws > 1
                    else "greedy (k=1)"
                ),
                "draws": str(self._draws),
                "max_tokens": str(self._max_tokens),
                "chat_template": TORCH_CHAT_TEMPLATE,
            }
        )


def _load_torch(
    model_path: Path, revision: str, adapter_path: Path | None
) -> tuple[Any, Any, str]:
    """Load the base, stack the adapter when there is one, and return both with the device.

    The adapter is applied through `PeftModel.from_pretrained`, which is the only thing that
    knows how to map a saved adapter back onto the modules it was trained against. Reproducing
    that mapping here would be reimplementing the part of a library we depend on, which is the
    mistake the arm's own driver made (#34).
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = torch_device()
    dtype = getattr(torch, DEVICE_PRECISION[device])

    tokenizer = AutoTokenizer.from_pretrained(str(model_path), revision=revision)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    # Annotated `Any` deliberately, and for the reason `gate_engine` records at its own call
    # site. Under plain `uv sync` every symbol in `transformers` and `peft` resolves to `Any` and
    # none of this is checked at all; with the extra installed, `PeftModel.to` is a decorated
    # `_Wrapped` typed against `PreTrainedModel` and `.eval()` is untyped, so the same two lines
    # become errors. CI's second mypy run — the one with the extra — is what surfaced that, and
    # the annotation is what stops the file typechecking on one machine only.
    model: Any = AutoModelForCausalLM.from_pretrained(
        str(model_path), revision=revision, dtype=dtype
    )

    if adapter_path is not None:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, str(adapter_path))

    # Reassigned rather than called for the side effect: `nn.Module.to` returns `self`, but
    # `PeftModel`'s wrapper does not promise to, and a model left on the wrong device generates
    # correctly and slowly rather than raising.
    model = model.to(device)
    model.eval()
    return model, tokenizer, device


def torch_sampling_engine(weights: Any, max_tokens: int) -> Any:
    """The night's `Engine` on Torch: load a verified base from its own directory, offline.

    `sampling.sampling_engine`'s shape exactly — `HF_HUB_OFFLINE` is set **first**, so a defect
    in anything after it raises instead of downloading; the **path** is passed rather than
    `weights.repo_id`, because the two are one paste apart and one of them is a download.
    """
    import os

    from whetstone.bakeoff.run import HF_HUB_OFFLINE
    from whetstone.loop.sampling import K

    os.environ[HF_HUB_OFFLINE] = "1"
    return TorchGenerator(
        weights.local_dir, revision=weights.revision, draws=K, max_tokens=max_tokens
    )


def torch_gate_engine(
    weights: Any, checkpoint: Any, max_tokens: int = DEFAULT_MAX_TOKENS
) -> Any:
    """The gate's `GateEngine` on Torch: the base, with this checkpoint's adapter stacked.

    `gate.gate_engine`'s shape, and its dispatch too: an **untrained** checkpoint holds no
    adapter, so it loads the base alone. That is not a convenience — the gate's first evaluation
    scores a night's candidate against the untrained base it started from, and an untrained
    incumbent that quietly loaded some adapter would be a comparison against something else.

    **Greedy, and that is load-bearing.** `gate_engine` decodes with `sampler_for(1)`, which is
    `greedy_sampler` by identity, so a single-draw gate evaluation and the bake-off are one
    experiment. `draws=1` here gives `do_sample=False` with no temperature and no top-p, which
    is `transformers`' spelling of the same decision. A sampled gate would make a promotion
    decision depend on a draw.
    """
    import os

    from whetstone.bakeoff.run import HF_HUB_OFFLINE

    os.environ[HF_HUB_OFFLINE] = "1"
    return TorchGenerator(
        weights.local_dir,
        revision=weights.revision,
        draws=1,
        max_tokens=max_tokens,
        adapter_path=None if checkpoint.untrained else checkpoint.directory,
    )
