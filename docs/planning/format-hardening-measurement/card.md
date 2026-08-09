# Brief — format-hardening-measurement

**Source:** inline brief (handoff from `whetstone-next`, 2026-08-09). No GitHub issue exists
for this slug; the id lives in the branch and PR.

Complete the unspent code of the `p2-format-hardening` measured-arm aspect (plan
`docs/planning/p2-format-hardening/measured-arm/plan_20260809.md` Phases 3–4; PRD R5–R6).
Phase 1's pre-analysis already measured the retry-eligible ceiling (118 retry-eligible, 5
inferred-truncation, 113 ceiling — gitignored `runs/format-hardening-preanalysis/ceiling.json`)
and the runbook is written; the operator's GPU arm may or may not have run — build for both.

**Deliverables:**

1. A deterministic, stdlib-only comparison module (extend `preanalysis.py` or a sibling, TDD
   with synthetic autopsy documents first, own no-inference AST walk) that assembles the
   before/after cause breakdown from autopsy documents and writes only under gitignored roots.
2. Render `reports/format-hardening/{report.md,report.json,cost.json}` via aspect 3's writer
   with both arms, both contracts, per-arm token spend, the 113 ceiling, the non-comparability
   sentence, and a pointer to the gitignored breakdowns — never restating a classifier count.
3. `docs/planning/p2-format-hardening/measured-arm/finding.md` stating the before/after, the
   halt/hold decision, and what is not claimed (no raised count predicted, no § 7.3 close, no
   base selected).
4. CLAUDE.md status + CHANGELOG updates in the same commit.

**Acceptance criteria, written first:**

- The comparison module is deterministic over synthetic documents with the fine→coarse mapping
  asserted (a contradiction is reported, never reconciled) and refuses published paths.
- The report states the flat-before/after as a valid outcome if that is what the data shows.
- No figure about a model appears outside `reports/format-hardening/` and gitignored homes.
- `uv run pytest`, `ruff check .`, `mypy src/`, the one-home guard, and `tests/test_docs.py`
  all green.
- `src/whetstone/verify/`, `patch.py`, and `attribution.py` stay byte-identical to
  `origin/master`.

**Caveat to plan around:** if the arm has not run when work starts, the tooling is verified on
synthetic fixtures and the real breakdown lands the moment the operator's run produces
`runs/format-hardening-arm-evidence/transcript.jsonl`.
