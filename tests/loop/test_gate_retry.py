"""The gate's liveness mechanism: the deterministic retry of tasks that reached no verdict.

`unverified == 0` is the honest term in the gate rule, and a gate demanding exactly zero of a
real machine would never fire: a flaky test, a sandbox that timed out, disk pressure — none of
them are statements about the checkpoint, and all of them make the term nonzero
(`docs/ROADMAP.md:429-443`). So each held-out task with no verdict retries a fixed `R` times
with **identical seed and inputs**, and a task that verifies on retry is verified.

What makes the retry safe is what it is *not* allowed to do:

- It never retries a **verdict**. `NO_DIFF`, `NOT_APPLIED`, `NOT_SOLVED`, `OUT_OF_SCOPE` are
  the candidate having been scored and failed; re-rolling them until one comes up SOLVED is
  the reward-hacking the whole project exists to refuse. Only `report._UNCOVERED` retries.
- It never re-generates. The retry replays the **recorded bytes** of the first attempt through
  `gate._Replay`, which refuses a prompt whose hash is not the one it recorded — so "identical
  inputs" is a check the code performs, not a property the reader is asked to trust.
- It never runs out of the operator's sight: `R` is a declared module constant, the retries
  used are recorded per task, and a task still unverified after `R` keeps the whole evaluation
  `UNVERIFIED` — not promoted, and not rejected either.

The flakiness here is simulated at exactly one seam — `gate._score_one`, the per-task scoring
call — because a genuinely flaky sandbox cannot be written down. Everything in front of and
behind that seam is the real path: the real prompts, the real extraction, the real `git apply`,
the real STRICT verifier, and the real decision core.

No model, no `mlx`, no network, no clock.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from loop.test_gate import _BULK, _INCUMBENT_SOLVES, _MEMBERS, _PRIVATE_IDS, _run_gate
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.loop import gate
from whetstone.loop.gate import Exit
from whetstone.verify.verdict import Status

#: The first held-out member — the task every flakiness table in this file picks on.
_FIRST = _MEMBERS[0]


def _flaky(
    monkeypatch: pytest.MonkeyPatch, failures: Mapping[tuple[str, str], int]
) -> dict[tuple[str, str], int]:
    """Make the first `n` scorings of `(side, task_id)` come back with no verdict.

    The real `_score_one` still runs — the prompt is rendered, the base is asked, the patch is
    extracted and verified — and only the *outcome* is overwritten, with the shape a timed-out
    sandbox produces (`UNVERIFIED` on both verifiers). That is the honest simulation: the first
    attempt really happened, so the recorder really holds its completion, and the retry really
    has identical bytes to replay.

    Returns the live attempt counter, keyed the same way, so a test can assert how many times
    the gate actually scored a task rather than trusting what it reports.
    """
    real = gate._score_one
    remaining = dict(failures)
    attempts: dict[tuple[str, str], int] = {}

    def patched(**kwargs: Any) -> Rollout:
        record = real(**kwargs)
        key = (str(kwargs["label"]).split(":")[0], str(kwargs["task"].task_id))
        attempts[key] = attempts.get(key, 0) + 1
        if remaining.get(key, 0) > 0:
            remaining[key] -= 1
            return replace(
                record,
                outcome=Outcome.UNVERIFIED,
                strict=Status.UNVERIFIED,
                weak=Status.UNVERIFIED,
                detail="simulated flaky sandbox",
            )
        return record

    monkeypatch.setattr(gate, "_score_one", patched)
    return attempts


def _counted(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], int]:
    """Count scorings per (side, task id) without touching a single outcome.

    The companion to `_flaky` for the tests that are about what the gate declines to do: a
    table that tampered with the outcome could not prove a task was left alone, because the
    tampering would be the thing that changed it.
    """
    real = gate._score_one
    attempts: dict[tuple[str, str], int] = {}

    def patched(**kwargs: Any) -> Rollout:
        key = (str(kwargs["label"]).split(":")[0], str(kwargs["task"].task_id))
        attempts[key] = attempts.get(key, 0) + 1
        return real(**kwargs)

    monkeypatch.setattr(gate, "_score_one", patched)
    return attempts


def _retries(outcome: gate.GateOutcome) -> dict[tuple[str, str], gate.RetryOutcome]:
    """The run's retry outcomes, keyed by (side, task id)."""
    return {(one.side, one.task_id): one for one in outcome.retries}


# --------------------------------------------------------------------------------------------
# Phase 1: a task that verifies on retry is verified; one that does not keeps the eval honest.
# --------------------------------------------------------------------------------------------


def test_a_task_that_verifies_on_retry_is_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1: one flaky held-out task, verified on its second attempt, and the eval proceeds.

    The candidate's first held-out task reaches no verdict once. Without the retry the whole
    evaluation would reduce to `UNVERIFIED` and nothing could ship — which is exactly the
    gate-never-fires failure the liveness items exist to prevent. With it, the task is scored
    a second time on identical bytes, reaches its verdict, and the known-better pair promotes.
    """
    attempts = _flaky(monkeypatch, {("candidate", _FIRST): 1})

    outcome, _fixtures = _run_gate(tmp_path)

    assert outcome.decision.exit is Exit.PROMOTED, outcome.decision.detail
    assert outcome.decision.unverified == 0, (
        "WHY THIS IS A FAILURE: a task that reached a verdict on retry was still counted "
        "unverified. A task that verifies on retry is verified (docs/ROADMAP.md:431-433)"
    )
    assert outcome.decision.solved_new == len(_MEMBERS)
    assert attempts[("candidate", _FIRST)] == 2, (
        f"WHY THIS IS A FAILURE: the flaky task was scored {attempts[('candidate', _FIRST)]} "
        "time(s). It reached no verdict once, so the gate must have retried it exactly once"
    )

    retry = _retries(outcome)[("candidate", _FIRST)]
    assert retry.retries_used == 1 and retry.before is Outcome.UNVERIFIED
    assert retry.after is Outcome.SOLVED and retry.verified is True
    assert outcome.retryable == (), (
        "WHY THIS IS A FAILURE: a task that verified on retry is still in the final "
        "no-verdict set. `retryable` is what remained unverified after the retries"
    )


def test_a_task_unverified_after_r_retries_makes_the_whole_eval_unverified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: `R` retries exhausted → `UNVERIFIED`, not promoted and not rejected.

    The flaky table outlasts the budget: the first attempt and every retry come back without a
    verdict. The comparison was therefore never actually made on that task, and the roadmap's
    third liveness item says what that means for the eval as a whole — it reduces to
    `UNVERIFIED` (`docs/ROADMAP.md:438-440`). The retries used are recorded, so the operator
    can read the budget was spent rather than skipped.
    """
    budget = 1 + gate.RETRY_COUNT
    attempts = _flaky(monkeypatch, {("candidate", _FIRST): budget})

    outcome, _fixtures = _run_gate(tmp_path)

    assert outcome.decision.exit is Exit.UNVERIFIED, outcome.decision.detail
    assert outcome.decision.unverified == 1
    assert attempts[("candidate", _FIRST)] == budget, (
        f"WHY THIS IS A FAILURE: the task was scored {attempts[('candidate', _FIRST)]} times "
        f"against a budget of one attempt plus R={gate.RETRY_COUNT} retries"
    )

    retry = _retries(outcome)[("candidate", _FIRST)]
    assert retry.retries_used == gate.RETRY_COUNT and retry.verified is False
    assert retry.after is Outcome.UNVERIFIED
    assert [(one.side, one.task_id) for one in outcome.retryable] == [("candidate", _FIRST)], (
        "WHY THIS IS A FAILURE: the task that outlasted the budget is not in the final "
        "no-verdict set — the set the gate reports as what it could not decide on"
    )


def test_the_retry_never_runs_more_than_the_declared_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`R` is a ceiling, not a suggestion: an always-flaky task stops after `R` retries.

    Asserted separately from the exit because the two failures look identical from the outside:
    an eval that gave up too early and one that retried forever both end `UNVERIFIED`, and only
    the attempt count tells them apart.
    """
    attempts = _flaky(monkeypatch, {("candidate", _FIRST): 500})

    outcome, _fixtures = _run_gate(tmp_path)

    assert outcome.decision.exit is Exit.UNVERIFIED
    assert attempts[("candidate", _FIRST)] == 1 + gate.RETRY_COUNT


def test_the_retry_budget_is_spent_per_task_not_per_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two flaky tasks each get their own `R`, and both recover — the budget is not shared.

    A run-wide budget would make the gate's liveness depend on how many tasks happened to
    wobble, which is a property of the machine rather than of the checkpoint.
    """
    second = _MEMBERS[1]
    attempts = _flaky(
        monkeypatch, {("candidate", _FIRST): 1, ("candidate", second): gate.RETRY_COUNT}
    )

    outcome, _fixtures = _run_gate(tmp_path)

    assert outcome.decision.exit is Exit.PROMOTED, outcome.decision.detail
    assert attempts[("candidate", _FIRST)] == 2
    assert attempts[("candidate", second)] == 1 + gate.RETRY_COUNT
    assert _retries(outcome)[("candidate", second)].retries_used == gate.RETRY_COUNT


def test_both_sides_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The incumbent's flaky tasks retry too — the mechanism is per side, not per candidate.

    An incumbent left un-retried would let a wobbling machine manufacture a promotion: the
    incumbent's lost solve would reduce the eval to `UNVERIFIED` at best and, if the term were
    read less carefully, flatter the candidate's margin at worst.
    """
    attempts = _flaky(monkeypatch, {("incumbent", _FIRST): 1})

    outcome, _fixtures = _run_gate(tmp_path)

    assert outcome.decision.exit is Exit.PROMOTED, outcome.decision.detail
    assert outcome.decision.solved_old == _INCUMBENT_SOLVES
    assert attempts[("incumbent", _FIRST)] == 2
    assert _retries(outcome)[("incumbent", _FIRST)].side == "incumbent"


def test_a_no_verdict_task_with_no_first_attempt_is_never_retried(tmp_path: Path) -> None:
    """A `NO_ORACLE` task is not retryable: there is nothing to replay, so nothing is re-run.

    The retry is *verification* re-execution of recorded bytes. A task no prompt was ever
    rendered for has no recorded bytes, so a "retry" of it would be a fresh generation — a
    different experiment wearing the same name. It stays unverified, and the eval reduces to
    `UNVERIFIED`, which is the honest outcome: the gate's default is don't promote.
    """
    private_ids = (*_PRIVATE_IDS, "t-12")
    members = (*_MEMBERS[:9], "t-12")

    outcome, _fixtures = _run_gate(
        tmp_path, private_ids=private_ids, members=members, bulk=_BULK, incumbent_solve=9
    )

    assert outcome.decision.exit is Exit.UNVERIFIED, outcome.decision.detail
    assert all(one.task_id != "t-12" for one in outcome.retries), (
        "WHY THIS IS A FAILURE: a task with no rendered prompt was retried. There is no "
        "recorded completion to replay, so the retry would be a new generation"
    )
    assert {one.task_id for one in outcome.retryable} == {"t-12"}


def test_a_fail_is_never_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: a verdict is final. A `NO_DIFF` task is scored once and stays a FAIL.

    The candidate answers prose for the last held-out task, so its rollout is `NO_DIFF` — a
    real verdict, reached by the real extractor. The counter proves the gate asked about that
    task exactly once. This is the whole reason the retry predicate is `report._UNCOVERED` and
    not "anything that is not SOLVED": re-rolling a graded zero until it comes up green is
    manufacturing a win, and the gate must be structurally unable to do it.
    """
    lost = _MEMBERS[-1]
    attempts = _counted(monkeypatch)

    outcome, _fixtures = _run_gate(
        tmp_path, candidate_solve=len(_MEMBERS) - 1, incumbent_solve=len(_MEMBERS)
    )

    assert outcome.decision.exit is Exit.REJECTED, outcome.decision.detail
    assert outcome.decision.regressed == 1 and outcome.decision.unverified == 0
    assert attempts[("candidate", lost)] == 1, (
        f"WHY THIS IS A FAILURE: the FAIL task was scored "
        f"{attempts[('candidate', lost)]} times. NO_DIFF is a verdict — the candidate was "
        "scored and failed — and a verdict is never retried"
    )
    assert outcome.retries == (), (
        "WHY THIS IS A FAILURE: a FAIL was recorded as retried. Only the no-verdict set "
        "(report._UNCOVERED, by identity) is retryable"
    )
