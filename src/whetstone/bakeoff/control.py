"""The control arm: proof, taken in the same run, that the harness could have reached PASS.

**The failure this module prevents is a column of zeroes that means nothing.** The bake-off's
most likely result is that every candidate base solves zero of the 66 tasks, and that is a
legitimate P1 finding — but "all three bases are too weak" and "the harness never applied a patch
to the tree it verified" produce byte-identical output. They have opposite fixes. P1's pivot
signal (`docs/ROADMAP.md:387-389`) is the decision that rests on telling them apart, and nothing
in a rollout record can: a rollout only ever reports what one candidate did.

So the harness is measured directly, per candidate, on the same task set, under the **same
provisioned interpreter** the rollouts get, through the **same shipped `verify_strict`**:

* `inert_patch()` — a real diff that adds one inert non-python file — must reach **FAIL**. A PASS
  there means the declared failing test already passed at `base_commit`, so the task grades every
  policy as correct, including one that emitted nothing. That is a fact about the task or the
  checkout, never about the base, and it has to be loud.
* the task's own reference patch, **re-derived from the donor**, must reach **PASS**. A task its
  own gold patch cannot pass grades every policy as wrong, and a corpus of those reports a zero
  that says nothing about any model.

Either half wrong and the run is `UNVERIFIED` — see `harness_status` — and no ranking may be
emitted from it. The records are still findings; they are simply not evidence about a base.

**Why the reference is re-derived rather than stored.** `tasks/local/` holds the manifests, not
the patches: a gold patch committed beside a task would be an operator artifact nobody re-checked
against the donor, and it would drift the first time a donor was re-mined. `whetstone.tasks.derive`
already produces exactly this patch, proven across all 66 manifests, so it is reused unchanged
rather than reimplemented — a second derivation would be a second definition of "the commit's own
fix", and the one that disagreed would be the one nobody looked at.

**The pre-flight, and why it is not dead code.** A re-derived reference that touches an
operator-held test path is refused by STRICT before anything runs — the cheat-scope check doing
precisely its job — and that refusal is indistinguishable, from the outside, from "the harness
cannot reach PASS". The control arm would then raise a false alarm about the one thing it exists
to rule out. Checking the derived paths against `task.test_blobs` first costs one set comparison,
never fired across the 66 mined manifests, and turns a would-be control failure into a
`SKIPPED` carrying its reason. That check, and the path derivation it guards, live in
`whetstone.bakeoff.sources` — the rollout's oracle prompt is built from the *same* path set, and
two derivations of "which files does this fix touch" would be two definitions of the task's scope
with only one of them reviewed.

**No model here.** The control arm never asks a base for anything; it is about the harness. That
is why it takes no generator, and why it can be run before a single token has been generated.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from whetstone.bakeoff.scoring import Interpreters
from whetstone.bakeoff.sources import changed_paths
from whetstone.tasks.derive import gold_patch
from whetstone.tasks.donor import Candidate, GitFailed
from whetstone.tasks.liveness import inert_patch
from whetstone.verify.strict import verify_strict
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status

#: The provenance key naming the commit a task was mined from. Read here only to build the
#: `Candidate` `gold_patch` diffs; the derivation that decides whether it is usable at all lives
#: in `whetstone.bakeoff.sources`.
_COMMIT = "commit"
_PARENT = "parent"


class Control(str, Enum):
    """What the control arm established about the harness on one task.

    `str` mixin so a control serialises as its name, matching `Status` and `Outcome`.

    There are three members and not two because "the harness is broken" and "this task could not
    be used to check the harness" are different facts with different responses: the first stops
    the run being ranked, and the second is an ordinary gap in coverage that the remaining tasks
    close.
    """

    #: The inert patch FAILed and the re-derived reference PASSed. The harness discriminates on
    #: this task, so a candidate's zero on it is a statement about the candidate.
    INTACT = "INTACT"

    #: One of the two arms answered wrong. Nothing measured in this run is evidence about a base,
    #: and no ranking may be emitted from it.
    BROKEN = "BROKEN"

    #: No reference patch could be obtained — the task carries no donor provenance, the donor is
    #: not on this machine, or the commit's own fix touches an operator-held path. Not a failure
    #: of the harness, and deliberately not counted as one.
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class Reference:
    """The task's own fix, re-derived — or the reason there is none.

    `diff is None` and a populated `reason` is the only other shape. A single optional string
    with an empty-means-fine convention would make "derived an empty patch" and "could not
    derive" the same value, and an empty patch is one `git apply` refuses, so the two would be
    told apart by a FAIL at `patch-apply` that looked exactly like a broken harness.
    """

    #: The commit's diff over its non-test paths, or `None` if it could not be derived.
    diff: str | None

    #: Why there is no diff, or an empty string when there is one.
    reason: str


@dataclass(frozen=True)
class Probe:
    """What the control arm observed about the harness on one (candidate, task).

    Recorded per candidate rather than once per task, and that is not redundancy: the whole claim
    is that the harness was intact **for the run this candidate's rollouts came from**, under the
    interpreter that run provisioned. A control taken once and reused across candidates would be
    evidence about whichever candidate happened to go first.

    `without_patch` and `with_reference` are `None` when that arm never ran — a skip, or a
    reference the first arm's failure made pointless to try — which is not the same as UNVERIFIED.
    """

    #: Which candidate's run this control belongs to.
    candidate: str

    #: The task the harness was checked on.
    task_id: str

    #: What was established. The field `harness_status` reduces.
    control: Control

    #: STRICT's status under `inert_patch()`. Must be FAIL for an intact harness.
    without_patch: Status | None

    #: STRICT's status under the re-derived reference. Must be PASS for an intact harness.
    with_reference: Status | None

    #: A sentence for whoever reads a BROKEN or a SKIPPED. Empty when the harness was intact.
    detail: str

    #: Wall-clock seconds the two arms took. Outside everything the verdict depends on, for the
    #: same reason `Rollout`'s clocks are: two runs of the same probe must compare equal.
    seconds: float


def reference_patch(task: Task) -> Reference:
    """Re-derive `task`'s own fix from its donor, or say why it cannot be had.

    Returns rather than raises, because every reason this can fail is an ordinary property of a
    corpus rather than a defect: a public task has no donor commit to diff, a private task's donor
    may not be on this machine, and a commit may legitimately touch a held path. Each of those is
    a skip with a name on it, and a raise would turn the first one into an aborted bake-off.

    The path set — and the pre-flight against `task.test_blobs` that guards it — comes from
    `sources.changed_paths`, the same derivation the rollout's oracle prompt is built from. Both
    the provenance keys read below are therefore known present: `changed_paths` refused the task
    otherwise, which is why they are indexed rather than fetched with a default.
    """
    changed = changed_paths(task)
    if changed.paths is None:
        return Reference(diff=None, reason=changed.reason)
    paths = changed.paths
    commit = task.provenance[_COMMIT]
    parent = task.provenance[_PARENT]
    donor = Path(task.repo_url)

    candidate = Candidate(
        sha=commit,
        parent=parent,
        # The three fields `gold_patch` does not read. `held_tests` is empty rather than the task's
        # blobs because the derivation above has already removed every test path, and handing them
        # over would invite a future reader to think this is where the exclusion happens.
        subject=task.problem_statement,
        held_tests=(),
        source_paths=tuple(paths),
        other_paths=(),
    )
    try:
        diff = gold_patch(donor, candidate)
    except (GitFailed, subprocess.SubprocessError, OSError) as exc:
        return Reference(
            diff=None,
            reason=(
                f"the reference patch for task {task.task_id!r} could not be produced: "
                f"{type(exc).__name__}: {exc}"
            ),
        )
    return Reference(diff=diff, reason="")


def probe(
    *,
    candidate: str,
    task: Task,
    sandbox_root: Path | str,
    timeout: float,
    interpreters: Interpreters,
) -> Probe:
    """Check that the harness discriminates on `task`, under this run's own provisioning.

    `interpreters` is the same cache the rollouts use, deliberately and by argument rather than by
    default: a control taken under a different interpreter than the rollouts it controls for
    proves something about an environment nobody scored against.

    The no-patch arm runs first. It is the arm that catches a task which was never red, it is the
    cheaper of the two, and its failure makes the reference arm pointless — a task whose tests
    already pass will pass under the fix as well, and reporting that PASS would read as
    reassurance.
    """
    started = time.perf_counter()
    reference = reference_patch(task)
    if reference.diff is None:
        return Probe(
            candidate=candidate,
            task_id=task.task_id,
            control=Control.SKIPPED,
            without_patch=None,
            with_reference=None,
            detail=reference.reason,
            seconds=time.perf_counter() - started,
        )

    acquired = interpreters.acquire(task)
    if acquired.failure is not None:
        # An environment that could not be built is a fact about the machine. Running the arms
        # anyway would charge it to the harness, and a BROKEN harness stops the whole run being
        # ranked — a far heavier consequence than the missing lockfile that actually happened.
        return Probe(
            candidate=candidate,
            task_id=task.task_id,
            control=Control.SKIPPED,
            without_patch=None,
            with_reference=None,
            detail=f"the environment for task {task.task_id!r} could not be built: "
            f"{acquired.failure}",
            seconds=time.perf_counter() - started,
        )

    def run(patch: str, arm: str) -> Status:
        # One directory per arm, and `run_id` deliberately left to its default. A deterministic
        # run id would name the directory helpfully and would collide the moment the same probe
        # ran twice into the same root — a re-probe after an interrupted night — where the second
        # clone fails and STRICT answers UNVERIFIED. A control arm that reported a *directory*
        # collision as a broken harness would stop a whole run being ranked for nothing.
        return verify_strict(
            task,
            patch,
            sandbox_root=Path(sandbox_root) / arm,
            timeout=timeout,
            interpreter=acquired.interpreter,
        ).status

    try:
        without_patch = run(inert_patch(), "without-patch")
        if without_patch is not Status.FAIL:
            return Probe(
                candidate=candidate,
                task_id=task.task_id,
                control=Control.BROKEN,
                without_patch=without_patch,
                with_reference=None,
                detail=(
                    f"task {task.task_id!r} reduced to {without_patch.value} with a patch that "
                    f"changes nothing any test can read. Either its declared failing test already "
                    f"passes at base_commit, or the tree under verification is not the tree the "
                    f"patch was applied to. Every candidate graded against it would be graded "
                    f"correct, so nothing in this run is evidence about any base"
                ),
                seconds=time.perf_counter() - started,
            )

        with_reference = run(reference.diff, "with-reference")
    except (subprocess.TimeoutExpired, OSError, RuntimeError) as exc:
        return Probe(
            candidate=candidate,
            task_id=task.task_id,
            control=Control.SKIPPED,
            without_patch=None,
            with_reference=None,
            detail=f"the control arm for task {task.task_id!r} could not be run: "
            f"{type(exc).__name__}: {exc}",
            seconds=time.perf_counter() - started,
        )

    if with_reference is not Status.PASS:
        return Probe(
            candidate=candidate,
            task_id=task.task_id,
            control=Control.BROKEN,
            without_patch=without_patch,
            with_reference=with_reference,
            detail=(
                f"task {task.task_id!r} reduced to {with_reference.value} under the very commit "
                f"it was mined from. No patch can pass it, so every candidate scores zero on it "
                f"for a reason that has nothing to do with any base"
            ),
            seconds=time.perf_counter() - started,
        )

    return Probe(
        candidate=candidate,
        task_id=task.task_id,
        control=Control.INTACT,
        without_patch=without_patch,
        with_reference=with_reference,
        detail="",
        seconds=time.perf_counter() - started,
    )


def harness_status(probes: Iterable[Probe]) -> Status:
    """`PASS` when the harness was shown to discriminate, `UNVERIFIED` otherwise.

    Three rules, and the third is the one that is easy to leave out:

    1. any `BROKEN` and the run is UNVERIFIED — a harness that graded one task wrongly is not a
       harness anything may be ranked off;
    2. no `INTACT` at all and the run is UNVERIFIED, even with nothing broken, because a run whose
       every probe was skipped has established nothing and "nothing went wrong" is not proof;
    3. otherwise PASS.

    `Status` rather than a bool, so the answer carries this project's own honesty vocabulary into
    whatever reports it: `UNVERIFIED` never counts as a win, and this is not a win.

    Returns a status about the **harness**, never about a model. It is not a number, it is not
    ranked, and nothing downstream may render it as a score.
    """
    seen = list(probes)
    if any(one.control is Control.BROKEN for one in seen):
        return Status.UNVERIFIED
    if not any(one.control is Control.INTACT for one in seen):
        return Status.UNVERIFIED
    return Status.PASS


__all__ = [
    "Control",
    "Probe",
    "Reference",
    "harness_status",
    "probe",
    "reference_patch",
]
