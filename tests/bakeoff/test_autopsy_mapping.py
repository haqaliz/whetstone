"""The fine→coarse mapping and the per-record join: the autopsy's only comparison is its own
assertion.

Phase 2 named what each completion is; this file pins Phase 3, which asserts that naming
against the run's own `attribution.json` (`prd.md` R3). The fine pass and the coarse pass are
two instruments built for two different questions — the first reads the stored text, the
second is the attribution replay that already measured where a diff met git. Neither may drift
from the other, and the join below is the instrument that says so, per record:
`coarse_agrees` is the mapping assertion, and a contradiction is reported as a
`MappingViolation`, **never reconciled** (`prd.md` R-b) — an autopsy that smoothed a record
until it agreed would be reporting the shape it hoped for instead of the one on disk.

The mapping itself is a pure dict, `FINE_TO_COARSE`, in the `_FOLD`/`compare_to_counts` shape
(`attribution.py:257-264, 304-346`). Two members carry the honesty of the whole table:

* **`UNATTRIBUTED` is always allowed.** It means "not graded" — no checkout for the public
  instance — which is orthogonal to what the completion looks like. Both stored runs carry one
  `UNATTRIBUTED` record whose diff is shape-classifiable (`dig-transcripts.md` § 2 shape 2
  note); the always-allowed rule is the thing that keeps those records from reading as
  contradictions.
* **`UNRECOGNISED_SHAPE` maps to the empty set.** Nothing may be asserted about a shape no rule
  claims, so the empty set *is* its assertion: any recorded coarse cause contradicts it.

And a transcript record with **no attribution row** is `recorded_cause=None`,
`coarse_agrees=False` — by name, never skipped (`prd.md` D3): nothing to agree with is a
divergence, and an autopsy that dropped the row would render a run with a hole in its
attribution as a clean one.

All fixtures are tiny synthetic strings with toy names (`adder.py`, `multiplier.py`) —
replicas of the dig's observed shapes, never donor content (`card.md:68-70`).
"""

from __future__ import annotations

from collections.abc import Mapping

from whetstone.bakeoff.attribution import Cause
from whetstone.bakeoff.autopsy import (
    FINE_TO_COARSE,
    DeathKind,
    FineCause,
    MappingViolation,
    Marker,
    autopsy,
    breakdown,
    classify_completion,
    mapping_violations,
    marker_counts,
)
from whetstone.bakeoff.transcript import Transcribed

# --------------------------------------------------------------------------------------------
# Completion fixtures — the same observed shapes the partition file pins, in miniature: a
# well-formed plain-unified diff, a first-hunk death, an overrunning body, a header without
# a hunk, plain prose, the loop collapse, and the planted unrecognisable bytes.
# --------------------------------------------------------------------------------------------

#: Shape 15, the control: a plain-unified diff whose every hunk completes — `WELL_FORMED`.
WELL_FORMED_TEXT = """--- a/adder.py
+++ b/adder.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""

#: Shape 3: the first hunk dies on an unprefixed line — `HUNK_DIES_EARLY`, death `bare-line`.
STUB_TEXT = """--- a/adder.py
+++ b/adder.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a - b
+    return a + b
def add(a, b):
"""

#: Shape 2, the overrun: the hunk declares 6/24 and the body supplies 25 added lines — one
#: more than declared — so `new` goes negative while the walk consumes it and git refuses
#: the patch as corrupt — `HUNK_COUNT_MISMATCH` (`dig-transcripts.md` § 2 shape 2).
_ADDED_OVERFLOW = "".join("+    return a + b\n" for _ in range(25))
EXTENDS_TEXT = f"""--- a/adder.py
+++ b/adder.py
@@ -100,6 +100,24 @@
 def add(a, b):
     return a - b
     return a + b
{_ADDED_OVERFLOW} def add(a, b):
    # placeholder comment
    try:
"""

#: A diff header with no hunk after it — the extractor's own third reason, `HEADER_WITHOUT_HUNK`.
HEADER_ONLY_TEXT = """diff --git a/adder.py b/adder.py
index 1234567..89abcde 100644
"""

#: Plain prose — the inherited-not-observed `NO_DIFF` shape (`prd.md` § 8 gap 2).
PROSE_TEXT = "The bug is that `add` subtracts instead of adding.\n"

#: Shape 1: the loop collapse — chat-template tokens only, `IM_START_LOOP`.
LOOP_TEXT = "<|im_start|>\n" * 30

#: The planted unrecognisable completion: control bytes — `UNRECOGNISED_SHAPE` by name.
GARBAGE_TEXT = "\x00\x01\x02\x03\x04\x05\x06\x07\x08" * 16


def _transcribed(candidate: str, task_id: str, completion: str) -> Transcribed:
    """One stored generation, synthetic: a toy prompt and one of the completion fixtures above."""
    return Transcribed(
        candidate=candidate,
        task_id=task_id,
        prompt_sha256="0" * 64,
        prompt=f"Fix the bug in {task_id}.",
        completion=completion,
        attempt=1,
        decision="graded",
    )


#: One completion per fine cause, so the always-allowed rule is exercised on every cause — not
#: just the ones the main fixture happens to carry. The expected cause is named per row; the
#: test below proves each fixture actually classifies to it, so the rule is never tested against
#: a fixture that claims a cause it does not produce.
UNATTRIBUTED_COMPLETIONS: tuple[tuple[str, FineCause], ...] = (
    (LOOP_TEXT, FineCause.IM_START_LOOP),
    (STUB_TEXT, FineCause.HUNK_DIES_EARLY),
    (EXTENDS_TEXT, FineCause.HUNK_COUNT_MISMATCH),
    (HEADER_ONLY_TEXT, FineCause.HEADER_WITHOUT_HUNK),
    (WELL_FORMED_TEXT, FineCause.WELL_FORMED),
    (PROSE_TEXT, FineCause.NO_DIFF),
    (GARBAGE_TEXT, FineCause.UNRECOGNISED_SHAPE),
)

#: The same completions filed under `toy-u`, with `UNATTRIBUTED` recorded on every row — the
#: always-allowed rule's fixture, one row per fine cause in the list above.
UNATTRIBUTED_TRANSCRIBED: tuple[Transcribed, ...] = tuple(
    _transcribed("toy-u", f"task-{index}", text)
    for index, (text, _) in enumerate(UNATTRIBUTED_COMPLETIONS)
)
UNATTRIBUTED_ATTRIBUTIONS: Mapping[tuple[str, str], Cause] = {
    ("toy-u", f"task-{index}"): Cause.UNATTRIBUTED
    for index in range(len(UNATTRIBUTED_COMPLETIONS))
}


# --------------------------------------------------------------------------------------------
# The main fixture: six synthetic rollouts across three toy candidates, covering an agreeing
# record per coarse bucket, the always-allowed row, a missing attribution row, and a planted
# contradiction.
# --------------------------------------------------------------------------------------------

#: Six stored generations: `toy-a` agrees on both rows (APPLIED / WOULD_NOT_PARSE), `toy-b`
#: carries the missing attribution row (`task-2`) and the always-allowed row (`task-3`), and
#: `toy-c` carries the planted contradiction — a well-formed diff recorded as `NO_DIFF_HEADER`.
TRANSCRIBED: tuple[Transcribed, ...] = (
    _transcribed("toy-a", "task-1", WELL_FORMED_TEXT),
    _transcribed("toy-a", "task-2", STUB_TEXT),
    _transcribed("toy-b", "task-1", WELL_FORMED_TEXT),
    _transcribed("toy-b", "task-2", GARBAGE_TEXT),
    _transcribed("toy-b", "task-3", LOOP_TEXT),
    _transcribed("toy-c", "task-1", WELL_FORMED_TEXT),
)

#: The recorded coarse causes, keyed by `(candidate, task_id)` — the shape the run's own
#: `attribution.json` is read as. `toy-b`/`task-2` is deliberately absent: the missing-row case.
ATTRIBUTIONS: Mapping[tuple[str, str], Cause] = {
    ("toy-a", "task-1"): Cause.APPLIED,
    ("toy-a", "task-2"): Cause.WOULD_NOT_PARSE,
    ("toy-b", "task-1"): Cause.PARSED_BUT_DID_NOT_APPLY,
    ("toy-b", "task-3"): Cause.UNATTRIBUTED,
    ("toy-c", "task-1"): Cause.NO_DIFF_HEADER,
}


# --------------------------------------------------------------------------------------------
# The mapping's completeness: every fine cause has exactly one entry, both directions.
# --------------------------------------------------------------------------------------------


def _missing_entries(mapping: Mapping[FineCause, frozenset[Cause]]) -> set[FineCause]:
    """Fine causes `mapping` has no entry for — the failure a planted cause would produce."""
    return set(FineCause) - set(mapping)


def test_fine_to_coarse_covers_every_fine_cause_in_both_directions() -> None:
    """Every `FineCause` has an entry, and every entry names a real cause (`prd.md` R3).

    The `test_attribution.py:299-332` shape: a cause added to the enum with no entry fails
    here, and an entry for a cause that does not exist fails too. `UNRECOGNISED_SHAPE` is a
    member — the empty set is still an assertion — it just asserts nothing may be claimed about
    that shape, which is exactly the point of its entry.
    """
    assert set(FINE_TO_COARSE) == set(FineCause), (
        f"FINE_TO_COARSE keys are {sorted(FINE_TO_COARSE)} but the fine causes are "
        f"{sorted(FineCause)}.\n\n"
        "WHY THIS MATTERS: a fine cause with no mapping entry would make the join assert "
        "nothing about it — `coarse_agrees` would fall through to whatever the code happens "
        "to do, and the mapping would be whatever the code does rather than a table somebody "
        "wrote down and read."
    )
    assert FINE_TO_COARSE[FineCause.UNRECOGNISED_SHAPE] == frozenset(), (
        "UNRECOGNISED_SHAPE must map to the empty set: nothing may be asserted about a shape "
        "no rule claims (`prd.md` R3). A non-empty entry would give the named terminal a "
        "coarse cause nobody has grounded."
    )


def test_a_planted_missing_entry_is_reported_by_the_completeness_check() -> None:
    """The check above, proven able to fail: a mapping with one entry dropped must be caught.

    `CONTRIBUTING.md:56-60` — an honesty guard must be seen failing. A dict that drops a
    single entry must show up in `_missing_entries`, or the completeness test above could be
    passing for a mapping nobody has added a cause to.
    """
    planted = {
        cause: allowed
        for cause, allowed in FINE_TO_COARSE.items()
        if cause is not FineCause.NO_DIFF
    }

    assert _missing_entries(planted) == {FineCause.NO_DIFF}, (
        f"a mapping missing the NO_DIFF entry produced {_missing_entries(planted)}.\n\n"
        "WHY THIS MATTERS: the completeness assertion must be able to fail — a planted fifth "
        "cause, or a cause silently dropped from the table, is exactly the drift this slice "
        "exists to catch."
    )


# --------------------------------------------------------------------------------------------
# The join: one record per transcript row, agreeing exactly when the recorded cause is in the
# fine cause's allowed set.
# --------------------------------------------------------------------------------------------


def test_a_record_agrees_exactly_when_its_recorded_cause_is_in_its_allowed_set() -> None:
    """The agreement flag is the membership check itself, per record.

    `APPLIED` on a well-formed diff agrees; `WOULD_NOT_PARSE` on a first-hunk death agrees;
    `PARSED_BUT_DID_NOT_APPLY` on a well-formed diff agrees; `UNATTRIBUTED` always agrees; and
    `NO_DIFF_HEADER` on a well-formed diff does not. The record carries the verdict, the
    recorded cause and the agreement in one row, so a document reads as a whole record.
    """
    records = autopsy(TRANSCRIBED, ATTRIBUTIONS)
    by_key = {(r.candidate, r.task_id): r for r in records}

    assert by_key[("toy-a", "task-1")].coarse_agrees is True
    assert by_key[("toy-a", "task-2")].coarse_agrees is True
    assert by_key[("toy-b", "task-1")].coarse_agrees is True
    assert by_key[("toy-b", "task-2")].coarse_agrees is False
    assert by_key[("toy-b", "task-3")].coarse_agrees is True
    assert by_key[("toy-c", "task-1")].coarse_agrees is False, (
        "a well-formed diff recorded as NO_DIFF_HEADER must not agree.\n\n"
        "WHY THIS MATTERS: WELL_FORMED can only explain APPLIED or PARSED_BUT_DID_NOT_APPLY "
        "(`prd.md` R3); NO_DIFF_HEADER says the run recorded no diff at all. An agreement here "
        "is the credulous mapping the watched-failing test below exists to refuse."
    )


def test_a_record_carries_its_fine_verdict_beside_the_recorded_coarse_cause() -> None:
    """The record is the join: nothing is dropped in it.

    The classification (`cause`, `detail`, `markers`) rides alongside the recorded coarse
    cause, so the document's rows are whole records and the breakdowns need no second pass
    over the transcript. The detail is the fine pass's own — the death kind on a dies-early
    record, not a paraphrase.
    """
    records = autopsy(TRANSCRIBED, ATTRIBUTIONS)
    by_key = {(r.candidate, r.task_id): r for r in records}

    loop_record = by_key[("toy-b", "task-3")]
    assert loop_record.cause is FineCause.IM_START_LOOP
    assert Marker.LOOP_PRESENT in loop_record.markers
    assert loop_record.recorded_cause is Cause.UNATTRIBUTED

    stub_record = by_key[("toy-a", "task-2")]
    assert stub_record.cause is FineCause.HUNK_DIES_EARLY
    assert stub_record.detail == DeathKind.BARE_LINE.value
    assert stub_record.recorded_cause is Cause.WOULD_NOT_PARSE


# --------------------------------------------------------------------------------------------
# The watched-failing honesty test: a recorded cause contradicting its fine cause must be
# reported as a violation, never reconciled (`prd.md` R-b).
# --------------------------------------------------------------------------------------------


def test_a_contradicting_recorded_cause_is_reported_never_reconciled() -> None:
    """`WELL_FORMED` with a recorded `NO_DIFF_HEADER` is a violation, reported verbatim.

    `toy-c`/`task-1`'s completion is a diff whose every hunk completes; the run recorded it as
    `NO_DIFF_HEADER` — the two instruments disagree about the same rollout. The mapping
    assertion exists to surface exactly this, and the violation names both sides. The autopsy
    may not smooth the verdict to make the record agree: reconciling would turn a measurement
    disagreement into a measurement.
    """
    violations = mapping_violations(autopsy(TRANSCRIBED, ATTRIBUTIONS))

    assert len(violations) == 1, (
        f"expected exactly the one planted contradiction, got {len(violations)}:\n"
        + "\n".join(
            f"  {v.candidate}/{v.task_id}: {v.fine_cause.value} recorded as "
            f"{v.recorded_cause.value}"
            for v in violations
        )
        + "\n\nWHY THIS MATTERS: this test is watched failing against a credulous mapping "
        "that always agrees — a mapping with no teeth reports zero violations, and zero reads "
        "as 'the two instruments agree', which is the claim this slice's finding is built on."
    )
    assert violations[0] == MappingViolation(
        candidate="toy-c",
        task_id="task-1",
        fine_cause=FineCause.WELL_FORMED,
        recorded_cause=Cause.NO_DIFF_HEADER,
    )


# --------------------------------------------------------------------------------------------
# The missing attribution row: named, counted, never skipped (`prd.md` D3).
# --------------------------------------------------------------------------------------------


def test_a_record_with_no_attribution_row_is_counted_never_skipped() -> None:
    """A transcript record with no attribution row is `None`/`False` by name, never dropped.

    The join is per `(candidate, task_id)` against the run's own attribution rows; a row
    missing from `attribution.json` means the run never recorded a coarse cause for this
    rollout — "nothing to agree with", which `coarse_agrees=False` names. Dropping the record
    instead would make the autopsy look clean over a partial join, which is the failure mode
    `attribution.py`'s `UNATTRIBUTED` exists for.
    """
    records = autopsy(TRANSCRIBED, ATTRIBUTIONS)

    assert len(records) == len(TRANSCRIBED), (
        f"autopsy() returned {len(records)} records for {len(TRANSCRIBED)} transcript rows.\n\n"
        "WHY THIS MATTERS: a missing attribution row must never shrink the output — the "
        "counts must total over every rollout the run produced."
    )

    missing = [r for r in records if (r.candidate, r.task_id) == ("toy-b", "task-2")]
    assert len(missing) == 1
    assert missing[0].recorded_cause is None
    assert missing[0].coarse_agrees is False

    not_agreeing = [r for r in records if not r.coarse_agrees]
    assert any(r.candidate == "toy-b" and r.task_id == "task-2" for r in not_agreeing), (
        "the missing-row record is not among the records that do not agree.\n\n"
        "WHY THIS MATTERS: a missing attribution row is a divergence (nothing to agree "
        "with), and it must be counted as one — an autopsy that only reported recorded "
        "contradictions would render a run with a hole in its attribution as a clean one."
    )


# --------------------------------------------------------------------------------------------
# UNATTRIBUTED is always allowed — on every fine cause, including the empty-set one.
# --------------------------------------------------------------------------------------------


def test_each_unattributed_fixture_classifies_to_the_cause_it_names() -> None:
    """Anti-vacuity: each fixture actually produces the fine cause its row claims.

    The always-allowed test below is only meaningful if the fixture list genuinely covers one
    completion per fine cause — a fixture that classified to something else would make it pass
    over a subset, with the omitted causes' rows asserted by nobody.
    """
    for text, expected in UNATTRIBUTED_COMPLETIONS:
        assert classify_completion(text).cause is expected, (
            f"the fixture for {expected.value} classified to {classify_completion(text).cause!r}."
        )


def test_unattributed_is_always_allowed_on_every_fine_cause() -> None:
    """`UNATTRIBUTED` recorded on any fine cause agrees: it means "not graded", not "contradicts".

    The two stored runs each carry an `UNATTRIBUTED` record whose diff is shape-classifiable
    (`dig-transcripts.md` § 2 shape 2 note) — "we could not grade this" is orthogonal to what
    the completion looks like (`prd.md` R3). Every fine cause must agree with it, including
    `UNRECOGNISED_SHAPE`, which agrees with nothing else.
    """
    records = autopsy(UNATTRIBUTED_TRANSCRIBED, UNATTRIBUTED_ATTRIBUTIONS)

    assert all(record.coarse_agrees for record in records), [
        (r.candidate, r.task_id, r.cause.value) for r in records if not r.coarse_agrees
    ]
    assert mapping_violations(records) == ()


# --------------------------------------------------------------------------------------------
# The breakdowns: absent causes are absent, never zero (`attribution.py:227-242`).
# --------------------------------------------------------------------------------------------


def test_breakdown_omits_causes_that_never_occurred() -> None:
    """`breakdown` per candidate; a cause that never occurred has no key, never a zero.

    A zero is indistinguishable from a bucket that stopped matching anything — the difference
    between "this never happened" and "this stopped being observed" is the difference between
    a finding and a broken instrument. `toy-b` carries no `NO_DIFF` or `HUNK_DIES_EARLY`
    record, so its row must not carry those keys.
    """
    counts = breakdown(autopsy(TRANSCRIBED, ATTRIBUTIONS))

    assert counts == {
        "toy-a": {FineCause.WELL_FORMED: 1, FineCause.HUNK_DIES_EARLY: 1},
        "toy-b": {
            FineCause.WELL_FORMED: 1,
            FineCause.UNRECOGNISED_SHAPE: 1,
            FineCause.IM_START_LOOP: 1,
        },
        "toy-c": {FineCause.WELL_FORMED: 1},
    }, counts
    assert FineCause.NO_DIFF not in counts["toy-b"]
    assert FineCause.HUNK_DIES_EARLY not in counts["toy-b"]
    assert FineCause.HUNK_COUNT_MISMATCH not in counts["toy-a"]
    assert breakdown(()) == {}


def test_marker_counts_omit_markers_that_never_occurred() -> None:
    """`marker_counts` keeps the same discipline: markers are counted, absent ones never zeroed.

    Markers are observations, not causes (`prd.md` D4), so they count separately from the
    partition — with the same absent-never-zero rule, for the same reason. `toy-a` carries no
    marker anywhere, so its row is the empty dict, not a row of zeroes.
    """
    counts = marker_counts(autopsy(TRANSCRIBED, ATTRIBUTIONS))

    assert counts == {
        "toy-a": {},
        "toy-b": {Marker.LOOP_PRESENT: 1},
        "toy-c": {},
    }, counts
    assert Marker.NOOP_HUNKS not in counts["toy-b"]
    assert marker_counts(()) == {}


# --------------------------------------------------------------------------------------------
# Determinism (spec AC1): same inputs, identical output, every derived count included.
# --------------------------------------------------------------------------------------------


def test_the_same_inputs_yield_identical_records() -> None:
    """Determinism (`prd.md` R4): same transcript + attribution → identical records tuple.

    The autopsy's documents are compared across runs and across machines; a join whose result
    depended on set or dict iteration order would make a deterministic analysis produce
    non-deterministic output. The records and every derived count are checked, because the
    document writes all of them.
    """
    first = autopsy(TRANSCRIBED, ATTRIBUTIONS)
    second = autopsy(TRANSCRIBED, ATTRIBUTIONS)

    assert first == second
    assert breakdown(first) == breakdown(second)
    assert marker_counts(first) == marker_counts(second)
    assert mapping_violations(first) == mapping_violations(second)
