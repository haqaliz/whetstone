"""One `adapter_config.json`, one vocabulary: the trainer's own (#31).

`adapter_config` used to write MLX's keys and PEFT's keys into a single document, reasoning that
the two readers dereference disjoint key sets so one file could serve both — an adapter the
ecosystem could open rather than one only this repository could. The key sets are disjoint. The
conclusion still did not follow.

**The config is not the only thing that differs, and each of the others is independently fatal.**
Measured, not inferred:

| | MLX | PEFT |
|---|---|---|
| weights filename | `adapters.safetensors` (`tuner/utils.py`) | `adapter_model.safetensors` |
| tensor key | `…q_proj.lora_a` | `base_model.model.…q_proj.lora_A.weight` |
| shape of A | `(896, 8)` = `(in, r)` | `(8, 896)` = `(r, in)` |

So neither loader can read the other's checkpoint whatever the config says. The merged document
bought nothing and cost something real: PEFT emits `Unexpected keyword arguments
['fine_tune_type', 'lora_parameters', 'num_layers'] … It is highly recommended to upgrade the
PEFT version before continuing` — advice that is wrong, about a problem that does not exist, on
the first artifact a stranger loads.

**The cross-runtime bridge is `fuse`.** A fused model is a plain `Qwen2ForCausalLM` that any
runtime loads. The adapter is trainer-specific by construction, and this file is here so that
the next person to notice the two runtimes "nearly agree" finds out why they do not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whetstone.loop import backend, sft

BASE = "Qwen/Qwen2.5-Coder-0.5B-Instruct"

#: MLX's loader dereferences these off `adapter_config.json` (`mlx_lm/tuner/utils.py`).
MLX_KEYS = frozenset({"fine_tune_type", "num_layers", "lora_parameters"})

#: What PEFT's `LoraConfig` accepts and warns about the absence of a match for.
PEFT_KEYS = frozenset(
    {"peft_type", "task_type", "base_model_name_or_path", "r", "lora_alpha", "lora_dropout"}
)


def _args() -> sft.TrainingArgs:
    return sft.TrainingArgs()


@pytest.mark.parametrize("name", [backend.MLX])
def test_an_mlx_checkpoint_carries_mlx_keys_only(name: str) -> None:
    """PEFT's keys on an MLX adapter are unreachable: PEFT cannot open one at all."""
    written = set(adapter := sft.adapter_config(_args(), repo_id=BASE, backend_name=name))

    assert written >= MLX_KEYS, (
        f"WHY THIS IS A FAILURE: MLX's own loader dereferences {sorted(MLX_KEYS)} unguarded, so "
        "a checkpoint missing any of them raises before the gate can score it. Got "
        f"{sorted(written)}"
    )
    assert not (written & PEFT_KEYS), (
        "WHY THIS IS A FAILURE: PEFT's keys are on an MLX-trained adapter, which PEFT cannot "
        "load in any case — different weights filename, different tensor names, transposed "
        f"matrices. They buy nothing and are read by nobody. Got {sorted(written & PEFT_KEYS)}"
    )
    assert adapter["lora_parameters"] == _args().lora_config()


@pytest.mark.parametrize("name", [backend.TORCH, "torch-cpu", "torch-cuda"])
def test_a_torch_checkpoint_carries_peft_keys_only(name: str) -> None:
    """The warning this closes is emitted on the artifact a stranger loads first.

    Parameterised over the legacy spellings too: the only real checkpoint this project has
    records `torch-cpu` inside its digest, and that name has to keep resolving forever.
    """
    written = set(adapter := sft.adapter_config(_args(), repo_id=BASE, backend_name=name))

    assert written >= PEFT_KEYS, (
        f"WHY THIS IS A FAILURE: a PEFT adapter is missing {sorted(PEFT_KEYS - written)}"
    )
    assert not (written & MLX_KEYS), (
        "WHY THIS IS A FAILURE: MLX's keys are back on a Torch adapter. PEFT warns on every one "
        "of them and tells the reader to upgrade PEFT — wrong advice about a problem that does "
        f"not exist. They are also unread: MLX cannot open this checkpoint. Got "
        f"{sorted(written & MLX_KEYS)}"
    )
    # The alpha is a conversion between two conventions, never a preference.
    assert adapter["lora_alpha"] == _args().lora_scale * _args().lora_rank


def test_the_two_runtimes_disagree_about_more_than_the_config() -> None:
    """The load-bearing fact, pinned: fixing the config would not have made them interchangeable.

    If this ever fails because the two runtimes converged, the merged config becomes worth
    revisiting — and that is exactly the conversation this assertion is here to force.
    """
    from whetstone.loop.torch_runtime import PEFT_ADAPTER_FILE

    assert sft.ADAPTER_FILE != PEFT_ADAPTER_FILE, (
        f"WHY THIS IS A FAILURE: both runtimes now hardcode {sft.ADAPTER_FILE!r}. The reason one "
        "checkpoint cannot serve both loaders was never only the config, and if the filenames "
        "have converged the rest of that argument needs re-checking rather than assuming"
    )


def test_an_unknown_runtime_is_refused_rather_than_given_a_vocabulary(tmp_path: Path) -> None:
    """A config written in a guessed vocabulary is a checkpoint that loads as the wrong adapter."""
    with pytest.raises(backend.UnknownRuntime) as refused:
        sft.adapter_config(_args(), repo_id=BASE, backend_name="jax")
    assert "jax" in str(refused.value)


@pytest.mark.parametrize("name", [backend.MLX, backend.TORCH])
def test_what_is_written_is_exactly_what_the_other_vocabulary_strips(name: str) -> None:
    """Two lists of the same keys is how a stale key survives a re-seal.

    `write_checkpoint` removes the other runtime's keys before applying its own, so a directory
    holding a config from the merged-vocabulary scheme does not carry it forward. That strip is
    driven by `_VOCABULARY`, and `adapter_config` writes literals — so if they drift, the strip
    misses a key and the warning comes back on a checkpoint that was supposed to be clean.
    """
    written = set(sft.adapter_config(_args(), repo_id=BASE, backend_name=name))

    assert written == set(sft._VOCABULARY[name]), (
        "WHY THIS IS A FAILURE: the keys this writer emits and the keys it strips for the other "
        f"runtime have drifted. Writes {sorted(written)}, declares "
        f"{sorted(sft._VOCABULARY[name])}"
    )


def test_a_stale_vocabulary_does_not_survive_a_re_seal(tmp_path: Path) -> None:
    """The concrete case: a directory holding the old merged document, sealed again.

    `checkpoints/portability-arm/adapter_config.json` on disk today carries both vocabularies. It
    is never rewritten — its digest seals it — but a night that writes into a directory holding
    such a file must not merge the dead keys forward, or the PEFT warning outlives the fix.
    """
    directory = tmp_path / "checkpoint"
    directory.mkdir(parents=True)
    (directory / sft.ADAPTER_FILE).write_bytes(b"not a tensor, deliberately")
    (directory / sft.ADAPTER_CONFIG).write_text(
        '{"fine_tune_type": "lora", "num_layers": 8, "lora_parameters": {"rank": 8}, '
        '"peft_type": "LORA", "r": 8, "target_modules": ["q_proj"]}'
    )

    sft.write_checkpoint(
        directory,
        repo_id=BASE,
        revision="ea3f2471cf1b1f0db85067f1ef93848e38e88c25",
        dataset_digest="d" * 64,
        run_seed=20260906,
        args=_args(),
        tool_versions={"python": "3.12.13"},
        valid_split="",
        capacity=sft.CapacityProbe(
            iters=sft.CAPACITY_PROBE_ITERS,
            headroom_bytes=sft.CAPACITY_HEADROOM_BYTES,
            peak_bytes=1024,
            seconds=1.0,
        ),
        backend=backend.Backend(
            name="torch-cpu",
            library="torch",
            version="2.14.0+cu130",
            device="cpu",
            device_memory_bytes=16637317120,
        ),
    )

    import json

    document = json.loads((directory / sft.ADAPTER_CONFIG).read_text())
    assert not (set(document) & MLX_KEYS), (
        "WHY THIS IS A FAILURE: MLX's keys survived a re-seal onto a Torch checkpoint, so the "
        f"PEFT warning outlives the change that removed it. Got {sorted(set(document) & MLX_KEYS)}"
    )
    assert document.get("target_modules") == ["q_proj"], (
        "WHY THIS IS A FAILURE: the strip took `target_modules`, which belongs to the trainer "
        "and which this writer never knows. Only the other runtime's own keys may be removed"
    )
