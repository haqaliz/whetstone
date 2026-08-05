"""Arm A against the committed record — and the honest limit of what that can prove.

PRD D2a asks arm A to reproduce `reports/baseline/`: the P1 contract decodes greedily with no
seeds, so re-running it over the same tasks must produce the same outcomes, and a divergence is a
finding that outranks everything else in the slice.

**What the committed record actually supports is weaker than that, and this suite is where the
difference is pinned rather than papered over.** `reports/baseline/report.json` carries
per-candidate *counts* — `solved`, `covered`, `no_diff`, `not_applied`, `not_solved`,
`unverified` — and no per-task field at all. The run's journal, which *is* per-`(candidate,
task)`, was never committed: `--journal` is undefaulted and its output belongs under a gitignored
root, and no journal from the P1 run survives on this machine. So the per-task comparison the plan
described **cannot be made against the record that exists**.

The comparison is therefore over counts, and it is **necessary but not sufficient**: two runs can
agree on every count while disagreeing about which tasks produced them, because one task moving
from `no_diff` to `not_applied` and another moving the other way cancels exactly. That is stated
in `compare_to_counts`' own docstring and asserted below, so nobody reads a green comparison as
per-task reproduction.

The fix is forward-looking and costs nothing to state: a run invoked with `--journal` *and*
`--transcript` is per-task checkable afterwards. This suite is the reason to always pass both.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whetstone.bakeoff.attribution import CountDivergence, compare_to_counts

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _report(**per_candidate: dict[str, int]) -> dict[str, object]:
    """A minimal report payload in the shape `report.json` actually has."""
    return {"source_b": [{"candidate": name, **counts} for name, counts in per_candidate.items()]}


def test_a_replay_agreeing_with_the_record_reports_no_divergence() -> None:
    """The green case, asserted first so every red case below is known to be about the
    disagreement itself rather than about a comparison that reports everything."""
    record = _report(alpha={"no_diff": 2, "not_applied": 3})
    assert compare_to_counts({"alpha": {"no_diff": 2, "not_applied": 3}}, record) == ()


def test_a_single_flipped_count_is_reported_naming_both_sides() -> None:
    """The teeth. A comparison that returned `()` unconditionally would pass the test above.

    Both sides are named because "they disagree" is not actionable: an operator deciding whether
    to halt the slice needs to see which direction it moved and by how much.
    """
    record = _report(alpha={"no_diff": 2, "not_applied": 3})
    divergences = compare_to_counts({"alpha": {"no_diff": 2, "not_applied": 4}}, record)

    assert len(divergences) == 1, (
        f"a changed count was not reported: {divergences}. A reproduction check that misses a "
        "flip lets a re-run that did NOT reproduce be read as one, which is the single thing "
        "PRD D2a asks this comparison to prevent"
    )
    (only,) = divergences
    assert isinstance(only, CountDivergence), only
    assert only.candidate == "alpha"
    assert only.field == "not_applied"
    assert only.recorded == 3, only
    assert only.replayed == 4, only


@pytest.mark.parametrize(
    ("replayed", "recorded", "missing_side"),
    [
        ({}, {"alpha": {"no_diff": 1}}, "replay"),
        ({"alpha": {"no_diff": 1}}, {}, "record"),
    ],
)
def test_a_candidate_present_on_one_side_only_is_a_divergence_not_a_skip(
    replayed: dict[str, dict[str, int]],
    recorded: dict[str, dict[str, int]],
    missing_side: str,
) -> None:
    """A missing row is exactly how a partial run reads as agreement.

    This is the failure mode worth the parametrisation: a comparison written as "for each
    candidate in both, compare" is silent about a candidate that only one side has, and a run
    that died after its first base would then reproduce the record perfectly.
    """
    divergences = compare_to_counts(replayed, _report(**recorded))
    assert divergences, (
        f"a candidate absent from the {missing_side} was treated as agreement. A run that "
        "stopped early would then be indistinguishable from one that reproduced the record"
    )


def test_a_missing_field_is_a_divergence_rather_than_a_zero() -> None:
    """Absent is not zero. `breakdown` omits causes that did not occur, so this is a live shape.

    Defaulting a missing field to 0 would make "this cause never happened" and "this side never
    reported this cause" the same answer, and only one of them is evidence.
    """
    record = _report(alpha={"no_diff": 2, "not_applied": 3})
    divergences = compare_to_counts({"alpha": {"no_diff": 2}}, record)
    assert any(item.field == "not_applied" for item in divergences), divergences


def test_the_committed_report_carries_no_per_task_outcome() -> None:
    """The premise of this whole module, asserted against the real file rather than assumed.

    If a later report ever grows a per-task field, this test fails — and that failure is a
    *prompt to strengthen the comparison*, not a bug. The weaker check exists only because the
    stronger one has nothing to read.
    """
    payload = json.loads((REPO_ROOT / "reports" / "baseline" / "report.json").read_text())
    for row in payload["source_b"]:
        assert not any("task" in key.lower() for key in row), (
            f"reports/baseline/report.json now carries a per-task field in {sorted(row)}. The "
            "count comparison in attribution.py was written because it did not; per-task "
            "reproduction is now possible and should replace it"
        )
