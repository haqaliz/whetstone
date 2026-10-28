"""The probe decision: night #1's go/no-go as a deterministic answer over one run directory.

`docs/planning/p2-rollouts/night-door/runbook.md:78-80` pre-commits the rule in prose — the
night proceeds iff the probe completes with the control arm `PASS` on every draw and a
non-empty seed map — and this suite pins the command that holds it: `run_check(run)` reads
one probe run directory and returns a `ProbeReport`. The rule's two conditions are enforced
exactly as pre-committed — the fold compared against `Status` by identity, the seed map
literally non-empty (`len(seeds) > 0`) — and the two declared-input pins narrow it: the
ledger's draws must be `sampling.K`, and, with `heldout=<doc>`, its held-out digest must be the
committed document's. Every other shape of run directory is refused by name, never decided.

The fixtures are real `Ledger` documents written by `run_ledger.write`, schema-valid **by
construction**, so a doctored variant is a genuine adversary rather than a hand-rolled JSON
that could drift from the writer. Journals are real files derived from `evidence_paths` by
identity, touched and deleted, never parsed — content is the night's own record, not a new
bar.

No model, no `mlx`, no network. The inputs are one run directory and the verdict vocabulary.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from loop.test_run_ledger import _ledger
from whetstone.loop import backend, check_probe, heldout, night, sampling
from whetstone.loop import draws as run_draws
from whetstone.loop import ledger as run_ledger
from whetstone.loop.sampling import Applied
from whetstone.verify.verdict import Status

#: The committed held-out document the night excludes, read by the test as its own input.
_COMMITTED_HELDOUT = Path(__file__).resolve().parents[2] / "tasks" / "heldout" / "source-b.json"

#: The held-out record a probe records: the shipped `_ledger()` fixture's placeholder digest and
#: its 12 members. Overridable per test so a missing or mismatched record can be built.
_HELDOUT_RECORD = run_ledger.HeldoutRecord(document_digest="d" * 64, membership_count=12)

#: The seed map a genuine probe records: non-empty, in application order.
_PROBE_SEEDS = (Applied(task_id="alpha", attempt=1, seed=1234),)

#: The control fold a genuine probe records: every source `PASS`, by identity.
_HARNESS = {night.PRIVATE: Status.PASS, night.PUBLIC: Status.PASS}

#: The per-source counts a draw records, in the ledger's own `(denominator, unverified,
#: solved)` shape.
_COUNTS = {night.PRIVATE: (61, 7, 1), night.PUBLIC: (1, 0, 0)}

#: The backend the § 10.25 probe runs under, and the one a pin is expected to find.
_TORCH_BACKEND = backend.Backend(
    name=backend.TORCH,
    library="torch",
    version="2.14.1",
    device="mps",
    device_memory_bytes=25_628_071_526,
    precision="float16",
)


def _probe_run(
    tmp_path: Path,
    *,
    probe: int | None = 1,
    draws: int = sampling.K,
    seeds: tuple[Applied, ...] = _PROBE_SEEDS,
    harness: dict[str, Status] | None = None,
    recorded: tuple[run_ledger.DrawRecord, ...] | None = None,
    journals: bool = True,
    ledger: bool = True,
    unsealed: bool = False,
    heldout_record: run_ledger.HeldoutRecord | None = _HELDOUT_RECORD,
    backend_record: backend.Backend | None = None,
) -> Path:
    """A probe-shaped run directory: a real written `Ledger` plus one journal per draw.

    The ledger is a genuine `Ledger` document built from the shipped `_ledger()` fixture by
    `replace` and written through `run_ledger.write`, so the check under test reads exactly
    what the night would write — a doctored variant is a mutation of a real document, never
    a hand-rolled payload that could drift from the writer. Journal paths come from
    `evidence_paths` by identity, never re-typed. With `unsealed`, the written document is
    re-based on the shipped generation before the seal: `claims` and `digest` dropped and the
    schema rewritten to `LEDGER_SCHEMA_V2`, the same way `_v2` re-bases the ledger suite's
    fixture. No real `/2` ledger exists, so this fixture is the tolerance's only carrier.
    `heldout_record` is the ledger's held-out record; `None` builds a probe that applied no
    split at all.
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
        task_set=replace(base.task_set, probe=probe, heldout=heldout_record),
        checkpoint_digest=None,
        checkpoint_absent=(
            "this was a --probe 1 run: the control fold decides the gate, and no checkpoint "
            "is written"
        ),
        draws=draws,
        seeds=seeds,
        draws_recorded=recorded,
        backend=backend_record or base.backend,
    )
    run_ledger.write(run / run_ledger.LEDGER_FILE, candidate)
    if unsealed:
        path = run / run_ledger.LEDGER_FILE
        document = json.loads(path.read_text(encoding="utf-8"))
        del document["claims"]
        del document["digest"]
        document["schema"] = run_ledger.LEDGER_SCHEMA_V2
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    assert f"1 of {sampling.K}" in str(refusal.value)


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
    assert report.draws == sampling.K
    assert report.draws_recorded == sampling.K
    assert report.sources == 2
    assert report.probe == 1
    assert report.seeds == 1


def test_a_matching_backend_pin_proceeds(tmp_path: Path) -> None:
    """A probe recorded under the pinned runtime, device and precision still proceeds.

    The pin is a declared-input check, not a new bar: it compares the ledger's own backend
    block to what the operator says the probe ran under, and adds nothing to the GO rule.
    """
    report = check_probe.run_check(
        _probe_run(tmp_path, backend_record=_TORCH_BACKEND),
        runtime=backend.TORCH,
        device="mps",
        precision="float16",
    )

    assert report.proceed is True
    assert report.violation is None
    assert report.backend == _TORCH_BACKEND.recorded()
    assert report.pins == (
        ("runtime", backend.TORCH),
        ("device", "mps"),
        ("precision", "float16"),
    )


@pytest.mark.parametrize(
    ("pin", "pinned", "recorded"),
    [
        ("runtime", backend.MLX, backend.TORCH),
        ("device", "cpu", "mps"),
        ("precision", "bfloat16", "float16"),
    ],
)
def test_a_backend_mismatch_is_a_named_violation(
    tmp_path: Path, pin: str, pinned: str, recorded: str
) -> None:
    """Each pin can only add a violation, and it names both sides of the disagreement.

    A runtime comparison goes through `backend.family`, so a legacy `torch-*` record is still
    Torch; a device and a precision are pinned values and compare exactly.
    """
    report = check_probe.run_check(
        _probe_run(tmp_path, backend_record=_TORCH_BACKEND), **{pin: pinned}
    )

    assert report.proceed is False
    assert report.violation is not None
    assert pinned in report.violation, report.violation
    assert recorded in report.violation, report.violation


def test_an_unknown_recorded_runtime_is_a_violation_not_a_traceback(tmp_path: Path) -> None:
    """A record naming no implemented runtime is a named violation, never an exception."""
    unknown = backend.Backend(
        name="jax",
        library="jax",
        version="0.9",
        device="tpu",
        device_memory_bytes=1,
    )

    report = check_probe.run_check(
        _probe_run(tmp_path, backend_record=unknown), runtime=backend.TORCH
    )

    assert report.proceed is False
    assert report.violation is not None
    assert "jax" in report.violation, report.violation


def test_a_pin_without_a_recorded_backend_is_a_violation(tmp_path: Path) -> None:
    """A `/2` ledger may carry no backend; a pin over it is a violation, not a refusal.

    The tolerance path exists so an old ledger can still decide the budget; it cannot prove a
    runtime it never recorded, so the pin refuses the GO/NO-GO rather than reading past it.
    """
    run = _probe_run(tmp_path, unsealed=True)
    path = run / run_ledger.LEDGER_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    del document["backend"]
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = check_probe.run_check(run, runtime=backend.TORCH)

    assert report.proceed is False
    assert report.violation is not None
    assert "backend" in report.violation, report.violation


def test_no_pin_keeps_the_old_decision_and_still_shows_the_backend(tmp_path: Path) -> None:
    """Without a pin the decision is unchanged, and the recorded runtime is still disclosed."""
    report = check_probe.run_check(_probe_run(tmp_path))

    assert report.proceed is True
    assert report.pins == ()
    assert report.backend is not None
    lines = check_probe.disclosure(report)
    assert any(line.startswith("backend: mlx (mlx-lm 0.31.3,") for line in lines), lines


def test_disclosure_shows_the_pins_and_the_recorded_backend(tmp_path: Path) -> None:
    """A pinned probe prints what it pinned and what the ledger recorded, before the decision.

    An operator reading a refused run sees the two runtime records side by side; the violation
    line names the field that disagreed.
    """
    report = check_probe.run_check(
        _probe_run(tmp_path, backend_record=_TORCH_BACKEND),
        runtime=backend.TORCH,
        device="mps",
        precision="float16",
    )
    lines = check_probe.disclosure(report)

    assert any(
        line == "pins: runtime=torch, device=mps, precision=float16" for line in lines
    ), lines
    assert any(
        line == "backend: torch (torch 2.14.1, mps, float16)" for line in lines
    ), lines


def test_a_probe_at_another_budget_is_a_named_violation(tmp_path: Path) -> None:
    """M2: the ledger's declared draws must equal `sampling.K`, not merely its own record.

    The pre-committed budget is `sampling.K` imported by identity; a probe that ran any other
    budget proves the harness at a size the night does not use, so it cannot stand behind one.
    """
    report = check_probe.run_check(_probe_run(tmp_path, draws=sampling.K - 1))

    assert report.proceed is False
    assert report.violation is not None
    assert str(sampling.K) in report.violation
    assert str(sampling.K - 1) in report.violation


def _committed_heldout_digest() -> str:
    """The committed document's digest, through the same function the night uses."""
    document = json.loads(_COMMITTED_HELDOUT.read_text(encoding="utf-8"))
    return heldout.document_digest_of(document)


def test_a_matching_heldout_digest_proceeds(tmp_path: Path) -> None:
    """M3: a probe that excluded the committed document proceeds exactly as before."""
    digest = _committed_heldout_digest()
    report = check_probe.run_check(
        _probe_run(
            tmp_path,
            heldout_record=run_ledger.HeldoutRecord(
                document_digest=digest, membership_count=12
            ),
        ),
        heldout=_COMMITTED_HELDOUT,
    )

    assert report.proceed is True
    assert report.violation is None


def test_a_mismatched_heldout_digest_is_a_violation(tmp_path: Path) -> None:
    """M3: a probe that excluded a different split is a named violation naming both digests."""
    committed = _committed_heldout_digest()
    recorded = "0" * 64
    report = check_probe.run_check(
        _probe_run(
            tmp_path,
            heldout_record=run_ledger.HeldoutRecord(
                document_digest=recorded, membership_count=12
            ),
        ),
        heldout=_COMMITTED_HELDOUT,
    )

    assert report.proceed is False
    assert report.violation is not None
    assert recorded in report.violation
    assert committed in report.violation


def test_a_probe_without_a_heldout_record_is_a_violation(tmp_path: Path) -> None:
    """M3: a probe ledger that applied no split cannot prove the committed one was excluded."""
    report = check_probe.run_check(
        _probe_run(tmp_path, heldout_record=None),
        heldout=_COMMITTED_HELDOUT,
    )

    assert report.proceed is False
    assert report.violation is not None
    assert "no held-out" in report.violation
    assert _committed_heldout_digest() in report.violation


def test_an_unreadable_heldout_document_is_a_refusal(tmp_path: Path) -> None:
    """M3: a document the operator mistyped is a refusal, never a verdict about the probe."""
    unreadable = tmp_path / "heldout.json"
    unreadable.write_text("not json", encoding="utf-8")

    with pytest.raises(check_probe.HeldoutUnreadable) as refusal:
        check_probe.run_check(_probe_run(tmp_path), heldout=unreadable)
    assert str(unreadable) in str(refusal.value)


def test_a_refusal_takes_precedence_over_a_budget_violation(tmp_path: Path) -> None:
    """Refusals come first: a typo in `--heldout` is exit 2 even when the probe is also short.

    The two facts are independent, and the operator should see the mistyped path rather than a
    budget violation that sends them looking at the wrong thing.
    """
    unreadable = tmp_path / "heldout.json"
    unreadable.write_text("not json", encoding="utf-8")

    with pytest.raises(check_probe.HeldoutUnreadable):
        check_probe.run_check(
            _probe_run(tmp_path / "short", draws=sampling.K - 1),
            heldout=unreadable,
        )


def test_a_v2_probe_ledger_reads_unsealed_and_still_decides(tmp_path: Path) -> None:
    """Phase 2: no real `/2` ledger exists, so the probe's dual-read tolerance is pinned here.

    `_probe_run` writes through `run_ledger.write`, so its ordinary shape exercises the sealed
    path; this fixture is the generation before the seal, in the probe's own shape. The
    decision must be read from it exactly as before — unsealed, byte-unchanged, and deciding.
    """
    run = _probe_run(tmp_path, unsealed=True)
    path = run / run_ledger.LEDGER_FILE
    before = path.read_bytes()

    verified = run_ledger.verify_document(path)

    assert verified.sealed is False
    report = check_probe.run_check(run)
    assert report.proceed is True
    assert path.read_bytes() == before, (
        "WHY THIS IS A FAILURE: reading a `/2` probe ledger rewrote it. No existing document "
        "is upgraded in place"
    )


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
    assert any(f"draws: {sampling.K}" in line for line in lines), lines
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
    vocabulary, the journal path derivation, the declared budget, or the held-out loader and
    its digest would be a second answer to a question one document already answers — and the
    day they disagreed neither document would say so.
    """
    from whetstone.loop import draws, heldout, ledger
    from whetstone.verify import verdict

    assert check_probe.SOURCES[0] is night.PRIVATE
    assert check_probe.SOURCES[1] is night.PUBLIC
    assert check_probe.read_ledger is ledger.read
    assert check_probe.LEDGER_FILE is ledger.LEDGER_FILE
    assert check_probe.LedgerUnreadable is ledger.LedgerUnreadable
    assert check_probe.Status is verdict.Status
    assert check_probe.evidence_paths is draws.evidence_paths
    assert check_probe.EVIDENCE_DIR is night.EVIDENCE_DIR
    assert check_probe.K is sampling.K
    assert check_probe.read_document is heldout.read_document
    assert check_probe.document_digest_of is heldout.document_digest_of


def test_refusals_are_named_and_closed_by_value_error() -> None:
    """AC8: every refusal is named for exit-2, and `ValueError` closes the tuple — an
    unforeseen crash is a named exit-2, never a traceback."""
    assert check_probe.NotARun in check_probe.REFUSALS
    assert check_probe.LedgerUnreadable in check_probe.REFUSALS
    assert check_probe.NotAProbe in check_probe.REFUSALS
    assert check_probe.IncompleteRun in check_probe.REFUSALS
    assert check_probe.HeldoutUnreadable in check_probe.REFUSALS
    assert check_probe.REFUSALS[-1] is ValueError