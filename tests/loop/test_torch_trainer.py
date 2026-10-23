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
import sys
import types
from pathlib import Path
from typing import Any

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


def test_the_declared_precision_for_each_device_is_exact() -> None:
    """AC7: the declaration is pinned to the exact value, not merely present.

    Key presence is not enough: `float16`, `float32` and `bfloat16` are all "a stated precision",
    so a loose pin lets the map drift — fp32 silently becoming bf16, or bf16 back to fp16 — and
    every figure measured under it is then attributed to arithmetic it did not run in. The exact
    dict is asserted so the reader (and the gate) can tell one precision from another.
    """
    assert torch_runtime.DEVICE_PRECISION == {
        "cuda": "bfloat16",
        "mps": "float16",
        "cpu": "bfloat16",
    }, (
        f"WHY THIS IS A FAILURE: the declared precisions are {torch_runtime.DEVICE_PRECISION}, not "
        'the pinned {"cuda": "bfloat16", "mps": "float16", "cpu": "bfloat16"}. A loose pin lets '
        "fp16/fp32/bf16 drift silently, and a reader can no longer tell which arithmetic a figure "
        "was measured under"
    )


#: Which loads were prepared for k-bit training, so the branch is asserted rather than assumed.
PREPARED: list[Any] = []


def _prepare_kbit(model: Any, use_gradient_checkpointing: bool = True) -> Any:
    PREPARED.append(use_gradient_checkpointing)
    return model


def _install_fake_runtime(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Install just enough of Torch/transformers/peft/datasets to watch the load call.

    No runtime is installed anywhere in this suite by design, and the property under test is what
    the loader *asks for* rather than what the library does with it. `from_pretrained` records its
    keyword arguments; the rest of each module is the smallest surface `torch_trainer` and
    `_load_torch` touch.
    """
    calls: list[dict[str, Any]] = []
    PREPARED.clear()

    class _FakeModel:
        is_quantized = False

        def to(self, device: str) -> _FakeModel:
            return self

        def eval(self) -> None:
            return None

        def save_pretrained(self, path: str) -> None:
            Path(path).mkdir(parents=True, exist_ok=True)

    class _FakeAutoModel:
        @staticmethod
        def from_pretrained(*args: Any, **kwargs: Any) -> _FakeModel:
            calls.append(kwargs)
            model = _FakeModel()
            model.is_quantized = "quantization_config" in kwargs
            return model

    class _FakeTokenizer:
        pad_token = None
        eos_token = "<eos>"

    class _FakeDataset:
        @staticmethod
        def from_json(path: str) -> _FakeDataset:
            return _FakeDataset()

        def map(self, *args: Any, **kwargs: Any) -> _FakeDataset:
            return self

    class _TrainingArguments:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _Trainer:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def train(self) -> None:
            return None

    torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(
            is_available=lambda: False,
            reset_peak_memory_stats=lambda: None,
            max_memory_allocated=lambda: 0,
        ),
        backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False)),
        bfloat16="bfloat16",
        float16="float16",
        float32="float32",
    )
    class _FakeBnb:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    transformers = types.SimpleNamespace(
        AutoModelForCausalLM=_FakeAutoModel,
        AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda *a, **k: _FakeTokenizer()),
        BitsAndBytesConfig=_FakeBnb,
        Trainer=_Trainer,
        TrainingArguments=_TrainingArguments,
    )
    peft = types.SimpleNamespace(
        LoraConfig=lambda **kwargs: kwargs,
        get_peft_model=lambda model, config: model,
        prepare_model_for_kbit_training=_prepare_kbit,
    )
    datasets = types.SimpleNamespace(Dataset=_FakeDataset)

    for name, module in (
        ("torch", torch),
        ("transformers", transformers),
        ("peft", peft),
        ("datasets", datasets),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    return calls


def test_a_4bit_base_is_prepared_for_kbit_training(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A frozen 4-bit base needs `prepare_model_for_kbit_training` before LoRA is attached."""
    calls = _install_fake_runtime(monkeypatch)
    model_dir = tmp_path / "weights"
    model_dir.mkdir()
    (model_dir / torch_runtime.QUANTIZE_SIDECAR).write_text(
        '{"bnb_4bit_quant_type": "nf4"}', encoding="utf-8"
    )
    data = tmp_path / "data"
    data.mkdir()
    (data / "train.jsonl").write_text("{}\n", encoding="utf-8")
    request = sft.TrainingRequest(
        model_path=model_dir,
        revision="ea3f2471",
        data=data,
        adapters=tmp_path / "out",
        args=sft.TrainingArgs(),
    )

    torch_runtime.torch_trainer(request)

    assert calls[0].get("quantization_config") is not None, (
        f"WHY THIS IS A FAILURE: the trainer loaded {calls[0]!r} beside a quantize.json. A 4-bit "
        "base loaded in full precision does not fit the machine the night is committed to"
    )
    assert [request.args.grad_checkpoint] == PREPARED, (
        f"WHY THIS IS A FAILURE: prepare_model_for_kbit_training was called {PREPARED!r}. A "
        "4-bit base must be prepared before LoRA; skipping it leaves the adapter attached to "
        "frozen quantized weights in the wrong dtype"
    )


def test_a_full_precision_base_is_not_prepared_for_kbit_training(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The 8B path must not run the k-bit preparation: it is not a quantized model."""
    _install_fake_runtime(monkeypatch)
    data = tmp_path / "data"
    data.mkdir()
    (data / "train.jsonl").write_text("{}\n", encoding="utf-8")
    request = sft.TrainingRequest(
        model_path=tmp_path / "weights",
        revision="ea3f2471",
        data=data,
        adapters=tmp_path / "out",
        args=sft.TrainingArgs(),
    )

    torch_runtime.torch_trainer(request)

    assert PREPARED == [], (
        f"WHY THIS IS A FAILURE: a full-precision base was prepared for k-bit training "
        f"({PREPARED!r}). The preparation detaches and casts weights for a quantized model"
    )


def test_the_trainer_asks_for_the_low_memory_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The 7B double copy: `from_pretrained` then `.to(mps)` materialises weights twice.

    On unified memory the 0.5B arm's peak is consistent with two copies, and two 7B copies exceed
    the MPS headroom — a `CapacityExceeded` that writes no checkpoint. `low_cpu_mem_usage` is a
    necessary-condition fix; the 7B pre-flight remains the measurement of the real peak.
    """
    calls = _install_fake_runtime(monkeypatch)
    data = tmp_path / "data"
    data.mkdir()
    (data / "train.jsonl").write_text("{}\n", encoding="utf-8")
    request = sft.TrainingRequest(
        model_path=tmp_path / "weights",
        revision="ea3f2471",
        data=data,
        adapters=tmp_path / "out",
        args=sft.TrainingArgs(),
    )

    torch_runtime.torch_trainer(request)

    assert calls, "the trainer never called `from_pretrained`, so this proves nothing"
    assert calls[0]["low_cpu_mem_usage"] is True, (
        f"WHY THIS IS A FAILURE: the trainer loaded with {calls[0]!r}. Without "
        "`low_cpu_mem_usage=True` the load materialises a second full copy on the CPU before "
        "moving to MPS, which for a 7B base is the difference between fitting the headroom and "
        "not starting at all"
    )
