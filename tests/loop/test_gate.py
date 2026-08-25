"""The gate's pure decision core: the roadmap rule, with no harness in front of it.

The gate's verdict is `docs/ROADMAP.md:420-427` and nothing else:

    promote iff  solved_new > solved_old
            AND  regressed  == 0
            AND  unverified == 0

Three exits only: `promoted` / `rejected` / `UNVERIFIED`, and `UNVERIFIED` is never collapsed
into `promoted`. This file tests the *pure* half — `decide` over two per-task outcome maps —
because the rule is the one thing in this unit that must not be buried under the harness:
every other guarantee (re-hashed checkpoints, the held-out document, the STRICT verifier) is
machinery around it, and a rule that is only ever exercised through machinery is a rule whose
edge cases nobody has read.

The counts are all over the **shared denominator**: the task set both maps carry. A task
either side failed to reach a verdict on (`UNVERIFIED`, `UNPROVISIONED`, `NO_ORACLE` — the
sibling's own `_UNCOVERED` set, imported by identity) is a task no comparison was actually
made on, and it makes the whole evaluation `UNVERIFIED` (`docs/ROADMAP.md:438-440`): not
promoted and not rejected, because neither would be a statement the evidence supports.

No model, no `mlx`, no network — the inputs are outcome maps and the outputs are counts.
"""

from __future__ import annotations

import pytest

from whetstone.bakeoff.scoring import Outcome
from whetstone.loop import gate
from whetstone.loop.gate import Exit, GateDecision, decide

#: Three tasks, enough to separate every count the rule reads.
_IDS = ("a", "b", "c")


def _map(*outcomes: Outcome) -> dict[str, Outcome]:
    """One outcome per declared id, in order."""
    assert len(outcomes) == len(_IDS), outcomes
    return dict(zip(_IDS, outcomes, strict=True))


def test_known_better_is_promoted() -> None:
    """The rule's happy path: more solves, nothing lost, nothing unverified."""
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.PROMOTED
    assert decision.denominator == 3
    assert decision.solved_new == 2 and decision.solved_old == 1
    assert decision.regressed == 0 and decision.unverified == 0


def test_known_worse_is_rejected() -> None:
    """Fewer solves is a rejection; the incumbent stays put."""
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.REJECTED
    assert decision.solved_new == 1 and decision.solved_old == 2


def test_equal_solved_counts_is_rejected_by_the_greater_than_term() -> None:
    """Equal solves is `rejected`, never a tie-break — the rule says `>`, not `>=`.

    This is the trap the asserted test exists for: a tie reads like a promotion to a reader
    who sees "no regression, no unverified" and stops there. The `>` term is the whole
    never-regress contract — a checkpoint that provably beats the last one, not merely
    matches it.
    """
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.REJECTED
    assert decision.solved_new == decision.solved_old == 2
    assert decision.regressed == 0 and decision.unverified == 0


def test_candidate_identical_to_incumbent_is_rejected() -> None:
    """The self-comparison is `rejected` by the `>` term — asserted, not an accident.

    A gate that promoted "the same checkpoint against itself" would let any operator
    manufacture a promotion by pointing both flags at one directory. There is no special
    case here; the rule's own `>` makes it a rejection, and the test pins that it does.
    """
    both = _map(Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.NOT_SOLVED)
    decision = decide(candidate=both, incumbent=dict(both))
    assert decision.exit is Exit.REJECTED
    assert decision.solved_new == decision.solved_old == 1


def test_one_still_unverified_task_makes_the_whole_eval_unverified() -> None:
    """`docs/ROADMAP.md:438-440`: no comparison was actually made, so nothing is decided.

    The counts are reported — the decision carries them — but the exit is the third one:
    not promoted and not rejected, because neither would be a statement the evidence
    supports.
    """
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.UNVERIFIED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.NOT_SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.UNVERIFIED
    assert decision.unverified == 1
    assert decision.solved_new == 1 and decision.solved_old == 0, (
        "WHY THIS IS A FAILURE: a solve on a task the other side could not be scored on "
        "was credited to a side. No comparison was actually made on that task, so neither "
        "side may count it"
    )


def test_unverified_outranks_a_promotion_shaped_comparison() -> None:
    """The `unverified` term beats the `>` term: counts that would promote still reduce to 3."""
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.UNVERIFIED),
        incumbent=_map(Outcome.NOT_SOLVED, Outcome.NOT_SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.UNVERIFIED
    assert decision.solved_new == 2 and decision.solved_old == 0


@pytest.mark.parametrize(
    "unknown",
    [Outcome.UNVERIFIED, Outcome.UNPROVISIONED, Outcome.NO_ORACLE],
    ids=["unverified", "unprovisioned", "no-oracle"],
)
def test_any_task_without_a_verdict_reduces_the_whole_eval(unknown: Outcome) -> None:
    """The sibling's `_UNCOVERED` set is the "reached no verdict" definition, by identity.

    A task whose environment could not be built, or whose generation contract could not be
    built, is a task no comparison was actually made on — the identical argument to a bare
    `UNVERIFIED`, one step earlier in the pipeline.
    """
    decision = decide(
        candidate=_map(Outcome.SOLVED, unknown, Outcome.SOLVED),
        incumbent=_map(Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.NOT_SOLVED),
    )
    assert decision.exit is Exit.UNVERIFIED
    assert decision.unverified == 1


def test_a_regressed_task_rejects_even_with_a_solved_gain() -> None:
    """`regressed == 0` is a conjunct, never an afterthought: one loss is a rejection.

    The candidate gained a task AND lost one the incumbent solved — net zero, and the rule
    does not do netting. The incumbent's solve on `c` must come back as `regressed`.
    """
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.NOT_SOLVED, Outcome.SOLVED, Outcome.SOLVED),
    )
    assert decision.exit is Exit.REJECTED
    assert decision.solved_new == 2 and decision.solved_old == 2
    assert decision.regressed == 1


def test_a_regression_rejects_even_when_solved_new_exceeds_solved_old() -> None:
    """The strongest form of the conjunct: more solves AND a regression is still `rejected`."""
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.NOT_SOLVED),
        incumbent=_map(Outcome.NOT_SOLVED, Outcome.NOT_SOLVED, Outcome.SOLVED),
    )
    assert decision.exit is Exit.REJECTED
    assert decision.solved_new == 2 and decision.solved_old == 1
    assert decision.regressed == 1


def test_mismatched_task_sets_are_refused() -> None:
    """Both sides must be scored over the same membership; a mismatch is a broken caller.

    Refused rather than silently compared over the intersection: a task scored on one side
    alone is a task one checkpoint was never asked about, and a decision over the overlap
    would read as a full comparison.
    """
    with pytest.raises(ValueError) as refused:
        decide(
            candidate=_map(Outcome.SOLVED, Outcome.SOLVED, Outcome.SOLVED),
            incumbent=dict(zip(("a", "b"), (Outcome.SOLVED, Outcome.SOLVED), strict=True)),
        )
    message = str(refused.value)
    assert "c" in message and "candidate-only" in message, (
        f"WHY THIS IS A FAILURE: the refusal does not name the mismatched id: {message!r}"
    )


def test_the_solved_definition_is_outcome_solved_by_identity() -> None:
    """`Outcome.SOLVED` — the same member the loop's trainable partition imports.

    A second notion of "this task was solved" is exactly how the gate and the training
    selection stop agreeing about what a win is. The module imports the one member; the
    assertion pins that it did.
    """
    assert gate.Outcome is Outcome


def test_the_unverified_definition_is_the_siblings_by_identity() -> None:
    """`report._UNCOVERED` — the same set coverage reduces against, imported, never restated."""
    from whetstone.bakeoff import report as bakeoff_report

    assert gate._UNCOVERED is bakeoff_report._UNCOVERED


def test_the_decision_carries_the_counts_a_record_needs() -> None:
    """The record's per-side counts come from the decision; their presence is asserted here.

    A decision that carried only the exit would be a verdict nobody could re-derive from
    the scored outcomes — the promotion record would have to guess these numbers back.
    """
    decision = decide(
        candidate=_map(Outcome.SOLVED, Outcome.NOT_SOLVED, Outcome.UNVERIFIED),
        incumbent=_map(Outcome.NOT_SOLVED, Outcome.SOLVED, Outcome.SOLVED),
    )
    assert isinstance(decision, GateDecision)
    assert decision.denominator == 3
    assert decision.exit is Exit.UNVERIFIED
    assert decision.detail, "WHY THIS IS A FAILURE: the decision carries no sentence explaining it"