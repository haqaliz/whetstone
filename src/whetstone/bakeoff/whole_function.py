"""The whole-function renderer and the format's home — this slice's measurement format.

This module asks the question this measurement exists to answer: can the pinned base
*address* a whole-function edit at all — name the file, name the function, and write the
replacement body? It is the generation half of the pre-committed format in
`docs/planning/whole-function-edit-finding/measurement-run/spec.md` ("Format"):
`EDIT <repository-relative path>`, `FUNCTION <name>`, a replacement section opened by
`<<<<<<< REPLACE` and closed by `>>>>>>> END`, exactly one block per completion. The
grammar's tokens are spelled once here — the constants below are the format's single
home, shared by the renderer, the parser, and later the instrument.

**The renderer is byte-deterministic by construction** (the `rendering.py:25-36` rule).
It takes the same `path -> contents` mapping `sources.oracle_sources` builds and reads no
file, so nothing about the prompt depends on the filesystem the renderer happened to run
on. Files are emitted in sorted path order — never in mapping order — the source
sections come from a list, and nothing is read from the clock, the environment, or any
set's iteration order, so the same input gives the same bytes across processes and hash
seeds. That is what makes the run's `prompt_sha256` (M8) a statement about the contract
rather than about the machine.

**The operator's tests are never rendered.** A sources path naming a key of
`task.test_blobs` is refused — exactly, and in any case-folded spelling — with
`HeldTestInSources`, the `rendering.py` refusal. The contents of `test_blobs` are what
STRICT restores from golden and grades against, so quoting them would hand the policy
the answer key and make cheat 6 — special-casing the graded inputs — the cheapest
strategy available, which no execution-grounded check downstream can catch. The
case-folded half is cheat 9's discipline (`docs/ROADMAP.md` § 3): on macOS's default
case-insensitive volume a path spelled `Tests/Test_Addition.py` reaches the held file
while comparing unequal to it. An empty source map is refused too (`EmptySources`), and
an escaping source path — absolute, or climbing out with `..` — is refused
(`EscapingSourcePath`), both as in `line_range.py`, because a prompt that showed no
file, or a file the format could not name, would not be this format's question.

**The parser never repairs.** The grammar is exactly one block: both headers present and
ordered, the fence opened and closed exactly once, and no `def ` or `async def ` line at
the body's own indentation — the signature restatement the format never asks for, since
the body is the only replacement surface and the harness keeps the original def line.
Any defect refuses the whole completion with a named reason; no part of it is ever
dropped while the rest proceeds, and nothing is guessed at. What the parser does NOT
judge is deliberately left to the instrument: whether the body sits at the right
indentation, and whether it parses, are the spec's classes (`IndentationError` →
`MALFORMED`, any other wrapped-parse failure → `NOT_PARSEABLE`; spec R1) — so an
indented nested `def` is body content here, exactly as a header inside a replacement
section is content in `line_range.py`.

**The format's bounds are the spec's, disclosed in the finding, never repaired here.**
Body-only replacement cannot express a signature change, and one function per rollout
cannot express a multi-function fix (spec R4); this module states the format and checks
it, and nothing more.

Stdlib only, by discipline and by construction: the module's own import list imports
nothing under `verify/` or `tasks/` — the `Task` type appears in the signature under
`TYPE_CHECKING` alone, so importing this module never executes a reward-path import —
and nothing from the inference stack or anywhere else can reach it. The import-list
assertion lives in `tests/bakeoff/test_whole_function_renderer.py`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from whetstone.bakeoff.line_range import EscapingSourcePath
from whetstone.bakeoff.rendering import EmptySources, HeldTestInSources

if TYPE_CHECKING:
    from whetstone.verify.task import Task

#: The grammar's tokens, spelled once. A header is `EDIT ` or `FUNCTION ` at the start of
#: a line; the markers open and close a replacement section. These four strings are the
#: format's single home — the renderer poses them, the parser recognises them, and the
#: instrument will record them, all from here.
EDIT_MARKER = "EDIT "
FUNCTION_MARKER = "FUNCTION "
REPLACE_OPEN = "<<<<<<< REPLACE"
REPLACE_CLOSE = ">>>>>>> END"

#: The named reasons a completion is refused, in the order the parser can hit them. Each
#: is what the instrument records beside `MALFORMED`, so the finding can name what the
#: base actually wrote instead of the class alone.
MISSING_EDIT = "missing EDIT header"
MISSING_PATH = "missing path"
MISSING_FUNCTION = "missing FUNCTION header"
MISSING_NAME = "missing name"
MISSING_MARKER = "missing marker"
STRAY_MARKER = "stray marker"
UNCLOSED_FENCE = "unclosed fence"
MULTIPLE_BLOCKS = "two blocks"
SIGNATURE_RESTATEMENT = "def line inside the body"


@dataclass(frozen=True)
class Block:
    """One whole-function block: the repository-relative path, the function name, and the
    replacement body, carried byte-exactly as written.

    Whether the body is usable is the instrument's judgement — the spec's classes —
    never this parser's: an empty body parses, and so does a body no real function could
    contain, because which of those is `MALFORMED` and which `NOT_PARSEABLE` is decided
    by the wrapped-parse gate, not here.
    """

    path: str
    name: str
    body: str


@dataclass(frozen=True)
class NoBlock:
    """The grammar refused the completion. Carries the reason the instrument records.

    Returned rather than raised so every defect is a value the instrument can classify —
    a completion that did not parse is an ordinary outcome of the measurement, not an
    exception in it.
    """

    reason: str


def render_whole_function_prompt(task: Task, sources: Mapping[str, str]) -> str:
    """The whole-function prompt for `task`: the problem, the oracle files, the grammar.

    `sources` is the `path -> contents` mapping `sources.oracle_sources` builds — the
    files as they stand at `base_commit`, which is the only state a completion can
    address. A required argument with no default, for the same reason `render_prompt`'s
    is: no spelling of this call may quietly ask the sourceless question.

    The prompt poses the problem statement, shows every source file inside a fence the
    contents cannot close, in sorted path order, and states the format's grammar exactly
    as the spec pins it: one block, both headers, the fence, and the rules that bound
    the body — the name is a module-level `def`/`async def`, the body is the only
    replacement surface (no def line, no signature restatement), the body arrives at the
    function's indentation, and exactly one block per reply.

    Refusals, in order: an empty source map (`EmptySources`); a path naming a key of
    `task.test_blobs`, exactly or case-folded (`HeldTestInSources`); an absolute or
    `..`-climbing path (`EscapingSourcePath`). Nothing is rendered when any fires.
    """
    if not sources:
        raise EmptySources(
            f"no source files were offered for task {task.task_id!r}, so the prompt would "
            f"ask for an EDIT block against files the base has never seen. That question "
            f"is not hard, it is impossible — and scoring it beside oracle prompts would "
            f"put two different experiments under one denominator"
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

    lines = [
        _PROBLEM_HEADING,
        "",
        task.problem_statement.strip(),
        "",
        _SOURCES_HEADING,
        "",
        _SOURCES_INTRO,
        "",
        *(line for path in sorted(sources) for line in _shown(path, sources[path])),
        _RESPONSE_HEADING,
        "",
        _RESPONSE_INTRO,
        "",
        _RESPONSE_EXAMPLE,
        "",
        _RESPONSE_RULES,
        "",
    ]
    return "\n".join(lines)


def parse_edit_block(text: str) -> Block | NoBlock:
    """Parse a completion in the whole-function format, or refuse it with a named reason.

    The grammar is exactly one block: `EDIT <path>` then `FUNCTION <name>`, the line
    after the headers the open marker, the replacement body up to the first close marker,
    and nothing structural after it. Prose before the block or after it is skipped — the
    spec's `MALFORMED` is about the block, so words around a real block do not make it
    unparseable — but nothing inside the block is forgiven, and a second block, a stray
    marker, or a stray header refuses the whole completion.

    Never repairs, and never partially succeeds. Every defect refuses the completion with
    a named `NoBlock`: no EDIT header at all (a `FUNCTION` header where the EDIT belongs,
    or prose only); an EDIT header with no path; no FUNCTION header after the EDIT; a
    FUNCTION header with no name; a line other than the open marker after the headers; a
    stray marker with no block around it; a replacement that never reaches the close
    marker; a second block; a `def ` or `async def ` line at the body's own indentation —
    the signature restatement the format never asks for. An empty body parses; whether
    it is usable is the instrument's class, never this parser's. A completion that
    parses returns `Block(path, name, body)` with the body preserved byte-exactly.
    """
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line == "":
            index += 1
            continue
        if line in (REPLACE_OPEN, REPLACE_CLOSE):
            return NoBlock(STRAY_MARKER)
        if line.startswith(FUNCTION_MARKER):
            return NoBlock(MISSING_EDIT)
        if line.startswith(EDIT_MARKER):
            break
        index += 1
    else:
        return NoBlock(MISSING_EDIT)

    path = line[len(EDIT_MARKER) :]
    if not path:
        return NoBlock(MISSING_PATH)
    index += 1
    if index >= len(lines) or not lines[index].startswith(FUNCTION_MARKER):
        return NoBlock(MISSING_FUNCTION)
    name = lines[index][len(FUNCTION_MARKER) :]
    if not name:
        return NoBlock(MISSING_NAME)
    index += 1
    if index >= len(lines) or lines[index] != REPLACE_OPEN:
        return NoBlock(MISSING_MARKER)
    index += 1
    body: list[str] = []
    while index < len(lines) and lines[index] != REPLACE_CLOSE:
        line = lines[index]
        if line == REPLACE_OPEN:
            return NoBlock(STRAY_MARKER)
        if line.startswith("def ") or line.startswith("async def "):
            return NoBlock(SIGNATURE_RESTATEMENT)
        body.append(line)
        index += 1
    if index >= len(lines):
        return NoBlock(UNCLOSED_FENCE)
    for trailing in lines[index + 1 :]:
        if trailing == "":
            continue
        if trailing.startswith(EDIT_MARKER):
            return NoBlock(MULTIPLE_BLOCKS)
        if trailing in (REPLACE_OPEN, REPLACE_CLOSE) or trailing.startswith(FUNCTION_MARKER):
            return NoBlock(STRAY_MARKER)
    return Block(path=path, name=name, body="\n".join(body))


#: The response section, which states the spec's grammar and the rules that bound it —
#: the format is the pre-committed rule, and the prompt's job is to state it, not to
#: teach it.
_PROBLEM_HEADING = "# Problem"
_SOURCES_HEADING = "# Source files"
_SOURCES_INTRO = (
    "These are the repository files at the checkout you are editing, shown exactly as they "
    "stand. The EDIT path names one of these files."
)
_RESPONSE_HEADING = "# Response format"
_RESPONSE_INTRO = "Replace the body of one module-level function."
_RESPONSE_EXAMPLE = (
    f"{EDIT_MARKER.strip()} <repository-relative path>\n"
    f"{FUNCTION_MARKER.strip()} <name>\n"
    f"{REPLACE_OPEN}\n"
    f"<body — the new function body, at the function's indentation>\n"
    f"{REPLACE_CLOSE}"
)
_RESPONSE_RULES = (
    "<name> is a module-level def or async def in the named file. The body is the ONLY "
    "replacement surface — no def line, no signature restatement: the harness keeps the "
    "original def line. The body arrives at the function's indentation. Reply with exactly "
    "one block. Paths are relative to the repository root."
)

#: How one file's body is delimited — a fence whose length is computed from the content,
#: the `rendering.py` discipline: a source file containing a fenced example would
#: otherwise close its own block, and everything after it would read as prose.
_FENCE = "`"
_MINIMUM_FENCE = 3
_BACKTICKS = re.compile(r"`+")


def _shown(path: str, contents: str) -> tuple[str, ...]:
    """One file's section: its path, then its whole body inside a fence the body cannot
    close.

    Trailing newlines are dropped so the closing fence sits against the last line of the
    file, for the same reason `problem_statement` is stripped: whether a file ends in one
    blank line or two is not part of the question, and letting it move the recorded prompt
    hash would read as an edited contract under M7b. Nothing else about the bytes is
    touched — a body is written against these lines, so re-indenting or re-wrapping them
    would be handing the base a file that is not in the checkout.
    """
    # A list rather than `max(minimum, *runs)`: a file with no backticks in it at all
    # makes that spelling `max(3)`, which raises rather than returning three.
    fence = _FENCE * max([_MINIMUM_FENCE, *(len(run) + 1 for run in _BACKTICKS.findall(contents))])
    return (f"## {path}", "", fence, contents.rstrip("\n"), fence, "")


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


__all__ = [
    "EDIT_MARKER",
    "FUNCTION_MARKER",
    "MISSING_EDIT",
    "MISSING_FUNCTION",
    "MISSING_MARKER",
    "MISSING_NAME",
    "MISSING_PATH",
    "MULTIPLE_BLOCKS",
    "REPLACE_CLOSE",
    "REPLACE_OPEN",
    "SIGNATURE_RESTATEMENT",
    "STRAY_MARKER",
    "UNCLOSED_FENCE",
    "Block",
    "EmptySources",
    "EscapingSourcePath",
    "HeldTestInSources",
    "NoBlock",
    "parse_edit_block",
    "render_whole_function_prompt",
]