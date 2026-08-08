"""Name what a completion is before walking its hunks: markers and the loop rule.

The autopsy's fine pass reads a stored completion and says which zero it was, but it does so in
two layers and this module is the first: what the raw text *is* before any hunk walking begins.
The dig read all 208 stored completions by hand (`dig-transcripts.md` § 2) and every shape it
found was detectable by a pure pattern over the raw text; this module is those patterns, kept
separate from the walk because a completion is still a loop or a stacked fence whether or not a
diff can be found in it.

**Markers are observations, not causes** (`prd.md` D4). A marker says the text carried a shape —
a stacked fence, garbage on an index line, a phantom assignment — it never says the completion
failed *because* of that shape. The dig's evidence is that most of these are cosmetic corruption
that only kills when a hunk is also broken (`dig-transcripts.md` § 5 Q2b), so they are reported
beside the primary cause, never instead of it. The set is the *observed* set: append-only by
evidence, and the anti-vacuity test in this slice requires every member to have a fixture.

**The loop rule.** The 7B base's signature failure was a degenerate repetition loop of chat-
template tokens (`<|im_start|>` / `<|im_end|>` / `system`), and the dig found the ratio of
loop-token lines to total non-blank lines separated every observed case cleanly above `0.2`
(`dig-transcripts.md` § 2 shape 1). `im_start_ratio` measures it; `loop_verdict` applies the
rule; the `LOOP_PRESENT` marker is the detector's output, promoted to a primary cause in
Phase 2 only when no well-formed diff follows the loop.

Stdlib only, plus `patch.py`'s own span logic imported — never copied (`prd.md` R1). No model,
no network.
"""

from __future__ import annotations

import re
from collections import Counter
from enum import Enum
from itertools import pairwise

from whetstone.bakeoff.patch import _bare, _fenced_spans


#: A shape observed in a completion's raw text. Markers are observations, never verdicts: the
#: same stacked fence sits on a diff that applies and on one that dies — the marker names the
#: text, the primary cause names the failure (`prd.md` D4). The set is the observed set, from
#: the dig's shape catalogue (`dig-transcripts.md` § 2); it is append-only by evidence.
class Marker(str, Enum):
    STACKED_FENCE = "stacked-fence"
    INDEX_GARBAGE = "index-garbage"
    B_PATH_MISSING_SLASH = "b-path-missing-slash"
    SECOND_TURN_ROLLOVER = "second-turn-rollover"
    REPEATED_DIFFS = "repeated-diffs"
    PHANTOM_ASSIGNMENTS = "phantom-assignments"
    NOOP_HUNKS = "noop-hunks"
    LOOP_PRESENT = "loop-present"


#: The fine causes, the partition's vocabulary. Phase 1 uses only `IM_START_LOOP` (the loop
#: rule); the rest arrive with the hunk walk in Phase 2.
class FineCause(str, Enum):
    IM_START_LOOP = "im-start-loop"
    HUNK_DIES_EARLY = "hunk-dies-early"
    HUNK_COUNT_MISMATCH = "hunk-count-mismatch"
    HEADER_WITHOUT_HUNK = "header-without-hunk"
    WELL_FORMED = "well-formed"
    NO_DIFF = "no-diff"
    UNRECOGNISED_SHAPE = "unrecognised-shape"


#: The observed separation: a completion is loop-dominated above this ratio of loop-token lines
#: to total non-blank lines (`dig-transcripts.md` § 2 shape 1).
LOOP_DOMINANCE_RATIO = 0.2

#: The lines the dig found filling the loop, entire content exactly (`dig-transcripts.md` § 2
#: shape 1): the chat template's two markers and the word `system`.
_LOOP_TOKENS = frozenset({"<|im_start|>", "<|im_end|>", "system"})

#: The legal trailing modes on an `index` line, git's own vocabulary. Every other trailing
#: token was junk in the corpus (`dig-transcripts.md` § 2 shape 7).
_LEGAL_INDEX_MODES = frozenset({"100644", "100755", "120000", "160000"})

#: Shape 5: a line of concatenated fences, ` ``` ```diff ` or ` ``` ``` ```diff ` — the model
#: closes one fence and opens the next on the same line. Matched anywhere, on any line. The
#: gap is horizontal whitespace only: a newline between two fence lines is two lines, and a
#: closing fence followed by an opening one on the next line is the ordinary block boundary.
_STACKED_FENCE = re.compile(r"^```[ \t]*```+", re.MULTILINE)

#: Shape 7: an `index <h1>..<h2>` line, with any trailing token captured — the token decides.
_INDEX_LINE = re.compile(r"^index ([0-9a-fA-F]+)\.\.([0-9a-fA-F]+)(?:\s+(.*))?$", re.MULTILINE)

#: Shape 6: a `diff --git a/<path> b <path>` header whose `b` path lost its slash — `b `
#: followed by a space and a path that does not begin with `/`.
_B_PATH_MISSING_SLASH = re.compile(r"^diff --git a/\S+ b [^/]", re.MULTILINE)

#: Shape 12: an added line whose content begins with `=` — the left-hand side vanished.
_PHANTOM_ASSIGNMENT = re.compile(r"^\+[ \t]*=", re.MULTILINE)


def im_start_ratio(text: str) -> float:
    """The share of non-blank lines whose entire content is a chat-template token.

    The loop's lines are exactly `<|im_start|>`, `<|im_end|>` or `system` after the terminator
    is stripped — nothing else counts, because a line that carries prose next to a token is
    not the loop, it is prose. Blank lines are excluded from the denominator so a loop padded
    with blanks does not read as diluted; empty text has no loop and reports `0.0`.
    """
    lines = [_bare(line) for line in text.splitlines()]
    non_blank = [line for line in lines if line.strip()]
    if not non_blank:
        return 0.0
    loop_lines = [line for line in non_blank if line in _LOOP_TOKENS]
    return len(loop_lines) / len(non_blank)


def loop_verdict(text: str) -> tuple[FineCause | None, float]:
    """The dominance rule: `IM_START_LOOP` when the loop dominates, `None` otherwise.

    The second member is the measured ratio — Phase 2 renders it into the record's detail.
    "Not loop-dominated" is deliberately not a cause: a completion that merely carries a loop
    token or two falls through to the rest of the precedence table, and a verdict that claimed
    a cause for it would preempt that.
    """
    ratio = im_start_ratio(text)
    if ratio > LOOP_DOMINANCE_RATIO:
        return FineCause.IM_START_LOOP, ratio
    return None, ratio


def markers_of(text: str) -> frozenset[Marker]:
    """Every marker the raw completion carries, as a set.

    Each marker's detector is one pure predicate over the raw text — the dig's detectability
    notes made into code (`dig-transcripts.md` § 2), with the exact patterns pinned by the
    fixtures in `tests/bakeoff/test_autopsy_markers.py`. The `LOOP_PRESENT` detector is the
    ratio itself: it fires when the loop dominates the text, and Phase 2 decides whether the
    loop is the primary cause or a marker beside a real diff.
    """
    markers: set[Marker] = set()

    if _STACKED_FENCE.search(text):
        markers.add(Marker.STACKED_FENCE)
    if _index_garbage(text):
        markers.add(Marker.INDEX_GARBAGE)
    if _B_PATH_MISSING_SLASH.search(text):
        markers.add(Marker.B_PATH_MISSING_SLASH)
    if _second_turn(text):
        markers.add(Marker.SECOND_TURN_ROLLOVER)
    if _repeated_diffs(text):
        markers.add(Marker.REPEATED_DIFFS)
    if _PHANTOM_ASSIGNMENT.search(text):
        markers.add(Marker.PHANTOM_ASSIGNMENTS)
    if _noop_hunks(text):
        markers.add(Marker.NOOP_HUNKS)
    if im_start_ratio(text) > LOOP_DOMINANCE_RATIO:
        markers.add(Marker.LOOP_PRESENT)

    return frozenset(markers)


def _index_garbage(text: str) -> bool:
    """Is there an `index` line whose trailing token is not a legal mode?

    git writes `index <h1>..<h2>` with no trailing token, or a single legal mode when the mode
    changed. The corpus carried `10`, `101112`, `1234567`, `1024567 10` and a ~600-digit
    counting run in that position (`dig-transcripts.md` § 2 shape 7); any trailing content
    other than exactly one legal mode is junk.
    """
    for match in _INDEX_LINE.finditer(text):
        trailing = match.group(3)
        if trailing is not None and trailing.strip() not in _LEGAL_INDEX_MODES:
            return True
    return False


def _second_turn(text: str) -> bool:
    """Is there an `<|endoftext|>` with a fresh `Human:` turn after it?

    The rollover shape: the sampled conversation hit its end-of-text marker and then started a
    new example (`dig-transcripts.md` § 2 shape 9). The `Human:` must come *after* the marker —
    a transcript that quotes a prior turn with the marker at the very end is not a rollover.
    """
    end = text.find("<|endoftext|>")
    return end >= 0 and "Human:" in text[end + len("<|endoftext|>") :]


def _repeated_diffs(text: str) -> bool:
    """Are two or more fenced bodies byte-identical?

    The degenerate copy loop fences the same block two to fifteen times; a real multi-file
    patch's bodies differ (`dig-transcripts.md` § 2 shape 11). The fenced spans are `patch.py`'s
    own, imported never copied (`prd.md` R1), and the bodies are hashed whole — a byte of
    difference anywhere clears the marker.
    """
    lines = text.splitlines(keepends=True)
    bodies = ["".join(lines[begin:end]) for begin, end in _fenced_spans(lines)]
    return any(count > 1 for count in Counter(bodies).values())


def _noop_hunks(text: str) -> bool:
    """Is there an adjacent `-`/`+` pair whose content is byte-identical?

    The 14B signature of patch-shaped output with no edit in it (`dig-transcripts.md` § 2
    shape 13). The pair must be adjacent and in delete-then-add order; identical content on a
    `+`/`-` pair is the same noop seen from the other side of the hunk.
    """
    lines = [_bare(line) for line in text.splitlines()]
    for removed, added in pairwise(lines):
        if removed.startswith("-") and added.startswith("+") and removed[1:] == added[1:]:
            return True
    return False


__all__ = [
    "LOOP_DOMINANCE_RATIO",
    "FineCause",
    "Marker",
    "im_start_ratio",
    "loop_verdict",
    "markers_of",
]
