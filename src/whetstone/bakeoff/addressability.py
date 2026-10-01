"""A finished measurement run's completions in; whether the pinned base could address the listing.

`measure.py` spends the bake-off — one greedy completion per pinned task under the
numbered-listing prompt, graded by nothing — and this module asks what the finding turns
on: **when the base wrote `EDIT` blocks, did they name real lines the harness could render
a diff from?** The format exists to remove the quoting burden that killed unified diffs
(`docs/planning/patch-representation/finding.md`); this instrument measures whether the
base can *address* the listing at all — range arithmetic and syntax-only replacement
grammaticality — over a finished run's evidence, so the go/no-go for building the contract
is a count rather than a hunch (`docs/planning/edit-contract-finding/measurement-run/spec.md`).

**The rules are fixed in the spec, before the run.** Every class, the worst-first order and
the strict-majority inequality were written before this module saw a real transcript. The
classes: `UNCLASSIFIED` (evidence unreachable — no graded transcript record, a task nobody
offered, a file that is not UTF-8; stays in the denominator) → `MALFORMED`
(`line_range.parse_edit_blocks` refused the completion, with its reason) → `NO_FILE` (the
named path is absent at `base_commit`, or absolute, or climbs out with `..`, or a symlink
leaves the checkout — the `locatability` escape rules, read through its `checkout_reader`
by identity) → `OUT_OF_RANGE` (start > end, start < 1, end past the file's last line,
ranges on one file overlapping, or a replacement that does not parse) → `ADDRESSABLE`
(every block in range, non-overlapping, and every replacement parses with `ast.parse` — a
syntax-only proxy, never a semantics check). Worst first, in the enum's declaration order.

**The ast gate's landing place is the pre-committed ladder's, not a sixth class.** The spec
names five classes, and `ADDRESSABLE`'s definition carries the parse conjunct; a replacement
that does not parse is therefore the nearest worse class — `OUT_OF_RANGE` — with the reason
spelled beside it. The ladder is a total order, and the finding reads the reasons.

**Two sub-counts, reported beside the partition and never moving a class.** (a)
*syntax-fragile-in-context*: replacements that parse alone but the file with them spliced
over their lines fails `ast.parse` — the offline proxy for "parses but the file would not
import", computable without the task's dependencies. It is counted only when the base file
itself parses (a file already broken at `base_commit` cannot be blamed on the replacement)
and the range is in bounds (there is no splice to try). (b) *outside-listing*: blocks
addressing a path the oracle listing does not carry — re-derived the way the run derived
it, `sources.oracle_sources(task, pool=None)` — classified by file existence at
`base_commit`, never by listing membership, so a held test the base could not have been
shown is still `ADDRESSABLE` when its lines are real.

**The population is the manifest's, pinned by identity.** The manifest (`whetstone-measure/1`)
is the source of truth; the instrument cross-checks it three ways before classifying: the
task list equals `measure._PINNED_POPULATION` by identity; the stratum and held-out
documents, through their own fail-closed loaders, subtract to the same list; and the
documents' digests match the digests the manifest recorded. Any disagreement is a refusal
(exit 2) — a changed pre-committed input is a halt, never a rerun. A transcript record
whose `prompt_sha256` disagrees with the manifest's recorded digest is not this run's
evidence and is `UNCLASSIFIED`, never classified.

**The decision is the process exit.** `GO iff count(ADDRESSABLE) * 2 > population` — the
strict-majority inequality inherited from locatability — as 0 GO, 1 NO-GO, 2 refused; a
refusal prints its named reason to stderr and writes nothing, because an empty or partial
document would read as a measurement.

Stdlib only. No model, no network, and nothing under `verify/` or `tasks/` may import this.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from whetstone.bakeoff import stratum as stratum_module
from whetstone.bakeoff.line_range import EditBlock, MalformedCompletion, parse_edit_blocks
from whetstone.bakeoff.locatability import NotText, Reader, checkout_reader
from whetstone.bakeoff.measure import _PINNED_POPULATION, MANIFEST_SCHEMA
from whetstone.bakeoff.sources import oracle_sources
from whetstone.bakeoff.transcript import Transcript
from whetstone.loop import heldout as heldout_module
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.repo import materialise
from whetstone.verify.task import Task

#: The output document's schema. Bumped on any change to a field's meaning.
SCHEMA = "whetstone-addressability/1"

#: The rule, written into every document so a reader never has to find the spec to know it
#: (spec.md, "Decision" — the locatability output-schema pattern).
RULE = "GO iff count(ADDRESSABLE) * 2 > population"

#: Exit codes, `check-probe`'s shape: the decision is the process exit.
_EXIT = {"GO": 0, "NO-GO": 1}
_REFUSED = 2


class BlockClass(str, Enum):
    """What one block's range and replacement were, against the file it named.

    The rollout takes the worst of its blocks; these are the three classes a block can
    earn, the `ADDRESSABLE` half of the spec's ladder with the two worse rungs.
    """

    #: The path is absent at `base_commit`, absolute, or climbs out with `..`.
    NO_FILE = "NO_FILE"
    #: The range or the replacement is unusable: out of bounds, overlapping, or
    #: not parseable Python.
    OUT_OF_RANGE = "OUT_OF_RANGE"
    #: In range, non-overlapping with earlier blocks on the file, and the replacement parses.
    ADDRESSABLE = "ADDRESSABLE"


class RolloutClass(str, Enum):
    """One completion's class: the worst of its blocks. Declared worst first.

    `UNCLASSIFIED` and `MALFORMED` are decided for the whole completion rather than per
    block — the first by evidence the instrument could not reach, the second by a parser
    that refuses the whole text — so the ladder's other three rungs are the block classes
    above, folded up by value.
    """

    #: The question could not be asked — no graded record, no task, or a file that is not
    #: text. Kept in the denominator by name, never folded into a neighbour.
    UNCLASSIFIED = "UNCLASSIFIED"
    #: No EDIT block could be parsed; `line_range.parse_edit_blocks` refused the completion.
    MALFORMED = "MALFORMED"
    #: A named path is absent at `base_commit`, or escapes the repository.
    NO_FILE = "NO_FILE"
    #: A range is unusable, ranges on one file overlap, or a replacement does not parse.
    OUT_OF_RANGE = "OUT_OF_RANGE"
    #: Every block is in range, non-overlapping, and parses as Python.
    ADDRESSABLE = "ADDRESSABLE"


#: Worst first: the order a rollout's class is chosen in (spec, "Classes, worst-first").
_SEVERITY = tuple(RolloutClass)


@dataclass(frozen=True)
class Classified:
    """One rollout's answer: its class, per-block classes, and the two sub-count flags.

    `syntax_fragile` and `outside_listing` are index-aligned with `blocks`: one flag per
    block, reported beside the class and never moving it (spec, "Sub-counts").
    """

    klass: RolloutClass
    blocks: tuple[BlockClass, ...]
    #: Per block: the replacement parses alone but the file with it spliced in does not.
    syntax_fragile: tuple[bool, ...]
    #: Per block: the addressed path is outside the oracle listing's set.
    outside_listing: tuple[bool, ...]
    #: Why, when the class alone does not say — the parser's reason, the block and defect,
    #: or the unreachable evidence.
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


def classify_rollout(
    completion: str, read: Reader, listing: frozenset[str] = frozenset()
) -> Classified:
    """Class one completion by the spec's worst-first rule, against `read`'s files.

    `completion` is the transcript's graded record for one (candidate, task); `read` is a
    `locatability.checkout_reader` over the task's tree at `base_commit` (or an in-memory
    stand-in in tests); `listing` is the oracle listing's path set, whose membership feeds
    sub-count (b) only.

    A completion `parse_edit_blocks` refuses is `MALFORMED` with the parser's reason. A
    named file that is not UTF-8 leaves the whole rollout `UNCLASSIFIED` — "the file is not
    there" and "the file could not be read as text" are different facts, and only the first
    is `NO_FILE` (the `locatability.NotText` discipline). Otherwise the rollout is the
    worst of its blocks' classes, and the detail names the first block that earned the
    worst class, if any.
    """
    try:
        blocks = parse_edit_blocks(completion)
    except MalformedCompletion as exc:
        return Classified(RolloutClass.MALFORMED, (), (), (), exc.reason)

    classes: list[BlockClass] = []
    fragile: list[bool] = []
    outside: list[bool] = []
    reasons: list[str] = []
    covered: dict[str, int] = {}
    for index, block in enumerate(blocks, start=1):
        try:
            klass, reason, is_fragile, is_outside = _classify_block(
                block, index, read, covered, listing
            )
        except NotText as exc:
            return Classified(RolloutClass.UNCLASSIFIED, (), (), (), f"not UTF-8: {exc}")
        classes.append(klass)
        fragile.append(is_fragile)
        outside.append(is_outside)
        reasons.append(reason)

    worst = min((RolloutClass(one.value) for one in classes), key=_SEVERITY.index)
    detail = next(
        (
            reason
            for klass, reason in zip(classes, reasons, strict=True)
            if RolloutClass(klass.value) is worst and reason
        ),
        "",
    )
    return Classified(worst, tuple(classes), tuple(fragile), tuple(outside), detail)


def _classify_block(
    block: EditBlock,
    index: int,
    read: Reader,
    covered: dict[str, int],
    listing: frozenset[str],
) -> tuple[BlockClass, str, bool, bool]:
    """One block's class, reason, and sub-count flags — in that order.

    The escape rules run before the reader is touched, so an absolute or `..`-climbing
    path is answered `NO_FILE` without anything being read (the `locatability` shape). The
    range defects are checked in the spec's order — start > end, start < 1, end past the
    last line, overlap — and a block that passes them updates `covered`, the greatest line
    an earlier block on the same file already addressed, which is how overlap is decided.
    The `ast.parse` gate runs last: a replacement that does not parse is `OUT_OF_RANGE`,
    the nearest worse class in the pre-committed ladder — never a sixth class.

    `outside` — the sub-count (b) flag — is set for every block whose path the oracle
    listing does not carry, whatever the class; it is reported beside the partition and
    never moves it.
    """
    outside = block.path not in listing
    if _escapes(block.path):
        return (
            BlockClass.NO_FILE,
            f"block {index} ({block.path}): absolute or climbs out of the repository",
            False,
            outside,
        )
    text = read(block.path)
    if text is None:
        return (
            BlockClass.NO_FILE,
            f"block {index} ({block.path}): no such file at base_commit",
            False,
            outside,
        )
    lines = _lines(text)
    if block.start > block.end:
        return _out_of_range(index, block, f"start {block.start} > end {block.end}", outside)
    if block.start < 1:
        return _out_of_range(index, block, f"start {block.start} < 1", outside)
    if block.end > len(lines):
        return _out_of_range(
            index, block, f"end {block.end} exceeds the file's {len(lines)} lines", outside
        )
    if block.start <= covered.get(block.path, 0):
        return _out_of_range(
            index, block, "overlaps an earlier block on the same file", outside
        )
    covered[block.path] = max(covered.get(block.path, 0), block.end)
    if not _parses(block.replacement):
        return _out_of_range(index, block, "replacement does not parse as Python", outside)
    return BlockClass.ADDRESSABLE, "", _syntax_fragile(block, lines), outside


def _out_of_range(
    index: int, block: EditBlock, defect: str, outside: bool
) -> tuple[BlockClass, str, bool, bool]:
    return (
        BlockClass.OUT_OF_RANGE,
        f"block {index} ({block.path}): {defect}",
        False,
        outside,
    )


def _syntax_fragile(block: EditBlock, lines: list[str]) -> bool:
    """Sub-count (a): the replacement parses alone but the spliced file does not.

    The proxy for "parses but the file would not import", computable offline: a file that
    fails `ast.parse` cannot be imported, and the stronger check needs the task's
    dependencies. Counted only when the base file itself parses — a file already broken at
    `base_commit` cannot be blamed on the replacement — and the caller only splices
    in-range blocks, for which there is a well-defined splice.
    """
    if not _parses("\n".join(lines)):
        return False
    return not _parses(_spliced(lines, block.start, block.end, block.replacement))


def _spliced(lines: list[str], start: int, end: int, replacement: str) -> str:
    """The file's text with `replacement` over lines `start..end`, by the format's line rule.

    The replacement's lines are split like the listing counts the file's — on `\n` with
    the phantom element after a final newline dropped (`line_range._lines`) — so splicing
    "x = 1\n" in means the same thing as writing "x = 1" over the addressed lines.
    """
    new = replacement.split("\n")
    if new and new[-1] == "":
        new = new[:-1]
    return "\n".join([*lines[: start - 1], *new, *lines[end:]])


def _parses(text: str) -> bool:
    """`ast.parse` with any `SyntaxError` folded to False — syntax only, never semantics."""
    try:
        ast.parse(text)
    except SyntaxError:
        return False
    return True


def _lines(text: str) -> list[str]:
    """The file's real lines: split on `\n`, the phantom element after a final newline
    dropped, interior empty lines kept. An empty file has no lines — nothing to address.
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
    """GO iff more than half of the population is `ADDRESSABLE`. Every class counts in the total.

    An empty population is refused, not decided: "nothing to classify" is a join bug or the
    wrong manifest, never a result.
    """
    if not classes:
        raise ValueError("the population is empty, so there is nothing to decide over")
    addressable = sum(1 for klass in classes if klass is RolloutClass.ADDRESSABLE)
    return Decision.GO if addressable * 2 > len(classes) else Decision.NO_GO


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
        prog="python -m whetstone.bakeoff.addressability",
        description=(
            "Classify a finished measurement run's completions against the files each task "
            "showed at base_commit, and exit 0 GO / 1 NO-GO / 2 refused by the pre-committed "
            "rule: GO iff count(ADDRESSABLE) * 2 > population."
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

    with tempfile.TemporaryDirectory(prefix="whetstone-addressability-") as scratch:
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


def _read_corpus(namespace: argparse.Namespace, manifest: Manifest) -> dict[str, Task]:
    """The pinned tasks, loaded from the declared corpus roots — nothing else is wanted.

    A root that cannot be read is refused by name; a task the corpus does not carry is
    left to the per-rollout `UNCLASSIFIED` — a missing task document is evidence
    unreachable, never a refusal of the whole run.
    """
    wanted = set(manifest.tasks)
    try:
        return {
            task.task_id: task
            for root in namespace.tasks
            for task in load_tasks(Path(root))
            if task.task_id in wanted
        }
    except (OSError, ValueError) as exc:
        raise ValueError(f"a corpus root could not be loaded: {exc}") from exc


def _classify_key(
    task_id: str,
    manifest: Manifest,
    records: Mapping[tuple[str, str], Any],
    tasks: Mapping[str, Task],
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
        listing = _listing(task)
        listings[task_id] = listing
    return classify_rollout(record.completion, checkout_reader(checkout), listing)


def _listing(task: Task) -> frozenset[str]:
    """The oracle listing's path set, re-derived the way the run derived it (measure.py).

    `oracle_sources` was the run's own derivation; a task whose oracle cannot be re-derived
    has an empty listing, so every block it wrote is counted outside it — unreachable in a
    real run, because the driver records no completion for a task it could not pose.
    """
    sources = oracle_sources(task, pool=None)
    return frozenset(sources.files) if sources.files is not None else frozenset()


def _materialised(task: Task, destination: Path) -> Path | str:
    """The task's tree at `base_commit`, or the sentence saying why there is none."""
    try:
        materialise(task, destination)
    except (OSError, RuntimeError, ValueError) as exc:
        return f"the task's checkout could not be materialised: {exc}"
    return destination


def _unclassified(detail: str) -> Classified:
    return Classified(RolloutClass.UNCLASSIFIED, (), (), (), detail)


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
            "syntax_fragile_in_context": sum(
                1 for one in classified.values() for flag in one.syntax_fragile if flag
            ),
            "outside_listing": sum(
                1 for one in classified.values() for flag in one.outside_listing if flag
            ),
        },
        "decision": decision.value,
        "rollouts": [
            {
                "task_id": task_id,
                "class": classified[task_id].klass.value,
                "blocks": [klass.value for klass in classified[task_id].blocks],
                "syntax_fragile": list(classified[task_id].syntax_fragile),
                "outside_listing": list(classified[task_id].outside_listing),
                "detail": classified[task_id].detail,
            }
            for task_id in sorted(classified)
        ],
    }


def _refuse(reason: str) -> int:
    print(f"whetstone addressability: {reason}", file=sys.stderr)
    return _REFUSED


__all__ = [
    "RULE",
    "SCHEMA",
    "BlockClass",
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