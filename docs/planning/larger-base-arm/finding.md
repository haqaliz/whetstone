# Finding — the larger-base arm

**Written:** 2026-08-18, after the arm ran and the post-run chain completed. PRD:
`prd.md` (the decision rule, pre-committed before any rollout). The run's own report lives
at the gitignored `runs/larger-base-arm/`; the published home is `reports/larger-base/`
(rendered by the report door); the classifier breakdowns live at the gitignored
`runs/larger-base-preanalysis/comparison.md`. **No figure about a model appears in this
document** — those live in the home above, which this document points at and never
restates (`finding`-discipline: `probe-run/finding.md:7-8`).

## What was measured

The arm scored `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` — the candidate the
runbook's resolution block named before anything ran — on the declared source-B set under
the hardened contract § 10.4 discloses (retries on, retrieval oracle, the five declared dev
ids excluded), with source A scored in full alongside; both sources published together.

The operator-executed sequence ran as the runbook wrote it:

1. **The weights fetch** (human-run, the one declared network exception): the 32B snapshot
   was downloaded by hand to the primary's `weights/`, pinned at
   `d1e3b690c8e225d7795bccddf971ca6be68b2012`, and recorded into `provenance.json` by
   hashing every file — the harness re-hashes all four candidates on every run and refused
   nothing.
2. **The probe pass (D7)** — declared before it ran: N = 3 sampled tasks, headroom 10 GiB
   against the machine's 36 GiB, `--recorded-on 2026-08-18`. The probe completed on all
   three with harness PASS, and its published peak — corroborated by a direct load test
   (~8 GiB resident peak for an 18.4 GB model: MLX memory-maps the safetensors and the
   kernel evicts clean file-backed pages) — left the stated headroom, so **the arm
   proceeded**. The ROADMAP § 10 capacity question is settled for this base by
   measurement: it fits, at roughly 6 tokens/second.
3. **The arm ran to completion**: every task scored under the frozen contract, the control
   discipline held (`INTACT` on every probe, `BROKEN` zero, `SKIPPED` zero — the run's own
   report records it), and the transcript recorded every attempt.
4. **The post-run chain ran clean**: attribution → autopsy → the mandatory pre-analysis
   extension over all five autopsy documents → comparison — zero mapping violations, zero
   `unrecognised-shape`, the trigger mapping re-derived by identity over every record, the
   D6 denominators disclosed side by side (rollout records vs classified completions) — →
   the larger-base report door rendered `reports/larger-base/`.

**The measurement:** under the hardened contract on the declared source-B set, the 32B
produced the first nonzero strict-PASS yield the harness has ever measured. Source A
remains a single instance and is reported per-instance, never as a measurement.

## The fork decision

Yield > 0, with control intact → **the P2 premise is supported at a larger base**: training
data exists, and the next unit is P2's first slice (rollouts + expert iteration on the
declared set), per the decision rule pre-committed before any rollout (`prd.md:38-53`).
The finding names the 32B as the first candidate with evidence — **base selection is not
made here**: § 7.3 closes only by a Type 1 amendment committed before the measurement it
governs runs (§ 8.1), which is P3's baseline, and this arm's evidence is what that
amendment rests on.

## M13 — the read, in words

The probe's finding read the 14B/3B zero as **premise failure, not axis failure** — the
wall had moved to "git read it, applied it, and the tests still fail". This arm is the
premise question at the next rung, and the answer is the first positive evidence the fork
has produced:

- The formatting wall receded further: the majority of the arm's classified completions
  were well-formed, and the run's own patch-apply rows are the large majority of the
  scored set — the 32B writes diffs git accepts.
- The wall did not move back to reasoning: **one rollout solved a task** — the STRICT
  verifier reached PASS on the declared set through the same harness, same contract, same
  environment pins. The harness's control discipline (INTACT on every probe) is what makes
  that PASS a measurement rather than a claim.
- The per-candidate residuals of the smaller bases are not this candidate's walls: the 14B's
  `hunk-count-mismatch` persistence and the 3B's small `hunk-dies-early`/`no-diff`
  remainders (recorded in `probe-run/finding.md:48-53`) are carried by the smaller
  candidates, not here.

## Disclosed, not buried

- **The unverified count is material** (the report's own row): the 32B's ~6 tokens/second
  against the 900 s verification timeout left a minority of tasks without a verdict. They
  lower coverage and stay in the denominator — `UNVERIFIED` is neither a win nor a loss.
  This is a timing property of this matrix, not a harness defect: the control arm proved
  the harness on every probe, and the P3 gate's deterministic-retry discipline is the
  named response to a nonzero unverified rate (`docs/ROADMAP.md:423-435`).
- **One runbook defect was found in the field and closed test-first.** The post-run chain
  wrote the arm's autopsy to a stem that did not match the journal's run name, and the
  comparison refused the mismatch by name — the instrument's own guard. The runbook was
  corrected (autopsy `--out` aligned to the journal's run name) and the guard extended
  with a pin that asserts the alignment, watched failing first
  (`tests/test_larger_base_runbook_guards.py`); commits `0e625c1`, `5ee36ba`.
- **The probe's declared values** (N = 3, headroom 10 GiB) were declared before the probe
  ran, per the runbook's rule, never after seeing its output.

## Provenance

Recorded on 2026-08-18 (declared, never read from a clock). Evidence: the run's own
report (`runs/larger-base-arm/`), the journal and transcript
(`runs/larger-base-arm-evidence/`), the probe record (`runs/larger-base-probe/probe.json`),
the attribution and autopsy (`runs/diff-autopsy/larger-base-arm-evidence.json`), the
extended pre-analysis and comparison (`runs/larger-base-preanalysis/`), and the published
home (`reports/larger-base/`), all gitignored under the primary checkout except the
published home. The weights are pinned by hash in `weights/provenance.json`.