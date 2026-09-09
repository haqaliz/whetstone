"""The ledger's account of *how* a night sampled must name the runtime that actually sampled.

**The defect this closes, observed rather than imagined.** `runs/night-002/ledger.json` — written by
a night that ran end to end on a CPU-only Linux host, 408 rollouts over ten hours — recorded

    "backend": {"name": "torch", "library": "torch", "version": "2.14.0+cpu", "device": "cpu"}
    "generation_contract": {"sampler": "categorical: ... (mlx_lm.sample_utils.make_sampler),
                            with mx.random.seed(...) applied immediately before each draw ..."}

`mlx_lm` is not installed on that machine. `mx.random.seed` was never called. Every one of those
draws went through `transformers` and was seeded with `torch.manual_seed`.

**Why this is worse than an inaccurate comment.** M6 dispatched the engine, the seeder, the trainer
and `tool_versions` on the detected runtime, precisely so that a night could not record one runtime
and run another. The *mechanism* was fixed and the ledger's *description* of the mechanism was
missed — so the exact failure that work existed to prevent survived, in the one artefact whose
whole purpose is that a reader can trust it without re-running the night. The comparability key
(`backend.name`) was right the whole time, so nothing downstream broke and nothing complained;
that is what made it survivable, and it is why this is asserted rather than proof-read.

`TORCH_SAMPLER` already existed at `torch_runtime.py:221`, correct and unused by this path. The
bug was never a missing string, it was a hardcoded one — which is why the test that matters here is
the negative: a Torch night's contract must not be able to say `mlx`, whatever anyone later adds.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from whetstone.loop import night
from whetstone.loop.backend import MLX, TORCH, UnknownRuntime
from whetstone.loop.sampling import TEMPERATURE, TOP_P, sampler_description_for


@dataclass(frozen=True)
class _Frozen:
    """The one attribute `_contract` reads. A real `freeze` needs a task set and a pool."""

    sha256: str = "0" * 64


def test_the_torch_description_names_torch_and_cannot_name_mlx() -> None:
    """The negative half is the point: this is what night-002's ledger failed."""
    described = sampler_description_for(TORCH)

    assert "torch.manual_seed" in described
    assert "transformers" in described
    assert "mlx" not in described.lower()
    assert "mx.random" not in described


def test_the_mlx_description_names_mlx_and_cannot_name_torch() -> None:
    """The mirror, so the dispatch is not a one-armed check that passes on a constant."""
    described = sampler_description_for(MLX)

    assert "mlx_lm" in described
    assert "mx.random.seed" in described
    assert "torch" not in described.lower()


def test_the_description_is_rendered_and_carries_no_unfilled_placeholder() -> None:
    """`TORCH_SAMPLER` is a template. An unrendered one records `{temperature}` as evidence.

    That would be a quieter version of the same defect — a ledger stating a decoding parameter
    nobody can read — so the rendering is asserted rather than left to the caller to remember.
    """
    described = sampler_description_for(TORCH)

    assert "{" not in described and "}" not in described
    assert str(TEMPERATURE) in described
    assert str(TOP_P) in described


def test_an_unknown_runtime_is_refused_rather_than_defaulted() -> None:
    """A default here is how the defect got in: something had to be recorded, so MLX was.

    Refusing costs a crash on a runtime nobody has taught this function about. Defaulting costs a
    document that describes a run that did not happen, discovered — if ever — by someone reading a
    ledger months later.
    """
    with pytest.raises(UnknownRuntime):
        sampler_description_for("runtime-that-does-not-exist")


def test_a_torch_nights_contract_records_torch_sampling() -> None:
    """The regression, at the layer that actually wrote the wrong bytes.

    `night._contract` is where the hardcoded constant sat. Asserted here rather than only on
    `sampler_description_for`, because a correct dispatcher that nothing calls is exactly the state
    this repository was already in: `TORCH_SAMPLER` was right, and unreachable from the ledger.
    """
    built = night._contract(
        _Frozen(),
        max_tokens=1024,
        declared=(),
        retries=False,
        backend_name=TORCH,
    )

    assert "mlx" not in built.sampler.lower()
    assert "torch.manual_seed" in built.sampler


def test_an_mlx_nights_contract_records_mlx_sampling() -> None:
    """The other side of the same call, so the argument is threaded and not merely accepted."""
    built = night._contract(
        _Frozen(),
        max_tokens=1024,
        declared=(),
        retries=False,
        backend_name=MLX,
    )

    assert "mlx_lm" in built.sampler
    assert "torch" not in built.sampler.lower()
