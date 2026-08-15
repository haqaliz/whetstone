# Finding — the easier-stratum probe

**Written:** 2026-08-15, after the arm ran and the post-run chain completed. Spec:
`spec.md` (A5, A6). The run's own report lives at the gitignored
`runs/easier-stratum/`; the published home is `reports/easier-stratum/`; the classifier
breakdowns live at the gitignored `runs/easier-stratum-preanalysis/comparison.md`.
**No figure about a model appears in this document** — those live in the two homes above,
which this document points at and never restates.

## What was measured

The probe scored the pre-committed stratum (`tasks/stratum/easier.json`, membership 19)
under the hardened contract § 10.4 discloses (retries on, retrieval oracle, dev subset
none declared — see the launch correction below), with the two retained candidates —
`mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` and
`mlx-community/Qwen2.5-Coder-3B-Instruct-4bit` — the third excluded by name under the
pre-committed zero-ceiling rule (`prd.md:93-103`). Source A was scored in full alongside,
both sources publishing together.

The control discipline held on every probe: the harness proved it could grade before any
rollout was paid for, and the post-run chain ran clean — zero mapping violations, zero
unrecognised shapes, the trigger mapping re-derived by identity over every record.

**The measurement:** under the hardened contract on the declared stratum, **no rollout
solved a task** — yield zero for every candidate, with the harness intact.

## The fork decision

Yield == 0 for every candidate, with control intact → **the premise is refuted on the
easier stratum, and the larger-base arm is the named next response** (`prd.md:44-55`;
`docs/ROADMAP.md:387-389`). Not a looser verifier; not a fourth generation-contract change,
ever (`prd.md:49-51`). The next unit is the **larger-base arm**.

## M13 — the axis read, in words

The zero is a **premise failure, not an axis failure** — an observational claim grounded
in the autopsy/attribution read, not a ranking of the two:

- The stratum did what it was selected to do: the formatting wall that dominated the
  stored runs receded. On the probe run the majority of classified completions were
  well-formed for both candidates, against the stored runs where parse refusals
  dominated.
- The wall moved downstream: the well-formed patches **reached the verifier and applied**
  (the run's own patch-apply rows are a large majority of the private set), and **none
  turned the tests green** — `solved` stayed zero while applied patches sat in the
  checkout. The failure shape is no longer "git would not read the diff"; it is "git read
  it, applied it, and the tests still fail".
- Per-candidate residuals, recorded so the larger-base arm's runbook knows what it is up
  against: the 14B candidate's `hunk-count-mismatch` wall persisted even under the retry
  budget (its retry-triggered cause, still present after the budget was spent), and the 3B
  candidate's `hunk-dies-early` and `no-diff` causes remained small. Neither observation
  changes the fork routing: the axis is not the binding constraint, so an even-easier
  stratum is not the response this zero points at.

The denumerators are disclosed side by side (rollout records vs classified completions,
the D6 discipline) in the breakdown home; this document deliberately restates neither.

## The launch correction, recorded (landed test-first)

The sheet first carried the measured arm's five declared dev ids. **None of them is a
member of the committed stratum** — the band excluded them — so the overlay they implied
was vacuous, and the harness refused the vacuous declaration by name at launch
(`UnknownDevSubset`): the five ids matched nothing in the stratum-filtered universe, and
the run died before freeze. The correction: the membership is the exclusion, the arm
declares no dev subset, and the sheet now says so — with the guard extended
(`tests/test_probe_runbook_guards.py`: every declared `--dev-subset` id must be a stratum
member; an empty overlay must be stated, not silent), watched failing first. The refusal
was the harness's own; it cost one launch, not one night.

## Provenance

Recorded on 2026-08-15 (declared, never read from a clock). Evidence: the run's own
report (`runs/easier-stratum/`), the journal and transcript
(`runs/easier-stratum-evidence/`), the attribution and autopsy
(`runs/diff-autopsy/easier-stratum-evidence.json`), the extended pre-analysis
(`runs/easier-stratum-preanalysis/ceiling-with-probe.json`) and the comparison
(`runs/easier-stratum-preanalysis/comparison.json`), all gitignored under the primary
checkout.
