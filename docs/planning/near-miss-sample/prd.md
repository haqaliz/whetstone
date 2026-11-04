# PRD — near-miss-sample

**Unit:** `feat/near-miss-sample/aliz`. **Source:** inline brief, `docs/planning/_card/issue.md`.
**Understanding:** `docs/planning/near-miss-sample/understanding.md`. **Status:** measurement pin
and sheet alignment; no number is measured.

## Problem statement

The § 10.25 probe returned NO-GO with **one** near-miss in 208 evaluable draws. The sample was
too thin to test the failure-class repair: 207 of 208 evaluable draws never produced an
applied-and-failed patch. The 8B night's journals record **51 private `NOT_SOLVED` draws across
20 private tasks**, plus **1** on the public task. The next repair probe must use that population,
and the pre-registration must name it before the run.

The finding's earlier phrase "51 `NOT_SOLVED` across 51 tasks" is wrong: it is 51 private draws
across 20 tasks plus 1 public. The amendment records the correction.

## Goals & success metrics

- § 10.27 names the 20 private ids and `pallets__flask-4045`, pins 21 tasks × `K = 16` = **336
  draws**, and states the GO (at least one strict-`PASS`), the outcome-selected disclosure and the
  non-comparability.
- The Torch/MPS sheet's probe pass runs the § 10.27 sample: a symlink root of the 20 manifests,
  `--probe 20`, and `check-probe --probe 20`; the night block is unchanged.
- The docs and sheet guards pin the 20 ids against the committed corpus and the held-out document.
- No runtime, reward, gate, corpus, held-out, `K` or `R` change; no GPU run.

## Requirements

### Must-have

1. **§ 10.27.** Append a Type 1 amendment naming the 20 private ids and the public task, the
   336-draw sample, the 52 near-misses (51 private + 1 public), the outcome-selected rule and the
   correction of the finding's "51 tasks". It introduces no success threshold, does not edit
   § 10.25 or § 10.26, and states no count has been measured.
2. **The sample root.** The sheet's probe pass creates `tasks/local/near-miss` by symlinking the
   20 manifests from `tasks/local/donor-a` / `donor-b` (the user's private corpus; the root is
   gitignored), then runs `--tasks $REPO/tasks/local/near-miss --probe 20`. The public task comes
   from `--public`; the five dev ids are not in the root, so the probe omits `--dev-subset`.
3. **The door.** `check-probe --probe 20` pins the ledger's sample size; the sheet passes it. The
   harness rule and § 10.27's GO are stated separately, as § 10.25/§ 10.26 did: `check-probe` exit
   0 is not the GO; a zero yield is a NO-GO.
4. **The night block is unchanged.** The full 51+1 corpus, the five dev ids and the remine stay.
   The probe is the measurement; the night follows a GO.
5. **The disclosures.** The 20 near-miss tasks are all oracle-fittable; the 12 `NO_ORACLE` tasks
   are outside the sample; the public task's near-miss is included. The sample is
   outcome-selected; a GO is not a corpus claim.
6. **Guards.** `tests/test_docs.py` derives the 20 ids from § 10.27 and cross-pins them to
   `tasks/local-ledger.json` (all present) and `tasks/heldout/source-b.json` (none held out);
   `tests/test_torch_mps_runbook_guards.py` pins the symlink root, the 20 ids, `--probe 20`, the
   336/21-task statement, § 10.27, the two decisions and the no-`NO_ORACLE` disclosure.
7. **The finding correction.** A dated correction in
   `docs/planning/torch-mps-series/finding.md` records the 51-private/20-task/1-public count and
   points at § 10.27. A dated note in `docs/ROADMAP.md` § 14 M1 records that the near-miss sample
   is named.
8. **Write-up.** `CHANGELOG.md` Unreleased, `docs/STATUS.md`, `CLAUDE.md`. No probe run.

### Should-have

- The sheet's `--tasks` root sentence states that the near-miss root is a selection, not a second
  corpus, and that the night still draws the full corpus.
- A guard that the 20 ids include the five repair-night tasks (the subset that fired the
  verdict-only repair), so the sample is demonstrably near-miss-rich.

### Nice-to-have

- A `check-probe --stratum`/`--sample-ids` pin. Declined: the sample identity is the committed
  § 10.27 ids and the symlink root; the command pins the size, as it did for § 10.26.

## Technical considerations

- **The 8B night has no ledger.** The provenance is the per-draw journals under the gitignored
  `runs/`; the amendment cites the run and the counts; the docs test pins the ids against the
  committed corpus, not the journals.
- **The symlink root is a local input.** `tasks/local/` is gitignored; the sheet's pre-step
  creates it. A missing manifest fails the loader by name; the sheet does not copy or modify the
  user's private data.
- **`--probe 20` is the private count.** The public task is separate; the ledger's
  `task_set.probe=20`, `private=20`, `public=1`; the draws are 21 × 16 = 336.
- **No runtime change.** The repair-evidence unit already records repairs; this unit only names
  the sample and aligns the sheet.

## Risks & open questions

- **Outcome-selected sample.** The 20 tasks were chosen because they produced a `NOT_SOLVED` in
  the 8B night. That is the repair's target population, but a GO is not a corpus claim. The
  amendment must say so; the finding and write-up repeat it.
- **The sample's near-miss rate may not transfer.** The 8B night was one seed; a new seed may
  produce fewer near-misses on the same tasks. The 20-task sample is the full 8B near-miss
  population, not the 5-task repair-night subset; it is the broader, more robust choice. The
  336-draw probe is still a probe, not a night.
- **The finding's count correction.** The "51 across 51 tasks" phrase must be corrected rather
  than silently reused; the amendment and finding carry the dated correction.
- **The symlink root is operator-created.** A missing or wrong symlink is a provisioning failure,
  not a model result; the sheet's guard and the loader fail by name.

## Out of scope

Running the § 10.27 probe; changing the base, runtime, precision, `K`, `R`, the held-out
document, the verifier, the gate or the corpus; a second task family; the MPS hang; a
`check-probe` id pin.

## Aspect decomposition

One aspect: **`near-miss-sheet`** — the amendment, the sheet, the guards and the write-up. The
unit is docs/guards; a second aspect would be overhead.

---

## Self-critique (prd-generator workflow)

**🟡 The sample is selected by an observed outcome.** This is the first sample in the series chosen
from a previous run's results. It is honest only because the amendment says so and the GO is
scoped to the sample; the write-up must not let a GO read as a corpus result.

**🟡 The 20-task sample is still a probe, not the night.** If it returns GO, the next step is the
full 51+1 night; if NO-GO, the 20-task sample is the finding, and the base/approach change is the
next lever. The unit must not pre-empt that.

**🟢 Guardrails.** No reward, gate, corpus, held-out, `K`, `R`, GPU or egress. The private
manifests stay local; the symlink root is gitignored.

**The question I would want answered before greenlighting this:** if the 20-task probe returns
GO, is the full night the same 20 tasks (a night on the near-miss population) or the 51+1 corpus
(the series' night)? This PRD keeps the night block as the full corpus; the probe is the gate,
not the series.
