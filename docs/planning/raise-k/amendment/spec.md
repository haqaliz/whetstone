# Spec — `amendment` (raise-k)

**Aspect:** pre-register the raised budget as a Type 1 amendment, supersede § 10.9's value,
and cross-pin the document to the constant.
**Source:** `docs/planning/raise-k/prd.md` (M5, M6, M8; AC5, AC7).

## Problem slice

§ 8.1 requires the input of a measurement be pinned **before** the measurement it governs
runs. The loop's draw budget is such an input (`docs/ROADMAP.md:775`). § 10.9 (a Type 2
disclosure, `PREREGISTRATION.md:565-580`) names the value then in force as
`sampling.K = 8`. A new amendment must pin `16`, mark § 10.9's value superseded (without
editing § 10.9's body — the document is append-only), and add the doc↔code cross-pin the dig
found absent for `sampling.K`.

## In scope

- Append `### 10.19 <title> — 2026-10-17` to `PREREGISTRATION.md`, in the § 10.18 (Type 1)
  shape: bold `**Type 1 (§ 8.1): …` line; **What changes** (8 → 16); **The blast radius**
  (every prior loop figure non-comparable); a comparability paragraph ending *"the old series
  is not extended"*; the § 10.9 supersession sentence; closing **What is not claimed.**.
- Append the amendment-log row after `PREREGISTRATION.md:327`.
- Add a `tests/test_docs.py` guard pinning § 10.19's shape **by interpolating `sampling.K`**.
- Update `tests/test_docs.py`'s § 10.9 guard so it no longer asserts a now-historical value
  as if current.

## Out of scope

- § 10.9's body (preserved byte-intact). Any other § 10.x body. The ROADMAP prose (that is
  the `prose` aspect).

## Acceptance criteria (testable, watched failing first)

- **AC2.1** `tests/test_docs.py`: a guard asserts `sampling.K == 16` from the code and
  `f"sampling.K = {sampling.K}"` in the flattened document — the missing doc↔code cross-pin.
- **AC2.2** The same guard asserts § 10.19's Type 1 line, the `8` → `16` move, a
  non-comparability sentence, the § 10.9-supersession sentence, and the exact amendment-log
  row substring.
- **AC2.3** `tests/test_docs.py`'s § 10.9 test is updated: it keeps the two § 10.9 identity
  substrings (`"seeded categorical sampler"`, `"differs from every published contract's greedy
  sampler"`) and drops the bare `"sampling.K = 8"` current-value assertion; the value is pinned
  by AC2.1 instead. Watched failing before the edit.
- **AC2.4** `PREREGISTRATION.md` still contains no `%`/`percent`/placeholder token and its
  `PREREGISTRATION_SECTIONS` tuple is unchanged.

## Amendment content (exact shape to write)

- Title: `### 10.19 The nightly loop's draw budget is raised from 8 to 16 — 2026-10-17`
- Type line: `**Type 1 (§ 8.1): pins an input of the measurement it precedes, committed before
  the night it governs runs.** It introduces no success threshold, rewords nothing in § 1, § 4
  or § 6, and does not change the base § 10.10 pinned.`
- Log row: `| 2026-10-17 | The nightly loop's draw budget is raised from 8 to 16 (§ 10.19) |
  1 — pins the inputs of a measurement | Yes |` (the `Yes` matches the § 10.18 precedent).

## Dependencies / sequencing

Depends on `declaration` (the constant must be `16` before the cross-pin is written). Must be
committed **before** any night that records `16`.

## Open questions / risks

- The § 10.9 guard edit (AC2.3) is a guard *weakening* unless the dropped literal is picked
  up by AC2.1 — the plan replaces it with the cross-pin, keeping the net strength.
- `Closes an open item = Yes` is the § 10.18 precedent; the strict § 8.1 reading ("closes a
  § 7 item") would say `No`. Recorded in the PRD; default `Yes`.
