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