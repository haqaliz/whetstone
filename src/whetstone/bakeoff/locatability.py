"""Stored refusals in; whether the code each one quoted is in the file. No model consulted.

`attribution.py` says *that* git refused a rollout's diff; `autopsy.py` names the diff's shape.
Neither answers the question a change of edit representation turns on: **when the model quoted
existing code, was that code there?** A representation without line numbers or hunk counts
(search/replace blocks) removes the arithmetic a unified diff demands — but it still requires the
model to quote the file exactly. If the quoted text is *misplaced*, a new representation can
convert the refusal; if it is *invented*, the refusal only moves. This module measures which,
offline, over a finished run's evidence, so the decision to build the representation is made on
a count rather than on a hunch (`docs/planning/patch-representation/prd.md` § 4.2).

**The rules are fixed in the spec, before the run.** Every classification rule lives in
`docs/planning/patch-representation/locatability-finding/spec.md` and was written before this
module saw a real transcript. The go/no-go it feeds is a threshold, and a threshold chosen after
the number is known is not a rule.

**The walk is lenient on purpose, and only in the walk.** git refuses a hunk whose header counts
its body does not satisfy; this module ignores the counts, because the question is what the model
*quoted*, not whether it counted. It reads a bare empty line as an empty context line, because
that is the commonest way a model breaks the prefix grammar. Nothing else is forgiven: location
is exact, byte for byte, and whitespace drift is reported beside the partition, never folded into
it.

Stdlib only. No model, no network, and nothing under `verify/` or `tasks/` may import this.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath

#: The prefixes the walk recognises inside a hunk body.
_CONTEXT = " "
_REMOVED = "-"
_ADDED = "+"
_NO_NEWLINE = "\\"

_OLD_FILE = "--- "
_NEW_FILE = "+++ "
_HUNK = "@@"
_DEV_NULL = "/dev/null"


@dataclass(frozen=True)
class Hunk:
    """One hunk the model wrote, reduced to what it claimed the file contained."""

    #: The file the hunk names, relative to the repository root as the model wrote it.
    path: str

    #: The hunk's context and removed lines, in order, without their prefixes, joined by `\n`.
    #: Empty for a pure insertion, which quotes nothing.
    old_side: str


def walk(diff: str) -> tuple[Hunk, ...]:
    """Every hunk in `diff`, in order, by the spec's lenient rules.

    Counts in hunk headers are ignored. Inside a hunk a line is context, removed, added, a
    `\\ No newline` marker (skipped), or empty (an empty context line); any other line ends it.
    """
    lines = diff.splitlines()
    hunks: list[Hunk] = []
    path: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith(_OLD_FILE) and index + 1 < len(lines):
            following = lines[index + 1]
            if following.startswith(_NEW_FILE):
                path = _path_of(line[len(_OLD_FILE) :], following[len(_NEW_FILE) :])
                index += 2
                continue
        if line.startswith(_HUNK) and path is not None:
            old_side, index = _body(lines, index + 1)
            hunks.append(Hunk(path=path, old_side=old_side))
            continue
        index += 1
    return tuple(hunks)


def _path_of(old: str, new: str) -> str:
    """The new side with one `b/` stripped, or the old side with `a/` if the new is `/dev/null`."""
    new = new.split("\t", 1)[0].strip()
    if new != _DEV_NULL:
        return new.removeprefix("b/")
    return old.split("\t", 1)[0].strip().removeprefix("a/")


def _body(lines: list[str], index: int) -> tuple[str, int]:
    """Walk one hunk body from `index`; return its old side and the index where it stopped."""
    old: list[str] = []
    # Empty lines are held back until a later body line proves they were inside the hunk; a run
    # of them that ends the hunk is not quoted code (spec: "only when a later line follows").
    pending = 0
    end = index
    while index < len(lines):
        line = lines[index]
        if line == "":
            pending += 1
            index += 1
            continue
        if line.startswith((_CONTEXT, _REMOVED)) and not line.startswith(_OLD_FILE):
            old.extend([""] * pending)
            old.append(line[1:])
        elif (line.startswith(_ADDED) and not line.startswith(_NEW_FILE)) or line.startswith(
            _NO_NEWLINE
        ):
            old.extend([""] * pending)
        else:
            break
        pending = 0
        index += 1
        end = index
    return "\n".join(old), end


class NotText(ValueError):
    """A file the classifier was asked to read is not valid UTF-8.

    Raised by a `Reader` rather than answered as absent, because "the file is not there" and "the
    file could not be read as text" are different facts, and only the first is `NO_FILE`.
    """


#: Path -> the file's text at `base_commit`, or `None` if it does not exist there. Raises
#: `NotText` for a file that is not UTF-8. Injected, so the pure layer never touches disk.
Reader = Callable[[str], "str | None"]


class HunkClass(str, Enum):
    """What one hunk's quote was, against the file it named."""

    #: The path is absent at `base_commit`, absolute, or climbs out with `..`.
    NO_FILE = "NO_FILE"
    #: A pure insertion: it quotes nothing, so it can be neither located nor invented.
    EMPTY = "EMPTY"
    #: The quote occurs nowhere in the file.
    INVENTED = "INVENTED"
    #: The quote occurs more than once, so a representation keyed on it could not choose.
    AMBIGUOUS = "AMBIGUOUS"
    #: The quote occurs exactly once.
    LOCATABLE = "LOCATABLE"


class RolloutClass(str, Enum):
    """One refused rollout's class: the worst of its hunks. Declared worst first."""

    #: The question could not be asked — no task, no checkout, no graded record, or a file that is
    #: not text. Kept in the denominator by name, never folded into a neighbour.
    UNCLASSIFIED = "UNCLASSIFIED"
    NO_FILE = "NO_FILE"
    #: No diff was located, or no hunk quoted anything.
    UNREADABLE = "UNREADABLE"
    INVENTED = "INVENTED"
    AMBIGUOUS = "AMBIGUOUS"
    LOCATABLE = "LOCATABLE"


#: Worst first: the order a rollout's class is chosen in (spec, "Per-rollout class").
_SEVERITY = tuple(RolloutClass)


@dataclass(frozen=True)
class Classified:
    """One rollout's answer: its class, its drift tag, and the per-hunk classes behind them."""

    klass: RolloutClass
    #: Every invented hunk would be found exactly once if whitespace were forgiven. Reported beside
    #: the class and never moving it: the converter this finding decides on forgives nothing.
    drift: bool
    hunks: tuple[HunkClass, ...]
    #: Why, when the class alone does not say — the unreadable file, for `UNCLASSIFIED`.
    detail: str = ""


def classify_hunk(hunk: Hunk, read: Reader) -> HunkClass:
    """Class one hunk by the spec's line-aligned, overlap-counting rule."""
    if not hunk.old_side:
        return HunkClass.EMPTY
    if _escapes(hunk.path):
        return HunkClass.NO_FILE
    text = read(hunk.path)
    if text is None:
        return HunkClass.NO_FILE
    found = _occurrences(hunk.old_side.split("\n"), text.split("\n"))
    if found == 0:
        return HunkClass.INVENTED
    return HunkClass.AMBIGUOUS if found > 1 else HunkClass.LOCATABLE


def classify_rollout(diff: str | None, read: Reader) -> Classified:
    """Class one refused rollout from the diff the extractor located in it, or `None` if none."""
    hunks = walk(diff) if diff is not None else ()
    try:
        classes = tuple(classify_hunk(hunk, read) for hunk in hunks)
    except NotText as exc:
        return Classified(RolloutClass.UNCLASSIFIED, False, (), f"not UTF-8: {exc}")

    quoted = [klass for klass in classes if klass is not HunkClass.EMPTY]
    if not quoted:
        return Classified(RolloutClass.UNREADABLE, False, classes)
    klass = min((RolloutClass(one.value) for one in quoted), key=_SEVERITY.index)
    invented = [h for h, c in zip(hunks, classes, strict=True) if c is HunkClass.INVENTED]
    drift = klass is RolloutClass.INVENTED and all(_drifted(hunk, read) for hunk in invented)
    return Classified(klass, drift, classes)


def _escapes(path: str) -> bool:
    """Absolute, or climbing out of the repository. Refused before any reader sees it."""
    pure = PurePosixPath(path)
    return pure.is_absolute() or ".." in pure.parts


def _occurrences(needle: list[str], haystack: list[str]) -> int:
    """Start lines at which `needle` equals `haystack`'s lines in order — overlaps counted."""
    width = len(needle)
    return sum(
        1 for start in range(len(haystack) - width + 1) if haystack[start : start + width] == needle
    )


def _drifted(hunk: Hunk, read: Reader) -> bool:
    """Would this invented quote occur exactly once with whitespace forgiven?"""
    text = read(hunk.path)
    if text is None:
        return False
    return _occurrences(_folded(hunk.old_side), _folded(text)) == 1


def _folded(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.split("\n")]


__all__ = [
    "Classified",
    "Hunk",
    "HunkClass",
    "NotText",
    "Reader",
    "RolloutClass",
    "classify_hunk",
    "classify_rollout",
    "walk",
]
