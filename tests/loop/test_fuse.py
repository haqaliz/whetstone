"""Fusing an adapter into its base: the step that makes a checkpoint runnable by other people.

A LoRA checkpoint is two small files that mean nothing without the base they attach to. That is
the right shape for the loop — a night's output is an adapter, not eighteen gigabytes — but it is
the wrong shape for somebody who wants to *run* the thing. Fusing merges the adapter into the
base and emits one standalone model, which is what every downstream tool expects: it is what
llama.cpp converts to GGUF, and GGUF is what Ollama, LM Studio, Jan and GPT4All load on every
operating system.

**The fuser is chosen by the checkpoint's recorded backend, never by the host's.** This is the
sharp edge of the whole unit. An adapter trained under Torch and an adapter trained under MLX
are different tensor layouts under the same filename, and both runtimes will happily be pointed
at either. Fusing a Torch adapter with MLX's fuser on a Mac does not raise — it produces
*weights*, and nothing about them looks wrong until somebody measures a model that was never
trained. `Checkpoint.backend` exists precisely so the artefact carries the answer, and this is
where it earns that.

**An untrained checkpoint cannot be fused.** It holds no adapter; merging nothing into a base
yields the base, and a directory presented as a fused model that is byte-for-byte the base is
the most confusing artefact this project could emit.

**The checkpoint is re-verified before a tensor is read.** `verify_checkpoint`'s argument,
applied one step later: a gitignored directory can be rebuilt, truncated or hand-edited between
the night that sealed it and the moment somebody fuses it, and a fused model inherits every
byte it was built from.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whetstone.loop import backend, fuse, sft

BASE = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
REVISION = "ea3f2471cf1b1f0db85067f1ef93848e38e88c25"


def _runtime(name: str = backend.MLX, library: str = "mlx-lm") -> backend.Backend:
    return backend.Backend(
        name=name,
        library=library,
        version="0.31.3",
        device="Apple M4 Max",
        device_memory_bytes=38654705664,
    )


def _sealed(tmp_path: Path, *, runtime: backend.Backend | None = None) -> Path:
    """A checkpoint sealed by the real writer, so what is fused is what a night would emit."""
    directory = tmp_path / "checkpoint"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / sft.ADAPTER_FILE).write_bytes(b"not a tensor, deliberately")
    sft.write_checkpoint(
        directory,
        repo_id=BASE,
        revision=REVISION,
        dataset_digest="d" * 64,
        run_seed=20260906,
        args=sft.TrainingArgs(),
        tool_versions={"python": "3.12.13"},
        valid_split="",
        capacity=sft.CapacityProbe(
            iters=sft.CAPACITY_PROBE_ITERS,
            headroom_bytes=sft.CAPACITY_HEADROOM_BYTES,
            peak_bytes=24 * 1024**3,
            seconds=300.0,
        ),
        backend=runtime or _runtime(),
    )
    return directory


def test_the_fuser_is_chosen_by_the_checkpoint_not_by_the_host(tmp_path: Path) -> None:
    """AC1: which runtime trained the adapter decides which fuser reads it. Nothing else does.

    The failure this prevents is silent and produces a plausible artefact. A Torch adapter and an
    MLX adapter are different tensor layouts behind the same filename, and each runtime will
    accept the other's file without complaint — the merge does not raise, it emits weights, and
    nobody discovers the problem until a number is measured on a model that was never trained.

    So the answer comes from `Checkpoint.backend`, read back from the provenance the night sealed.
    A Mac fusing a Torch-trained checkpoint uses the Torch fuser, and a CUDA box fusing an
    MLX-trained one uses MLX's — the host has no vote.
    """
    torch_trained = _sealed(tmp_path, runtime=_runtime(name=backend.TORCH_CUDA, library="torch"))
    checkpoint = sft.verify_checkpoint(torch_trained)

    assert fuse.fuser_for(checkpoint) == backend.TORCH_CUDA, (
        "WHY THIS IS A FAILURE: a checkpoint whose provenance says Torch would be fused by "
        "whatever the host happens to have. The two adapters are different tensor layouts under "
        "one filename, and the wrong fuser does not raise — it emits weights nobody can tell "
        "apart from correct ones"
    )

    mlx_trained = _sealed(tmp_path / "other", runtime=_runtime())
    assert fuse.fuser_for(sft.verify_checkpoint(mlx_trained)) == backend.MLX


def test_a_checkpoint_with_no_recorded_backend_is_refused(tmp_path: Path) -> None:
    """AC2: an unlabelled checkpoint is refused rather than guessed at.

    Checkpoints written before `whetstone-run/2` carry no backend. Guessing from the host would
    be right about half the time and silently wrong the rest, and the artefact produced by the
    wrong half is indistinguishable from the right one.
    """
    directory = _sealed(tmp_path)
    document = json.loads((directory / sft.CHECKPOINT_FILE).read_text())
    document.pop("backend")
    (directory / sft.CHECKPOINT_FILE).write_text(json.dumps(document))

    stale = sft.Checkpoint(directory=directory, digest="d" * 64, files=(), backend=None)
    with pytest.raises(fuse.UnknownProvenance, match="backend"):
        fuse.fuser_for(stale)


def test_an_untrained_checkpoint_cannot_be_fused(tmp_path: Path) -> None:
    """AC3: there is nothing to merge, and the result would be the base wearing a new name.

    A directory presented as a fused model that is byte-for-byte its own base is the most
    confusing artefact this project could emit — it would load, generate, and be wrong about
    what it is.
    """
    directory = tmp_path / "untrained"
    directory.mkdir()
    untrained = sft.Checkpoint(
        directory=directory, digest="u" * 64, files=(), untrained=True, backend=None
    )

    with pytest.raises(fuse.NothingToFuse, match="untrained"):
        fuse.fuser_for(untrained)


def test_the_fused_model_records_what_it_was_built_from(tmp_path: Path) -> None:
    """AC4: a fused model names its base, its adapter and the runtime that merged them.

    Fusing destroys the distinction the checkpoint made: afterwards there is no adapter file to
    inspect and no `base_model_name_or_path` to read, only weights. Everything a later reader
    needs to know about where those weights came from has to be written down at the moment it is
    still knowable, or it is gone.
    """
    directory = _sealed(tmp_path)
    checkpoint = sft.verify_checkpoint(directory)
    out = tmp_path / "fused"
    out.mkdir()

    fuse.write_fusion_provenance(
        out,
        checkpoint=checkpoint,
        repo_id=BASE,
        revision=REVISION,
    )

    recorded = json.loads((out / fuse.FUSION_FILE).read_text())
    assert recorded["schema"] == fuse.FUSION_SCHEMA
    assert recorded["base"]["repo_id"] == BASE
    assert recorded["base"]["revision"] == REVISION
    assert recorded["adapter"]["digest"] == checkpoint.digest, (
        "WHY THIS IS A FAILURE: the fused model does not name the adapter it absorbed, so "
        "nobody can tell which night produced it. After fusing there is no adapter left to ask"
    )
    assert recorded["backend"]["name"] == backend.MLX


def test_fusing_into_a_published_home_is_refused(tmp_path: Path) -> None:
    """AC5: a fused model is gigabytes of weights and never belongs under `reports/`.

    The same refusal `--runs` and `--checkpoints` already carry. `reports/` holds the sanctioned
    homes of figures, and its contents are pinned artifact-by-artifact by a guard: a model
    written there is both an unsanctioned file in a place that permits none and gigabytes of
    weights in a directory meant for three small documents.
    """
    with pytest.raises(ValueError, match="reports"):
        fuse.refuse_published_destination(tmp_path / "reports" / "portability-arm" / "fused")


def test_the_fused_model_is_not_the_checkpoint_directory(tmp_path: Path) -> None:
    """AC6: fusing never writes into the sealed checkpoint it is reading.

    The checkpoint's digest covers its files. Writing a fused model beside them changes what the
    directory holds, so the checkpoint would no longer verify against its own provenance — the
    act of publishing it would destroy the evidence it was published from.
    """
    directory = _sealed(tmp_path)
    checkpoint = sft.verify_checkpoint(directory)

    with pytest.raises(ValueError, match="checkpoint"):
        fuse.refuse_destination_inside(checkpoint, directory / "fused")
