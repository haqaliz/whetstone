# feat p2-easier-stratum — Easier task stratum + yield re-probe

**Type:** feat · **Branch:** `feat/p2-easier-stratum/aliz` · **Owner:** aliz
**Source:** inline brief (handed off by `whetstone-next`, 2026-08-14; no GitHub issue exists for this work)

> **Artifacts live here rather than in `docs/planning/_card/`** following the precedent set by
> `docs/planning/p2-diff-autopsy/card.md:14-21`: the `_card` path is the measured-arm-run unit's
> live-cited home (`docs/planning/measured-arm-run/prd.md:4`) and is not a safe place for this
> unit's documents.

## Brief

Execute the roadmap's named fork, first arm: an easier task stratum. The measured-arm finding pre-commits that format hardening is exhausted and the next unit is an easier task stratum or a larger base — never a fourth generation-contract change — with the roadmap's P2 pivot signal naming difficulty stratification first (docs/ROADMAP.md:387-389, :405; docs/planning/p2-format-hardening/measured-arm/finding.md § 5). Define a difficulty axis a priori in code before any rollout — never as "tasks the bases failed" (PREREGISTRATION.md:171-177; src/whetstone/bakeoff/selection.py) — select or re-mint an easier source-B stratum from the 66 proven-live tasks, and re-run the existing bake-off harness on it to re-test the P2 premise: strict-PASS yield > 0, i.e. training data exists. Acceptance criteria, written test-first before the run: a pre-committed stratum document whose membership is provably computable from the manifest alone, the probe run with control INTACT on every task, a report under reports/ naming per-candidate yields on the stratum as their only home, and a finding in the same commit recording the premise as supported or refuted with the larger-base arm as the named next response if it is not. The verifier, patch.py, and attribution.py stay byte-identical — the AC2 pins hold.

## Grounding files (primary source of truth)

- `docs/ROADMAP.md` § 4 P2 (pivot signal: stratify by difficulty; the fork at :387-389)
- `docs/planning/p2-format-hardening/measured-arm/finding.md` § 5 (fork decision, pre-committed rule M7)
- `docs/planning/measured-arm-run/prd.md` (M7 — the fork's pre-committed rule)
- `PREREGISTRATION.md` § 7.1 (held-out split open), § 7.3 (base open), :171-177 (no post-hoc rules)
- `src/whetstone/bakeoff/selection.py` (selection rule: ranking, never post-hoc)
- `CHANGELOG.md` 0.3.0 / 0.4.0 / 0.5.0 (what shipped: harness, autopsy, hardening, measured arm)
