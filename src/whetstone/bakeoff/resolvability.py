"""A finished whole-function measurement run's completions in; whether the pinned base could
resolve a whole-function edit.

`measure.py` spends the run — one greedy completion per pinned task under the whole-function
prompt, graded by nothing — and this module asks what the finding turns on: **when the base
wrote an `EDIT`/`FUNCTION` block, did it name a real module-level function and write a body
that could replace its body?** The format exists to remove the quoting burden that killed
unified diffs and the range arithmetic the numbered listing demands; this instrument measures
whether the base can *resolve* an edit at all — name the file, name the function, write a
usable body — over a finished run's evidence, so the go/no-go for building the contract is a
count rather than a hunch (`docs/planning/whole-function-edit-finding/measurement-run/spec.md`).

**The rules are fixed in the spec, before the run.** Every class, the worst-first order and
the strict-majority inequality were written before this module saw a real transcript. The
classes: `UNCLASSIFIED` (evidence unreachable — no graded transcript record, a task nobody
offered, a `prompt_sha256` the manifest did not record or that disagrees with it, an
unmaterialisable checkout, a file that is not UTF-8, the `NO_ORACLE` members; stays in the
denominator) → `MALFORMED` (the format's grammar violated — `whole_function.parse_edit_block`
refused the completion with its reason, or the body fails the wrapped parse with
`IndentationError`) → `NO_FILE` (the `EDIT` path is not a shown source file, or is absent from
the checkout at `base_commit`) → `AMBIGUOUS` (the name resolves to more than one module-level
function) → `UNKNOWN_FUNCTION` (the name is not a module-level function) → `NOT_PARSEABLE`
(the body fails the wrapped parse with anything but an `IndentationError`) → `RESOLVABLE`
(path shown and present, name unique and module-level, body passes the wrapped parse). Worst
first, in the enum's declaration order.

**The wrapped parse is the spec's gate, and it never repairs.** `ast.parse("def
__whetstone_synthetic():\\n" + body)` — the body wrapped in a synthetic `def` at column 0. A
body at column 0 — the indentation the format requires, violated — raises `IndentationError`,
which is `MALFORMED`; any other parse failure is `NOT_PARSEABLE` (spec R1's class rule).
Never dedented, never repaired: the body the base wrote is the body the harness would splice,
and a gate that fixed it up would measure a repair the harness never performs.

**Two sub-counts, reported beside the partition and never moving a class.** (a)
*splice-in-context*: the file at `base_commit` re-parsed with the body spliced over the
resolved extent (decorators and signature kept from the original, the body replaced) — the
offline proxy for "parses, and the file it lands in still parses", computed only for
`RESOLVABLE` rollouts. (b) *outside-shown-set*: completions whose `EDIT` path is real at
`base_commit` but outside the oracle sources the run showed — held-test paths included. Both
are counted beside the partition; `decide` sees only the classes, so the decision is blind to
them by construction.

**The shown set is re-derived the way the run derived it.** `bakeoff.sources.oracle_sources`
is the run's own derivation — the non-test paths `provenance.commit` touched, read at
`base_commit`. This module reads the same commit from the same donor, filters test paths by
the same rule (`tasks.donor.is_test_path`), and reads the survivors from the checkout this
instrument already materialised. The oracle budget is deliberately not consulted: it decides
*whether* the run posed the task, which the transcript record's existence already encodes — a
task whose oracle did not fit was never posed, and a record that disagrees with the manifest
is `UNCLASSIFIED` before any shown set matters.

**The population is the manifest's, pinned by identity.** The manifest (`whetstone-measure/1`)
is the source of truth; the instrument cross-checks it three ways before classifying: the
task list equals `measure._PINNED_POPULATION` by identity; the stratum and held-out
documents, through their own fail-closed loaders, subtract to the same list; and the
documents' digests match the digests the manifest recorded. Any disagreement is a refusal
(exit 2) — a changed pre-committed input is a halt, never a rerun. A transcript record
whose `prompt_sha256` disagrees with the manifest's recorded digest is not this run's
evidence and is `UNCLASSIFIED`, never classified.

**The decision is the process exit.** `GO iff count(RESOLVABLE) * 2 > population` — the
strict-majority inequality — as 0 GO, 1 NO-GO, 2 refused; a refusal prints its named reason to
stderr and writes nothing, because an empty or partial document would read as a measurement.

Stdlib only. No model, no network, and nothing under `verify/` or `tasks/` is imported here:
task manifests are read by a minimal fail-closed reader, and checkouts are materialised with
git itself, so importing this module never executes a reward-path import (the
`whole_function.py` hygiene shape).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from whetstone.bakeoff import stratum as stratum_module
from whetstone.bakeoff.locatability import NotText, Reader, checkout_reader
from whetstone.bakeoff.measure import _PINNED_POPULATION, MANIFEST_SCHEMA
from whetstone.bakeoff.transcript import Transcript
from whetstone.bakeoff.whole_function import Block, NoBlock, parse_edit_block
from whetstone.loop import heldout as heldout_module

#: The output document's schema. Bumped on any change to a field's meaning.
SCHEMA = "whetstone-resolvability/1"

#: The rule, written into every document so a reader never has to find the spec to know it
#: (spec.md, "Decision" — the locatability output-schema pattern).
RULE = "GO iff count(RESOLVABLE) * 2 > population"

#: Exit codes, `check-probe`'s shape: the decision is the process exit.
_EXIT = {"GO": 0, "NO-GO": 1}
_REFUSED = 2

#: The wrapped-parse gate's synthetic def (spec R1): the body is parsed as the body of a
#: module-level function, which is exactly the position the harness would splice it into.
_WRAP = "def __whetstone_synthetic():\n"

#: Directory names that make everything below them test code — `tasks.donor.is_test_path`'s
#: rule, kept here by identity because this module must not import `tasks/`.
_TEST_DIRECTORIES = frozenset({"test", "tests"})

#: Long enough for a large clone on a slow disk, short enough that a wedged git does not hang
#: the instrument forever — `verify.repo`'s own bound.
_GIT_TIMEOUT = 300.0


class RolloutClass(str, Enum):
    """One completion's class, in the spec's worst-first order.

    The format is one block per rollout, so the class is the block's: the ladder is decided
    for the whole completion, `UNCLASSIFIED` and `MALFORMED` first — the first by evidence the
    instrument could not reach, the second by a parser that refuses the whole text — then the
    path, the name and the body in the spec's order.
    """

    #: The question could not be asked — no graded record, no task, a prompt digest that is
    #: not this run's, no checkout, or a file that is not text. Kept in the denominator by
    #: name, never folded into a neighbour.
    UNCLASSIFIED = "UNCLASSIFIED"
    #: The format's grammar is violated: `parse_edit_block` refused the completion, or the
    #: body fails the wrapped parse with `IndentationError`.
    MALFORMED = "MALFORMED"
    #: The `EDIT` path is not a shown source file, or is absent from the checkout at
    #: `base_commit`.
    NO_FILE = "NO_FILE"
    #: The `FUNCTION` name resolves to more than one module-level function in the named file.
    AMBIGUOUS = "AMBIGUOUS"
    #: The name is not a module-level function in the named file.
    UNKNOWN_FUNCTION = "UNKNOWN_FUNCTION"
    #: The body fails the wrapped parse with anything but an `IndentationError`.
    NOT_PARSEABLE = "NOT_PARSEABLE"
    #: Path shown and present, name unique and module-level, body passes the wrapped parse.
    RESOLVABLE = "RESOLVABLE"


#: Worst first: the order a rollout's class is chosen in (spec, "Classes, worst-first").
_SEVERITY = tuple(RolloutClass)


@dataclass(frozen=True)
class Classified:
    """One rollout's answer: its class and the two sub-count flags.

    `outside_shown_set` and `splice_in_context` are reported beside the class and never move
    it (spec, "Sub-counts"): `decide` sees only the classes.
    """

    klass: RolloutClass
    #: The `EDIT` path is real at `base_commit` but outside the shown set — sub-count (b),
    #: held-test paths included.
    outside_shown_set: bool
    #: For a `RESOLVABLE` rollout: the file still parses with the body spliced over the
    #: resolved extent — sub-count (a). False for every other class.
    splice_in_context: bool
    #: Why, when the class alone does not say — the parser's reason, the defect, or the
    #: unreachable evidence.
    detail: str = ""


@dataclass(frozen=True)
class Manifest:
    """The fields of the run manifest the instrument reads, validated by `_manifest_of`."""

    run_id: str
    candidate: str
    revision: str
    tasks: tuple[str, ...]
    prompt_sha256: Mapping[str, str]
    stratum_document_digest: str
    heldout_document_digest: str


@dataclass(frozen=True)
class _Task:
    """The fields of a task manifest the instrument reads, and nothing else.

    The contract's own loader (`verify.task.load_task`) validates the whole manifest; this
    instrument reads only what it uses — `task_id`, `repo_url`, `base_commit` and the
    provenance the shown-set derivation reads — and reads them fail-closed, so a manifest
    that half-parsed would never materialise a checkout the operator did not declare.
    """

    task_id: str
    repo_url: str
    base_commit: str
    provenance: Mapping[str, str]


@dataclass(frozen=True)
class _Extent:
    """A resolved function's extent at `base_commit`: decorators and signature kept from the
    original, the body replaced (spec, "Format" — the body is the only replacement surface).
    """

    #: The first decorator's line, or the def line, 1-based.
    first: int
    #: The first body line, 1-based — the signature ends the line before it.
    body_start: int
    #: The function's last line (`end_lineno`), 1-based, inclusive.
    end: int


def classify_rollout(
    completion: str, read: Reader, shown: frozenset[str] = frozenset()
) -> Classified:
    """Class one completion by the spec's worst-first rule, against `read`'s files.

    `completion` is the transcript's graded record for one (candidate, task); `read` is a
    `locatability.checkout_reader` over the task's tree at `base_commit` (or an in-memory
    stand-in in tests); `shown` is the oracle sources the run showed, whose membership feeds
    class `NO_FILE` and sub-count (b).

    A completion `parse_edit_block` refuses is `MALFORMED` with the parser's reason. A named
    file that is not UTF-8 leaves the whole rollout `UNCLASSIFIED` — "the file is not there"
    and "the file could not be read as text" are different facts, and only the first is
    `NO_FILE` (the `locatability.NotText` discipline). Otherwise the rollout takes the worst
    of the classes its block earns: a `NO_FILE` path, an `AMBIGUOUS`/`UNKNOWN_FUNCTION` name,
    or a `MALFORMED`/`NOT_PARSEABLE` body, in the ladder's order.
    """
    parsed = parse_edit_block(completion)
    if isinstance(parsed, NoBlock):
        return Classified(RolloutClass.MALFORMED, False, False, parsed.reason)
    klass, outside, splice, detail = _classify_block(parsed, read, shown)
    return Classified(klass, outside, splice, detail)


def _classify_block(
    block: Block, read: Reader, shown: frozenset[str]
) -> tuple[RolloutClass, bool, bool, str]:
    """One block's class, outside-shown-set flag, splice flag and detail — in that order.

    The classes the block earns are collected and the worst taken, because the ladder is a
    total order: a completion whose body fails the wrapped parse with `IndentationError` is
    `MALFORMED` even when its path is also bad, exactly as the ladder places `MALFORMED`
    above `NO_FILE`. The outside-shown-set flag is set only when the path is real at
    `base_commit` — a completion naming a file that is not there is `NO_FILE`, not scope
    adjacency. The splice is computed only for a `RESOLVABLE` block.
    """
    outside = False
    text: str | None = None
    extent: _Extent | None = None
    defects: list[tuple[RolloutClass, str]] = []
    if _escapes(block.path):
        defects.append((RolloutClass.NO_FILE, "absolute or climbs out of the repository"))
    else:
        try:
            text = read(block.path)
        except NotText as exc:
            return (RolloutClass.UNCLASSIFIED, False, False, f"not UTF-8: {exc}")
        if text is None:
            defects.append((RolloutClass.NO_FILE, "no such file at base_commit"))
        elif block.path not in shown:
            outside = True
            defects.append((RolloutClass.NO_FILE, "not a shown source file"))
        else:
            outcome = _resolve(block.name, text)
            if isinstance(outcome, _Extent):
                extent = outcome
            else:
                defects.append(outcome)
    wrapped = _wrapped(block.body)
    if wrapped is not None:
        defects.append(wrapped)
    if not defects:
        assert text is not None and extent is not None
        return (
            RolloutClass.RESOLVABLE,
            outside,
            _splice_parses(block.body, extent, text),
            "",
        )
    worst = min((klass for klass, _detail in defects), key=_SEVERITY.index)
    detail = next((reason for klass, reason in defects if klass is worst), "")
    return (worst, outside, False, detail)


def _resolve(name: str, text: str) -> _Extent | tuple[RolloutClass, str]:
    """The module-level function `name` names in `text`, or the class and reason it does not.

    Only direct children of the module body count — a `def` inside a class or an `if` is a
    method or a nested definition, never the harness's replacement surface. The name is
    matched exactly, never by substring. A file that does not parse has no module-level
    functions, so any name is `UNKNOWN_FUNCTION` there.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return (
            RolloutClass.UNKNOWN_FUNCTION,
            f"the named file does not parse, so {name!r} is not a module-level function in "
            f"it: {exc}",
        )
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if len(matches) > 1:
        return (
            RolloutClass.AMBIGUOUS,
            f"{name!r} names {len(matches)} module-level functions in the file",
        )
    if not matches:
        return (
            RolloutClass.UNKNOWN_FUNCTION,
            f"{name!r} is not a module-level function in the file",
        )
    node = matches[0]
    return _Extent(
        first=node.decorator_list[0].lineno if node.decorator_list else node.lineno,
        body_start=node.body[0].lineno,
        end=node.end_lineno if node.end_lineno is not None else node.lineno,
    )


def _wrapped(body: str) -> tuple[RolloutClass, str] | None:
    """The spec's wrapped-parse gate (R1's class rule), or `None` when the body parses.

    `IndentationError` — a body at column 0, or an empty one — is `MALFORMED`, the format's
    grammar; any other parse failure is `NOT_PARSEABLE`. The order matters: `IndentationError`
    is a `SyntaxError` subclass, and the class rule is decided by which of the two it is.
    """
    try:
        ast.parse(_WRAP + body)
    except IndentationError as exc:
        return (
            RolloutClass.MALFORMED,
            f"the body fails the wrapped parse with IndentationError: {exc}",
        )
    except SyntaxError as exc:
        return (RolloutClass.NOT_PARSEABLE, f"the body fails the wrapped parse: {exc}")
    return None


def _splice_parses(body: str, extent: _Extent, text: str) -> bool:
    """Sub-count (a): the file still parses with the body spliced over the resolved extent.

    The splice keeps the decorators and the signature verbatim — the harness keeps them too —
    and replaces the body region with the completion's body, byte-exactly. The body's own
    lines carry the function's indentation, so they land in the file at the columns the wrap
    just vouched for; the spliced file is parsed whole, and any failure — the sharp proxy —
    counts against the sub-count, never the class.
    """
    lines = _lines(text)
    replacement = _lines(body)
    spliced = (
        lines[: extent.first - 1]
        + lines[extent.first - 1 : extent.body_start - 1]
        + replacement
        + lines[extent.end :]
    )
    return _parses("\n".join(spliced))


def _parses(text: str) -> bool:
    """`ast.parse` with any `SyntaxError` folded to False — syntax only, never semantics."""
    try:
        ast.parse(text)
    except SyntaxError:
        return False
    return True


def _lines(text: str) -> list[str]:
    """The text's real lines: split on `\n`, the phantom element after a final newline
    dropped, interior empty lines kept — the `addressability._lines` rule.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def _escapes(path: str) -> bool:
    """Absolute, or climbing out of the repository with `..`. Refused before any read."""
    pure = PurePosixPath(path)
    return pure.is_absolute() or ".." in pure.parts


def decide(classes: Sequence[RolloutClass]) -> Decision:
    """GO iff more than half of the population is `RESOLVABLE`. Every class counts in the total.

    An empty population is refused, not decided: "nothing to classify" is a join bug or the
    wrong manifest, never a result.
    """
    if not classes:
        raise ValueError("the population is empty, so there is nothing to decide over")
    resolvable = sum(1 for klass in classes if klass is RolloutClass.RESOLVABLE)
    return Decision.GO if resolvable * 2 > len(classes) else Decision.NO_GO


class Decision(str, Enum):
    """The pre-committed go/no-go (spec, "Decision"). Exit codes follow `check-probe`'s."""

    GO = "GO"
    NO_GO = "NO-GO"


#: The named refusals the CLI turns into exit 2 rather than a traceback: the document
#: loaders' own errors first, then the instrument's — `ValueError` closes the tuple
#: (the `measure.REFUSALS` shape).
_REFUSALS: tuple[type[Exception], ...] = (
    stratum_module.StratumSchemaError,
    stratum_module.StratumDigestMismatch,
    stratum_module.EmptyStratum,
    stratum_module.UnknownStratumId,
    heldout_module.HeldoutSchemaError,
    heldout_module.HeldoutDigestMismatch,
    heldout_module.EmptyHeldout,
    heldout_module.UnknownHeldoutId,
    OSError,
    ValueError,
)


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface, built separately so tests can exercise it without running anything."""
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.bakeoff.resolvability",
        description=(
            "Classify a finished whole-function measurement run's completions against the "
            "files each task showed at base_commit, and exit 0 GO / 1 NO-GO / 2 refused by "
            "the pre-committed rule: GO iff count(RESOLVABLE) * 2 > population."
        ),
    )
    parser.add_argument("--manifest", required=True, type=Path, help="the run's manifest")
    parser.add_argument("--transcript", required=True, type=Path, help="the run's transcript")
    parser.add_argument(
        "--tasks",
        action="append",
        default=[],
        type=Path,
        metavar="DIR",
        help="a corpus root, repeatable; a task not offered here is UNCLASSIFIED by name",
    )
    parser.add_argument(
        "--stratum",
        required=True,
        type=Path,
        help="the committed stratum document, read through its own fail-closed loader",
    )
    parser.add_argument(
        "--heldout",
        required=True,
        type=Path,
        help="the committed held-out document, read through its own fail-closed loader",
    )
    parser.add_argument("--out", required=True, type=Path, help="where the document is written")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Classify one measurement run's completions, and exit with the decision.

    Offline: no model, no network. Checkouts are materialised into a temporary directory,
    read, and discarded; the run's evidence is never written to. A refusal writes nothing,
    because an empty or partial document would read as a measurement.
    """
    parser = build_parser()
    namespace = parser.parse_args(argv)

    if not Path(namespace.out).is_absolute():
        return _refuse(
            f"--out must be an absolute path, got {str(namespace.out)!r}. A relative output "
            "path resolves against wherever the process happened to be started, so the same "
            "command from two shells writes its document to two places — the runbook's known "
            "pitfall, refused here rather than recorded"
        )

    for label, path in (("manifest", namespace.manifest), ("transcript", namespace.transcript)):
        if not Path(path).is_file():
            return _refuse(f"the {label} {str(path)!r} is not a file; nothing was classified")

    try:
        manifest = _read_manifest(Path(namespace.manifest))
        _read_documents(namespace, manifest)
        tasks = _read_corpus(namespace, manifest)
        records = Transcript(Path(namespace.transcript)).replay()
    except _REFUSALS as refusal:
        return _refuse(str(refusal))

    with tempfile.TemporaryDirectory(prefix="whetstone-resolvability-") as scratch:
        checkouts: dict[str, Path | str] = {}
        listings: dict[str, frozenset[str]] = {}
        classified = {
            task_id: _classify_key(
                task_id, manifest, records, tasks, checkouts, listings, Path(scratch)
            )
            for task_id in manifest.tasks
        }

    decision = decide([one.klass for one in classified.values()])
    document = _document(namespace, manifest, classified, decision)
    out = Path(namespace.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{manifest.candidate}: {decision.value} over {len(classified)} ({document['counts']})")
    print(f"wrote {out}")
    return _EXIT[decision.value]


def _read_manifest(path: Path) -> Manifest:
    """Read and validate the run manifest, or refuse it by name.

    Fail-closed like the document loaders: a manifest that half-parsed would let the
    instrument classify a population its own fields do not support. The task list is
    checked against the spec's pinned population by identity — a run whose task set
    differs is a different experiment, refused before anything is classified.
    """
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"the manifest at {str(path)!r} could not be read: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("the manifest must be a JSON object")
    if raw.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(
            f"the manifest declares schema {raw.get('schema')!r}, but this module reads "
            f"{MANIFEST_SCHEMA!r}; an old-schema manifest fails decode rather than defaulting"
        )

    run_id = raw.get("run_id")
    if not isinstance(run_id, str):
        raise ValueError("the manifest carries no run_id")
    candidate = raw.get("candidate")
    if (
        not isinstance(candidate, dict)
        or not isinstance(candidate.get("repo_id"), str)
        or not isinstance(candidate.get("revision"), str)
    ):
        raise ValueError("the manifest carries no candidate with a repo_id and a revision")
    tasks = raw.get("tasks")
    if not isinstance(tasks, list) or not all(isinstance(one, str) for one in tasks):
        raise ValueError("the manifest's tasks must be a list of task ids")
    prompts = raw.get("prompt_sha256")
    if not isinstance(prompts, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in prompts.items()
    ):
        raise ValueError("the manifest's prompt_sha256 must map task ids to digests")
    for label in ("stratum_document_digest", "heldout_document_digest"):
        if not isinstance(raw.get(label), str):
            raise ValueError(f"the manifest carries no {label}")

    manifest = Manifest(
        run_id=run_id,
        candidate=str(candidate["repo_id"]),
        revision=str(candidate["revision"]),
        tasks=tuple(tasks),
        prompt_sha256=prompts,
        stratum_document_digest=str(raw["stratum_document_digest"]),
        heldout_document_digest=str(raw["heldout_document_digest"]),
    )
    if not manifest.tasks:
        raise ValueError(
            "the manifest records an empty task list, so there is no population to decide "
            "over; a run of no tasks is a usage error, never a result"
        )
    if manifest.tasks != _PINNED_POPULATION:
        raise ValueError(
            f"the manifest's task list differs from the spec's pinned {len(_PINNED_POPULATION)} "
            "tasks (spec.md, \"Population\"). A run whose task set differs from the pinned "
            "list is a different experiment, and a changed pre-committed input is a halt, "
            "never a rerun"
        )
    return manifest


def _read_documents(namespace: argparse.Namespace, manifest: Manifest) -> None:
    """Read the stratum and held-out documents through their own loaders, and cross-check.

    The loaders refuse an unknown schema, a drifted rule, a broken document digest or a
    hand-edited payload by name. The membership subtraction must equal the manifest's task
    list — the same rule the driver ran under — and the documents' own digests must match
    the digests the manifest recorded, so pointing the instrument at documents the run did
    not consume is refused rather than quietly re-derived.
    """
    stratum = stratum_module.read_document(Path(namespace.stratum))
    heldout = heldout_module.read_document(Path(namespace.heldout))
    derived = tuple(sorted(set(stratum.membership) - set(heldout.membership)))
    if derived != manifest.tasks:
        raise ValueError(
            f"the committed documents subtract to {len(derived)} tasks, not the manifest's "
            f"{len(manifest.tasks)}. A manifest and a document set that disagree are a "
            "different experiment, and a changed pre-committed input is a halt, never a rerun"
        )
    if _document_digest(Path(namespace.stratum)) != manifest.stratum_document_digest or (
        _document_digest(Path(namespace.heldout)) != manifest.heldout_document_digest
    ):
        raise ValueError(
            "a committed document's digest does not match the digest the manifest recorded; "
            "the instrument was pointed at documents the run did not consume"
        )


def _document_digest(path: Path) -> str:
    """The document's own `document_digest` field, from the file the loader just vouched for."""
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    return str(raw["document_digest"])


def _read_corpus(namespace: argparse.Namespace, manifest: Manifest) -> dict[str, _Task]:
    """The pinned tasks, read from the declared corpus roots — nothing else is wanted.

    A root that cannot be read is refused by name; a task the corpus does not carry is
    left to the per-rollout `UNCLASSIFIED` — a missing task document is evidence
    unreachable, never a refusal of the whole run. Nothing is skipped inside a root, the
    `load_task_directory` discipline: a stray entry fails the invocation loudly, because a
    task quietly dropped is a denominator nobody chose.
    """
    wanted = set(manifest.tasks)
    try:
        loaded: dict[str, _Task] = {}
        for root in namespace.tasks:
            entries = sorted(Path(root).iterdir())
            if not entries:
                raise ValueError(
                    f"task directory {str(root)!r} contains no task manifests; an empty set "
                    "of tasks is a malformed invocation, not a verdict"
                )
            for entry in entries:
                if not entry.is_file():
                    raise ValueError(
                        f"task directory {str(root)!r} contains {entry.name!r}, which is not "
                        "a task manifest; nothing is skipped, because a skipped task is a "
                        "missing denominator"
                    )
                task = _task_of(entry)
                if task.task_id in wanted:
                    loaded[task.task_id] = task
        return loaded
    except (OSError, ValueError) as exc:
        raise ValueError(f"a corpus root could not be loaded: {exc}") from exc


def _task_of(path: Path) -> _Task:
    """The minimal fail-closed read of a task manifest the instrument needs.

    `verify.task.load_task` is the contract's own loader; this instrument reads only the
    fields it uses, and reads them fail-closed — a manifest that half-parsed would let the
    instrument materialise a checkout the operator never declared. Reading the whole
    contract here would import `verify`/`tasks` onto the measurement side, which the
    hygiene guard forbids.
    """
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"task manifest {str(path)!r} could not be read: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"task manifest {str(path)!r} must contain a JSON object")
    task_id = raw.get("task_id")
    repo_url = raw.get("repo_url")
    base_commit = raw.get("base_commit")
    if not (
        isinstance(task_id, str)
        and isinstance(repo_url, str)
        and isinstance(base_commit, str)
    ):
        raise ValueError(
            f"task manifest {str(path)!r} must carry string task_id, repo_url and base_commit"
        )
    values = raw.get("provenance")
    if not isinstance(values, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in values.items()
    ):
        raise ValueError(
            f"task manifest {str(path)!r} must carry a provenance mapping of strings"
        )
    provenance: Mapping[str, str] = {str(key): str(value) for key, value in values.items()}
    return _Task(task_id=task_id, repo_url=repo_url, base_commit=base_commit, provenance=provenance)


def _classify_key(
    task_id: str,
    manifest: Manifest,
    records: Mapping[tuple[str, str], Any],
    tasks: Mapping[str, _Task],
    checkouts: dict[str, Path | str],
    listings: dict[str, frozenset[str]],
    scratch: Path,
) -> Classified:
    """One task's answer, or `UNCLASSIFIED` with the reason the question could not be asked."""
    record = records.get((manifest.candidate, task_id))
    if record is None:
        return _unclassified("the transcript holds no graded record for this rollout")
    task = tasks.get(task_id)
    if task is None:
        return _unclassified("the task was not offered under any --tasks root")
    recorded = manifest.prompt_sha256.get(task_id)
    if recorded is None:
        return _unclassified("the manifest records no prompt digest for this task")
    if record.prompt_sha256 != recorded:
        return _unclassified(
            "the transcript record's prompt digest does not match the manifest's recorded "
            "digest for this task, so the record is not evidence about this run's prompt"
        )
    checkout = checkouts.get(task_id)
    if checkout is None:
        checkout = _materialised(task, scratch / task_id)
        checkouts[task_id] = checkout
    if isinstance(checkout, str):
        return _unclassified(checkout)
    listing = listings.get(task_id)
    if listing is None:
        listing = _listing(task, checkout)
        listings[task_id] = listing
    return classify_rollout(record.completion, checkout_reader(checkout), listing)


def _listing(task: _Task, checkout: Path) -> frozenset[str]:
    """The oracle sources the run showed, re-derived the way the run derived them.

    `sources.oracle_sources` was the run's own derivation; this module reads the same
    commit (`provenance.commit`) from the same donor, filters test paths by the same rule
    (`tasks.donor.is_test_path`), and reads the survivors from the checkout this instrument
    already materialised. The oracle budget is deliberately not consulted: it decides
    whether the run posed the task at all, which the transcript record's existence already
    encodes — a task whose oracle did not fit was never posed, and a record that disagrees
    with the manifest is `UNCLASSIFIED` before any shown set matters. A task whose commit or
    donor cannot be read has an empty listing — the `addressability._listing` shape.
    """
    commit = task.provenance.get("commit")
    if not commit:
        return frozenset()
    try:
        touched = _touched_paths(Path(task.repo_url), commit)
    except _GitFailed:
        return frozenset()
    return frozenset(
        path for path in touched if not _is_test_path(path) and _readable(checkout, path)
    )


def _touched_paths(donor: Path, commit: str) -> frozenset[str]:
    """Every path `commit` touched, read from git's own name-status record.

    `-z` because a repository is allowed to hold a path with a newline or a quote in it; a
    rename or a copy record carries two paths and every other carries one — the
    `sources._touched_paths` parse, by identity.
    """
    raw = _git(["show", "--format=", "--name-status", "-z", commit], cwd=donor)
    fields = [field for field in raw.split("\0") if field.strip()]
    paths: set[str] = set()
    index = 0
    while index < len(fields):
        status = fields[index]
        wanted = 2 if status.startswith(("R", "C")) else 1
        paths.update(fields[index + 1 : index + 1 + wanted])
        index += 1 + wanted
    return frozenset(paths)


def _is_test_path(path: str) -> bool:
    """Is this path test code? `tasks.donor.is_test_path`'s rule, kept here by identity.

    A `.py` file under a `test/` or `tests/` directory, or named `test_*.py`/`*_test.py`. A
    root `conftest.py` is deliberately not test code — the donor's judgement, and a second
    spelling of it here would make the shown set drift from the run's.
    """
    if not path.endswith(".py"):
        return False
    pure = PurePosixPath(path)
    if _TEST_DIRECTORIES & set(pure.parts[:-1]):
        return True
    return pure.name.startswith("test_") or pure.name.endswith("_test.py")


def _readable(checkout: Path, path: str) -> bool:
    """The path exists at `base_commit` and is UTF-8 text — the oracle's own omissions."""
    target = checkout / path
    if not target.is_file():
        return False
    try:
        target.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _materialised(task: _Task, destination: Path) -> Path | str:
    """The task's tree at `base_commit`, or the sentence saying why there is none.

    `verify.repo.materialise`'s own commands — clone with no checkout, then a detached
    checkout of `base_commit` — run with the machine's git configuration switched off, so a
    developer's `~/.gitconfig` cannot change what gets classified.
    """
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        _git(
            [
                "clone",
                "--quiet",
                "--no-checkout",
                "--no-hardlinks",
                task.repo_url,
                str(destination),
            ],
            cwd=destination.parent,
        )
        _git(["checkout", "--quiet", "--detach", task.base_commit], cwd=destination)
    except (_GitFailed, OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
        return f"the task's checkout could not be materialised: {exc}"
    return destination


class _GitFailed(RuntimeError):
    """git itself said no — not a repository, an unreadable object, a wedged process."""


def _git(args: list[str], *, cwd: Path) -> str:
    """Run git with the machine's configuration switched off.

    `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` are pointed at `/dev/null` so that a
    developer's `~/.gitconfig` or a system-wide one cannot change what gets classified, and
    `GIT_TERMINAL_PROMPT=0` so an unreachable remote fails instead of waiting for a password
    — the `verify.repo._git` discipline.
    """
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=environment,
        timeout=_GIT_TIMEOUT,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise _GitFailed(detail or f"git {args[0]} exited {completed.returncode}")
    return completed.stdout


def _unclassified(detail: str) -> Classified:
    return Classified(RolloutClass.UNCLASSIFIED, False, False, detail)


def _document(
    namespace: argparse.Namespace,
    manifest: Manifest,
    classified: Mapping[str, Classified],
    decision: Decision,
) -> dict[str, object]:
    counts = Counter(one.klass.value for one in classified.values())
    return {
        "schema": SCHEMA,
        "manifest": str(namespace.manifest),
        "transcript": str(namespace.transcript),
        "run_id": manifest.run_id,
        "candidate": {"repo_id": manifest.candidate, "revision": manifest.revision},
        "rule": RULE,
        "population": len(classified),
        "counts": dict(sorted(counts.items())),
        "sub_counts": {
            "splice_in_context": sum(
                1 for one in classified.values() if one.splice_in_context
            ),
            "outside_shown_set": sum(
                1 for one in classified.values() if one.outside_shown_set
            ),
        },
        "decision": decision.value,
        "rollouts": [
            {
                "task_id": task_id,
                "class": classified[task_id].klass.value,
                "splice_in_context": classified[task_id].splice_in_context,
                "outside_shown_set": classified[task_id].outside_shown_set,
                "detail": classified[task_id].detail,
            }
            for task_id in sorted(classified)
        ],
    }


def _refuse(reason: str) -> int:
    print(f"whetstone resolvability: {reason}", file=sys.stderr)
    return _REFUSED


__all__ = [
    "RULE",
    "SCHEMA",
    "Classified",
    "Decision",
    "Manifest",
    "RolloutClass",
    "build_parser",
    "classify_rollout",
    "decide",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())