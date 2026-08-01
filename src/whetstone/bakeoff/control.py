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

**Source A has no donor, so it has a second route — and the record says which one it took.** A
SWE-bench instance is a dataset row: its fixing commit is not on this machine and its `provenance`
carries an `instance_id` rather than a `commit`, so there is nothing to diff. Its gold patch is
committed instead, in the source-A pool, and this module reads it from there — the fallback
`docs/planning/p1-baseline-bakeoff/scoring-harness/spec.md:34` declared before any of this ran.
The first scored bake-off aborted for want of it: the public task's probe was SKIPPED, source A's
run reached no INTACT at all, and `sweep.rankable` refused the whole night's records.

Three things about that route are deliberate:

* **the pool is an argument, never a path this module knows.** A hardcoded `tasks/public/pool.json`
  would make every test either read a 3.2 MB committed artefact or exercise a different code path
  from the one that runs at night;
* **source B never falls back to it.** A private task whose donor is missing is a skip about the
  donor. Reaching into a public dataset on an id collision would control it against a patch for
  another repository entirely, and the INTACT that earned would be about neither;
* **`Origin` is recorded.** "Re-derived from the user's own donor" and "read out of a committed
  dataset nobody here re-derived" are different provenance, and a report publishing both as *the
  task's own reference patch* would be claiming the stronger of the two for both.

There is no second definition of "the commit's own fix" hiding in that route, because for source A
nothing is derived: the patch is given. The only thing derived from it is which paths it touches,
and that is asked of `verify.repo.declared_paths` — git's own parse, the same one STRICT's scope
check runs on the patch it is about to apply.

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
import tempfile
import time
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from whetstone.bakeoff.scoring import Interpreters
from whetstone.bakeoff.sources import changed_paths
from whetstone.tasks.derive import gold_patch
from whetstone.tasks.donor import Candidate, GitFailed
from whetstone.tasks.fetch import read_pool
from whetstone.tasks.liveness import inert_patch
from whetstone.verify.repo import PatchError, declared_paths
from whetstone.verify.strict import verify_strict
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status

#: The provenance key naming the commit a task was mined from. Read here only to build the
#: `Candidate` `gold_patch` diffs; the derivation that decides whether it is usable at all lives
#: in `whetstone.bakeoff.sources`.
_COMMIT = "commit"
_PARENT = "parent"

#: The provenance key a source-A manifest carries in place of a commit. `whetstone.tasks.public`
#: writes the instance id into both this key and `task_id`; both are consulted below, in that
#: order, so a manifest that ever stops using its instance id as its task id still resolves.
_INSTANCE = "instance_id"


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

    #: No reference patch could be obtained — the donor is not on this machine, the source-A pool
    #: does not carry the instance (or was never offered), or the fix touches an operator-held
    #: path. Not a failure of the harness, and deliberately not counted as one.
    SKIPPED = "SKIPPED"


class Origin(str, Enum):
    """Where a reference patch came from. Recorded, never inferred from the source afterwards.

    `str` mixin for the same reason `Control` has one: it serialises as its name into the journal
    and reads as itself in a report.

    The two live routes are not equally strong evidence, which is the whole reason this exists.
    `DONOR` means the diff was computed here, now, from a commit on this machine. `POOL` means it
    was read verbatim out of a committed dataset artefact that nobody in this project re-derived
    from anything. Publishing both as "the task's own reference patch" would claim the first for
    the second.
    """

    #: Re-derived from `provenance.commit` against `provenance.parent` in the task's own donor.
    DONOR = "DONOR"

    #: Read from the source-A pool's `patch` field, keyed by instance id. Source A only.
    POOL = "POOL"

    #: No reference was obtained. Distinct from the two above rather than folded into a `None`,
    #: so a skip can never be read off the record as a derivation that happened.
    NONE = "NONE"


@dataclass(frozen=True)
class Reference:
    """The task's own fix — re-derived or read — or the reason there is none.

    `diff is None` and a populated `reason` is the only other shape. A single optional string
    with an empty-means-fine convention would make "derived an empty patch" and "could not
    derive" the same value, and an empty patch is one `git apply` refuses, so the two would be
    told apart by a FAIL at `patch-apply` that looked exactly like a broken harness.
    """

    #: The commit's diff over its non-test paths, or `None` if it could not be obtained.
    diff: str | None

    #: Why there is no diff, or an empty string when there is one.
    reason: str

    #: Which of the two routes produced `diff`, or `NONE` when neither did.
    origin: Origin


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

    #: Where that reference came from, so a report can disclose that source A's control ran
    #: against a committed gold patch while source B's was re-derived from the user's own donor.
    origin: Origin

    #: A sentence for whoever reads a BROKEN or a SKIPPED. Empty when the harness was intact.
    detail: str

    #: Wall-clock seconds the two arms took. Outside everything the verdict depends on, for the
    #: same reason `Rollout`'s clocks are: two runs of the same probe must compare equal.
    seconds: float


def reference_patch(task: Task, *, pool: Path | None = None) -> Reference:
    """Obtain `task`'s own fix — from its donor, or from the pool — or say why it cannot be had.

    Returns rather than raises, because every reason this can fail is an ordinary property of a
    corpus rather than a defect: a donor may not be on this machine, a commit may legitimately
    touch a held path, and a pool may not carry the instance it was asked for. Each of those is a
    skip with a name on it, and a raise would turn the first one into an aborted bake-off.

    **The route is chosen by what the task carries, and only by that.** A donor commit means the
    donor route; no donor commit means the pool. There is no falling back from one to the other,
    in either direction: a private task whose donor is gone must not be controlled against a public
    dataset's patch for a repository that merely shares an id, and a public instance has nothing to
    re-derive from in the first place.
    """
    if not (task.provenance.get(_COMMIT) and task.provenance.get(_PARENT)):
        return _from_pool(task, pool)
    return _from_donor(task)


def _from_donor(task: Task) -> Reference:
    """Source B's route: the commit's own diff over its non-test paths, computed now.

    The path set — and the pre-flight against `task.test_blobs` that guards it — comes from
    `sources.changed_paths`, the same derivation the rollout's oracle prompt is built from. Both
    the provenance keys read below are therefore known present: the caller checked, and
    `changed_paths` refuses the task otherwise, which is why they are indexed rather than fetched
    with a default.
    """
    changed = changed_paths(task)
    if changed.paths is None:
        return Reference(diff=None, reason=changed.reason, origin=Origin.NONE)
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
                f"the reference patch for task {task.task_id!r} could not be produced from its "
                f"donor at {str(donor)!r}: {type(exc).__name__}: {exc}"
            ),
            origin=Origin.NONE,
        )
    return Reference(diff=diff, reason="", origin=Origin.DONOR)


def _from_pool(task: Task, pool: Path | None) -> Reference:
    """Source A's route: the instance's committed gold patch, read verbatim from `pool`.

    Verbatim, and that is the point — SWE-bench splits each record into `patch` and `test_patch`
    precisely so the gold fix touches no test, so there is nothing here to filter and filtering
    would be this project quietly editing a dataset's answer. What there *is* to check is that the
    given diff stays inside the task's scope, and the pre-flight below is the same one the donor
    route gets for the same reason: a patch touching an operator-held path is refused by STRICT
    before anything runs, and the control arm would record that refusal — the reward's cheat-scope
    check working exactly as designed — as "the harness cannot reach PASS", and un-rank the run.

    The paths are read by `git apply --numstat`, which parses and reports without writing, so the
    scratch directory it runs in need not be a repository and nothing is applied anywhere. It is
    the same parse STRICT itself performs on the patch it is about to apply; a second parser here
    would be a second answer to "what does this diff touch", and the one that disagreed would be
    the one nobody looked at.
    """
    instance = str(task.provenance.get(_INSTANCE) or task.task_id)
    if pool is None:
        return Reference(
            diff=None,
            reason=(
                f"task {task.task_id!r} carries no donor commit in its provenance and no source-A "
                f"pool was offered, so there is no fix to control the harness with: its gold patch "
                f"lives in the pool, keyed by instance {instance!r}, and nothing here was told "
                f"where that pool is"
            ),
            origin=Origin.NONE,
        )

    try:
        instances = read_pool(Path(pool))
    except ValueError as exc:
        return Reference(
            diff=None,
            reason=f"the source-A pool for task {task.task_id!r} could not be read: {exc}",
            origin=Origin.NONE,
        )

    found = [one for one in instances if one.instance_id == instance]
    if not found or not found[0].patch.strip():
        return Reference(
            diff=None,
            reason=(
                f"the source-A pool at {str(pool)!r} carries no usable gold patch for instance "
                f"{instance!r} of task {task.task_id!r} ({len(instances)} instances read), so the "
                f"harness cannot be shown to reach PASS on it and nothing measured on this task is "
                f"evidence about any base"
            ),
            origin=Origin.NONE,
        )
    diff = found[0].patch

    try:
        with tempfile.TemporaryDirectory(prefix="whetstone-pool-") as scratch:
            touched = declared_paths(diff, Path(scratch))
    except (PatchError, subprocess.SubprocessError, OSError) as exc:
        return Reference(
            diff=None,
            reason=(
                f"the gold patch for instance {instance!r} of task {task.task_id!r} could not be "
                f"parsed: {type(exc).__name__}: {exc}"
            ),
            origin=Origin.NONE,
        )

    collisions = sorted(set(touched) & set(task.test_blobs))
    if collisions:
        return Reference(
            diff=None,
            reason=(
                f"the gold patch for instance {instance!r} of task {task.task_id!r} touches "
                f"operator-held {collisions}, which STRICT refuses as a cheat before anything "
                f"runs. Using it as a reference would report the reward's own scope check as `the "
                f"harness cannot reach PASS` and take the whole run's ranking with it"
            ),
            origin=Origin.NONE,
        )
    return Reference(diff=diff, reason="", origin=Origin.POOL)


def probe(
    *,
    candidate: str,
    task: Task,
    sandbox_root: Path | str,
    timeout: float,
    interpreters: Interpreters,
    pool: Path | None = None,
) -> Probe:
    """Check that the harness discriminates on `task`, under this run's own provisioning.

    `interpreters` is the same cache the rollouts use, deliberately and by argument rather than by
    default: a control taken under a different interpreter than the rollouts it controls for
    proves something about an environment nobody scored against.

    `pool` is the source-A pool, and it is an argument for the same reason: a path this module knew
    by heart would be a 3.2 MB committed artefact that every test either reads or routes around.
    It is consulted only for a task carrying no donor commit, so passing it changes nothing about
    source B, and omitting it makes every source-A probe a skip that says so.

    The no-patch arm runs first. It is the arm that catches a task which was never red, it is the
    cheaper of the two, and its failure makes the reference arm pointless — a task whose tests
    already pass will pass under the fix as well, and reporting that PASS would read as
    reassurance.
    """
    started = time.perf_counter()
    reference = reference_patch(task, pool=pool)
    if reference.diff is None:
        return Probe(
            candidate=candidate,
            task_id=task.task_id,
            control=Control.SKIPPED,
            without_patch=None,
            with_reference=None,
            origin=reference.origin,
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
            origin=reference.origin,
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
                origin=reference.origin,
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
            origin=reference.origin,
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
            origin=reference.origin,
            detail=(
                f"task {task.task_id!r} reduced to {with_reference.value} under its own reference "
                f"patch, taken from {reference.origin.value}. No patch can pass it, so every "
                f"candidate scores zero on it for a reason that has nothing to do with any base"
            ),
            seconds=time.perf_counter() - started,
        )

    return Probe(
        candidate=candidate,
        task_id=task.task_id,
        control=Control.INTACT,
        without_patch=without_patch,
        with_reference=with_reference,
        origin=reference.origin,
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
    "Origin",
    "Probe",
    "Reference",
    "harness_status",
    "probe",
    "reference_patch",
]
