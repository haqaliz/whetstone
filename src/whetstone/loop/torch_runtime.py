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
from typing import Any

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
