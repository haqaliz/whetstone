"""The portability arm's driver: the run `PREREGISTRATION.md` § 10.11 declares, in the repository.

This module exists because the arm's first run was not driven from here. It was driven by a
`train_portability.py` written onto the Linux box during the session that produced it, and that
script is the single cause of every defect in the only real checkpoint this project has:

- it hand-built a `CapacityProbe` with `iters=CAPACITY_PROBE_ITERS` and `seconds` taken from the
  **full training run**, so the record says eight steps took six and a quarter hours (#32) — and
  no probe ever ran, because `probe_capacity` was never called;
- it passed `CAPACITY_HEADROOM_BYTES`, the constant compiled in for a 36 GiB Mac, as the ceiling
  for a 15.5 GiB Linux box, so the guard checked against nearly twice the machine (#30);
- it called `tool_versions()` with no backend, so the provenance names `mlx-lm` on a host that
  ran PyTorch and never had MLX installed (#33);
- it hand-built the `Backend` record, hardcoding `device_memory_bytes=0`.

None of those is a hard problem. Every one of them is what happens when a run goes **around** the
constructors instead of through them: `sft` has a `probe_capacity`, a `train` and a
`write_checkpoint`, and the script reimplemented the parts of each it needed. So the fix is not
better care next time — it is that the arm's driver is a command, under test, in the tree.

**What this module does not do.** It does not re-seal the existing checkpoint. That artifact's
digest covers its provenance, defects and all, and a record corrected after the fact verifies
nothing; #32 and #33 stand as the statement of what its fields get wrong. It also claims no
delta — § 10.11 committed in advance that this arm demonstrates the loop off Apple Silicon and
does not measure an improvement, and nothing here scores anything.

**It is not portability-specific, despite the name it is filed under.** Every input — base,
revision, dataset, destination — is an argument, and the runtime is detected. Running the same
door on a CUDA host with a larger base is the same call with different arguments, which is what
§ 10.11's "larger bases are expected and intended" requires of the machinery.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.loop import backend as backend_module
from whetstone.loop import ledger as run_ledger
from whetstone.loop import sft
from whetstone.loop.backend import Backend as BackendRecord

#: The night run's sealed selection, and the directory of files the trainer reads. Both are
#: produced by `run_night` and read here rather than rebuilt, so the arm trains on exactly the
#: examples a night selected — a second selection path would be a second answer to "what did this
#: train on" with nothing comparing them.
DATASET_FILE = "dataset.json"
DATA_DIR = "data"


class NothingSelected(ValueError):
    """The night this arm was pointed at selected no example, so there is nothing to train on.

    `sft.train` raises the same refusal one step later. Raised here as well because the probe
    runs *before* that check and would otherwise spend eight steps discovering it.
    """


class RunIncomplete(ValueError):
    """The night directory does not hold the two things a training run reads.

    Named separately from a bare `FileNotFoundError` so an operator who pointed the door at the
    wrong run is told which of the two is missing, rather than reading a traceback.
    """


@dataclass(frozen=True)
class ArmRun:
    """What the arm produced, and what it was measured under. Frozen: written is what is passed."""

    #: The sealed checkpoint, re-verified from disk before this record was built.
    checkpoint: sft.Checkpoint

    #: The runtime that trained it, detected before the first token.
    runtime: BackendRecord

    #: The probe that gated it — a real one, run by `probe_capacity` at the declared step count.
    capacity: sft.CapacityProbe


def read_selection(run: Path) -> tuple[str, int]:
    """The night's dataset digest and how many examples it selected.

    Read from the sealed document rather than by counting the files the trainer will read: the
    digest is what the checkpoint's provenance publishes, and deriving the count from a different
    source than the digest is how the two come to describe different sets.
    """
    document = run / DATASET_FILE
    data = run / DATA_DIR
    missing = [str(one) for one in (document, data) if not one.exists()]
    if missing:
        raise RunIncomplete(
            f"{str(run)!r} is missing {missing}, so there is no sealed selection to train on. A "
            "night writes both; pointing this door at a directory holding neither would train on "
            "whatever happened to be there and seal it as though a night had chosen it"
        )
    sealed = json.loads(document.read_text(encoding="utf-8"))
    examples = sealed.get("examples") or []
    if not examples:
        raise NothingSelected(
            f"the night at {str(run)!r} selected no strict-PASS rollout, so this arm has nothing "
            "to train on and no candidate to emit. The response is to raise the number of draws, "
            "never to loosen what counts as a win"
        )
    return str(sealed["digest"]), len(examples)


def run_arm(
    *,
    base: Path,
    repo_id: str,
    revision: str,
    run: Path,
    destination: Path,
    run_seed: int,
    valid_split: str = sft.NO_VALID_SPLIT,
    args: sft.TrainingArgs | None = None,
    trainer: sft.Trainer | None = None,
    runtime: BackendRecord | None = None,
) -> ArmRun:
    """Probe, train and seal — through `sft`'s own constructors, every one of them.

    The order is the design, and it is `run_night`'s order rather than a second one:

    1. **The runtime is detected first**, before a token is generated or a weight is read. A run
       whose runtime cannot be identified has nothing to label its evidence with, and finding
       that out after six hours is how this project already lost a night.
    2. **The ceiling comes from that record**, via `sft.headroom_for`, so the probe is checked
       against the machine it is running on. The arm's first run was checked against another
       machine and passed on luck.
    3. **The probe is run, not constructed.** `probe_capacity` times the night's own arguments at
       the declared step count; a hand-built record is a measurement nobody took.
    4. **`sft.train` decides**, so the capacity finding and the projected-duration refusal are the
       same ones a night gets, raised from the same place.
    5. **`write_checkpoint` seals**, with the versions block given the same backend record as the
       backend block, so the two cannot disagree about which runtime ran.
    """
    runtime = backend_module.detect() if runtime is None else runtime
    trainer = sft.trainer_for(runtime.name) if trainer is None else trainer
    dataset_digest, examples = read_selection(run)

    request = sft.TrainingRequest(
        model_path=base,
        revision=revision,
        data=run / DATA_DIR,
        adapters=destination,
        args=sft.TrainingArgs() if args is None else args,
    )
    capacity = sft.probe_capacity(
        request,
        trainer=trainer,
        headroom_bytes=sft.headroom_for(runtime.device_memory_bytes),
    )
    sft.train(request, trainer=trainer, capacity=capacity, examples=examples)

    sft.write_checkpoint(
        destination,
        repo_id=repo_id,
        revision=revision,
        dataset_digest=dataset_digest,
        run_seed=run_seed,
        args=request.args,
        tool_versions=run_ledger.tool_versions(backend=runtime),
        valid_split=valid_split,
        capacity=capacity,
        backend=runtime,
    )
    # Re-verified from disk rather than trusting what was just returned: the checkpoint's own
    # argument, applied to itself. What a later reader gets is what this asserts.
    return ArmRun(
        checkpoint=sft.verify_checkpoint(destination),
        runtime=runtime,
        capacity=capacity,
    )


def recorded(outcome: ArmRun) -> dict[str, Any]:
    """The run as plain JSON types, for an operator's console and nothing else.

    Deliberately not a report. `reports/` homes are pinned artifact-by-artifact and this door
    publishes into none of them; the arm's report home already exists and is written by hand
    under § 10.11.
    """
    return {
        "digest": outcome.checkpoint.digest,
        "directory": str(outcome.checkpoint.directory),
        "files": sorted(one.name for one in outcome.checkpoint.files),
        "backend": outcome.runtime.recorded(),
        "capacity_probe": outcome.capacity.recorded(),
    }


__all__ = [
    "DATASET_FILE",
    "DATA_DIR",
    "ArmRun",
    "NothingSelected",
    "RunIncomplete",
    "read_selection",
    "recorded",
    "run_arm",
]
