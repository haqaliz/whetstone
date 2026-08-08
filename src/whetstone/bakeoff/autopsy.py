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

**The hunk walk** (`classify_completion`) is the second layer: it walks the hunks of the diff
`patch.py` actually extracted and records *why the walk stopped*, because a completion that
failed the bake-off failed at a specific line. The walk re-runs the extractor's span logic over
the same span it found — same hunk headers, same counts — but records what `_diff_span` throws
away: counts remaining at the stop line (a death: `bare-line` when the stop line is unprefixed,
`fence-cut` when it is a closing fence, `end-of-output` when the completion ends with counts
remaining — the truncation shape, *inferred*, `prd.md` D5), or a counter driven below zero
while the body was consumed (the overrun: a body with more lines of a kind than its header
declared, the shape git refuses as a corrupt patch — its parser loops while either counter is
non-zero, and a negative counter is truthy in C). The margin between `hunk-dies-early` and
`hunk-count-mismatch` is the dig's documented fuzzy boundary (`dig-transcripts.md` § 5 Q1);
the rule here is the mechanical one — first-hunk death is `hunk-dies-early`, any later-hunk
death or overrun is `hunk-count-mismatch` — and divergence from the dig's provisional split is
a finding, never a tune. A hunk that completes exactly at the diff's end is well-formed
whatever the completion continues with: the extracted diff is all git receives, so a line
beyond the extractor's span is text git never parses and the walk must not judge it.

**The precedence table** (`prd.md` D4) resolves exactly one primary cause per record, in a fixed
order: a no-hunk `NoDiff` is `HEADER_WITHOUT_HUNK`; a loop-dominated completion whose diff, if
any, is not well-formed is `IM_START_LOOP` (a loop before a *well-formed* diff demotes to the
`LOOP_PRESENT` marker); any other `NoDiff` is `NO_DIFF` with the extractor's own reason sentence
(the inherited vocabulary, `prd.md` § 8 gap 2); a first-hunk death is `HUNK_DIES_EARLY`; a
later-hunk death or overrun is `HUNK_COUNT_MISMATCH`; all hunks complete is
`WELL_FORMED`; and a completion no rule can claim is `UNRECOGNISED_SHAPE` by name — never
folded into a neighbour (`prd.md` R2). The terminal's one reachable face today is a NoDiff whose
text defeats the claim its inherited reason makes: binary-looking bytes are not "prose", so a
completion dominated by non-printable characters is named `UNRECOGNISED_SHAPE` instead of
inheriting the prose sentence.

**The fine→coarse mapping** (`FINE_TO_COARSE`, `autopsy`, `mapping_violations`) is the third
layer: it asserts the fine verdict against the coarse cause the run's own `attribution.json`
recorded, per record — no second `git` pass, no checkout (`prd.md` D3). `UNATTRIBUTED` is
always allowed: it means "not graded", orthogonal to the shape of the completion. A
contradiction is reported as a `MappingViolation`, never reconciled (`prd.md` R-b): the table
is the instrument that surfaces disagreement between the two layers, and an autopsy that
smoothed a record until it agreed would report the shape it hoped for instead of the one on
disk. A transcript record with no attribution row is `recorded_cause=None`,
`coarse_agrees=False` — named, never skipped, because a partial join renders a run with a
hole in its attribution as a clean one.

**The CLI** (`main`, `refuse_published_out`) is the door: `python -m whetstone.bakeoff.autopsy`
reads a run's transcript and its own attribution document, classifies every record, and writes
the `whetstone-autopsy/1` document — byte-deterministically (`json.dumps(..., sort_keys=True)`),
one record per transcript row in run order, with every attribution row that matched no record
listed as an orphan rather than dropped. The document's home is a documented gitignored root
(`runs/`, `reports/local/`, `checkpoints/`, `tasks/local/`, `_sandbox/` — `.gitignore:20-24`),
enforced **before anything is read**: an autopsy output quotes stored completions, which carry
the user's own private code, so a path git would commit is refused by name — the
`_refuse_published_transcript` discipline (`run.py:886-907`) applied to this module's own
document.

Stdlib only, plus `patch.py`'s own span logic imported — never copied (`prd.md` R1). No model,
no network.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from itertools import pairwise
from pathlib import Path

from whetstone.bakeoff.attribution import Attribution, Cause
from whetstone.bakeoff.patch import (
    _HUNK_HEADER,
    NoDiff,
    _bare,
    _diff_span,
    _fenced_spans,
    extract_patch,
)
from whetstone.bakeoff.transcript import Transcribed, Transcript


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


#: Why a hunk's body stopped with counts remaining — the three observed deaths inside a hunk
#: body (`dig-transcripts.md` § 2 shape 3). Each has a different fix, so the detail must carry
#: the kind, not just the cause. `END_OF_OUTPUT` is the inferred truncation shape (`prd.md`
#: D5): the runtime returns a bare `str` with no finish reason, so it is named from shape,
#: never claimed as a measured token cap.
class DeathKind(str, Enum):
    BARE_LINE = "bare-line"
    FENCE_CUT = "fence-cut"
    END_OF_OUTPUT = "end-of-output"


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


# --------------------------------------------------------------------------------------------
# Phase 2 — the hunk walk and the precedence table.
# --------------------------------------------------------------------------------------------

#: One completion's fine verdict: the primary cause, the detail that says why, and the markers
#: the raw text carried. Frozen and order-free so a record read twice is a record read once
#: (`prd.md` R4): `markers` is a `frozenset` precisely so equality is not iteration order.
@dataclass(frozen=True)
class AutopsyResult:
    cause: FineCause
    detail: str
    markers: frozenset[Marker]


#: What the hunk walk found. `later_death` and `overrun` carry the hunk number that violated
#: its counts, so the mismatch detail can name the violation rather than just its shape.
@dataclass(frozen=True)
class _WalkResult:
    first_death: DeathKind | None
    later_death: tuple[int, DeathKind] | None
    overrun: int | None
    hunks: int

    @property
    def is_well_formed(self) -> bool:
        """Every hunk completed within its declared counts, and at least one hunk was walked."""
        return (
            self.hunks > 0
            and self.first_death is None
            and self.later_death is None
            and self.overrun is None
        )


def classify_completion(text: str) -> AutopsyResult:
    """The precedence table (`prd.md` D4): exactly one primary cause per completion.

    The extractor's verdict comes first — a `NoDiff` is a completion with no diff in it, and a
    well-formed diff is the control — and the hunk walk then decides between the diff-side
    causes. The orderings that matter are pinned pairwise in
    `tests/bakeoff/test_autopsy_partition.py`: the no-hunk reason outranks the loop, the loop
    outranks an inherited `NoDiff` but demotes to a marker beside a well-formed diff, the
    first-hunk death outranks a later-hunk mismatch, and the named terminal catches what no
    rule can claim.
    """
    markers = markers_of(text)
    extraction = extract_patch(text)

    if isinstance(extraction, NoDiff):
        if "no hunk" in extraction.reason:
            # The extractor's own third reason: a header was found but no hunk followed.
            return AutopsyResult(FineCause.HEADER_WITHOUT_HUNK, extraction.reason, markers)
        cause, ratio = loop_verdict(text)
        if cause is FineCause.IM_START_LOOP:
            # No diff at all behind a dominant loop: the loop is the completion.
            return AutopsyResult(FineCause.IM_START_LOOP, _loop_detail(ratio), markers)
        if _unrecognisable_shape(text):
            # The inherited reason would claim "prose" for bytes; the terminal refuses by name.
            return AutopsyResult(
                FineCause.UNRECOGNISED_SHAPE, _unrecognisable_detail(text), markers
            )
        return AutopsyResult(FineCause.NO_DIFF, extraction.reason, markers)

    lines = text.splitlines(keepends=True)
    diff_lines = extraction.diff.splitlines(keepends=True)
    start = _diff_start(lines, diff_lines)
    if start is None:
        # Defensive terminal: `Extracted.diff` is always a slice of the text the walk can
        # re-derive; a record that reaches this has defeated the span logic itself.
        return AutopsyResult(
            FineCause.UNRECOGNISED_SHAPE,
            "the extractor found a diff whose span the walk could not locate in the completion",
            markers,
        )
    fenced_ends = frozenset(end for _, end in _fenced_spans(lines))
    walk = _walk(lines, start, diff_lines, fenced_ends)

    cause, ratio = loop_verdict(text)
    if cause is FineCause.IM_START_LOOP and not walk.is_well_formed:
        # The loop is the failure: it dominates the completion and what follows it is not a
        # diff git would grade. Only a well-formed diff outranks the loop.
        return AutopsyResult(FineCause.IM_START_LOOP, _loop_detail(ratio), markers)
    if walk.first_death is not None:
        # The walk ended in the first hunk with counts remaining: the stub shape.
        return AutopsyResult(FineCause.HUNK_DIES_EARLY, walk.first_death.value, markers)
    if walk.later_death is not None:
        hunk, kind = walk.later_death
        return AutopsyResult(
            FineCause.HUNK_COUNT_MISMATCH,
            f"hunk {hunk} dies early: {kind.value}",
            markers,
        )
    if walk.overrun is not None:
        return AutopsyResult(
            FineCause.HUNK_COUNT_MISMATCH,
            f"hunk {walk.overrun} body exceeds its declared counts",
            markers,
        )
    return AutopsyResult(FineCause.WELL_FORMED, f"all {walk.hunks} hunks complete", markers)


def _diff_start(lines: list[str], diff_lines: list[str]) -> int | None:
    """Where the extracted diff sits in the original lines, or `None` if it cannot be found.

    `Extracted.diff` is a byte slice of `lines` (`patch.py:170`), except that a missing final
    newline is supplied (`patch.py:313-320`) — so lines are compared bared, terminators not
    part of the identity. The first position whose bared lines match the diff *and* from which
    the extractor's own walk stops exactly where the diff ends is the candidate the extractor
    returned; the walk validation is what rejects an earlier look-alike run.
    """
    first = _bare(diff_lines[0])
    count = len(diff_lines)
    for index, line in enumerate(lines):
        if _bare(line) != first or index + count > len(lines):
            continue
        if [_bare(candidate) for candidate in lines[index : index + count]] != [
            _bare(candidate) for candidate in diff_lines
        ]:
            continue
        stop, hunks = _diff_span(lines, index, -1)
        if stop == index + count and hunks > 0:
            return index
    return None


def _walk(
    lines: list[str], start: int, diff_lines: list[str], fenced_ends: frozenset[int]
) -> _WalkResult:
    """Walk every hunk in the extracted diff, recording why the walk stopped.

    The diff's own lines are exactly what the extractor's span accepted — headers, metadata and
    hunk bodies — so a line that is not a hunk header is metadata to be passed over, the same
    traversal `_diff_span` performs. Each hunk's body is consumed against its declared counts;
    counts remaining at the stop line is a death, classified from the line after the diff in
    the original text (`_death_kind`); a counter driven below zero while the body was consumed
    is the overrun — a body with more lines of a kind than its header declared, the shape git
    refuses as a corrupt patch. The overrun is recorded but the walk continues, so a later
    hunk's death still outranks it; only a death ends the walk. `_hunk_body` is deliberately
    not called: it returns where the body stopped, not why, and the why is this phase's
    entire product.
    """
    index = 0
    hunks = 0
    first_death: DeathKind | None = None
    later_death: tuple[int, DeathKind] | None = None
    overrun: int | None = None

    while index < len(diff_lines):
        header = _HUNK_HEADER.match(_bare(diff_lines[index]))
        if header is None:
            index += 1
            continue
        hunks += 1
        old = int(header.group(2)) if header.group(2) is not None else 1
        new = int(header.group(4)) if header.group(4) is not None else 1
        index += 1
        went_negative = False
        while index < len(diff_lines) and (old > 0 or new > 0):
            line = _bare(diff_lines[index])
            if line.startswith("\\"):
                index += 1
                continue
            if line.startswith("+"):
                new -= 1
                went_negative = went_negative or new < 0
            elif line.startswith("-"):
                old -= 1
                went_negative = went_negative or old < 0
            elif line.startswith(" ") or line == "":
                old -= 1
                new -= 1
                went_negative = went_negative or old < 0 or new < 0
            else:
                break
            index += 1
        while index < len(diff_lines) and _bare(diff_lines[index]).startswith("\\"):
            index += 1
        if old > 0 or new > 0:
            kind = _death_kind(lines, fenced_ends, start + index)
            if hunks == 1:
                first_death = kind
            else:
                later_death = (hunks, kind)
            break
        if went_negative and overrun is None:
            # git's parser loops while either counter is non-zero — in C a negative counter
            # is truthy — so a body with more lines of a kind than declared keeps it reading
            # past the hunk, and the patch dies as corrupt. The walk's loop exits at
            # zero-or-negative, so the overrun must be recorded by name, or the walk and git
            # would disagree about the same hunk (`prd.md` R-a).
            overrun = hunks

    return _WalkResult(first_death, later_death, overrun, hunks)


def _death_kind(lines: list[str], fenced_ends: frozenset[int], stop: int) -> DeathKind:
    """The death's shape, read from the line the walk stopped at.

    `END_OF_OUTPUT` when the completion ends with counts remaining — the inferred truncation
    shape (`prd.md` D5); `FENCE_CUT` when the stop line is a closing fence (the fence ends of
    `_fenced_spans`, never a guessed prefix); `BARE_LINE` when it is unprefixed — a pasted
    source line, or anything else the walk cannot consume.
    """
    if stop >= len(lines):
        return DeathKind.END_OF_OUTPUT
    if stop in fenced_ends:
        return DeathKind.FENCE_CUT
    return DeathKind.BARE_LINE


def _loop_detail(ratio: float) -> str:
    """The loop cause's detail: the measured ratio that decided it (`prd.md` D4)."""
    return f"loop-dominated: {ratio:.3f} of non-blank lines are chat-template tokens"


def _unrecognisable_share(text: str) -> float:
    """The share of non-blank characters that are not printable.

    Control bytes are not prose: a completion dominated by them is a shape no inherited reason
    may claim. Blank characters are excluded so a short garbage burst padded with newlines is
    not read as diluted.
    """
    chars = [char for char in text if not char.isspace()]
    if not chars:
        return 0.0
    return sum(not char.isprintable() for char in chars) / len(chars)


def _unrecognisable_shape(text: str) -> bool:
    """Is the completion dominated by non-printable characters?

    The named terminal's reachable face (`prd.md` R2): the extractor would report "the output
    is prose" for bytes, and a bucket that means "wrote prose" cannot honestly hold them.
    """
    return _unrecognisable_share(text) > 0.5


def _unrecognisable_detail(text: str) -> str:
    """The terminal's detail: the shape that defeated the detectors, named, never guessed."""
    return (
        f"the completion is dominated by non-printable characters "
        f"({_unrecognisable_share(text):.3f} of non-blank characters)"
    )


# --------------------------------------------------------------------------------------------
# Phase 3 — the fine→coarse mapping and the per-record join against the run's own attribution.
# --------------------------------------------------------------------------------------------


#: Which recorded coarse causes each fine cause may explain (`prd.md` R3). Pure data in the
#: `_FOLD`/`compare_to_counts` shape (`attribution.py:257-264, 304-346`): the fine pass names
#: the shape of the completion, the run's own `attribution.json` records the coarse cause, and
#: this table is the assertion between them.
#:
#: `UNATTRIBUTED` is deliberately not listed — it is **always** allowed: it means "not graded"
#: (no checkout for the public instance), which is orthogonal to the shape of the completion,
#: and each stored run carries one such record whose diff is shape-classifiable
#: (`dig-transcripts.md` § 2 shape 2 note). `UNRECOGNISED_SHAPE` maps to the **empty set**:
#: nothing may be asserted about a shape no rule claims, so the empty set is its assertion —
#: any recorded coarse cause contradicts it.
#:
#: `IM_START_LOOP` allows `WOULD_NOT_PARSE` because a loop-dominated completion can still
#: carry a diff git refused: the loop ate the token budget, and the completions that escape
#: it near the cap write a stub the run's attribution recorded as `WOULD_NOT_PARSE`
#: (`dig-transcripts.md` § 4). The two layers describe the same record from two sides.
#:
#: A contradiction is reported as a `MappingViolation`, never reconciled (`prd.md` R-b): this
#: table is the instrument that surfaces disagreement between the two layers, not a smoother.
FINE_TO_COARSE: Mapping[FineCause, frozenset[Cause]] = {
    FineCause.IM_START_LOOP: frozenset(
        {Cause.NO_DIFF_HEADER, Cause.FENCED_WITHOUT_DIFF, Cause.WOULD_NOT_PARSE}
    ),
    FineCause.HUNK_DIES_EARLY: frozenset({Cause.WOULD_NOT_PARSE}),
    FineCause.HUNK_COUNT_MISMATCH: frozenset({Cause.WOULD_NOT_PARSE}),
    FineCause.HEADER_WITHOUT_HUNK: frozenset({Cause.HEADER_WITHOUT_HUNK}),
    FineCause.WELL_FORMED: frozenset({Cause.APPLIED, Cause.PARSED_BUT_DID_NOT_APPLY}),
    FineCause.NO_DIFF: frozenset({Cause.NO_DIFF_HEADER, Cause.FENCED_WITHOUT_DIFF}),
    FineCause.UNRECOGNISED_SHAPE: frozenset(),
}


@dataclass(frozen=True)
class AutopsyRecord:
    """One rollout, whole: the fine verdict, the coarse cause its run recorded, and the agreement.

    The record is the join (`prd.md` R3): the fine pass names what the completion is, the
    recorded cause names what the run's own attribution measured, and `coarse_agrees` says
    whether the two agree. `recorded_cause` is `None` exactly when the attribution has no row
    for this `(candidate, task_id)` — a divergence named, never skipped.
    """

    candidate: str
    task_id: str
    cause: FineCause
    detail: str
    markers: frozenset[Marker]
    recorded_cause: Cause | None
    coarse_agrees: bool


def _joined(record: Transcribed, recorded: Cause | None) -> AutopsyRecord:
    """One record: its fine verdict bound to its recorded coarse cause, with the agreement flag.

    `None` (a missing attribution row) is the only case where the agreement is `False` without
    a contradiction: there is nothing to agree with, and that is named rather than skipped
    (`prd.md` D3). `UNATTRIBUTED` always agrees — it means "not graded", orthogonal to the
    completion's shape (`prd.md` R3). Every other recorded cause agrees exactly when the fine
    cause's allowed set contains it.
    """
    result = classify_completion(record.completion)
    if recorded is None:
        agrees = False
    elif recorded is Cause.UNATTRIBUTED:
        agrees = True
    else:
        agrees = recorded in FINE_TO_COARSE[result.cause]
    return AutopsyRecord(
        candidate=record.candidate,
        task_id=record.task_id,
        cause=result.cause,
        detail=result.detail,
        markers=result.markers,
        recorded_cause=recorded,
        coarse_agrees=agrees,
    )


def autopsy(
    transcribed: tuple[Transcribed, ...],
    attributions: Mapping[tuple[str, str], Cause],
) -> tuple[AutopsyRecord, ...]:
    """Join every stored completion to the coarse cause its own run recorded, in transcript order.

    Each record is classified by the fine pass and looked up in the run's own attribution rows
    by `(candidate, task_id)` — the transcript's own key shape (`transcript.py:61`). A record
    with no attribution row is `recorded_cause=None`, `coarse_agrees=False` **by name**, never
    skipped: a partial join would render a run with a hole in its attribution as a clean one
    (`prd.md` D3). The order is the transcript's — the document is written in run order.
    """
    return tuple(_joined(record, attributions.get(record.key)) for record in transcribed)


@dataclass(frozen=True)
class MappingViolation:
    """One record whose recorded coarse cause contradicts its fine cause. Both sides named.

    `recorded_cause` is never `None` and never `UNATTRIBUTED` here: a missing row has nothing
    to contradict — it is named by `coarse_agrees=False` instead — and `UNATTRIBUTED` is
    always allowed (`prd.md` R3). The contradiction is reported, never reconciled: both sides
    travel so the operator reading the divergence sees the direction and the size.
    """

    candidate: str
    task_id: str
    fine_cause: FineCause
    recorded_cause: Cause


def mapping_violations(records: Iterable[AutopsyRecord]) -> tuple[MappingViolation, ...]:
    """Every record where the recorded coarse cause contradicts the fine cause, in order.

    The filter is the complement of the agreement rule, narrowed to what can contradict: a
    record that agrees is not a violation; a missing row (`recorded_cause is None`) is a gap,
    not a contradiction, and is named by `coarse_agrees=False` where it stands; and
    `UNATTRIBUTED` is always allowed (`prd.md` R3) — it means "not graded", orthogonal to
    shape. What remains is a real disagreement between the fine pass and the run's own
    attribution, reported rather than smoothed (`prd.md` R-b).
    """
    violations: list[MappingViolation] = []
    for record in records:
        recorded = record.recorded_cause
        if record.coarse_agrees or recorded is None or recorded is Cause.UNATTRIBUTED:
            continue
        violations.append(
            MappingViolation(
                candidate=record.candidate,
                task_id=record.task_id,
                fine_cause=record.cause,
                recorded_cause=recorded,
            )
        )
    return tuple(violations)


def breakdown(records: Iterable[AutopsyRecord]) -> dict[str, dict[FineCause, int]]:
    """Counts per candidate, per fine cause. Absent causes are absent, never zero-filled.

    The `attribution.py:227-242` discipline, carried into the fine pass: a zero here would be
    indistinguishable from a cause that stopped matching anything, and the difference between
    "this never happened" and "this stopped being observed" is the difference between a
    finding and a broken instrument. Per candidate because that is the finding: the failure
    modes differ between bases, and a pooled total is exactly what would hide it.
    """
    counts: dict[str, dict[FineCause, int]] = {}
    for record in records:
        per_candidate = counts.setdefault(record.candidate, {})
        per_candidate[record.cause] = per_candidate.get(record.cause, 0) + 1
    return counts


def marker_counts(records: Iterable[AutopsyRecord]) -> dict[str, dict[Marker, int]]:
    """The same shape for markers: per candidate, per marker; absent markers absent.

    Markers are observations, not causes (`prd.md` D4), so they are counted separately from
    the partition — with the same absent-never-zero rule, for the same reason: a marker that
    has stopped matching anything must read as a broken detector, not as a quiet zero.
    """
    counts: dict[str, dict[Marker, int]] = {}
    for record in records:
        per_candidate = counts.setdefault(record.candidate, {})
        for marker in record.markers:
            per_candidate[marker] = per_candidate.get(marker, 0) + 1
    return counts


# --------------------------------------------------------------------------------------------
# Phase 4 — the CLI and the locality refusal.
# --------------------------------------------------------------------------------------------

#: The document this module writes.
AUTOPSY_SCHEMA = "whetstone-autopsy/1"

#: The document it reads: `attribution.py`'s own output (`attribution.py:499`). A document
#: carrying any other schema is not the run's own attribution and is refused by name — the
#: coarse causes must be the ones the run recorded, not a near-miss from another run.
ATTRIBUTION_SCHEMA = "whetstone-attribution/1"

#: The roots `.gitignore:20-24` reserves for the loop's own artifacts, which is where an autopsy
#: document belongs. Trailing-slash form, the directory-only patterns as git reads them; the
#: bare form answers "not ignored" and is pinned as a trap by `tests/test_tasks_layout.py`.
IGNORED_OUT_ROOTS = ("runs/", "reports/local/", "checkpoints/", "tasks/local/", "_sandbox/")


class _UsageError(ValueError):
    """An invocation mistake the CLI reports as exit 2: a document that does not parse."""


class OutNotPrivate(ValueError):
    """An `--out` path git would commit. Raised before anything is read or written."""


def refuse_published_out(out: Path) -> None:
    """Refuse an `--out` that does not sit under a documented gitignored root.

    Resolved rather than compared as written, and compared with `is_relative_to`, because
    `out/../out/x.json` and a symlinked scratch directory both name a path inside `out` while
    comparing unequal to it — the check has to hold against the path that gets written, not the
    one that got typed. `resolve()` never requires the path to exist, so an honest first run
    into a not-yet-created directory is not refused (`run.py:886-907`).
    """
    if any(out.resolve().is_relative_to(Path(root).resolve()) for root in IGNORED_OUT_ROOTS):
        return
    raise OutNotPrivate(
        f"the document at {str(out)!r} does not sit under one of the documented gitignored "
        f"roots ({', '.join(IGNORED_OUT_ROOTS)}). An autopsy reads stored completions, and a "
        "completion quotes the user's own private donor code back verbatim, so the document is "
        "only ever written under a root git already ignores. Point --out under one of those; "
        "this is refused rather than warned about because a warning is read after the file "
        "already exists"
    )


def _read_attribution_rows(path: Path) -> tuple[Attribution, ...]:
    """The run's own attribution document, parsed strictly — a row that does not parse is an error.

    The document must declare `whetstone-attribution/1` and carry an `attributions` list, and
    every row must be keyable: candidate, task id, and a cause string the replay actually has a
    member for. A row that cannot be keyed is refused by name rather than matched by a guess —
    the alternative is an unknown cause drifting into whichever bucket happens to match, which
    is the invented-taxonomy failure this whole slice exists to refuse (`prd.md` § 8). The
    `detail` field travels with the row and is carried through unused; the document does not
    consume it.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise _UsageError(
            f"the attribution document at {str(path)!r} could not be read as JSON "
            f"({type(exc).__name__}: {exc})"
        ) from exc
    except OSError as exc:
        raise _UsageError(
            f"the attribution document at {str(path)!r} could not be read: {exc}"
        ) from exc
    if not isinstance(raw, dict) or raw.get("schema") != ATTRIBUTION_SCHEMA:
        raise _UsageError(
            f"the attribution document at {str(path)!r} does not declare schema "
            f"{ATTRIBUTION_SCHEMA!r}, so its rows cannot be trusted as the coarse causes this "
            "run recorded"
        )
    rows = raw.get("attributions")
    if not isinstance(rows, list):
        raise _UsageError(
            f"the attribution document at {str(path)!r} carries no 'attributions' list, so "
            "there is nothing to join the transcript against"
        )

    parsed: list[Attribution] = []
    for number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise _UsageError(
                f"attribution row {number} of {str(path)!r} is not an object, so the join "
                "cannot key it"
            )
        try:
            candidate = row["candidate"]
            task_id = row["task_id"]
        except KeyError as exc:
            raise _UsageError(
                f"attribution row {number} of {str(path)!r} is missing {exc.args[0]!r}, which "
                "is half the join key — a row that cannot be keyed is refused, not matched by "
                "a guess"
            ) from exc
        if not isinstance(candidate, str) or not isinstance(task_id, str):
            raise _UsageError(
                f"attribution row {number} of {str(path)!r} names its candidate or task with "
                "a non-string, so the join cannot key it"
            )
        try:
            cause = Cause(row["cause"])
        except (KeyError, ValueError, TypeError) as exc:
            raise _UsageError(
                f"attribution row {number} of {str(path)!r} names cause "
                f"{row.get('cause')!r}, which is not one of the replay's causes "
                f"({', '.join(cause.value for cause in Cause)})"
            ) from exc
        parsed.append(Attribution(candidate, task_id, cause, str(row.get("detail", ""))))
    return tuple(parsed)


def main(argv: Sequence[str] | None = None) -> int:
    """Classify a run's transcript offline and write the document. No model, no network.

    Separate from `run.py` on purpose, and beside `attribution.py` for the same reason that
    module sits beside it: an autopsy costs a file read, and a driver that needed the engine
    back would make every question about a finished night cost another night of generation.

    `--out` is checked **before** anything is loaded — the refusal is the
    `_refuse_published_transcript` discipline (`run.py:886-907`) applied to this module's own
    document: an autopsy output quotes stored completions, which carry the user's own private
    code, so a path git would commit is a usage error, named, with nothing read and nothing
    written. A missing transcript or attribution, a document that does not parse, and a cause
    string the replay has no member for are each exit 2 with the reason named — a join against
    nothing would render every record's recorded cause `None`, which is a run with a hole in
    its attribution wearing the shape of a clean one.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.bakeoff.autopsy",
        description=(
            "Classify every stored completion of a bake-off run and assert each fine verdict "
            "against the coarse cause the run's own attribution.json recorded. Offline: no "
            "model is loaded and no network is touched, and the document is written only "
            "under a documented gitignored root."
        ),
    )
    parser.add_argument("--transcript", required=True, type=Path, help="the run's transcript")
    parser.add_argument(
        "--attribution", required=True, type=Path, help="the run's own attribution.json"
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="where the document is written"
    )
    namespace = parser.parse_args(argv)

    out = namespace.out
    try:
        refuse_published_out(out)
    except OutNotPrivate as exc:
        print(f"whetstone autopsy: {exc}", file=sys.stderr)
        return 2

    transcript = namespace.transcript
    if not transcript.is_file():
        print(
            f"whetstone autopsy: {str(transcript)!r} is not a file. Classifying a transcript "
            "that is not there would report an empty run — no records, no causes — which reads "
            "as 'every rollout classified and none found', a run nobody measured wearing the "
            "shape of a clean one",
            file=sys.stderr,
        )
        return 2

    attribution = namespace.attribution
    if not attribution.is_file():
        print(
            f"whetstone autopsy: {str(attribution)!r} is not a file. The coarse causes come "
            "from the run's own attribution.json, and a join against nothing would render "
            "every record's recorded cause as None — a run whose attribution was lost, wearing "
            "the shape of one that never had any",
            file=sys.stderr,
        )
        return 2

    try:
        rows = _read_attribution_rows(attribution)
    except _UsageError as exc:
        print(f"whetstone autopsy: {exc}", file=sys.stderr)
        return 2

    records = tuple(Transcript(transcript).replay().values())
    attributions = {(row.candidate, row.task_id): row.cause for row in rows}
    audited = autopsy(records, attributions)
    counts = breakdown(audited)
    markers = marker_counts(audited)
    violations = mapping_violations(audited)
    recorded_keys = {record.key for record in records}
    orphans = [row for row in rows if (row.candidate, row.task_id) not in recorded_keys]

    document = {
        "schema": AUTOPSY_SCHEMA,
        "transcript": str(transcript),
        "attribution": str(attribution),
        "rollouts": len(records),
        "breakdown": {
            candidate: {cause.value: count for cause, count in sorted(per.items())}
            for candidate, per in sorted(counts.items())
        },
        "marker_counts": {
            candidate: {marker.value: count for marker, count in sorted(per.items())}
            for candidate, per in sorted(markers.items())
        },
        "mapping_violations": [asdict(one) for one in violations],
        "orphan_attribution_rows": [
            {"candidate": one.candidate, "task_id": one.task_id, "cause": one.cause.value}
            for one in sorted(orphans, key=lambda row: (row.candidate, row.task_id))
        ],
        "records": [
            {
                "candidate": one.candidate,
                "task_id": one.task_id,
                "cause": one.cause.value,
                "detail": one.detail,
                "markers": sorted(marker.value for marker in one.markers),
                "recorded_cause": (
                    None if one.recorded_cause is None else one.recorded_cause.value
                ),
                "coarse_agrees": one.coarse_agrees,
            }
            for one in audited
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for candidate, per in sorted(counts.items()):
        rendered = ", ".join(f"{cause.value}={count}" for cause, count in sorted(per.items()))
        print(f"{candidate}: {rendered}")
    for violation in violations:
        print(
            f"{violation.candidate} {violation.task_id}: "
            f"fine={violation.fine_cause.value} recorded={violation.recorded_cause.value}",
            file=sys.stderr,
        )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ATTRIBUTION_SCHEMA",
    "AUTOPSY_SCHEMA",
    "FINE_TO_COARSE",
    "IGNORED_OUT_ROOTS",
    "LOOP_DOMINANCE_RATIO",
    "AutopsyRecord",
    "AutopsyResult",
    "DeathKind",
    "FineCause",
    "MappingViolation",
    "Marker",
    "OutNotPrivate",
    "autopsy",
    "breakdown",
    "classify_completion",
    "im_start_ratio",
    "loop_verdict",
    "main",
    "mapping_violations",
    "marker_counts",
    "markers_of",
    "refuse_published_out",
]
