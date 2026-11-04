# Understanding — near-miss-sample

**Unit:** `feat/near-miss-sample/aliz` · **Written:** 2026-11-05 · **Source:**
`docs/planning/_card/issue.md`, after the § 10.25 probe and the repair-evidence unit.

## What the work is really asking

The § 10.25 probe's 16-task sample produced **one** near-miss in 208 evaluable draws; the repair
was barely exercised. The 8B night's journals (`runs/torch-mps/torch-8b-night-001/draws/`) record
**51 private `NOT_SOLVED` draws across 20 private tasks**, plus **1** on the public task —
**52** in total. The next repair probe must use that near-miss population, not another positional
16-task sample. A § 10.27 Type 1 amendment names the 20 private ids + `pallets__flask-4045` and
pins 21 tasks × `K = 16` = **336 draws**, GO unchanged (at least one strict-`PASS`). The Torch/MPS
sheet's probe pass becomes that measurement; the night block stays the full 51+1 corpus.

The sample is **outcome-selected** from an already-run night. The amendment must say so: a GO is
evidence on these 21 tasks, not the corpus, and the earlier finding's "51 `NOT_SOLVED` across 51
tasks" is corrected to 51 private draws across 20 tasks plus 1 public.

## The sample, derived from the journals

`torch-8b-night-001` has no ledger; its per-draw journals are the provenance. Counting
`rollout.outcome == "NOT_SOLVED"` per `task_id` over `draws/draw-*.journal.jsonl`:

| task | NOT_SOLVED |
|---|---|
| `donor-a-2f4e497580ff` | 11 |
| `donor-a-34daf85182d5` | 6 |
| `donor-a-4731e32044c5` | 4 |
| `donor-a-12a1d8e4d766` | 4 |
| `donor-a-5e25b106874c` | 4 |
| `donor-a-f100a90e47f2` | 3 |
| `donor-a-955d9a079c16` | 3 |
| `donor-a-a93fe36d6e85` | 2 |
| `donor-a-d601ff2d0ec0` | 2 |
| `donor-a-99c0e0464c21` | 2 |
| `donor-a-37a91266029a` | 1 |
| `donor-a-df207b27e82c` | 1 |
| `donor-a-c32d7c672465` | 1 |
| `donor-a-6d35bb3a4d17` | 1 |
| `donor-a-3326ca8a116d` | 1 |
| `donor-b-c3e132b7469b` | 1 |
| `donor-b-0fe4582aeac1` | 1 |
| `donor-b-c57246c7841a` | 1 |
| `donor-b-cc7d3f520f1c` | 1 |
| `donor-b-ce6425d3101a` | 1 |
| `pallets__flask-4045` | 1 (public) |

The 20 private tasks + the public task = 21 tasks. The 5 repair-night near-miss tasks
(`donor-a-34daf85182d5`, `donor-b-ce6425d3101a`, `donor-a-2f4e497580ff`, `donor-a-4731e32044c5`,
`donor-a-12a1d8e4d766`) are a subset; the sample is the full 8B near-miss population, not the
repair-night subset. None of the 20 is in `tasks/heldout/source-b.json`'s membership; all are in
`tasks/local-ledger.json`.

## Current sheet and mechanism

- The Torch/MPS sheet's probe pass is § 10.26's 16-task, 272-draw sample: `--probe 16` against
  `tasks/local/donor-b` + `donor-a`, the five `--dev-subset` ids, and `check-probe --probe 16`
  (`docs/planning/torch-mps-series/night-door/runbook.md`).
- `whetstone run --night --probe N` narrows `private_tasks[:N]` after the dev overlay and
  held-out exclusion; it cannot select arbitrary ids. A **training-only root** of symlinks to the
  20 manifests is the existing mechanism: `--tasks $REPO/tasks/local/near-miss --probe 20` takes
  all 20; the public task comes from `--public`; the five dev ids are not in the root, so the
  probe omits `--dev-subset`.
- `check-probe --probe N` (0.32.0) pins the ledger's `task_set.probe`; the new probe passes
  `--probe 20`. The sample's identity is the 20 symlinks + § 10.27; the command pins the size.
- The night block is the full corpus (donor-b + donor-a, five dev ids, remine) and is unchanged.

## Core-loop placement

**② the nightly improvement loop's evidence**, and the measurement that decides whether the
failure-class repair can convert a near-miss. The reward (①), the gate (③) and the report (④) are
untouched: no runtime, gate, corpus, held-out, `K` or `R` change.

## Contradictions surfaced

- **The finding says "51 `NOT_SOLVED` across 51 tasks"; the journals say 51 private across 20
  tasks plus 1 public.** The amendment corrects it and cites the run; the finding gets a dated
  correction.
- **Outcome-selected sample.** The 20 were chosen because they produced a near-miss. That is the
  population the repair targets, but a GO is not a corpus claim. The amendment must say so; the
  write-up must repeat it.
- **The sheet's `--dev-subset` applies to both doors today.** The probe's near-miss root excludes
  the five dev ids by selection, so the probe omits the flag; the night keeps it. The guard's
  dev-id test must apply to the night block only.
- **The sheet's no-`NO_ORACLE` disclosure is § 10.26's.** The 20 near-miss tasks are all
  oracle-fittable (they produced `NOT_SOLVED`); the 12 `NO_ORACLE` tasks are outside the sample.
  The sheet's disclosure changes.
- **The 8B night has no ledger.** The sample's provenance is the journals, not a sealed run
  document; the amendment cites the run and the counts, and the docs test pins the 20 ids against
  the committed corpus.

## Affected areas

`PREREGISTRATION.md` (§ 10.27 + log row), `tests/test_docs.py`, the Torch/MPS runbook,
`tests/test_torch_mps_runbook_guards.py`, `docs/planning/torch-mps-series/finding.md` (dated
correction), `docs/ROADMAP.md` (§ 14 M1 note), `CHANGELOG.md`, `docs/STATUS.md`, `CLAUDE.md`.
No `src/` change; no GPU run.
