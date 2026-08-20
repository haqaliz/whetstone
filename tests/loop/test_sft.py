"""The capacity probe that may stop the night, and the checkpoint P3's gate will have to trust.

Two things are being protected here, and neither is the training itself — what a LoRA fit
achieves is not this repository's claim and there is no held-out set to measure it against yet.

**The probe must be a declaration, not a description.** A step count and a headroom chosen *after*
a peak is known is a measurement designed around its own answer, which is the failure the arms'
D7 discipline exists to prevent. So the declared values travel inside the probe's own record, and
a probe above headroom raises rather than quietly shrinking something — the fallback (gradient
checkpointing, gradient accumulation) was pre-committed in the spec and is already on.

**The checkpoint must be re-verifiable.** `weights.py` re-hashes the base before every run because
a recorded digest nobody reads renders in a review exactly like a checked one, and a gitignored
directory can be rebuilt, truncated or hand-edited. A checkpoint has every one of those
properties and P3's gate will compare two of them, so the same treatment applies — asserted here
by tampering with one and requiring the refusal.

The trainer is a stub behind the injected seam. The one test that needs a real engine — the
adapter round-trip — skips loudly, naming what is missing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whetstone.loop import sft
from whetstone.loop.dataset import NO_VALID_SPLIT

#: What the stub trainer reports. Comfortably under the declared headroom, so a test asserting the
#: refusal has to ask for the refusal rather than get it by accident.
FITS = 4 * 1024**3


def _request(tmp_path: Path, **overrides: object) -> sft.TrainingRequest:
    fields: dict[str, object] = {
        "model_path": tmp_path / "weights",
        "revision": "d1e3b69",
        "data": tmp_path / "data",
        "adapters": tmp_path / "checkpoint",
        "args": sft.TrainingArgs(),
    }
    fields.update(overrides)
    return sft.TrainingRequest(**fields)  # type: ignore[arg-type]


def _trainer(peak: int = FITS) -> sft.Trainer:
    """A trainer that writes an adapter-shaped file and reports `peak`."""

    def train(request: sft.TrainingRequest) -> sft.TrainingResult:
        request.adapters.mkdir(parents=True, exist_ok=True)
        (request.adapters / request.args.adapter_file).write_bytes(b"not a tensor")
        return sft.TrainingResult(peak_bytes=peak, seconds=0.25)

    return train


def _written(tmp_path: Path, *, valid_split: str = "") -> sft.Checkpoint:
    request = _request(tmp_path)
    capacity = sft.probe_capacity(request, trainer=_trainer())
    sft.train(request, trainer=_trainer(), capacity=capacity, examples=3)
    return sft.write_checkpoint(
        request.adapters,
        repo_id="mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",
        revision=request.revision,
        dataset_digest="d" * 64,
        run_seed=20260820,
        args=request.args,
        tool_versions={"python": "3.12.0"},
        valid_split=valid_split,
        capacity=capacity,
    )


def test_the_probe_records_the_values_it_was_declared_against(tmp_path: Path) -> None:
    """A peak without its declaration is a number a later reader will measure against anything.

    Both declared values travel inside the record, so a probe run under one headroom cannot be
    quoted under another — the same reason `report.GenerationContract` is published beside every
    count rather than looked up beside it.
    """
    probe = sft.probe_capacity(_request(tmp_path), trainer=_trainer())

    assert probe.iters == sft.CAPACITY_PROBE_ITERS, (
        f"WHY THIS IS A FAILURE: the probe ran {probe.iters} steps and the declared count is "
        f"{sft.CAPACITY_PROBE_ITERS}. A step count chosen once a peak is known is a measurement "
        "designed around its own answer"
    )
    assert probe.headroom_bytes == sft.CAPACITY_HEADROOM_BYTES
    assert probe.fits is True
    recorded = probe.recorded()
    assert {"iters", "headroom_bytes", "peak_bytes", "fits"} <= set(recorded), recorded


def test_the_probe_runs_the_nights_own_arguments_at_a_shorter_step_count(tmp_path: Path) -> None:
    """A probe of some other configuration measures a configuration nothing runs.

    Only `iters` may differ — which is what makes the peak a statement about the night that is
    about to happen. In particular the pre-committed memory fallback must be **on in the probe**,
    or the probe would measure a heavier configuration than the night and refuse a night that
    would have fitted.
    """
    seen: list[sft.TrainingArgs] = []

    def watching(request: sft.TrainingRequest) -> sft.TrainingResult:
        seen.append(request.args)
        return _trainer()(request)

    request = _request(tmp_path)
    sft.probe_capacity(request, trainer=watching)

    assert len(seen) == 1 and seen[0].iters == sft.CAPACITY_PROBE_ITERS
    assert seen[0].replace_iters(request.args.iters) == request.args, (
        "WHY THIS IS A FAILURE: the probe varied something other than the step count, so its "
        f"peak describes a configuration the night does not run. Probe {seen[0]!r} vs night "
        f"{request.args!r}"
    )
    assert seen[0].grad_checkpoint and seen[0].grad_accumulation_steps > 1, (
        "WHY THIS IS A FAILURE: the pre-committed memory fallback is off in the probe. It was "
        "decided in the spec before any probe ran, precisely so that turning it on later could "
        "not be a reaction to a peak — and a probe without it measures a heavier configuration "
        "than the night it gates"
    )


def test_a_probe_above_the_declared_headroom_stops_the_training(tmp_path: Path) -> None:
    """A capacity finding, published — never a constant edited until it fits.

    The refusal names both numbers, because an operator told only "it did not fit" cannot tell a
    machine that is 5% short from one that is five times short, and those have different responses.
    """
    request = _request(tmp_path)
    capacity = sft.probe_capacity(request, trainer=_trainer(peak=sft.MACHINE_BYTES * 2))

    assert capacity.fits is False
    with pytest.raises(sft.CapacityExceeded) as refused:
        sft.train(request, trainer=_trainer(), capacity=capacity, examples=5)
    assert str(sft.CAPACITY_HEADROOM_BYTES) in str(refused.value), refused.value
    assert "gradient checkpointing" in str(refused.value), (
        "WHY THIS IS A FAILURE: the capacity refusal does not say that the fallback was already "
        "on, so the obvious next move — turn on grad checkpointing — reads as available when it "
        "has already been spent"
    )


def test_a_night_with_no_examples_trains_nothing(tmp_path: Path) -> None:
    """An adapter trained on nothing is indistinguishable, to the gate, from one that learned."""
    request = _request(tmp_path)
    capacity = sft.probe_capacity(request, trainer=_trainer())
    with pytest.raises(sft.NothingToTrain, match="raise the number of draws"):
        sft.train(request, trainer=_trainer(), capacity=capacity, examples=0)


def test_the_checkpoint_records_its_pinned_inputs_and_re_verifies(tmp_path: Path) -> None:
    """Base revision, dataset digest, run seed, training args, tool versions — and a live re-hash.

    The provenance is the only thing that says what this adapter *is*. P3's gate compares two
    checkpoints; one whose base or dataset cannot be named is one the gate's verdict cannot be
    attributed to anything.
    """
    checkpoint = _written(tmp_path)
    document = json.loads(
        (checkpoint.directory / sft.CHECKPOINT_FILE).read_text(encoding="utf-8")
    )

    assert document["base"]["revision"] == "d1e3b69" and document["dataset_digest"] == "d" * 64
    assert document["run_seed"] == 20260820 and document["tool_versions"]
    assert document["training_args"]["grad_checkpoint"] is True, document["training_args"]
    assert document["capacity_probe"]["iters"] == sft.CAPACITY_PROBE_ITERS

    reverified = sft.verify_checkpoint(checkpoint.directory)
    assert reverified.digest == checkpoint.digest, (
        "WHY THIS IS A FAILURE: a checkpoint does not survive its own verification an instant "
        "after being written, so nothing later could ever trust it"
    )


def test_an_edited_checkpoint_is_refused_rather_than_re_digested(tmp_path: Path) -> None:
    """The whole point of hashing it: the disk is checked against the record, not the reverse.

    A gitignored directory can be rebuilt, truncated or hand-edited between the night that wrote
    it and the gate that reads it, and every one of those produces a promotion decision about
    bytes nobody can identify.

    Two edits, because the two refusals say different things and the order matters. A **same
    length** edit can only be caught by the digest; a length change is caught first and reports as
    a truncated file, which is the more useful sentence for whoever has to fix it — the ordering
    `weights.verify` established for exactly that reason.
    """
    checkpoint = _written(tmp_path)
    adapter = checkpoint.directory / sft.ADAPTER_FILE
    original = adapter.read_bytes()

    adapter.write_bytes(bytes(len(original)))
    with pytest.raises(sft.CheckpointUnverified, match="sha256"):
        sft.verify_checkpoint(checkpoint.directory)

    adapter.write_bytes(original[:-1])
    with pytest.raises(sft.CheckpointUnverified, match="bytes and"):
        sft.verify_checkpoint(checkpoint.directory)


def test_a_hand_edited_digest_is_refused_because_the_document_disagrees_with_itself(
    tmp_path: Path,
) -> None:
    """Editing the top-level digest to match a tampered file must not rescue the checkpoint."""
    checkpoint = _written(tmp_path)
    document = checkpoint.directory / sft.CHECKPOINT_FILE
    payload = json.loads(document.read_text(encoding="utf-8"))
    payload["digest"] = "0" * 64
    document.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(sft.CheckpointUnverified, match="disagrees with itself"):
        sft.verify_checkpoint(checkpoint.directory)


def test_a_checkpoint_trained_without_validation_says_so_verbatim(tmp_path: Path) -> None:
    """The degenerate-split rule reaches the artefact, in the pre-committed words.

    A checkpoint silent on the question reads exactly like a validated one, which is the failure
    the rule exists for. The sentence is compared as a constant rather than by substring so that
    a second, softer wording cannot appear beside it.
    """
    checkpoint = _written(tmp_path, valid_split=NO_VALID_SPLIT)
    document = json.loads(
        (checkpoint.directory / sft.CHECKPOINT_FILE).read_text(encoding="utf-8")
    )

    assert document["validation"] == NO_VALID_SPLIT, (
        "WHY THIS IS A FAILURE: a checkpoint trained without a validation split does not state "
        f"it verbatim. Got {document['validation']!r}, expected {NO_VALID_SPLIT!r}"
    )


def test_a_checkpoint_with_no_files_is_refused(tmp_path: Path) -> None:
    """A provenance over nothing verifies nothing and succeeds — the shape of every silent hole."""
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(sft.CheckpointUnverified, match="verify nothing"):
        sft.write_checkpoint(
            empty,
            repo_id="x",
            revision="y",
            dataset_digest="z",
            run_seed=1,
            args=sft.TrainingArgs(),
            tool_versions={},
            valid_split="",
            capacity=sft.probe_capacity(_request(tmp_path), trainer=_trainer()),
        )


def test_the_emitted_adapter_loads_against_the_pinned_base(tmp_path: Path) -> None:
    """AC3b: a stranded adapter is refused as a candidate, not merely hashed.

    An adapter that hashes perfectly and cannot be loaded — a revision drift, a format change in
    the library — is a candidate the gate would compare and could never run. Proving otherwise
    needs a real engine and real weights, so this skips loudly rather than passing vacuously: a
    silently-skipped round-trip is a green suite in which nothing was ever loaded.
    """
    mlx = pytest.importorskip(
        "mlx_lm",
        reason=(
            "the `mlx` extra is not installed, so no adapter can be loaded here. This is CI's "
            "state by design (`uv sync` omits the extra); run `uv sync --extra mlx` on macOS / "
            "Apple Silicon to exercise it"
        ),
    )
    weights = Path(__file__).resolve().parents[2] / "weights"
    if not weights.is_dir():
        pytest.skip(
            f"no local weights at {weights} — the base snapshots are gitignored and fetched by "
            "the operator, so the round-trip can only run on the machine that holds them"
        )
    assert hasattr(mlx, "load"), (
        "WHY THIS IS A FAILURE: the pinned mlx-lm exposes no `load`, so the adapter round-trip "
        "cannot be performed at all and the checkpoint's loadability is unasserted"
    )
