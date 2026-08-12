# Finding — the measured arm's before/after

**Slice:** `p2-format-hardening` measured arm, executed by `measured-arm-run` ·
**Written:** 2026-08-12, after the arm ran and the post-run chain completed.
**Instrument:** attribution → autopsy → comparison → report door, per the runbook's post-run
section · **Local evidence:** `runs/format-hardening-arm/`, `runs/format-hardening-arm-evidence/`,
`runs/diff-autopsy/`, `runs/format-hardening-preanalysis/` (gitignored — the only home of the
numbers).

---

## 1. What this document is

The hold is spent. The previous finding (`finding.md`, 2026-08-10) recorded that the arm had
not run and that everything it needed was built; this finding records that it ran, what the
measurement shows, and the fork decision it converts into — argued strictly within the rule
the PRD pre-committed before the run (`docs/planning/measured-arm-run/prd.md` M7). The
transferable discipline is unchanged: **the read is a measurement, never a hand-read.** The
trigger mapping is re-derived by identity and asserted against the pre-analysis's decisions
over every record — the assertion held clean, and a contradiction would have been reported,
never reconciled.

**This document carries no figure about a model**: verdict counts live in the two reports
(`reports/baseline/`, `reports/format-hardening/` — declared non-comparable by the D6
argument), classifier counts live in the gitignored breakdown home
(`runs/format-hardening-preanalysis/comparison.md`), and a number quoted here would be a
second home for itself.

## 2. The run's story — two launches, one defect, one measurement

The first launch died before it measured anything: every environment build failed with a
`FileNotFoundError` naming a **relative** workspace path, every rollout came back
`UNPROVISIONED`, and the run stopped itself with `HarnessNotProven` — none of its tasks
reached `INTACT`, so a run of zeroes would have been a result about a harness that graded
nothing. The cause is the worktrees skill's documented pitfall: the workspace is built as
`workspace / digest` and provisioned by subprocesses whose CWD is not the run's
(`run.py:546`, `scoring.py:351`), so a relative path does not resolve there. The runbook had
inherited the original plan's relative paths; the dig and the guard test had not caught them.

The correction landed test-first in the unit itself: a guard asserting the arm's writable
paths are absolute (RED on the runbook as it shipped, GREEN after), the four paths made
absolute under the primary's `runs/`, and the runbook's rationale corrected
(`tests/test_runbook_guards.py`, commit `e5fcd06`). The dead evidence is **quarantined, never
deleted**: `runs/format-hardening-arm-evidence-dead-20260812-relative-workspace/` holds the
dead run's journal — the defect's own record.

The restart ran clean to completion: the control discipline held on every task of the sweep
(the journal records `INTACT` probes throughout — their counts live in the run's own report),
and the run's report was written under the hardened contract's fields: the retry budget, the
retry template digest, the diagnosis vocabulary version, retrieval oracle, and the declared
dev subset, with the non-comparability sentence beside the baseline arm's.

## 3. One instrument discovery, corrected in the same commit

The runbook's post-run comparison command could not run as written. The comparison asserts
the trigger mapping against the pre-analysis document's per-run `decisions` rows, and the
stored ceiling document carries decisions only for the two stored runs — a run without
declared decisions is refused by name (exit 2, nothing written), which is the instrument
working as designed: an assertion cannot trust decisions a document does not declare. The
runbook omitted the step that produces them. Corrected: the pre-analysis is re-run over all
three autopsy documents, so the extended document's decisions cover the arm's own records,
and the comparison runs against that document. The extended document's combined ceiling is a
**different measurement over a different record set** than the halt-check ceiling the
runbook's opening block pre-commits (which remains, with its provenance, in the original
ceiling document); the two are never fused — each is labeled for what it is.

## 4. The measured before/after

The walls, in words, per candidate — the counts live in the breakdown home and are not
restated here:

- **One candidate is a loop-collapse wall, and it is unchanged.** Its completions repeat
  their own chat-template tokens; nothing retry-shaped ever fired, because the pre-analysis
  measured its retry-eligible ceiling at zero before any GPU was spent. The dig predicted
  exactly this shape; the measurement confirmed it without a single retry being issued — the
  per-candidate finding stands, and no retry budget could have converted it.
- **The second candidate's hunk-count wall receded.** A share of its retry-eligible parse
  refusals converted into well-formed patches — the retry machinery did what it was built to
  do — leaving a smaller hunk-count remainder and a new no-diff remainder.
- **The third candidate's hunk-dies-early spread narrowed the same way**: fewer early hunks,
  more well-formed completions, and its hunk-count refusal population gone.

**The common fact, which is the measurement's content:** well-formed patches apply but do not
solve. The verdict counts under the hardened contract — their home is the rendered report,
stated under that contract's own fields — show no rollout solved a task on the declared set:
the same zero the baseline arm shows under its own contract. The formatting wall was the
first wall, and the hardening cleared a share of it; the wall behind it is fix quality. That
is the first measurement that reaches this question: the yield probe's premise — that the
measurement had never reached *"can the bases fix these bugs"* — is now tested rather than
inferred, and the answer it reaches is that the bases write acceptable patches and still do
not fix the bugs.

## 5. The fork decision (pre-committed rule M7, applied)

> Per candidate, the retry-eligible parse refusals the arm's transcript converts into
> well-formed or better, against the ceiling the pre-analysis measured, decides the P2 fork.
> A flat arm means the format-hardening response is exhausted, and the next unit is the
> roadmap's own named fork — an easier task stratum or a larger base — never a fourth
> generation-contract change. (`docs/planning/measured-arm-run/prd.md` M7)

- **Conversion happened** — material for the two trigger-eligible candidates, per the
  breakdown home; the loop-collapse candidate was unconvertible by its own zero ceiling, a
  per-candidate finding rather than a tie.
- **The strict-PASS yield across the corpus is zero under the hardened contract** — the P2
  premise, *training data from strict-PASS rollouts*, has no training data
  (`docs/ROADMAP.md` § 4 P2). The pivot signal's condition is measured, not inferred.
- **The decision:** the format-hardening response is exhausted as a yield lever. No fourth
  generation-contract change follows — the rule forbids it by name. The next unit is the
  roadmap's named fork: **an easier task stratum or a larger base**
  (`docs/ROADMAP.md:387-389`), with the P2 pivot signal's own responses — stratify by
  difficulty, raise *k* — as the next unit's options, chosen on this evidence. The evidence
  now points one way the previous finding could not: the wall is no longer formatting, so the
  fork's premise is supported directly rather than by elimination.

## 6. What is not claimed

- That the retries failed — **untrue**: they converted a material share of what they fired
  on; the measurement of that is the breakdown home.
- That a base is selected — **untrue**: solved zero under the hardened contract too, so
  `PREREGISTRATION.md` § 7.3 stays open and no base is chosen.
- That the arm's measurement is a baseline — **untrue**: the pinned baseline stands unmeasured
  on the held-out split, which does not exist until P3; `reports/baseline/` is untouched.
- That a looser verifier follows — **never**: the roadmap forbids it by name, and nothing here
  touches the reward (`src/whetstone/verify/`, `patch.py`, `attribution.py` stay byte-identical
  to `origin/master` — the AC2 pins held through the whole unit).
- That this document carries a figure about a model — **it does not**: the numbers live in the
  two reports and the gitignored breakdown home, and a number quoted here would be a second
  home for itself.
- That `PREREGISTRATION.md` moved — **it did not**: R5 forbids an amendment, and § 10.4
  already disclosed the hardened contract and the two reports' non-comparability.

## 7. Where the evidence lives

- The run's report: `runs/format-hardening-arm/{report.md,report.json,cost.json}` (gitignored).
- The evidence: `runs/format-hardening-arm-evidence/{journal.jsonl,transcript.jsonl,attribution.json}`
  (gitignored); the autopsy document `runs/diff-autopsy/format-hardening-arm-evidence.json`.
- The breakdown home: `runs/format-hardening-preanalysis/comparison.md` (and
  `ceiling-with-arm.json`, the extended decisions document; `ceiling.json`, the halt-check
  document it was measured against) — gitignored, the only home of the numbers.
- The dead run's quarantine: `runs/format-hardening-arm-evidence-dead-20260812-relative-workspace/`.
- The published side: `reports/format-hardening/` — rendered by the report door from the
  journals and contract sidecars by identity, both arms under their own contracts, declared
  non-comparable.
