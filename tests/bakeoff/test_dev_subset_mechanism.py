"""The dev-subset mechanism, proven as the three layers it is (PRD D5 / M7b).

The generation contract may not be scored on the tasks it was developed against — iterating a
prompt or an extractor against a task and then scoring that task is optimising on the outcome.
The mechanism is three layers, each independent of the others, and this file proves each
through the real driver:

1. the partition (`conduct`, `run.py:540`) removes the declared ids from **both** sources
   before the contract is frozen and before any engine exists — a dev task is never posed,
   so its prompt is not even sealed;
2. an id that matches no task is refused (`UnknownDevSubset`) — a mistyped exclusion would
   exclude nothing while the report still printed the subset as excluded;
3. the report refuses the build if a dev id reached the scored set anyway (`ScoredDevSubset`,
   `report.py:385-397`) — the backstop for any caller that bypasses the partition.

The ids themselves arrive with the measured arm's pre-analysis; the mechanism is proven here
with synthetic ids over the same fixtures `test_run.py` and `test_report.py` build.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bakeoff.test_report import CONTRACT, FUNNEL, PROVENANCE, _entrant, _rollout, _sweep
from bakeoff.test_run import _corpus, _run
from whetstone.bakeoff.report import Entrant, ScoredDevSubset, build_report
from whetstone.bakeoff.run import UnknownDevSubset
from whetstone.bakeoff.scoring import Outcome


def test_the_declared_dev_subset_is_excluded_from_both_sources_before_anything_runs(
    tmp_path: Path,
) -> None:
    """M7b on both sources at once: the exclusion is the driver's first act.

    `conduct` partitions before the contract is frozen and before any engine exists, so a dev
    task is never posed — no prompt for it is ever rendered or sealed. Asserted through the
    published evidence: neither id is scored, both denominators shrank by exactly the declared
    ids, and the report names the exclusion so a reader can check it.
    """
    # Not `tmp_path / "public"` under `tmp_path` itself: `_run` builds its default corpora at
    # those names before applying overrides, and two corpora sharing a task id would collide
    # on the donor directory. A dedicated root keeps the fixtures apart.
    root = tmp_path / "arm"
    public = _corpus(root, "public", ("pallets__flask-4045", "pub-dev"))
    conducted = _run(tmp_path, public=public, dev_subset=["beta", "pub-dev"])

    assert conducted.report is not None
    assert "beta" not in conducted.scored and "pub-dev" not in conducted.scored, (
        f"WHY THIS IS A FAILURE: a declared dev-subset task was scored anyway "
        f"({conducted.scored}). Its prompt and extractor were developed against it, so its "
        "outcome is not a measurement of anything"
    )
    assert conducted.report.private[0].denominator == 2, (
        "WHY THIS IS A FAILURE: three private tasks were loaded, one was declared as the dev "
        "subset, and the published private denominator is "
        f"{conducted.report.private[0].denominator} rather than 2. The exclusion must hold in "
        "the denominator the report publishes"
    )
    assert conducted.report.public[0].denominator == 1, (
        "WHY THIS IS A FAILURE: two public tasks were loaded, one was declared as the dev "
        "subset, and the published public denominator is "
        f"{conducted.report.public[0].denominator} rather than 1. The exclusion applies to "
        "both sources, not only the private one"
    )
    assert "beta" in conducted.report.markdown and "pub-dev" in conducted.report.markdown, (
        "WHY THIS IS A FAILURE: an excluded task is not named in the report, so the exclusion "
        "is asserted rather than auditable"
    )


def test_a_dev_subset_id_that_matches_no_task_is_refused(tmp_path: Path) -> None:
    """A mistyped exclusion excludes nothing while the report says it excluded something.

    The failure is silent by construction: the driver filters on an id that matches nothing,
    every task is scored, and the report still prints the declared subset. Refusing costs one
    comparison and closes the only route by which the dev-subset disclosure could be false.
    """
    with pytest.raises(UnknownDevSubset) as refusal:
        _run(tmp_path, dev_subset=["betta"])

    assert "betta" in str(refusal.value), (
        "WHY THIS IS A FAILURE: the refusal does not name the id that matched nothing, so the "
        f"operator cannot see the typo. Got {str(refusal.value)!r}"
    )


def test_a_dev_id_that_reached_the_scored_set_is_refused_by_the_report(tmp_path: Path) -> None:
    """The backstop layer: the report refuses what the partition did not catch.

    The partition removes declared ids before anything runs; this is the second layer, for a
    dev id that reaches the scored set anyway — a caller that bypasses the partition, or a
    partition bug. `build_report` is the last place the leak can be noticed, and it fires
    rather than caveats (`report.py:385-397`).
    """
    leaked = _entrant("small", billions=3.0, private=[Outcome.SOLVED])
    contaminated = Entrant(
        contender=leaked.contender,
        private=_sweep("small", [_rollout("small", "dev-a", Outcome.SOLVED)]),
        public=leaked.public,
    )

    with pytest.raises(ScoredDevSubset) as refusal:
        build_report(
            entrants=[contaminated],
            provenance=PROVENANCE,
            contract=CONTRACT,
            funnel=FUNNEL,
        )
    assert "dev-a" in str(refusal.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name the leaked task. Got "
        f"{str(refusal.value)!r}"
    )
