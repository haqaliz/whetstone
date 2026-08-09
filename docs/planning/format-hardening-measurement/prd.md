# PRD — `format-hardening-measurement`

**Card:** `docs/planning/_card/issue.md` · **Understanding:**
`docs/planning/format-hardening-measurement/understanding.md`
**Upstream:** `docs/planning/p2-format-hardening/measured-arm/plan_20260809.md` (Phases 3–4),
`runbook.md` (post-run section), `spec.md` (D-arm3, D-arm4, AC3–AC5), `p2-format-hardening/prd.md`
(R5, R6), `p2-diff-autopsy/finding.md` (the finding-document precedent).

---

## 1. The problem

The `p2-format-hardening` measured-arm aspect shipped its machinery and its runbook, and
stopped. What it did not ship is the analysis chain its own runbook names but does not provide:
**"assembled from the autopsy documents by the Phase 3 comparison tooling"
(`runbook.md:136-138`)**. No such tooling exists (`src/whetstone/bakeoff/` has
`preanalysis.py` but no comparison module; the word "comparison" belongs only to the shipped
report writer). The report writer is shipped but **has no production caller** —
`build_contract_comparison`/`write_comparison` (`report.py:577,673`) are exercised only by
tests. `measured-arm/finding.md` does not exist. `CLAUDE.md`'s aspect-4 paragraph and
`CHANGELOG.md` still describe the deliverable as unspent.

Consequence: even after the operator runs the GPU arm, the slice's deliverable — the measured
before/after cause breakdown and the published two-contract report — **cannot be produced**.
Every figure would have to be hand-assembled from journals and autopsy documents, which is the
exact failure mode this repo's instrumented-measurement discipline exists to prevent
(`p2-diff-autopsy/finding.md` — the read must be a measurement, not a hand-read).

## 2. What is already decided upstream (not re-litigated)

| Decided | Where |
|---|---|
| The arm's run is operator-executed; everything after it (attribution, autopsy, breakdown, report assembly) is deterministic, offline, agent-verifiable | `measured-arm/spec.md` D-arm3 |
| The before/after is a comparison of **contracts**, never of models; a bucket shift is a contract effect | `spec.md` D-arm4; `prd.md` R6 |
| The breakdown lives in gitignored homes; the published report points at them and never restates a classifier count | `prd.md:230-234`; `runbook.md:139-141`; `finding.md:89-92` |
| The ceiling the arm was measured against (113) is reported alongside the after breakdown | `prd.md:243-248`; `runbook.md:139-141` |
| A flat before/after is a valid, publishable outcome; no threshold is introduced | `prd.md:235-236`; yield-probe R9 |
| `src/whetstone/verify/`, `patch.py`, `attribution.py` are frozen byte-identical to `origin/master` | `prd.md` R7; card AC2 |
| The comparison tooling is code and follows TDD — RED first on synthetic autopsy documents | `plan_20260809.md:138-142` |
| Output home: `runs/format-hardening-preanalysis/comparison.md` (gitignored) | `runbook.md:136-138` |
| The report renders both arms under their own contract fields with the non-comparability sentence, both token spends, the ceiling, and the breakdown pointer | `prd.md` R6; `plan_20260809.md:106-111` |
| The finding states the measured before/after, the halt/hold decision, and what is not claimed (no raised count predicted, no § 7.3 close, no base selected) | `plan_20260809.md:112-114` |
| CLAUDE.md status block + CHANGELOG final updates land in the same commit as the capability | `plan_20260809.md:115`; `CLAUDE.md:263-267` |

## 3. Decisions taken in this unit

**D1 — A new `comparison.py` sibling module, not an extension of `preanalysis.py`.** The
pre-analysis module's ceiling measurement and output shape are pinned by its own tests
(`test_preanalysis.py:564-598` pins the document byte-for-byte); adding the before/after
assembly would give it two responsibilities and a second schema. The new module follows the
established pattern: stdlib-only, deterministic, offline, own no-inference AST walk, output
refused under published paths, schema `whetstone-comparison/1`. It reuses by identity:
`preanalysis.analyze_document` (the strict autopsy-document read), `preanalysis.combine`,
`diffcheck.trigger_of_cause` (the trigger mapping — never reimplemented), `journal`'s own
journal parse (the per-run record of record), and `autopsy.IGNORED_OUT_ROOTS` / the
`refuse_published_out` pattern.

**D2 — The comparison writes a schema'd JSON document and a rendered markdown breakdown.**
`runs/format-hardening-preanalysis/comparison.md` is the runbook's named home, and the
autopsy/preanalysis precedent is JSON documents. Both: the JSON is the machine-readable
measurement (byte-deterministic, `sort_keys`); the markdown is its render, for the operator
and the finding. Both refused under published paths (`OutNotPrivate`, the established door).

**D3 — Read set: journals + autopsy documents + the pre-analysis document.** Journals carry
per-`(candidate, task)` rollout records with `outcome`, `verdict_kinds`, and
`generation_seconds` — the source for per-candidate tallies and summed token spend. Autopsy
documents carry the cause breakdowns. The pre-analysis document (`ceiling.json`) carries the
ceiling and the per-record trigger decisions the arm was measured against. The stored
`runs/arm-a/` and `runs/budget-2048/` hold journal + autopsy artifacts but **no** report or
cost file; the journal is the per-run record of record.

**D4 — The mapping is asserted, never reconciled.** The comparison re-derives
`diffcheck.trigger_of_cause` per autopsy record and asserts agreement with the pre-analysis
document's `decisions` rows. A contradiction is written into the comparison document as a
named violation and the run exits nonzero — reported, never smoothed (the autopsy's own
contract, `autopsy.py:644-667`). Nonzero `mapping_violations` in any input autopsy document
are surfaced the same way.

**D5 — The Phase-4 report door is built now, rendered later.** A deterministic CLI (in the
comparison module, `--render-report` mode) builds the `ContractArm`s — per-candidate tallies
from the journal, contract from the arm's sidecar (`GenerationContract.parse`, which backfills
the old five-field shape), `generation_seconds` summed from the journal — and calls
`build_contract_comparison` + `write_comparison` into `reports/format-hardening/`. Tested on
synthetic arms; the published render stays the committed declaration until the arm runs, so
the post-run render is one command. The before-arms' contracts come from
`reports/baseline/report.json`'s `generation_contract` block (the yield-probe arm-a reproduced
the baseline contract exactly); the after-arm's from its own run's report sidecar.

**D6 — Disclosures, not fusions.** Two shapes that differ and must not be fused: (a) journal
rollout counts (tallies' denominator) vs autopsy record counts (classified completions) —
different measurements of the same run, reported side by side, never reconciled into one
number; (b) the new arm's scored set excludes the declared dev subset (five ids), so its
denominator is smaller — the arm's contract field carries `dev_subset`, and the comparison
states the difference explicitly.

**D6a — Three autopsy documents, two published arms.** The before/after *breakdown* covers
all three runs per candidate — stored arm-a, stored budget-2048, and the new arm — because
the ceiling was measured over the two stored runs and the dig's before/after question is
about the stored parse refusals. The published report covers **exactly two arms** — arm-a
under the baseline contract and the new arm under the hardened contract; **budget-2048 (a
yield-probe run at double tokens) appears only in the gitignored breakdowns, never in
`reports/format-hardening/`**. The report door's contract sidecar is therefore unambiguous:
arm-a's contract is read from `reports/baseline/report.json`'s `generation_contract` block
(the yield-probe arm-a reproduced the baseline contract exactly); the new arm's from its own
run's report sidecar.

**D7 — The stale claim is fixed in the rewrite.** `CLAUDE.md:261` says "No version has been
released and there are no tags"; **v0.3.0 is tagged** (`1ebe09c` → tag `5d3faf4`). The status
block is being rewritten anyway; the fix lands in the same commit.

## 4. Requirements

### R1 — The comparison module (must-have)

- CLI `python -m whetstone.bakeoff.comparison --journal PATH [--journal ...] --autopsy PATH
  [--autopsy ...] --preanalysis PATH --out PATH`, exit 2 with the reason named, in a fixed
  order: `--out` refusal **before anything is read** (the pre-analysis discipline,
  `preanalysis.py:469`); missing file; duplicate stems (the stem is the run's key — a
  collision is refused, never fused, `preanalysis.py:487-495`); unparseable document or
  unknown `cause` (exit 2 naming the string).
- Per-arm, per-candidate: cause counts from the autopsy document (absent causes absent —
  the autopsy contract, `autopsy.py:670-683`), tallies from the journal, generation seconds
  summed from the journal, and the arm's contract identity.
- The before/after: each arm's per-candidate cause counts side by side, with the delta
  against a named "before" arm (the two stored arms are the before; the new arm is the
  after), rendered per candidate — never pooled into one total (the autopsy's
  per-candidate discipline, `autopsy.py:676-677`).
- The ceiling: carried from the pre-analysis document's own numbers, not recomputed.
- D4's assertion (contradiction → named violation + nonzero exit, never reconciled).
- D6's disclosures written into the document (rollout-vs-autopsy denominators, dev-subset
  exclusion).
- Byte-deterministic output: same inputs → same bytes, tested (the `sort_keys` + indent
  precedent).
- The no-inference AST walk over module + test, with anti-vacuity controls (the
  `test_preanalysis.py:687-745` pattern).

### R2 — The markdown render (must-have)

- `comparison.md` at the runbook's named home: per-candidate tables, the deltas, the
  trigger/ceiling numbers, the disclosures, any named violations. It may carry classifier
  counts — it is gitignored — but nothing in it may be restated in a published document.

### R3 — The report door (must-have)

- Deterministic CLI that builds the `ContractArm`s and renders
  `reports/format-hardening/{report.md,report.json,cost.json}` via the shipped writer
  (`write_comparison`), with both arms, both contracts, per-arm token spend, the ceiling
  pointed at via `breakdown_home` (never committed — the one-home guards refuse a fourth
  file), the non-comparability sentence, and the pointer to the gitignored breakdown home.
- When an arm has not run (no journal/contract), the door refuses rather than rendering a
  half-truth — except the committed declaration, which is the arms-empty render.
- **Control discipline.** The door verifies each arm's harness-proven status from its journal
  (the probe records carry the control; `sweep.rankable` raises `HarnessNotProven` when the
  control did not pass) and refuses an arm whose control did not prove the harness — nothing
  from such a run may become a count, in the report or in the breakdown.
- Synthetic-arm tests: distinct contract fields per arm (retry trio present only on the
  hardened arm), token spend per arm in prose and in `cost.arms[].generation_seconds`, and
  no `N of M` figure colliding with `reports/baseline/` (the disjointness rule,
  `test_report.py:1259-1281`).

### R4 — The finding (must-have)

- `docs/planning/p2-format-hardening/measured-arm/finding.md`, in the `p2-diff-autopsy/finding.md`
  shape: measured before/after (pointing at the gitignored homes), the halt/hold decision,
  and the not-claimed list — no raised count predicted, no § 7.3 close, no base selected.
  **No figure about a model inside the finding** — walls and decisions in words, numbers in
  the breakdowns.

### R5 — Status block + CHANGELOG (must-have)

- `CLAUDE.md`: the aspect-4 paragraph (lines 234-254) rewritten to its completed state; the
  stale no-tags claim at line 261 corrected (D7); nothing above the status block edited.
- `CHANGELOG.md`: entries for the comparison tooling, the report door, and the finding under
  the unit's version section — placement per the gate's decision on the open question below.
- The present-tense no-figure claims stay absent (`test_docs.py:248-297`); no proportion and
  no placeholder anywhere in `PREREGISTRATION.md` (untouched).

### R6 — Gates (must-have)

- `uv run pytest tests/bakeoff/test_comparison.py` green, RED first (the comparison's tests
  are written before its code).
- Full suite green; `ruff check .`, `mypy src/`, `whetstone --help` exit 0.
- The one-home guards green — the six-file `reports/` list unchanged, and a planted fourth
  file still fails both (`test_report.py:1353`, `test_transcript_locality.py:73`).
- Frozen-path stasis: `src/whetstone/verify/`, `patch.py`, `attribution.py` byte-identical
  to `origin/master`; the reward-path guard and its scope partition pass unchanged.
- `tests/test_docs.py` green.

## 5. Acceptance criteria

Every one is a command that exits 0 or an artifact that exists.

1. `uv run pytest tests/bakeoff/test_comparison.py` — RED first, then green.
2. The comparison module over the two stored arms' real autopsy + journal documents produces
   `runs/format-hardening-preanalysis/comparison.md` and the `whetstone-comparison/1` JSON,
   verified byte-identical across invocations; the per-record trigger mapping asserts clean
   against the pre-analysis document; the JSON and the markdown are refused under any
   published path (exit 2, named).
3. The report door, run on synthetic arms, writes exactly
   `reports/format-hardening/{report.md,report.json,cost.json}` into a test directory; the
   render carries both contracts (retry trio only on the hardened arm), both token spends,
   the non-comparability sentence, and the breakdown pointer; a planted count collision with
   `reports/baseline/` fails the disjointness test; a journal whose control did not prove
   the harness is refused, with the reason named.
4. `reports/format-hardening/` in the tree: still exactly the three committed files with the
   declaration render (the arm has not run — nothing published claims a figure the arm
   didn't produce).
5. `docs/planning/p2-format-hardening/measured-arm/finding.md` exists, states the hold
   decision, and contains no figure about a model.
6. `CLAUDE.md` aspect-4 paragraph rewritten, line 261's stale claim corrected;
   `CHANGELOG.md` carries the unit's entries; `tests/test_docs.py` green.
7. `uv run pytest` (full suite), `ruff check .`, `mypy src/`, `whetstone --help` all green;
   diff-stat pins assert `verify/`, `patch.py`, `attribution.py` unchanged.
8. When the operator's arm has run (journal + transcript present under the runbook's names),
   the report door renders the real report with the real after-arm — the runbook's post-run
   checklist becomes one command sequence, and this PRD's criteria 3-4 are re-run on the real
   artifacts.

## 6. Risks

| # | Risk | Mitigation |
|---|---|---|
| R-a | The comparison disagrees with the pre-analysis on the same bytes (the autopsy's own lesson, `finding.md:53-77`) | D4: `trigger_of_cause` imported by identity; agreement asserted per record; a contradiction is a named violation with nonzero exit, never smoothed |
| R-b | Journals' rollout denominators differ from autopsy record counts, and a reader fuses them into one number | D6: side-by-side reporting with the shape named in the document; the markdown states both denominators per arm |
| R-c | The arm has not run, and the unit has no real "after" to compare | Pre-committed: the stored-arms comparison is the tooling's real-data verification; the finding states the hold; nothing claims an after figure (criteria 4-5) |
| R-d | The report door labels an arm's counts under the wrong contract | `GenerationContract.parse` backfill defaults; synthetic-arm tests pin the retry trio to the hardened arm only (the `test_report.py:1177` precedent) |
| R-e | A figure lands in a published home it doesn't own | One-home guards are names-only and stay green; the door writes only through `write_comparison`; the ceiling is pointed at, never committed (criterion 4) |
| R-f | The comparison tooling touches the reward path or an inference import | Frozen paths stay byte-identical (R6); the module's own no-inference AST walk with anti-vacuity (R1) |

## 7. Out of scope

- **All of P2 proper** — no rollout loop, no rejection sampling, no LoRA, no training.
- **Any change to `src/whetstone/verify/`, `patch.py`, or `attribution.py`** — frozen.
- **Any autopsy taxonomy change** — an `unrecognised-shape` in the new arm's autopsy is a
  named divergence finding, not this unit's repair.
- **Closing `PREREGISTRATION.md` § 7.3**, the held-out split, or the gate's retry count `R`.
- **The operator's GPU arm itself** — it is commanded from the runbook, never from this unit.
- **Any new task family, any prompt-side hardening, any report change that adds a file to
  `reports/`** — the six-file list is pinned.

## 8. Open questions

- **CHANGELOG placement.** v0.3.0 is already tagged; the plan's instruction ("CHANGELOG final
  updates in the same commit") predates the tag. Extend the `[0.3.0]` section in place (the
  entries exist in code in the same commit, satisfying the "nothing listed until it exists"
  contract) or open an `[Unreleased]` section? **Gate's call** — recommended: extend `[0.3.0]`
  in place, matching the plan's wording and the repo's single-version flow.
- **CLI shape of the report door** (`comparison.py --render-report` vs a sibling module):
  planning detail, resolved in tech-plan.
- **The after-arm's contract sidecar source** when the run lands: the run writes a
  baseline-shaped report into its `--out`; reading its `generation_contract` block is the
  plan, confirmed in tech-plan against `run.py:665`'s actual output.

## 9. Self-critique

| Dimension | Rating | Note |
|---|---|---|
| Problem Definition | 🟢 | The gap is structural and named by the slice's own docs: tooling the runbook references does not exist, the writer has no caller, the finding is absent |
| Success Metrics | 🟢 | Every criterion is a command or an artifact; no invented number — the real before/after is explicitly held until the arm runs |
| User Understanding | 🟢 | Operator persona (the GPU pass is theirs; the analysis is agent-verifiable, D-arm3) |
| Scope Clarity | 🟢 | In/out explicit; P2 proper and the frozen trio refused by name; the six-file list is pinned |
| Edge Cases & Risks | 🟢 | Six risks; R-a (mapping disagreement) and R-b (denominator fusion) are the named hard parts, each with a fixture-first mitigation |
| Stakeholder Alignment | 🟢 | Solo project; the review gate is the approval |
| Feasibility Signal | 🟢 | All machinery reused by identity is shipped and tested; the unit is two deterministic modules plus docs |
| Reward Integrity & Never-Regress | 🟢 | Reward path frozen and pinned; the one-home discipline is the whole design; nothing leaves the box |

**The top gaps, stated as findings:**

🟡 **The unit's real-data deliverable is conditional on the operator.** If the arm has not run
by the end of this unit, the published report never moves past the declaration and the
finding records a hold. That is the pre-committed outcome (R-c), but it means the slice's
headline — the measured before/after — may land in a later session; the unit's acceptance
criteria are written so the unit is complete either way.

🟡 **Denominator discipline is the sharpest edge.** Journals count rollouts; autopsies count
classified completions; the new arm's scored set excludes the dev subset. Three numbers that
look like one denominator. D6 names the shapes; the tech-plan must pin the disclosure text
with a fixture before the code.

**The question to answer before greenlighting:** *the report door renders only through
`write_comparison` into `reports/format-hardening/` — is rendering the declaration (arms
empty) on every run an acceptable no-op, or must the door refuse to run at all until an arm's
journal exists?* The PRD's answer is pre-committed: the door builds and tests on synthetic
arms; it refuses a half-truth render; the declaration stays as committed until the arm runs —
the gate confirms this now rather than after.
