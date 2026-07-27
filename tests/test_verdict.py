"""Pins the reduction's honesty contract: a result we could not verify never reads as clean.

The failure this prevents: a reduction that folds sub-checks by the ordering you would reach
for first — PASS, WARN, FAIL, with UNVERIFIED somewhere harmless — so a task whose reward we
failed to compute reduces to PASS and is counted as a win. That is the false pass Whetstone
exists to refuse, and it is a one-line edit away at all times, so the ordering is asserted
directly rather than only through its consequences.

``test_unverified_outranks_pass_in_the_severity_table`` is the anti-vacuity control: the
behavioural tests below would all still pass if ``reduce`` special-cased its way to the right
answers while ``_RANK`` said the opposite, so one test reads the table itself. It was watched
failing against a ``_RANK`` with UNVERIFIED ordered below PASS before being trusted.
"""

from dataclasses import FrozenInstanceError

import pytest

from whetstone.verify.verdict import _RANK, Status, Verdict, reduce


def verdict(status: Status, kind: str = "pytest") -> Verdict:
    """A grounded sub-check carrying ``status`` — the reduction reads nothing else."""
    return Verdict(
        kind=kind,
        status=status,
        observed=None,
        expected=None,
        message=f"synthetic {status.value} sub-check",
    )


def test_an_empty_verdict_set_reduces_to_unverified() -> None:
    """Nothing checked is never a pass — and never NOT_COVERED either."""
    assert reduce([]) is Status.UNVERIFIED


def test_a_pass_beside_an_unverified_reduces_to_unverified() -> None:
    """"We could not check this" is a stronger statement about the task than "this looked fine"."""
    assert reduce([verdict(Status.PASS), verdict(Status.UNVERIFIED)]) is Status.UNVERIFIED


def test_only_not_covered_reduces_to_unverified_because_the_filter_empties_the_set() -> None:
    """NOT_COVERED is dropped BEFORE ranking, so a set of only NOT_COVERED is an empty set."""
    assert reduce([verdict(Status.NOT_COVERED)]) is Status.UNVERIFIED


def test_a_failing_sub_check_sinks_the_task_and_an_all_passing_one_does_not() -> None:
    """Worst-status-wins, in both directions — the second half stops the first passing vacuously."""
    assert reduce([verdict(Status.PASS), verdict(Status.FAIL)]) is Status.FAIL
    assert reduce([verdict(Status.PASS)]) is Status.PASS


def test_unverified_outranks_pass_in_the_severity_table() -> None:
    """Anti-vacuity control — watched failing against an inverted ``_RANK`` before being trusted."""
    assert _RANK, "the severity table is empty, so this proves nothing about the ordering"
    assert _RANK[Status.UNVERIFIED] > _RANK[Status.PASS]
    assert _RANK[Status.UNVERIFIED] > _RANK[Status.WARN]
    assert _RANK[Status.FAIL] > _RANK[Status.UNVERIFIED]


def test_a_verdict_is_frozen_and_carries_no_axis() -> None:
    """One axis, so no ``axis`` field: an always-constant field is a lie about the structure."""
    v = verdict(Status.PASS)
    assert not hasattr(v, "axis")
    with pytest.raises(FrozenInstanceError):
        v.kind = "mutated"
