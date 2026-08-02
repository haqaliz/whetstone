"""One candidate across the task set: the control arm and the rollouts, in one checkpointed run.

This is where the two halves meet. `scoring.score` says what a candidate did on a task;
`control.probe` says whether the harness that graded it could grade anything at all. Kept apart,
the second is something a caller has to remember to run — and the caller who forgets is the one
publishing a column of zeroes with nothing to say about which kind of zero it is. So they are
issued together, per task, and stored together, and the run's status is the control arm's.

**The refusal is the point of `rankable`.** A run whose harness was not proven is not merely
labelled unusable, it is *unrankable*: the accessor raises rather than returning records with a
caveat attached, because a caveat is a thing downstream code reads past. Aspect 3 owns every
number in the published baseline and it obtains its records through here, so the one place a
number can come from is also the place that checks whether one is allowed to exist.

**The control runs before the rollout on each task, and the two share an interpreter.** Same
`Interpreters` cache, same acquired environment, same run: a control taken under a different
python than the rollouts it controls for is evidence about an environment nobody scored against.
Probing first also means a broken harness is visible from the first task rather than after a
night of generation.

**What this module does not do.** It does not count, total, rank, average, or write a report. It
returns records and one status *about the harness*. A convenience `solved` count here would
become a second definition of the headline the moment the report's own differed, and
`PREREGISTRATION.md` fixes that headline as a single quantity with a single definition.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from whetstone.bakeoff.control import Control, Probe, harness_status, probe
from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.journal import Journal, Step
from whetstone.bakeoff.scoring import Interpreters, Rollout, score
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status


class HarnessNotProven(RuntimeError):
    """The control arm did not establish that this run's harness grades anything.

    Raised by `rankable`, and raised rather than returned because the failure it guards against is
    a caller carrying on regardless. `UNVERIFIED` never counts as a win; it must not count as a
    loss either, and a run nobody proved is a run whose zeroes are not attributable to any base.
    """


@dataclass(frozen=True)
class Sweep:
    """What one candidate's run produced: every step, and the harness verdict over them.

    `status` is `PASS` only when the control arm proved the harness discriminated — see
    `control.harness_status`. It is a statement about the harness and never about the candidate,
    and nothing may render it as a score.
    """

    #: The base this run was of. Carried through unread; this module never parses it.
    candidate: str

    #: `PASS` when the harness was proven intact, `UNVERIFIED` otherwise. The gate on `rankable`.
    status: Status

    #: One per task, in the order the tasks were given, whether run now or replayed from disk.
    steps: tuple[Step, ...]

    @property
    def probes(self) -> tuple[Probe, ...]:
        """The control arm's records, in task order."""
        return tuple(step.probe for step in self.steps)

    @property
    def rollouts(self) -> tuple[Rollout, ...]:
        """Every rollout, ranked or not. Available unconditionally *because* they are findings.

        A broken harness does not make these records disappear — they are what a reader debugging
        the harness needs. It makes them unusable as evidence about a base, which is what
        `rankable` enforces and this property deliberately does not.
        """
        return tuple(step.rollout for step in self.steps)


def sweep(
    *,
    candidate: str,
    tasks: Sequence[Task],
    generator: Generator,
    sandbox_root: Path | str,
    timeout: float,
    interpreters: Interpreters,
    journal: Journal | None = None,
    pool: Path | None = None,
) -> Sweep:
    """Run `candidate` over `tasks`, checking the harness on each, resuming from `journal`.

    `journal=None` runs without a checkpoint, which is right for a test and wrong for a night.
    It is an explicit `None` rather than a default file path because a default would put a
    checkpoint somewhere the operator did not choose, and a second run would silently resume from
    a first one they had forgotten about.

    `pool` reaches the control arm **and the rollout** untouched, and nothing here reads it. It is
    the source-A pool holding the committed gold patches, consulted only for a task carrying no
    donor commit: `control.reference_patch` takes that task's reference from it, and
    `scoring.score` takes the file set the prompt shows from the same patch. Both halves or
    neither — a sweep that passed it to one would prove the harness grades a task the base was
    never asked. A sweep over source B alone never opens it.

    Exceptions from the generator are **not caught**. An interrupted run is an interrupted run: it
    stops, having checkpointed every pair it completed, and resumes where it stopped. Swallowing
    the failure would produce a full-looking record set in which some tasks were never attempted.
    """
    done = journal.replay() if journal is not None else {}
    root = Path(sandbox_root)

    steps: list[Step] = []
    for task in tasks:
        recorded = done.get((candidate, task.task_id))
        if recorded is not None:
            # Returned verbatim, never re-verified. Re-running a recorded step would make the
            # resumed run's records depend on when it resumed, which is the one property the
            # checkpoint exists to preserve.
            steps.append(recorded)
            continue

        # One directory per task so two tasks cannot land in each other's sandbox, and the control
        # under the same `interpreters` the rollout gets — the arm is only a control if it ran in
        # the environment it is a control for.
        here = root / task.task_id
        step = Step(
            probe=probe(
                candidate=candidate,
                task=task,
                sandbox_root=here / "control",
                timeout=timeout,
                interpreters=interpreters,
                pool=pool,
            ),
            rollout=score(
                candidate=candidate,
                task=task,
                generator=generator,
                sandbox_root=here / "rollout",
                timeout=timeout,
                interpreters=interpreters,
                pool=pool,
            ),
        )
        if journal is not None:
            journal.append(step)
        steps.append(step)

    return Sweep(
        candidate=candidate,
        status=harness_status(step.probe for step in steps),
        steps=tuple(steps),
    )


def rankable(run: Sweep) -> tuple[Rollout, ...]:
    """The rollouts a number may be derived from — or a refusal naming why none may be.

    The single door between this aspect and the report. It raises instead of returning a flag
    because a flag is something a caller reads past, and what it is guarding is the difference
    between publishing a measurement and publishing an artefact of a broken verifier.
    """
    if run.status is Status.PASS:
        return run.rollouts

    broken = [step.probe for step in run.steps if step.probe.control is Control.BROKEN]
    if broken:
        named = "; ".join(f"{one.task_id}: {one.detail}" for one in broken)
        raise HarnessNotProven(
            f"the control arm found the harness broken on {len(broken)} of {len(run.steps)} "
            f"tasks in {run.candidate!r}'s run, so nothing it measured is evidence about any "
            f"base and no ranking may be emitted from it — {named}"
        )
    raise HarnessNotProven(
        f"the control arm proved nothing about the harness in {run.candidate!r}'s run: none of "
        f"its {len(run.steps)} tasks reached INTACT, so there is no observation that this harness "
        f"can distinguish a patch that fixes the bug from one that does not. A run of zeroes "
        f"against an unproven harness is not a result about any base"
    )


__all__ = ["HarnessNotProven", "Sweep", "rankable", "sweep"]
