"""Merge an adapter into its base, so a night's output is something other people can run.

A LoRA checkpoint is two small files that mean nothing without the base they attach to. That is
the right shape for the loop — a night produces an adapter, not eighteen gigabytes — and the
wrong shape for anybody who wants to *run* it. Fusing merges the two into one standalone model,
which is the form every downstream tool expects: it is what llama.cpp converts to GGUF, and GGUF
is what Ollama, LM Studio, Jan and GPT4All load on every operating system.

**The fuser is chosen by the checkpoint's recorded backend, never by the host's.** This is the
whole reason `Checkpoint.backend` exists, and the failure it prevents is silent. A Torch adapter
and an MLX adapter are different tensor layouts behind the same filename, and each runtime will
accept the other's file without complaint — the merge does not raise, it emits weights, and
nothing looks wrong until somebody measures a model that was never trained. A Mac fusing a
Torch-trained checkpoint uses the Torch fuser; the host has no vote.

**A checkpoint with no recorded backend is refused rather than guessed at.** Guessing from the
host would be right about half the time, and the artefact produced by the other half is
indistinguishable from the correct one.

**Fusing is deliberately not part of the night.** The night's job is to produce evidence and a
candidate; fusing is a publishing step, taken afterwards, by somebody who has decided to
distribute. Folding it into `run_night` would make every night pay for a step most nights do not
need, and would put gigabytes of derived weights beside the evidence that justifies them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from whetstone.loop.backend import MLX, TORCH_CUDA
from whetstone.loop.sft import Checkpoint

#: The fused model's own provenance document, in the `weights.py` / `sft.py` shape.
FUSION_FILE = "fusion.json"

#: Its schema, so a reader refuses a document it does not understand rather than parsing it
#: optimistically.
FUSION_SCHEMA = "whetstone-fusion/1"


class NothingToFuse(ValueError):
    """The checkpoint holds no adapter, so there is nothing to merge into the base.

    An untrained checkpoint fused would produce a directory that is byte-for-byte its own base
    while presenting as a trained model — the most confusing artefact this project could emit,
    because it loads, generates, and is wrong only about what it is.
    """


class FusionFailed(RuntimeError):
    """The merge did not complete, so whatever is on disk is not a model.

    Raised rather than returned, and never left for the caller to notice: a partially written
    model directory loads far enough to look plausible, and the first thing anybody does with a
    fused model is publish it.
    """


class UnknownProvenance(ValueError):
    """The checkpoint does not say which runtime trained it, so no fuser can be chosen.

    Refused rather than guessed from the host. The wrong fuser does not raise; it emits weights
    nobody can distinguish from correct ones, and the error surfaces as a number measured on a
    model that was never trained.
    """


def fuser_for(checkpoint: Checkpoint) -> str:
    """Which runtime's fuser must read this adapter — the checkpoint's answer, not the host's."""
    if checkpoint.untrained:
        raise NothingToFuse(
            f"{str(checkpoint.directory)!r} is an untrained checkpoint: it holds no adapter, so "
            "there is nothing to merge. Fusing it would produce a directory byte-for-byte "
            "identical to its own base while presenting as a trained model"
        )
    recorded = checkpoint.backend
    if not recorded or not recorded.get("name"):
        raise UnknownProvenance(
            f"{str(checkpoint.directory)!r} records no backend, so which runtime trained this "
            "adapter is unknown and no fuser can be chosen. Refused rather than guessed from "
            "this host: a Torch adapter and an MLX adapter are different tensor layouts behind "
            "one filename, and the wrong fuser emits weights rather than raising. Checkpoints "
            "sealed before schema `whetstone-run/2` carry no backend and cannot be fused"
        )
    name = str(recorded["name"])
    if name not in {MLX, TORCH_CUDA} and not name.startswith("torch"):
        raise UnknownProvenance(
            f"{str(checkpoint.directory)!r} records backend {name!r}, which this repository has "
            "no fuser for. Refused rather than approximated with the nearest one"
        )
    return MLX if name == MLX else TORCH_CUDA


def refuse_published_destination(destination: Path) -> None:
    """Refuse a fused model written under `reports/`.

    The refusal `--runs` and `--checkpoints` already carry, for a sharper reason here: `reports/`
    holds the sanctioned homes of figures and its contents are pinned artifact-by-artifact by a
    guard, so a model written there is both an unsanctioned file in a place that permits none and
    gigabytes of weights in a directory meant for three small documents.
    """
    for part in Path(destination).resolve().parts:
        if part == "reports":
            raise ValueError(
                f"{str(destination)!r} resolves inside a `reports/` directory. That tree holds "
                "the sanctioned homes of figures, pinned file by file; a fused model there is an "
                "unsanctioned artifact in a place that permits none, and gigabytes of weights in "
                "a directory meant for three small documents"
            )


def refuse_destination_inside(checkpoint: Checkpoint, destination: Path) -> None:
    """Refuse a fused model written inside the checkpoint it was built from.

    The checkpoint's digest covers the files in its directory, so writing a fused model beside
    them changes what the directory holds and the checkpoint stops verifying against its own
    provenance. Publishing it would destroy the evidence it was published from.
    """
    sealed = Path(checkpoint.directory).resolve()
    target = Path(destination).resolve()
    if sealed == target or sealed in target.parents:
        raise ValueError(
            f"{str(destination)!r} is inside the checkpoint at {str(sealed)!r}. The checkpoint's "
            "digest covers what that directory holds, so writing here would stop it verifying "
            "against its own provenance — publishing the model would destroy the evidence it was "
            "published from"
        )


def write_fusion_provenance(
    destination: Path, *, checkpoint: Checkpoint, repo_id: str, revision: str
) -> Path:
    """Record what the fused model was built from, while that is still knowable.

    Fusing destroys the distinction the checkpoint made: afterwards there is no adapter file to
    inspect and no `base_model_name_or_path` to read, only weights. Everything a later reader
    needs about where those weights came from has to be written at the one moment it is still
    available.
    """
    document: dict[str, Any] = {
        "schema": FUSION_SCHEMA,
        "base": {"repo_id": repo_id, "revision": revision},
        "adapter": {
            "digest": checkpoint.digest,
            "files": [one.name for one in checkpoint.files],
        },
        "backend": dict(checkpoint.backend or {}),
        "fused_by": fuser_for(checkpoint),
    }
    written = Path(destination) / FUSION_FILE
    written.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return written


def fuse_checkpoint(
    *, checkpoint_path: Path, base: Path, destination: Path, revision: str, repo_id: str
) -> Path:
    """Merge a verified checkpoint's adapter into its base and write one standalone model.

    The order is the design, and it is the order every door in this repository uses: the
    destination is refused before anything is read, the checkpoint is **re-verified** before a
    tensor is touched, the fuser is chosen from what the checkpoint says rather than from what
    the host has, and the provenance is written last — after the weights exist, so it cannot
    describe a model that was never produced.

    Re-verification is not ceremony. A gitignored directory can be rebuilt, truncated or
    hand-edited between the night that sealed it and the moment somebody publishes from it, and
    a fused model inherits every byte it was built from with no way to tell afterwards.
    """
    from whetstone.loop.sft import verify_checkpoint

    destination = Path(destination)
    refuse_published_destination(destination)

    verified = verify_checkpoint(Path(checkpoint_path))
    refuse_destination_inside(verified, destination)
    mechanism = fuser_for(verified)

    destination.mkdir(parents=True, exist_ok=True)
    if mechanism == MLX:
        _fuse_mlx(base=base, adapter=verified.directory, destination=destination)
    else:
        _fuse_torch(
            base=base, adapter=verified.directory, destination=destination, revision=revision
        )

    write_fusion_provenance(
        destination, checkpoint=verified, repo_id=repo_id, revision=revision
    )
    return destination


def _fuse_mlx(*, base: Path, adapter: Path, destination: Path) -> None:
    """MLX's own fuser, called rather than reimplemented — through its CLI, not its internals.

    `mlx_lm` owns how its adapters merge; a second implementation here would be a second answer
    to "what does this adapter mean", and the day they disagreed neither would say so.

    Invoked as a subprocess rather than by importing `mlx_lm.fuse.main`, and that is a
    deliberate choice mypy forced into the open: `main()` takes no arguments and parses
    `sys.argv` itself, so calling it in-process would mean mutating global argv around it. The
    documented CLI is the library's stable surface; `main`'s shape is not, and binding to it
    would break on a refactor that breaks nothing for anybody else.
    """
    import subprocess
    import sys

    completed = subprocess.run(
        [
            sys.executable, "-m", "mlx_lm", "fuse",
            "--model", str(base),
            "--adapter-path", str(adapter),
            "--save-path", str(destination),
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise FusionFailed(
            f"`mlx_lm fuse` exited {completed.returncode}: "
            f"{completed.stderr.decode(errors='replace').strip()!r}. Raised rather than left as "
            "a partial directory: a half-written model is one somebody publishes"
        )


def _fuse_torch(*, base: Path, adapter: Path, destination: Path, revision: str) -> None:
    """PEFT's `merge_and_unload`, which is the library's own answer to the same question.

    `save_pretrained` writes a complete model directory, and the tokenizer is copied beside it
    because a model directory without one is not loadable by anything downstream — llama.cpp's
    converter reads both, and so does every serving stack.
    """
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model = AutoModelForCausalLM.from_pretrained(str(base), revision=revision)
    merged = PeftModel.from_pretrained(model, str(adapter)).merge_and_unload()
    merged.save_pretrained(str(destination))
    AutoTokenizer.from_pretrained(str(base), revision=revision).save_pretrained(str(destination))
