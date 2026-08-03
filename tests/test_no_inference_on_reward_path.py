"""Pins the one claim the whole project rests on: no model is consulted on the reward path.

The failure this prevents: a single `import openai` — or `import mlx_lm`, or
`from .judge import score` — inside ``src/whetstone/verify/`` turns the reward from
deterministic re-execution into a model's opinion of itself, which is the
up-to-35%-false-positive LLM-as-judge this project exists to replace. Every other test in
the suite would stay green while it happened, because a judge that agrees with the tests
looks exactly like a verifier.

So this walks every module under the guarded roots with ``ast`` — never importing them,
because importing runs side effects and reports on the installed venv rather than on the
source that ships — and asserts none of them reaches an inference client or a first-party
module whose name is inference-shaped. A docstring may say "model" as often as it likes;
``ast`` reads imports, not prose.

**Scoped, not tree-wide.** ``mlx-lm`` is a declared optional dependency
(``pyproject.toml``) and P2's rollout code will import it legitimately. A tree-wide ban
would be false the moment P2 lands, and a guard that has to be weakened is a guard that
gets weakened. The ban applies to the reward path and nowhere else.

**Three roots**: ``verify/`` and ``tasks/`` since P1 slice 2, and the single module
``cli.py`` since the bake-off — see ``GUARDED_ROOTS`` for why ingestion is inside the line
rather than next to it, and why the CLI was outside it for two slices. Widening a scoped
guard is the moment it can go quietly dead, so ``_modules`` asserts **each** root contributes
modules and control A names an import only the second root makes.

**Which roots are named is itself guarded**, by
``tests/test_reward_path_scope_is_partitioned.py``: every package and top-level module under
``src/whetstone/`` must appear here or on that file's ``EXEMPT`` mapping with a written
reason. This file answers "does a guarded module import a model?"; that one answers "is
everything either guarded or knowingly not?" — and a scoped guard needs both, because on its
own it stays green while the tree grows out from under it.

**Ported from ``<sibling>/tests/test_verify_zero_llm.py`` with three fixes**, each of which is
a live bypass here rather than a theoretical one, and each proven by a planted-violation
test below:

1. The sibling project gates its first-party half on ``if root == "<its own package name>"``,
   hardcoded. Ported verbatim, ``whetstone.judge`` sails straight through.
2. The sibling project's client list has no ``mlx``, ``mlx_lm``, ``peft`` or ``accelerate`` — a hole
   shaped exactly like Whetstone's own stack.
3. The sibling project's walk skips ``ast.ImportFrom`` nodes with ``node.level != 0``, so **relative
   imports are invisible**. The sibling project escapes this because its detection keys on the
   dotted ``<sibling>.judge`` form; our reward path is one package whose modules import each other,
   so ``from .judge import score`` would record nothing at all. Relative imports are resolved to
   their absolute dotted path from the file's position under ``src/``.

**Two anti-vacuity controls, where the sibling project ships one.** It asserts the walk observes
real imports (control A), but never that the first-party predicate actually *fires* — so fix 1
could be dropped and its own control would stay green. Control B asserts the predicate is live
for *this* project's namespace.

**The teeth are demonstrated here, not just claimed.** The planted-violation tests below
build synthetic modules in a temp directory and require the guard to flag them; real source
is never edited. Every one of them was watched failing against the verbatim port
before the three fixes landed: ``import openai`` and the function-local ``import torch``
passed straight away (the sibling got those right), while the ``mlx_lm`` and relative-import
plants and control B all failed, naming exactly the three traps above.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from textwrap import dedent

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"

#: The reward path and what authors it, and nothing else. ``verify/`` decides PASS/FAIL by
#: running the task's own tests in a sandbox and reading the executed set; nothing it does
#: needs a model, so nothing it imports may provide one.
#:
#: ``tasks/`` is inside the guard because it is where ``test_blobs`` is written, and
#: ``test_blobs`` *is* the boundary the reward path enforces — the set of paths a patch may
#: not touch and that are restored from golden before pytest runs. A model that decided
#: which files belong in that set would be deciding, one step removed, which edits count as
#: cheating, and it would do so with none of re-execution's determinism. The guard reaches
#: one layer up from the verdict for the same reason it exists at the verdict: an authored
#: boundary and a graded run are the same claim, and only one of them was previously watched.
#: Verified 2026-07-28 that this root was unguarded: a planted ``from .judge import score``
#: under ``src/whetstone/tasks/`` passed the whole file green until this tuple was widened.
#:
#: ``cli.py`` is a **file** root, not a package, and it is here because it is the reward's
#: entry point: ``cli.py:248-250`` calls ``verify_strict`` and prints the verdict a human
#: acts on. It sat outside this tuple for two slices — found by
#: ``tests/test_reward_path_scope_is_partitioned.py``, which is the file that asks whether
#: this one still describes the tree. Guarding its parent instead would be the wrong fix:
#: ``src/whetstone/`` will hold the bake-off package, which imports ``mlx_lm`` legitimately
#: and off the reward path, and a root that has to be narrowed later is a root that gets
#: narrowed under pressure. ``CONTRIBUTING.md:20`` forbids widening this tuple *to make a
#: failing check pass*; this widening adds code that was always inside the line and that
#: nothing had been watching, which is the opposite act and is recorded as such.
#:
#: ``__init__.py`` is here for a blunter reason than ``cli.py``: it **executes on every
#: import of every guarded module**, so an inference import in it would reach the reward path
#: exactly as one under ``verify/`` would. It was briefly written up as a documented residual
#: on the ground that it is twenty lines a reviewer reads in full — which is true, and is not
#: a reason. A residual is for a hole that is hard to close (cheats 6 and 10 are the
#: project's examples); this one costs a single line, and a residual nobody had to accept is
#: a residual nobody should have written.
GUARDED_ROOTS = (
    SRC / "whetstone" / "verify",
    SRC / "whetstone" / "tasks",
    SRC / "whetstone" / "cli.py",
    SRC / "whetstone" / "__init__.py",
)

#: Third-party inference clients: hosted model SDKs, local-inference runtimes, training
#: adapters, and LLM-orchestration frameworks. The set is deliberately broad — a reward
#: grounded in re-execution needs none of them, so the cost of an over-broad ban here is
#: zero while the cost of a missed one is the entire thesis.
_INFERENCE_CLIENTS = frozenset(
    {
        # Inherited from the sibling project's list.
        "openai",
        "anthropic",
        "cohere",
        "mistralai",
        "groq",
        "together",
        "replicate",
        "litellm",
        "google",  # google.generativeai / vertexai
        "vertexai",
        "boto3",  # bedrock is reached this way; the reward path has no business calling AWS
        "llama_cpp",
        "ctransformers",
        "ollama",
        "vllm",
        "transformers",
        "sentence_transformers",
        "torch",
        "tensorflow",
        "jax",
        "huggingface_hub",
        "langchain",
        "langchain_core",
        "langchain_openai",
        "llama_index",
        "guidance",
        "dspy",
        "instructor",
        "outlines",
        # Added for Whetstone (trap 2). The sibling project's list predates this project's runtime
        # choice, so it bans everyone else's inference stack and none of ours: MLX is the
        # locked local runtime and `mlx-lm` is an installable extra, while peft/accelerate/
        # trl are the LoRA path P2 will use. The inherited list had a hole shaped like us.
        "mlx",
        "mlx_lm",
        "peft",
        "accelerate",
        "trl",
        "bitsandbytes",
        "safetensors",
        "tokenizers",
        "sentencepiece",
    }
)

#: First-party module-name fragments that would smuggle inference in wearing our own coat.
#: A ``whetstone.judge`` on the reward path is the same failure as ``openai``, so the same
#: guard bans it.
_INFERENCE_FIRST_PARTY = frozenset(
    {"llm", "judge", "model", "models", "inference", "completion", "prompt", "prompts"}
)

#: The distribution's import package. Trap 1: the sibling project hardcodes its own name here, and a
#: verbatim port would leave the first-party half of the guard permanently dead for us.
_FIRST_PARTY_ROOT = "whetstone"


def _modules(roots: tuple[Path, ...] = GUARDED_ROOTS) -> list[Path]:
    """Every module under every guarded root, asserting **each root** contributes one.

    Per-root rather than in aggregate, and that distinction is the whole point once there is
    more than one root: a misspelled or since-moved root matches nothing, and an aggregate
    ``assert files`` stays green on the strength of the roots that still exist. The dead root
    would then be watching nothing while reading, in the failure message, as though it were
    guarded — a guard that has quietly stopped guarding half of what it names.

    **A root is a directory or a single module**, because ``cli.py`` is reward-path code with
    no package of its own and guarding its parent would drag in every future sibling — the
    bake-off runner included, which imports ``mlx_lm`` legitimately and would then fail this
    file. The two shapes are branched on explicitly rather than left to ``rglob``: ``rglob``
    on a file path yields nothing at all, so a file root would have contributed zero modules
    in silence had the assertion below not been per-root. That is not hypothetical — adding
    ``cli.py`` before this branch existed is exactly how it was observed, and the assertion
    is what caught it.
    """
    assert roots, "no guarded roots — this guard would pass vacuously"
    files: list[Path] = []
    for root in roots:
        found = [root] if root.is_file() else sorted(root.rglob("*.py"))
        assert found, (
            f"no modules found for the guarded root {root} — the root is dead (moved, "
            "renamed, or misspelled) and is guarding nothing, while the other roots keep "
            "this file green. A root naming a single module fails here the moment that "
            "module moves; a directory root fails here the moment it holds no Python."
        )
        files.extend(found)
    return sorted(files)


def _dotted_package(path: Path, src_root: Path) -> str:
    """The package a module lives in, e.g. ``whetstone.verify`` for ``verify/strict.py``.

    Dropping the final part is right for both cases: a module contributes its own name,
    and ``__init__.py`` contributes the literal ``__init__``. Neither belongs in the
    package a relative import counts up from.
    """
    parts = path.relative_to(src_root).with_suffix("").parts
    return ".".join(parts[:-1])


def _resolve_relative(package: str, level: int) -> str:
    """The absolute prefix a ``level``-dotted relative import refers to (trap 3).

    ``level == 1`` is the module's own package; each further dot climbs one. Climbing past
    the top is not valid Python, so it collapses to the empty prefix rather than raising —
    an unparseable import is not this guard's business to adjudicate.
    """
    parts = package.split(".") if package else []
    ascent = level - 1
    return ".".join(parts[: len(parts) - ascent]) if ascent <= len(parts) else ""


def _imported_names(path: Path, src_root: Path) -> list[tuple[str, int]]:
    """Every module name ``path`` imports (dotted, absolute), with the line it appears on.

    ``ast.walk`` so an import nested inside a function counts too — a guard that read only
    the top of the file would be sidestepped by indenting one line.

    Both halves of ``from X import y`` are recorded: the module *and* each imported name
    appended to it. ``from whetstone.verify import judge`` names a module in its alias, not
    in ``node.module``, so recording only the module would miss it — the same shape of hole
    as trap 3, reached by a different syntax.
    """
    tree = ast.parse(path.read_bytes(), filename=str(path))
    package = _dotted_package(path, src_root)
    names: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _absolute_module(node, package)
            if not base:
                continue
            names.append((base, node.lineno))
            names.extend(
                (f"{base}.{alias.name}", node.lineno) for alias in node.names if alias.name != "*"
            )
    return names


def _absolute_module(node: ast.ImportFrom, package: str) -> str:
    """The absolute dotted module an ``ImportFrom`` names, relative or not (trap 3).

    The sibling project writes ``if node.level == 0`` here and drops everything else on the
    floor, which makes every relative import invisible to the walk. Resolving instead of
    skipping is what closes that bypass.
    """
    if node.level == 0:
        return node.module or ""
    prefix = _resolve_relative(package, node.level)
    if node.module is None:
        return prefix
    return f"{prefix}.{node.module}" if prefix else node.module


def _is_inference_import(dotted: str) -> bool:
    root = dotted.split(".")[0]
    if root in _INFERENCE_CLIENTS:
        return True
    if root == _FIRST_PARTY_ROOT:
        parts = set(dotted.split("."))
        return bool(parts & _INFERENCE_FIRST_PARTY)
    return False


def _offenders(paths: list[Path], src_root: Path) -> list[str]:
    """Every inference-shaped import in ``paths``, formatted as ``file:line imports 'x'``."""
    return [
        f"{path.relative_to(src_root)}:{lineno} imports {dotted!r}"
        for path in paths
        for dotted, lineno in _imported_names(path, src_root)
        if _is_inference_import(dotted)
    ]


@pytest.fixture
def plant(tmp_path: Path) -> Callable[[str], list[str]]:
    """Writes a synthetic module at the reward path's own package position and scans it.

    Synthetic rather than real: proving the guard has teeth by editing ``src/`` would mean
    committing a violation and trusting a later revert. The temp tree reproduces the one
    thing the guard reads from the filesystem — a module's position under ``src/``, which
    is what relative imports resolve against — so a plant is scanned exactly as the real
    file would be.
    """

    def _plant(source: str, *, name: str = "planted.py") -> list[str]:
        root = tmp_path / "src" / "whetstone" / "verify"
        root.mkdir(parents=True, exist_ok=True)
        module = root / name
        module.write_text(dedent(source).lstrip(), encoding="utf-8")
        return _offenders([module], tmp_path / "src")

    return _plant


def test_no_module_on_the_reward_path_imports_an_inference_client() -> None:
    """THE positioning, in code: the reward is re-execution, so no model may be reachable.

    Whetstone's reward is the exit status of the task's own tests, run in a sandbox, with
    the executed node-id set checked against the task contract. That is the entire answer
    to "isn't this an LLM judge with extra steps?". An inference client anywhere under
    ``verify/`` makes the answer false while every other test stays green.
    """
    offenders = _offenders(_modules(), SRC)
    assert not offenders, (
        "an inference client is imported on the reward path ("
        + ", ".join(str(root.relative_to(SRC.parent)) for root in GUARDED_ROOTS)
        + "):\n  "
        + "\n  ".join(offenders)
        + "\n\nWHY THIS IS A FAILURE: the reward is deterministic re-execution — the task's"
        " own tests, run in a sandbox, with the executed set checked against the contract."
        " No model is consulted, and that is the project's whole claim. A model SDK on the"
        " reward path turns the grounded reward into a judge's guess, which is the failure"
        " mode Whetstone exists to design out. If a LATER phase legitimately needs a model,"
        " it belongs off the reward path (P2's rollouts), and this guard is narrowed as a"
        " deliberate, visible decision — never sidestepped."
    )


def test_the_guard_sees_the_imports_the_reward_path_actually_makes() -> None:
    """Anti-vacuity control A: the walk really is reading imports out of these files.

    A walk that parsed nothing, or an ``_imported_names`` that silently returned empty,
    would satisfy the ban above no matter what the reward path imported. This pins that
    the mundane, legitimate imports the verifier makes are observed.
    """
    seen = {dotted for path in _modules() for dotted, _lineno in _imported_names(path, SRC)}

    # The verifier composes its own verdict semantics and sandbox; if the walk sees these,
    # it is really reading imports rather than reporting an empty set.
    assert any(name.startswith("whetstone.verify.verdict") for name in seen), seen
    assert any(name.startswith("whetstone.verify.sandbox") for name in seen), seen
    # And stdlib imports are seen too, so the walk is not somehow first-party-only.
    assert "subprocess" in seen, seen
    # Named because `load_task` is imported by `whetstone/tasks/manifest.py` and by nothing
    # else under the guarded roots: it is the one observation that can only come from the
    # ingestion root, so it proves the second root is really being read rather than merely
    # listed. `_modules` proves the root has files; this proves those files are parsed.
    assert "whetstone.verify.task.load_task" in seen, seen
    # The same observation for the third root, which needs it most: a file root reaches the
    # walk down a branch of `_modules` no directory root uses, and `rglob` yields nothing for
    # a file — so a mistake there is silent by construction. `MintFailed` is imported by
    # `whetstone/cli.py` and by nothing else under the guarded roots, so seeing it here can
    # only mean the CLI itself was parsed.
    assert "whetstone.tasks.mine.MintFailed" in seen, seen
    # And for the fourth root, on the same principle. `PackageNotFoundError` is imported by
    # `whetstone/__init__.py` and by no other module under the guarded roots, so seeing it
    # here can only mean the package's own `__init__` was parsed rather than merely listed.
    assert "importlib.metadata.PackageNotFoundError" in seen, seen


def test_the_first_party_predicate_is_live_for_whetstone_not_the_sibling() -> None:
    """Anti-vacuity control B: the ban on first-party inference modules actually fires.

    This is the control the sibling project does not ship, and the reason trap 1 is dangerous.
    Its control asserts the walk sees *imports*; it never asserts that
    ``_is_inference_import`` returns True for anything. Port the hardcoded package name
    verbatim and the first-party half of this guard is dead for every Whetstone module,
    with the sibling's own control still green and this file still passing.
    """
    assert _is_inference_import("whetstone.judge") is True
    assert _is_inference_import("whetstone.verify.llm") is True
    # And not blanket-true for the namespace: an ordinary first-party import is allowed,
    # or the assertion above would hold under a predicate that simply returned True.
    assert _is_inference_import("whetstone.verify.strict") is False


def test_a_planted_hosted_model_sdk_is_flagged(plant: Callable[[str], list[str]]) -> None:
    """The base case the sibling project already got right, re-proven here rather than assumed."""
    offenders = plant("import openai\n")
    assert offenders == ["whetstone/verify/planted.py:1 imports 'openai'"], offenders


def test_a_planted_mlx_import_is_flagged(plant: Callable[[str], list[str]]) -> None:
    """Trap 2: the inherited client list had a hole shaped like Whetstone's own runtime.

    MLX is the locked local runtime and ``mlx-lm`` an installable extra, so of every name
    in the list these are the ones most likely to be reached for by accident. The sibling
    project's list contains none of them; ported verbatim, this test fails.
    """
    assert plant("import mlx_lm\n")
    assert plant("import mlx.core as mx\n")
    assert plant("from mlx_lm import load\n")
    assert plant("import peft\n")
    assert plant("import accelerate\n")


def test_a_planted_relative_import_of_a_judge_module_is_flagged(
    plant: Callable[[str], list[str]],
) -> None:
    """Trap 3 — the bypass the sibling project would miss, and the one that matters most here.

    The sibling project's walk skips every ``ImportFrom`` with ``node.level != 0``, so a
    relative import records nothing at all. It survives that because its first-party
    detection keys on the dotted ``<sibling>.judge`` form written out in full. Whetstone's
    reward path is a single package whose modules import one another, so
    ``from .judge import score`` is the *natural* way to write the violation and it would be
    invisible.
    """
    offenders = plant("from .judge import score\n")

    # Asserted as the exact resolved paths, not merely "something fired": the fix is only
    # correct if the single leading dot resolves to the planted module's OWN package. A
    # resolver off by one level would still flag this line while pointing at the wrong
    # module, and would then mis-resolve every deeper relative import in real source.
    assert offenders == [
        "whetstone/verify/planted.py:1 imports 'whetstone.verify.judge'",
        "whetstone/verify/planted.py:1 imports 'whetstone.verify.judge.score'",
    ], offenders

    # The same hole reached by the other two relative syntaxes. ``from . import judge``
    # names the offending module in its alias rather than in ``node.module``, so recording
    # only the module would miss it even with the levels resolved correctly.
    assert plant("from . import judge\n") == [
        "whetstone/verify/planted.py:1 imports 'whetstone.verify.judge'"
    ]
    assert plant("from ..llm import complete\n") == [
        "whetstone/verify/planted.py:1 imports 'whetstone.llm'",
        "whetstone/verify/planted.py:1 imports 'whetstone.llm.complete'",
    ]


def test_a_planted_function_local_import_is_flagged(plant: Callable[[str], list[str]]) -> None:
    """Indenting is not a bypass: ``ast.walk`` descends, which the sibling project got right.

    A guard that read only module-level nodes would be defeated by moving the import
    inside the function that uses it — which is where a smuggled one would naturally go.
    """
    offenders = plant(
        """
        def score(patch: str) -> float:
            import torch

            return float(torch.rand(1))
        """
    )
    assert offenders == ["whetstone/verify/planted.py:2 imports 'torch'"], offenders


def test_ordinary_stdlib_and_first_party_imports_are_not_flagged(
    plant: Callable[[str], list[str]],
) -> None:
    """The guard must be precise, not blunt — a false positive is how a guard gets weakened.

    A ban broad enough to catch ``subprocess`` would force ``# noqa``-shaped workarounds at
    every real call site, and the first one added would be the moment this guard stopped
    meaning anything. So the imports the reward path legitimately makes must pass cleanly.
    """
    assert (
        plant(
            """
            import subprocess
            import xml.etree.ElementTree as ElementTree
            from collections.abc import Mapping
            from pathlib import Path

            from whetstone.verify.sandbox import run_confined
            from whetstone.verify.task import Task
            from whetstone.verify.verdict import Status, Verdict, reduce

            from .repo import apply_patch
            """
        )
        == []
    )
