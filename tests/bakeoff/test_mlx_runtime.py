"""Pins the one module allowed to import `mlx_lm` — and pins it from a machine that lacks it.

The adapter this file covers is the only place in the repository where an inference library is
imported at all, so it carries three failures that nothing else can carry, and every one of them
is quiet.

**First: a run that reaches the network while claiming to be offline.** `mlx_lm.utils.load`
decides what it was handed with a plain `Path.exists()` (`utils.py:218-256`): an existing
directory is read from disk, and **anything else is a HuggingFace repo id and a download**. Those
two are one typo apart and they produce the same object, so a bake-off pointed at
`mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` instead of at the directory holding it would still
generate patches, still score them, and still publish a number — a number produced by whatever
weights the Hub served that morning, against a `revision` the run never pinned because the
download path was never meant to be taken. That is the same class of defect as the unpinned
`environment` this project already closed for the *verifier* (`tests/test_environment_pins.py`),
arriving on the *generation* side instead. So the refusal is asserted here, before any weights
exist to be fetched: a repo id is refused at construction and `load` is never reached.

**Second: decoding that stops being greedy without anyone editing this repository.** Greedy is
`mlx-lm==0.31.3`'s default sampler (`generate.py:386`, `sampler or (lambda x: mx.argmax(x,
axis=-1))`) — and a default is a property of a *version*, not of our code. `uv.lock` moves, a
default becomes `temp=0.7`, and the bake-off silently starts comparing draws instead of bases,
with the between-run variance appearing in a report that attributes it to the models. So this
adapter passes an **explicit** greedy sampler rather than inheriting one, and this file asserts
which of the two it did. The failure mode of an explicit sampler is a `TypeError` on a version
that changed the protocol; the failure mode of an inherited default is a wrong number. Loud beats
quiet.

**Third: the extra becoming a hard dependency by accident.** `.github/workflows/ci.yml:32` runs
the suite under a plain `uv sync`, which does not install the `mlx` extra (`pyproject.toml:29`),
and the tempting fix for the resulting collection error is to add `mlx-lm` to the `dev` group —
which `pyproject.toml:26-29` refuses, because a dev-group inference library is one careless
import away from the reward path. So `import mlx_lm` in the adapter is **function-local**, the
module itself imports anywhere, and that is asserted in a subprocess where mlx is *forcibly*
refused rather than merely absent.

**How this file is arranged, and why almost none of it needs mlx.** Everything above is a
property of the adapter's *logic* — which path it validates, what it passes, what it refuses —
and logic does not need an engine to be tested. So the engine is substituted: a fake `mlx_lm` and
`mlx.core` are installed into `sys.modules`, and because the adapter's imports are function-local
they resolve to the fake at call time with no module reloading. That keeps the interesting
assertions running on CI's actual machine, which is the only machine that runs them every time.

Exactly two tests genuinely need the real engine — the version canary, and the proof that the
greedy sampler really selects an argmax — and both **skip loudly**. `tests/conftest.py:66-69`
states this repository's position on the alternative: a silently skipped assertion is a green
suite in which nothing was demonstrated, the same class of lie as rendering `UNVERIFIED` as
`PASS`. The skip reason therefore says what went undemonstrated and how to demonstrate it, and
`ci.yml:33-74` is the shape that surfaces such a skip in a log instead of swallowing it.

**No weights are downloaded here, by anything, ever.** Every "model directory" below is an empty
directory with a `config.json` in it. Provisioning real weights is a separate, human-run,
disclosed step (aspect 4).
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from collections.abc import Iterator
from importlib.util import find_spec
from pathlib import Path
from textwrap import dedent
from types import ModuleType
from typing import Any

import pytest

from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.mlx_runtime import (
    CHAT_TEMPLATE,
    PINNED_MLX_LM,
    SAMPLER,
    MlxGenerator,
    NotALocalModelDirectory,
    greedy_sampler,
)

#: A revision that looks like what an operator would pin: a full commit sha. Its *content* is
#: never interpreted by anything here — what matters is that the same string reaches `load` and
#: the provenance block unchanged, because a revision that is silently normalised is a revision
#: the published run cannot be reproduced from.
REVISION = "9d0c1e6b0f4f4a1a9a2b3c4d5e6f70819a2b3c4d"

#: A repo id, and the single most dangerous string this adapter can be handed. It is well-formed,
#: it is what every model card on the Hub tells you to paste, and `mlx_lm.utils.load` accepts it
#: happily — by downloading. Verified behaviour: under `HF_HUB_OFFLINE=1` the same call raises
#: `LocalEntryNotFoundError`, which is to say the offline run's *only* protection today is an
#: environment variable nobody in this repository sets.
REPO_ID = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"

#: What the fake engine "generates". Deliberately a diff-shaped string with trailing prose, so a
#: passthrough assertion is checking that the adapter returned raw model output rather than
#: something it had already tidied — extraction is `patch.py`'s job and must be given the mess.
ANSWER = "```diff\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-i + 1\n+i\n```\nHope that helps!"

#: The token the fake `mx.argmax` returns. An arbitrary sentinel: the assertion is that the
#: sampler *delegates* to argmax over the last axis, not that this repository can compute one.
ARGMAX_TOKEN = 7

#: Sampling knobs that belong to no version of this call. `mlx-lm==0.31.3` injects sampling as a
#: **callable**, so a `temperature=` here would not be an alternative spelling of greedy — it
#: would flow into `**kwargs` and be either ignored or fatal, and the first of those is a
#: non-deterministic bake-off that looks exactly like a deterministic one.
NOT_A_KNOB = ("temp", "temperature", "top_p", "top_k", "min_p", "seed")

#: Skips the two tests that cannot be answered without the engine — and says so in a sentence a
#: reader of a CI log can act on. `find_spec` rather than a bare `import`, because the question is
#: whether the extra is installed, not whether an import happened to succeed once.
requires_mlx = pytest.mark.skipif(
    find_spec("mlx_lm") is None,
    reason=(
        "UNDEMONSTRATED-HERE: mlx-lm is not installed in this environment, so this assertion "
        "about the real engine did not run — it did NOT pass. Install the extra with "
        "`uv sync --extra mlx` (macOS/Apple Silicon) to demonstrate it. Everything else in this "
        "file runs against a stubbed engine and did run."
    ),
)

#: Run in a **fresh interpreter** with every `mlx` import forcibly refused. The question this
#: probe answers is "does this module import, and refuse to construct, where mlx does not exist"
#: — and asking it inside the running suite would answer "…on this laptop today" instead, which
#: is the machine-dependent answer it exists to replace. It proves its own blocker bites first.
_NO_MLX_PROBE = """
import sys

BANNED = ("mlx", "mlx_lm")


class Refuse:
    \"\"\"A meta-path finder that makes mlx unimportable, however this venv is provisioned.\"\"\"

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BANNED:
            raise ImportError(f"mlx is absent in this environment (refused {fullname!r})")
        return None


sys.meta_path.insert(0, Refuse())
for name in [n for n in sys.modules if n.split(".")[0] in BANNED]:
    del sys.modules[name]

# Anti-vacuity: where mlx is genuinely absent this arm is satisfied by the absence; where the
# extra IS installed, the blocker is what satisfies it, and that is the case this arm exists for.
try:
    import mlx_lm
except ImportError:
    pass
else:
    raise SystemExit("BLOCKER-INERT: mlx_lm imported despite the meta-path refusal")

from whetstone.bakeoff.mlx_runtime import MlxGenerator, MlxUnavailable

print("IMPORTED-WITHOUT-MLX")

try:
    MlxGenerator(sys.argv[1], revision=sys.argv[2])
except MlxUnavailable as error:
    print("REFUSED-AT-CONSTRUCTION", str(error).replace("\\n", " "))
else:
    raise SystemExit("CONSTRUCTED: the adapter built itself with no engine behind it")
"""


class FakeMlx:
    """The engine, replaced by a recorder. Records every call; loads nothing; downloads nothing.

    This is what makes the bulk of this file runnable on CI's actual environment. It is
    deliberately not a `Mock`: the assertions below are about *which arguments were passed*, and
    a recorder whose call log is a plain list of `(args, kwargs)` pairs makes a failure message
    show the call as it was made rather than as a matcher's opinion of it.
    """

    def __init__(self) -> None:
        #: Every `mlx_lm.utils.load(...)` the adapter made, as `(args, kwargs)`.
        self.load_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        #: Every `mlx_lm.generate.generate(...)` the adapter made, as `(args, kwargs)`.
        self.generate_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        #: Every `mlx.core.argmax(...)` the sampler made, as `(array, axis)`.
        self.argmax_calls: list[tuple[Any, Any]] = []
        #: What `generate` returns. Reassigned by the test that checks a non-text answer.
        self.answer: Any = ANSWER
        self.model = object()
        self.tokenizer = object()

    def load(self, *args: Any, **kwargs: Any) -> tuple[Any, Any]:
        self.load_calls.append((args, kwargs))
        return self.model, self.tokenizer

    def generate(self, *args: Any, **kwargs: Any) -> Any:
        self.generate_calls.append((args, kwargs))
        return self.answer

    def argmax(self, array: Any, axis: Any = None) -> Any:
        self.argmax_calls.append((array, axis))
        return ARGMAX_TOKEN


@pytest.fixture
def fake_mlx(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeMlx]:
    """Install a fake `mlx_lm` and `mlx.core` in `sys.modules`, for the duration of one test.

    This works — and works without reloading anything — precisely *because* the adapter imports
    `mlx_lm` inside its functions rather than at module scope. The substitution is therefore not
    merely a convenience: it exercises the same import discipline CI depends on, and it would
    stop working on the day someone hoisted the import to the top of the module, which is the day
    the suite stops being collectable under a plain `uv sync`.

    `monkeypatch.setitem` restores `sys.modules` afterwards, so a machine that *does* have the
    extra installed gets its real modules back before the next test runs.
    """
    fake = FakeMlx()

    mlx = ModuleType("mlx")
    core = ModuleType("mlx.core")
    core.argmax = fake.argmax  # type: ignore[attr-defined]
    mlx.core = core  # type: ignore[attr-defined]

    mlx_lm = ModuleType("mlx_lm")
    utils = ModuleType("mlx_lm.utils")
    utils.load = fake.load  # type: ignore[attr-defined]
    generate = ModuleType("mlx_lm.generate")
    generate.generate = fake.generate  # type: ignore[attr-defined]
    mlx_lm.utils = utils  # type: ignore[attr-defined]
    mlx_lm.generate = generate  # type: ignore[attr-defined]

    modules = {
        "mlx": mlx,
        "mlx.core": core,
        "mlx_lm": mlx_lm,
        "mlx_lm.utils": utils,
        "mlx_lm.generate": generate,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    yield fake


@pytest.fixture
def model_dir(tmp_path: Path) -> Path:
    """A directory shaped enough like a model to be accepted, holding no weights whatsoever.

    `config.json` and nothing else, because that is the first file `mlx_lm.utils.load` opens and
    therefore the cheapest honest precondition this adapter can check. It is emphatically not a
    claim that the directory contains a working model — that claim can only be made by loading
    one, which is aspect 4's job and needs gigabytes this test suite will never have.
    """
    path = tmp_path / "base"
    path.mkdir()
    (path / "config.json").write_text("{}\n", encoding="utf-8")
    return path


def _built(model_dir: Path) -> MlxGenerator:
    """The adapter under test, built the way every scored run will build it."""
    return MlxGenerator(model_dir, revision=REVISION)


def test_the_module_imports_and_refuses_to_construct_where_mlx_does_not_exist(
    model_dir: Path,
) -> None:
    """CI's real environment, reproduced deliberately: no engine, and both halves asserted.

    Two claims, and they pull in opposite directions, which is why both are made in one probe.
    The module must **import** with mlx absent — otherwise `uv run pytest` stops being runnable
    under the plain `uv sync` CI performs (`ci.yml:29-32`), and the fix reached for under
    deadline is the dev-group dependency `pyproject.toml:26-29` refuses. And it must **refuse to
    construct**, naming the command that fixes it — because an adapter that imported cleanly and
    then failed somewhere deep inside a generate call would report the missing extra as a
    generation failure, which is a base model scoring zero for a reason that has nothing to do
    with the base model.
    """
    probe = subprocess.run(
        [sys.executable, "-c", dedent(_NO_MLX_PROBE), str(model_dir), REVISION],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent,
    )

    assert probe.returncode == 0 and "IMPORTED-WITHOUT-MLX" in probe.stdout, (
        f"whetstone.bakeoff.mlx_runtime did not import without mlx (exit {probe.returncode}).\n"
        f"stdout: {probe.stdout}\nstderr: {probe.stderr}\n\n"
        "WHY THIS IS A FAILURE: `import mlx_lm` must live inside this module's functions, not at"
        " its top. `.github/workflows/ci.yml:32` runs the suite under a plain `uv sync`, which"
        " does not install the `mlx` extra, so a module-scope import makes this file"
        " uncollectable there — and the fix reached for under deadline is to move `mlx-lm` into"
        " the `dev` group, which `pyproject.toml:26-29` refuses because a dev-group inference"
        " library is one careless import away from the reward path."
    )
    assert "BLOCKER-INERT" not in probe.stdout, (
        "the probe's mlx blocker did not bite, so its success proves nothing.\n\n"
        "WHY THIS IS A FAILURE: the point of the subprocess is to answer the question with mlx"
        " forcibly absent. If the meta-path refusal is not in effect, this test degrades into"
        ' "mlx happens not to be installed here", which is the machine-dependent answer it was'
        " written to replace."
    )
    assert "REFUSED-AT-CONSTRUCTION" in probe.stdout, (
        f"the adapter did not refuse to construct with no engine behind it.\nstdout:"
        f" {probe.stdout}\nstderr: {probe.stderr}\n\n"
        "WHY THIS IS A FAILURE: the missing extra must surface as its own named error at the"
        " moment the adapter is built. Deferred to the first generate call it would be recorded"
        " as a generation that produced no patch, and a candidate base would be published as"
        " having solved nothing when what was actually missing was a `uv sync --extra mlx`."
    )
    assert "uv sync --extra mlx" in probe.stdout, (
        f"the refusal did not name the command that fixes it: {probe.stdout!r}.\n\n"
        "WHY THIS IS A FAILURE: this is the one error in the bake-off whose remedy is a single"
        " documented command. An `ImportError: No module named 'mlx_lm'` costs the reader a"
        " search through `pyproject.toml` to discover that the dependency is optional and what"
        " the extra is called."
    )


def test_a_bare_repo_id_is_refused_and_nothing_is_loaded(
    fake_mlx: FakeMlx,
) -> None:
    """The offline guarantee, asserted where it is actually decided. *(adversarial)*

    `mlx_lm.utils.load` distinguishes a local directory from a Hub repo id with `Path.exists()`
    and nothing else (`utils.py:218-256`), so handing it `REPO_ID` is a download — silent,
    successful, and producing a model whose identity is "whatever `main` pointed at when the run
    started". Every number the bake-off publishes would then rest on weights nobody recorded.
    The refusal must therefore happen *before* `load` is reached, which is why the recorded call
    log is asserted empty rather than merely inspected.
    """
    with pytest.raises(NotALocalModelDirectory) as raised:
        MlxGenerator(REPO_ID, revision=REVISION)

    message = str(raised.value)
    assert REPO_ID in message, (
        f"the refusal did not name what it refused: {message!r}.\n\n"
        "WHY THIS IS A FAILURE: the operator's next action is to replace this string with a"
        " path, and a refusal that does not quote the string back leaves them guessing which of"
        " their arguments was wrong."
    )
    assert fake_mlx.load_calls == [], (
        f"load was called with a repo id: {fake_mlx.load_calls!r}.\n\n"
        "WHY THIS IS A FAILURE: this is the download, and it is the whole point of the check."
        " `load()` treats any non-existent path as a HuggingFace repo id, so reaching it at all"
        " means the scored run fetched weights over the network at an unpinned revision — an"
        " unreproducible measurement that looks identical to a reproducible one from the"
        " outside, which is the same defect the `environment` pins closed for the verifier."
    )


def test_a_directory_is_accepted_even_when_it_is_named_like_a_repo_id(
    tmp_path: Path, fake_mlx: FakeMlx
) -> None:
    """Anti-vacuity for the refusal: the rule is existence on disk, not a slash in the string.

    Without this, `NotALocalModelDirectory` could be implemented as "contains a `/`" — which
    refuses every absolute path on this platform and would be caught by no other test in this
    file, since every other model directory here is handed over as a `Path` object.
    """
    path = tmp_path / REPO_ID
    path.mkdir(parents=True)
    (path / "config.json").write_text("{}\n", encoding="utf-8")

    generator = MlxGenerator(str(path), revision=REVISION)

    assert generator.model_path == path.resolve()
    assert len(fake_mlx.load_calls) == 1, (
        f"the engine was not asked to load anything: {fake_mlx.load_calls!r}.\n\n"
        "WHY THIS IS A FAILURE: a repo-id-shaped name that exists on disk is a local directory"
        " and must load offline like any other. A check that refused it would force the operator"
        " to rename the directory the Hub's own download tool created, and the rename is exactly"
        " the step that loses the record of which repo the weights came from."
    )


def test_a_directory_that_holds_no_config_is_refused(tmp_path: Path, fake_mlx: FakeMlx) -> None:
    """An empty directory is not a model, and saying so here costs one line instead of a stack.

    `load` opens `config.json` first; handed a directory without one it raises a bare
    `FileNotFoundError` from inside the library, which names a path the operator never typed.
    """
    empty = tmp_path / "not-a-model"
    empty.mkdir()

    with pytest.raises(NotALocalModelDirectory) as raised:
        MlxGenerator(empty, revision=REVISION)

    assert "config.json" in str(raised.value)
    assert fake_mlx.load_calls == []


def test_a_path_that_is_not_a_directory_is_refused(tmp_path: Path, fake_mlx: FakeMlx) -> None:
    """A file is not a directory, and `Path.exists()` cannot tell the difference.

    That is the precise gap between this adapter's check and `load`'s own: `exists()` is true for
    a file, so a path pointing at `config.json` itself — an easy mistake when tab-completing —
    takes the *local* branch inside `load` and fails obscurely rather than being refused here.
    """
    file = tmp_path / "config.json"
    file.write_text("{}\n", encoding="utf-8")

    with pytest.raises(NotALocalModelDirectory):
        MlxGenerator(file, revision=REVISION)

    assert fake_mlx.load_calls == []


def test_an_unpinned_revision_is_refused(model_dir: Path, fake_mlx: FakeMlx) -> None:
    """A blank revision records nothing, and a provenance block full of nothing is worse than none.

    Aspect 4 publishes what generated each patch. `revision=""` would serialise cleanly, read as
    a filled-in field, and identify no snapshot at all — a reproducibility claim that cannot be
    checked and therefore cannot be falsified.
    """
    with pytest.raises(ValueError):
        MlxGenerator(model_dir, revision="   ")

    assert fake_mlx.load_calls == []


def test_load_is_given_the_resolved_directory_and_the_pinned_revision(
    model_dir: Path, fake_mlx: FakeMlx
) -> None:
    """The call `mlx-lm==0.31.3` documents, made with the arguments that keep it offline.

    The path is asserted to still be a directory *at the moment it was passed*, which is the
    property `load` branches on. Asserting the string alone would pass against an adapter that
    validated one path and then passed another — a plausible slip once a resolved path and an
    as-typed path both exist in the same constructor.
    """
    _built(model_dir)

    assert len(fake_mlx.load_calls) == 1, f"expected exactly one load: {fake_mlx.load_calls!r}"
    args, kwargs = fake_mlx.load_calls[0]

    assert Path(args[0]).is_dir(), (
        f"load was handed something that is not a directory on disk: {args[0]!r}.\n\n"
        "WHY THIS IS A FAILURE: `load()` takes the local branch only for a path that exists"
        " (`utils.py:218-256`); everything else is a Hub repo id and a download. A validated"
        " path that is not the passed path leaves the check in place and the guarantee gone."
    )
    assert Path(args[0]).resolve() == model_dir.resolve()
    assert kwargs.get("revision") == REVISION, (
        f"the pinned revision did not reach load: {kwargs!r}.\n\n"
        "WHY THIS IS A FAILURE: `revision` is what makes a later run comparable to this one."
        " For a local directory `load()` does not consult it — the download branch is not taken"
        " — so passing it is belt-and-braces there; but the day the path is anything else, an"
        " absent revision is an unpinned fetch, and this assertion is what stops that arriving"
        " unnoticed."
    )


def test_generation_asks_for_an_explicit_greedy_sampler(model_dir: Path, fake_mlx: FakeMlx) -> None:
    """Greedy is *this adapter's* decision, not a version's default. AC7.

    `mlx-lm==0.31.3` decodes greedily when handed no sampler (`generate.py:386`), so passing
    nothing would be correct today and silently wrong on the day the default moves — and the
    symptom of that would be a bake-off comparing draws, published as a comparison of bases. So
    the sampler is passed explicitly, and the assertion is twofold: that a sampler was passed at
    all, and that the callable passed really takes an argmax over the final axis. Checking only
    the presence of the kwarg would accept a sampler that sampled.
    """
    generator = _built(model_dir)
    generator.generate("fix the off-by-one")

    assert len(fake_mlx.generate_calls) == 1
    _, kwargs = fake_mlx.generate_calls[0]

    assert "sampler" in kwargs, (
        f"no sampler was passed to generate: {sorted(kwargs)!r}.\n\n"
        "WHY THIS IS A FAILURE: with no sampler the decoding rule is whatever the installed"
        " `mlx-lm` defaults to. That is greedy in 0.31.3 and is a property of the version, not"
        " of this repository — a lockfile bump could make every bake-off number a sample from a"
        " distribution while nothing in the diff mentioned decoding at all."
    )

    logprobs = object()
    token = kwargs["sampler"](logprobs)

    assert fake_mlx.argmax_calls == [(logprobs, -1)], (
        f"the sampler did not take an argmax over the last axis: {fake_mlx.argmax_calls!r}.\n\n"
        "WHY THIS IS A FAILURE: a sampler kwarg that is present but not greedy passes the check"
        " above and reintroduces exactly the non-determinism it was added to prevent. `axis=-1`"
        " is the vocabulary axis; an argmax over any other axis returns a token id that indexes"
        " the wrong thing entirely."
    )
    assert token == ARGMAX_TOKEN

    passed = [knob for knob in NOT_A_KNOB if knob in kwargs]
    assert passed == [], (
        f"generate was passed sampling knobs that this API does not take: {passed!r}.\n\n"
        "WHY THIS IS A FAILURE: `mlx-lm==0.31.3` injects sampling as a callable. A"
        " `temperature=` argument does not configure the sampler — it flows into `**kwargs`,"
        " where it is either ignored (leaving the caller believing they set something) or fatal."
        " The first of those is a bake-off whose decoding is not what its own code says it is."
    )


def test_the_prompt_reaches_the_engine_verbatim_and_its_answer_returns_unchanged(
    model_dir: Path, fake_mlx: FakeMlx
) -> None:
    """The adapter transports; it does not edit. Neither the question nor the answer.

    Both halves matter for a different reason. The prompt is `rendering.py`'s fixed, hashed
    contract (PRD M7b) — an adapter that decorated it would make the recorded hash describe
    something other than what the model was shown. The answer is raw model output, and tidying it
    here would move a decision that belongs to `patch.py`, where "no diff" and "a wrong diff" are
    deliberately kept distinguishable, into a module that has no vocabulary for the difference.
    """
    prompt = "You are fixing a bug in a Python repository.\n\n# Problem\n\nIt is off by one.\n"

    answer = _built(model_dir).generate(prompt)

    args, _ = fake_mlx.generate_calls[0]
    assert args[0] is fake_mlx.model and args[1] is fake_mlx.tokenizer, (
        f"generate was not given the loaded model and tokenizer positionally: {args!r}.\n\n"
        "WHY THIS IS A FAILURE: `mlx_lm.generate.generate(model, tokenizer, prompt, ...)` is the"
        " pinned call shape for 0.31.3. Anything else is a different function than the one this"
        " adapter's docstring claims to be calling."
    )
    assert args[2] == prompt, (
        f"the prompt was altered on its way to the engine: {args[2]!r} vs {prompt!r}.\n\n"
        "WHY THIS IS A FAILURE: the prompt is content-hashed as provenance. If this layer"
        " prepends, wraps or templates anything, the published hash describes a string the model"
        " never saw, and M7b's rule that the contract is fixed and disclosed becomes unauditable."
    )
    assert answer.encode("utf-8") == ANSWER.encode("utf-8"), (
        f"the answer was altered on its way back: {answer!r} vs {ANSWER!r}.\n\n"
        "WHY THIS IS A FAILURE: `Generator.generate` returns raw model output by contract."
        " Stripping fences or trimming prose here would silently take over `patch.py`'s job, and"
        " `patch.py` is where the distinction between 'wrote no diff' and 'wrote a wrong diff' —"
        " the distinction P1's pivot signal depends on — is actually made."
    )


def test_the_generation_budget_is_passed_and_is_not_left_to_the_library(
    model_dir: Path, fake_mlx: FakeMlx
) -> None:
    """A truncated patch must be a recorded budget, not an unrecorded default.

    `patch.py` treats output that stops mid-hunk as an attempted patch and lets `git apply`
    charge it at `patch-apply`, precisely so a too-small budget is visible in the report rather
    than absorbed into "the model got it wrong". That is only readable if the budget is a number
    this repository chose and recorded.
    """
    generator = MlxGenerator(model_dir, revision=REVISION, max_tokens=64)
    generator.generate("anything")

    _, kwargs = fake_mlx.generate_calls[0]
    assert kwargs.get("max_tokens") == 64, f"budget not passed through: {kwargs!r}"
    assert generator.provenance()["max_tokens"] == "64"


def test_an_answer_that_is_not_text_is_refused_rather_than_coerced(
    model_dir: Path, fake_mlx: FakeMlx
) -> None:
    """`str(obj)` is the quiet way this contract breaks; a `TypeError` is the loud way.

    `mlx_lm.generate.generate` returns a string in 0.31.3 — and returned a
    `GenerationResponse` in neighbouring versions. Coercing whatever arrives would hand
    `patch.py` a repr, which contains no diff, which is reported as a base that produced no
    patch: a version mismatch published as a model result.
    """
    fake_mlx.answer = object()

    with pytest.raises(TypeError) as raised:
        _built(model_dir).generate("anything")

    assert "str" in str(raised.value)


def test_provenance_records_exactly_what_generated_a_patch(
    model_dir: Path, fake_mlx: FakeMlx
) -> None:
    """Everything aspect 4 needs to reproduce a patch, in one read-only mapping of strings.

    Strings throughout so the block serialises to JSON without a codec, and read-only so a
    caller assembling a report cannot edit the record on its way into the report — provenance
    that the reporting layer can amend is provenance about the reporting layer.
    """
    generator = _built(model_dir)
    record = generator.provenance()

    assert record["model_path"] == str(model_dir.resolve())
    assert record["revision"] == REVISION
    assert record["sampler"] == SAMPLER
    assert record["chat_template"] == CHAT_TEMPLATE
    assert record["mlx_lm"] == PINNED_MLX_LM
    assert all(isinstance(value, str) for value in record.values()), (
        f"provenance holds a non-string value: {dict(record)!r}.\n\n"
        "WHY THIS IS A FAILURE: this block is written into a run record that is read back by a"
        " human and by aspect 4's report. A `Path` or an `int` in it serialises differently"
        " depending on which writer touched it, and a provenance field whose spelling depends on"
        " the writer cannot be compared between two runs."
    )

    with pytest.raises(TypeError):
        record["revision"] = "something else"  # type: ignore[index]

    assert "greedy" in SAMPLER.lower(), (
        f"the sampler description does not say what the sampler does: {SAMPLER!r}.\n\n"
        "WHY THIS IS A FAILURE: the description is what a reader of the published run sees in"
        " place of the code. If it does not name the decoding rule, the run's determinism claim"
        " rests on the reader taking this repository's word for it."
    )
    assert fake_mlx.load_calls, (
        "the adapter never loaded anything, so this record describes nothing at all"
    )


def test_the_adapter_satisfies_the_generator_protocol(model_dir: Path, fake_mlx: FakeMlx) -> None:
    """The swap aspect 2 depends on: stub out, engine in, and no call site changes.

    `isinstance` against a `runtime_checkable` protocol asserts that an attribute named
    `generate` exists and nothing at all about its signature, so the signature is compared
    directly too — a `generate(self, prompt, *, max_tokens)` would pass the first check and break
    every caller written against the stub.
    """
    generator = _built(model_dir)

    assert isinstance(generator, Generator)
    assert inspect.signature(MlxGenerator.generate) == inspect.signature(Generator.generate), (
        f"MlxGenerator.generate{inspect.signature(MlxGenerator.generate)} does not match"
        f" Generator.generate{inspect.signature(Generator.generate)}.\n\n"
        "WHY THIS IS A FAILURE: every test in this slice substitutes `StubGenerator` for this"
        " class. If the two do not accept the same call, the substitution is a fiction and the"
        " harness is only ever proven against the double — with the difference discovered on the"
        " one run that has a real model in it and gigabytes already on disk."
    )


@requires_mlx
def test_the_installed_mlx_lm_is_the_version_these_call_shapes_were_read_against() -> None:
    """The version canary. It exists to fail on a lockfile bump, and that is its whole value.

    Every claim this adapter makes about `mlx_lm` — that `load` takes `revision`, that sampling
    is a callable, that greedy is what argmax-over-the-last-axis means here — was read against
    `mlx-lm==0.31.3` (`uv.lock:485`). None of it is guaranteed across versions. A silent bump
    would leave the code compiling, the tests green, and the decoding rule unknown; this fails
    instead, and the required response is to re-read the API and update `PINNED_MLX_LM`, never to
    relax the assertion.
    """
    from importlib.metadata import version

    assert version("mlx-lm") == PINNED_MLX_LM, (
        f"installed mlx-lm is {version('mlx-lm')}, not the pinned {PINNED_MLX_LM}.\n\n"
        "WHY THIS IS A FAILURE: this adapter's call shapes and its determinism claim were both"
        " verified against one version. Re-read `utils.load` and `generate.generate` against the"
        " new one and update the pin deliberately; do not widen this assertion to a range,"
        " because the thing being pinned is a reading, not a dependency."
    )

    from mlx_lm.generate import generate_step, stream_generate
    from mlx_lm.utils import load

    assert "revision" in inspect.signature(load).parameters, (
        "mlx_lm.utils.load no longer takes a `revision` argument.\n\n"
        "WHY THIS IS A FAILURE: the revision is how a published run says which weights it used."
        " If the library stopped accepting it, this adapter is passing an argument into"
        " `**kwargs` and recording a pin that pins nothing."
    )
    # Corrected 2026-07-31, by this canary firing the first time the extra was installed. It
    # used to assert `sampler` on `stream_generate`, and that was simply wrong about 0.31.3:
    # neither `generate` nor `stream_generate` names it. Both take `**kwargs` and forward, and
    # `generate_step` is the function that actually names `sampler`. The old assertion would
    # have failed on a correct library forever — a canary that cries on a healthy bird is worse
    # than none, because the documented response to it firing is "re-read the API", and a
    # reader who did that would have concluded the injection had been removed when it had not.
    assert "sampler" not in inspect.signature(stream_generate).parameters, (
        "mlx_lm.generate.stream_generate now names `sampler` directly.\n\n"
        "WHY THIS IS A FAILURE: not because it is broken, but because the call path this"
        " adapter was read against has changed shape. Re-read where the sampler is consumed"
        " before trusting the greedy claim."
    )
    step = inspect.signature(generate_step).parameters
    assert "sampler" in step, (
        "mlx_lm.generate.generate_step no longer accepts an injected `sampler` callable.\n\n"
        "WHY THIS IS A FAILURE: greedy decoding is asserted in this repository by passing the"
        " sampler explicitly through `generate`'s `**kwargs`. `generate_step` is where that"
        " keyword lands, so if the name is gone the explicit greedy request no longer reaches"
        " anything and the real decoding rule is once again whatever the library chose — the"
        " exact silent regression the explicit sampler exists to prevent."
    )
    assert not any(p.kind is p.VAR_KEYWORD for p in step.values()), (
        "mlx_lm.generate.generate_step grew a `**kwargs`.\n\n"
        "WHY THIS IS A FAILURE: today the absence of `**kwargs` here is a real safety property"
        " — the sampler keyword travels through two pass-through layers, and `generate_step`"
        " raising TypeError on an unknown keyword is what stops a renamed parameter from being"
        " swallowed in silence. With `**kwargs` present, a future rename would leave this"
        " adapter passing a sampler nothing reads, and every test here would still be green."
    )


@requires_mlx
def test_the_greedy_sampler_really_selects_the_argmax_under_the_real_engine() -> None:
    """The one claim the fake cannot make: that `greedy_sampler` is greedy against real arrays.

    Everything else in this file proves the sampler *delegates to* `mx.argmax`; a recorder cannot
    prove that `mx.argmax(x, axis=-1)` picks the highest-scoring token, because that is the
    engine's behaviour and not ours. Needs no weights — three floats are enough.
    """
    import mlx.core as mx

    logprobs = mx.array([[-3.0, -0.1, -2.5, -9.0]])

    assert int(greedy_sampler(logprobs).item()) == 1, (
        f"greedy_sampler did not select the highest-scoring token: {greedy_sampler(logprobs)!r}."
        "\n\nWHY THIS IS A FAILURE: greedy decoding is what makes two bake-off runs of the same"
        " base comparable. A sampler that returns anything but the argmax turns the published"
        " difference between two candidate bases into a difference between two draws."
    )
