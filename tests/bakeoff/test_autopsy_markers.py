"""The markers and the loop rule: what a completion *is* before anyone walks its hunks.

The dig read every stored completion by hand and found each failure shape was detectable by a
pure pattern over the raw text (`dig-transcripts.md` § 2) — before any hunk walking, before any
`git apply`. This file pins those detectors and the loop rule, because both are honesty-bearing:
a marker that no fixture can produce, or that fires on a legal line, quietly corrupts the very
next phase, which renders the primary cause and trusts these markers to say what the raw text
contained.

**Failure one: a detector with no fixture.** `prd.md` R7 — a marker whose detector no fixture
exercises reports nothing forever, and nothing reads as "this never happens" rather than "this
detector stopped working". The bijection below (the `test_attribution.py:299-332` shape) asserts
the fixture set and the marker set cover each other in both directions, so a marker added to the
enum with no fixture fails this file instead of shipping silent.

**Failure two: a detector that fires on a legal line.** A marker is only worth having if it can
refuse: `100644` is a legal index mode and must not be `INDEX_GARBAGE`; a single fenced body must
not be `REPEATED_DIFFS`; a real multi-file patch must not read as a duplicate loop; prose with a
loop token here and there must not be loop-dominated. The near-miss controls below are the
watched-failing half: a credulous detector that flags everything fails every one of them.

The loop rule itself: the 7B base's signature failure was a degenerate repetition loop of the
chat-template tokens, and the dig found the ratio of loop-token lines to total non-blank lines
separates every observed case above `0.2` (`dig-transcripts.md` § 2 shape 1). A dominated loop is
`IM_START_LOOP` — Phase 2's precedence table promotes it only when no well-formed diff follows;
below the threshold the completion is simply not a loop.

All fixtures are tiny synthetic strings with toy names (`adder.py`, `multiplier.py`) — replicas
of the dig's observed shapes, never donor content (`card.md:68-70`).
"""

from __future__ import annotations

import pytest

from whetstone.bakeoff.autopsy import (
    LOOP_DOMINANCE_RATIO,
    FineCause,
    Marker,
    im_start_ratio,
    loop_verdict,
    markers_of,
)

# --------------------------------------------------------------------------------------------
# One fixture per marker — synthetic replicas of the dig's observed shapes
# (`dig-transcripts.md` § 2), toy paths, tiny. Never donor content.
# --------------------------------------------------------------------------------------------

#: Shape 5: a block boundary where the model closes one fence and opens the next on one line.
#: The opening line is ``` plus a space plus ```diff — two concatenated fences.
STACKED_FENCE_TEXT = """``` ```diff
diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1 +1 @@
-    return a - b
+    return a + b
```
"""

#: Shape 7: an index line whose trailing token is junk, not a legal mode. The observed corpus
#: carries `10`, `101112`, `1234567`, `1024567 10` and a ~600-digit counting run; `101112` is
#: the replica here.
INDEX_GARBAGE_TEXT = """diff --git a/adder.py b/adder.py
index 1234567..89abcde 101112
--- a/adder.py
+++ b/adder.py
@@ -1 +1 @@
-    return a - b
+    return a + b
"""

#: Shape 6: a `diff --git` header whose `b` path lost its slash — `b ` followed by a space and
#: a path that does not begin with `/`.
B_PATH_MISSING_SLASH_TEXT = """diff --git a/adder.py b adder.py
--- a/adder.py
+++ b/adder.py
@@ -1 +1 @@
-    return a - b
+    return a + b
"""

#: Shape 9: `<|endoftext|>` appears mid-completion and a fresh chat turn — `Human:` — follows
#: it, as if the sampled conversation rolled over into a new example.
SECOND_TURN_ROLLOVER_TEXT = """```diff
diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1 +1 @@
-    return a - b
+    return a + b
```
<|endoftext|>
Human: What about a different script?
Assistant: For <your_script.py> you would write the same diff.
"""

#: Shape 11: the same diff fenced verbatim twice — a degenerate copy loop at the block level.
REPEATED_DIFFS_TEXT = """```diff
diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1 +1 @@
-    return a - b
+    return a + b
```
```diff
diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1 +1 @@
-    return a - b
+    return a + b
```
"""

#: Shape 12: an added line whose content begins with `=` — the left-hand side vanished.
PHANTOM_ASSIGNMENTS_TEXT = """diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a - b
+        = foo()
+    return a + b
"""

#: Shape 13: a `-`/`+` pair whose two lines are byte-identical, so the hunk changes nothing.
NOOP_HUNKS_TEXT = """diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a - b
"""

#: Shape 1: the 7B collapse — a 511-line `<|im_start|>` repetition loop, the dig's modal shape.
LOOP_PRESENT_TEXT = "<|im_start|>\n" * 511

#: The fixture set: exactly one synthetic text per marker, paired with the marker it alone must
#: carry. The equality assertions below are in both directions — each fixture detected, and
#: nothing detected that is not its own marker.
MARKER_FIXTURES: tuple[tuple[str, frozenset[Marker]], ...] = (
    (STACKED_FENCE_TEXT, frozenset({Marker.STACKED_FENCE})),
    (INDEX_GARBAGE_TEXT, frozenset({Marker.INDEX_GARBAGE})),
    (B_PATH_MISSING_SLASH_TEXT, frozenset({Marker.B_PATH_MISSING_SLASH})),
    (SECOND_TURN_ROLLOVER_TEXT, frozenset({Marker.SECOND_TURN_ROLLOVER})),
    (REPEATED_DIFFS_TEXT, frozenset({Marker.REPEATED_DIFFS})),
    (PHANTOM_ASSIGNMENTS_TEXT, frozenset({Marker.PHANTOM_ASSIGNMENTS})),
    (NOOP_HUNKS_TEXT, frozenset({Marker.NOOP_HUNKS})),
    (LOOP_PRESENT_TEXT, frozenset({Marker.LOOP_PRESENT})),
)

# --------------------------------------------------------------------------------------------
# Near-miss controls — legal lines a credulous detector would flag.
# --------------------------------------------------------------------------------------------

#: The index-garbage fixture with the trailing junk replaced by a legal mode: git writes
#: `index <h1>..<h2> 100644` when the mode changes, and `100644` is not garbage.
LEGAL_INDEX_MODE_TEXT = INDEX_GARBAGE_TEXT.replace("101112", "100644")

#: A single fenced body — a code sample, not a duplicate loop.
SINGLE_FENCED_BODY_TEXT = """```python
def add(a, b):
    return a + b
```
"""

#: A real multi-file patch: two fenced bodies that differ, one file each. Distinct from the
#: degenerate copy loop, whose blocks are byte-identical.
MULTI_FILE_PATCH_TEXT = """```diff
diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1 +1 @@
-    return a - b
+    return a + b
```
```diff
diff --git a/multiplier.py b/multiplier.py
--- a/multiplier.py
+++ b/multiplier.py
@@ -1 +1 @@
-    return a * b
+    return a ** b
```
"""

#: Prose with a single loop token mixed in: 1 loop line in 6, ratio 0.167 — below the 0.2
#: separation the dig observed.
MIXED_LOOP_TEXT = "\n".join(
    [
        "The loop began, and then the model escaped it.",
        "<|im_start|>",
        "The bug is that add subtracts instead of adding.",
        "Fix it by flipping the sign.",
        "This is ordinary prose below the loop threshold.",
        "And this line is the last one.",
    ]
)


# --------------------------------------------------------------------------------------------
# Each marker's fixture, and the marker list's coverage of it (and its of it).
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    MARKER_FIXTURES,
    ids=[next(iter(expected)).name for _, expected in MARKER_FIXTURES],
)
def test_every_marker_fixture_detects_exactly_its_marker(
    text: str, expected: frozenset[Marker]
) -> None:
    """One fixture per marker, asserted in both directions: detected, and nothing else.

    The equality is exact, not a subset check. `markers_of` returning the marker is the
    "each detected" half; `markers_of` returning nothing else is the near-miss half held
    inside the same assertion — a fixture that trips a neighbour's detector fails here,
    which is how the marker list stays a partition of the observed shapes rather than a
    set of overlapping hints.
    """
    assert markers_of(text) == expected, (
        f"markers_of returned {sorted(markers_of(text))}, expected {sorted(expected)}.\n\n"
        "WHY THIS MATTERS: each marker's detector is a pure pattern pinned by exactly one "
        "fixture. A fixture that detects nothing makes its marker a silent member that reports "
        "nothing forever; a fixture that detects more than its marker means two detectors "
        "disagree about what the raw text contains, and the record that carries both reads as "
        "an observation of a shape that was never seen."
    )


def test_the_fixture_set_and_the_marker_set_cover_each_other() -> None:
    """The bijection: every marker has a fixture, and no fixture covers no marker.

    `prd.md` R7's anti-vacuity shape, applied to the marker list (`test_attribution.py:299-332`).
    A marker added to the enum with no fixture fails here — the union of the fixtures' expected
    sets comes up short of `set(Marker)` — and a fixture whose expected set is empty fails too,
    because a detector nobody asked to detect anything may be passing on nothing at all.
    """
    covered = set().union(*(expected for _, expected in MARKER_FIXTURES))

    assert all(expected for _, expected in MARKER_FIXTURES), (
        "at least one marker fixture names no marker it must detect.\n\n"
        "WHY THIS MATTERS: a fixture with an empty expected set proves nothing and fails nothing; "
        "the bijection only has teeth if every fixture demands a non-empty verdict."
    )
    assert covered == set(Marker), (
        f"markers without a fixture: {sorted(set(Marker) - covered)}; "
        f"fixtures naming no marker: {sorted(covered - set(Marker))}.\n\n"
        "WHY THIS MATTERS: a detector with no fixture reports zero forever, and zero reads as "
        "'this never happens' rather than as 'this detector stopped working'. The marker list is "
        "append-only by evidence (`prd.md` D4): a marker must earn its fixture before it earns "
        "its place in the enum."
    )


# --------------------------------------------------------------------------------------------
# Near-miss controls — watched failing against a detector that flags everything.
# --------------------------------------------------------------------------------------------


def test_a_legal_index_mode_is_not_index_garbage() -> None:
    """`index <h1>..<h2> 100644` is git's own output, not garbage.

    The dig's mode allow-list is `{100644, 100755, 120000, 160000}` (`dig-transcripts.md` § 2
    shape 7); every other trailing token on an index line was junk. `100644` must clear the
    detector, or every well-formed mode-change diff in every future run carries a marker for
    what it is not.
    """
    assert markers_of(LEGAL_INDEX_MODE_TEXT) == frozenset(), (
        f"a legal index mode was flagged: {sorted(markers_of(LEGAL_INDEX_MODE_TEXT))}.\n\n"
        "WHY THIS MATTERS: the index-garbage marker exists to name corruption, and a detector "
        "that cannot refuse git's own legal output names everything — including the 3B APPLIED "
        "records git tolerated."
    )


def test_a_single_fenced_body_is_not_repeated_diffs() -> None:
    """One fenced code block is an answer, not a degenerate copy loop.

    `REPEATED_DIFFS` requires two or more fenced bodies with identical bytes; a single body
    cannot be a duplicate of anything, and flagging it would mark the most ordinary shape in
    the corpus.
    """
    assert markers_of(SINGLE_FENCED_BODY_TEXT) == frozenset(), (
        f"a single fenced body was flagged: {sorted(markers_of(SINGLE_FENCED_BODY_TEXT))}.\n\n"
        "WHY THIS MATTERS: the repeated-diffs shape is a copy loop at the block level — the dig "
        "counted two to fifteen byte-identical blocks. A detector without the duplicate check "
        "flags every fenced answer, and the marker stops separating anything."
    )


def test_a_multi_file_patch_is_not_a_duplicate_loop() -> None:
    """Two different fenced diffs are a multi-file patch, not a repetition.

    The distinction the dig drew is byte-identity: a real multi-file patch's bodies differ,
    while the degenerate loop fences the same block two to fifteen times. Distinct bodies must
    not trip the duplicate detector — a patch touching two files is the healthy shape, and
    this is the control that says the detector hashes content rather than counting fences.
    """
    assert markers_of(MULTI_FILE_PATCH_TEXT) == frozenset(), (
        f"a multi-file patch was flagged as a duplicate loop: "
        f"{sorted(markers_of(MULTI_FILE_PATCH_TEXT))}.\n\n"
        "WHY THIS MATTERS: the repeated-diffs shape is byte-identical blocks (`dig-transcripts.md` "
        "§ 2 shape 11). Without the byte-identity check the marker cannot tell a degenerate copy "
        "loop from a patch that touches several files — the exact confusion the dig separated."
    )


def test_a_loop_mixed_with_prose_below_the_threshold_is_not_loop_dominated() -> None:
    """1 loop line in 6 (ratio 0.167) is prose with a token, not the 7B collapse.

    The dig's observed separation is above `0.2` (`dig-transcripts.md` § 2 shape 1); below it the
    completion is not loop-dominated, and the `LOOP_PRESENT` marker must stay off — Phase 2's
    precedence table demotes a loop to a marker exactly when it does not dominate the record.
    """
    assert im_start_ratio(MIXED_LOOP_TEXT) <= LOOP_DOMINANCE_RATIO, (
        f"ratio {im_start_ratio(MIXED_LOOP_TEXT)} exceeds the "
        f"{LOOP_DOMINANCE_RATIO} separation.\n\n"
        "WHY THIS MATTERS: the dominance rule is the dig's measured separation, not a guess. If "
        "prose with a token reads as loop-dominated, the classifier calls ordinary answers the "
        "7B collapse, and Phase 2's primary-cause table inherits the misreading."
    )
    assert Marker.LOOP_PRESENT not in markers_of(MIXED_LOOP_TEXT), (
        "a below-threshold loop still carries the LOOP_PRESENT marker.\n\n"
        "WHY THIS MATTERS: the marker is the detector's output, and the detector is the ratio — "
        "a marker that fires below the threshold means the marker and the rule disagree about "
        "what a loop is."
    )


# --------------------------------------------------------------------------------------------
# The loop rule and determinism.
# --------------------------------------------------------------------------------------------


def test_a_dominant_loop_is_im_start_loop_with_its_ratio() -> None:
    """A 511-line `<|im_start|>` loop is `IM_START_LOOP`, with the ratio that decided it.

    The dig's modal shape — 511 lines of the chat template, ratio ~1.0 — is the one record the
    rule must name without hesitation: the dig's own counts made `im-start-loop` the correction
    to the extractor's "prose" misreading (`dig-transcripts.md` § 1, finding 1). The verdict
    carries the ratio so Phase 2's precedence table can render the detail verbatim.
    """
    cause, ratio = loop_verdict(LOOP_PRESENT_TEXT)
    assert cause is FineCause.IM_START_LOOP, (
        f"a 511-line loop was not named IM_START_LOOP; verdict cause: {cause!r}.\n\n"
        "WHY THIS MATTERS: the loop is the 7B base's signature failure, and the classifier's "
        "whole job here is to name it. A loop this dominant that escapes the cause would be "
        "classified by Phase 2 as whatever the precedence table's fallback says."
    )
    assert ratio == im_start_ratio(LOOP_PRESENT_TEXT), (
        f"the verdict ratio {ratio} disagrees with im_start_ratio "
        f"{im_start_ratio(LOOP_PRESENT_TEXT)}.\n\n"
        "WHY THIS MATTERS: the ratio in the verdict must be the measured ratio, or the detail "
        "rendered from it is not a measurement."
    )
    assert ratio > LOOP_DOMINANCE_RATIO

    cause, ratio = loop_verdict(MIXED_LOOP_TEXT)
    assert cause is None, (
        f"a below-threshold loop was named a cause: {cause!r}.\n\n"
        "WHY THIS MATTERS: 'not loop-dominated' is not a cause — Phase 2 must fall through to "
        "the rest of the precedence table, and a verdict that claims a cause for it would "
        "preempt that."
    )
    assert ratio <= LOOP_DOMINANCE_RATIO


def test_classifying_a_fixture_twice_yields_identical_markers() -> None:
    """Determinism (spec AC1): the same fixture classified twice gives the same markers.

    The autopsy's documents are compared across runs, so a classifier that read the same text
    differently on the second pass would make a deterministic analysis produce non-deterministic
    output. The verdict must be stable too — the loop rule's cause and ratio are what Phase 2
    renders into the record.
    """
    for text, _ in MARKER_FIXTURES:
        assert markers_of(text) == markers_of(text), (
            "classifying the same fixture twice yielded different marker sets.\n\n"
            "WHY THIS MATTERS: determinism is an acceptance criterion (spec AC1); a detector "
            "whose output depends on iteration order or set hashing would fail the slice's "
            "byte-identical document promise."
        )
        assert loop_verdict(text) == loop_verdict(text), (
            "the loop verdict was not stable across two classifications of the same fixture.\n\n"
            "WHY THIS MATTERS: the verdict feeds Phase 2's precedence table, and an unstable "
            "rule would assign records different causes depending on when they were read."
        )
