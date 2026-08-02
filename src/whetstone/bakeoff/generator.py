"""The model seam: one method, injected, with no model behind it yet.

Everything downstream of this file — the prompt contract, the diff extractor, the runner that
scores a base against the verifier — needs *some* way to turn a prompt into text. Writing that
against `mlx_lm` directly would make three things true at once, each bad: the test suite would
need multi-gigabyte weights on disk to run at all, it would need `mlx` installed in an
environment CI does not build (`.github/workflows/ci.yml:32` runs `uv run pytest` under a plain
`uv sync`, which omits the `mlx` extra from `pyproject.toml:29`), and every later test would be
measuring a real model's mood alongside the code under test.

So the dependency is inverted at the smallest possible surface. `Generator` is a `Protocol` with
exactly one method. The MLX adapter is one implementation of it and arrives in a later phase;
`StubGenerator` is the other, and it is what every test in this slice substitutes.

**One method, and deliberately so.** A seam with two methods is a seam whose implementations can
disagree about which one the caller uses, and each addition is another thing the real adapter
must reproduce faithfully or the substitution becomes a fiction. Sampling parameters, model
identity, revision pinning and load-from-disk-not-from-a-repo-id all belong to the adapter's
*constructor*, where they are recorded as provenance — not to this call, where they would become
knobs a later phase could tune per task. That distinction is the anti-tuning discipline the
bake-off's PRD calls M7b: what a base is shown, and how it is decoded, is fixed and disclosed
rather than adjusted until the number improves.

**Off the reward path.** See the package docstring: this module may not be imported by anything
under `verify/` or `tasks/`, and nothing here imports `mlx` — the adapter does, in its own
module, so that importing this seam never requires the extra.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol, runtime_checkable


class UnstubbedPrompt(LookupError):
    """A `StubGenerator` was asked for a prompt it holds no answer for.

    A distinct exception rather than a bare `KeyError` because the message is the point: a
    `KeyError` renders as the repr of the missing key alone, and a prompt is a multi-line string
    whose repr in a traceback tells the reader nothing about *why* it went unmatched.
    """


@runtime_checkable
class Generator(Protocol):
    """Text in, text out. The entire surface a base model presents to the bake-off.

    `runtime_checkable` so conformance can be asserted rather than assumed: `mypy` runs over
    `src/` only (`pyproject.toml`: `files = ["src"]`), so a protocol relied upon by test doubles
    would otherwise be checked by nothing on the path that actually exercises it. Note the
    limit of what that buys — `isinstance` against a protocol checks that an attribute named
    `generate` exists and nothing whatever about its signature, so the tests compare signatures
    too.
    """

    def generate(self, prompt: str) -> str:
        """Return the model's completion of `prompt`, as text.

        The return value is **raw model output**, not a patch: extracting a unified diff from it
        (or reporting that it contains none) is a separate step, deliberately, so that "the
        model wrote no diff" and "the model wrote a wrong diff" stay distinguishable all the way
        to the report.

        Implementations are expected to be deterministic for a given prompt — the MLX adapter
        decodes greedily for that reason. A sampled generator would make the bake-off's
        comparison between bases a comparison between draws.
        """
        ...


@dataclass(frozen=True)
class StubGenerator:
    """A `Generator` that answers from a fixed table. Deterministic by construction.

    This is the double every test in this slice substitutes for a base model, so its own
    behaviour has to be beyond question: if a stub could answer the same prompt two ways, a red
    result in a later test would be consistent with a broken harness *and* with a moving double,
    and nothing in the output would say which.

    **The answers are copied and frozen at construction.** Holding the caller's mapping would
    make the stub's determinism a property of every caller's discipline rather than of the stub
    — a module-level dict shared across a parameterised run is all it would take. `frozen=True`
    protects the attribute; the `MappingProxyType` copy protects what the attribute points at,
    and only both together make the object actually fixed.

    **An unknown prompt raises.** It does not return `""`. That is the whole reason this class
    is more than a `dict.get`: `verify_strict(task, "")` is charged FAIL at `patch-apply`
    (`whetstone.verify.liveness`), so an empty answer is indistinguishable downstream from a
    model that produced a wrong fix. A stub that answered unmatched prompts with the empty
    string would let a mis-wired test read as a failed task — the exact confusion the extractor
    contract exists to prevent, reintroduced in the fixture.
    """

    #: Prompt -> the text a base model is pretending to have produced for it. Replaced with a
    #: read-only copy in `__post_init__`; the annotation stays `Mapping` because that is what
    #: callers may pass in.
    answers: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "answers", MappingProxyType(dict(self.answers)))

    def generate(self, prompt: str) -> str:
        """The answer stubbed for `prompt`, or `UnstubbedPrompt` naming what went unmatched."""
        try:
            return self.answers[prompt]
        except KeyError:
            raise UnstubbedPrompt(
                f"no answer was stubbed for this prompt: {prompt!r}. The stub refuses rather "
                "than returning an empty string, because empty output is charged FAIL at "
                "patch-apply and would be indistinguishable from a model that got the task "
                f"wrong. Stubbed prompts: {sorted(self.answers)!r}"
            ) from None


__all__ = ["Generator", "StubGenerator", "UnstubbedPrompt"]
