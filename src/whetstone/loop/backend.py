"""Which runtime produced a run: detected from the machine, refused when ambiguous, recorded.

Every GPU-touching surface here is already behind an injected seam — `sft.Trainer` and
`run.Engine` are both plain callables passed in, and the whole suite runs with no runtime, no
weights and no GPU. So a second backend (Torch/CUDA beside MLX/Metal) is **additive code**, not a
rewrite. This module is the part that is *not* additive: the record.

**The problem a second backend creates is not portability, it is comparability.** Two nights can
agree in every recorded field — same base, same seed, same task set, same generation contract —
and still not be comparable, because different kernels and a different quantisation of the same
weights do not produce the same rollouts. The promotion gate scores a candidate against an
incumbent; if those came from different runtimes, it measures the runtime and calls the
difference an improvement. Never-regress exists precisely to prevent that, so the backend has to
be a **pinned input** in the sense `PREREGISTRATION.md` already uses for the base weights: fixed
before the run, written into the evidence, and never re-derived afterwards by a reader.

It also closes a live inaccuracy. `ledger.tool_versions()` records `"mlx-lm": PINNED_MLX_LM`
unconditionally, so a night produced by any other runtime would write a ledger naming a library
it never loaded. That field predates the possibility of a second backend; this record is what
makes it answerable rather than assumed.

**Detection consults the import system and never imports a runtime.** `installed()` runs
wherever a night starts, and pulling an inference stack into a process merely to ask whether one
is present is both expensive and wrong — it would make "is it installed" depend on whether the
import happens to succeed. `importlib.util.find_spec` answers the question it is actually asking.

**Ambiguity is refused, never defaulted.** On a machine with both runtimes there is no
defensible default: picking the first of a tuple makes the answer depend on the order somebody
wrote it in, and two runs on that machine could then differ in backend while their evidence
agreed in every field. The operator says which, the same way `run --night` refuses to be implied.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Any

#: MLX / Metal on Apple Silicon. The runtime the roadmap locked and the only one implemented.
MLX = "mlx"

#: Torch. The **runtime**, and nothing about the accelerator: the comparability key answers
#: "which library generated this", and which chip it ran on is `Backend.device`'s answer, not a
#: second half of this string. The first spelling here was `torch-cuda`, which made a CPU-only
#: Linux box and an Apple Silicon Mac both record `cuda` — a record read by a human months later
#: saying the opposite of what happened. Evidence already written keeps its old name (see
#: `fuse.fuser_for`); nothing rewrites a checkpoint to agree with a later constant.
TORCH = "torch"

#: The accelerator names that may appear in `Backend.device` and must never appear in a backend
#: *name*. Guarded rather than merely intended: the previous defect was exactly a name that had
#: absorbed one of these, and a convention nothing checks is a convention that decays.
ACCELERATORS = ("cuda", "mps", "cpu", "metal", "rocm", "xpu")

#: The import name each backend is detected by, and the distribution it belongs to. The import
#: name is what `find_spec` takes; the distribution is what a person types to install it.
_RUNTIMES: dict[str, tuple[str, str]] = {
    MLX: ("mlx_lm", "mlx-lm"),
    TORCH: ("torch", "torch"),
}


class NoBackend(RuntimeError):
    """No runtime is installed, or the one asked for is not.

    Raised rather than defaulted. A default would let a run proceed, produce evidence, and label
    it with a runtime that was never loaded — which is worse than not running, because the
    evidence outlives the mistake and reads as fact.
    """


class AmbiguousBackend(RuntimeError):
    """More than one runtime is installed and none was named.

    Raised rather than resolved by an ordering. Which runtime ran decides whether a night's
    numbers may be compared with another's, and an answer that depends on the order of a literal
    in this file is not an answer.
    """


@dataclass(frozen=True)
class Backend:
    """One runtime, as a run records it. Frozen, so what is passed is what is written."""

    #: `MLX` or `TORCH` — the comparability key. Two runs with different names are not
    #: comparable, whatever else they agree on.
    name: str

    #: The library actually loaded, so the record does not depend on `tool_versions()` being
    #: right about which one that was.
    library: str

    #: Its installed version. A runtime's minor release can change generation; night #1 was lost
    #: to exactly such a change in an unpinned dependency.
    version: str

    #: What the run executed on, as the runtime itself reports it — "Apple M4 Max",
    #: "NVIDIA A100-SXM4-40GB". Two runs of the same backend on different hardware are not
    #: interchangeable, and a record silent on the device cannot say so.
    device: str

    #: The device's total memory. Recorded beside the capacity probe's peak so a later reader can
    #: tell a finding measured with room to spare from one measured without.
    device_memory_bytes: int

    def recorded(self) -> dict[str, Any]:
        """The record as plain JSON types, for the ledger and the checkpoint's provenance.

        Written field by field rather than by `asdict`, the `ledger._payload` rule: a field added
        later would otherwise reach the document with no reader for it, and a schema change would
        round-trip lossily instead of failing.
        """
        return {
            "name": self.name,
            "library": self.library,
            "version": self.version,
            "device": self.device,
            "device_memory_bytes": self.device_memory_bytes,
        }


def _present() -> tuple[str, ...]:
    """The backends whose runtime is importable here, asked of the import system, in declared order.

    `find_spec` rather than `import`: this runs wherever a night starts, and importing a runtime
    to discover whether it exists would both cost gigabytes and answer a different question —
    "does its import succeed" rather than "is it present".

    The private spelling is what `detect` calls, so the public `installed()` below can keep the
    name the parameter also uses without either shadowing the other.
    """
    return tuple(
        name for name, (module, _) in _RUNTIMES.items() if importlib.util.find_spec(module)
    )


def installed() -> tuple[str, ...]:
    """The backends whose runtime is importable here. See `_present`."""
    return _present()


def detect(*, installed: tuple[str, ...] | None = None, prefer: str | None = None) -> Backend:
    """The one backend this run uses, described — the choice followed by the load.

    Split in two on purpose. `choose` decides *which*, and imports nothing; `describe` loads the
    winner to read its version and device. Keeping them apart is what lets every refusal be
    asserted on a machine with no runtime at all, which is CI's state by design — and CI is
    where this split was learned, by a first version that made the choice and the import
    inseparable and so could only be tested where a runtime happened to be installed.
    """
    return describe(choose(installed=installed, prefer=prefer))


def choose(*, installed: tuple[str, ...] | None = None, prefer: str | None = None) -> str:
    """Which backend this run uses, as a name — or a named refusal. Imports no runtime.

    `installed` is injected for the reason every other seam here is: the refusals are properties
    of this function and asserting them must not require installing two inference stacks.
    """
    present = _present() if installed is None else installed

    if prefer is not None:
        if prefer not in present:
            raise NoBackend(
                f"the backend {prefer!r} was asked for and is not installed here (found: "
                f"{list(present)}). Refused rather than substituted: running the other runtime "
                "while the operator believes they selected this one produces evidence labelled "
                "with a backend that never ran"
            )
        return prefer

    if not present:
        raise NoBackend(
            "no runtime is installed, so there is nothing to run and nothing to record. Install "
            f"one: `uv sync --extra mlx` for {MLX} on Apple Silicon, or the {TORCH} extra for "
            "CUDA, MPS or CPU. A default here would label a run with a runtime it never loaded"
        )
    if len(present) > 1:
        raise AmbiguousBackend(
            f"more than one runtime is installed ({list(present)}) and none was named. Which one "
            "ran decides whether this run's numbers may be compared with another's, so it is "
            "stated rather than defaulted — pass one of "
            f"{sorted(_RUNTIMES)} (e.g. prefer={MLX!r}). Choosing by the order of a list would "
            "make the answer depend on how this file happens to be written"
        )
    return present[0]


def describe(name: str) -> Backend:
    """Load the named runtime far enough to record what it is and what it is running on.

    The only place a runtime is imported, and it happens **after** `choose` has decided — so a
    machine with two installed never loads the one it did not pick, and a test of the choice
    never loads either.
    """
    library = _RUNTIMES[name][1]
    if name == MLX:
        return _describe_mlx(library)
    return _describe_torch(library)


def _describe_mlx(library: str) -> Backend:
    """MLX's own report of the Metal device, not a guess derived from the platform string."""
    from importlib.metadata import version as installed_version

    import mlx.core as mx

    info = mx.device_info()
    return Backend(
        name=MLX,
        library=library,
        version=installed_version(library),
        device=str(info.get("device_name", "unknown Metal device")),
        device_memory_bytes=int(info.get("memory_size", 0)),
    )


def _describe_torch(library: str) -> Backend:
    """Torch's own report of whatever it is running on — CUDA, MPS or CPU.

    **The device is asked of `torch_runtime.torch_device()` rather than probed again here.** Two
    functions answering "which device" is how a record comes to disagree with the run it
    describes: this module once refused every non-CUDA host outright, while the trainer beside it
    happily trained on the CPU. The refusal was written against a 32B base, where a CPU run really
    would look like progress for days — but it was spelled as a fact about the device, so it also
    refused the small-base portability arm (§ 10.11), which then produced this project's only
    real checkpoint by going around it. A judgement about how long a run will take belongs where
    the run's cost is measured; see `sft.projected_seconds`.
    """
    from importlib.metadata import version as installed_version

    import torch

    from whetstone.loop.torch_runtime import torch_device

    device = torch_device()
    return Backend(
        name=TORCH,
        library=library,
        version=installed_version(library),
        device=device,
        device_memory_bytes=_torch_device_memory(torch, device),
    )


def _torch_device_memory(torch: Any, device: str) -> int:
    """How much memory the chosen device has, asked of the device rather than declared.

    Zero is never returned as "unknown but proceed": `sft.headroom_for` refuses a zero, because
    the alternative is what already happened once — a probe on a 15.5 GiB Linux box checked
    against a 30.6 GiB ceiling derived from the author's Mac, which passed on luck rather than on
    fit.
    """
    if device == "cuda":
        return int(torch.cuda.get_device_properties(0).total_memory)
    if device == "mps":
        # Unified memory: what MPS will hand out, not what the machine physically holds.
        recommended = getattr(torch.mps, "recommended_max_memory", None)
        if recommended is not None:
            return int(recommended())
    return _system_memory_bytes()


def _system_memory_bytes() -> int:
    """Physical RAM, from the OS. The CPU's "device memory" is the machine's memory."""
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (ValueError, OSError, AttributeError):
        return 0
