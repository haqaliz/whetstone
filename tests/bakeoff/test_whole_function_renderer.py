"""The whole-function renderer and the format's home — this slice's measurement format.

`docs/planning/whole-function-edit-finding/measurement-run/spec.md` pins the format
("Format") and acceptance criterion 1 before any rollout ran, and every rule tested here
is that rule: the prompt poses the grammar — one block, both headers, the fence, the
body-only rule — and is byte-deterministic; a held test path is refused by name in every
spelling; and the parser never repairs — any defect refuses the whole completion with a
named reason, and no part of it is dropped while the rest proceeds.

The hygiene half is the measurement-side mirror of `test_no_inference_on_reward_path`:
bakeoff is the exempt generation side, so nothing structural stops a renderer from
importing the inference stack — which is why this module's own import list is pinned
here. The walk is `ast`, the guard's shape: nothing under `verify/` or `tasks/` is
imported at runtime (the `Task` type is annotation-only, under `TYPE_CHECKING`), and no
inference library is imported anywhere in the module; two controls keep the walk honest
— it must really read the imports, and the banned-name predicate must really fire.

No model, no network, no disk: the renderer takes its sources as a mapping of contents
already read at `base_commit`, and the parser takes text. The determinism test runs the
renderer in two subprocesses under different `PYTHONHASHSEED` values, which is the only
honest way to ask "byte-identical across processes".
"""

from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from whetstone.bakeoff.line_range import EscapingSourcePath
from whetstone.bakeoff.rendering import EmptySources, HeldTestInSources
from whetstone.bakeoff.whole_function import (
    EDIT_MARKER,
    FUNCTION_MARKER,
    MISSING_EDIT,
    MISSING_FUNCTION,
    MISSING_MARKER,
    MISSING_NAME,
    MISSING_PATH,
    MULTIPLE_BLOCKS,
    REPLACE_CLOSE,
    REPLACE_OPEN,
    SIGNATURE_RESTATEMENT,
    STRAY_MARKER,
    UNCLOSED_FENCE,
    Block,
    NoBlock,
    parse_edit_block,
    render_whole_function_prompt,
)
from whetstone.verify.task import Environment, Task

#: The operator-held test path, spelled the way a real manifest spells it. The point of the
#: held-test tests is that this exact string — and only its casing — names the answer key.
HELD = "tests/test_addition.py"

#: The module whose import list is pinned by the hygiene tests.
SRC = Path(__file__).resolve().parent.parent.parent / "src"
WHOLE_FUNCTION = SRC / "whetstone" / "bakeoff" / "whole_function.py"

#: The inference stack the measurement side must never import. `mlx` and `mlx_lm` both
#: appear because the locked runtime ships both spellings; the rest are the hosts and
#: runtimes whose presence would drag the reward's question into a model's opinion.
INFERENCE_ROOTS = frozenset(
    {"mlx", "mlx_lm", "torch", "transformers", "openai", "anthropic", "vllm", "ollama"}
)


def _task() -> Task:
    """A `Task` whose `test_blobs` holds `HELD`. Built, not mocked.
    `test_blobs` is the one field the renderer reads for refusal, so the tests assert
    against the same string a real manifest would hold.
    """
    return Task(
        task_id="whole-function",
        source="private",
        repo_url="/does/not/matter",
        base_commit="0" * 40,
        environment=Environment(python="python3.12", pins=(), import_roots=(".",)),
        problem_statement="add() subtracts instead of adding",
        fail_to_pass=(f"{HELD}::test_adds",),
        pass_to_pass=(),
        test_blobs={HELD: b"def test_adds():\n    assert add(2, 2) == 4\n"},
        provenance={},
    )


def _sources() -> dict[str, str]:
    """The oracle map the tests render: two files, `mult.py` inserted first on purpose."""
    return {
        "mult.py": "x = 1\n",
        "calc.py": "def add(a, b):\n    return a - b\n",
    }


# --- The renderer ----------------------------------------------------------------------------

EXPECTED_PROMPT = (
    "# Problem\n"
    "\n"
    "add() subtracts instead of adding\n"
    "\n"
    "# Source files\n"
    "\n"
    "These are the repository files at the checkout you are editing, shown exactly as they "
    "stand. The EDIT path names one of these files.\n"
    "\n"
    "## calc.py\n"
    "\n"
    "```\n"
    "def add(a, b):\n"
    "    return a - b\n"
    "```\n"
    "\n"
    "## mult.py\n"
    "\n"
    "```\n"
    "x = 1\n"
    "```\n"
    "\n"
    "# Response format\n"
    "\n"
    "Replace the body of one module-level function.\n"
    "\n"
    "EDIT <repository-relative path>\n"
    "FUNCTION <name>\n"
    "<<<<<<< REPLACE\n"
    "<body — the new function body, at the function's indentation>\n"
    ">>>>>>> END\n"
    "\n"
    "<name> is a module-level def or async def in the named file. The body is the ONLY "
    "replacement surface — no def line, no signature restatement: the harness keeps the "
    "original def line. The body arrives at the function's indentation. Reply with exactly "
    "one block. Paths are relative to the repository root.\n"
)


def test_the_prompt_is_byte_identical_to_the_committed_shape() -> None:
    """The same inputs give the same bytes, asserted against a literal string — the
    renderer is a pure function of `(task, sources)`, so a drift of a single byte in
    the assembled prompt fails here.
    """
    assert render_whole_function_prompt(_task(), _sources()) == EXPECTED_PROMPT


def test_the_prompt_contains_the_grammar_markers_verbatim() -> None:
    """The pinned markers appear in the prompt exactly as the format spells them — the
    renderer poses the grammar from the module's own constants, never a paraphrase.
    """
    prompt = render_whole_function_prompt(_task(), _sources())
    assert EDIT_MARKER in prompt
    assert FUNCTION_MARKER in prompt
    assert REPLACE_OPEN in prompt
    assert REPLACE_CLOSE in prompt


def test_files_are_rendered_in_sorted_path_order_not_mapping_order() -> None:
    """`mult.py` is inserted first above; the prompt must still lead with `calc.py`.
    Iterating the mapping as it arrived would make the prompt depend on how the caller
    built its dict — the byte-instability across processes the rendering rule forbids.
    """
    prompt = render_whole_function_prompt(_task(), _sources())
    assert prompt.index("## calc.py\n") < prompt.index("## mult.py\n")


def test_the_problem_statement_is_posed_verbatim() -> None:
    prompt = render_whole_function_prompt(_task(), _sources())
    assert "# Problem\n\nadd() subtracts instead of adding\n" in prompt


def test_the_prompt_is_byte_identical_across_processes_and_hash_seeds() -> None:
    """The same input must give the same bytes under different `PYTHONHASHSEED` values —
    a set iterated into the prompt would be stable within one process and different
    between two, which is exactly the drift the pre-committed hash rule exists to catch.
    """
    in_process = hashlib.sha256(
        render_whole_function_prompt(_task(), _sources()).encode("utf-8")
    ).hexdigest()
    seeds = [render_in_subprocess(seed) for seed in ("0", "1")]
    assert seeds == [in_process, in_process]


def render_in_subprocess(seed: str) -> str:
    """The renderer's sha256 under one `PYTHONHASHSEED`, in a fresh interpreter."""
    code = (
        "import hashlib\n"
        "from whetstone.bakeoff.whole_function import render_whole_function_prompt\n"
        "from whetstone.verify.task import Environment, Task\n"
        "task = Task(\n"
        "    task_id='whole-function', source='private', repo_url='/does/not/matter',\n"
        "    base_commit='0' * 40,\n"
        "    environment=Environment(python='python3.12', pins=(), import_roots=('.',)),\n"
        "    problem_statement='add() subtracts instead of adding',\n"
        "    fail_to_pass=('tests/test_addition.py::test_adds',), pass_to_pass=(),\n"
        "    test_blobs={'tests/test_addition.py': b'x'}, provenance={},\n"
        ")\n"
        "sources = {'mult.py': 'x = 1\\n', 'calc.py': 'def add(a, b):\\n    return a - b\\n'}\n"
        "prompt = render_whole_function_prompt(task, sources)\n"
        "print(hashlib.sha256(prompt.encode('utf-8')).hexdigest())\n"
    )
    env = {**os.environ, "PYTHONHASHSEED": seed}
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True
    )
    return result.stdout.strip()


def test_a_held_test_path_is_refused_by_name() -> None:
    with pytest.raises(HeldTestInSources) as exc:
        render_whole_function_prompt(_task(), {HELD: "def test_adds():\n    assert False\n"})
    assert HELD in str(exc.value)


def test_a_case_folded_held_path_is_refused_by_name() -> None:
    """Cheat 9's spelling: on a case-insensitive volume `Tests/Test_Addition.py` reaches
    the held file while comparing unequal to it, so the refusal must fold case too.
    """
    with pytest.raises(HeldTestInSources) as exc:
        render_whole_function_prompt(_task(), {"Tests/Test_Addition.py": "x = 1\n"})
    assert "Tests/Test_Addition.py" in str(exc.value)


def test_the_held_refusal_is_structural_a_path_not_an_import_walk() -> None:
    """The refusal fires on the sources map's path alone — no module is imported, no
    file is read, and nothing about which code imports what is consulted.
    """
    with pytest.raises(HeldTestInSources):
        render_whole_function_prompt(_task(), {HELD: "x = 1\n"})


def test_an_empty_source_map_is_refused() -> None:
    with pytest.raises(EmptySources):
        render_whole_function_prompt(_task(), {})


def test_an_escaping_source_path_is_refused() -> None:
    for path in ("/outside.py", "pkg/../../outside.py"):
        with pytest.raises(EscapingSourcePath) as exc:
            render_whole_function_prompt(_task(), {path: "x = 1\n"})
        assert path in str(exc.value)


# --- The parser ------------------------------------------------------------------------------

def one_block(path: str = "calc.py", name: str = "add", body: str = "return a + b") -> str:
    return (
        f"EDIT {path}\n"
        f"FUNCTION {name}\n"
        f"<<<<<<< REPLACE\n"
        f"{body}\n"
        f">>>>>>> END\n"
    )


def refused(text: str) -> str:
    """The named reason a completion is refused — a `Block` here is the test failing."""
    result = parse_edit_block(text)
    assert isinstance(result, NoBlock), f"expected NoBlock, got {result!r}"
    return result.reason


def test_one_block_parses_to_path_name_and_body() -> None:
    """A compliant completion returns the exact `Block`, the body preserved byte-exactly:
    a multi-line body round-trips with its line breaks, nothing stripped and nothing added.
    """
    text = one_block(body="result = a + b\nreturn result")
    assert parse_edit_block(text) == Block(
        path="calc.py", name="add", body="result = a + b\nreturn result"
    )


def test_an_empty_body_is_a_valid_block() -> None:
    """An empty replacement parses. Whether an empty body is usable is the instrument's
    class (`IndentationError` under the wrapped parse), never this parser's judgement.
    """
    text = "EDIT calc.py\nFUNCTION add\n<<<<<<< REPLACE\n>>>>>>> END\n"
    assert parse_edit_block(text) == Block(path="calc.py", name="add", body="")


def test_prose_before_and_after_the_block_is_skipped() -> None:
    """The spec's `MALFORMED` is about the block, so words around a real block do not
    make it unparseable; they are skipped, and never mistaken for structure.
    """
    text = "Here is the fix:\n" + one_block() + "That should do it.\n"
    assert parse_edit_block(text) == Block(path="calc.py", name="add", body="return a + b")


def test_an_indented_nested_def_is_body_content_not_a_restatement() -> None:
    """The def-line rule targets the signature restatement — a `def ` line at the body's
    own indentation, transcribing the original. An indented nested `def` is new code,
    which is exactly what the format asks for; whether the indentation is usable is the
    instrument's class, never this parser's.
    """
    body = "result = a + b\n    def helper():\n        return 1\nreturn result"
    text = one_block(body=body)
    assert parse_edit_block(text) == Block(path="calc.py", name="add", body=body)


def test_a_missing_edit_header_refuses() -> None:
    assert refused("FUNCTION add\n<<<<<<< REPLACE\nreturn a + b\n>>>>>>> END\n") == MISSING_EDIT
    assert refused("I would fix this by changing the sign in add().\n") == MISSING_EDIT
    assert refused("") == MISSING_EDIT


def test_a_missing_function_header_refuses() -> None:
    assert refused("EDIT calc.py\n<<<<<<< REPLACE\nreturn a + b\n>>>>>>> END\n") == (
        MISSING_FUNCTION
    )


def test_a_missing_open_marker_refuses() -> None:
    """The format pins the replacement section as *opened by* `<<<<<<< REPLACE`; a blank
    line or prose between the headers and the marker is not in the format, and tolerating
    it would be the harness repairing the block.
    """
    assert refused("EDIT calc.py\nFUNCTION add\nreturn a + b\n>>>>>>> END\n") == MISSING_MARKER
    assert refused("EDIT calc.py\nFUNCTION add\n\n<<<<<<< REPLACE\nx\n>>>>>>> END\n") == (
        MISSING_MARKER
    )


def test_an_empty_path_refuses() -> None:
    assert refused("EDIT \nFUNCTION add\n<<<<<<< REPLACE\nx\n>>>>>>> END\n") == MISSING_PATH


def test_an_empty_name_refuses() -> None:
    assert refused("EDIT calc.py\nFUNCTION \n<<<<<<< REPLACE\nx\n>>>>>>> END\n") == MISSING_NAME


def test_an_unclosed_fence_refuses() -> None:
    assert refused("EDIT calc.py\nFUNCTION add\n<<<<<<< REPLACE\nreturn a + b\n") == (
        UNCLOSED_FENCE
    )
    assert refused("EDIT calc.py\nFUNCTION add\n<<<<<<< REPLACE\n") == UNCLOSED_FENCE


def test_two_blocks_refuse() -> None:
    """The format is exactly one block per rollout; a second block is `MALFORMED`, never
    two edits let through while the parser looks away.
    """
    text = one_block() + one_block(path="mult.py", name="mul")
    assert refused(text) == MULTIPLE_BLOCKS


def test_a_stray_marker_refuses_the_completion() -> None:
    """A marker with no block around it is a half-written block, never noise to drop
    while the rest proceeds.
    """
    assert refused("<<<<<<< REPLACE\nreturn a + b\n>>>>>>> END\n") == STRAY_MARKER
    assert refused(">>>>>>> END\n") == STRAY_MARKER
    assert refused(one_block() + "<<<<<<< REPLACE\nx\n>>>>>>> END\n") == STRAY_MARKER
    assert refused(one_block() + "FUNCTION mul\n") == STRAY_MARKER


@pytest.mark.parametrize(
    ("def_line", "id"),
    [
        ("def add(a, b):", "plain"),
        ("async def add(a, b):", "async"),
    ],
)
def test_a_def_line_in_the_body_refuses(def_line: str, id: str) -> None:
    """The body is the only replacement surface — a `def ` or `async def ` line at the
    body's own indentation is the signature restatement the format never asks for.
    """
    text = (
        f"EDIT calc.py\nFUNCTION add\n<<<<<<< REPLACE\n{def_line}\n"
        f"    return a + b\n>>>>>>> END\n"
    )
    assert refused(text) == SIGNATURE_RESTATEMENT


def test_crlf_output_parses_as_the_same_language_as_lf() -> None:
    """Line endings are separators of the format, not content — the parsing precedent
    `patch.py` sets with `_bare`. The body comes back joined with `\n`.
    """
    text = "EDIT calc.py\r\nFUNCTION add\r\n<<<<<<< REPLACE\r\nreturn a + b\r\n>>>>>>> END\r\n"
    assert parse_edit_block(text) == Block(path="calc.py", name="add", body="return a + b")


# --- Hygiene (the measurement-side mirror of the reward-path guard) --------------------------

def _type_checking_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    """The line ranges of the module's `if TYPE_CHECKING:` blocks.

    An import inside one is an annotation import — it never executes, so it never makes
    what it names a runtime import of the module. The walk needs to know which imports
    those are, or a `Task` type import would fail the very guard it exists to serve.
    """
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            ranges.append((node.lineno, node.end_lineno or node.lineno))
    return ranges


def _dotted_package(path: Path, src_root: Path) -> str:
    """The package a module lives in, e.g. `whetstone.bakeoff` for
    `bakeoff/whole_function.py`.
    """
    parts = path.relative_to(src_root).with_suffix("").parts
    return ".".join(parts[:-1])


def _resolve_relative(package: str, level: int) -> str:
    """The absolute prefix a `level`-dotted relative import refers to."""
    parts = package.split(".") if package else []
    ascent = level - 1
    return ".".join(parts[: len(parts) - ascent]) if ascent <= len(parts) else ""


def _absolute_module(node: ast.ImportFrom, package: str) -> str:
    """The absolute dotted module an ImportFrom names, relative or not."""
    if node.level == 0:
        return node.module or ""
    prefix = _resolve_relative(package, node.level)
    if node.module is None:
        return prefix
    return f"{prefix}.{node.module}" if prefix else node.module


def _imported_names(tree: ast.Module, package: str) -> list[tuple[str, int, bool]]:
    """Every module name `tree` imports: dotted and absolute, with its line and whether
    the import sits inside an `if TYPE_CHECKING:` block. `ast.walk` so an import nested
    inside a function counts too.
    """
    type_checking = _type_checking_ranges(tree)
    names: list[tuple[str, int, bool]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(
                (alias.name, node.lineno, _inside(node, type_checking))
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            base = _absolute_module(node, package)
            if not base:
                continue
            names.append((base, node.lineno, _inside(node, type_checking)))
            names.extend(
                (f"{base}.{alias.name}", node.lineno, _inside(node, type_checking))
                for alias in node.names
                if alias.name != "*"
            )
    return names


def _inside(node: ast.AST, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= node.lineno <= end for start, end in ranges)


def _is_inference(dotted: str) -> bool:
    return dotted.split(".")[0] in INFERENCE_ROOTS


def _is_reward_path(dotted: str) -> bool:
    return dotted.startswith("whetstone.verify.") or dotted.startswith("whetstone.tasks.")


def test_the_module_imports_no_reward_path_or_inference_code() -> None:
    """The measurement side's hygiene mirror: the renderer and the parser are stdlib-only
    plus the sibling bakeoff modules, and nothing they import may be the reward path or
    the inference stack.

    The reward-path half is about runtime imports only: the `Task` type appears in the
    renderer's signature under `TYPE_CHECKING`, which never executes — importing the
    module must not import anything under `verify/` or `tasks/`. The inference half is
    about the whole module, type-checking imports included.
    """
    tree = ast.parse(WHOLE_FUNCTION.read_bytes(), filename=str(WHOLE_FUNCTION))
    package = _dotted_package(WHOLE_FUNCTION, SRC)
    names = _imported_names(tree, package)
    runtime = [dotted for dotted, _lineno, in_type_checking in names if not in_type_checking]

    inference = [dotted for dotted, _lineno, _in_type_checking in names if _is_inference(dotted)]
    assert not inference, (
        "an inference library is imported by the whole-function module ("
        + ", ".join(sorted(inference))
        + ").\n\nWHY THIS IS A FAILURE: bakeoff is the exempt generation side, so nothing "
        "structural stops this module from dragging the inference stack into the "
        "measurement's import graph — which is why its own import list is pinned. The "
        "renderer and the parser are stdlib-only by discipline; an import of mlx, torch, "
        "transformers or a hosted SDK would make the measurement depend on the stack it "
        "exists to measure"
    )
    reward_path = [dotted for dotted in runtime if _is_reward_path(dotted)]
    assert not reward_path, (
        "a reward-path module is imported at runtime by the whole-function module ("
        + ", ".join(sorted(reward_path))
        + ").\n\nWHY THIS IS A FAILURE: the measurement side poses the question and never "
        "grades it — the verifier is never entered (spec AC2) — and an import under "
        "`verify/` or `tasks/` would tie the prompt's bytes to the reward path it must "
        "stay off"
    )

    # Anti-vacuity: the walk really read the module's imports, and the TYPE_CHECKING skip
    # is what allowed the annotation import — not the walk going blind.
    all_names = {dotted for dotted, _lineno, _in_type_checking in names}
    assert "whetstone.verify.task" in all_names, (
        "the walk does not see the module's TYPE_CHECKING `Task` import — the skip is "
        "unexercised, and the guard is passing on a walk that read nothing"
    )
    assert "whetstone.verify.task" not in runtime, (
        "the TYPE_CHECKING skip failed: the annotation import would count as a runtime "
        "reward-path import"
    )
    assert "whetstone.bakeoff.rendering" in runtime, (
        "the walk does not see the module's real imports — the guard would pass vacuously"
    )
    assert "dataclasses" in runtime, (
        "the walk does not see the module's stdlib imports — the guard would pass vacuously"
    )


def test_the_banned_predicates_are_live() -> None:
    """Anti-vacuity control B: the predicates the main test leans on really fire.

    A predicate that returned False for everything would keep the main test green while
    banning nothing — the reward-path guard's own lesson, restated here.
    """
    for dotted in (
        "mlx",
        "mlx_lm",
        "torch",
        "transformers",
        "openai",
        "anthropic",
        "vllm",
        "ollama",
    ):
        assert _is_inference(dotted) is True, dotted
    assert _is_inference("whetstone.bakeoff.rendering") is False
    assert _is_inference("dataclasses") is False
    assert _is_reward_path("whetstone.verify.strict") is True
    assert _is_reward_path("whetstone.tasks.manifest") is True
    assert _is_reward_path("whetstone.bakeoff.whole_function") is False