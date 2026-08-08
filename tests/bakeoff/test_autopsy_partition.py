"""The hunk walk and the precedence table: one cause per completion, with the reason it stopped.

Phase 1 named what a completion *is*; this file pins Phase 2, which walks the hunks of the diff
`patch.py` actually extracted and records *why the walk stopped* (`plan_20260809.md` § Phase 2).
Every stored completion that failed the bake-off carries its failure in this walk: the first hunk
dying on an unpasted source line, the closing fence arriving before the counts are spent, the
completion simply ending mid-hunk, a later hunk dying after an earlier one completed, or a body
that runs past its declared counts. Each has a different fix, and the dig's hand-read split them
only provisionally (`dig-transcripts.md` § 5 Q1) — this file makes the split a measurement.

**The precedence table is the contract.** One primary cause per record, resolved in a fixed
order (`prd.md` D4): a no-hunk `NoDiff` outranks the loop; a loop outranks an inherited `NoDiff`
but demotes to the `LOOP_PRESENT` marker when a well-formed diff follows it; a first-hunk death
outranks a later-hunk mismatch; a body that extends beyond its declared counts *is* the mismatch.
The pairwise assertions below pin the orderings that would silently change which zero a record
wears if they were reordered.

**The fuzzy margin is mechanical, not judged.** Counts remaining at the stop line is always a
death — `bare-line` when the stop line is unprefixed, `fence-cut` when it is a closing fence,
`end-of-output` when the completion ends with counts remaining (the truncation shape, labelled
*inferred* — `prd.md` D5: the runtime returns a bare `str` with no finish reason). Counts
exhausted with a hunk-content line (`+`/`-`/` `) following is always extends-beyond. The dig
flagged this boundary as genuinely fuzzy at the margin; the rule here is the mechanical one the
plan fixes, and any divergence from the dig's provisional split is a finding, never a tune.

**`NO_DIFF` is inherited, not observed.** The category exists because `patch.py`'s reasons are
the extractor's vocabulary and the classifier must name every record, including ones no stored
run produced. Its fixture below is a faithful replica of the extractor's *documented* shape, not
of observed data — it is labelled `inherited-not-observed` so no reader mistakes it for a
grounded one (`prd.md` § 8 gap 2).

**Identity, not equivalence.** The fine pass walks with `patch.py`'s own functions — imported,
never copied (`prd.md` R1) — and this file asserts the module uses them by identity and that
`patch.py` itself has no diff on this branch. `_hunk_body` is the one extractor private the walk
does not call: its return value exposes only where the body stopped, not *why*, and the whole
point of this phase is the why — so the walk re-runs the body consumption recording the stop
reason, over the same span, against the same counts. The identity test pins the five functions
the walk does call.

All fixtures are tiny synthetic strings with toy paths (`adder.py`, `multiplier.py`) — replicas
of the dig's observed shapes, never donor content (`card.md:68-70`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from whetstone.bakeoff import autopsy as autopsy_module
from whetstone.bakeoff import patch as patch_module
from whetstone.bakeoff.autopsy import (
    DeathKind,
    FineCause,
    Marker,
    classify_completion,
    im_start_ratio,
)

#: The repository root, reached from `tests/bakeoff/`. Used by the `patch.py`-unmodified guard.
ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------------------------
# One fixture per outcome — synthetic replicas of the dig's observed shapes (`dig-transcripts.md`
# § 2 shapes 2, 3, 15), toy paths, tiny. Never donor content. The leading spaces on context
# lines are load-bearing: a pasted source line with no prefix is exactly the death being pinned.
# --------------------------------------------------------------------------------------------

#: Shape 3, bare-line death (dominant in 3B): the hunk declares 3/3 and the body supplies two
#: lines, then the model pastes the source line verbatim — no leading space, no `+`, no `-`.
#: The walk stops at that line with counts remaining; the death line is unprefixed.
BARE_LINE_STUB = """diff --git a/adder.py b/adder.py
index 1234567..89abcde 100644
--- a/adder.py
+++ b/adder.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a - b
+    return a + b
def add(a, b):
"""

#: Shape 3, fence-cut death: the hunk declares 3/3, the body supplies two lines, and the
#: closing ``` arrives before the counts are exhausted. The walk stops at the fence.
FENCE_CUT_STUB = """```diff
diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a - b
+    return a + b
```
"""

#: Shape 3, end-of-output death (every 7B stub ends this way): the hunk declares 3/3, the body
#: supplies two lines, and the completion simply ends with counts remaining. The inferred
#: truncation shape (`prd.md` D5) — the runtime gives no finish reason, so this is shape-only.
END_OF_OUTPUT_STUB = """--- a/adder.py
+++ b/adder.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a - b
+    return a + b
"""

#: Shape 2, later-hunk death (14B): the first hunk completes and a second hunk — a second file —
#: dies at the end of the output. A walk that stopped at the first hunk would call a multi-file
#: failure well-formed; the walk must continue through metadata to the later hunk.
LATER_HUNK_DEATH = """--- a/adder.py
+++ b/adder.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
--- a/multiplier.py
+++ b/multiplier.py
@@ -1,3 +1,3 @@
 def mul(a, b):
-    return a * b
+    return a ** b
"""

#: Shape 2, extends-beyond: the hunk declares 2/2 and the body supplies three lines — the fourth
#: is a `+` line after the counts are spent. The extractor's walk stops at it, so the diff ends
#: one line before the body does; the walk must see the hunk-content line that follows.
EXTENDS_BEYOND = """--- a/adder.py
+++ b/adder.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
+    return a + b
"""

#: Shape 15, header without hunk: a `diff --git` header and an index line, then nothing. This is
#: `extract_patch`'s own third reason — the record that ran out of budget before the first hunk.
HEADER_ONLY = """diff --git a/adder.py b/adder.py
index 1234567..89abcde 100644
"""

#: Shape 15 (well-formed), the control: a plain-unified diff git parses — the dialect behind all
#: of 14B's APPLIED records. This is also the fixture the real-git oracle below runs through
#: `git apply --numstat`.
PLAIN_UNIFIED = """--- a/adder.py
+++ b/adder.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""

#: Shape 1 + well-formed: a short loop precedes a real diff. Six loop-token lines in thirteen
#: (ratio ~0.46) dominate the text, but the diff after the loop is the state that matters —
#: the loop demotes to the `LOOP_PRESENT` marker, never the cause (`prd.md` D4).
LOOP_AND_DIFF = """<|im_start|>
<|im_end|>
system
<|im_start|>
<|im_end|>
system
--- a/adder.py
+++ b/adder.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""

#: Shape 1 + shape 3: a dominant loop followed by a *stub* — the 7B signature, nine such
#: records in arm-a (`dig-transcripts.md` § 2 shape 1). The loop is the failure: the precedence
#: table names it `IM_START_LOOP` even though a diff of sorts follows, because a broken diff
#: does not outrank the loop — only a well-formed one does.
LOOP_AND_STUB = """<|im_start|>
<|im_end|>
system
<|im_start|>
<|im_end|>
system
--- a/adder.py
+++ b/adder.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a - b
+    return a + b
def add(a, b):
"""

#: Shape 1, loop only: the 7B collapse — chat-template tokens filling the output, nothing else.
LOOP_ONLY = "<|im_start|>\n" * 30

#: First-hunk death beats later-hunk mismatch in the same diff: hunk 1 dies on an unprefixed
#: line and a second hunk header sits beyond it, but the walk stops at the death — rule 4
#: outranks rule 5, and the second hunk is never reached (`spec.md` Open questions).
FIRST_DEATH_BEATS_LATER = """--- a/adder.py
+++ b/adder.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a - b
+    return a + b
this line was pasted without a prefix
@@ -1,2 +1,2 @@
 def mul(a, b):
-    return a * b
"""

#: The planted unrecognisable completion: binary-looking control bytes, no loop, no header, no
#: fence. It must be named `UNRECOGNISED_SHAPE`, never folded into the extractor's "the output
#: is prose" reason — bytes are not prose (`prd.md` R2, the anti-vacuity control).
GARBAGE = "\x00\x01\x02\x03\x04\x05\x06\x07\x08" * 16

#: The `NO_DIFF` fixture — **inherited-not-observed**: plain prose in the extractor's documented
#: shape. Zero stored records are genuine prose answers (`dig-transcripts.md` § 2, absences);
#: the cause exists because the classifier must name every record, including future ones.
PROSE = "The bug is that `add` subtracts instead of adding.\n"


# --------------------------------------------------------------------------------------------
# The per-outcome partition, and the fixture-per-cause completeness control (`prd.md` AC1).
# --------------------------------------------------------------------------------------------

#: The death fixtures: one per `DeathKind`, each a distinct observed way for the first hunk to
#: die (`dig-transcripts.md` § 2 shape 3). The death kinds have different fixes — a pasted
#: source line, a fence that arrived too early, and a budget that ran out are three different
#: responses — so the split must be pinned, not blurred.
DEATH_FIXTURES: tuple[tuple[str, DeathKind], ...] = (
    (BARE_LINE_STUB, DeathKind.BARE_LINE),
    (FENCE_CUT_STUB, DeathKind.FENCE_CUT),
    (END_OF_OUTPUT_STUB, DeathKind.END_OF_OUTPUT),
)

#: One fixture per primary cause, the partition's completeness control. Every `FineCause` must
#: be claimed by at least one fixture and every fixture must claim exactly the cause it names —
#: the `test_attribution.py:299-332` bijection shape applied to the cause list. A cause added
#: to the enum with no fixture fails here.
CAUSE_FIXTURES: tuple[tuple[str, FineCause], ...] = (
    (LOOP_ONLY, FineCause.IM_START_LOOP),
    (BARE_LINE_STUB, FineCause.HUNK_DIES_EARLY),
    (EXTENDS_BEYOND, FineCause.HUNK_COUNT_MISMATCH),
    (HEADER_ONLY, FineCause.HEADER_WITHOUT_HUNK),
    (PLAIN_UNIFIED, FineCause.WELL_FORMED),
    (PROSE, FineCause.NO_DIFF),
    (GARBAGE, FineCause.UNRECOGNISED_SHAPE),
)


@pytest.mark.parametrize(
    ("text", "expected"), DEATH_FIXTURES, ids=[kind.value for _, kind in DEATH_FIXTURES]
)
def test_a_first_hunk_dying_is_hunk_dies_early_with_its_death_kind(
    text: str, expected: DeathKind
) -> None:
    """A first-hunk death is `HUNK_DIES_EARLY`, with the death kind as the detail.

    The three deaths have three different fixes — the model pasted a source line, the fence
    arrived before the counts were spent, or the budget ran out mid-hunk — and the detail must
    say which, or the breakdown cannot tell a format problem from a budget problem.
    """
    result = classify_completion(text)

    assert result.cause is FineCause.HUNK_DIES_EARLY, (
        f"a first-hunk death was classified {result.cause!r} (detail {result.detail!r}).\n\n"
        "WHY THIS MATTERS: the walk ended with counts remaining at the stop line, and the "
        "precedence table names that `hunk-dies-early` — the stub shape that dominates the "
        "bake-off's failures. Any other verdict misreads the most common zero in the corpus."
    )
    assert result.detail == expected.value, (
        f"the death detail {result.detail!r} is not the DeathKind value {expected.value!r}.\n\n"
        "WHY THIS MATTERS: bare-line, fence-cut and end-of-output are three different fixes, and "
        "a detail that cannot distinguish them collapses the classification back into the "
        "coarse cause this slice exists to refine."
    )


def test_a_later_hunk_dying_is_hunk_count_mismatch() -> None:
    """A first hunk that completes and a later hunk that dies is the count mismatch.

    The walk must continue through the second file's metadata to the later hunk: a walk that
    stopped at the first completion would call a two-file failure well-formed, and the whole
    14B failure mode would read as a success.
    """
    result = classify_completion(LATER_HUNK_DEATH)

    assert result.cause is FineCause.HUNK_COUNT_MISMATCH, (
        f"a later-hunk death was classified {result.cause!r} (detail {result.detail!r}).\n\n"
        "WHY THIS MATTERS: counts remaining at a stop line is a death by the mechanical rule; "
        "a death on the first hunk is `hunk-dies-early`, and on any later hunk it is the count "
        "mismatch (`spec.md` Open questions). A verdict that names the first hunk's completion "
        "would report the 14B signature as healthy."
    )
    assert "hunk 2" in result.detail and "end-of-output" in result.detail, result.detail


def test_a_body_extending_beyond_declared_counts_is_hunk_count_mismatch() -> None:
    """A body that runs past its declared counts is the mismatch, and the detail names it.

    The declared count is the contract the hunk walked with; a body line beyond it means the
    counts were invented, not counted (`dig-transcripts.md` § 2 shape 2) — the mechanical
    `extends-beyond` violation.
    """
    result = classify_completion(EXTENDS_BEYOND)

    assert result.cause is FineCause.HUNK_COUNT_MISMATCH, (
        f"an extends-beyond body was classified {result.cause!r} (detail {result.detail!r}).\n\n"
        "WHY THIS MATTERS: counts exhausted with a hunk-content line following is the rule's "
        "extends-beyond arm (`prd.md` D4). Folding it into a death would blame a budget cut "
        "for a body that was simply never counted."
    )
    assert "extends" in result.detail, result.detail


def test_a_header_without_a_hunk_is_header_without_hunk() -> None:
    """A `diff --git` header with no hunk is the extractor's own reason, kept verbatim.

    The detail is the reason sentence itself — the inherited vocabulary (`prd.md` § 8 gap 2),
    not a paraphrase — so whoever reads the record sees exactly what `patch.py` said.
    """
    extraction = patch_module.extract_patch(HEADER_ONLY)
    assert isinstance(extraction, patch_module.NoDiff)

    result = classify_completion(HEADER_ONLY)

    assert result.cause is FineCause.HEADER_WITHOUT_HUNK, (
        f"a header without a hunk was classified {result.cause!r}.\n\n"
        "WHY THIS MATTERS: the budget ran out before the first hunk — the extractor's own "
        "third reason, outranking even a dominant loop in the precedence table."
    )
    assert result.detail == extraction.reason, (
        f"the detail {result.detail!r} is not the extractor's reason {extraction.reason!r}.\n\n"
        "WHY THIS MATTERS: the reason is for reading and the bucket is for counting; a detail "
        "rewritten here loses the sentence `patch.py` wrote about the record."
    )


def test_a_plain_unified_well_formed_diff_is_well_formed() -> None:
    """A complete plain-unified diff — the 14B control — is `WELL_FORMED`.

    Every hunk completes and nothing follows the last hunk; this is the shape git parses, the
    shape behind 14B's APPLIED records, and the control that says the classifier can say yes.
    """
    result = classify_completion(PLAIN_UNIFIED)

    assert result.cause is FineCause.WELL_FORMED, (
        f"a well-formed diff was classified {result.cause!r} (detail {result.detail!r}).\n\n"
        "WHY THIS MATTERS: `well-formed` is the control (`dig-transcripts.md` § 2 shape 15): "
        "each base can write a diff git accepts, so the walls this slice names are real. A "
        "classifier that refused a complete diff would report every base as broken."
    )
    assert "complete" in result.detail, result.detail


# --------------------------------------------------------------------------------------------
# The precedence table, asserted pairwise (`spec.md` AC2).
# --------------------------------------------------------------------------------------------


def test_a_loop_preceding_a_well_formed_diff_demotes_to_the_loop_present_marker() -> None:
    """Loop + well-formed diff → `WELL_FORMED` with the `LOOP_PRESENT` marker.

    A real diff's state outranks the loop: the loop is the mode the model was stuck in, but the
    diff after it is what the verifier would have graded, and the record must say the diff was
    the failure's home. The loop is still observed — hence the marker — it just is not the cause.
    """
    result = classify_completion(LOOP_AND_DIFF)

    assert result.cause is FineCause.WELL_FORMED, (
        f"a loop followed by a well-formed diff was classified {result.cause!r}.\n\n"
        "WHY THIS MATTERS: `im-start-loop` is primary only when no well-formed diff follows "
        "it (`prd.md` D4). Demoting the loop here keeps the partition honest about which "
        "records the loop actually killed."
    )
    assert Marker.LOOP_PRESENT in result.markers, (
        "the loop that preceded the well-formed diff was not reported as a marker.\n\n"
        "WHY THIS MATTERS: the marker is the observation (`prd.md` D4); a loop that vanishes "
        "from the record is a detector that stopped reporting."
    )


def test_a_loop_only_completion_is_im_start_loop_with_its_ratio() -> None:
    """Loop-only → `IM_START_LOOP`, with the measured ratio in the detail.

    The 7B collapse has no diff after it, so nothing outranks the loop; the detail carries the
    ratio that decided it, so the record reads as a measurement, not a label.
    """
    result = classify_completion(LOOP_ONLY)

    assert result.cause is FineCause.IM_START_LOOP, (
        f"a loop-only completion was classified {result.cause!r}.\n\n"
        "WHY THIS MATTERS: the 7B collapse is the dig's modal shape, and the classifier's "
        "whole job is to name it when it fills the record."
    )
    assert f"{im_start_ratio(LOOP_ONLY):.3f}" in result.detail, result.detail


def test_a_loop_preceding_a_broken_diff_is_still_im_start_loop() -> None:
    """Loop + stub diff → `IM_START_LOOP`: only a *well-formed* diff outranks the loop.

    Nine arm-a records carry a real stub after the loop (`dig-transcripts.md` § 2 shape 1). The
    loop is the failure there — the diff after it never survives to a verdict — so the rule's
    AND arm (`loop-dominated` AND `not well-formed`) must name the loop, not the stub.
    """
    result = classify_completion(LOOP_AND_STUB)

    assert result.cause is FineCause.IM_START_LOOP, (
        f"a loop followed by a broken diff was classified {result.cause!r}.\n\n"
        "WHY THIS MATTERS: the loop dominates and the diff after it is not well-formed, so "
        "the precedence table names the loop (`prd.md` D4). Classifying the stub instead would "
        "put nine 7B records in the wrong bucket."
    )


def test_a_first_hunk_death_beats_a_later_hunk_mismatch_in_the_same_diff() -> None:
    """First-hunk death → `HUNK_DIES_EARLY`, even when a later hunk would also mismatch.

    The walk stops at the first death; the second hunk is never reached, and the mechanical
    rule says the record is the death that ended the walk. This is the documented fuzzy margin
    (`dig-transcripts.md` § 5 Q1) resolved by the precedence table, not by judgement.
    """
    result = classify_completion(FIRST_DEATH_BEATS_LATER)

    assert result.cause is FineCause.HUNK_DIES_EARLY, (
        f"a first-hunk death beside a later mismatch was classified {result.cause!r}.\n\n"
        "WHY THIS MATTERS: rule 4 outranks rule 5 in the table (`plan_20260809.md` § Phase 2). "
        "A classifier that reported the later hunk would be naming a hunk the walk never "
        "reached, and a record can only carry the death that stopped it."
    )
    assert result.detail == DeathKind.BARE_LINE.value, result.detail


# --------------------------------------------------------------------------------------------
# The named terminal: planted garbage is unrecognised by name, never folded (`prd.md` R2).
# --------------------------------------------------------------------------------------------


def test_planted_garbage_is_unrecognised_shape_by_name() -> None:
    """Binary-looking garbage → `UNRECOGNISED_SHAPE`, with the shape that defeated the detectors.

    The extractor's prose reason would claim "the output is prose" for bytes — a false claim
    that folds a shape nobody has seen into a bucket that means "the model wrote prose". The
    terminal must refuse by name: countable, never guessed, never folded (`prd.md` R2).
    """
    result = classify_completion(GARBAGE)

    assert result.cause is FineCause.UNRECOGNISED_SHAPE, (
        f"planted garbage was classified {result.cause!r} (detail {result.detail!r}).\n\n"
        "WHY THIS MATTERS: the anti-vacuity control (`plan_20260809.md` § Phase 2, test 5). A "
        "classifier that folded bytes into `no-diff` would be reporting prose counts that were "
        "never prose, and the completeness claim — zero unrecognised records — would hold for "
        "the wrong reason."
    )
    assert "non-printable" in result.detail, (
        f"the detail {result.detail!r} does not name the shape that defeated the detectors.\n\n"
        "WHY THIS MATTERS: `unrecognised-shape` is the named terminal (R2); a detail that "
        "cannot say what was seen is a guess wearing a measurement's clothes."
    )


def test_prose_is_no_diff_with_the_extractors_reason() -> None:
    """Plain prose → `NO_DIFF`, detail = the extractor's own reason sentence.

    **Inherited-not-observed**: no stored record is a genuine prose answer; the fixture is a
    faithful replica of the extractor's documented shape so the classifier has somewhere to put
    a future prose record without inventing one.
    """
    extraction = patch_module.extract_patch(PROSE)
    assert isinstance(extraction, patch_module.NoDiff)

    result = classify_completion(PROSE)

    assert result.cause is FineCause.NO_DIFF, (
        f"prose was classified {result.cause!r} rather than NO_DIFF.\n\n"
        "WHY THIS MATTERS: the category is inherited from `patch.py`'s own reasons (`prd.md` "
        "§ 8 gap 2), and the reason sentence is the vocabulary the record must speak."
    )
    assert result.detail == extraction.reason, (
        f"the detail {result.detail!r} is not the extractor's reason {extraction.reason!r}."
    )


# --------------------------------------------------------------------------------------------
# The completeness control: every primary cause has a fixture, and every fixture claims one.
# --------------------------------------------------------------------------------------------


def test_the_fixture_set_and_the_cause_set_cover_each_other() -> None:
    """The bijection: every primary cause has a fixture, and no fixture claims no cause.

    The `test_attribution.py:299-332` shape applied to the fine causes: a cause added to the
    enum with no fixture fails here, and a fixture whose expected cause is empty fails too —
    a classifier that can name a cause no fixture exercises may be passing on nothing at all.
    """
    covered = {expected for _, expected in CAUSE_FIXTURES}

    assert all(expected for _, expected in CAUSE_FIXTURES), (
        "at least one cause fixture names no cause it must produce.\n\n"
        "WHY THIS MATTERS: the completeness control only has teeth if every fixture demands a "
        "non-empty verdict."
    )
    assert covered == set(FineCause), (
        f"causes without a fixture: {sorted(set(FineCause) - covered)}; "
        f"fixtures naming no cause: {sorted(covered - set(FineCause))}.\n\n"
        "WHY THIS MATTERS: a cause with no fixture reports zero forever, and zero reads as "
        "'this never happens' rather than as 'this classifier stopped naming it'. The partition "
        "is complete over the causes it promises (`prd.md` AC1)."
    )


# --------------------------------------------------------------------------------------------
# Identity, determinism, and the unmodified extractor (`prd.md` R1, R4; spec.md AC7).
# --------------------------------------------------------------------------------------------


def test_classify_uses_patch_pys_own_functions_by_identity() -> None:
    """Identity, not equivalence: the walk uses `patch.py`'s own objects, never copies.

    A re-implementation that agreed on today's fixtures would diverge the first time `patch.py`
    changed, and the divergence would be invisible — the autopsy would keep partitioning with a
    second extractor nobody knew existed (`prd.md` R1, the `test_attribution.py:190-195` shape).
    `_hunk_body` is the one private the walk does not call, for the reason stated in the module
    docstring: its return exposes where the body stopped, not why.
    """
    assert autopsy_module.extract_patch is patch_module.extract_patch
    assert autopsy_module._HUNK_HEADER is patch_module._HUNK_HEADER
    assert autopsy_module._diff_span is patch_module._diff_span
    assert autopsy_module._fenced_spans is patch_module._fenced_spans
    assert autopsy_module._bare is patch_module._bare
    assert autopsy_module.NoDiff is patch_module.NoDiff


def test_patch_py_is_unmodified_on_this_branch(tmp_path: Path) -> None:
    """`patch.py` has no diff on this branch: the walk measures the extractor it was built on.

    The identity test pins the function objects; this pins the file. A `patch.py` modified on
    the same branch would mean the stored completions were extracted by a different extractor
    than the one this slice's fixtures were built against — and the verification runs the git
    with the developer's own configuration switched off, so a machine-local setting cannot
    change what the diff reports (`test_attribution.py:118-141`).
    """
    result = git(
        ["diff", "--stat", "origin/master", "--", "src/whetstone/bakeoff/patch.py"],
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "", (
        f"patch.py changed on this branch:\n{result.stdout}\n\n"
        "WHY THIS MATTERS: the autopsy's walk is pinned to the extractor's own span logic; a "
        "file modified under it means the fixtures and the real extractor describe different "
        "code, and the identity test above would be passing for the wrong reason."
    )


def test_classifying_a_fixture_twice_yields_identical_records() -> None:
    """Determinism (spec AC1): the same fixture twice gives identical `(cause, detail, markers)`.

    The autopsy's documents are compared across runs, and a classifier that read the same text
    differently on the second pass would make a deterministic analysis produce
    non-deterministic output. Every fixture in the partition is checked, not one.
    """
    fixtures = [text for text, _ in CAUSE_FIXTURES] + [
        text for text, _ in DEATH_FIXTURES
    ] + [LATER_HUNK_DEATH, LOOP_AND_DIFF, LOOP_AND_STUB, FIRST_DEATH_BEATS_LATER]
    for text in fixtures:
        first = classify_completion(text)
        second = classify_completion(text)
        assert first == second, (
            f"classifying the same fixture twice yielded different records:\n"
            f"  first:  {first.cause!r} {first.detail!r} {sorted(first.markers)}\n"
            f"  second: {second.cause!r} {second.detail!r} {sorted(second.markers)}\n\n"
            "WHY THIS MATTERS: determinism is an acceptance criterion (`prd.md` R4); a walk "
            "whose verdict depends on iteration order or set hashing would fail the slice's "
            "byte-identical document promise."
        )


# --------------------------------------------------------------------------------------------
# The real-git oracle: the well-formed fixture is the shape git actually parses
# (`test_attribution.py:144-162` pattern, config scrubbed as `:118-141`).
# --------------------------------------------------------------------------------------------


def git(
    args: list[str], *, cwd: Path, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Real git, with the developer's own configuration switched off.

    The same environment scrubbing `whetstone.verify.repo._git` does, and for the same reason:
    a machine-local `apply.whitespace=fix` or a `hooksPath` would change which of these fixtures
    parses, and the parse/apply split is the entire claim this oracle makes.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        input=stdin,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "HOME": str(cwd),
        },
        check=False,
    )


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A one-file git repository that `PLAIN_UNIFIED` parses cleanly against.

    Real git rather than a stub, because the question the oracle answers — *does the shape the
    classifier called well-formed actually parse* — has one authority, and it is the `git apply`
    that `whetstone.verify.repo` shells out to.
    """
    tree = tmp_path / "checkout"
    tree.mkdir()
    (tree / "adder.py").write_text("def add(a, b):\n    return a - b\n")
    assert git(["init", "--quiet", "."], cwd=tree).returncode == 0
    assert git(["add", "adder.py"], cwd=tree).returncode == 0
    committed = git(
        ["-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "base"],
        cwd=tree,
    )
    assert committed.returncode == 0, committed.stderr
    return tree


def test_the_well_formed_fixture_parses_under_git_apply_numstat(checkout: Path) -> None:
    """The `WELL_FORMED` verdict agrees with the oracle that decided the dig's shape 15.

    `git apply --numstat` is the same parse the attribution layer's oracle uses: a fixture the
    classifier calls well-formed must be one git reads without complaint, or the classifier and
    the checkout layer would disagree about what a real diff looks like.
    """
    result = git(["apply", "--numstat", "-"], cwd=checkout, stdin=PLAIN_UNIFIED)

    assert result.returncode == 0, (
        f"git apply --numstat refused the well-formed fixture:\n{result.stderr}\n\n"
        "WHY THIS MATTERS: the classifier's `WELL_FORMED` verdict is a claim about git's own "
        "vocabulary, and git is the authority. A fixture that parses nowhere while the "
        "classifier calls it well-formed would make the control arm of every run a lie."
    )
    assert "adder.py" in result.stdout, result.stdout
