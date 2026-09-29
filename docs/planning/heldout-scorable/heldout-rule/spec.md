# Spec — heldout-rule (aspect 2 of heldout-scorable)

**Aspect dir:** `docs/planning/heldout-scorable/heldout-rule/` · **Written:** 2026-09-27.
**Source:** `docs/planning/heldout-scorable/prd.md` (must-haves 2-5; technical
considerations), `docs/planning/heldout-scorable/oracle-predicate/spec.md` (the predicate it
consumes). **Core loop element:** ③ gate (selection input).

## Problem slice

The held-out derivation (`src/whetstone/loop/heldout.py`) draws 12 members from the 66-task
corpus with no notion of whether a member's oracle can be built; two members are permanently
`NO_ORACLE` and the gate cannot fire. Aspect 1 delivered `oracle_fittable`; this aspect
makes the derivation **exclude the class by a digested rule** — the filter is part of the
rule the document seals, so an edit to it invalidates every committed document by design
(the § 10.7 discipline, `PREREGISTRATION.md:514-522`).

## In scope

- `heldout.py`: a rule function applying `oracle_fittable` to the corpus, added to
  `_RULE_FUNCTIONS` so its source is digest-covered; `_RULE_PARAMETERS` gains
  `oracle_budget_chars`; the derivation refuses by name if the parameter disagrees with
  `sources.ORACLE_BUDGET_CHARS` (drift guard).
- The draw runs over the **filtered** population; `select_band` takes the first
  `_PER_BAND_TAKE` of each filtered band (fewer if the band holds fewer); floors
  (`MIN_HELDOUT`, `MIN_PER_BAND`, non-degenerate) run over the post-exclusion membership —
  unmet → `EmptyHeldout` (the published finding), never a loosened floor.
- The document gains a new required, digested field recording the exclusion:
  `excluded: {task_id: reason}`. `refusals` keeps its stratum meaning ("no difficulty
  measured"). `corpus`/`difficulty`/`bands` still cover all 66 — only the draw changes.
- The loader (`read_document`) fails closed on: a document missing `excluded` (the
  pre-amendment shape — a gate pointed at the old document must refuse by name); a
  membership naming an `excluded` id; an `excluded` entry naming an id not in the corpus;
  an `excluded` entry whose task is in `refusals` (the two meanings must never blur).
  Every existing refusal stays.
- Derivation-time machine state: a task whose donor cannot be read is a **named refusal**
  of the derivation (the runbook tells the operator), never a classification — the
  predicate raises (aspect 1 AC5) and the derivation wraps it.
- Document regeneration machinery: `write_document`/`compose_document` updated; the
  recomputation test stays green on the re-derived document.

## Out of scope

The re-mint swap and the actual re-derived committed documents (aspect 3); the amendment
(aspect 4); the runbook (aspect 5); the gate; the budget value; `check-leakage` semantics
(consumes the document unchanged).

## Acceptance criteria (testable, written first)

- **AC1.** A task `oracle_fittable` refuses is never drawn: over the machine corpus, every
  membership member of the recomputed document is `fits=True` (the document's own
  guarantee, asserted by the recomputation test).
- **AC2.** The filter is digest-covered: `_RULE_FUNCTIONS` contains the new rule function
  and `_RULE_PARAMETERS` contains `oracle_budget_chars`; a change to either changes
  `rule_digest()` (test pins the digest input set, not the value).
- **AC3.** Drift guard: `compose_document` refuses by name when `_RULE_PARAMETERS`'
  `oracle_budget_chars` ≠ `sources.ORACLE_BUDGET_CHARS`.
- **AC4.** Floors over the filtered population: a synthetic corpus whose scorable members
  cannot meet `MIN_PER_BAND` in some band (or `MIN_HELDOUT` overall) → `EmptyHeldout` with
  the existing sentences; a band with fewer scorable members than `_PER_BAND_TAKE` draws
  fewer than 4 without error.
- **AC5.** The document records the exclusion: `excluded` names every unfittable corpus
  task with the predicate's reason; `corpus`/`difficulty`/`bands` are unchanged in scope
  (still 66 measured ids); `membership ∩ excluded = ∅`.
- **AC6.** Loader: a document missing `excluded` → named refusal; a membership naming an
  `excluded` id → named refusal; an `excluded` id not in the corpus → named refusal; an
  `excluded` id also in `refusals` → named refusal; every existing refusal still fires on
  its fixture.
- **AC7.** Derivation-time machine state: a task whose donor is unreadable makes the
  derivation refuse by name (the refusal names the task), never excluding it.
- **AC8.** The gate and `check-leakage` consume the new document unchanged (existing tests
  green; `read_document` is the same function by identity).
- **AC9.** Determinism: same corpus + same rule → same document, byte for byte (the
  recomputation pin's property, kept).

## Dependencies & sequencing

Depends on aspect 1 (`oracle_fittable`, identity-imported). Aspects 3-5 depend on this.

## Open questions / risks

- **Where the rule function lives.** `inspect.getsource` must cover it; if it is defined in
  `heldout.py` and delegates to `bakeoff.sources.oracle_fittable` by identity, the digest
  covers the wrapper (the budget *value* is separately in `_RULE_PARAMETERS`). A wrapper is
  the right shape; a copy of the logic would be a second rule.
- **The `excluded` reason at derivation time vs the bakeoff's sentence.** `oracle_fittable`
  returns the bakeoff's own sentences (byte-identical under the default budget) — the
  document records those; no new sentence dialect.
- **`_PER_BAND_TAKE` and the take.** `select_band` already returns `min(take, len(band))`
  by construction (`ids[:take]`); the floors are the binding statement — the amendment
  (aspect 4) states the "4 per band" supersession in words.