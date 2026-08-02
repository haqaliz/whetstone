"""Model text in; a unified diff, or an explicit account of why there isn't one.

This module is the join between a base model's answer and the reward, and it holds the seam
where two different failures could be made to look identical. Both would corrupt the bake-off's
only output — a comparison of STRICT-PASS counts between candidate bases — while producing
numbers that look entirely ordinary.

**Why "no diff" is not the empty string.** `verify_strict(task, "")` does not mean "nothing was
submitted". `git apply` answers an empty patch with *"No valid patches in input"*, so STRICT
charges `FAIL` at `kind="patch-apply"` (`whetstone.tasks.liveness:14-20`) — **the same status a
genuinely wrong fix earns**. An extractor that returned `""` whenever it found no diff would
therefore turn its own failures into plausible model failures. Broken across the board, it would
report every candidate base as solving zero tasks, which is indistinguishable from P1's real
pivot signal — the finding that no candidate base solves any task (`docs/ROADMAP.md:387`), which
is the finding that would tell the founder to abandon expert iteration and change plan. A bug
able to forge that is the most expensive bug in this slice; it is PRD risk R1. Hence two types.
`NoDiff` has no `.diff`, so the empty patch cannot be handed on by a caller's slip — only by
someone rewriting this contract deliberately.

**Why this module never repairs a diff.** A base that emits a patch aimed at a path in the
task's `test_blobs` is attempting the canonical reward hack: editing the tests it is graded by.
STRICT refuses that before anything runs, at `kind="patch-scope"` (`strict.py:524-533`), and the
refusal is counted and published. Every part of that depends on the held path still being in the
patch when the verifier sees it. So a hunk touching a held test is passed through **unmodified**
— stripping it would convert a caught cheat into an uncaught one, grade the patch on its
remaining hunks, and quietly lower a number this project publishes as evidence of its own
honesty. That would be a reward-hacking mitigation implemented in the wrong layer. The rule this
module works to is therefore narrow and absolute: **locate a diff; never author one.**

**The one exception, and why it is not a hole.** A diff whose final line has no terminator is not
a diff git will parse: it answers *"corrupt patch at line 8"* and refuses outright (measured
against the `git apply` this repository calls). Models stop mid-line routinely. So an unterminated
extraction gets a final `\\n` and nothing else. This is safe on exactly the ground the ban rests
on: appending a line terminator cannot change which paths a diff touches and cannot drop a hunk,
so it cannot turn a patch STRICT would refuse into one STRICT would grade.

**Decisions taken here rather than deferred**, each measured against real `git apply` behaviour
and each asserted in `tests/bakeoff/test_extraction.py`:

- *Several candidate diffs* → the **first well-formed one in document order**, over fenced and
  unfenced candidates alike. The only rule that requires no judgement about which diff is better;
  any "best" rule is the harness choosing the model's answer for it.
- *Absolute paths* (`--- /Users/me/repo/x.py`) → `Extracted`, unchanged. git parses it and fails
  to find the file, because `apply` runs with `cwd=checkout` and strips one leading component
  (`repo.py`); STRICT charges `patch-apply`. Reporting `NoDiff` would record a model that wrote a
  patch as one that wrote nothing; rewriting the prefix would have this module guessing a checkout
  root it was never told, and a lucky guess grades a patch aimed somewhere the model never aimed.
- *CRLF* → `Extracted`, line endings untouched. git parses it and fails to match context against
  an LF tree. The terminator of an added line is content the patch writes to disk, so normalising
  it is authoring. The failure stays visible in the `patch-apply` count, which is what PRD M2
  requires and what R1's mitigation actually is.
- *Truncated mid-hunk* → `Extracted`. The model attempted a patch and ran out of budget; git says
  "corrupt patch" and the report separates that from a model that wrote no patch at all.
- *Truncated before the first hunk* → `NoDiff`, with a reason that names the missing hunk. A
  patch with no hunks changes nothing, but the reader needs to know it was a budget problem and
  not a prompt problem.

Stdlib only. No model, no network, and nothing under `verify/` or `tasks/` may import this.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: A hunk header, and the source of truth for where a hunk ends. The counts are optional in the
#: format — `@@ -1 +1 @@` means one line — and they are what makes trailing prose separable from
#: patch content: a markdown bullet (`- like this`) after a diff is indistinguishable from a
#: deletion line to anything that is not counting.
_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

#: The line prefixes that open a diff. `diff --git ` is git's own header; `--- ` is the plain
#: unified form, and it is accepted only when `+++ ` follows, because a lone `--- ` is also how
#: prose writes a rule, and a false start would take a paragraph for a patch.
_GIT_HEADER = "diff --git "
_OLD_FILE = "--- "
_NEW_FILE = "+++ "

#: Metadata lines that may appear between a diff header and its first hunk, or between files in a
#: multi-file patch. Taken from git's own output vocabulary. A line matching none of these, and
#: not a hunk header, ends the diff — which is what stops trailing prose being absorbed.
_HEADER_PREFIXES = (
    _GIT_HEADER,
    _OLD_FILE,
    _NEW_FILE,
    "index ",
    "old mode ",
    "new mode ",
    "new file mode ",
    "deleted file mode ",
    "similarity index ",
    "dissimilarity index ",
    "rename from ",
    "rename to ",
    "copy from ",
    "copy to ",
    "Binary files ",
    "GIT binary patch",
)

#: The fence marker. Matched after stripping leading whitespace, so an indented fence inside a
#: list item is still a fence, and after stripping the trailing `\r`, so CRLF output is not
#: silently treated as a different language.
_FENCE = "```"


@dataclass(frozen=True)
class Extracted:
    """A diff was found. `diff` is what the model wrote, ready to hand to the verifier.

    "Ready to hand to the verifier" is a claim about *shape*, never about *content*: this type
    asserts that a unified diff was located, not that it applies, not that it is correct, and
    emphatically not that it is in scope. A patch aimed at an operator-held test arrives here
    exactly as the model wrote it — deciding what to do about that is `verify_strict`'s job and
    nowhere else's (see the module docstring on why repairing it here would be a defect).
    """

    #: The located diff, byte-identical to the model's output over that region, except that a
    #: missing final newline is supplied — the single repair this module makes, and the only one
    #: that cannot change which paths a patch touches.
    diff: str


@dataclass(frozen=True)
class NoDiff:
    """No diff was found, and here is why. Deliberately **without** a `diff` attribute.

    The absence is the design. A `diff` field defaulting to `""` would let any caller hand this
    outcome to `verify_strict` and receive a FAIL at `patch-apply` — a harness failure wearing a
    model failure's clothes, which is the confusion this whole module is arranged to prevent.
    Reaching for `.diff` here raises `AttributeError` at the call site instead, loudly, in the
    caller's own stack frame.
    """

    #: A sentence naming what was seen instead of a diff, written for whoever is looking at a
    #: candidate base that scored zero. It has to distinguish "wrote prose" from "wrote a fenced
    #: block we did not recognise" from "wrote nothing", because those are a prompt problem, an
    #: extractor problem and a model problem, with three different fixes.
    reason: str


#: What `extract_patch` returns. A union rather than a shared base class on purpose: a common
#: parent invites a common `.diff` accessor, and the entire guarantee here is that no such
#: accessor exists on the no-diff arm.
Extraction = Extracted | NoDiff


def extract_patch(text: str) -> Extraction:
    """Locate the first well-formed unified diff in `text`, or explain why there is none.

    Candidates are the bodies of fenced code blocks and any diff-shaped run of unfenced lines,
    considered together in **document order** — not fences first. The first candidate that is a
    well-formed diff (a file header, plus at least one parsable hunk) wins, and is returned
    verbatim from its opening header to the end of its last hunk.
    """
    lines = text.splitlines(keepends=True)
    if not any(line.strip() for line in lines):
        return NoDiff(
            "the model produced no output at all beyond whitespace, so there was nothing to "
            "search for a diff in"
        )

    fenced = _fenced_spans(lines)
    starts = [index for index in range(len(lines)) if _opens_a_diff(lines, index)]

    saw_a_header = False
    for start in starts:
        stop, hunks = _diff_span(lines, start, _fence_end(start, fenced))
        if hunks:
            return Extracted(_terminated("".join(lines[start:stop])))
        saw_a_header = True

    if saw_a_header:
        return NoDiff(
            "a diff header was found but no hunk (`@@`) followed it, so the patch would change "
            "nothing; this is the shape of output that ran out of generation budget before the "
            "first hunk"
        )
    if fenced:
        return NoDiff(
            f"the model produced {len(fenced)} fenced code block(s) but none of them contained a "
            "unified diff; the output is a code sample or an explanation rather than a patch"
        )
    return NoDiff(
        f"no diff header (`{_GIT_HEADER.strip()}`, or `---`/`+++`) appears anywhere in the "
        f"{len(lines)} line(s) the model produced; the output is prose"
    )


def _fenced_spans(lines: list[str]) -> list[tuple[int, int]]:
    """The body of every fenced code block, as half-open line ranges.

    An unclosed fence runs to the end of the text rather than being discarded. That is not
    tolerance for sloppiness: a model that hits its token limit mid-patch leaves exactly this
    shape, and dropping the block would report the most interesting failure in the run — the
    generation budget being too small — as "the model wrote no diff".
    """
    spans: list[tuple[int, int]] = []
    opened: int | None = None
    for index, line in enumerate(lines):
        if not _bare(line).lstrip().startswith(_FENCE):
            continue
        if opened is None:
            opened = index + 1
        else:
            spans.append((opened, index))
            opened = None
    if opened is not None:
        spans.append((opened, len(lines)))
    return spans


def _fence_end(start: int, fenced: list[tuple[int, int]]) -> int:
    """Where a candidate beginning at `start` must stop: its fence's end, or `-1` for unfenced.

    A diff inside a fence may not run past the closing fence. Without this, two adjacent fenced
    blocks with no blank line between them could have the second block's prose parsed as a
    continuation of the first block's patch.
    """
    for begins, ends in fenced:
        if begins <= start < ends:
            return ends
    return -1


def _opens_a_diff(lines: list[str], index: int) -> bool:
    """Does the line at `index` begin a diff?

    `--- ` requires `+++ ` on the following line. A plain unified diff always has that pair, and
    the requirement is what keeps a prose paragraph — or a YAML document separator, or a
    signature delimiter — from being mistaken for the start of a patch.
    """
    line = _bare(lines[index])
    if line.startswith(_GIT_HEADER):
        return True
    following = _bare(lines[index + 1]) if index + 1 < len(lines) else ""
    return line.startswith(_OLD_FILE) and following.startswith(_NEW_FILE)


def _diff_span(lines: list[str], start: int, limit: int) -> tuple[int, int]:
    """Walk the diff beginning at `start`; return where it ends and how many hunks it had.

    The hunk header's declared line counts are what decide the end. That matters for one
    specific, very common shape: a model that follows its patch with a markdown bullet list.
    `- I also renamed the function` is a deletion line to any parser that goes by prefixes, so
    prefix-following would swallow the explanation into the patch and git would reject the whole
    thing as corrupt — scoring a base that produced a correct fix as having produced a broken
    one, which measures its writing habits rather than its ability.

    A hunk that ends before its declared count is exhausted — truncated output — stops the walk
    where the text stops. What was found is returned as it stands; padding it would mean grading
    context lines the model never wrote.
    """
    end = len(lines) if limit < 0 else min(limit, len(lines))
    index, hunks = start, 0

    while index < end:
        line = _bare(lines[index])
        header = _HUNK_HEADER.match(line)
        if header:
            hunks += 1
            index = _hunk_body(lines, index + 1, end, header)
            continue
        if line.startswith(_HEADER_PREFIXES):
            index += 1
            continue
        break

    return index, hunks


def _hunk_body(lines: list[str], index: int, end: int, header: re.Match[str]) -> int:
    """Consume exactly the lines one hunk declares, and no more."""
    # An omitted count means one line — `@@ -1 +1 @@` is legal, and models emit it.
    old = int(header.group(2)) if header.group(2) is not None else 1
    new = int(header.group(4)) if header.group(4) is not None else 1

    while index < end and (old > 0 or new > 0):
        line = _bare(lines[index])
        if line.startswith("\\"):
            # "\ No newline at end of file" annotates the previous line and counts as none.
            index += 1
            continue
        if line.startswith("+"):
            new -= 1
        elif line.startswith("-"):
            old -= 1
        elif line.startswith(" ") or line == "":
            # A blank context line is written by git as a bare newline, not as a space.
            old -= 1
            new -= 1
        else:
            # The hunk stopped short of its own count: truncated output, or a miscount. Either
            # way, what follows is not part of it.
            break
        index += 1

    while index < end and _bare(lines[index]).startswith("\\"):
        index += 1
    return index


def _bare(line: str) -> str:
    """The line without its terminator, so CRLF output parses as the same language as LF.

    Parsing only. The extracted text is sliced from the original `lines`, so nothing here can
    change the bytes that reach the verifier — see the module docstring on why normalising a
    line ending would be authoring rather than locating.
    """
    return line.rstrip("\r\n")


def _terminated(diff: str) -> str:
    """Supply the final newline if the model did not. The only edit this module makes.

    Measured: `git apply` refuses a patch whose last line is unterminated outright, with
    "corrupt patch at line N", so without this a model that stopped one newline early is charged
    FAIL at `patch-apply` on every task it actually solved.
    """
    return diff if diff.endswith("\n") else diff + "\n"


__all__ = ["Extracted", "Extraction", "NoDiff", "extract_patch"]
