# Card — `p2-format-hardening`

**Type:** feat · **Branch:** `feat/p2-format-hardening/aliz` · **Owner:** aliz
**Started:** 2026-08-09 · **Source:** inline brief (no GitHub issue; the id is a slug)

---

## Why there is no issue body

Whetstone's tracker is GitHub Issues, but this unit of work came out of a `whetstone-next`
ranking run over the repository's own files on 2026-08-09, immediately after the P2 diff
autopsy closed. The id is therefore a descriptive slug rather than a number, and the brief
below is the source of truth for Phases 2–5.

**Artifacts live here rather than in `docs/planning/_card/`** following the precedent set by
`docs/planning/p2-diff-autopsy/card.md:16-21`: three live citations point into
`_card/understanding.md` by section number, so the `_card` path is not a safe place for this
unit's documents. This unit's docs are `docs/planning/p2-format-hardening/*`.

## Brief

Reproduced verbatim from the `whetstone-next` handoff the user acted on by invoking
`wbf feat p2-format-hardening`:

---
Build the format-hardening response the diff autopsy named
(`docs/planning/p2-diff-autopsy/finding.md:43-49`): a generation-contract fix — structured/
fenced diff output, a pre-verifier diff validator, or malformed-output retry
(`docs/planning/p2-diff-autopsy/dig-transcripts.md:318` — decide with evidence, in the dig) —
that converts the "git would not read this diff" bucket into rollouts the STRICT verifier
actually grades. Caveat: the finding predicts nothing; the deliverable is a measured
before/after cause breakdown via `src/whetstone/bakeoff/autopsy.py`, not a raised count.
Acceptance criteria, written first per the repo's test-first contract:

1. A test asserts the converter/validator never silently repairs a held-path edit — a scope
   violation still produces a diff touching that path so STRICT fires `patch-scope` (the R5
   credulity lesson from `docs/planning/p2-yield-probe/prd.md:154-168`).
2. A test asserts `src/whetstone/verify/`, `patch.py`, and `attribution.py` are byte-identical
   to `origin/master`.
3. The run persists raw generations under a gitignored root and its transcript autopsies
   completely with zero `unrecognised-shape`.
4. The new report declares its contract (prompt hash, retrieval, sampler, budget, extractor
   version) and its non-comparability with `reports/baseline/`, with the one-home guard
   amended by argument (`docs/planning/p2-yield-probe/prd.md` D6).
5. `whetstone bakeoff` stays a nonexistent subcommand.
---
