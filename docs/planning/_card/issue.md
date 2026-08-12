# Card — measured-arm-run

**Type:** feat · **Branch:** `feat/measured-arm-run/aliz` · **Owner:** aliz
**Source:** inline brief (handed off by `whetstone-next`, 2026-08-12; no GitHub issue exists for this work)

## Brief

Execute the measured format-hardening arm and complete the unspent before/after.
First: refresh the stale worktree paths in `docs/planning/p2-format-hardening/measured-arm/runbook.md`
(it names `feat-p2-format-hardening` and `feat-format-hardening-measurement`, which no longer
exist) and re-verify every flag against `run.py`'s parser. Then the operator runs the arm's
command from the runbook — `--retries`, the two donor roots, the five declared dev-subset ids,
journal+transcript in the sibling evidence directory — accepting its halt conditions (uniform
provisioning failure = harness defect; unstubbed retry prompt = void run; never reuse a
workspace). Then run the post-run chain from the primary checkout: attribution, autopsy,
comparison, and `--render-report` into `reports/format-hardening/`, and write the after-finding
stating per-candidate before/after walls and the P2 fork decision. Acceptance: the evidence
directory exists with journal+transcript, autopsy shows zero `unrecognised-shape` or a named
divergence, comparison exits with zero mapping violations, the two-contract report renders with
both arms' verdict counts and the non-comparability sentence, and the finding is written in the
same commit that lands any runbook or taxonomy correction it surfaces. A flat before/after is a
valid, pre-committed, publishable outcome — never a reason to weaken the verifier or the retry
trigger mapping.

## Grounding files (primary source of truth)

- `docs/planning/p2-format-hardening/measured-arm/runbook.md` — the command, halt conditions,
  expected artifacts, post-run chain, verify steps
- `docs/planning/p2-format-hardening/measured-arm/finding.md` — the hold decision (§ 3) and
  where evidence lives (§ 5)
- `docs/planning/p2-format-hardening/measured-arm/spec.md` (D-arm1..D-arm4) and
  `plan_20260809.md`
- `docs/planning/format-hardening-measurement/prd.md` (R-c: pre-committed flat outcome)
- `docs/ROADMAP.md` § 4 P2 (the fork the arm's measurement decides)
- `CHANGELOG.md` 0.3.0 / 0.4.0 (what shipped: preanalysis, retries, comparison, report door)
