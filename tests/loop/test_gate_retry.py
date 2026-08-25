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


# --------------------------------------------------------------------------------------------
# Phase 2: determinism, the credulous-retry differential, and the liveness the operator reads.
# --------------------------------------------------------------------------------------------


def _flips(
    monkeypatch: pytest.MonkeyPatch, wins: Mapping[tuple[str, str], int]
) -> dict[tuple[str, str], int]:
    """Make the `n`-th and later scorings of `(side, task_id)` come back `SOLVED`.

    A verifier that changes its mind — the threat model the retry predicate exists to refuse.
    Nothing in the real harness behaves like this; that is the point. If the gate were willing
    to re-score a task it had already graded, this is the machine on which it would
    manufacture a win, and the differential below measures exactly that willingness.
    """
    real = gate._score_one
    attempts: dict[tuple[str, str], int] = {}

    def patched(**kwargs: Any) -> Rollout:
        record = real(**kwargs)
        key = (str(kwargs["label"]).split(":")[0], str(kwargs["task"].task_id))
        attempts[key] = attempts.get(key, 0) + 1
        if attempts[key] >= wins.get(key, 0) > 0:
            return replace(record, outcome=Outcome.SOLVED, strict=Status.PASS, weak=Status.PASS)
        return record

    monkeypatch.setattr(gate, "_score_one", patched)
    return attempts


def _retry_payload(outcome: gate.GateOutcome) -> Any:
    """The record's retry half — the three facts, read back off disk."""
    import json

    document = json.loads(outcome.record.read_text(encoding="utf-8"))
    return {
        "retry_count": document["retry_count"],
        "retries_used": document["retries_used"],
        "retries": document["retries"],
        "unverified_after_retries": document["unverified_after_retries"],
    }


def test_the_credulous_retry_loses_the_differential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: retrying anything-not-SOLVED converts a regression into a promotion. It must not.

    The differential, watched failing against the credulous predicate. Both sides solve nine
    of the ten held-out tasks and both answer prose for the tenth, so the honest answer is
    `rejected` by the `>` term: the candidate is not better. On a machine whose verifier would
    come up SOLVED the second time it is asked, a gate that retries verdicts turns that tenth
    `NO_DIFF` into a solve and **promotes a candidate that is not better than its incumbent**.
    The shipped predicate — `report._UNCOVERED`, by identity — never asks a second time, so
    the same machine yields `rejected`. This is the reward-hacking the project exists to
    refuse, and the test is here so that a later "why not retry everything, it is only fairer"
    cannot land quietly.
    """
    lost = _MEMBERS[-1]
    arguments: dict[str, Any] = {
        "candidate_solve": len(_MEMBERS) - 1,
        "incumbent_solve": len(_MEMBERS) - 1,
    }

    _flips(monkeypatch, {("candidate", lost): 2})
    shipped, _fixtures = _run_gate(tmp_path / "shipped", **arguments)

    assert shipped.decision.exit is Exit.REJECTED, shipped.decision.detail
    assert shipped.decision.solved_new == shipped.decision.solved_old == len(_MEMBERS) - 1

    monkeypatch.undo()
    _flips(monkeypatch, {("candidate", lost): 2})
    monkeypatch.setattr(gate, "_is_retryable", lambda outcome: outcome is not Outcome.SOLVED)
    credulous, _fixtures = _run_gate(tmp_path / "credulous", **arguments)

    assert credulous.decision.exit is Exit.PROMOTED, (
        "WHY THIS IS A FAILURE: the credulous retry did not change the answer, so this test "
        "proves nothing about the shipped predicate. The differential must be real — a "
        "credulous gate must actually manufacture the win the shipped one refuses"
    )
    assert credulous.decision.solved_new == len(_MEMBERS)


def test_the_retry_never_regenerates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A retry re-verifies; it never re-asks the base. Measured on the stub's own call log.

    `_Replay` answers from the recording, so the base behind the engine seam is asked each
    prompt exactly once no matter how many times a task is scored. This is what makes
    "identical inputs" a fact rather than an argument about greedy sampling: the second
    verification runs the *same bytes*, because no second generation ever happened.

    Counted at `_CompletionRecorder.generate`, which is the only path to the engine's
    generator — a replay never reaches it.
    """
    asked: list[str] = []
    real_generate = gate._CompletionRecorder.generate

    def counting(self: Any, prompt: str) -> str:
        asked.append(prompt)
        return str(real_generate(self, prompt))

    monkeypatch.setattr(gate._CompletionRecorder, "generate", counting)
    _flaky(monkeypatch, {("candidate", _FIRST): gate.RETRY_COUNT})

    outcome, _fixtures = _run_gate(tmp_path)

    assert _retries(outcome)[("candidate", _FIRST)].retries_used == gate.RETRY_COUNT
    scored = len(_MEMBERS) + 1
    assert len(asked) == 2 * scored, (
        f"WHY THIS IS A FAILURE: the base was asked {len(asked)} times to score "
        f"{scored} tasks on each of two sides. A retry replays the first attempt's recorded "
        "completion — a second generation would be a different experiment scored under the "
        "name of a retry"
    )


def test_the_replay_refuses_a_prompt_that_is_not_the_recorded_one() -> None:
    """The identical-inputs pin is a check, not a comment: a different prompt is refused.

    Asserted directly on `_Replay` rather than through a run, because the whole value of the
    check is that it fires on a path no fixture can reach today — it is the guard against a
    later change that renders the retry's prompt differently from the first attempt's.
    """
    from whetstone.bakeoff.rendering import prompt_hash

    recorded = "the first attempt's prompt"
    replay = gate._Replay(
        task_id="t-01", prompt_sha256=prompt_hash(recorded), completion="a patch"
    )

    assert replay.generate(recorded) == "a patch"

    with pytest.raises(gate.RetryInputsChanged) as refusal:
        replay.generate("a different question entirely")
    assert "t-01" in str(refusal.value)
    assert prompt_hash(recorded)[:12] in str(refusal.value), (
        "WHY THIS IS A FAILURE: the refusal does not name the hash it expected. A retry that "
        "was posed the wrong prompt is a defect in the gate, and a refusal an operator "
        "cannot trace to two hashes is a refusal nobody can act on"
    )


def test_the_retry_sequence_is_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: same inputs → same retry sequence, and the same recorded retry half.

    Determinism holds here by construction — the retry replays recorded bytes through a
    greedy path — and that is exactly why it is pinned: a future change that reached for a
    fresh generation, a clock, or a set's iteration order would still look correct in every
    other test in this file, and would break only this one.
    """
    first_attempts = _flaky(monkeypatch, {("candidate", _FIRST): 1, ("incumbent", _FIRST): 500})
    first, _fixtures = _run_gate(tmp_path / "one")

    monkeypatch.undo()
    second_attempts = _flaky(monkeypatch, {("candidate", _FIRST): 1, ("incumbent", _FIRST): 500})
    second, _fixtures = _run_gate(tmp_path / "two")

    assert first_attempts == second_attempts
    assert first.retries == second.retries
    assert first.retryable == second.retryable
    assert _retry_payload(first) == _retry_payload(second), (
        "WHY THIS IS A FAILURE: two runs on identical inputs recorded different retry "
        "evidence. The promotion record is the accumulated verified-improvement trail, and a "
        "trail that differs between two renders of the same command is not evidence"
    )


def test_the_record_carries_the_declared_budget_what_it_spent_and_what_it_could_not_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The three retry facts, on disk: `R`, the per-task spend, and the survivors.

    A total alone would hide the difference between many tasks wobbling once and one task
    wobbling every time, which are very different facts about the machine — and the machine
    is what the roadmap says to fix when the gate cannot fire (`docs/ROADMAP.md:441-443`).
    """
    second = _MEMBERS[1]
    _flaky(monkeypatch, {("candidate", _FIRST): 1, ("candidate", second): 500})

    outcome, _fixtures = _run_gate(tmp_path)
    payload = _retry_payload(outcome)

    assert payload["retry_count"] == gate.RETRY_COUNT
    assert payload["retries_used"] == 1 + gate.RETRY_COUNT
    spend = [
        (one["task_id"], one["retries_used"], one["verified"]) for one in payload["retries"]
    ]
    assert spend == [(_FIRST, 1, True), (second, gate.RETRY_COUNT, False)]
    assert [one["side"] for one in payload["retries"]] == ["candidate", "candidate"]
    assert payload["retries"][0]["before"] == "UNVERIFIED"
    assert payload["retries"][0]["after"] == "SOLVED"
    assert payload["retries"][0]["completion_sha256"] != ""
    assert payload["unverified_after_retries"] == [
        {"side": "candidate", "task_id": second, "outcome": "UNVERIFIED"}
    ]


def test_the_disclosure_reports_the_budget_and_the_unverified_term(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Liveness item 4: the unverified rate is in the output, over its denominator.

    Not a rate as a proportion — `PREREGISTRATION.md:157` requires the denominator, and this
    repository never renders one without it. The line also carries `R` and what was spent, so
    an operator reading a run that reduced to `UNVERIFIED` can tell "the budget was spent and
    the machine is unreliable" from "the budget was never spent".
    """
    _flaky(monkeypatch, {("candidate", _FIRST): 500})

    outcome, _fixtures = _run_gate(tmp_path)
    lines = [line for line in gate.disclosure(outcome) if line.startswith("retries:")]

    assert len(lines) == 1, gate.disclosure(outcome)
    assert f"R={gate.RETRY_COUNT}" in lines[0]
    assert f"{gate.RETRY_COUNT} spent" in lines[0]
    assert f"1 of {len(_MEMBERS)}" in lines[0], (
        f"WHY THIS IS A FAILURE: {lines[0]!r} does not carry the unverified count over its "
        "denominator. Every rate in this repository carries its denominator"
    )


def test_the_disclosure_reports_the_budget_when_nothing_wobbled(tmp_path: Path) -> None:
    """The liveness line is unconditional: reported from the first eval onward, spend or none.

    A line that appeared only when something went wrong would make its absence ambiguous —
    a clean machine and an unmeasured one would read identically.
    """
    outcome, _fixtures = _run_gate(tmp_path)
    lines = [line for line in gate.disclosure(outcome) if line.startswith("retries:")]

    assert len(lines) == 1, gate.disclosure(outcome)
    assert "0 spent" in lines[0] and f"0 of {len(_MEMBERS)}" in lines[0]


def test_the_retry_budget_is_not_a_command_line_flag() -> None:
    """`R` is a pinned input, so the door must not offer to change it.

    The PRD declines `--retry R` explicitly: a CLI override would make the § 7.2 amendment a
    formality, because any run could then quietly choose its own liveness and no two gate
    evaluations would be comparable. Asserted against the shipped parser rather than against
    the intention.
    """
    from whetstone import cli

    parser = cli.build_parser()
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, __import__("argparse")._SubParsersAction)
    ]
    assert subparsers, "the CLI has no subcommands"
    gate_parser = subparsers[0].choices["gate"]
    offered = [option for action in gate_parser._actions for option in action.option_strings]

    assert not [option for option in offered if "retr" in option.lower()], (
        f"WHY THIS IS A FAILURE: `whetstone gate` offers {offered!r}, which includes a retry "
        "knob. R is pinned by PREREGISTRATION.md § 7.2 and revisable only by a further dated "
        "amendment — a flag would make that amendment a formality"
    )
    assert cli is not None
