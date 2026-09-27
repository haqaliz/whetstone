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

import argparse
import json
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath

from whetstone.bakeoff.journal import Journal
from whetstone.bakeoff.patch import Extracted, extract_patch
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.bakeoff.transcript import Transcribed, Transcript
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.repo import materialise
from whetstone.verify.task import Task

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


class Decision(str, Enum):
    """The pre-committed go/no-go (spec, "Decision"). Exit codes follow `check-probe`'s."""

    GO = "GO"
    NO_GO = "NO-GO"


def decide(classes: Sequence[RolloutClass]) -> Decision:
    """GO iff more than half of the population is `LOCATABLE`. Every class counts in the total.

    An empty population is refused, not decided: "no refusals to classify" is a join bug or the
    wrong candidate, never a result.
    """
    if not classes:
        raise ValueError("the population is empty, so there is nothing to decide over")
    located = sum(1 for klass in classes if klass is RolloutClass.LOCATABLE)
    return Decision.GO if located * 2 > len(classes) else Decision.NO_GO


def checkout_reader(root: Path) -> Reader:
    """A `Reader` over a checkout at `base_commit`. Reads only; refuses to leave `root`.

    The path is resolved before it is read, so a symlink pointing out of the checkout is answered
    as absent rather than followed onto the host.
    """
    base = root.resolve()

    def read(path: str) -> str | None:
        target = (base / path).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            return None
        try:
            return target.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NotText(path) from exc

    return read


def population(rows: Iterable[Rollout], *, candidate: str) -> tuple[tuple[str, str], ...]:
    """The (candidate, task) keys the decision is over: this candidate's `NOT_APPLIED` rollouts."""
    return tuple(
        (row.candidate, row.task_id)
        for row in rows
        if row.candidate == candidate and row.outcome is Outcome.NOT_APPLIED
    )


#: The output document's schema. Bumped on any change to a field's meaning.
SCHEMA = "whetstone-locatability/1"

#: The rule, written into every document so a reader never has to find the spec to know it.
RULE = "GO iff count(LOCATABLE) * 2 > population; every class, UNCLASSIFIED included, counts"

#: Exit codes, `check-probe`'s shape: the decision is the process exit.
_EXIT = {Decision.GO: 0, Decision.NO_GO: 1}
_REFUSED = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Classify one candidate's refused rollouts in a finished run, and exit with the decision.

    Offline: no model, no network. Checkouts are materialised into a temporary directory, read,
    and discarded; the run's evidence is never written to. A refusal writes nothing, because an
    empty or partial document would read as a measurement.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.bakeoff.locatability",
        description=(
            "Ask whether the code a candidate's refused diffs quoted is in the file at the task's "
            "base commit, and exit 0 GO / 1 NO-GO / 2 refused by the pre-committed rule."
        ),
    )
    parser.add_argument("--transcript", required=True, type=Path, help="the run's transcript")
    parser.add_argument("--journal", required=True, type=Path, help="the run's journal")
    parser.add_argument("--candidate", required=True, help="the one candidate to classify")
    parser.add_argument(
        "--tasks",
        action="append",
        default=[],
        type=Path,
        metavar="DIR",
        help="a corpus root, repeatable; a task not offered here is UNCLASSIFIED by name",
    )
    parser.add_argument("--out", required=True, type=Path, help="where the document is written")
    namespace = parser.parse_args(argv)

    for label, path in (("transcript", namespace.transcript), ("journal", namespace.journal)):
        if not Path(path).is_file():
            return _refuse(f"the {label} {str(path)!r} is not a file; nothing was classified")

    rows = [step.rollout for step in Journal(Path(namespace.journal)).replay().values()]
    if not any(row.candidate == namespace.candidate for row in rows):
        return _refuse(
            f"the journal holds no rollout for {namespace.candidate!r}; a misspelt candidate "
            "must not read as a candidate with nothing to classify"
        )
    keys = population(rows, candidate=namespace.candidate)
    if not keys:
        return _refuse(
            f"{namespace.candidate!r} has no NOT_APPLIED rollout, so there is no population "
            "to decide over"
        )

    wanted = {task_id for _, task_id in keys}
    try:
        tasks = {
            task.task_id: task
            for root in namespace.tasks
            for task in load_tasks(Path(root))
            if task.task_id in wanted
        }
    except (OSError, ValueError) as exc:
        return _refuse(f"a corpus root could not be loaded: {exc}")

    records = Transcript(Path(namespace.transcript)).replay()
    with tempfile.TemporaryDirectory(prefix="whetstone-locatability-") as scratch:
        checkouts: dict[str, Path | str] = {}
        classified = {
            key: _classify_key(key, records, tasks, checkouts, Path(scratch)) for key in keys
        }

    decision = decide([one.klass for one in classified.values()])
    document = _document(namespace, keys, classified, decision)
    out = Path(namespace.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{namespace.candidate}: {decision.value} over {len(keys)} ({document['counts']})")
    print(f"wrote {out}")
    return _EXIT[decision]


def _classify_key(
    key: tuple[str, str],
    records: Mapping[tuple[str, str], Transcribed],
    tasks: Mapping[str, Task],
    checkouts: dict[str, Path | str],
    scratch: Path,
) -> Classified:
    """One key's answer, or `UNCLASSIFIED` with the reason the question could not be asked."""
    record = records.get(key)
    if record is None:
        return _unclassified("the transcript holds no graded record for this rollout")
    task = tasks.get(key[1])
    if task is None:
        return _unclassified("the task was not offered under any --tasks root")
    checkout = checkouts.get(task.task_id)
    if checkout is None:
        checkout = _materialised(task, scratch / task.task_id)
        checkouts[task.task_id] = checkout
    if isinstance(checkout, str):
        return _unclassified(checkout)
    extraction = extract_patch(record.completion)
    diff = extraction.diff if isinstance(extraction, Extracted) else None
    return classify_rollout(diff, checkout_reader(checkout))


def _materialised(task: Task, destination: Path) -> Path | str:
    """The task's tree at `base_commit`, or the sentence saying why there is none."""
    try:
        materialise(task, destination)
    except (OSError, RuntimeError, ValueError) as exc:
        return f"the task's checkout could not be materialised: {exc}"
    return destination


def _unclassified(detail: str) -> Classified:
    return Classified(RolloutClass.UNCLASSIFIED, False, (), detail)


def _document(
    namespace: argparse.Namespace,
    keys: Sequence[tuple[str, str]],
    classified: Mapping[tuple[str, str], Classified],
    decision: Decision,
) -> dict[str, object]:
    counts = Counter(one.klass.value for one in classified.values())
    return {
        "schema": SCHEMA,
        "candidate": namespace.candidate,
        "transcript": str(namespace.transcript),
        "journal": str(namespace.journal),
        "rule": RULE,
        "population": len(keys),
        "counts": dict(sorted(counts.items())),
        "drift": sum(1 for one in classified.values() if one.drift),
        "decision": decision.value,
        "rollouts": [
            {
                "task_id": key[1],
                "class": classified[key].klass.value,
                "drift": classified[key].drift,
                "hunks": [klass.value for klass in classified[key].hunks],
                "detail": classified[key].detail,
            }
            for key in sorted(keys)
        ],
    }


def _refuse(reason: str) -> int:
    print(f"whetstone locatability: {reason}", file=sys.stderr)
    return _REFUSED


__all__ = [
    "Classified",
    "Decision",
    "Hunk",
    "HunkClass",
    "NotText",
    "Reader",
    "RolloutClass",
    "checkout_reader",
    "classify_hunk",
    "classify_rollout",
    "decide",
    "main",
    "population",
    "walk",
]


if __name__ == "__main__":
    sys.exit(main())
