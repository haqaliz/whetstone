"""One candidate across the task set, checkpointed — and the two zeroes that must not look alike.

This file holds the assertion the whole bake-off rests on. A base that writes **no diff at all**
produces a run of zeroes. A **broken harness** produces the same run of zeroes. Read off the
rollout records alone the two are byte-identical, and they are the two findings P1 has to choose
between: one says change the base, the other says fix the verifier before believing anything.

So the adversarial test below runs a generator stubbed to return **no diff whatever** — the
weakest possible base, guaranteed to score zero — twice: once where the harness is sound and once
where it is not. The rollouts are identical across both, deliberately and assertedly, and the runs
are still told apart, because the control arm is carried alongside them and the run's own status
falls to UNVERIFIED when a control fails. A run that cannot be ranked must also be *unrankable*
rather than merely labelled, so the accessor refuses rather than returning records with a warning
attached.

**Resumability is the other half, and it is not a convenience.** A bake-off over 66 tasks times
several candidates, each rollout a sandboxed pytest run, is an overnight job. An interruption that
cost the whole night would mean the P1 base decision waits another day per crash. So each
(candidate, task) is checkpointed once both its control and its rollout are in hand, and a resumed
run replays what is on disk instead of re-running it. The property that makes that safe is
asserted directly: **resuming produces the record set an uninterrupted run would have produced.**
Anything weaker and a resumed run is a different experiment from the one that was pre-registered.

**No model, no `mlx`, no network.** Every base here is `StubGenerator`; the tasks are two-commit
synthetic donors built with real git in `tmp_path`.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from fixtures.repos.mined import build_mined_task

from whetstone.bakeoff.control import Control, reference_patch
from whetstone.bakeoff.generator import StubGenerator, UnstubbedPrompt
from whetstone.bakeoff.journal import Journal, Step
from whetstone.bakeoff.rendering import render_prompt
from whetstone.bakeoff.scoring import Interpreters, Outcome
from whetstone.bakeoff.sources import oracle_sources
from whetstone.bakeoff.sweep import HarnessNotProven, Sweep, rankable, sweep
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status

#: Generous enough that a two-commit donor with one module and one pytest file can never reach it.
TIMEOUT = 120.0

#: What a base says when it has nothing to offer: prose, no fence, no diff header. The shape
#: `extract_patch` reports as no-diff, and therefore a guaranteed zero with no verifier entered.
REFUSAL = "I could not work out what is wrong with this repository, so I have made no change."


def posed(task: Task) -> str:
    """The prompt `score` renders for `task`, oracle sources included.

    The stubs here are keyed on the exact prompt string, so a test rendering the pre-oracle
    prompt would build a table the harness never hits and would die on `UnstubbedPrompt` instead
    of asserting anything about the sweep.
    """
    sources = oracle_sources(task)
    assert sources.files is not None, sources.reason
    return render_prompt(task, sources.files)


def _run(
    tmp_path: Path,
    tasks: list[Task],
    *,
    candidate: str,
    answers: dict[str, str],
    journal: Journal | None = None,
    where: str,
) -> Sweep:
    """Run one candidate across `tasks`, with `answers` keyed by rendered prompt."""
    return sweep(
        candidate=candidate,
        tasks=tasks,
        generator=StubGenerator(answers),
        sandbox_root=tmp_path / where,
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / f"{where}-envs"),
        journal=journal,
    )


def test_a_broken_harness_and_an_honest_zero_are_told_apart(tmp_path: Path) -> None:
    """The weakest possible base, run twice: sound harness and broken harness must not match.

    The generator returns no diff at all, so **every rollout in both runs is `NO_DIFF`** — the
    test asserts that, because the whole difficulty is that the rollouts cannot tell these two
    runs apart and a reader who only had them would conclude the same thing about both. The
    distinction has to come from somewhere else, and the somewhere else is the control arm.

    The broken run's task is one whose declared failing test already passes at `base_commit`: the
    inert patch reaches PASS, the harness grades nothing, and every candidate scored against it —
    including this one — would have its zeroes mean nothing at all.
    """
    sound = build_mined_task(tmp_path / "sound", task_id="sound").task
    broken = build_mined_task(tmp_path / "broken", task_id="broken", vacuous=True).task

    honest = _run(
        tmp_path,
        [sound],
        candidate="says-nothing",
        answers={posed(sound): REFUSAL},
        where="honest",
    )
    unusable = _run(
        tmp_path,
        [broken],
        candidate="says-nothing",
        answers={posed(broken): REFUSAL},
        where="unusable",
    )

    outcomes = {step.rollout.outcome for step in (*honest.steps, *unusable.steps)}
    assert outcomes == {Outcome.NO_DIFF}, (
        "WHY THIS IS A FAILURE: this test's premise is that both runs produce identical, "
        "uniformly zero rollouts, so that the distinction between them can only come from the "
        f"control arm. It does not hold here ({outcomes}), and the assertions below would pass "
        "for the wrong reason"
    )

    assert (honest.status, unusable.status) == (Status.PASS, Status.UNVERIFIED), (
        "WHY THIS IS A FAILURE: an honest all-zero run and a run whose harness grades nothing "
        "came back with the same status, so nothing in the output distinguishes `these bases are "
        "too weak` from `this verifier never worked`. Those are opposite findings with opposite "
        f"fixes, and P1's pivot decision rests on telling them apart. Got {honest.status!r} and "
        f"{unusable.status!r}"
    )
    assert unusable.steps[0].probe.control is Control.BROKEN, (
        "WHY THIS IS A FAILURE: the run was marked unusable without recording which task's "
        f"control failed or how, leaving nobody anything to go and fix. Got "
        f"{unusable.steps[0].probe!r}"
    )

    assert rankable(honest) == honest.rollouts, (
        "WHY THIS IS A FAILURE: a run whose harness was proven intact must hand its records over "
        "for ranking. A control arm that refused everything would be a control arm nobody keeps"
    )
    with pytest.raises(HarnessNotProven) as refusal:
        rankable(unusable)
    assert "broken" in str(refusal.value), (
        "WHY THIS IS A FAILURE: the refusal does not name the task whose control failed, so the "
        f"operator is told only that something is wrong. Got {str(refusal.value)!r}"
    )


def test_resuming_produces_the_record_set_an_uninterrupted_run_would_have(tmp_path: Path) -> None:
    """An interrupted overnight run resumes; it does not restart, and it does not drift.

    The interruption is real rather than simulated: the base is stubbed with answers for the first
    two tasks only, so the third rollout raises and the run dies with two (candidate, task) pairs
    checkpointed. The resumed run is then given the full set of answers and the same journal.

    Equality is asserted **with the three clocks zeroed**, which is the honest comparison and not
    a weakening of it: a replayed record carries the duration from when it was actually produced,
    and demanding those match a second, fresh measurement would be demanding that two different
    wall-clock readings be identical. Everything the outcome depends on is compared exactly —
    `StrictResult` carries no durations for precisely this reason.
    """
    # Distinct subjects, because `render_prompt` reads the problem statement and the failing node
    # ids and nothing else: three tasks differing only in `task_id` would render one prompt, the
    # stub would answer all three the same way, and the interruption below could not be aimed.
    tasks = [
        build_mined_task(
            tmp_path / f"task-{index}", task_id=f"t{index}", subject=f"Fix addition ({index})"
        ).task
        for index in "123"
    ]

    solved = reference_patch(tasks[0]).diff
    assert solved is not None, "the fixture's own reference patch must be derivable"
    answers = {posed(tasks[0]): solved} | {posed(task): REFUSAL for task in tasks[1:]}
    partial = {
        prompt: answer for prompt, answer in answers.items() if prompt != posed(tasks[2])
    }

    journal = Journal(path=tmp_path / "night.jsonl")
    with pytest.raises(UnstubbedPrompt):
        _run(
            tmp_path, tasks, candidate="base-a", answers=partial, journal=journal, where="crashed"
        )

    checkpointed = journal.replay()
    assert len(checkpointed) == 2, (
        "WHY THIS IS A FAILURE: the run died after completing two of three tasks and the journal "
        f"holds {len(checkpointed)} of them. Fewer and the night's completed work is lost on every "
        "interruption; more and a task that never finished was recorded as if it had, which is a "
        "record of something that did not happen"
    )

    resumed = _run(
        tmp_path, tasks, candidate="base-a", answers=answers, journal=journal, where="resumed"
    )
    uninterrupted = _run(tmp_path, tasks, candidate="base-a", answers=answers, where="fresh")

    assert _untimed(resumed.steps) == _untimed(uninterrupted.steps), (
        "WHY THIS IS A FAILURE: a resumed run and an uninterrupted run over the same inputs "
        "produced different records. Whatever the resumed run measured is then a different "
        "experiment from the one that was pre-registered, and every number derived from a night "
        f"that crashed once is uncomparable to one that did not.\n{resumed.steps}\n"
        f"{uninterrupted.steps}"
    )
    assert resumed.status is uninterrupted.status is Status.PASS, (
        "WHY THIS IS A FAILURE: the control arm's verdict did not survive resumption, so an "
        "interrupted night would be unrankable for no reason other than having been interrupted"
    )
    assert resumed.steps[0].rollout.outcome is Outcome.SOLVED, (
        "WHY THIS IS A FAILURE: the one record in this run that carries a real verdict came back "
        f"as {resumed.steps[0].rollout.outcome!r} after being replayed from disk. A checkpoint "
        "that cannot round-trip a win is a checkpoint that turns solved tasks into zeroes"
    )


def _untimed(steps: tuple[Step, ...]) -> list[Step]:
    """`steps` with every wall-clock reading set to zero — see the docstring above."""
    return [
        dataclasses.replace(
            step,
            probe=dataclasses.replace(step.probe, seconds=0.0),
            rollout=dataclasses.replace(
                step.rollout, generation_seconds=0.0, strict_seconds=0.0, weak_seconds=0.0
            ),
        )
        for step in steps
    ]
