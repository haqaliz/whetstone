"""The second trainer: PEFT LoRA on Torch, so the loop is not Apple Silicon's alone.

`sft.Trainer` has always been a seam — a plain callable passed into `run_night` — and the whole
suite runs with no runtime, no weights and no GPU. So a second implementation is additive code.
What it must not be is a *different contract*: a night trained on Torch and a night trained on
MLX have to produce the same shaped artefact, be recorded the same way, and be refused by the
gate against each other. The first two are this module's job; the third landed with
`MismatchedBackend`.

**Base size is an input, and this file is where that is enforced.** `PREREGISTRATION.md` § 10.11
opens the portability arm at the smallest size that trains on the hardware available, and says
plainly that larger bases are expected — so it requires the trainer, the adapter format and the
gate to be *indifferent to base size*, so that scaling up is an amendment and not a rewrite. A
module that named a model, a parameter count, or a quantisation would quietly convert that
amendment into a rewrite, and nothing would look wrong until somebody tried it.

**The device is probed, not assumed** — the shape `sandbox.confinement()` already uses, for the
same reason: a CPU fallback nobody chose is how a 32B training run silently becomes a job that
never finishes.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from whetstone.loop import sft, torch_runtime

#: Substrings that would mean a base was named in the trainer rather than passed to it. Deliberately
#: broad: the point is not to ban these exact strings but to fail on the *shape* of a hardcoded
#: model, so a reviewer is forced to look.
_HARDCODED_BASE_MARKERS = (
    "qwen",
    "llama",
    "mistral",
    "0.5b",
    "1.5b",
    "7b",
    "32b",
    "mlx-community",
)


def test_the_trainer_names_no_base_and_no_size() -> None:
    """AC1: § 10.11's requirement, asserted rather than trusted.

    The amendment permits this arm to start small **and** commits it to growing. Both halves
    depend on the base being an input: a trainer that named one would make every later size a
    code change, which is precisely the "rewrite instead of an amendment" the amendment forbids.

    Read from the module's own source rather than from a config object, because the failure this
    catches is somebody writing the model id inline in six months, and a config check would not
    see it.
    """
    source = inspect.getsource(torch_runtime).lower()
    # The docstring legitimately discusses sizes; only executable lines are searched.
    tree = ast.parse(inspect.getsource(torch_runtime))
    code = "\n".join(
        line
        for i, line in enumerate(inspect.getsource(torch_runtime).splitlines(), start=1)
        if not _in_docstring(tree, i)
    ).lower()

    named = [marker for marker in _HARDCODED_BASE_MARKERS if marker in code]
    assert not named, (
        f"WHY THIS IS A FAILURE: the trainer's code names {named}. `PREREGISTRATION.md` § 10.11 "
        "requires the trainer to be indifferent to base size so that scaling up is an amendment "
        "and not a rewrite. A base named here converts every future size into a code change, and "
        "nothing looks wrong until somebody tries one"
    )
    assert "model_path" in source, (
        "WHY THIS IS A FAILURE: the trainer does not take the base as a path, so it cannot be "
        "the input § 10.11 requires it to be"
    )


def _in_docstring(tree: ast.Module, line: int) -> bool:
    """True when `line` falls inside a docstring — prose may discuss what code may not name."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Constant):
            continue
        if not isinstance(node.value.value, str):
            continue
        if node.lineno <= line <= (node.end_lineno or node.lineno):
            return True
    return False


def test_the_device_is_probed_in_a_declared_order() -> None:
    """AC2: which device trains is discovered from the machine and stated, never assumed.

    The order is declared here rather than inferred from whatever the library returns, for
    `sandbox.confinement()`'s reason: a silent CPU fallback is how a 32B run becomes a job that
    never finishes while looking like it is working. `torch_device` names what it found so the
    checkpoint's provenance can record it beside the peak it measured.
    """
    order = torch_runtime.DEVICE_ORDER
    assert order == ("cuda", "mps", "cpu"), (
        f"WHY THIS IS A FAILURE: the declared probe order is {order}. It is a declaration, so a "
        "change to it is a change somebody has to make deliberately — not a consequence of "
        "whichever accelerator a library happens to enumerate first"
    )
    assert order[-1] == "cpu", (
        "WHY THIS IS A FAILURE: there is no final fallback, so a host with no accelerator has no "
        "device at all and the arm cannot run where it was designed to run"
    )


def test_the_peft_config_is_derived_from_the_declared_arguments() -> None:
    """AC3: one set of hyper-parameters, two runtimes, and the scale conversion is not guessed.

    `TrainingArgs` is the single record of what decides training, and it is written into every
    checkpoint's provenance. The Torch path must therefore *derive* its LoRA configuration from
    it rather than keep a second copy — two copies drift, and the provenance would then describe
    the one that did not run.

    MLX applies `scale * (x @ A @ B)`; PEFT applies `(lora_alpha / r) * (x @ A @ B)`. So the
    equivalent alpha is `scale * r`, exactly as the adapter config already publishes it. An
    adapter trained at any other alpha is a different adapter from the one the arguments describe.
    """
    args = sft.TrainingArgs()
    config = torch_runtime.peft_lora_config(args)

    assert config["r"] == args.lora_rank
    assert config["lora_dropout"] == args.lora_dropout
    assert config["lora_alpha"] == args.lora_scale * args.lora_rank, (
        f"WHY THIS IS A FAILURE: alpha is {config['lora_alpha']} and the declared MLX scale is "
        f"{args.lora_scale} at rank {args.lora_rank}, so the equivalent alpha is "
        f"{args.lora_scale * args.lora_rank}. Training at any other value produces an adapter "
        "that does not match its own recorded arguments"
    )
    assert config["task_type"] == "CAUSAL_LM"


def test_the_trainer_satisfies_the_seam_the_night_injects() -> None:
    """AC4: it is a `Trainer`, so `run_night(trainer=...)` accepts it without a special case.

    The night takes the trainer as a parameter precisely so a second runtime needs no branch
    inside the loop. If this signature drifted, the Torch path would need one — and a branch in
    the night is where two runtimes stop being interchangeable and start being two nights.
    """
    signature = inspect.signature(torch_runtime.torch_trainer)
    parameters = list(signature.parameters)
    assert parameters == ["request"], (
        f"WHY THIS IS A FAILURE: the trainer takes {parameters}, and the seam is "
        "`Callable[[TrainingRequest], TrainingResult]`. A trainer needing anything else forces a "
        "branch inside `run_night`, which is where two runtimes stop being interchangeable"
    )


def test_the_runtime_is_importable_without_torch_installed() -> None:
    """AC5: importing the module must not require the engine, exactly as `sft` does not.

    Every `mlx` import in `sft.py` is function-local so the module imports, type-checks and is
    fully tested on a machine with no extra. The same rule applies here and for the same reason:
    the reward path must never acquire an inference stack by importing something near it.
    """
    tree = ast.parse(inspect.getsource(torch_runtime))
    offenders = [
        node.names[0].name
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for name in [getattr(node, "module", None) or node.names[0].name]
        if str(name).split(".")[0] in {"torch", "transformers", "peft", "datasets"}
    ]
    assert not offenders, (
        f"WHY THIS IS A FAILURE: {offenders} is imported at module scope. `sft.py` keeps every "
        "engine import function-local so the module works on a machine with no extra; a "
        "module-scope import here puts an inference stack on the import path of anything that "
        "reaches this package"
    )


@pytest.mark.parametrize("name", ["cuda", "mps", "cpu"])
def test_every_declared_device_has_a_stated_precision(name: str) -> None:
    """AC6: what dtype each device trains in is declared, not inherited from a default.

    A CPU run in fp16 is arithmetic that silently produces nothing useful, and a CUDA run in
    fp32 wastes the memory the capacity probe is there to bound. Both are decisions, so both are
    written down where a reader can see them beside the device that caused them.
    """
    assert name in torch_runtime.DEVICE_PRECISION, (
        f"WHY THIS IS A FAILURE: {name!r} is a declared device with no declared precision, so "
        "what it trains in would be whatever the library defaults to"
    )
