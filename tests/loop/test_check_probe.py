"""The probe decision: night #1's go/no-go as a deterministic answer over one run directory.

`docs/planning/p2-rollouts/night-door/runbook.md:78-80` pre-commits the rule in prose — the
night proceeds iff the probe completes with the control arm `PASS` on every draw and a
non-empty seed map — and this suite pins the command that holds it: `run_check(run)` reads
one probe run directory and returns a `ProbeReport`. The rule's two conditions are enforced
exactly as pre-committed — the fold compared against `Status` by identity, the seed map
literally non-empty (`len(seeds) > 0`) — and every other shape of run directory is refused
by name, never decided.

The fixtures are real `Ledger` documents written by `run_ledger.write`, schema-valid **by
construction**, so a doctored variant is a genuine adversary rather than a hand-rolled JSON
that could drift from the writer. Journals are real files derived from `evidence_paths` by
identity, touched and deleted, never parsed — content is the night's own record, not a new
bar.

No model, no `mlx`, no network. The inputs are one run directory and the verdict vocabulary.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from loop.test_run_ledger import _ledger
from whetstone.loop import check_probe, night
from whetstone.loop import draws as run_draws
from whetstone.loop import ledger as run_ledger
from whetstone.loop.sampling import Applied
from whetstone.verify.verdict import Status

#: The seed map a genuine probe records: non-empty, in application order.
_PROBE_SEEDS = (Applied(task_id="alpha", attempt=1, seed=1234),)

#: The control fold a genuine probe records: every source `PASS`, by identity.
_HARNESS = {night.PRIVATE: Status.PASS, night.PUBLIC: Status.PASS}

#: The per-source counts a draw records, in the ledger's own `(denominator, unverified,
#: solved)` shape.
_COUNTS = {night.PRIVATE: (61, 7, 1), night.PUBLIC: (1, 0, 0)}


def _probe_run(
    tmp_path: Path,
    *,
    probe: int | None = 1,
    draws: int = 2,
    seeds: tuple[Applied, ...] = _PROBE_SEEDS,
    harness: dict[str, Status] | None = None,
    recorded: tuple[run_ledger.DrawRecord, ...] | None = None,
    journals: bool = True,
    ledger: bool = True,
) -> Path:
    """A probe-shaped run directory: a real written `Ledger` plus one journal per draw.

    The ledger is a genuine `Ledger` document built from the shipped `_ledger()` fixture by
    `replace` and written through `run_ledger.write`, so the check under test reads exactly
    what the night would write — a doctored variant is a mutation of a real document, never
    a hand-rolled payload that could drift from the writer. Journal paths come from
    `evidence_paths` by identity, never re-typed.
    """
    run = tmp_path / "runs" / "probe-001"
    run.mkdir(parents=True, exist_ok=True)
    if not ledger:
        return run
    if harness is None:
        harness = _HARNESS
    if recorded is None:
        recorded = tuple(
            run_ledger.DrawRecord(attempt=index, harness=dict(harness), counts=_COUNTS)
            for index in range(1, draws + 1)
        )
    base = _ledger()
    candidate = replace(
        base,
        task_set=replace(base.task_set, probe=probe),
        checkpoint_digest=None,
        checkpoint_absent=(
            "this was a --probe 1 run: the control fold decides the gate, and no checkpoint "
            "is written"
        ),
        draws=draws,
        seeds=seeds,
        draws_recorded=recorded,
    )
    run_ledger.write(run / run_ledger.LEDGER_FILE, candidate)
    if journals:
        for attempt in range(1, draws + 1):
            journal, _ = run_draws.evidence_paths(run / night.EVIDENCE_DIR, attempt)
            journal.parent.mkdir(parents=True, exist_ok=True)
            journal.touch()
    return run


def test_a_full_night_is_refused_as_not_a_probe(tmp_path: Path) -> None:
    """AC4: a decision gate over a run that was never a probe proves nothing about the night."""
    run = _probe_run(tmp_path, probe=None)

    with pytest.raises(check_probe.NotAProbe) as refusal:
        check_probe.run_check(run)
    assert str(run) in str(refusal.value)
    assert "None" in str(refusal.value)


def test_a_directory_without_a_ledger_is_not_a_run(tmp_path: Path) -> None:
    """AC5: refused by name — a probe decision over an unidentified run proves nothing."""
    run = _probe_run(tmp_path, ledger=False)

    with pytest.raises(check_probe.NotARun) as refusal:
        check_probe.run_check(run)
    assert run_ledger.LEDGER_FILE in str(refusal.value)


def test_an_unreadable_ledger_is_refused(tmp_path: Path) -> None:
    """The schema gate by identity: a doctored ledger never reaches the decision."""
    run = tmp_path / "runs" / "probe-001"
    run.mkdir(parents=True)
    (run / run_ledger.LEDGER_FILE).write_text('{"schema": "not-the-schema"}', encoding="utf-8")

    with pytest.raises(run_ledger.LedgerUnreadable) as refusal:
        check_probe.run_check(run)
    assert run_ledger.LEDGER_SCHEMA in str(refusal.value)


def test_a_truncated_draws_recorded_is_incomplete(tmp_path: Path) -> None:
    """AC6: fewer recorded draws than declared is refused, named with both counts."""
    run = _probe_run(
        tmp_path,
        recorded=(
            run_ledger.DrawRecord(attempt=1, harness=dict(_HARNESS), counts=_COUNTS),
        ),
    )

    with pytest.raises(check_probe.IncompleteRun) as refusal:
        check_probe.run_check(run)
    assert "1 of 2" in str(refusal.value)


def test_a_missing_source_is_incomplete(tmp_path: Path) -> None:
    """AC6: a draw whose harness lacks a declared source is refused, never silently skipped."""
    run = _probe_run(tmp_path, harness={night.PRIVATE: Status.PASS})

    with pytest.raises(check_probe.IncompleteRun) as refusal:
        check_probe.run_check(run)
    assert "draw 1" in str(refusal.value)
    assert night.PUBLIC in str(refusal.value)


def test_a_missing_journal_is_incomplete(tmp_path: Path) -> None:
    """AC7: a declared draw whose journal file is absent is refused, named with the draw."""
    run = _probe_run(tmp_path)
    journal, _ = run_draws.evidence_paths(run / night.EVIDENCE_DIR, 1)
    journal.unlink()

    with pytest.raises(check_probe.IncompleteRun) as refusal:
        check_probe.run_check(run)
    assert "draw 1" in str(refusal.value)


def test_a_valid_probe_proceeds(tmp_path: Path) -> None:
    """AC1: the pre-committed rule holds — every source `PASS`, non-empty seed map."""
    report = check_probe.run_check(_probe_run(tmp_path))

    assert report.proceed is True
    assert report.violation is None
    assert report.draws == 2
    assert report.draws_recorded == 2
    assert report.sources == 2
    assert report.probe == 1
    assert report.seeds == 1


def test_a_non_pass_harness_is_a_named_violation(tmp_path: Path) -> None:
    """AC2: a doctored fold names the attempt and the source — never just "failed"."""
    report = check_probe.run_check(
        _probe_run(
            tmp_path,
            harness={night.PRIVATE: Status.PASS, night.PUBLIC: Status.FAIL},
        )
    )

    assert report.proceed is False
    assert "draw 1" in report.violation
    assert night.PUBLIC in report.violation


def test_an_empty_seed_map_is_a_named_violation(tmp_path: Path) -> None:
    """AC3: the recorded seed map is refused when empty — literally, no coverage assertion."""
    report = check_probe.run_check(_probe_run(tmp_path, seeds=()))

    assert report.proceed is False
    assert "seed map" in report.violation


def test_disclosure_states_the_decision_and_counts(tmp_path: Path) -> None:
    """A proceeding probe discloses the decision and the counts it was read from."""
    report = check_probe.run_check(_probe_run(tmp_path))
    lines = check_probe.disclosure(report)

    assert any("PROCEED" in line for line in lines), lines
    assert any("draws: 2" in line for line in lines), lines
    assert any("seeds: 1" in line for line in lines), lines


def test_disclosure_names_the_violation_of_a_refused_run(tmp_path: Path) -> None:
    """A refused probe discloses "DO NOT PROCEED" and the named violation."""
    report = check_probe.run_check(
        _probe_run(
            tmp_path / "harness",
            harness={night.PRIVATE: Status.PASS, night.PUBLIC: Status.FAIL},
        )
    )
    lines = check_probe.disclosure(report)

    assert any("DO NOT PROCEED" in line for line in lines), lines
    assert any("draw 1 (public)" in line for line in lines), lines

    empty = check_probe.run_check(_probe_run(tmp_path / "seeds", seeds=()))
    seed_lines = check_probe.disclosure(empty)

    assert any("DO NOT PROCEED" in line for line in seed_lines), seed_lines
    assert any("seed map" in line for line in seed_lines), seed_lines


def test_a_refused_disclosure_never_renders_pass_or_unverified(tmp_path: Path) -> None:
    """A refused run's harness is never rendered — `UNVERIFIED` is never rendered as `PASS`."""
    for run in (
        _probe_run(
            tmp_path / "harness",
            harness={night.PRIVATE: Status.PASS, night.PUBLIC: Status.FAIL},
        ),
        _probe_run(tmp_path / "seeds", seeds=()),
    ):
        lines = check_probe.disclosure(check_probe.run_check(run))
        assert not any("PASS" in line or "UNVERIFIED" in line for line in lines), lines


@pytest.mark.parametrize(
    "relative",
    ["src/whetstone/loop/check_probe.py", "tests/loop/test_check_probe.py"],
)
def test_the_probe_check_path_imports_no_inference_library(relative: str) -> None:
    """The decision reads one JSON document. It must cost nothing and load no weights.

    The test file is walked too: a fixture that generated its own harness would make the
    module's guarantee untestable, since the guard would pass while the path that exercised
    it did the very thing the guard forbids.
    """
    from bakeoff.test_comparison import FORBIDDEN_IMPORT_ROOTS, _imported_roots

    path = Path(__file__).resolve().parents[2] / relative
    roots = _imported_roots(path.read_bytes())

    assert not roots & FORBIDDEN_IMPORT_ROOTS, (
        f"{relative} imports {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}.\n\n"
        "WHY THIS IS A FAILURE: the probe decision reads one ledger document and compares "
        "values against a verdict vocabulary. An inference import here means the gate needs "
        "a GPU to decide."
    )
    assert roots, (
        f"{relative} contains no import at all, so the assertion above holds for a file "
        "nothing was checked against (`CONTRIBUTING.md:60`)."
    )


def test_the_probe_check_composes_by_identity() -> None:
    """AC10: every fact the decision reads is the shipped one, asserted `is`.

    A second spelling of a source name, the ledger's name, the schema gate, the verdict
    vocabulary, or the journal path derivation would be a second answer to a question one
    document already answers — and the day they disagreed neither document would say so.
    """
    from whetstone.loop import draws, ledger
    from whetstone.verify import verdict

    assert check_probe.SOURCES[0] is night.PRIVATE
    assert check_probe.SOURCES[1] is night.PUBLIC
    assert check_probe.read_ledger is ledger.read
    assert check_probe.LEDGER_FILE is ledger.LEDGER_FILE
    assert check_probe.LedgerUnreadable is ledger.LedgerUnreadable
    assert check_probe.Status is verdict.Status
    assert check_probe.evidence_paths is draws.evidence_paths
    assert check_probe.EVIDENCE_DIR is night.EVIDENCE_DIR


def test_refusals_are_named_and_closed_by_value_error() -> None:
    """AC8: every refusal is named for exit-2, and `ValueError` closes the tuple — an
    unforeseen crash is a named exit-2, never a traceback."""
    assert check_probe.NotARun in check_probe.REFUSALS
    assert check_probe.LedgerUnreadable in check_probe.REFUSALS
    assert check_probe.NotAProbe in check_probe.REFUSALS
    assert check_probe.IncompleteRun in check_probe.REFUSALS
    assert check_probe.REFUSALS[-1] is ValueError