# Spec — promotion-record-n (aspect 1 of honest-number-report)

## Problem slice

The pre-registered shape requires `N: f at baseline, g at final` (`PREREGISTRATION.md:57-72`),
but the final side's `N` has no on-disk source: `SideCounts` in the promotion record
(`whetstone-promotion/1`, written by `src/whetstone/loop/gate.py`) has no `weaker_wins` field
and the gate writes no per-rollout evidence. The P4 report writer is the "later reader" the
record's own docstring anticipated (gate.py:97: "checked on read by nobody yet — the record is
written, never read back by this module — and named so a later reader has one answer to 'what
shape is this file'"). This aspect records `N_final` at scoring time and ships the fail-closed
reader that reader needs.

## In-scope

- `SideCounts` gains `weaker_wins`, recorded at scoring time (the gate's `_counts(rollouts,
  tasks)` has the `Rollout` records at hand; the definition is `report.tally`'s by identity:
  `weak is Status.PASS and strict is Status.FAIL` — never a new definition, never a rate).
- The `whetstone-promotion/1` schema documentation updated with the new field.
- `read_promotion_record(path) -> PromotionRecord` — the fail-closed reader: unknown fields,
  wrong/missing schema, unreadable JSON, counts that don't sum
  (`solved + failed + unverified == denominator`), `weaker_wins > denominator`, and a
  missing `weaker_wins` (records written before this field existed) are each refused by name
  — never defaulted.
- The existing promotion-record writer's tests updated (schema round-trip, deterministic
  payload) and extended with the new field and the reader's refusals.

## Out-of-scope

- Any change to the gate's decision logic, retry discipline, or exit codes.
- Rollout-level evidence documents (the record stays counts-only).
- Reading the record anywhere except this unit's door and its tests.
- `src/whetstone/verify/`, `patch.py`, `attribution.py` — AC2 pins, byte-untouched.

## Acceptance criteria

1. A promotion record written by the gate now carries `weaker_wins` per side, equal to
   `report.tally`'s definition over the same rollouts — asserted by identity, not by a copied
   formula.
2. `read_promotion_record` returns the record's counts verbatim; a clean round-trip holds.
3. Each refusal is by name, nothing defaulted: unreadable file; wrong schema; unknown field;
   counts not summing to the denominator; `weaker_wins > denominator`; missing `weaker_wins`.
4. A pre-field record (fixture without `weaker_wins`) is refused by name — the reader never
   defaults it to zero (zero is a measurement, absence is a fact).
5. The gate's own tests still pass unchanged where they assert the record's other fields;
   the record's payload remains deterministic and the suite stays green.
6. The AC2 pins and the partition guard hold; no new inference import anywhere.

## Dependencies & sequencing

- Depends on: the shipped gate (`gate.py`, `SideCounts`, `write_promotion_record`,
  `PROMOTION_SCHEMA`), `report.tally`'s `weaker_wins` by identity.
- First of the five aspects: the door (aspect 3) consumes the reader; nothing else blocks on
  this aspect.

## Open questions

- None — the field placement (`SideCounts`) and the refusal surface are fixed by the dig and
  the PRD decisions.