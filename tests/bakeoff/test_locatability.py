"""Was the code a refused diff quoted *in the file*? The pure layer of the locatability finding.

`docs/planning/patch-representation/locatability-finding/spec.md` fixes every rule tested here
before the classifier is run over any real transcript. A test that disagrees with the spec is a
defect in the test or the module; a rule that turns out ambiguous is amended in the spec, in its
own commit, before the run — never after it.

No model, no network, no disk beyond `tmp_path`: every file the classifier "reads" in this file is
an in-memory string handed to it by an injected reader.
"""

from __future__ import annotations

from whetstone.bakeoff.locatability import Hunk, walk

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
        "--- a/m.py\n+++ b/m.py\n@@ -1,2 +1,2 @@\n"
        " a = 1\n-b = 2\n+b = 3\nThat fixes it.\n c = 4\n"
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
