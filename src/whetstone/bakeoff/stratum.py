"""The difficulty axis: the shape of a task's own fix, measured a priori, never from a verdict.

The easier-stratum probe needs a subset of the declared source-B set that is *easier*, where
"easier" is fixed before any rollout — a pure selection over the corpus the project already
holds. This module is that axis: `difficulty_of(task)` measures the **reference fix's shape** —
the non-test files the mined commit touched, and the hunks and added/deleted lines of the gold
patch derived from the donor at `provenance.commit`/`parent` — and `in_band` decides the band
("easier") the probe is restricted to.

**The measure is fixed at mint time, and it may never read a verdict.** The gold patch is a
pure function of the manifest's provenance plus the pinned donor state it names, and the rule
reads nothing a rollout produced (`PREREGISTRATION.md:171-177`). A rule that consulted a
verdict, a rollout record, or a report figure would make the stratum a function of the run it
is supposed to predate; the no-inference AST walk in `test_stratum_rule.py` keeps the module's
path free of any inference import, and the module docstring states the boundary because a
guard asserts only the absence, never the reason.

**The gold patch is reused, never redefined.** `changed_paths` is `sources.changed_paths` and
`gold_patch` is `derive.gold_patch`, imported by identity and asserted `is` in a test. The
`Candidate` is composed exactly as `control._from_donor` composes it (`control.py:231-241`):
a second implementation of "the commit's own fix" would be a second definition, and the one
that disagreed would be the one nobody looked at (`control.py:24-29`).

**Why the shape is measured by the rule's own walk rather than by git's report.** No git
command reports hunk counts, and `verify.repo.declared_paths` — git's own `--numstat` parse —
drops the added/deleted counts and reports renames by destination only (`repo.py:87-95`), so
it cannot carry this measure even where it agrees with it. The walk counts `@@` hunk headers
and `+`/`-` content lines over the git-produced patch text (always well-formed: `gold_patch`
emits it), excluding file headers, `\\ No newline` markers, and binary literal payload. The
corpus test asserts the walk's added/deleted against git's `--numstat` on all 66 real tasks —
a contradiction is a named failure, never reconciled (the autopsy finding's discipline,
`docs/planning/p2-diff-autopsy/finding.md:69-71`).

**The committed document is the pinned input, and the loader refuses rather than trusts.**
`write_document`/`compose_document` produce schema `whetstone-stratum/1` deterministically —
sorted ids, sorted keys, no timestamp, so two runs over one corpus are byte-identical and the
recomputation test can compare — and refuse a degenerate membership by name: empty, or the
whole declared corpus, is a usage error, never a vacuous pass (the empty-directory refusal of
`manifest.py:70-75`). `read_document` is the fail-closed consumer: unknown schema, a rule
whose digest no longer matches the document's, a hand-edited payload that breaks the
`document_digest`, an id that does not resolve, and the two degenerate memberships are each a
named refusal. The four loader refusals are defined here because the run-side filter (aspect
2) imports them by identity — a second definition of "what may be selected" would be a second
answer to the same question, with only one of them reviewed.

The document is evidence about the data, never the data (`tasks/README.md:126-128`): counts
only — files/hunks/added/deleted and the manifest-structural tie-break fields — never path
names, never patch content, never donor code. The locality walk in `test_stratum_document.py`
asserts that structurally, with a canary that proves the walk would see a leak.

Stdlib and subprocess only. No model, no network, nothing under `verify/`, `patch.py` or
`attribution.py` is touched.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.bakeoff.sources import changed_paths
from whetstone.tasks.derive import gold_patch
from whetstone.tasks.donor import Candidate, GitFailed, run_git
from whetstone.tasks.manifest import load_tasks
from whetstone.verify.task import Task

#: The provenance key naming the commit a task was mined from, and the one naming its parent.
#: Read here only to build the `Candidate` the gold patch is derived from; the derivation that
#: decides whether the task can be measured at all lives in `sources.changed_paths`.
_COMMIT = "commit"
_PARENT = "parent"

#: The pre-committed band, fixed before any run (spec D4): one non-test file, at most two
#: hunks, at most thirty changed lines. Membership falls out of `in_band`; widening after
#: seeing the corpus is post-hoc selection (`prd.md:218-221`), and the frozen-band test pins
#: these numbers to the spec's.
BAND_MAX_NON_TEST_FILES = 1
BAND_MAX_HUNKS = 2
BAND_MAX_CHANGED_LINES = 30

#: The band as the document carries it — the canonical spelling `rule_digest` hashes.
_BAND_PARAMETERS = {
    "max_non_test_files": BAND_MAX_NON_TEST_FILES,
    "max_hunks": BAND_MAX_HUNKS,
    "max_changed_lines": BAND_MAX_CHANGED_LINES,
}


@dataclass(frozen=True)
class Difficulty:
    """The reference fix's shape, and the manifest-structural counts that tie-break it.

    `files`/`hunks`/`added`/`deleted` are the axis: what the fix itself looks like, measured
    from the donor at the task's pinned commits. `f2p`/`pins`/`blobs` are `len(fail_to_pass)`,
    `len(environment.pins)` and `len(test_blobs)` — present in every manifest
    (`understanding.md:31-38`), fixed at mint time, and recorded so the committed document
    carries the same manifest signals a future secondary axis would need, never a verdict.
    """

    files: int
    hunks: int
    added: int
    deleted: int
    f2p: int
    pins: int
    blobs: int


@dataclass(frozen=True)
class Refusal:
    """Why a task has no difficulty. The only other answer `difficulty_of` returns.

    `difficulty_of` returns rather than raises because every reason this can fail is an
    ordinary property of a corpus rather than a defect: a source-A task has no donor commit,
    a donor may be missing, and a fix may touch a held path. Each is a refusal with its
    reason on it — never a measured difficulty, never a guessed one.
    """

    reason: str


def measure_patch(diff: str) -> tuple[int, int, int]:
    """`(hunks, added, deleted)` of a gold patch, from its text, without consulting git.

    Lines are classified by their diff prefix and nothing else. A `@@` header is a hunk; a
    `+`/`-` line is added/deleted content; a `+++`/`---` line is a file header; a `\\` line is
    git's no-newline annotation; and everything inside a `GIT binary patch` literal is
    payload, counted by nothing. The corpus test proves this walk and git's own `--numstat`
    agree on the real corpus, lines only — a contradiction is a named failure, never
    reconciled (spec D3).
    """
    hunks = 0
    added = 0
    deleted = 0
    in_binary = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_binary = False
            continue
        if line == "GIT binary patch":
            in_binary = True
            continue
        if in_binary:
            continue
        if line.startswith("@@"):
            hunks += 1
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("\\"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            deleted += 1
    return hunks, added, deleted


def _measured(task: Task) -> tuple[str, tuple[str, ...]] | Refusal:
    """The task's own fix and the non-test paths it touches, composed as the control arm does.

    The route is chosen by what the task carries, and only by that — the same rule
    `control.reference_patch` follows: a donor commit means the donor, no donor commit means
    a refusal. The `Candidate` mirrors `control._from_donor` (`control.py:231-241`) field for
    field: `held_tests` empty rather than the task's blobs, because `changed_paths` has
    already removed every test path, and handing them over would invite a future reader to
    think this is where the exclusion happens.
    """
    if not (task.provenance.get(_COMMIT) and task.provenance.get(_PARENT)):
        return Refusal(
            reason=(
                f"task {task.task_id!r} carries no donor commit in its provenance, so its "
                f"difficulty cannot be measured: the axis is the reference fix's shape, "
                f"derived from the donor at provenance.commit/parent, and there is nothing "
                f"to derive from"
            )
        )
    changed = changed_paths(task)
    if changed.paths is None:
        return Refusal(reason=changed.reason)
    candidate = Candidate(
        sha=task.provenance[_COMMIT],
        parent=task.provenance[_PARENT],
        subject=task.problem_statement,
        held_tests=(),
        source_paths=tuple(changed.paths),
        other_paths=(),
    )
    donor = Path(task.repo_url)
    try:
        diff = gold_patch(donor, candidate)
    except (GitFailed, subprocess.SubprocessError, OSError) as exc:
        return Refusal(
            reason=(
                f"the gold patch for task {task.task_id!r} could not be produced from its "
                f"donor at {str(donor)!r}: {type(exc).__name__}: {exc}"
            )
        )
    if not diff.strip():
        return Refusal(
            reason=(
                f"the gold patch for task {task.task_id!r} is empty, so there is no fix "
                f"shape to measure"
            )
        )
    return diff, changed.paths


def _gold_diff(task: Task) -> str | Refusal:
    """The task's own fix, byte for byte — the diff the control arm would trust (spec D2)."""
    measured = _measured(task)
    if isinstance(measured, Refusal):
        return measured
    return measured[0]


def difficulty_of(task: Task) -> Difficulty | Refusal:
    """The difficulty of `task`: its own fix's shape, or the reason there is none.

    The walk's numbers are the axis; the tie-break fields come from the manifest. An empty
    gold patch is refused as "nothing to measure" even though `changed_paths` already refuses
    the no-non-test-path case (`sources.py:277-286`) — belt and braces, because a difficulty
    computed from an empty patch would be a shape invented out of nothing.
    """
    measured = _measured(task)
    if isinstance(measured, Refusal):
        return measured
    diff, paths = measured
    hunks, added, deleted = measure_patch(diff)
    return Difficulty(
        files=len(paths),
        hunks=hunks,
        added=added,
        deleted=deleted,
        f2p=len(task.fail_to_pass),
        pins=len(task.environment.pins),
        blobs=len(task.test_blobs),
    )


def in_band(difficulty: Difficulty) -> bool:
    """Is this difficulty "easier"? The pre-committed membership rule (spec D4)."""
    return (
        difficulty.files == BAND_MAX_NON_TEST_FILES
        and difficulty.hunks <= BAND_MAX_HUNKS
        and difficulty.added + difficulty.deleted <= BAND_MAX_CHANGED_LINES
    )


#: The functions whose source IS the rule, for the drift guard. Scoped to the rule rather
#: than the module's I/O: a loader-only edit (an error-message change) must not refuse the
#: committed document, while any edit to the measurement or the membership must (spec D7).
_RULE_FUNCTIONS = (difficulty_of, measure_patch, in_band)


def rule_digest() -> str:
    """The digest of the rule as it stands: the rule functions' source plus the band.

    Hashes `inspect.getsource` of the rule functions and a canonical JSON rendering of the
    band parameters (spec D7). The stratum document records it, and the loader refuses a
    document whose digest no longer matches the module's — any rule-source or band edit
    breaks the pairing, which is the rule-drift guard (`prd.md:78-85`).
    """
    hasher = hashlib.sha256()
    for function in _RULE_FUNCTIONS:
        hasher.update(inspect.getsource(function).encode("utf-8"))
    hasher.update(
        json.dumps(_BAND_PARAMETERS, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return hasher.hexdigest()


# --------------------------------------------------------------------------------------------
# The stratum document: schema `whetstone-stratum/1`, and its deterministic writer and
# fail-closed loader. The four loader refusals are defined here, imported by identity there.
# --------------------------------------------------------------------------------------------

#: Names the shape of the file so a later format change is a visible one rather than a silent
#: reinterpretation of an old file by new code (the transcript codec discipline, spec N1).
STRATUM_SCHEMA = "whetstone-stratum/1"

#: The fields the `document_digest` covers — the canonical payload of everything except the
#: digest itself. `donor_heads` is deliberately absent: it is informational and never gated
#: (the `Recipe.donor_head` posture, `ledger.py:109-110`), and a donor that has moved on must
#: not break the recomputation test's digest equality.
_DIGESTED_FIELDS = (
    "schema",
    "rule_digest",
    "band",
    "corpus",
    "difficulty",
    "refusals",
    "membership",
)


class UnknownStratumId(ValueError):
    """The document names a task it neither measured nor refused — or vice versa."""


class EmptyStratum(ValueError):
    """The membership is degenerate: empty, or the whole declared corpus."""


class StratumSchemaError(ValueError):
    """The document is not schema `whetstone-stratum/1` — unknown schema or malformed shape."""


class StratumDigestMismatch(ValueError):
    """The document's digest does not match its payload, or the rule's has moved on."""


class OutUnderLocalCorpus(ValueError):
    """An `--out` path git would never commit. Raised before anything is read or written."""


@dataclass(frozen=True)
class Band:
    """The pre-committed band as the document carries it. The module constants are the source."""

    max_non_test_files: int
    max_hunks: int
    max_changed_lines: int


@dataclass(frozen=True)
class Stratum:
    """A parsed, validated stratum document — the shape the run-side filter consumes.

    `schema` is carried rather than assumed, `document_digest` is not carried at all: the
    loader's checks are the gate, and a consumer that re-checked the digest would be a second
    answer to "is this document trustworthy" with only one of them reviewed.
    """

    schema: str
    rule_digest: str
    band: Band
    corpus: tuple[str, ...]
    donor_heads: Mapping[str, str]
    difficulty: Mapping[str, Difficulty]
    refusals: Mapping[str, str]
    membership: tuple[str, ...]


def document_digest_of(document: Mapping[str, Any]) -> str:
    """The digest over the canonical payload of the other fields (spec D5).

    Canonical JSON — sorted keys, no whitespace — so the digest is a pure function of the
    payload. The field is aspect 2's mechanically-required check: a hand-edited membership
    breaks it, and the loader refuses rather than trusts.
    """
    payload = {key: document[key] for key in _DIGESTED_FIELDS}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _donor_head(donor: Path) -> str:
    """The commit a donor's history was read at. Informational, never gated.

    Records the state the corpus was computed against, like `Recipe.donor_head`
    (`ledger.py:109-110`); a donor that cannot be read records an empty head rather than
    refusing the document, because the head is evidence about the run, not part of the
    membership.
    """
    try:
        return run_git(["rev-parse", "HEAD"], cwd=donor).strip()
    except (GitFailed, subprocess.SubprocessError, OSError):
        return ""


def compose_document(tasks: Sequence[Task], donors: Mapping[str, Path]) -> dict[str, Any]:
    """The document for `tasks` under `donors`: every field except nothing, digest included.

    Sorted ids, sorted keys, no timestamp: two calls over one corpus are byte-identical,
    which is the recomputation test's premise (spec D5). An empty corpus is refused — a set
    with nothing in it that reduces to a document is the vacuous-pass lie
    (`manifest.py:70-75`).
    """
    ids = [task.task_id for task in tasks]
    if not ids:
        raise ValueError(
            "the stratum corpus is empty: no task manifests were loaded, and a document over "
            "nothing would be a stratum nobody chose"
        )
    duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
    if duplicates:
        raise ValueError(
            f"the stratum corpus repeats task id {duplicates!r}; two manifests naming one "
            f"task would make the membership ambiguous"
        )

    measured: dict[str, Difficulty] = {}
    refusals: dict[str, str] = {}
    for task in tasks:
        result = difficulty_of(task)
        if isinstance(result, Refusal):
            refusals[task.task_id] = result.reason
        else:
            measured[task.task_id] = result

    membership = tuple(sorted(task_id for task_id, d in measured.items() if in_band(d)))
    if not membership:
        raise EmptyStratum(
            "the rule produced an empty membership: no task in the corpus falls inside the "
            "pre-committed band (one non-test file, at most two hunks, at most thirty "
            "changed lines). A stratum of nothing is a usage error, never a vacuous pass — "
            "record it as a finding; do not widen the band after seeing the corpus"
        )
    if set(membership) == set(ids):
        raise EmptyStratum(
            "the rule selected the whole declared corpus: every task falls inside the "
            "pre-committed band, so \"easier\" is not a stratum but the corpus itself. "
            "A degenerate membership is a usage error, never a silent widening"
        )

    document: dict[str, Any] = {
        "schema": STRATUM_SCHEMA,
        "rule_digest": rule_digest(),
        "band": dict(_BAND_PARAMETERS),
        "corpus": sorted(ids),
        "donor_heads": {label: _donor_head(Path(root)) for label, root in donors.items()},
        "difficulty": {
            task_id: {
                "files": d.files,
                "hunks": d.hunks,
                "added": d.added,
                "deleted": d.deleted,
                "f2p": d.f2p,
                "pins": d.pins,
                "blobs": d.blobs,
            }
            for task_id, d in measured.items()
        },
        "refusals": dict(sorted(refusals.items())),
        "membership": list(membership),
    }
    document["document_digest"] = document_digest_of(document)
    return document


def write_document(
    out: Path, tasks: Sequence[Task], donors: Mapping[str, Path]
) -> None:
    """Write the stratum document for `tasks`, deterministically, with a trailing newline.

    The committed file diffs line by line: indented, sorted keys, no timestamp — the same
    reviewable shape as the ledger (`ledger.py:155-165`).
    """
    document = compose_document(tasks, donors)
    location = Path(out)
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


def read_document(path: Path) -> Stratum:
    """Read and validate a stratum document, or refuse it by name.

    Fail-closed like `load_task`: a document that half-parsed would let the run select a
    membership the document's own fields do not support. The checks are the four named
    refusals — unknown schema, digest mismatches (the rule's, then the document's), an id
    that does not resolve, and a degenerate membership — plus `ValueError` for a file that
    cannot be read at all (the `ledger.py:168-187` shape).
    """
    location = Path(path)
    try:
        raw = json.loads(location.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"stratum document {str(location)!r} could not be read: {exc}") from exc
    if not isinstance(raw, dict):
        raise StratumSchemaError(
            f"stratum document {str(location)!r} must be a JSON object, "
            f"got {type(raw).__name__}"
        )

    if raw.get("schema") != STRATUM_SCHEMA:
        raise StratumSchemaError(
            f"stratum document {str(location)!r} declares schema {raw.get('schema')!r}, "
            f"but this module reads {STRATUM_SCHEMA!r}; an old-schema document fails decode "
            "rather than defaulting (spec N1)"
        )

    if raw.get("rule_digest") != rule_digest():
        raise StratumDigestMismatch(
            f"stratum document {str(location)!r} was sealed under a different rule: its "
            f"rule digest {raw.get('rule_digest')!r} does not match the module's current "
            f"{rule_digest()!r}. Any rule-source or band edit invalidates the committed "
            "document by design (spec D7); regenerate it in the same commit as the edit"
        )

    _require(raw, "rule_digest", str, location)
    _require(raw, "band", dict, location)
    _require(raw, "corpus", list, location)
    _require(raw, "difficulty", dict, location)
    _require(raw, "refusals", dict, location)
    _require(raw, "membership", list, location)
    _require(raw, "document_digest", str, location)

    band_raw = raw["band"]
    band = Band(
        max_non_test_files=_int_field(band_raw, "max_non_test_files", location),
        max_hunks=_int_field(band_raw, "max_hunks", location),
        max_changed_lines=_int_field(band_raw, "max_changed_lines", location),
    )

    corpus = tuple(_str_list(raw["corpus"], "corpus", location))
    membership = tuple(_str_list(raw["membership"], "membership", location))

    difficulty: dict[str, Difficulty] = {}
    for task_id, counts in raw["difficulty"].items():
        if not isinstance(task_id, str) or not isinstance(counts, dict):
            raise StratumSchemaError(
                f"stratum document {str(location)!r} has a malformed difficulty entry; "
                f"each entry must be a task id mapping to its counts"
            )
        difficulty[task_id] = Difficulty(
            files=_int_field(counts, "files", location),
            hunks=_int_field(counts, "hunks", location),
            added=_int_field(counts, "added", location),
            deleted=_int_field(counts, "deleted", location),
            f2p=_int_field(counts, "f2p", location),
            pins=_int_field(counts, "pins", location),
            blobs=_int_field(counts, "blobs", location),
        )

    refusals: dict[str, str] = {}
    for task_id, reason in raw["refusals"].items():
        if not isinstance(task_id, str) or not isinstance(reason, str):
            raise StratumSchemaError(
                f"stratum document {str(location)!r} has a malformed refusal; each entry "
                f"must be a task id mapping to a reason string"
            )
        refusals[task_id] = reason

    donor_heads = raw.get("donor_heads", {})
    if not isinstance(donor_heads, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in donor_heads.items()
    ):
        raise StratumSchemaError(
            f"stratum document {str(location)!r} has a malformed donor_heads; each entry "
            f"must be a donor label mapping to a commit sha"
        )

    ids = set(corpus)
    measured_ids = set(difficulty)
    for task_id in membership:
        if task_id not in ids:
            raise UnknownStratumId(
                f"stratum document {str(location)!r} lists {task_id!r} in its membership, "
                f"but the corpus never names that task; an unknown id is refused rather "
                "than silently selected for the run"
            )
    for task_id in measured_ids | set(refusals):
        if task_id not in ids:
            raise UnknownStratumId(
                f"stratum document {str(location)!r} records difficulty or a refusal for "
                f"{task_id!r}, which is not in its corpus"
            )
    overlap = measured_ids & set(refusals)
    if overlap:
        raise UnknownStratumId(
            f"stratum document {str(location)!r} both measures and refuses "
            f"{sorted(overlap)!r}; a task cannot carry both"
        )
    uncovered = ids - measured_ids - set(refusals)
    if uncovered:
        raise UnknownStratumId(
            f"stratum document {str(location)!r} leaves {sorted(uncovered)!r} of its own "
            "corpus neither measured nor refused; a silently dropped task is a missing "
            "denominator"
        )

    if not membership:
        raise EmptyStratum(
            f"stratum document {str(location)!r} has an empty membership; a stratum of "
            "nothing is a usage error, never a vacuous pass"
        )
    if set(membership) == ids:
        raise EmptyStratum(
            f"stratum document {str(location)!r} selects the whole declared corpus; "
            "\"easier\" must be a proper subset, or the stratum measures nothing new"
        )

    if raw.get("document_digest") != document_digest_of(raw):
        raise StratumDigestMismatch(
            f"stratum document {str(location)!r} carries a document_digest that does not "
            f"match its own payload: a hand-edited membership, band or value breaks the "
            "digest, and the loader refuses rather than trusts (spec D5)"
        )

    return Stratum(
        schema=raw["schema"],
        rule_digest=raw["rule_digest"],
        band=band,
        corpus=corpus,
        donor_heads=donor_heads,
        difficulty=difficulty,
        refusals=refusals,
        membership=membership,
    )


def _require(raw: dict[str, Any], key: str, kind: type[Any], location: Path) -> None:
    """One field, one type: a missing or wrong-typed field is a schema error, never a default."""
    if key not in raw:
        raise StratumSchemaError(
            f"stratum document {str(location)!r} is missing required field {key!r}"
        )
    if not isinstance(raw[key], kind):
        raise StratumSchemaError(
            f"stratum document {str(location)!r} has a non-{kind.__name__} {key} "
            f"({type(raw[key]).__name__})"
        )


def _int_field(raw: dict[str, Any], key: str, location: Path) -> int:
    """One int in a nested object: a missing or non-int value is a schema error."""
    value = raw.get(key)
    if not isinstance(value, int):
        raise StratumSchemaError(
            f"stratum document {str(location)!r} has a missing or non-int {key!r}"
        )
    return value


def _str_list(values: list[Any], key: str, location: Path) -> tuple[str, ...]:
    """A list of task ids: one non-string entry is a schema error, never a silent drop."""
    for value in values:
        if not isinstance(value, str):
            raise StratumSchemaError(
                f"stratum document {str(location)!r} has a non-string entry in {key} "
                f"({type(value).__name__})"
            )
    return tuple(values)


#: The gitignored data roots (`/.gitignore`): a document under any of them is a document git
#: cannot see, and a pinned input git history cannot prove predated the run.
_LOCAL_OUT_ROOTS = ("tasks/local/", "runs/", "checkpoints/", "reports/local/", "_sandbox/")


def refuse_committed_out(out: Path) -> None:
    """Refuse an `--out` that passes through a gitignored data root.

    The document is the pre-committed pinned input (spec D5): a stratum written under a
    gitignored data root is a stratum git history cannot prove predated the run. The check
    is over the resolved path's own segments — `out/../tasks/local/x.json` and a symlinked
    directory both resolve to a path that passes through the root — and it is a refusal,
    never a rewrite: the operator's spelling is heard as given, and the message names the
    committable home.
    """
    parts = out.resolve().parts
    for root in _LOCAL_OUT_ROOTS:
        root_parts = Path(root).parts
        if any(
            parts[i : i + len(root_parts)] == root_parts
            for i in range(len(parts) - len(root_parts) + 1)
        ):
            raise OutUnderLocalCorpus(
                f"the document at {str(out)!r} sits under the gitignored root {root!r}. "
                "The stratum is the pre-committed pinned input the probe runs over, and a "
                "document git cannot see is a document git history cannot prove predated "
                "the run. Point --out at a committable path such as tasks/stratum/easier.json"
            )


def main(argv: Sequence[str] | None = None) -> int:
    """The runbook door: `python -m whetstone.bakeoff.stratum --corpus A [--corpus B ...] --out P`.

    Loads one directory of manifests per `--corpus` (the two-donor union,
    `test_run_task_roots.py` shape), resolves each task's donor from its `repo_url`, and
    writes the document. `--out` is checked **before** anything is loaded — the refusal is
    about the artifact's home, and it must fire even against a corpus that would itself
    refuse. A degenerate membership is exit 2 with the reason named; the committed document
    can never be degenerate.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whetstone.bakeoff.stratum",
        description=(
            "Compute the difficulty rule over a corpus and write the committed stratum "
            "document: schema whetstone-stratum/1, the rule digest, the band, per-task "
            "difficulty and refusals, the membership, and the document digest. Offline: no "
            "model is loaded and no network is touched; the donors named by the manifests "
            "are read only."
        ),
    )
    parser.add_argument(
        "--corpus",
        action="append",
        required=True,
        type=Path,
        help="a directory of task manifests (repeatable; the roots are unioned)",
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="where the document is written"
    )
    namespace = parser.parse_args(argv)

    out = namespace.out
    try:
        refuse_committed_out(out)
    except OutUnderLocalCorpus as exc:
        print(f"whetstone stratum: {exc}", file=sys.stderr)
        return 2

    tasks: list[Task] = []
    for root in namespace.corpus:
        try:
            tasks.extend(load_tasks(Path(root)))
        except ValueError as exc:
            print(f"whetstone stratum: {exc}", file=sys.stderr)
            return 2

    donors: dict[str, Path] = {}
    for task in tasks:
        label = task.provenance.get("donor") or Path(task.repo_url).name
        donors[label] = Path(task.repo_url)

    try:
        write_document(out, tasks, donors)
    except (EmptyStratum, ValueError) as exc:
        print(f"whetstone stratum: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BAND_MAX_CHANGED_LINES",
    "BAND_MAX_HUNKS",
    "BAND_MAX_NON_TEST_FILES",
    "STRATUM_SCHEMA",
    "Band",
    "Difficulty",
    "EmptyStratum",
    "OutUnderLocalCorpus",
    "Refusal",
    "Stratum",
    "StratumDigestMismatch",
    "StratumSchemaError",
    "UnknownStratumId",
    "changed_paths",
    "compose_document",
    "difficulty_of",
    "document_digest_of",
    "gold_patch",
    "in_band",
    "main",
    "measure_patch",
    "read_document",
    "refuse_committed_out",
    "rule_digest",
    "write_document",
]
