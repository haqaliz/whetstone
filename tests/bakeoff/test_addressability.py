"""Could the pinned base *address* a numbered listing? The pure layer of the measurement's decision.

`docs/planning/edit-contract-finding/measurement-run/spec.md` fixes every rule tested here
before the instrument is run over any real transcript: the classes worst-first
(`UNCLASSIFIED` > `MALFORMED` > `NO_FILE` > `OUT_OF_RANGE` > `ADDRESSABLE`), the
strict-majority inequality, and the two sub-counts that are reported beside the partition
and never move a class. A test that disagrees with the spec is a defect in the test or the
module; a rule that turns out ambiguous is amended in the spec, in its own commit, before
the run — never after it.

No model, no network, no disk beyond `tmp_path`: every file the classifier "reads" in this
file is an in-memory string handed to it by an injected reader, and the only thing the
classifier needs from a file is its text — the same `Reader` seam `locatability` uses.
"""

from __future__ import annotations

import pytest

from whetstone.bakeoff.addressability import (
    BlockClass,
    Decision,
    RolloutClass,
    classify_rollout,
    decide,
)
from whetstone.bakeoff.locatability import NotText, Reader

#: A two-line file. Line 2 is indented, so a module-level replacement spliced before it
#: makes the file unparseable — the sub-count (a) fixture.
INDENTED = "def f():\n    return 1\n"

#: A file that does not parse at all — the "already broken at base_commit" sub-count case.
BROKEN = "def f(:\n    return 1\n"

#: A three-line file, for range arithmetic that needs somewhere to be beyond.
THREE = "a = 1\nb = 2\nc = 3\n"


def reader(files: dict[str, str]) -> Reader:
    """An in-memory reader: the pure layer never touches disk."""
    return files.get


def block(path: str, start: int, end: int, replacement: str = "x = 1") -> str:
    """One well-formed EDIT block in the measurement format, with `replacement` as its text."""
    return (
        f"EDIT {path}:{start}-{end}\n"
        "<<<<<<< REPLACE\n"
        f"{replacement}\n"
        ">>>>>>> END\n"
    )


# --- Every class fires on a fixture ---------------------------------------------------------


def test_real_lines_with_a_parsing_replacement_are_addressable() -> None:
    completion = block("calc.py", 1, 2, "def add(a, b):\n    return a + b")
    result = classify_rollout(completion, reader({"calc.py": INDENTED}))
    assert result.klass is RolloutClass.ADDRESSABLE
    assert result.blocks == (BlockClass.ADDRESSABLE,)
    assert result.detail == ""


def test_end_beyond_the_files_last_line_is_out_of_range() -> None:
    result = classify_rollout(block("calc.py", 1, 9), reader({"calc.py": THREE}))
    assert result.klass is RolloutClass.OUT_OF_RANGE
    assert result.blocks == (BlockClass.OUT_OF_RANGE,)
    assert "end 9 exceeds the file's 3 lines" in result.detail


def test_start_greater_than_end_is_out_of_range() -> None:
    result = classify_rollout(block("calc.py", 5, 2), reader({"calc.py": THREE}))
    assert result.klass is RolloutClass.OUT_OF_RANGE
    assert "start 5 > end 2" in result.detail


def test_start_below_one_is_out_of_range() -> None:
    result = classify_rollout(block("calc.py", 0, 1), reader({"calc.py": THREE}))
    assert result.klass is RolloutClass.OUT_OF_RANGE
    assert "start 0 < 1" in result.detail


def test_overlapping_ranges_on_one_file_are_out_of_range() -> None:
    completion = block("calc.py", 1, 2) + block("calc.py", 2, 2)
    result = classify_rollout(completion, reader({"calc.py": THREE}))
    assert result.klass is RolloutClass.OUT_OF_RANGE
    assert result.blocks == (BlockClass.ADDRESSABLE, BlockClass.OUT_OF_RANGE)
    assert "overlaps an earlier block" in result.detail


def test_an_unknown_path_is_no_file() -> None:
    result = classify_rollout(block("nowhere.py", 1, 1), reader({"calc.py": THREE}))
    assert result.klass is RolloutClass.NO_FILE
    assert result.blocks == (BlockClass.NO_FILE,)


def test_an_escaping_path_is_no_file_and_is_never_read() -> None:
    asked: list[str] = []

    def spy(path: str) -> str | None:
        asked.append(path)
        return THREE

    for path in ("/etc/passwd", "../outside.py", "pkg/../../outside.py"):
        result = classify_rollout(block(path, 1, 1), spy)
        assert result.klass is RolloutClass.NO_FILE
    assert asked == [], f"an escaping path reached the reader: {asked}"


def test_a_garbage_completion_is_malformed() -> None:
    result = classify_rollout("hello there", reader({"calc.py": THREE}))
    assert result.klass is RolloutClass.MALFORMED
    assert result.detail == "no blocks"
    assert result.blocks == ()


def test_a_block_with_a_missing_marker_is_malformed() -> None:
    result = classify_rollout("EDIT calc.py:1-2\nprose instead of the marker\n", reader({}))
    assert result.klass is RolloutClass.MALFORMED
    assert result.detail == "missing marker"


def test_a_file_that_is_not_text_leaves_the_rollout_unclassified() -> None:
    def undecodable(path: str) -> str | None:
        raise NotText(path)

    result = classify_rollout(block("calc.py", 1, 2), undecodable)
    assert result.klass is RolloutClass.UNCLASSIFIED
    assert "not UTF-8" in result.detail


# --- Worst-first severity --------------------------------------------------------------------


def test_the_worst_block_decides_the_rollout() -> None:
    completion = block("calc.py", 1, 1) + block("calc.py", 9, 9)
    result = classify_rollout(completion, reader({"calc.py": THREE}))
    assert result.klass is RolloutClass.OUT_OF_RANGE
    assert result.blocks == (BlockClass.ADDRESSABLE, BlockClass.OUT_OF_RANGE)


def test_no_file_outranks_out_of_range() -> None:
    completion = block("gone.py", 1, 1) + block("calc.py", 9, 9)
    result = classify_rollout(completion, reader({"calc.py": THREE}))
    assert result.klass is RolloutClass.NO_FILE
    assert result.blocks == (BlockClass.NO_FILE, BlockClass.OUT_OF_RANGE)


# --- The ast.parse gate ----------------------------------------------------------------------


def test_a_replacement_that_does_not_parse_is_not_addressable() -> None:
    result = classify_rollout(block("calc.py", 1, 1, "def f(:"), reader({"calc.py": THREE}))
    assert result.klass is not RolloutClass.ADDRESSABLE
    assert result.klass is RolloutClass.OUT_OF_RANGE
    assert "does not parse as Python" in result.detail


def test_an_empty_replacement_is_addressable() -> None:
    """The gate is `ast.parse` alone, and empty text parses: a deletion is a valid edit."""
    result = classify_rollout(block("calc.py", 1, 1, ""), reader({"calc.py": THREE}))
    assert result.klass is RolloutClass.ADDRESSABLE


# --- Sub-count (a): syntax-fragile in context, never moving a class --------------------------


def test_a_context_fragile_replacement_is_counted_but_never_moves_the_class() -> None:
    """`x = 1` parses alone, but spliced before an indented line the file stops parsing."""
    result = classify_rollout(block("calc.py", 1, 1, "x = 1"), reader({"calc.py": INDENTED}))
    assert result.syntax_fragile == (True,)
    assert result.klass is RolloutClass.ADDRESSABLE, (
        "WHY THIS IS A FAILURE: a sub-count moved a class. The sub-count is reported "
        "beside the partition by design, never folded into it"
    )


def test_a_replacement_that_keeps_the_file_parsing_is_not_counted() -> None:
    completion = block("calc.py", 1, 2, "def f():\n    pass")
    result = classify_rollout(completion, reader({"calc.py": INDENTED}))
    assert result.syntax_fragile == (False,)


def test_a_base_file_that_already_does_not_parse_is_not_counted() -> None:
    """A file broken at `base_commit` cannot be blamed on the replacement — not counted."""
    result = classify_rollout(block("calc.py", 1, 1, "x = 1"), reader({"calc.py": BROKEN}))
    assert result.syntax_fragile == (False,)
    assert result.klass is RolloutClass.ADDRESSABLE


def test_an_out_of_range_block_is_not_spliced_for_the_sub_count() -> None:
    result = classify_rollout(block("calc.py", 1, 9, "x = 1"), reader({"calc.py": THREE}))
    assert result.syntax_fragile == (False,)


# --- Sub-count (b): outside the oracle listing, never moving a class -------------------------


def test_a_block_outside_the_oracle_listing_is_counted_and_never_moves_the_class() -> None:
    """A real file the listing did not show (a held test) is counted, and still ADDRESSABLE."""
    completion = block("calc.py", 1, 1) + block("tests/test_addition.py", 1, 1)
    files = {"calc.py": THREE, "tests/test_addition.py": "def test_add():\n    pass\n"}
    result = classify_rollout(completion, reader(files), listing=frozenset({"calc.py"}))
    assert result.outside_listing == (False, True)
    assert result.klass is RolloutClass.ADDRESSABLE, (
        "WHY THIS IS A FAILURE: a sub-count moved a class. Classification is by file "
        "existence at base_commit; the listing only feeds the count beside the partition"
    )


def test_a_block_inside_the_listing_is_not_counted() -> None:
    result = classify_rollout(
        block("calc.py", 1, 1), reader({"calc.py": THREE}), listing=frozenset({"calc.py"})
    )
    assert result.outside_listing == (False,)


def test_a_no_file_block_is_still_counted_outside_the_listing() -> None:
    result = classify_rollout(block("gone.py", 1, 1), reader({}), listing=frozenset())
    assert result.outside_listing == (True,)
    assert result.klass is RolloutClass.NO_FILE


# --- The decision ----------------------------------------------------------------------------


ADR, OUT, MAL, NOF, UNC = (
    RolloutClass.ADDRESSABLE,
    RolloutClass.OUT_OF_RANGE,
    RolloutClass.MALFORMED,
    RolloutClass.NO_FILE,
    RolloutClass.UNCLASSIFIED,
)


def test_more_than_half_addressable_is_go() -> None:
    assert decide([ADR, ADR, OUT]) is Decision.GO


def test_exactly_half_is_no_go() -> None:
    assert decide([ADR, MAL]) is Decision.NO_GO


def test_two_of_four_is_no_go_and_three_of_four_is_go() -> None:
    assert decide([ADR, ADR, MAL, NOF]) is Decision.NO_GO
    assert decide([ADR, ADR, ADR, NOF]) is Decision.GO


def test_an_unclassified_rollout_stays_in_the_denominator() -> None:
    """Dropping what could not be asked would turn one addressable of two into one of one."""
    assert decide([ADR, UNC]) is Decision.NO_GO


def test_an_empty_population_is_refused_not_decided() -> None:
    with pytest.raises(ValueError, match="empty"):
        decide([])