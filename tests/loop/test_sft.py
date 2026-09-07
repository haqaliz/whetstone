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

import inspect
import json
import re
import shutil
from pathlib import Path

import pytest

from whetstone.loop import backend, sft
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
        backend=backend.Backend(
            name=backend.MLX,
            library="mlx-lm",
            version="0.31.3",
            device="Apple M4 Max",
            device_memory_bytes=38654705664,
        ),
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
        backend=backend.Backend(
            name=backend.MLX,
            library="mlx-lm",
            version="0.31.3",
            device="Apple M4 Max",
            device_memory_bytes=38654705664,
        ),
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
    adapter = Path(__file__).resolve().parents[2] / "checkpoints" / "night-001" / sft.ADAPTER_FILE
    if not adapter.is_file():
        pytest.skip(
            f"no adapter at {adapter} — checkpoints/ is gitignored, so the round-trip can only "
            "run on a machine that has trained one"
        )

    # Sealed by the real writer, never hand-assembled. The bug this asserts against was invisible
    # precisely because the gate's fixtures hand-write `adapter_config.json`: production wrote a
    # bare tensor file, `load_adapters` opens that config unguarded, and the gate would have
    # raised `FileNotFoundError` on its first real candidate.
    directory = tmp_path / "sealed"
    directory.mkdir()
    shutil.copy2(adapter, directory / sft.ADAPTER_FILE)
    sft.write_checkpoint(
        directory,
        repo_id="mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",
        revision="d1e3b690c8e225d7795bccddf971ca6be68b2012",
        dataset_digest="d" * 64,
        run_seed=20260906,
        args=sft.TrainingArgs(),
        tool_versions={"python": "3.12.13"},
        valid_split="",
        capacity=sft.CapacityProbe(
            iters=sft.CAPACITY_PROBE_ITERS,
            headroom_bytes=sft.CAPACITY_HEADROOM_BYTES,
            peak_bytes=FITS,
            seconds=1.0,
        ),
        backend=backend.Backend(
            name=backend.MLX,
            library="mlx-lm",
            version="0.31.3",
            device="Apple M4 Max",
            device_memory_bytes=38654705664,
        ),
    )

    base = weights / "Qwen2.5-Coder-32B-Instruct-4bit"
    if not base.is_dir():
        pytest.skip(f"no base weights at {base}")
    loaded = mlx.load(str(base), adapter_path=str(directory))

    # Asserted by module TYPE, not by module name. `linear_to_lora_layers` replaces a module at
    # its existing key, so the path stays `q_proj` while the class becomes `LoRALinear` — a
    # search for "lora" in the names finds nothing even on a perfectly applied adapter, which is
    # what the first version of this check did and it reported a false failure.
    attached = sum(
        1 for _, module in loaded[0].named_modules() if "lora" in type(module).__name__.lower()
    )
    assert attached, (
        "WHY THIS IS A FAILURE: the checkpoint loaded and NO adapter attached. "
        "`load_weights(..., strict=False)` applies nothing rather than raising, so the gate "
        "would score the untrained base and publish it as the candidate's result — silent, and "
        "worse than a crash"
    )


def test_the_lora_config_supplies_every_key_the_library_requires() -> None:
    """AC4: the LoRA configuration handed to `mlx_lm` carries every key `mlx_lm` subscripts.

    Night #1 died here after 26.6 hours of verified rollouts. The call site passed a literal
    `{"rank": 8, "scale": 20.0}` and the pinned `mlx_lm.tuner.utils.to_lora` reads
    `config["dropout"]` **unconditionally**, so the capacity probe raised `KeyError: 'dropout'`
    before a single training step — with every draw already generated and paid for.

    The guard reads the library's own source for the keys it subscripts rather than restating a
    list here, because a list restated in a test drifts from the library the same way the literal
    drifted from it: silently, and only on the night that matters. `config.get(...)` keys are
    excluded deliberately — those the library supplies a default for, and demanding them would
    pin an interface the library does not actually require.
    """
    utils = pytest.importorskip(
        "mlx_lm.tuner.utils",
        reason=(
            "the `mlx` extra is not installed, so the library's own requirements cannot be read. "
            "This is CI's state by design (`uv sync` omits the extra); run `uv sync --extra mlx` "
            "on macOS / Apple Silicon to exercise it"
        ),
    )
    source = inspect.getsource(utils.linear_to_lora_layers)
    required = set(re.findall(r'config\["(\w+)"\]', source))
    assert required, (
        "WHY THIS IS A FAILURE: no `config[...]` subscript was found in the pinned "
        "`linear_to_lora_layers`, so this guard is asserting nothing. The library's shape changed "
        "and the guard must be re-read against it rather than left passing vacuously"
    )

    supplied = set(sft.TrainingArgs().lora_config())

    assert required <= supplied, (
        f"WHY THIS IS A FAILURE: the pinned mlx_lm subscripts {sorted(required)} on the LoRA "
        f"config and this repository supplies {sorted(supplied)}. The missing key(s) "
        f"{sorted(required - supplied)} raise `KeyError` inside the capacity probe — after every "
        "rollout of the night has been generated, and before any of them can be trained on"
    )


def test_the_lora_shape_travels_into_the_checkpoints_provenance(tmp_path: Path) -> None:
    """AC5: rank, scale and dropout are recorded, like every other value that decides training.

    The module's own contract is that *everything that decides what is trained* is fixed at
    construction and written into provenance. Rank and scale were neither: they lived as a literal
    at the call site, so two checkpoints trained at different ranks carried provenance documents
    that agreed in every field. A gate comparing them would be comparing an unrecorded variable.
    """
    checkpoint = _written(tmp_path)
    recorded = json.loads((checkpoint.directory / sft.CHECKPOINT_FILE).read_text())
    args = recorded["training_args"]

    for key in ("lora_rank", "lora_scale", "lora_dropout"):
        assert key in args, (
            f"WHY THIS IS A FAILURE: {key!r} decides what the adapter is and the checkpoint's "
            f"provenance does not name it. Got {sorted(args)}. Two candidates trained at "
            "different LoRA shapes would produce provenance documents that agree in every field"
        )


def test_the_capacity_probe_preserves_the_lora_shape(tmp_path: Path) -> None:
    """AC6: only `iters` may differ between the probe and the night, the LoRA shape included.

    `replace_iters` enumerates its fields, so a field added to `TrainingArgs` and forgotten here
    silently reverts to its default in the probe — and the probe would then measure the peak of a
    configuration the night does not run. Rank is exactly such a field: it drives adapter size,
    which is what the probe exists to measure.
    """
    shaped = sft.TrainingArgs(lora_rank=4, lora_scale=8.0, lora_dropout=0.25)
    probed = shaped.replace_iters(sft.CAPACITY_PROBE_ITERS)

    assert probed.lora_config() == shaped.lora_config(), (
        f"WHY THIS IS A FAILURE: the probe runs LoRA config {probed.lora_config()} and the night "
        f"runs {shaped.lora_config()}. A probe of a different adapter shape measures a peak for a "
        "configuration nothing trains"
    )


def test_the_datasets_are_wrapped_the_way_the_trainer_indexes_them(tmp_path: Path) -> None:
    """AC9: what reaches `lora_train` answers `dataset[i][0]`, which is how it reads lengths.

    The second defect behind night #1, found only by running the real trainer on the real base.
    `load_local_dataset` returns a bare `TextDataset` whose `__getitem__` hands back the raw
    record — `{"text": ...}` — while `iterate_batches` sorts by `len(dataset[idx][0])`. Indexing
    a dict with `0` raises `KeyError: 0`, so training died on its first batch. The library's own
    entry point never hits this because `mlx_lm/lora.py:299-300` wraps both sets in
    `CacheDataset`, which is what applies `process()` and turns each record into the
    `(tokens, offset)` pair the trainer indexes. This repository composed the library's parts by
    hand and left that wrapper out.

    Asserted by evaluating the trainer's own expression rather than by checking the wrapper's
    type: a future version that changes how it indexes would still be caught, and a wrapper
    renamed but equivalent would not fail for the wrong reason.
    """
    pytest.importorskip(
        "mlx_lm.tuner.datasets",
        reason=(
            "the `mlx` extra is not installed, so the library's dataset shapes cannot be "
            "exercised. This is CI's state by design (`uv sync` omits the extra); run "
            "`uv sync --extra mlx` on macOS / Apple Silicon"
        ),
    )

    class _Tokenizer:
        """Only what `TextDataset.process` touches."""

        eos_token_id = 2

        def encode(self, text: str) -> list[int]:
            return [1] * max(1, len(text.split()))

    data = tmp_path / "data"
    data.mkdir()
    (data / "train.jsonl").write_text(
        '{"text": "a diff and the prompt that produced it"}\n{"text": "another one"}\n'
    )

    train, valid = sft.training_datasets(data, _Tokenizer())

    assert len(train) == 2, f"WHY THIS IS A FAILURE: the loader read {len(train)} of 2 records"
    # Verbatim `mlx_lm.tuner.trainer.iterate_batches`' own `len_fn`. If this raises, training
    # dies on its first batch — after every rollout of the night has been generated and paid for.
    assert len(train[0][0]) > 0, (
        "WHY THIS IS A FAILURE: `dataset[0][0]` did not yield tokens. This is exactly the "
        "expression `iterate_batches` sorts by, so a dataset that fails it kills training at its "
        "first batch — which is where night #1's 26.6 hours went the second time"
    )
    assert not valid, (
        "WHY THIS IS A FAILURE: no `valid.jsonl` was written and the validation set is truthy, "
        "so the trainer would print a `Val loss` computed over something that is not one"
    )


def test_the_capacity_peak_counts_the_gpu_allocator_not_just_resident_bytes() -> None:
    """AC10: the probe's peak measures the memory training actually holds.

    `peak_bytes()` reads `ru_maxrss` — the process's *resident* bytes. MLX allocates through
    Metal, and those buffers are largely invisible to RSS, so the number the capacity probe
    recorded was not the number the capacity probe exists to bound. Observed on the first real
    run of the fixed trainer: `mlx_lm` reported a peak of **22.994 GB** while `peak_bytes()`
    returned **8.83 GiB** — a 2.6x under-measurement, written into a checkpoint's provenance as
    a capacity finding.

    It happened to say `fits` correctly (23 GB against a declared 30.6 GiB ceiling on a 36 GB
    machine), which is the dangerous case: the guard was wrong and the decision was right, so
    nothing surfaced it. A larger base, a longer sequence or a wider adapter would have had it
    answer `fits` on the way into swapping at three in the morning.

    **This corrects an instrument, it does not tune a threshold.** `CAPACITY_HEADROOM_BYTES`
    and `CAPACITY_PROBE_ITERS` are unchanged and still declared before any run; what changes is
    that the quantity compared against them is now the one that was always meant.

    `max` rather than a sum: on unified memory both readings draw from the same pool and the
    portion of Metal buffers that *is* resident would be double-counted by adding them. The
    weights themselves are MLX arrays, so the allocator's peak already dominates.
    """
    gib = 1024**3

    observed = sft.training_peak_bytes(mlx_peak=23 * gib, resident=9 * gib)
    assert observed == 23 * gib, (
        f"WHY THIS IS A FAILURE: the allocator peaked at 23 GiB, the process was resident at 9, "
        f"and the recorded peak is {observed / gib:.1f} GiB. A capacity guard that reports the "
        "smaller of the two answers `fits` on the way into swap"
    )
    assert sft.training_peak_bytes(mlx_peak=0, resident=9 * gib) == 9 * gib, (
        "WHY THIS IS A FAILURE: with no allocator reading available the resident bytes are the "
        "only measurement there is, and dropping them would report a peak of zero"
    )


def test_the_pinned_runtime_still_exposes_the_allocator_reading() -> None:
    """AC11: the reading AC10 depends on exists in the pinned runtime.

    Asserted rather than assumed, for the reason night #1 exists: this repository already lost a
    day to a library contract that had moved while a call site had not. If these disappear, the
    capacity probe silently falls back to resident bytes — which is the defect AC10 just closed,
    returning without a sound.
    """
    mx = pytest.importorskip(
        "mlx.core",
        reason=(
            "the `mlx` extra is not installed, so the allocator's API cannot be checked. This is "
            "CI's state by design (`uv sync` omits the extra); run `uv sync --extra mlx` on "
            "macOS / Apple Silicon"
        ),
    )
    for name in ("get_peak_memory", "reset_peak_memory"):
        assert hasattr(mx, name), (
            f"WHY THIS IS A FAILURE: the pinned mlx exposes no `{name}`, so the capacity probe "
            "cannot read what training actually allocated and falls back to resident bytes — "
            "the 2.6x under-measurement that AC10 closed"
        )
