"""Aspect 1 of the honest-number-report unit: the promotion record carries N_final, and a
reader refuses a doctored record by name.

The pre-registered shape needs `N: f at baseline, g at final` (`PREREGISTRATION.md:57-72`),
and the final side's `N` has no on-disk source anywhere: `SideCounts` in the promotion
record carries no `weaker_wins`, and the gate writes no per-rollout evidence. This aspect
records `weaker_wins` at scoring time — `report.tally`'s definition by identity (weak is
PASS and strict is FAIL over the same rollouts), never a copied formula, never a rate — and
ships the fail-closed reader the schema's own docstring anticipated (gate.py): unknown
fields, a wrong schema, unreadable JSON, counts that do not sum to their denominator,
`weaker_wins` over its denominator, and a record missing `weaker_wins` (written before the
field existed) are each refused by name — never defaulted, because zero is a measurement
and absence is a fact.

No model, no `mlx`, no network — the fixtures are mined tasks and hand-built rollouts, and
the record is written and read as JSON on disk.
"""

from __future__ import annotations

from pathlib import Path

from loop.harness import corpus
from whetstone.bakeoff import report
from whetstone.bakeoff.scoring import Outcome, Rollout
from whetstone.loop import gate
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status

#: Six tasks: two true solves, two graded zeros, one no-verdict, one no-patch.
_IDS = ("t-01", "t-02", "t-03", "t-04", "t-05", "t-06")


def _rollout(
    task_id: str,
    outcome: Outcome,
    *,
    weak: Status | None,
    strict: Status | None,
) -> Rollout:
    """One hand-built rollout: the fields `_counts` and `tally` read, the rest inert."""
    return Rollout(
        candidate="candidate",
        task_id=task_id,
        outcome=outcome,
        strict=strict,
        weak=weak,
        verdict_kinds=(),
        executed=None,
        prompt_sha256="",
        detail="",
        generation_seconds=0.0,
        strict_seconds=0.0,
        weak_seconds=0.0,
    )


def _fixture_rollouts() -> tuple[Rollout, ...]:
    """Six rollouts with known weak/strict statuses: two weaker-wins among four verdicts.

    The fixture's ground truth is 2: `t-02` and `t-04` are the shape a weaker check would
    have scored as wins (weak PASS, strict FAIL); `t-03` is a genuine zero on both checks;
    `t-01` is a true solve; `t-05` is a no-verdict and `t-06` never reached a verifier.
    """
    return (
        _rollout("t-01", Outcome.SOLVED, weak=Status.PASS, strict=Status.PASS),
        _rollout("t-02", Outcome.NOT_SOLVED, weak=Status.PASS, strict=Status.FAIL),
        _rollout("t-03", Outcome.NOT_SOLVED, weak=Status.FAIL, strict=Status.FAIL),
        _rollout("t-04", Outcome.NOT_SOLVED, weak=Status.PASS, strict=Status.FAIL),
        _rollout("t-05", Outcome.UNVERIFIED, weak=Status.PASS, strict=Status.UNVERIFIED),
        _rollout("t-06", Outcome.NO_DIFF, weak=None, strict=None),
    )


def _tasks(tmp_path: Path) -> tuple[Task, ...]:
    """One mined task per fixture id — the real task objects `_counts` maps by id."""
    _directory, built = corpus(tmp_path / "corpus", "private", _IDS)
    return tuple(fixture.task for fixture in built)


def test_weaker_wins_is_the_tallys_definition_by_identity(tmp_path: Path) -> None:
    """The gate's scoring-time count equals `report.tally`'s over the same rollouts.

    `weaker_wins` is `N` at the final side (`PREREGISTRATION.md:57-72`): the rollouts a
    weaker check would have scored as wins — weak is PASS and strict is FAIL. The gate
    computes it by calling the tally over the same records, never by restating its
    predicate, so the record's `N` cannot drift from the published definition.
    """
    rollouts = _fixture_rollouts()

    counts = gate._counts(rollouts, _tasks(tmp_path))

    assert counts.weaker_wins == 2, counts
    assert counts.weaker_wins == report.tally("candidate", rollouts).weaker_wins


def test_the_gate_counts_weaker_wins_through_the_report_module_by_identity() -> None:
    """The tally the gate calls is `bakeoff.report`'s own — imported, never copied.

    A second implementation of "what counts as a weaker win" anywhere in the gate would be
    a second definition of `N` with nothing to say so; the module-level import pins that the
    gate reads the one tally.
    """
    assert gate.bakeoff_report is report