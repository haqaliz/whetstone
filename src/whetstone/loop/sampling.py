"""`k` seeded attempts per task: the one genuinely new seam P2 needs, at its smallest size.

The bake-off's entire decode rule is one greedy attempt per (candidate, task), with no seed and
deliberately so — D3 fixed it that way so a comparison between bases was not a comparison between
draws (`whetstone.bakeoff.run._SEEDS` records the reasoning rather than a blank). Rejection
sampling needs the opposite: several draws per task, each reproducible on its own. That is a
different *decoding rule*, not a different model interface, so nothing about the one-method
`Generator` seam changes here — this module adds one more wrapper of the kind `Sealed`,
`Recording` and `Retry` already are.

**Three decisions, and none of them are style.**

*The seed derivation is sha256, never the builtin `hash`.* `hash("a-task-id")` is salted per
process (`PYTHONHASHSEED`), so a derivation built on it would produce a different dataset on
every invocation while every line of it read as deterministic. The P2 exit criterion is *"same
seed → byte-identical training set"*; built on the builtin, that criterion would be a statement
about an environment variable.

*The sampling index **is** the attempt index.* Draw *i* of *k* is attempt *i*, and its seed is
`attempt_seed(run_seed, task_id, attempt)` — a pure function of three declared things, recomputable
by a reader holding the ledger. The `Retry` wrapper composes **outside** a single draw: a retry
re-asks the same draw (its prompt is a pure function of the first prompt and a trigger,
`retry.py`), reuses that draw's seed, and consumes no new one. So a (candidate, task, draw) has
exactly one seed, and the transcript's own `attempt` field — which numbers *retries* within a
draw — cannot be confused with it, because the two live in different files (one transcript per
draw index).

*`k = 1` must still be greedy.* `sampler_for(1)` returns
`whetstone.bakeoff.mlx_runtime.greedy_sampler` **by identity**, so a single-draw loop decodes
exactly as the bake-off does and the two are comparable. Anything else would mean the loop's
k=1 and the bake-off's k=1 were different experiments that nothing in either report would
disclose.

**The seed reaches a global.** `mlx-lm==0.31.3` samples from process-global `mx.random` state —
`mlx_lm.sample_utils.categorical_sampling` takes no seed argument — so a per-attempt seed can only
be applied by seeding that global immediately before the draw, serially. `Draw` does exactly that
through an injected `Seeder`, which is also what lets every test in this package run with no `mlx`
installed. The residual is honest and is a machine-level constraint rather than a code fix:
another process sharing the device can perturb the draws, so nights are serialised (the
worktrees skill's GPU rule, restated in the runbook).

**Off the reward path.** This module imports `whetstone.bakeoff` and `whetstone.verify`; nothing
guarded may import it. Every `mlx` import is function-local, so the module imports and
type-checks on a machine with no extra.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.mlx_runtime import (
    DEFAULT_MAX_TOKENS,
    MODEL_CONFIG,
    NotALocalModelDirectory,
    greedy_sampler,
)
from whetstone.bakeoff.rendering import prompt_hash
from whetstone.bakeoff.weights import Weights

#: How many attempts each task gets, per candidate, per night. **Declared here and nowhere else,
#: and deliberately not a flag.** A per-run `k` is a knob an operator turns after seeing a
#: disappointing yield, which is optimising on the run's own scored outcome (PRD M7b's discipline
#: applied to the sampling budget rather than to the prompt). Raising it is the roadmap's named
#: response to low yield (`docs/ROADMAP.md:405-406`) — as an edit to this line, in a diff, before
#: a night, never as an argument on a command that has already run once.
#:
#: The value is a small multiple of the bake-off's k=1 probe. **No claim about any model is
#: asserted by this number**: what it buys is measured by the run's own yield-versus-unverified
#: read, and nothing here predicts that.
K = 8

#: The decoding rule a multi-draw night uses, spelled for a reader who will not open this file —
#: the shape `mlx_runtime.SAMPLER` uses, for the same reason: "sampled" alone is a word, and the
#: parameters are the claim.
SAMPLER = (
    "categorical: temperature 0.8, top-p 0.95 (mlx_lm.sample_utils.make_sampler), with "
    "mx.random.seed(attempt_seed(run_seed, task_id, attempt)) applied immediately before each "
    "draw and draws taken serially; k=1 decodes greedily, identically to the bake-off"
)

#: The sampling temperature. Fixed at module scope rather than per run, for the reason `K` is:
#: a per-night decoding knob is a knob that gets turned until the number improves.
TEMPERATURE = 0.8

#: Nucleus cut-off. Same argument as `TEMPERATURE`.
TOP_P = 0.95

#: How a seed reaches whatever is about to draw. Injected so that the entire sampling path is
#: exercised on a machine with no `mlx`: the real one seeds `mx.random`, and a test's records what
#: it was handed. Returns nothing, because the thing it configures is a global.
Seeder = Callable[[int], None]


def attempt_seed(run_seed: int, task_id: str, attempt: int) -> int:
    """The seed for one draw: a pure function of the run seed, the task and the attempt index.

    **sha256, not `hash`.** See the module docstring: the builtin is salted per process, so a
    derivation built on it would make the determinism criterion a claim about `PYTHONHASHSEED`.
    This is recomputable by anyone holding the ledger and a shell.

    Truncated to 64 bits because that is what a seed is for — `mx.random.seed` takes an integer,
    and a 256-bit value would be reduced by the library rather than by a line anybody can read.
    The fields are joined with a separator that cannot occur in a task id, so
    `("a", 11)` and `("a1", 1)` cannot collide into one seed.
    """
    if attempt < 1:
        raise ValueError(
            f"attempt must be one-based, got {attempt}. Draw i of k is attempt i, and a zeroth "
            "attempt would give two draws the same numbering in the ledger — which is the one "
            "field a reader uses to recompute a seed"
        )
    material = f"{run_seed}\n{task_id}\n{attempt}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


@dataclass(frozen=True)
class Applied:
    """One seed, as it was actually applied. The evidence behind the determinism claim.

    Recorded rather than only recomputed. The derivation is pure, so a reader *can* recompute it —
    but the ledger's job is to say what the run did, and a document that only carries the recipe
    cannot distinguish a run that followed it from one that skipped the seeding entirely.
    """

    #: The task the draw was for.
    task_id: str

    #: Which draw of `K` this was. One-based.
    attempt: int

    #: What was handed to the `Seeder`.
    seed: int


def mlx_seeder(seed: int) -> None:
    """Seed `mx.random`, the global state `mlx-lm==0.31.3` samples from.

    Function-local import for the reason `mlx_runtime.py` gives: this module must import,
    type-check and test on a machine with no `mlx` extra, and CI is such a machine.
    """
    import mlx.core as mx

    mx.random.seed(seed)


@dataclass(frozen=True)
class Draw:
    """A base pinned to one draw index: seed the sampler, then ask. In that order, deliberately.

    A `Generator` by structure, wrapping another, so `sweep` and `score` learn nothing about
    sampling — the same composition `run.Sealed` and `run.Recording` use, and for the same reason:
    a second method on the model seam is a second thing the MLX adapter has to reproduce
    faithfully before every model-free test in this tree stops being a fiction.

    **The task is resolved from the frozen contract, never inferred from the prompt.** The seed
    derivation needs a task id and the seam carries only a prompt; the `posed` map already knows
    which task each sealed prompt asks about, and that is the mechanism `run.Recording` uses. A
    wrapper that parsed the id out of the prompt text would attribute one task's draw to another
    the first time the template changed.

    **A prompt the contract does not carry is passed straight down, unseeded and unrecorded.**
    That is the point of the composition rather than a gap: this wrapper sits *outside* `Sealed`,
    so a drifted prompt reaches it first, and delegating lets `Sealed` raise `ContractChanged`
    while this object's record stays a record of draws that actually happened. Seeding for it
    would file an `Applied` for a generation the run then refused.
    """

    #: What actually generates. Called once per `generate`, with the prompt unaltered.
    inner: Generator

    #: The frozen `posed` map — prompt digest to task id. Read only to learn which task a prompt
    #: is about; enforcing the seal is `Sealed`'s job and a second enforcement is one more thing
    #: to get wrong.
    contract: Mapping[str, str]

    #: The night's single declared seed. Every per-attempt seed descends from it.
    run_seed: int

    #: Which draw of `K` this wrapper is. One-based; fixed at construction, never per call.
    attempt: int

    #: How the seed is applied. Defaults to the real thing, substituted in tests — the
    #: inversion `scoring.Interpreters.provision` and `retry.Retry.decide` already use, so the
    #: whole sampling path is exercised on a machine with no `mlx`.
    seeder: Seeder = mlx_seeder

    #: Every seed this wrapper applied, in the order it applied them. A list on a frozen
    #: dataclass: the *attribute* is fixed, and what it points at is the record being built.
    applied: list[Applied] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.attempt < 1:
            raise ValueError(
                f"attempt must be one-based, got {self.attempt}: draw i of k is attempt i"
            )

    def generate(self, prompt: str) -> str:
        """Seed for this (task, attempt), then delegate. An unfrozen prompt goes down untouched."""
        task_id = self.contract.get(prompt_hash(prompt))
        if task_id is None:
            return self.inner.generate(prompt)
        seed = attempt_seed(self.run_seed, task_id, self.attempt)
        # Applied before the call and recorded before the call, because the seeding is what the
        # record is about: a draw that raised still drew under this seed, and a record written
        # afterwards would silently omit exactly the attempts a reader is trying to explain.
        self.seeder(seed)
        self.applied.append(Applied(task_id=task_id, attempt=self.attempt, seed=seed))
        return self.inner.generate(prompt)


def sampler_for(draws: int) -> Any:
    """The sampler a night of `draws` attempts decodes with.

    `draws == 1` returns `greedy_sampler` **by identity** — the bake-off's own function, not a
    reimplementation of it — so a single-draw loop is byte-for-byte the bake-off's experiment.
    Anything above one returns the categorical sampler at the declared temperature and top-p,
    because k identical greedy draws would be k copies of one answer and rejection sampling over
    them would select nothing.
    """
    if draws < 1:
        raise ValueError(
            f"a night must take at least one draw per task, got {draws}. Zero draws is a night "
            "that asks nothing and reports a dataset of nothing, which is a usage error and not "
            "a finding"
        )
    if draws == 1:
        return greedy_sampler
    return _categorical_sampler()


def _categorical_sampler() -> Any:
    """`mlx_lm.sample_utils.make_sampler` at the declared temperature and top-p.

    Built through the library's own factory rather than written out here: `make_sampler` is the
    documented injection point at the pinned version, and a hand-rolled categorical draw would be
    a second decoding rule that nothing compares against the first.
    """
    from mlx_lm.sample_utils import make_sampler

    return make_sampler(temp=TEMPERATURE, top_p=TOP_P)


class SampledMlxGenerator:
    """A base model on this machine, decoding by sampling rather than by argmax.

    Deliberately a sibling of `mlx_runtime.MlxGenerator` rather than a subclass or an edit of it.
    The bake-off's adapter is the thing four published reports were measured through; giving it a
    second decoding mode would make every one of those reports depend on a default. What is shared
    is shared **by identity** — the path refusal's constants, the greedy sampler, the pinned
    version — and what differs is one line: which sampler is passed.

    Everything that decides *what* is generated is fixed at construction and disclosed through
    `provenance()`. Nothing can be varied per call, which is the anti-tuning discipline M7b names.
    """

    def __init__(
        self,
        model_path: Path | str,
        *,
        revision: str,
        draws: int = K,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        """Validate the path, choose the sampler, then load. The order is the guarantee.

        The path is checked before `mlx_lm` is imported at all, so a repo id is refused on a
        machine with no engine and with no possibility of a download having started — the
        `mlx_runtime.MlxGenerator` argument, which is about `mlx_lm.utils.load` treating anything
        that is not an existing directory as something to fetch.
        """
        if not revision.strip():
            raise ValueError(
                f"revision must name the snapshot these weights came from; got {revision!r}. A"
                " blank revision serialises into the run ledger as a filled-in field that"
                " identifies nothing, which is a reproducibility claim that cannot be falsified."
            )
        path = Path(model_path)
        if not path.is_dir():
            raise NotALocalModelDirectory(
                f"{str(model_path)!r} is not a directory on this machine, so it cannot be loaded"
                " offline. mlx_lm.utils.load treats anything that does not exist on disk as a"
                " HuggingFace repo id and DOWNLOADS it at call time. Pass the directory holding"
                " the weights; fetch them yourself, once, as a separate and recorded step."
            )
        if not (path / MODEL_CONFIG).is_file():
            raise NotALocalModelDirectory(
                f"{str(path)!r} holds no {MODEL_CONFIG}, so it is a directory rather than a model."
            )

        self._model_path = path.resolve()
        self._revision = revision
        self._draws = draws
        self._max_tokens = max_tokens
        self._sampler = sampler_for(draws)
        self._model, self._tokenizer = _load(self._model_path, revision)

    @property
    def model_path(self) -> Path:
        """The resolved directory these weights were loaded from. Never a repo id."""
        return self._model_path

    @property
    def revision(self) -> str:
        """The snapshot the operator says is in `model_path`, recorded verbatim."""
        return self._revision

    def generate(self, prompt: str) -> str:
        """Return the model's completion, raw. The seed was applied by `Draw`, not here.

        Seeding belongs to the wrapper because the seed depends on which *task* and which
        *attempt* this is, and this object knows neither — it is constructed once per candidate
        and shared across every task in a source, exactly as the bake-off's adapter is.
        """
        answer = _generate(
            self._model,
            self._tokenizer,
            prompt,
            max_tokens=self._max_tokens,
            sampler=self._sampler,
        )
        if not isinstance(answer, str):
            raise TypeError(
                f"mlx_lm.generate.generate returned {type(answer).__name__}, not str. Coercing it"
                " here would hand the extractor a repr, which holds no diff, and the night would"
                " record a version mismatch as a base that wrote no patch."
            )
        return answer

    def provenance(self) -> Mapping[str, str]:
        """Everything that decided what was generated, as read-only strings."""
        from whetstone.bakeoff.mlx_runtime import CHAT_TEMPLATE, PINNED_MLX_LM

        return MappingProxyType(
            {
                "runtime": "mlx-lm",
                "mlx_lm": PINNED_MLX_LM,
                "model_path": str(self._model_path),
                "revision": self._revision,
                "sampler": SAMPLER if self._draws > 1 else "greedy (k=1)",
                "draws": str(self._draws),
                "max_tokens": str(self._max_tokens),
                "chat_template": CHAT_TEMPLATE,
            }
        )


def sampling_engine(weights: Weights, max_tokens: int) -> Generator:
    """Load a verified candidate from its own directory, offline, decoding by sampling.

    The loop's `Engine`, in the shape `run.mlx_engine` established: `HF_HUB_OFFLINE` is set
    **first**, so a defect in anything after it raises instead of downloading; the **path** is
    passed rather than `weights.repo_id`, because the two are one paste apart and one of them is
    a download; and `revision` is the immutable commit sha `load_weights` verified the bytes
    against.
    """
    import os

    from whetstone.bakeoff.run import HF_HUB_OFFLINE

    os.environ[HF_HUB_OFFLINE] = "1"
    return SampledMlxGenerator(
        weights.local_dir, revision=weights.revision, draws=K, max_tokens=max_tokens
    )


def _load(model_path: Path, revision: str) -> tuple[Any, Any]:
    """`mlx_lm.utils.load` on a directory, with the extra's absence named as its own error."""
    from whetstone.bakeoff.mlx_runtime import MlxUnavailable

    try:
        from mlx_lm.utils import load
    except ImportError as error:
        raise MlxUnavailable(
            "the `mlx` extra is not installed, so there is no engine to run a base model with."
            " Install it with `uv sync --extra mlx` (macOS / Apple Silicon)."
        ) from error

    # Indexed rather than unpacked for the reason `mlx_runtime._load` gives: `load` is typed as
    # returning either a two- or a three-tuple, selected by a default argument mypy cannot narrow.
    loaded = load(str(model_path), revision=revision)
    return loaded[0], loaded[1]


def _generate(model: Any, tokenizer: Any, prompt: str, *, max_tokens: int, sampler: Any) -> Any:
    """`mlx_lm.generate.generate` with the pinned call shape and no sampling knobs beyond these."""
    from whetstone.bakeoff.mlx_runtime import MlxUnavailable

    try:
        from mlx_lm.generate import generate
    except ImportError as error:  # pragma: no cover - construction fails first, in _load
        raise MlxUnavailable(
            "the `mlx` extra is not installed; install it with `uv sync --extra mlx`"
        ) from error

    return generate(model, tokenizer, prompt, max_tokens=max_tokens, sampler=sampler)


__all__ = [
    "SAMPLER",
    "TEMPERATURE",
    "TOP_P",
    "Applied",
    "Draw",
    "K",
    "SampledMlxGenerator",
    "Seeder",
    "attempt_seed",
    "mlx_seeder",
    "sampler_for",
    "sampling_engine",
]
