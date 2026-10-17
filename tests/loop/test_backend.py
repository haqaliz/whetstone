"""Which runtime produced a run — detected, refused when ambiguous, and recorded.

The failure this prevents is not a crash. It is two nights whose evidence looks identical and
whose numbers are not comparable.

Every GPU-touching surface in this repository is already behind an injected seam
(`sft.Trainer`, `run.Engine`), so a second backend is additive. What is *not* yet additive is
the record: `ledger.tool_versions()` hardcodes `"mlx-lm": PINNED_MLX_LM`, so a night produced by
a Torch backend would write a ledger naming a runtime it never loaded. A checkpoint carrying
that ledger's dataset digest would then be compared by the promotion gate against a candidate
from the other backend, and the gate would be measuring the backend rather than the improvement
— which is the one thing the never-regress rule exists to prevent.

So the backend is a **pinned input**, in the sense `PREREGISTRATION.md` already uses for the
base weights and the generation contract: detected once, recorded beside them, and never
inferred by a later reader from a field that happens to be lying.

**Detection consults, it never guesses.** A machine with both runtimes installed is a machine
where "which one ran" has no defensible default, so it is a named refusal rather than a silent
pick. That is the same shape as `run --night` refusing to be implied.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from whetstone.loop import backend


def test_the_backend_is_detected_rather_than_assumed() -> None:
    """AC1: what this machine actually runs is read off the machine, not declared in a constant.

    Skips loudly without the extra rather than passing vacuously: a green suite in which nothing
    was ever detected would assert only that the module imports.
    """
    pytest.importorskip(
        "mlx_lm",
        reason=(
            "no runtime extra is installed, so there is nothing to detect. This is CI's state by "
            "design (`uv sync` omits the extras); run `uv sync --extra mlx` on macOS / Apple "
            "Silicon"
        ),
    )
    detected = backend.detect()

    assert detected.name == backend.MLX, (
        f"WHY THIS IS A FAILURE: the `mlx` extra is installed and detection answered "
        f"{detected.name!r}. A run that misnames its own runtime writes evidence that cannot be "
        "compared against anything"
    )
    assert detected.library == "mlx-lm"
    assert detected.version, "WHY THIS IS A FAILURE: the runtime's version is unrecorded"
    assert detected.device, (
        "WHY THIS IS A FAILURE: no device was named. Two runs of the same backend on different "
        "hardware are not interchangeable, and a record silent on the device cannot say so"
    )
    assert detected.device_memory_bytes > 0, (
        "WHY THIS IS A FAILURE: the device's memory is recorded as zero, so a later reader "
        "cannot tell whether a capacity finding was measured with room to spare or without"
    )


def test_no_runtime_is_a_named_refusal_never_a_default() -> None:
    """AC2: with nothing installed, detection refuses by name instead of picking one.

    A default here would be the worst kind: the run would proceed, produce evidence, and label
    it with a runtime that was never loaded.
    """
    with pytest.raises(backend.NoBackend) as refusal:
        backend.choose(installed=())

    assert "mlx" in str(refusal.value) and "torch" in str(refusal.value), (
        "WHY THIS IS A FAILURE: the refusal does not say what could be installed to satisfy it, "
        f"so an operator cannot act on it. Got {str(refusal.value)!r}"
    )


def test_two_runtimes_is_a_refusal_rather_than_a_silent_choice() -> None:
    """AC3: ambiguity is refused, and resolved only by saying which one — never by an order.

    A machine with both installed has no defensible default. Picking the first in some list
    would make the answer depend on the order a tuple happens to be written in, and two runs on
    that machine could then differ in backend while their evidence agreed in every field.
    """
    both = (backend.MLX, backend.TORCH)

    with pytest.raises(backend.AmbiguousBackend) as refusal:
        backend.choose(installed=both)
    assert backend.MLX in str(refusal.value) and backend.TORCH in str(refusal.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name the candidates it could not choose "
        f"between. Got {str(refusal.value)!r}"
    )

    assert backend.choose(installed=both, prefer=backend.MLX) == backend.MLX, (
        "WHY THIS IS A FAILURE: an explicit choice was not honoured, so an operator on a machine "
        "with both runtimes has no way to run at all"
    )


def test_an_unknown_preference_is_refused_rather_than_ignored() -> None:
    """AC4: asking for a runtime that is not installed fails loudly.

    Ignoring the preference and falling back would run the *other* backend while the operator
    believed they had selected one — the silent-substitution failure, applied to the one input
    that decides comparability.
    """
    with pytest.raises(backend.NoBackend) as refusal:
        backend.choose(installed=(backend.MLX,), prefer=backend.TORCH)

    assert backend.TORCH in str(refusal.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name what was asked for. Got "
        f"{str(refusal.value)!r}"
    )


def test_detection_consults_the_import_system_without_importing_the_runtime() -> None:
    """AC5: finding out what is installed must not load 18 GiB of runtime to answer.

    `installed()` runs on every night, and on the reward path's own machine. Importing `torch`
    or `mlx` to answer "is it there" would pull an inference stack into a process that may have
    no business holding one — and would make the answer depend on whether the library's import
    happens to succeed, rather than on whether it is present.
    """
    seen: list[str] = []
    real = importlib.util.find_spec

    def recording(name: str, *args: Any, **kwargs: Any) -> Any:
        seen.append(name)
        return real(name, *args, **kwargs)

    original = importlib.util.find_spec
    importlib.util.find_spec = recording  # type: ignore[assignment]
    try:
        backend.installed()
    finally:
        importlib.util.find_spec = original  # type: ignore[assignment]

    assert "mlx_lm" in seen and "torch" in seen, (
        f"WHY THIS IS A FAILURE: `installed()` did not ask the import system about both "
        f"runtimes. It asked about {seen!r}, so it is either importing them or answering from a "
        "hardcoded list that cannot notice an installation"
    )


def test_the_record_is_json_plain_and_distinguishes_the_backends() -> None:
    """AC6: the record round-trips into a ledger, and two backends never compare equal.

    The gate's refusal to compare across backends is only possible if the two records differ.
    Asserted here rather than assumed at the call site, because "these two are different" is the
    entire property the ledger field exists to carry.
    """
    one = backend.Backend(
        name=backend.MLX, library="mlx-lm", version="0.31.3", device="Apple M4 Max",
        device_memory_bytes=38654705664,
    )
    other = backend.Backend(
        name=backend.TORCH, library="torch", version="2.5.1",
        device="NVIDIA A100-SXM4-40GB", device_memory_bytes=42949672960,
    )

    assert one != other, (
        "WHY THIS IS A FAILURE: two different runtimes compare equal, so a gate cannot refuse "
        "to score a candidate from one against an incumbent from the other"
    )
    recorded = one.recorded()
    assert all(v is None or isinstance(v, (str, int)) for v in recorded.values()), (
        f"WHY THIS IS A FAILURE: the record holds a value a JSON ledger cannot carry: {recorded!r}"
    )
    assert set(recorded) == {
        "name", "library", "version", "device", "device_memory_bytes", "precision",
    }, (
        f"WHY THIS IS A FAILURE: the recorded shape is not the declared one. Got {sorted(recorded)}"
    )


def test_the_precision_is_recorded_and_defaults_to_none() -> None:
    """AC3: the record names the dtype, and an undeclared one is an explicit None, not a guess.

    Precision is what makes a bf16 checkpoint and an fp32 one non-comparable — the
    non-comparability § 13 names. Defaulting to a string would invent a precision for every
    backend that declares none, so the absence is recorded as `None` and the gate reads it as
    part of the record rather than inferring it from the device.
    """
    undeclared = backend.Backend(
        name=backend.MLX, library="mlx-lm", version="0.31.3", device="Apple M4 Max",
        device_memory_bytes=38654705664,
    )
    assert undeclared.recorded()["precision"] is None, (
        "WHY THIS IS A FAILURE: a backend that declares no precision must record `null`, not a "
        f"fabricated dtype. Got {undeclared.recorded()['precision']!r}"
    )

    declared = backend.Backend(
        name=backend.TORCH, library="torch", version="2.5.1", device="cpu",
        device_memory_bytes=8589934592, precision="bfloat16",
    )
    assert declared.recorded()["precision"] == "bfloat16", (
        f"WHY THIS IS A FAILURE: the declared precision did not survive into the record. Got "
        f"{declared.recorded()['precision']!r}"
    )


def test_the_record_carries_no_draw_budget() -> None:
    """AC1.5: the draw budget is not a comparability key, and this is the guard that keeps it so.

    **A documented regression guard, not a RED: there is no currently-reachable failure.** The
    shipped `Backend` carries no draw-budget field, so this passes on the tree as it stands. Its
    value is prospective: it fails the day a future implementer mirrors the § 10.18 `precision`
    addition — which deliberately *does* enter the `Backend` record so the gate can refuse a
    cross-value pair — and moves the draw budget (`K` / `draws`) in with it.

    That mirroring would be the wrong direction. `raise-k` moves `K` from 8 to 16, and the gate's
    whole-dict backend comparison must **permit** a higher-`K` candidate against a lower-`K`
    incumbent, because that comparison *is* the experiment. A draw budget in the `Backend` record
    would make `refuse_cross_backend` refuse exactly that pair, and the unit could never be
    measured.
    """
    recorded = backend.Backend(
        name=backend.MLX, library="mlx-lm", version="0.31.3", device="Apple M4 Max",
        device_memory_bytes=38654705664,
    ).recorded()

    assert "draws" not in recorded, (
        "WHY THIS IS A FAILURE: `draws` reached the backend record. The draw budget is not a "
        "comparability key — a higher-K candidate against a lower-K incumbent is the raise-k "
        f"experiment the gate must permit. Got {sorted(recorded)}"
    )
    assert "k" not in recorded, (
        "WHY THIS IS A FAILURE: `k` reached the backend record. The gate compares the whole "
        "backend dict, so a draw budget here would refuse the very pair the raise-k experiment "
        f"is. Got {sorted(recorded)}"
    )


def test_a_precision_mismatch_is_refused_and_a_match_is_not() -> None:
    """AC5: the gate refuses a bf16-vs-fp32 pair through the existing whole-dict `==`.

    This is § 13's non-comparability made enforceable, and it needs no gate-logic change: the two
    records already differ, so `refuse_cross_backend` refuses them for the same reason it refuses
    two runtimes. Two records identical in every field, precision included, stay comparable — and
    the untrained incumbent (`None`) keeps its exemption.
    """
    from whetstone.loop import gate

    bf16 = backend.Backend(
        name=backend.TORCH, library="torch", version="2.5.1", device="cpu",
        device_memory_bytes=8589934592, precision="bfloat16",
    ).recorded()
    fp32 = backend.Backend(
        name=backend.TORCH, library="torch", version="2.5.1", device="cpu",
        device_memory_bytes=8589934592, precision="float32",
    ).recorded()

    with pytest.raises(gate.MismatchedBackend) as refusal:
        gate.refuse_cross_backend(candidate=bf16, incumbent=fp32)
    assert "torch" in str(refusal.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name the runtime it declined to compare. "
        f"Got {str(refusal.value)!r}"
    )

    gate.refuse_cross_backend(candidate=bf16, incumbent=bf16)
    gate.refuse_cross_backend(candidate=bf16, incumbent=None)


def test_describe_torch_records_the_declared_precision() -> None:
    """AC2: the recorded precision is the one the chosen device causes, not a second opinion.

    `DEVICE_PRECISION[torch_device()]` is the same lookup `torch_trainer` and `_load_torch` cast
    the model to, so the checkpoint names the dtype that actually trained it — a record derived
    independently would be free to disagree with the run it describes.

    Skipped loudly without the extra: a green suite in which the Torch path was never described
    would assert only that this test was collected.
    """
    if importlib.util.find_spec("torch") is None:
        pytest.skip(
            "torch is not installed, so there is no device and no declared precision to record. "
            "This is CI's state by design (`uv sync` omits the extras); run `uv sync --extra torch`"
        )

    from whetstone.loop import torch_runtime

    described = backend._describe_torch("torch")
    assert described.precision == torch_runtime.DEVICE_PRECISION[torch_runtime.torch_device()], (
        f"WHY THIS IS A FAILURE: the Torch backend recorded precision {described.precision!r}, "
        f"not the declared {torch_runtime.DEVICE_PRECISION[torch_runtime.torch_device()]!r} the "
        "trainer casts the model to, so the checkpoint would name a dtype that did not train it"
    )


def test_describe_mlx_records_no_precision() -> None:
    """AC2: MLX names no precision, because this module is not told one.

    Leaving it `None` is deliberate, not an omission: MLX's dtype is decided downstream and
    declared nowhere here, and inventing a value would put an unverified claim into evidence a
    reader trusts. The absence is recorded as `null`, which the gate reads as part of the record.

    Skipped loudly without the extra, the `test_the_backend_is_detected_rather_than_assumed` shape.
    """
    if importlib.util.find_spec("mlx_lm") is None:
        pytest.skip(
            "mlx-lm is not installed, so there is no MLX backend to describe. This is CI's state "
            "by design (`uv sync` omits the extras); run `uv sync --extra mlx` on macOS / Apple "
            "Silicon"
        )

    described = backend._describe_mlx("mlx-lm")
    assert described.precision is None, (
        f"WHY THIS IS A FAILURE: the MLX backend recorded precision {described.precision!r}, but "
        "nothing in this module asks MLX for one — a value here is an invented claim about a run"
    )


def test_the_nights_ledger_records_which_runtime_produced_it(tmp_path: Path) -> None:
    """AC7: the run's evidence names its own backend, so a reader never has to infer it.

    Without this the ledger is actively misleading rather than merely silent:
    `ledger.tool_versions()` writes `"mlx-lm": <pinned>` unconditionally, so a Torch-produced
    night would record a library it never loaded. A field that is wrong reads, in review,
    exactly like a field that is right.
    """
    from whetstone.loop import ledger as run_ledger

    written = run_ledger.write(tmp_path / "ledger.json", _ledger())
    recorded = run_ledger.read(written)

    assert "backend" in recorded, (
        f"WHY THIS IS A FAILURE: the ledger does not name the runtime that produced it. Got "
        f"{sorted(recorded)}. Two nights from different backends are not comparable, and "
        "evidence that cannot say which one ran cannot be compared with anything"
    )
    assert recorded["backend"]["name"] == backend.MLX
    assert recorded["backend"]["device"] == "Apple M4 Max"


def test_the_run_ledger_records_the_precisions_backend(tmp_path: Path) -> None:
    """AC4: the night's ledger names the dtype, so a bf16 run and an fp32 run are distinguishable.

    The ledger already names the runtime; the precision completes the non-comparability key, and
    it reaches the document through the same single `recorded()` writer the checkpoint uses — so
    the two pieces of evidence cannot disagree about the dtype the run used.
    """
    from dataclasses import replace

    from whetstone.loop import ledger as run_ledger

    bf16 = backend.Backend(
        name=backend.TORCH, library="torch", version="2.5.1", device="cpu",
        device_memory_bytes=8589934592, precision="bfloat16",
    )
    written = run_ledger.write(tmp_path / "ledger.json", replace(_ledger(), backend=bf16))
    recorded = run_ledger.read(written)

    assert recorded["backend"]["precision"] == "bfloat16", (
        f"WHY THIS IS A FAILURE: the ledger does not carry the precision that produced the run. "
        f"Got {recorded['backend'].get('precision')!r}. A bf16 night and an fp32 night would then "
        "be indistinguishable evidence for two runs the gate must not compare"
    )


def test_the_ledger_schema_moved_when_the_field_was_added(tmp_path: Path) -> None:
    """AC8: a reader can rely on `backend` being there, which means the schema version moved.

    Adding a field under the old version would make its presence optional in practice — a
    reader could not tell a night that recorded no backend from one written before the field
    existed. The whole value of the field is that its absence is impossible.
    """
    from whetstone.loop import ledger as run_ledger

    assert run_ledger.LEDGER_SCHEMA != "whetstone-run/1", (
        "WHY THIS IS A FAILURE: a required field was added and the schema still declares "
        "`whetstone-run/1`, so two documents with the same schema string disagree about which "
        "fields exist"
    )
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps({"schema": "whetstone-run/1", "run_id": "night-000"}))
    with pytest.raises(run_ledger.LedgerUnreadable):
        run_ledger.read(stale)


def test_the_checkpoint_records_which_runtime_trained_it(tmp_path: Path) -> None:
    """AC9: the candidate carries its backend, because the gate compares candidates.

    The ledger records the night; the checkpoint is what outlives it. P3's gate loads two
    checkpoints and scores one against the other, and a candidate that cannot say which runtime
    produced it is one the gate cannot refuse to mis-compare. The provenance is the only
    document that travels with the adapter, so the field has to be in it and not only in the run
    directory the adapter came from.
    """
    from whetstone.loop import sft

    directory = tmp_path / "checkpoint"
    directory.mkdir()
    (directory / sft.ADAPTER_FILE).write_bytes(b"not a tensor, deliberately")
    runtime = backend.Backend(
        name=backend.MLX, library="mlx-lm", version="0.31.3",
        device="Apple M4 Max", device_memory_bytes=38654705664,
    )

    sft.write_checkpoint(
        directory,
        repo_id="mlx-community/base",
        revision="d1e3b69",
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
        backend=runtime,
    )

    recorded = json.loads((directory / sft.CHECKPOINT_FILE).read_text())
    assert recorded.get("backend") == runtime.recorded(), (
        f"WHY THIS IS A FAILURE: the checkpoint's provenance does not name the runtime that "
        f"trained it. Got {recorded.get('backend')!r}. The gate compares two of these, and two "
        "candidates from different backends differ by the backend before they differ by anything "
        "the night did"
    )


def test_the_checkpoint_records_the_precisions_backend(tmp_path: Path) -> None:
    """AC4: the candidate's provenance names the dtype, and still verifies with the extra key.

    The gate compares two checkpoints; a bf16 candidate and an fp32 incumbent differ by the dtype
    before anything the night did, so the provenance has to carry it. The precision is a nested
    key inside `backend`, so the checkpoint's schema does not move — the re-hash must tolerate it,
    which is what calling `verify_checkpoint` here pins.
    """
    from whetstone.loop import sft

    directory = tmp_path / "checkpoint"
    directory.mkdir()
    (directory / sft.ADAPTER_FILE).write_bytes(b"not a tensor, deliberately")
    runtime = backend.Backend(
        name=backend.TORCH, library="torch", version="2.5.1", device="cpu",
        device_memory_bytes=8589934592, precision="bfloat16",
    )

    sft.write_checkpoint(
        directory,
        repo_id="Qwen/Qwen2.5-Coder-0.5B",
        revision="d1e3b69",
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
        backend=runtime,
    )

    recorded = json.loads((directory / sft.CHECKPOINT_FILE).read_text())
    assert recorded["backend"]["precision"] == "bfloat16", (
        f"WHY THIS IS A FAILURE: the checkpoint's provenance does not name the dtype that trained "
        f"it. Got {recorded['backend'].get('precision')!r}. A bf16 candidate and an fp32 incumbent "
        "are not comparable, and evidence that cannot say which dtype it was cannot be refused"
    )
    assert sft.verify_checkpoint(directory).backend == runtime.recorded(), (
        "WHY THIS IS A FAILURE: adding the nested `precision` key moved the checkpoint's digest or "
        "was rejected by the re-hash, so a checkpoint that records its dtype no longer verifies"
    )


def test_the_gate_refuses_to_score_across_backends(tmp_path: Path) -> None:
    """AC10: two checkpoints from different runtimes are not comparable, and the gate says so.

    This is the reason every field above exists. The gate promotes a candidate over an incumbent
    on a held-out set, and never-regress is only meaningful if the difference it measures is the
    night's. Two adapters from different runtimes differ by kernels and by a different
    quantisation of the same weights *before* they differ by anything training did — so a gate
    that scored them would attribute the backend's difference to the improvement and promote on
    it. Refused rather than flagged: a warning beside a promotion still promotes.

    An **untrained** incumbent is exempt and must stay so — nothing trained it, so it has no
    backend to disagree about, and the untrained-incumbent dispatch is how a first night is
    gated at all.
    """
    from whetstone.loop import gate

    mlx_side = backend.Backend(
        name=backend.MLX, library="mlx-lm", version="0.31.3",
        device="Apple M4 Max", device_memory_bytes=38654705664,
    ).recorded()
    cuda_side = backend.Backend(
        name=backend.TORCH, library="torch", version="2.5.1",
        device="NVIDIA A100-SXM4-40GB", device_memory_bytes=42949672960,
    ).recorded()

    with pytest.raises(gate.MismatchedBackend) as refusal:
        gate.refuse_cross_backend(candidate=mlx_side, incumbent=cuda_side)
    assert backend.MLX in str(refusal.value) and backend.TORCH in str(refusal.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name the two runtimes it declined to "
        f"compare, so an operator cannot tell what went wrong. Got {str(refusal.value)!r}"
    )

    gate.refuse_cross_backend(candidate=mlx_side, incumbent=mlx_side)
    gate.refuse_cross_backend(candidate=mlx_side, incumbent=None)


def _ledger() -> Any:
    """The suite's own populated ledger, reused rather than rebuilt.

    A second hand-written `Ledger(...)` here would drift from the real one the day a field is
    added, and the drift would look like this test passing.
    """
    from loop.test_run_ledger import _ledger as built

    return built()


def test_a_backend_name_never_carries_an_accelerator() -> None:
    """#30: the name says which runtime; `device` says which chip. Guarded, not merely intended.

    `TORCH_CUDA = "torch-cuda"` made a CPU-only Linux box and an Apple Silicon Mac both record
    `cuda`. Nothing broke — the name's only job is comparability and it did that — but `Backend`
    exists to be read by a person months later, and a record of a CPU run that says `cuda` is a
    record that lies about the one thing it was added to state. The convention that replaced it
    is only worth having if something checks it.
    """
    for name in backend._RUNTIMES:
        assert not any(chip in name for chip in backend.ACCELERATORS), (
            f"WHY THIS IS A FAILURE: the backend name {name!r} contains an accelerator. The name "
            "is the comparability key — which runtime generated this — and the chip belongs in "
            "`Backend.device`, which is filled from the device itself. A name carrying both is "
            "wrong on every host whose chip is not the one spelled into the constant"
        )
    assert backend.TORCH == "torch"
