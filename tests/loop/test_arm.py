"""The arm's driver, in the repository and under test (#34).

The portability arm's first run — this project's only completed training and the source of its
only loadable checkpoint — was driven by a `train_portability.py` written onto the Linux box
during the session. It was not in version control, so the run was not reproducible from here, and
it went **around** `sft`'s constructors rather than through them. Every defect in the resulting
provenance follows from that one fact:

| what the record says | why |
|---|---|
| `iters: 8`, `seconds: 22602` | a `CapacityProbe` hand-built with the full run's duration (#32) |
| `headroom_bytes: 32856499814` | the constant compiled in for a 36 GiB Mac, on a 15.5 GiB box |
| `"mlx-lm": "0.31.3"` | `tool_versions()` with no backend, on a host that ran PyTorch (#33) |
| `device_memory_bytes: 0` | a `Backend` record built by hand |

None of those is a hard problem, and that is the point: they are what happens when a run
reimplements the parts of the constructors it needs. So these tests assert the shape rather than
the values — that the door *calls* `probe_capacity`, that it derives its ceiling from the machine,
that the versions block and the backend block are given the same record. A test that only checked
the output would pass against a second hand-built implementation.

Nothing here trains. `sft.Trainer` is the seam `run_night` already injects, and the whole point of
that seam is that the loop's order can be asserted with no weights, no GPU and no runtime.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from whetstone.bakeoff.scoring import Outcome
from whetstone.loop import arm, backend, sft
from whetstone.loop import dataset as training
from whetstone.verify.verdict import Status

BASE = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
REVISION = "ea3f2471cf1b1f0db85067f1ef93848e38e88c25"

#: What `free -b` reports on the box the arm actually trained on.
X131_BYTES = 16637317120


def _runtime(name: str = backend.TORCH, memory: int = X131_BYTES) -> backend.Backend:
    return backend.Backend(
        name=name,
        library="torch",
        version="2.14.0+cu130",
        device="cpu",
        device_memory_bytes=memory,
    )


def _example(index: int, *, source: str = "private") -> training.Example:
    """One selected record in the shape the night writes it — hashes and verdicts only."""
    return training.Example(
        task_id=f"t-{index:02d}",
        source=source,
        attempt=1,
        seed=index,
        prompt_sha256="a" * 64,
        completion_sha256="b" * 64,
        strict=Status.PASS,
        outcome=Outcome.SOLVED,
        control=Status.PASS,
    )


def _night(tmp_path: Path, *, examples: int = 6) -> Path:
    """A night run directory in the shape `run_night` seals, and nothing more.

    Through the real writer — `dataset.build` then `write_document` — so the arm is exercised
    over a document whose seal it must verify. The hand-rolled `{"digest": ..., "examples": []}`
    shape this replaces is exactly the unchecked path `read_selection` used to read.
    """
    run = tmp_path / "night-001"
    (run / arm.DATA_DIR).mkdir(parents=True)
    (run / arm.DATA_DIR / "train.jsonl").write_text("{}\n", encoding="utf-8")
    texts = tuple(
        training.TrainingText(example=_example(index), prompt="", completion="")
        for index in range(1, examples + 1)
    )
    built = training.build(texts, denominator=examples, unverified=0)
    training.write_document(run / arm.DATASET_FILE, built)
    return run


def _trainer(seconds: float = 30.0, peak: int = 7340687360) -> sft.Trainer:
    """A trainer that writes the adapter a real one would and reports what it cost."""

    def train(request: sft.TrainingRequest) -> sft.TrainingResult:
        request.adapters.mkdir(parents=True, exist_ok=True)
        (request.adapters / sft.ADAPTER_FILE).write_bytes(b"not a tensor, deliberately")
        return sft.TrainingResult(peak_bytes=peak, seconds=seconds)

    return train


def test_the_probe_is_run_rather_than_constructed(tmp_path: Path) -> None:
    """#32's root cause: the script never called `probe_capacity` at all.

    Asserted by watching the trainer, because that is the only way to tell a probe that ran from
    a record that says one did. The declared step count reaching the trainer *before* the night's
    own count is the whole signature of a probe.
    """
    seen: list[int] = []

    def watching(request: sft.TrainingRequest) -> sft.TrainingResult:
        seen.append(request.args.iters)
        return _trainer()(request)

    outcome = arm.run_arm(
        base=tmp_path / "weights",
        repo_id=BASE,
        revision=REVISION,
        run=_night(tmp_path),
        destination=tmp_path / "checkpoint",
        run_seed=20260906,
        trainer=watching,
        runtime=_runtime(),
    )

    assert seen == [sft.CAPACITY_PROBE_ITERS, sft.TrainingArgs().iters], (
        "WHY THIS IS A FAILURE: the trainer did not see the declared probe step count followed "
        f"by the night's. Got {seen}. A run that trains without probing records a capacity "
        "finding nobody measured, which is exactly what the arm's first checkpoint carries"
    )
    assert outcome.capacity.iters == sft.CAPACITY_PROBE_ITERS
    assert outcome.capacity.seconds == 30.0, (
        f"WHY THIS IS A FAILURE: the probe recorded {outcome.capacity.seconds}s, which is not "
        "what the probe call cost. The arm's first record holds the FULL run's 22602s against "
        "iters=8 — so `projected_seconds` reads 157 hours off it and would refuse the very run "
        "that produced it"
    )


def test_the_ceiling_comes_from_the_machine_that_is_running(tmp_path: Path) -> None:
    """The arm's probe was checked against 30.6 GiB on a 15.5 GiB box, and passed on luck."""
    outcome = arm.run_arm(
        base=tmp_path / "weights",
        repo_id=BASE,
        revision=REVISION,
        run=_night(tmp_path),
        destination=tmp_path / "checkpoint",
        run_seed=20260906,
        trainer=_trainer(),
        runtime=_runtime(),
    )

    assert outcome.capacity.headroom_bytes == sft.headroom_for(X131_BYTES), (
        f"WHY THIS IS A FAILURE: the ceiling is {outcome.capacity.headroom_bytes} and this "
        f"machine holds {X131_BYTES}. A guard checking one machine against another's memory "
        "reports fit it never established"
    )
    assert outcome.capacity.headroom_bytes < sft.CAPACITY_HEADROOM_BYTES


def test_the_versions_block_names_the_runtime_that_ran(tmp_path: Path) -> None:
    """#33: the arm's provenance says `mlx-lm` on a box that ran PyTorch and never had MLX."""
    destination = tmp_path / "checkpoint"
    arm.run_arm(
        base=tmp_path / "weights",
        repo_id=BASE,
        revision=REVISION,
        run=_night(tmp_path),
        destination=destination,
        run_seed=20260906,
        trainer=_trainer(),
        runtime=_runtime(),
    )
    sealed = json.loads((destination / sft.CHECKPOINT_FILE).read_text(encoding="utf-8"))

    assert "mlx-lm" not in sealed["tool_versions"], (
        "WHY THIS IS A FAILURE: a Torch-trained checkpoint's versions block names `mlx-lm`, a "
        "library the host never loaded. The backend block beside it says `torch`, so the "
        "provenance now carries both the right answer and the wrong one with no way to tell them "
        "apart — worse than either being absent"
    )
    assert sealed["tool_versions"]["torch"] == "2.14.0+cu130"
    assert sealed["backend"]["library"] == "torch", (
        "WHY THIS IS A FAILURE: the two blocks that answer 'what produced this' disagree"
    )


def test_a_run_directory_without_a_selection_is_refused_by_name(tmp_path: Path) -> None:
    """An operator who points the door at the wrong directory is told which half is missing."""
    empty = tmp_path / "not-a-night"
    empty.mkdir()

    with pytest.raises(arm.RunIncomplete) as refused:
        arm.run_arm(
            base=tmp_path / "weights",
            repo_id=BASE,
            revision=REVISION,
            run=empty,
            destination=tmp_path / "checkpoint",
            run_seed=20260906,
            trainer=_trainer(),
            runtime=_runtime(),
        )
    assert arm.DATASET_FILE in str(refused.value)


def test_a_night_that_selected_nothing_is_refused_before_the_probe_spends_anything(
    tmp_path: Path,
) -> None:
    """`sft.train` raises the same refusal, one step and eight training steps later."""
    ran: list[int] = []

    def watching(request: sft.TrainingRequest) -> sft.TrainingResult:
        ran.append(request.args.iters)
        return _trainer()(request)

    with pytest.raises(arm.NothingSelected):
        arm.run_arm(
            base=tmp_path / "weights",
            repo_id=BASE,
            revision=REVISION,
            run=_night(tmp_path, examples=0),
            destination=tmp_path / "checkpoint",
            run_seed=20260906,
            trainer=watching,
            runtime=_runtime(),
        )
    assert ran == [], (
        "WHY THIS IS A FAILURE: the probe ran before the door noticed there was nothing to train "
        f"on, spending {ran} steps to discover it. The refusal is knowable from a JSON document"
    )


def test_an_unknown_machine_stops_the_arm_rather_than_borrowing_a_ceiling(tmp_path: Path) -> None:
    """The arm's own record carries `device_memory_bytes: 0`, hardcoded by the script.

    With the ceiling now derived from that field, a zero has to refuse — the alternative is
    silently falling back to the declared constant, which is the defect this replaced.
    """
    with pytest.raises(sft.UnknownMachine):
        arm.run_arm(
            base=tmp_path / "weights",
            repo_id=BASE,
            revision=REVISION,
            run=_night(tmp_path),
            destination=tmp_path / "checkpoint",
            run_seed=20260906,
            trainer=_trainer(),
            runtime=_runtime(memory=0),
        )


def test_the_sealed_checkpoint_is_re_verified_from_disk(tmp_path: Path) -> None:
    """What the caller is handed is what a later reader will find, not what was just written."""
    destination = tmp_path / "checkpoint"
    outcome = arm.run_arm(
        base=tmp_path / "weights",
        repo_id=BASE,
        revision=REVISION,
        run=_night(tmp_path),
        destination=destination,
        run_seed=20260906,
        trainer=_trainer(),
        runtime=_runtime(),
    )

    assert outcome.checkpoint.digest == sft.verify_checkpoint(destination).digest
    assert outcome.checkpoint.backend is not None
    assert arm.recorded(outcome)["backend"]["name"] == backend.TORCH


# --- The selection is verified, not trusted --------------------------------------------------


def test_a_v1_selection_reads_with_its_recorded_digest(tmp_path: Path) -> None:
    """v1 accepts as it always did: the recorded digest and count, no verification claimed."""
    run = _night(tmp_path, examples=3)
    document = json.loads((run / arm.DATASET_FILE).read_text(encoding="utf-8"))
    document["schema"] = training.DATASET_SCHEMA_V1
    document["digest"] = hashlib.sha256(
        json.dumps(document["examples"], indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()
    (run / arm.DATASET_FILE).write_text(json.dumps(document), encoding="utf-8")

    digest, count = arm.read_selection(run)

    assert digest == document["digest"]
    assert count == 3


def test_a_tampered_v2_selection_is_refused_by_name(tmp_path: Path) -> None:
    """The arm's reader verifies: an edited v2 selection is refused, never trained on."""
    run = _night(tmp_path, examples=2)
    document = json.loads((run / arm.DATASET_FILE).read_text(encoding="utf-8"))
    document["examples"] = []
    (run / arm.DATASET_FILE).write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(training.DatasetUnverified, match=r"claim 'examples'"):
        arm.read_selection(run)


def test_a_tampered_selection_stops_the_arm_before_the_probe(tmp_path: Path) -> None:
    """A refusal, not a traceback and not a training run: nothing is spent on a tampered file."""
    run = _night(tmp_path, examples=2)
    document = json.loads((run / arm.DATASET_FILE).read_text(encoding="utf-8"))
    document["denominator"] = 99
    (run / arm.DATASET_FILE).write_text(json.dumps(document), encoding="utf-8")
    ran: list[int] = []

    def watching(request: sft.TrainingRequest) -> sft.TrainingResult:
        ran.append(request.args.iters)
        return _trainer()(request)

    with pytest.raises(training.DatasetUnverified, match=r"claim 'denominator'"):
        arm.run_arm(
            base=tmp_path / "weights",
            repo_id=BASE,
            revision=REVISION,
            run=run,
            destination=tmp_path / "checkpoint",
            run_seed=20260906,
            trainer=watching,
            runtime=_runtime(),
        )
    assert ran == [], (
        "WHY THIS IS A FAILURE: the probe ran before the arm refused a tampered selection, "
        f"spending {ran} steps on a document nobody should train from"
    )


def test_the_arm_reads_through_the_verifying_reader_by_identity() -> None:
    """No schema-check-free `json.loads` path remains: the arm's only read is `verify_document`."""
    source = Path(arm.__file__).read_text(encoding="utf-8")

    assert "json.loads" not in source, (
        "WHY THIS IS A FAILURE: the arm parses a run document itself, so a tampered sealed "
        "selection could reach training through a path the verifying reader never sees"
    )
    assert "verify_document" in source
