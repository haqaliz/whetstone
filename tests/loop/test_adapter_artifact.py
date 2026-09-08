"""The checkpoint must be a loadable adapter, not a bare tensor file.

The failure this prevents already exists in the tree. Night #1's checkpoint directory holds
exactly one file:

    checkpoints/night-001/adapters.safetensors    32 MB

and nothing else. `mlx_lm.tuner.utils.load_adapters` opens `adapter_config.json` **unguarded**
(`utils.py:127`), and `gate.py:584` hands it our checkpoint directory — so the promotion gate
raises `FileNotFoundError` on the first real candidate it is ever given. The never-regress
mechanism cannot load anything this project produces.

It is green in the suite because the fixtures write the file production does not
(`test_gate.py:281`, `test_honest_report_door.py:196` both hand-write `adapter_config.json`).
That is the same blind spot night #1 hit three times: a test asserting against a shape the real
path never emits.

**Two vocabularies, one filename.** MLX reads `num_layers` and `lora_parameters` and loads
weights from a hardcoded `adapters.safetensors`; PEFT reads `r`, `lora_alpha`, `target_modules`
and `base_model_name_or_path` from a hardcoded `adapter_model.safetensors`
(https://huggingface.co/docs/peft/developer_guides/checkpoint). The keys do not collide, so one
document can satisfy both readers — which is what makes a checkpoint this repository trains
loadable by anything else in the ecosystem rather than only by us.

**The scale conversion is derived, not guessed.** `mlx_lm/tuner/lora.py:98` applies
`y + scale * (x @ lora_a @ lora_b)`, while PEFT applies `y + (lora_alpha / r) * (x @ A @ B)`.
So the equivalent alpha is `scale * r`, and an adapter published with any other value is a
different adapter from the one that trained.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any

import pytest

from whetstone.loop import backend, sft

BASE = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"
REVISION = "d1e3b690c8e225d7795bccddf971ca6be68b2012"


def _runtime(
    name: str = backend.MLX, library: str = "mlx-lm"
) -> backend.Backend:
    return backend.Backend(
        name=name,
        library=library,
        version="0.31.3",
        device="Apple M4 Max",
        device_memory_bytes=38654705664,
    )


def _checkpoint(tmp_path: Path, **overrides: Any) -> Path:
    """A sealed checkpoint written by the real writer, adapter weights and all."""
    directory = tmp_path / "checkpoint"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / sft.ADAPTER_FILE).write_bytes(b"not a tensor, deliberately")
    fields: dict[str, Any] = {
        "repo_id": BASE,
        "revision": REVISION,
        "dataset_digest": "d" * 64,
        "run_seed": 20260906,
        "args": sft.TrainingArgs(),
        "tool_versions": {"python": "3.12.13"},
        "valid_split": "",
        "capacity": sft.CapacityProbe(
            iters=sft.CAPACITY_PROBE_ITERS,
            headroom_bytes=sft.CAPACITY_HEADROOM_BYTES,
            peak_bytes=24 * 1024**3,
            seconds=300.0,
        ),
        "backend": _runtime(),
    }
    fields.update(overrides)
    sft.write_checkpoint(directory, **fields)
    return directory


def test_the_checkpoint_carries_the_config_its_own_loader_dereferences(tmp_path: Path) -> None:
    """AC1: every attribute `load_adapters` reads off the config is one the checkpoint wrote.

    The guard reads the loader's own source for the attributes it dereferences rather than
    restating a list here, for the reason the `dropout` guard does: a list restated in a test
    drifts from the library exactly the way a literal does — silently, and only on the night
    that matters.
    """
    utils = pytest.importorskip(
        "mlx_lm.tuner.utils",
        reason=(
            "the `mlx` extra is not installed, so the loader's requirements cannot be read. "
            "This is CI's state by design (`uv sync` omits the extra); run "
            "`uv sync --extra mlx` on macOS / Apple Silicon"
        ),
    )
    source = inspect.getsource(utils.load_adapters)
    # `\b` matters: without it this matches "config.json" inside the *string*
    # "adapter_config.json" and demands a key called `json`. `_` is a word character, so a
    # boundary cannot fall inside `adapter_config`.
    required = set(re.findall(r"\bconfig\.(\w+)", source))
    assert required, (
        "WHY THIS IS A FAILURE: no `config.<attr>` dereference was found in the pinned "
        "`load_adapters`, so this guard asserts nothing. The loader's shape changed and the "
        "guard must be re-read against it rather than left passing vacuously"
    )

    directory = _checkpoint(tmp_path)
    written = directory / sft.ADAPTER_CONFIG
    assert written.is_file(), (
        f"WHY THIS IS A FAILURE: no {sft.ADAPTER_CONFIG} was written, so `load_adapters` raises "
        "`FileNotFoundError` at utils.py:127 and the promotion gate cannot load this candidate "
        "at all. This is the state night #1's checkpoint is in on disk right now"
    )
    supplied = set(json.loads(written.read_text()))

    assert required <= supplied, (
        f"WHY THIS IS A FAILURE: the pinned loader dereferences {sorted(required)} and the "
        f"checkpoint supplies {sorted(supplied)}. Missing {sorted(required - supplied)}, so the "
        "gate raises `AttributeError` while loading a candidate it has already re-hashed"
    )


def test_the_weights_use_the_filename_the_loader_hardcodes(tmp_path: Path) -> None:
    """AC2: the adapter is written under the name `load_adapters` looks for, not a near-miss.

    `utils.py:137` loads `adapter_path / "adapters.safetensors"` as a literal — it does not
    consult the config for the filename. A checkpoint whose weights sit under any other name
    loads *successfully* with no adapter applied, which is worse than failing: the gate would
    score the untrained base and report it as the candidate's result.
    """
    utils = pytest.importorskip("mlx_lm.tuner.utils", reason="the `mlx` extra is not installed")
    source = inspect.getsource(utils.load_adapters)
    names = set(re.findall(r'"([\w.]+\.safetensors)"', source))
    assert names, (
        "WHY THIS IS A FAILURE: the loader names no weights file, so this guard asserts nothing"
    )

    directory = _checkpoint(tmp_path)
    present = {one.name for one in directory.iterdir()}

    assert names <= present, (
        f"WHY THIS IS A FAILURE: the loader reads {sorted(names)} and the checkpoint holds "
        f"{sorted(present)}. `load_weights(..., strict=False)` would apply NOTHING and return "
        "the untrained base, so the gate would score the base and publish it as the candidate"
    )


def test_the_adapter_config_is_inside_the_checkpoints_own_digest(tmp_path: Path) -> None:
    """AC3: editing the config breaks verification, because the config decides what the adapter is.

    Rank, scale and dropout are the difference between two adapters. A config outside the digest
    could be edited after the fact and the checkpoint would still verify — so the gate would
    re-hash successfully and then build a *different* adapter from the one the night trained.
    """
    directory = _checkpoint(tmp_path)
    sft.verify_checkpoint(directory)

    document = json.loads((directory / sft.ADAPTER_CONFIG).read_text())
    document["num_layers"] = 999
    (directory / sft.ADAPTER_CONFIG).write_text(json.dumps(document))

    with pytest.raises(sft.CheckpointUnverified):
        sft.verify_checkpoint(directory)


def test_the_config_is_written_in_the_vocabulary_of_the_runtime_that_trained_it(
    tmp_path: Path,
) -> None:
    """AC4, corrected by #31: one vocabulary, the trainer's own.

    This test used to assert the opposite — that the document carried PEFT's keys *as well*, on
    the reasoning that MLX's and PEFT's key sets are disjoint so one file could serve both
    readers. The key sets are disjoint. The conclusion did not follow: the two runtimes also
    disagree on the weights filename, on the tensor names and on the orientation of the matrices,
    so neither loader could ever open the other's checkpoint whatever the config said. See
    `test_adapter_vocabulary.py`, which pins all three.

    What the dual document did buy was a warning. PEFT reports `Unexpected keyword arguments
    ['fine_tune_type', 'lora_parameters', 'num_layers'] … It is highly recommended to upgrade the
    PEFT version before continuing` — wrong advice, about a problem that does not exist, on the
    first artifact a stranger loads. The way a checkpoint reaches somebody else's runtime is
    `fuse`, which emits a plain `Qwen2ForCausalLM`.
    """
    directory = _checkpoint(tmp_path)
    document = json.loads((directory / sft.ADAPTER_CONFIG).read_text())

    for key in ("fine_tune_type", "num_layers", "lora_parameters"):
        assert key in document, (
            f"WHY THIS IS A FAILURE: {key!r} is absent, so `mlx_lm.tuner.utils.load_adapters` "
            f"raises on this checkpoint and the gate cannot score it. Got {sorted(document)}"
        )
    for absent in ("peft_type", "r", "lora_alpha", "base_model_name_or_path"):
        assert absent not in document, (
            f"WHY THIS IS A FAILURE: {absent!r} is on an MLX-trained adapter. PEFT cannot load "
            "one — different filename, different tensor names, transposed matrices — so the key "
            "is read by nobody, and its presence is what makes PEFT tell a reader to upgrade"
        )

    args = sft.TrainingArgs()
    assert document["num_layers"] == args.lora_layers
    assert document["lora_parameters"] == args.lora_config()


def test_a_torch_checkpoint_publishes_the_alpha_peft_will_divide(tmp_path: Path) -> None:
    """The conversion between the two conventions, which survives #31 unchanged.

    MLX applies `scale * (x @ A @ B)` (`lora.py:98`); PEFT applies `(alpha / r) * (x @ A @ B)`.
    An adapter published at any alpha other than `scale * r` behaves differently from the one
    that trained, and that is true of every Torch checkpoint this loop emits.
    """
    directory = _checkpoint(
        tmp_path, backend=_runtime(name=backend.TORCH, library="torch")
    )
    document = json.loads((directory / sft.ADAPTER_CONFIG).read_text())

    args = sft.TrainingArgs()
    assert document["r"] == args.lora_rank
    assert document["lora_dropout"] == args.lora_dropout
    assert document["base_model_name_or_path"] == BASE
    assert document["lora_alpha"] == args.lora_scale * args.lora_rank, (
        f"WHY THIS IS A FAILURE: the adapter trained at MLX scale {args.lora_scale} and is "
        f"published at PEFT alpha {document['lora_alpha']}. PEFT divides alpha by r, so the "
        f"equivalent alpha is scale * r = {args.lora_scale * args.lora_rank}. Any other value "
        "publishes an adapter that behaves differently from the one that trained"
    )


def test_a_config_the_trainer_already_wrote_is_merged_not_clobbered(tmp_path: Path) -> None:
    """AC5: a trainer that knows more about the adapter than the writer does keeps what it knew.

    PEFT's `save_pretrained` writes its own `adapter_config.json`, and it carries `target_modules`
    — which modules actually got adapters. That is knowledge only the trainer has: it resolves
    them from the model's architecture, and `sft.adapter_config` deliberately does not know them,
    because knowing them would mean knowing something about the base (`PREREGISTRATION.md`
    § 10.11).

    So the writer must **merge**. Overwriting would strip `target_modules` from every
    Torch-trained adapter and leave PEFT unable to reconstruct it — the checkpoint would load
    under MLX and not under the runtime that produced it, which is precisely backwards.

    The writer still wins on the keys it owns: the LoRA shape it records is the one from
    `TrainingArgs`, because that is the record the provenance publishes and two sources for one
    value is how a checkpoint comes to disagree with its own arguments.
    """
    directory = tmp_path / "checkpoint"
    directory.mkdir(parents=True)
    (directory / sft.ADAPTER_FILE).write_bytes(b"not a tensor, deliberately")
    (directory / sft.ADAPTER_CONFIG).write_text(
        json.dumps(
            {
                "peft_type": "LORA",
                "target_modules": ["q_proj", "v_proj"],
                "r": 999,
                "inference_mode": False,
            }
        )
    )

    # Sealed under the Torch backend, because the config being merged is the one PEFT's
    # `save_pretrained` writes. The fixture used to seal this under MLX, which asserted that a
    # PEFT document survives on a checkpoint PEFT cannot open — the test passed and described
    # something that never happens.
    _checkpoint(tmp_path, backend=_runtime(name=backend.TORCH, library="torch"))

    merged = json.loads((directory / sft.ADAPTER_CONFIG).read_text())
    assert merged.get("target_modules") == ["q_proj", "v_proj"], (
        f"WHY THIS IS A FAILURE: the trainer's `target_modules` was lost. Got "
        f"{merged.get('target_modules')!r}. PEFT cannot rebuild the adapter without it, so a "
        "Torch-trained checkpoint would load under MLX and not under the runtime that wrote it"
    )
    assert merged.get("inference_mode") is False, (
        "WHY THIS IS A FAILURE: a key the trainer wrote and the writer knows nothing about was "
        "dropped. Merging means keeping what it did not put there"
    )
    assert merged["r"] == sft.TrainingArgs().lora_rank, (
        f"WHY THIS IS A FAILURE: the merge kept the trainer's r={merged['r']} over the declared "
        "arguments. The writer owns the keys it records, because those are what provenance "
        "publishes — two sources for one value is how a checkpoint disagrees with its own "
        "arguments"
    )
