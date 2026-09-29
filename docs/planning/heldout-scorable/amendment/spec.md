# Spec — amendment (aspect 4 of heldout-scorable)

**Aspect dir:** `docs/planning/heldout-scorable/amendment/` · **Written:** 2026-09-27.
**Source:** `docs/planning/heldout-scorable/prd.md` (must-have 7),
`docs/planning/_card/issue.md`, `PREREGISTRATION.md` § 8.1, § 10.7, § 10.10 (the precedent),
`tests/test_docs.py` (the guard patterns). **Core loop element:** ③ gate (pre-registration).

## Problem slice

The held-out split is a pre-registered input (§ 10.7, Type 1, 2026-08-24). It is being
re-derived under a new rule (aspects 2-3) — a change to a pinned input that § 3
(`PREREGISTRATION.md:131-138`) makes a **new series** event. The pre-registration must
record it the way this document records everything: a dated Type 1 amendment, committed
**before the measurement it governs runs** (the next gated evaluation), with the rule
pre-committed, the series consequence stated, and nothing silently edited.

## In scope

- A dated Type 1 amendment (§ 10.16 — the next number) that:
  - pre-commits the derivation rule by name: the scorable filter (the digest-sealed rule in
    `heldout.py`, `oracle_budget_chars` = 80,000), the exclusion-by-class property (never a
    hand-picked membership), the re-minted corpus identity (`donor-a-*`/`donor-b-*` labels,
    the #62 pairing), and the floors binding ("4 per band" was the take, not the floor — the
    § 10.7 sentence is superseded, stated, never quietly edited);
  - states the § 3 series consequence: prior figures keyed to the old document (night
    denominators, `gate-001`) are non-comparable; the old series is never extended;
  - states in words what a decision on the new document means: the old series is
    superseded; the 12 oracle-unfittable tasks stay in the corpus with their status
    reported (the document's `excluded` field names them); a `rejected` 0-0 is a valid
    first decision, never dressed as a win;
  - carries the "does not change" clause (§ 10.10's base, the verifier, the gate's terms,
    the budget) and the no-threshold / no-reword-of-§-1-§-4-§-6 invariances;
  - lands in the § 9 amendment log with its row, and edits the status paragraph only where
    the § 10.10 precedent allows.
- A shape guard in `tests/test_docs.py`, watched RED first (the `close-base-7.3` precedent):
  pins the amendment's shape — the Type 1 label sentence, the no-measurement sentence, the
  closure/supersession sentences, the log row, and cross-pins the amendment's budget figure
  against `heldout._RULE_PARAMETERS` and `sources.ORACLE_BUDGET_CHARS` by identity.
- A dated correction blockquote in `docs/ROADMAP.md` where § 12/§ 13 reference the § 10.7
  document's liveness statements (the dated-correction precedent, e.g. the § 10.10
  correction style) — the split is re-derived by § 10.16.

## Out of scope

The re-derivation itself (aspect 3); the gate runbook (aspect 5); `STATUS.md`/`CHANGELOG.md`
entries (the final aspect — the repo's rule: status is written in the same commit the
capability lands, and the capability lands as one branch). No measurement, no thresholds.

## Acceptance criteria (testable, written first)

- **AC1.** The guard is written first and fails against the pre-amendment tree (RED), then
  the amendment satisfies it (GREEN).
- **AC2.** The amendment is dated, labelled Type 1, committed in this unit (the guard pins
  the shape).
- **AC3.** It names the rule and the budget by number, cross-pinned against
  `heldout._RULE_PARAMETERS["oracle_budget_chars"]` and `sources.ORACLE_BUDGET_CHARS` by
  identity (a drift between the amendment and the code is a guard failure).
- **AC4.** It states the series consequence (non-comparability of prior figures; the old
  series never extended) and what a decision on the new document means (supersession; the
  12 excluded tasks reported, never hidden; a `rejected` 0-0 valid) — the guard pins the
  sentences' presence.
- **AC5.** The "does not change" clause and the no-threshold invariance are present (guard).
- **AC6.** The § 9 log row exists, names § 10.16, and matches the log table's shape (guard).
- **AC7.** The § 10.7 sentences are not silently edited: the supersession is recorded by the
  new amendment and the status paragraph edit follows the § 10.10 precedent (guard: the old
  text survives as committed, and the status paragraph points at § 10.16).
- **AC8.** `docs/ROADMAP.md` carries the dated correction naming § 10.16 where the § 10.7
  document is referenced as live.
- **AC9.** The standing integrity sentence ("No amendment has introduced a success
  threshold...") still holds; nothing in § 1, § 4, or § 6 is reworded.

## Dependencies & sequencing

Depends on aspects 2-3 (it states the rule and the corpus identity, never the membership —
can run in parallel with aspect 3). Aspect 5 (`gate-runbook`) depends on this (the runbook
cites the amendment number and the new document).

## Open questions / risks

- **Amendment numbering**: the next free number is § 10.16 (after § 10.15). If the operator
  has filed another amendment meanwhile, take the next free number and say so.
- **The status paragraph**: the § 10.10 precedent permitted exactly one edit above § 10
  (the status paragraph's § 7.3 sentences). This amendment's analog is the § 7.1/§ 10.7
  sentence; the guard pins that no other above-§-10 text moves.