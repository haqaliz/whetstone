"""The numbered-listing renderer and the EDIT-block parser — the measurement format.

`docs/planning/edit-contract-finding/measurement-run/spec.md` pins the format ("Format")
and acceptance criteria 1-2 before any rollout ran, and every rule tested here is that
rule: the listing is 1-based, complete, and byte-deterministic; a held test path is refused
by name in every spelling; and the parser never repairs — a block with any defect refuses
the whole completion, and no block is ever dropped while others proceed.

A test that disagrees with the spec is a defect in the test or the module; a rule that
turns out ambiguous is amended in the spec, in its own commit, before the run — never
after it.

No model, no network, no disk: the renderer takes its sources as a mapping of contents
already read at `base_commit`, and the parser takes text. The determinism test runs the
renderer in two subprocesses under different `PYTHONHASHSEED` values, which is the only
honest way to ask "byte-identical across processes".
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

import pytest

from whetstone.bakeoff.line_range import (
    MISSING_MARKER,
    MISSING_PATH,
    MISSING_RANGE,
    NO_BLOCKS,
    STRAY_MARKER,
    UNCLOSED_REPLACEMENT,
    UNPARSABLE_RANGE,
    EditBlock,
    EmptySources,
    EscapingSourcePath,
    HeldTestInSources,
    MalformedCompletion,
    parse_edit_blocks,
    render_line_range_prompt,
)
from whetstone.verify.task import Environment, Task

#: The operator-held test path, spelled the way a real manifest spells it. The point of the
#: held-test tests is that this exact string — and only its casing — names the answer key.
HELD = "tests/test_addition.py"


def _task() -> Task:
    """A `Task` whose `test_blobs` holds `HELD`. Built, not mocked.
    `test_blobs` is the one field the renderer reads for refusal, so the tests assert
    against the same string a real manifest would hold.
    """
    return Task(
        task_id="line-range",
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
    "calc.py\n"
    "1: def add(a, b):\n"
    "2:     return a - b\n"
    "\n"
    "mult.py\n"
    "1: x = 1\n"
    "\n"
    "# Response format\n"
    "\n"
    "Address a line range and write the replacement text.\n"
    "\n"
    "One or more blocks:\n"
    "\n"
    "EDIT <repository-relative path>:<start>-<end>\n"
    "<<<<<<< REPLACE\n"
    "replacement text\n"
    ">>>>>>> END\n"
    "\n"
    "Blocks may sit inside one fenced block. Paths are relative to the repository root.\n"
)


def test_the_prompt_is_byte_identical_to_the_committed_shape() -> None:
    assert render_line_range_prompt(_task(), _sources()) == EXPECTED_PROMPT


def test_the_listing_numbers_every_line_one_based() -> None:
    prompt = render_line_range_prompt(_task(), _sources())
    assert "calc.py\n1: def add(a, b):\n2:     return a - b\n" in prompt
    assert "mult.py\n1: x = 1\n" in prompt


def test_files_are_rendered_in_sorted_path_order_not_mapping_order() -> None:
    """`mult.py` is inserted first above; the listing must still lead with `calc.py`.
    Iterating the mapping as it arrived would make the prompt depend on how the caller
    built its dict — the byte-instability across processes the rendering rule forbids.
    """
    prompt = render_line_range_prompt(_task(), _sources())
    assert prompt.index("calc.py\n") < prompt.index("mult.py\n")


def test_interior_empty_lines_are_numbered_and_only_the_trailing_phantom_is_dropped() -> None:
    prompt = render_line_range_prompt(_task(), {"calc.py": "a\n\nb\n\n"})
    assert "calc.py\n1: a\n2: \n3: b\n4: \n" in prompt


def test_an_empty_file_renders_no_numbered_lines() -> None:
    prompt = render_line_range_prompt(_task(), {"empty.py": ""})
    assert "empty.py\n\n# Response format" in prompt


def test_the_prompt_is_byte_identical_across_processes_and_hash_seeds() -> None:
    """The same input must give the same bytes under different `PYTHONHASHSEED` values —
    a set iterated into the prompt would be stable within one process and different
    between two, which is exactly the drift the pre-committed hash rule exists to catch.
    """
    in_process = hashlib.sha256(
        render_line_range_prompt(_task(), _sources()).encode("utf-8")
    ).hexdigest()
    seeds = [render_in_subprocess(seed) for seed in ("0", "1")]
    assert seeds == [in_process, in_process]


def render_in_subprocess(seed: str) -> str:
    """The renderer's sha256 under one `PYTHONHASHSEED`, in a fresh interpreter."""
    code = (
        "import hashlib\n"
        "from whetstone.bakeoff.line_range import render_line_range_prompt\n"
        "from whetstone.verify.task import Environment, Task\n"
        "task = Task(\n"
        "    task_id='line-range', source='private', repo_url='/does/not/matter',\n"
        "    base_commit='0' * 40,\n"
        "    environment=Environment(python='python3.12', pins=(), import_roots=('.',)),\n"
        "    problem_statement='add() subtracts instead of adding',\n"
        "    fail_to_pass=('tests/test_addition.py::test_adds',), pass_to_pass=(),\n"
        "    test_blobs={'tests/test_addition.py': b'x'}, provenance={},\n"
        ")\n"
        "sources = {'mult.py': 'x = 1\\n', 'calc.py': 'def add(a, b):\\n    return a - b\\n'}\n"
        "prompt = render_line_range_prompt(task, sources)\n"
        "print(hashlib.sha256(prompt.encode('utf-8')).hexdigest())\n"
    )
    env = {**os.environ, "PYTHONHASHSEED": seed}
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True
    )
    return result.stdout.strip()


def test_a_held_test_path_is_refused_by_name() -> None:
    with pytest.raises(HeldTestInSources) as exc:
        render_line_range_prompt(_task(), {HELD: "def test_adds():\n    assert False\n"})
    assert HELD in str(exc.value)


def test_a_case_folded_held_path_is_refused_by_name() -> None:
    """Cheat 9's spelling: on a case-insensitive volume `Tests/Test_Addition.py` reaches
    the held file while comparing unequal to it, so the refusal must fold case too.
    """
    with pytest.raises(HeldTestInSources) as exc:
        render_line_range_prompt(_task(), {"Tests/Test_Addition.py": "x = 1\n"})
    assert "Tests/Test_Addition.py" in str(exc.value)


def test_the_held_refusal_is_structural_a_path_not_an_import_walk() -> None:
    """The refusal fires on the sources map's path alone — no module is imported, no
    file is read, and nothing about which code imports what is consulted.
    """
    with pytest.raises(HeldTestInSources):
        render_line_range_prompt(_task(), {HELD: "x = 1\n"})


def test_an_empty_source_map_is_refused() -> None:
    with pytest.raises(EmptySources):
        render_line_range_prompt(_task(), {})


def test_an_escaping_source_path_is_refused() -> None:
    for path in ("/outside.py", "pkg/../../outside.py"):
        with pytest.raises(EscapingSourcePath) as exc:
            render_line_range_prompt(_task(), {path: "x = 1\n"})
        assert path in str(exc.value)


# --- The parser ------------------------------------------------------------------------------

def one_block(path: str = "calc.py", start: int = 1, end: int = 2, body: str = "x = 1") -> str:
    return (
        f"EDIT {path}:{start}-{end}\n"
        f"<<<<<<< REPLACE\n"
        f"{body}\n"
        f">>>>>>> END\n"
    )


def refused(text: str) -> str:
    with pytest.raises(MalformedCompletion) as exc:
        parse_edit_blocks(text)
    return exc.value.reason


def test_one_block_parses_to_path_range_and_replacement() -> None:
    text = one_block(body="def add(a, b):\n    return a + b")
    assert parse_edit_blocks(text) == [
        EditBlock(path="calc.py", start=1, end=2, replacement="def add(a, b):\n    return a + b")
    ]


def test_several_blocks_parse_in_order() -> None:
    text = one_block(path="calc.py", body="a") + one_block(path="mult.py", body="b")
    assert parse_edit_blocks(text) == [
        EditBlock(path="calc.py", start=1, end=2, replacement="a"),
        EditBlock(path="mult.py", start=1, end=2, replacement="b"),
    ]


def test_blocks_inside_one_fenced_block_parse() -> None:
    text = "```text\n" + one_block() + "```\n"
    assert parse_edit_blocks(text) == [
        EditBlock(path="calc.py", start=1, end=2, replacement="x = 1")
    ]


def test_prose_between_blocks_is_skipped_not_parsed() -> None:
    """The spec's `MALFORMED` is "no block could be parsed", so prose around real blocks
    does not make them unparseable; it is skipped, and never mistaken for a block.
    """
    text = "Here is the fix:\n" + one_block() + "And one more:\n" + one_block(path="b.py")
    assert parse_edit_blocks(text) == [
        EditBlock(path="calc.py", start=1, end=2, replacement="x = 1"),
        EditBlock(path="b.py", start=1, end=2, replacement="x = 1"),
    ]


def test_a_missing_path_refuses_the_completion() -> None:
    assert refused("EDIT :1-3\n<<<<<<< REPLACE\nx\n>>>>>>> END\n") == MISSING_PATH


def test_a_missing_range_refuses_the_completion() -> None:
    assert refused("EDIT calc.py\n<<<<<<< REPLACE\nx\n>>>>>>> END\n") == MISSING_RANGE


def test_a_header_with_no_range_at_all_refuses() -> None:
    assert refused("EDIT calc.py\n") == MISSING_RANGE


@pytest.mark.parametrize(
    ("range_part", "id"),
    [
        ("12-x", "non-numeric-end"),
        ("x-4", "non-numeric-start"),
        ("1-2-3", "two-dashes"),
        (" 1-2", "leading-space"),
        ("1-2 ", "trailing-space"),
    ],
)
def test_an_unparsable_range_refuses(range_part: str, id: str) -> None:
    assert refused(f"EDIT calc.py:{range_part}\n<<<<<<< REPLACE\nx\n>>>>>>> END\n") == (
        UNPARSABLE_RANGE
    )


def test_a_start_greater_than_end_is_syntactically_valid() -> None:
    """`5-2` parses. Whether the range is *usable* is the instrument's judgement — the
    spec's classes put start > end in `OUT_OF_RANGE`, which the parser must never
    pre-empt, or the classifier could never count the class the spec named.
    """
    assert parse_edit_blocks(one_block(start=5, end=2)) == [
        EditBlock(path="calc.py", start=5, end=2, replacement="x = 1")
    ]


def test_an_unclosed_replacement_refuses_the_completion() -> None:
    assert refused("EDIT calc.py:1-2\n<<<<<<< REPLACE\nx = 1\n") == UNCLOSED_REPLACEMENT


def test_a_missing_open_marker_refuses_the_completion() -> None:
    assert refused("EDIT calc.py:1-2\nx = 1\n>>>>>>> END\n") == MISSING_MARKER


def test_a_header_alone_refuses_the_completion() -> None:
    assert refused("EDIT calc.py:1-2\n") == MISSING_MARKER


def test_a_blank_line_between_header_and_marker_refuses() -> None:
    """The format pins the replacement section as *opened by* `<<<<<<< REPLACE`; a blank
    line between the header and the marker is not in the format, and tolerating it would
    be the harness repairing the block.
    """
    assert refused("EDIT calc.py:1-2\n\n<<<<<<< REPLACE\nx\n>>>>>>> END\n") == MISSING_MARKER


def test_a_bad_block_refuses_the_whole_completion() -> None:
    for text in (
        one_block() + "EDIT b.py\n<<<<<<< REPLACE\nx\n>>>>>>> END\n",
        "EDIT b.py\n<<<<<<< REPLACE\nx\n>>>>>>> END\n" + one_block(),
    ):
        assert refused(text) == MISSING_RANGE


def test_a_completion_with_no_blocks_refuses() -> None:
    assert refused("") == NO_BLOCKS
    assert refused("I would fix this by changing the sign in add().\n") == NO_BLOCKS


def test_a_stray_marker_refuses_the_completion() -> None:
    """A replacement section with no header is not a block to skip: the marker is the
    format's own vocabulary, and a marker outside a block is a half-written block, never
    noise to drop while the rest proceeds.
    """
    assert refused(one_block() + "<<<<<<< REPLACE\ny\n>>>>>>> END\n") == STRAY_MARKER
    assert refused(">>>>>>> END\n") == STRAY_MARKER


def test_an_empty_replacement_is_a_valid_block() -> None:
    """The replacement section may be empty — deleting lines is a legal edit. The first
    close marker ends the block; nothing after it is content.
    """
    assert parse_edit_blocks("EDIT calc.py:1-1\n<<<<<<< REPLACE\n>>>>>>> END\n") == [
        EditBlock(path="calc.py", start=1, end=1, replacement="")
    ]


def test_a_header_inside_a_replacement_is_content_not_a_block() -> None:
    assert parse_edit_blocks("EDIT calc.py:1-1\n<<<<<<< REPLACE\nEDIT b.py:9-9\n>>>>>>> END\n") == [
        EditBlock(path="calc.py", start=1, end=1, replacement="EDIT b.py:9-9")
    ]


def test_crlf_output_parses_as_the_same_language_as_lf() -> None:
    """Line endings are separators of the format, not content — the parsing precedent
    `patch.py` sets with `_bare`. The replacement comes back joined with `\n`.
    """
    text = "EDIT calc.py:1-2\r\n<<<<<<< REPLACE\r\nx = 1\r\n>>>>>>> END\r\n"
    assert parse_edit_blocks(text) == [
        EditBlock(path="calc.py", start=1, end=2, replacement="x = 1")
    ]


def test_a_colon_inside_a_path_is_allowed() -> None:
    assert parse_edit_blocks(one_block(path="src/foo:bar.py")) == [
        EditBlock(path="src/foo:bar.py", start=1, end=2, replacement="x = 1")
    ]