"""Was the code a refused diff quoted *in the file*? The pure layer of the locatability finding.

`docs/planning/patch-representation/locatability-finding/spec.md` fixes every rule tested here
before the classifier is run over any real transcript. A test that disagrees with the spec is a
defect in the test or the module; a rule that turns out ambiguous is amended in the spec, in its
own commit, before the run — never after it.

No model, no network, no disk beyond `tmp_path`: every file the classifier "reads" in this file is
an in-memory string handed to it by an injected reader.
"""

from __future__ import annotations

from whetstone.bakeoff.locatability import (
    Hunk,
    HunkClass,
    NotText,
    Reader,
    RolloutClass,
    classify_hunk,
    classify_rollout,
    walk,
)

#: A hunk whose header promises five old lines while the body carries three. git dies at
#: "corrupt patch"; the lenient walk ignores the counts and keeps the body, because what the
#: finding asks is what the model *quoted*, not whether its arithmetic was right.
WRONG_COUNTS = """\
--- a/calc.py
+++ b/calc.py
@@ -1,5 +1,5 @@
 def add(a, b):
-    return a - b
+    return a + b
"""


def test_the_counts_a_hunk_header_declares_are_ignored() -> None:
    assert walk(WRONG_COUNTS) == (
        Hunk(path="calc.py", old_side="def add(a, b):\n    return a - b"),
    )


def test_the_path_is_the_new_side_with_its_prefix_stripped() -> None:
    diff = "--- a/old/name.py\n+++ b/pkg/mod.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    assert walk(diff) == (Hunk(path="pkg/mod.py", old_side="x = 1"),)


def test_a_deleted_file_is_named_by_its_old_side() -> None:
    diff = "--- a/gone.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x = 1\n"
    assert walk(diff) == (Hunk(path="gone.py", old_side="x = 1"),)


def test_an_empty_line_inside_a_hunk_is_an_empty_context_line() -> None:
    """The commonest way a model breaks the prefix grammar: a blank line with no leading space."""
    diff = "--- a/m.py\n+++ b/m.py\n@@ -1,3 +1,3 @@\n a = 1\n\n-b = 2\n+b = 3\n"
    assert walk(diff) == (Hunk(path="m.py", old_side="a = 1\n\nb = 2"),)


def test_trailing_empty_lines_are_not_part_of_the_hunk() -> None:
    """Blank lines that end a hunk are not quoted code: gluing them on would turn a locatable
    old side into an invented one over nothing the model claimed about the file."""
    diff = "--- a/m.py\n+++ b/m.py\n@@ -1 +1 @@\n-a = 1\n+a = 2\n\n\nThat fixes it.\n"
    assert walk(diff) == (Hunk(path="m.py", old_side="a = 1"),)
    assert walk("--- a/m.py\n+++ b/m.py\n@@ -1 +1 @@\n-a = 1\n\n") == (
        Hunk(path="m.py", old_side="a = 1"),
    )


def test_a_no_newline_marker_is_skipped() -> None:
    diff = "--- a/m.py\n+++ b/m.py\n@@ -1 +1 @@\n-a = 1\n\\ No newline at end of file\n+a = 2\n"
    assert walk(diff) == (Hunk(path="m.py", old_side="a = 1"),)


def test_any_other_bare_line_ends_the_hunk() -> None:
    """Trailing prose must not be absorbed into the old side."""
    diff = (
        "--- a/m.py\n+++ b/m.py\n@@ -1,2 +1,2 @@\n a = 1\n-b = 2\n+b = 3\nThat fixes it.\n c = 4\n"
    )
    assert walk(diff) == (Hunk(path="m.py", old_side="a = 1\nb = 2"),)


def test_added_lines_are_not_part_of_the_old_side() -> None:
    diff = "--- a/m.py\n+++ b/m.py\n@@ -1,2 +1,3 @@\n a = 1\n+new = 0\n b = 2\n"
    assert walk(diff) == (Hunk(path="m.py", old_side="a = 1\nb = 2"),)


def test_several_hunks_and_files_are_walked_in_order() -> None:
    diff = (
        "--- a/one.py\n+++ b/one.py\n"
        "@@ -1 +1 @@\n-a = 1\n+a = 2\n"
        "@@ -9 +9 @@\n-z = 1\n+z = 2\n"
        "diff --git a/two.py b/two.py\n"
        "--- a/two.py\n+++ b/two.py\n"
        "@@ -1 +1 @@\n-q = 1\n+q = 2\n"
    )
    assert walk(diff) == (
        Hunk(path="one.py", old_side="a = 1"),
        Hunk(path="one.py", old_side="z = 1"),
        Hunk(path="two.py", old_side="q = 1"),
    )


def test_a_pure_insertion_has_an_empty_old_side() -> None:
    diff = "--- a/m.py\n+++ b/m.py\n@@ -0,0 +1 @@\n+a = 1\n"
    assert walk(diff) == (Hunk(path="m.py", old_side=""),)


def test_text_with_no_hunk_walks_to_nothing() -> None:
    assert walk("--- a/m.py\n+++ b/m.py\n") == ()


# --- Phase 2: per-hunk and per-rollout classes -----------------------------------------------

#: The file every class test reads, unless it says otherwise. `data = 1` is there so a quoted
#: `a = 1` cannot be found inside it: a match is whole lines, never a substring.
CALC = "def add(a, b):\n    return a - b\n\n\ndata = 1\nrepeat\nrepeat\nrepeat\n"


def reader(files: dict[str, str]) -> Reader:
    """An in-memory reader: the pure layer never touches disk."""
    return files.get


def one_hunk(path: str, old_side: str) -> str:
    """A minimal diff whose single hunk quotes `old_side` from `path`."""
    body = "".join(f"-{line}\n" for line in old_side.split("\n")) if old_side else ""
    return f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n{body}+changed\n"


def test_a_quote_found_once_is_locatable() -> None:
    hunk = Hunk(path="calc.py", old_side="def add(a, b):\n    return a - b")
    assert classify_hunk(hunk, reader({"calc.py": CALC})) is HunkClass.LOCATABLE


def test_a_quote_found_nowhere_is_invented() -> None:
    hunk = Hunk(path="calc.py", old_side="def multiply(a, b):")
    assert classify_hunk(hunk, reader({"calc.py": CALC})) is HunkClass.INVENTED


def test_a_quoted_line_is_never_found_inside_a_longer_line() -> None:
    hunk = Hunk(path="calc.py", old_side="a = 1")
    assert classify_hunk(hunk, reader({"calc.py": CALC})) is HunkClass.INVENTED


def test_a_quote_found_more_than_once_is_ambiguous() -> None:
    hunk = Hunk(path="calc.py", old_side="repeat")
    assert classify_hunk(hunk, reader({"calc.py": CALC})) is HunkClass.AMBIGUOUS


def test_overlapping_repeats_count_as_more_than_once() -> None:
    """`repeat\\nrepeat` starts at two lines of a three-line run; `str.count` would see one."""
    hunk = Hunk(path="calc.py", old_side="repeat\nrepeat")
    assert classify_hunk(hunk, reader({"calc.py": CALC})) is HunkClass.AMBIGUOUS


def test_a_missing_file_is_no_file() -> None:
    hunk = Hunk(path="nowhere.py", old_side="x")
    assert classify_hunk(hunk, reader({"calc.py": CALC})) is HunkClass.NO_FILE


def test_an_escaping_path_is_no_file_and_is_never_read() -> None:
    asked: list[str] = []

    def spy(path: str) -> str | None:
        asked.append(path)
        return CALC

    for path in ("/etc/passwd", "../outside.py", "pkg/../../outside.py"):
        assert classify_hunk(Hunk(path=path, old_side="x"), spy) is HunkClass.NO_FILE
    assert asked == [], f"an escaping path reached the reader: {asked}"


def test_an_insertion_quotes_nothing_and_is_empty() -> None:
    assert classify_hunk(Hunk(path="calc.py", old_side=""), reader({})) is HunkClass.EMPTY


def test_the_worst_hunk_decides_the_rollout() -> None:
    diff = one_hunk("calc.py", "def add(a, b):") + one_hunk("calc.py", "def multiply(a, b):")
    result = classify_rollout(diff, reader({"calc.py": CALC}))
    assert result.klass is RolloutClass.INVENTED
    assert result.hunks == (HunkClass.LOCATABLE, HunkClass.INVENTED)


def test_no_file_outranks_invented() -> None:
    diff = one_hunk("calc.py", "def multiply(a, b):") + one_hunk("gone.py", "x")
    assert classify_rollout(diff, reader({"calc.py": CALC})).klass is RolloutClass.NO_FILE


def test_an_insertion_beside_a_located_hunk_is_neutral() -> None:
    diff = one_hunk("calc.py", "def add(a, b):") + one_hunk("calc.py", "")
    assert classify_rollout(diff, reader({"calc.py": CALC})).klass is RolloutClass.LOCATABLE


def test_insertions_alone_are_unreadable() -> None:
    assert classify_rollout(one_hunk("calc.py", ""), reader({})).klass is RolloutClass.UNREADABLE


def test_no_diff_is_unreadable() -> None:
    assert classify_rollout(None, reader({})).klass is RolloutClass.UNREADABLE


def test_a_file_that_is_not_text_leaves_the_rollout_unclassified() -> None:
    def undecodable(path: str) -> str | None:
        raise NotText(path)

    result = classify_rollout(one_hunk("calc.py", "def add(a, b):"), undecodable)
    assert result.klass is RolloutClass.UNCLASSIFIED


def test_indentation_drift_is_tagged_and_never_forgiven() -> None:
    """A quote that is only wrong in its whitespace is `DRIFT`, and still `INVENTED`."""
    diff = one_hunk("calc.py", "def add(a, b):\n  return a - b")
    result = classify_rollout(diff, reader({"calc.py": CALC}))
    assert (result.klass, result.drift) == (RolloutClass.INVENTED, True)


def test_genuinely_absent_text_is_not_drift() -> None:
    diff = one_hunk("calc.py", "def multiply(a, b):")
    result = classify_rollout(diff, reader({"calc.py": CALC}))
    assert (result.klass, result.drift) == (RolloutClass.INVENTED, False)


def test_drift_needs_every_invented_hunk_to_be_drift() -> None:
    diff = one_hunk("calc.py", "  def add(a, b):") + one_hunk("calc.py", "def multiply(a, b):")
    assert classify_rollout(diff, reader({"calc.py": CALC})).drift is False


def test_drift_is_never_set_on_a_rollout_that_is_not_invented() -> None:
    diff = one_hunk("calc.py", "def add(a, b):")
    assert classify_rollout(diff, reader({"calc.py": CALC})).drift is False
