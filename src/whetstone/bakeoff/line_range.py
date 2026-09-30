"""The numbered-listing renderer and the EDIT-block parser — the measurement format.

This module asks the question the measurement exists to answer: can the pinned base
*address* a numbered listing at all? It is the generation half of the pre-committed
format in `docs/planning/edit-contract-finding/measurement-run/spec.md` ("Format"):
`EDIT <repository-relative path>:<start>-<end>`, a replacement section opened by
`<<<<<<< REPLACE` and closed by `>>>>>>> END`, one or more blocks, optionally inside one
fenced block. Two pure functions, deliberately the least clever files in the aspect.

**The renderer is byte-deterministic by construction** (the `rendering.py:25-36` rule).
It takes the same `path -> contents` mapping `sources.oracle_sources` builds and reads no
file, so nothing about the prompt depends on the filesystem the renderer happened to run
on. Files are emitted in sorted path order — never in mapping order — the numbered lines
are produced from a list, and nothing is read from the clock, the environment, or any
set's iteration order, so the same input gives the same bytes across processes and hash
seeds. That is what makes the run's `prompt_sha256` (M8) a statement about the contract
rather than about the machine.

**The operator's tests are never rendered.** A sources path naming a key of
`task.test_blobs` is refused — exactly, and in any case-folded spelling — with
`HeldTestInSources`, the `rendering.py` refusal. The contents of `test_blobs` are what
STRICT restores from golden and grades against, so quoting them would hand the policy the
answer key and make cheat 6 — special-casing the graded inputs — the cheapest strategy
available, which no execution-grounded check downstream can catch. The case-folded half
is cheat 9's discipline (`docs/ROADMAP.md` § 3): on macOS's default case-insensitive
volume a path spelled `Tests/Test_Addition.py` reaches the held file while comparing
unequal to it. An empty source map is refused too (`EmptySources`), because a prompt with
no listing asks for EDIT blocks against files the base has never seen — the sourceless
question wearing the oracle's name. An escaping source path — absolute, or climbing out
with `..` — is refused (`EscapingSourcePath`), the `locatability.checkout_reader`
discipline: the format's paths are repository-relative, and a listing that taught the
base to address anything else would not be the format.

**The parser never repairs.** A block with any defect — a missing path, a missing or
unparsable range, a missing marker, an unclosed replacement, a stray marker — refuses the
whole completion with a named reason; no block is ever dropped while others proceed. A
range that is syntactically valid but unusable (`5-2`, `0-3`) still parses: the spec's
classes put start > end and out-of-bounds ranges in `OUT_OF_RANGE`, which is the
instrument's judgement, not this parser's — the parser must never pre-empt the class the
spec named. Two leniencies, both in the format rather than against it: prose between
blocks is skipped — the spec's `MALFORMED` is "no block could be parsed", so prose around
real blocks does not make them unparseable — and line endings are separators of the
format rather than content (`patch.py`'s `_bare` precedent), so CRLF output parses as the
same language as LF. Inside a block nothing is forgiven: the line after a header must be
the open marker, the first close marker ends the replacement, and a stray marker outside
a block is a half-written block, never noise.

Stdlib only, by discipline and by construction: no third-party import — nothing from the
inference stack or anywhere else — can reach this module, and nothing under `verify/` or
`tasks/` may import it (the partition guard).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

from whetstone.bakeoff.rendering import EmptySources, HeldTestInSources
from whetstone.verify.task import Task

#: The grammar's tokens, spelled once. A header is `EDIT ` at the start of a line; the
#: markers open and close a replacement section. Everything the parser recognises outside
#: a block is one of these three.
EDIT_MARKER = "EDIT "
REPLACE_OPEN = "<<<<<<< REPLACE"
REPLACE_CLOSE = ">>>>>>> END"

#: A syntactically valid range: two decimal numbers separated by one dash. Nothing else —
#: no signs, no spaces, no partial shapes — because every other spelling is a model that
#: did not write the format, and the parser never decides what it meant.
_RANGE = re.compile(r"^(\d+)-(\d+)$")

#: The named reasons a completion is refused. Each is a defect of a block — or, for the
#: last two, the absence of any block and a marker outside a block — and each is what the
#: instrument records beside `MALFORMED`, so the finding can name what the base actually
#: wrote instead of the class alone.
MISSING_PATH = "missing path"
MISSING_RANGE = "missing range"
UNPARSABLE_RANGE = "unparsable range"
UNCLOSED_REPLACEMENT = "unclosed replacement"
MISSING_MARKER = "missing marker"
STRAY_MARKER = "stray marker"
NO_BLOCKS = "no blocks"


class EscapingSourcePath(ValueError):
    """A source map offered a path outside the repository, which the format cannot name.

    The listing's paths are the ones the base is expected to quote back after `EDIT `,
    so an absolute or `..`-climbing path would teach the base to address something the
    format does not contain. Raised rather than skipped so the caller hears that its
    source map was never the oracle the listing pretends to be.
    """


class MalformedCompletion(ValueError):
    """A completion that does not parse. The whole completion is refused, never repaired.

    Carries the reason as an attribute so the instrument can record what the model wrote
    beside its `MALFORMED` class. Raised rather than returned alongside a partial list,
    because a partial list is exactly the shape this refusal exists to make impossible.
    """

    reason: str

    def __init__(self, reason: str) -> None:
        super().__init__(f"malformed completion: {reason}")
        self.reason = reason


@dataclass(frozen=True)
class EditBlock:
    """One `EDIT` block: the path, the 1-based line range, and the replacement text.

    The range is carried exactly as written: `start > end` parses fine, because whether
    the range is usable is the instrument's `OUT_OF_RANGE` judgement, never the parser's.
    """

    path: str
    start: int
    end: int
    replacement: str


def render_line_range_prompt(task: Task, sources: Mapping[str, str]) -> str:
    """The numbered-listing prompt for `task`: every source file, numbered 1-based.

    `sources` is the `path -> contents` mapping `sources.oracle_sources` builds — the
    files as they stand at `base_commit`, which is the only commit a completion can
    address. A required argument with no default, for the same reason `render_prompt`'s
    is: no spelling of this call may quietly ask the sourceless question.

    The listing shows every line of every file, numbered 1-based, in sorted path order.
    A line number is `N: ` followed by the line, unpadded — the listing is for the base
    to *address*, and the only contract on the numbers is that they count the file's real
    lines. A file's lines are its contents split on `\n`, with the phantom empty element
    after a final newline dropped; interior empty lines are real lines and are numbered.
    An empty file has no lines and renders none — there is nothing to address.

    Refusals, in order: an empty source map (`EmptySources`); a path naming a key of
    `task.test_blobs`, exactly or case-folded (`HeldTestInSources`); an absolute or
    `..`-climbing path (`EscapingSourcePath`). Nothing is rendered when any fires.
    """
    if not sources:
        raise EmptySources(
            f"no source files were offered for task {task.task_id!r}, so the prompt would "
            f"ask for EDIT blocks against files the base has never seen. That question is "
            f"not hard, it is impossible — and scoring it beside oracle prompts would put "
            f"two different experiments under one denominator"
        )

    held = _held_among(sources, task)
    if held:
        raise HeldTestInSources(
            f"the source map for task {task.task_id!r} offers operator-held {held}, whose "
            f"contents are what STRICT restores from golden and grades against. Rendering "
            f"them — in any casing — would hand the policy the answer key and make cheat 6, "
            f"special-casing the graded inputs, the cheapest strategy available, which no "
            f"execution-grounded check downstream can catch"
        )

    escaping = sorted(path for path in sources if _escapes(path))
    if escaping:
        raise EscapingSourcePath(
            f"the source map for task {task.task_id!r} offers {escaping}, which are "
            f"absolute or climb out of the repository. The format's paths are "
            f"repository-relative, and a listing that named anything else would teach the "
            f"base to address files the format does not contain"
        )

    parts: list[str] = []
    for path in sorted(sources):
        parts.append(path)
        parts.extend(f"{n}: {line}" for n, line in enumerate(_lines(sources[path]), start=1))
        parts.append("")
    parts.extend(
        [
            _RESPONSE_HEADING,
            "",
            _RESPONSE_INTRO,
            "",
            _RESPONSE_BLOCKS,
            "",
            _RESPONSE_EXAMPLE,
            "",
            _RESPONSE_RULE,
            "",
        ]
    )
    return "\n".join(parts)


def parse_edit_blocks(text: str) -> list[EditBlock]:
    """Parse a completion in the measurement format into its blocks, in order.

    A block is `EDIT <path>:<start>-<end>` followed by `<<<<<<< REPLACE`, the replacement
    text, and `>>>>>>> END`. Blocks may sit inside one fenced block — the fence lines are
    prose like any other, since the format says nothing that makes them structural.
    Between blocks, blank lines and prose are skipped: the spec's `MALFORMED` is "no
    block could be parsed", and prose around real blocks does not make them unparseable.

    Never repairs, and never partially succeeds. Any defect refuses the whole completion
    with a named `MalformedCompletion`: a header with no path, no range, or an
    unparsable range; a header not followed immediately by the open marker; a
    replacement that never reaches the close marker; a marker with no block around it.
    A syntactically valid range is accepted whatever its numbers say — `5-2` is
    `OUT_OF_RANGE`'s judgement, made by the instrument, not here. A completion with no
    block at all is refused as `NO_BLOCKS`.
    """
    lines = text.splitlines()
    blocks: list[EditBlock] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line == "":
            index += 1
            continue
        if line in (REPLACE_OPEN, REPLACE_CLOSE):
            raise MalformedCompletion(STRAY_MARKER)
        if not line.startswith(EDIT_MARKER):
            index += 1
            continue
        path, start, end = _header(line)
        replacement, index = _section(lines, index + 1)
        blocks.append(EditBlock(path=path, start=start, end=end, replacement=replacement))
    if not blocks:
        raise MalformedCompletion(NO_BLOCKS)
    return blocks


#: The response section, which names the grammar and nothing else about editing — the
#: format is the pre-committed rule, and the prompt's job is to state it, not to teach it.
_RESPONSE_HEADING = "# Response format"
_RESPONSE_INTRO = "Address a line range and write the replacement text."
_RESPONSE_BLOCKS = "One or more blocks:"
_RESPONSE_EXAMPLE = (
    f"{EDIT_MARKER.strip()} <repository-relative path>:<start>-<end>\n"
    f"{REPLACE_OPEN}\n"
    f"replacement text\n"
    f"{REPLACE_CLOSE}"
)
_RESPONSE_RULE = (
    "Blocks may sit inside one fenced block. Paths are relative to the repository root."
)


def _lines(contents: str) -> list[str]:
    """The file's real lines: split on `\n`, the phantom element after a final newline
    dropped. Interior empty lines are kept — they are lines of the file, and a completion
    may address them. An empty file has no lines.
    """
    lines = contents.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def _held_among(sources: Mapping[str, str], task: Task) -> tuple[str, ...]:
    """Which of `sources`' paths the operator holds, exactly or case-folded.

    The exact half is `render_prompt`'s refusal; the folded half is cheat 9's discipline
    (`strict.py:_held_among` does the same comparison for the reward). Sorted so the
    refusal names the same paths on every process.
    """
    folded = {path.casefold() for path in task.test_blobs}
    return tuple(
        sorted(
            path for path in sources if path in task.test_blobs or path.casefold() in folded
        )
    )


def _escapes(path: str) -> bool:
    """Absolute, or climbing out of the repository with `..`. Refused before rendering."""
    pure = PurePosixPath(path)
    return pure.is_absolute() or ".." in pure.parts


def _header(line: str) -> tuple[str, int, int]:
    """One `EDIT` line's path and range, or the refusal naming what is missing.

    The path is everything before the **last** colon — a repository may hold a path
    containing a colon, and the range is what the format pins after it. A missing colon
    is a missing range; an empty path is a missing path; anything after the colon that is
    not `digits-digits` is an unparsable range. Each refuses with its own name, and no
    part of the line is guessed at.
    """
    remainder = line[len(EDIT_MARKER) :]
    if ":" not in remainder:
        raise MalformedCompletion(MISSING_RANGE)
    path, _, range_part = remainder.rpartition(":")
    if not path:
        raise MalformedCompletion(MISSING_PATH)
    match = _RANGE.match(range_part)
    if match is None:
        raise MalformedCompletion(UNPARSABLE_RANGE)
    return path, int(match.group(1)), int(match.group(2))


def _section(lines: list[str], index: int) -> tuple[str, int]:
    """The replacement section after a header: content up to the first close marker.

    The line at `index` must be the open marker — a blank line or prose between the
    header and the marker is a missing marker, never something to skip. The content is
    every line up to the first `>>>>>>> END`, joined with `\n`; a close marker that never
    comes is an unclosed replacement. The first close marker ends the block — a second
    marker, or anything after it, belongs to the next block or to prose.
    """
    if index >= len(lines) or lines[index] != REPLACE_OPEN:
        raise MalformedCompletion(MISSING_MARKER)
    content: list[str] = []
    index += 1
    while index < len(lines) and lines[index] != REPLACE_CLOSE:
        content.append(lines[index])
        index += 1
    if index >= len(lines):
        raise MalformedCompletion(UNCLOSED_REPLACEMENT)
    return "\n".join(content), index + 1


__all__ = [
    "EDIT_MARKER",
    "MISSING_MARKER",
    "MISSING_PATH",
    "MISSING_RANGE",
    "NO_BLOCKS",
    "REPLACE_CLOSE",
    "REPLACE_OPEN",
    "STRAY_MARKER",
    "UNCLOSED_REPLACEMENT",
    "UNPARSABLE_RANGE",
    "EditBlock",
    "EmptySources",
    "EscapingSourcePath",
    "HeldTestInSources",
    "MalformedCompletion",
    "parse_edit_blocks",
    "render_line_range_prompt",
]