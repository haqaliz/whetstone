"""The only module in this repository that imports an inference library. Deliberately small.

Everything else in the bake-off is a pure function over strings; this file is where a base model
actually runs. That makes it the file where three quiet failures live, and each of them would
produce a bake-off that publishes a number rather than one that visibly breaks.

**One: an offline run that is not offline.** `mlx_lm.utils.load` decides what it was handed with
a plain `Path.exists()` check (`utils.py:218-256`). An existing directory is read from disk with
no network at all; **anything else is a HuggingFace repo id and a download**, resolved at call
time against whatever `main` points at. `"mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"` and
`"/Users/me/models/qwen"` are one paste apart and produce the same kind of object, so nothing
downstream can tell which happened — the patches generate, the verifier grades them, and the run
publishes a comparison between weights nobody recorded. (Verified: the same call under
`HF_HUB_OFFLINE=1` raises `LocalEntryNotFoundError`, so the *only* thing standing between a
mistyped path and a network fetch today is an environment variable this repository does not set.)
So this adapter refuses anything that is not an existing directory, **before** `load` is reached,
and it refuses at construction rather than at first use. `revision` is required alongside it: for
a local directory `load` does not consult it — the download branch is not taken — so it is
belt-and-braces there and a recorded fact everywhere, and the day the path is anything else an
absent revision is an unpinned fetch.

**Two: decoding that stops being greedy without anyone editing this repository.** Greedy is
`mlx-lm==0.31.3`'s default: `sampler or (lambda x: mx.argmax(x, axis=-1))` (`generate.py:386`).
Inheriting that default would be correct today and silently wrong the day it moves — the symptom
being a bake-off that compares draws while reporting a comparison of bases, with the variance
attributed to the models. So the greedy sampler is passed **explicitly**. The trade is
deliberate: an explicit sampler breaks loudly (a `TypeError`) on a version that changes the
injection protocol, where an inherited default breaks silently, and a loud break is the only kind
this project can afford on the path that produces its published numbers.

**Three: the `mlx` extra becoming a hard dependency by accident.** `.github/workflows/ci.yml:32`
runs the suite under a plain `uv sync`, which does not install the extra (`pyproject.toml:29`).
A module-scope `import mlx_lm` here would make the whole suite uncollectable there, and the fix
reached for under deadline is to move `mlx-lm` into the `dev` group — which `pyproject.toml:26-29`
refuses, because a dev-group inference library is one careless import away from the reward path.
So **every `mlx` import in this file is function-local**. This module imports anywhere; only
constructing an `MlxGenerator` needs the engine, and the absence surfaces as `MlxUnavailable`
naming the command that fixes it. That discipline is not merely stated: it is what lets
`tests/bakeoff/test_mlx_runtime.py` substitute a fake engine through `sys.modules` and assert
almost everything here on a machine with no `mlx` at all.

**API pinned to `mlx-lm==0.31.3`** (`uv.lock:485`), which is the version every claim above was
read against:

    mlx_lm.utils.load(path_or_hf_repo, ..., revision=...) -> (model, tokenizer)
    mlx_lm.generate.generate(model, tokenizer, prompt, ...) -> str

Nothing here assumes those shapes hold across versions, and `PINNED_MLX_LM` is asserted against
the installed distribution by a test that skips loudly when the extra is absent. On a lockfile
bump the required response is to re-read the API and move the pin, never to widen the assertion:
what is pinned is a *reading*, not a dependency.

**What this module does not do.** It does not template, wrap or decorate the prompt — the
rendered contract (`rendering.py`) is content-hashed as provenance under PRD M7b, and a chat
template applied here would make the published hash describe a string the model never saw, and
would make a comparison between two bases partly a comparison between two templates. It does not
tidy the answer either: raw model output goes back to the caller, because "wrote no diff" and
"wrote a wrong diff" are separated by `patch.py` and by nothing else. And it produces no verdict
of any kind — what a patch earns is decided by `whetstone.verify`, by re-execution, and nothing
in this file participates in that.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

#: The exact `mlx-lm` this adapter's call shapes and its determinism claim were read against
#: (`uv.lock:485`). Recorded as provenance on every generation and asserted against the installed
#: distribution by a loudly-skipped test, so that a lockfile bump is a red build rather than an
#: unnoticed change of decoding rule.
PINNED_MLX_LM = "0.31.3"

#: The file `mlx_lm.utils.load` opens first, and therefore the cheapest honest precondition this
#: adapter can check. Its presence is *not* a claim that the directory holds a working model —
#: only loading one proves that, and that needs weights this repository never ships.
MODEL_CONFIG = "config.json"

#: The generation budget, in tokens, when the caller does not choose one. A number this
#: repository picks and records rather than a library default, because output that stops
#: mid-hunk is charged at `patch-apply` by the verifier and only reads as "the budget was too
#: small" if the budget is written down. Roomy enough for a multi-file diff and small enough that
#: a base which has started explaining itself is cut off rather than paid for.
DEFAULT_MAX_TOKENS = 1024

#: How the decoding rule is spelled in a published run, for a reader who will not open this file.
#: It names the operation and the axis, because "greedy" alone is a word and `axis=-1` is the
#: claim: the argmax is taken over the vocabulary, not over the batch.
SAMPLER = "greedy: argmax over the final logprob axis (mx.argmax(logprobs, axis=-1))"

#: Recorded so that the absence of a chat template is a disclosed decision rather than an
#: omission a later reader has to infer. See the module docstring: templating here would break
#: the prompt hash's meaning and make the bake-off partly a comparison of templates.
CHAT_TEMPLATE = "none: the rendered prompt is passed to mlx_lm verbatim"


class MlxUnavailable(ImportError):
    """The `mlx` extra is not installed, so there is no engine to run a base model with.

    Its own class, and raised at construction, because the alternative is that a missing optional
    dependency surfaces from somewhere inside a generation call and is recorded as a base that
    produced no patch — a candidate model published as having solved nothing when what was
    actually missing was one `uv sync`.
    """


class NotALocalModelDirectory(ValueError):
    """What was handed over is not an existing directory, so loading it would reach the network.

    A `ValueError` rather than `FileNotFoundError`: the objection is not that a file is missing
    but that this argument, whatever it names, cannot be loaded offline — and a repo id, the case
    this exists for, names nothing on this filesystem at all.
    """


def greedy_sampler(logprobs: Any) -> Any:
    """Pick the highest-scoring token. The bake-off's entire decoding rule, written out.

    Identical to what `mlx-lm==0.31.3` uses when handed no sampler (`generate.py:386`) — stated
    here rather than inherited, so that greedy decoding is a property of this repository that a
    version bump cannot quietly revoke.

    `mlx.core` is imported inside the function for the reason the module docstring gives: this
    file must import where the `mlx` extra does not exist. The cost is one `sys.modules` lookup
    per token, which is not measurable next to a forward pass.
    """
    import mlx.core as mx

    return mx.argmax(logprobs, axis=-1)


class MlxGenerator:
    """A base model on this machine, behind `Generator`'s single method.

    Loads at construction, from a local directory, greedily. Everything that decides *what* is
    generated — which weights, which revision, which sampler, how many tokens — is fixed here and
    exposed through `provenance()`, and nothing about it can be varied per call. That asymmetry
    is the anti-tuning discipline the bake-off's PRD calls M7b: per-task knobs are how a harness
    ends up optimising on its own scored outcome, so the seam (`generator.Generator`) offers
    exactly one argument, and it is the prompt.

    Satisfies `Generator` structurally rather than by inheritance, which is what lets the tests
    for every other module in this package substitute `StubGenerator` and never load a model.
    """

    def __init__(
        self,
        model_path: Path | str,
        *,
        revision: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        """Validate the path, then load. In that order, and the order is the guarantee.

        The path is checked before `mlx_lm` is even imported, so a repo id is refused on a
        machine with no engine and with no possibility of a download having already started.
        `revision` is keyword-only and has no default: a caller that has not decided which
        snapshot it is measuring has not yet described a run.
        """
        if not revision.strip():
            raise ValueError(
                "revision must name the snapshot these weights came from (a commit sha or tag);"
                f" got {revision!r}. A blank revision serialises into the run's provenance as a"
                " filled-in field that identifies nothing, which is a reproducibility claim that"
                " cannot be checked and therefore cannot be falsified."
            )

        path = Path(model_path)
        if not path.is_dir():
            raise NotALocalModelDirectory(
                f"{str(model_path)!r} is not a directory on this machine, so it cannot be loaded"
                " offline. mlx_lm.utils.load treats anything that does not exist on disk as a"
                " HuggingFace repo id and DOWNLOADS it at call time, which would make this run's"
                " weights whatever the Hub served this morning. Pass the directory holding the"
                " weights; fetch them yourself, once, as a separate and recorded step."
            )
        if not (path / MODEL_CONFIG).is_file():
            raise NotALocalModelDirectory(
                f"{str(path)!r} holds no {MODEL_CONFIG}, so it is a directory rather than a model."
                f" mlx_lm.utils.load opens {MODEL_CONFIG} first and would fail from inside the"
                " library, naming a path you never typed."
            )

        self._model_path = path.resolve()
        self._revision = revision
        self._max_tokens = max_tokens
        self._model, self._tokenizer = _load(self._model_path, revision)

    @property
    def model_path(self) -> Path:
        """The resolved directory these weights were loaded from. Never a repo id."""
        return self._model_path

    @property
    def revision(self) -> str:
        """The snapshot the operator says is in `model_path`, recorded verbatim."""
        return self._revision

    @property
    def max_tokens(self) -> int:
        """The generation budget every call to `generate` is given."""
        return self._max_tokens

    def generate(self, prompt: str) -> str:
        """Return the model's completion of `prompt`, as raw text.

        The prompt goes to the engine verbatim and the answer comes back unedited: see the module
        docstring on why templating the one and tidying the other both belong to other files, or
        to nobody.

        A non-string answer raises rather than being coerced. `str(obj)` would hand `patch.py` a
        repr — which contains no diff, which is reported as a base that produced no patch — and
        so would publish a version mismatch as a model result.
        """
        answer = _generate(
            self._model,
            self._tokenizer,
            prompt,
            max_tokens=self._max_tokens,
            sampler=greedy_sampler,
        )
        if not isinstance(answer, str):
            raise TypeError(
                f"mlx_lm.generate.generate returned {type(answer).__name__}, not str. This"
                f" adapter is written against mlx-lm=={PINNED_MLX_LM}, where it returns the"
                " generated text. Coercing the value here would hand the extractor a repr,"
                " which holds no diff, and the run would report a version mismatch as a base"
                " model that solved nothing."
            )
        return answer

    def provenance(self) -> Mapping[str, str]:
        """Everything needed to reproduce what generated a patch, as read-only strings.

        Strings throughout so the block serialises without a codec and compares between runs
        without depending on which writer touched it; read-only so a reporting layer cannot amend
        the record on its way into the report.
        """
        return MappingProxyType(
            {
                "runtime": "mlx-lm",
                "mlx_lm": PINNED_MLX_LM,
                "model_path": str(self._model_path),
                "revision": self._revision,
                "sampler": SAMPLER,
                "max_tokens": str(self._max_tokens),
                "chat_template": CHAT_TEMPLATE,
            }
        )


def _load(model_path: Path, revision: str) -> tuple[Any, Any]:
    """`mlx_lm.utils.load` on a directory, with the extra's absence named as its own error.

    The import is function-local and the submodule is imported by its full path rather than
    through the package's re-exports, so that what this file depends on is exactly what the pin
    documents.
    """
    try:
        from mlx_lm.utils import load
    except ImportError as error:
        raise MlxUnavailable(
            "the `mlx` extra is not installed, so there is no engine to run a base model with."
            " Install it with `uv sync --extra mlx` (macOS / Apple Silicon). It is deliberately"
            " optional and deliberately not a dev dependency: an inference library in the dev"
            " group is one careless import away from the reward path, which is the one place in"
            " this project a model may never appear."
        ) from error

    # `load` is typed as returning EITHER `(model, tokenizer)` OR `(model, tokenizer, config)`,
    # selected by `return_config` — which defaults to `False`, so the two-tuple is what arrives
    # here. mypy cannot narrow that union from a default argument, so unpacking two names
    # directly is an error. Indexing is total over both arms and needs no runtime check.
    #
    # Found by installing the extra locally, and it is worth recording why it survived review:
    # CI runs `uv run mypy src/` under plain `uv sync`, WITHOUT the mlx extra, so every symbol
    # in this module resolves to `Any` there and no call into `mlx_lm` is type-checked at all.
    # The `[[tool.mypy.overrides]]` that makes the import tolerable off-Darwin is exactly what
    # blinds the check on it. `.github/workflows/ci.yml` now runs mypy a second time with the
    # extra installed, so this class of error stops depending on someone happening to install it.
    loaded = load(str(model_path), revision=revision)
    return loaded[0], loaded[1]


def _generate(model: Any, tokenizer: Any, prompt: str, *, max_tokens: int, sampler: Any) -> Any:
    """`mlx_lm.generate.generate` with the pinned call shape, and no sampling knobs.

    `max_tokens` and `sampler` are the only two arguments passed beyond the positional three. In
    `mlx-lm==0.31.3` sampling is injected as a callable, so a `temperature=` here would not
    configure anything — it would flow into `**kwargs` and be ignored or fatal, and being ignored
    is a bake-off whose decoding is not what its own code says it is.
    """
    try:
        from mlx_lm.generate import generate
    except ImportError as error:  # pragma: no cover - construction fails first, in _load
        raise MlxUnavailable(
            "the `mlx` extra is not installed; install it with `uv sync --extra mlx`"
        ) from error

    return generate(model, tokenizer, prompt, max_tokens=max_tokens, sampler=sampler)


__all__ = [
    "CHAT_TEMPLATE",
    "DEFAULT_MAX_TOKENS",
    "MODEL_CONFIG",
    "PINNED_MLX_LM",
    "SAMPLER",
    "MlxGenerator",
    "MlxUnavailable",
    "NotALocalModelDirectory",
    "greedy_sampler",
]
