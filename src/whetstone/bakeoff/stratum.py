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
emits it), excluding file headers, `\ No newline` markers, and binary literal payload. The
corpus test asserts the walk's added/deleted against git's `--numstat` on all 66 real tasks —
a contradiction is a named failure, never reconciled (the autopsy finding's discipline,
`docs/planning/p2-diff-autopsy/finding.md:69-71`).

Stdlib and subprocess only. No model, no network, nothing under `verify/`, `patch.py` or
`attribution.py` is touched.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from whetstone.bakeoff.sources import changed_paths
from whetstone.tasks.derive import gold_patch
from whetstone.tasks.donor import Candidate, GitFailed
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


__all__ = [
    "BAND_MAX_CHANGED_LINES",
    "BAND_MAX_HUNKS",
    "BAND_MAX_NON_TEST_FILES",
    "Difficulty",
    "Refusal",
    "changed_paths",
    "difficulty_of",
    "gold_patch",
    "in_band",
    "measure_patch",
    "rule_digest",
]
