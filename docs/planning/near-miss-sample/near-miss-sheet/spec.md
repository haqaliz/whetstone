# Spec — near-miss-sheet (near-miss-sample)

**PRD:** `../prd.md`. **Branch:** `feat/near-miss-sample/aliz`. **Date:** 2026-11-05.

## Problem slice

§ 10.25's 16-task probe had one near-miss. The 8B night's journals record 51 private `NOT_SOLVED`
across 20 private tasks plus 1 public. Name that population in § 10.27 and make the Torch/MPS
probe pass measure it: 20 private + 1 public = 21 tasks × 16 = 336 draws.

## In-scope

1. **§ 10.27** (draft below) + the log row in `PREREGISTRATION.md`.
2. **`tests/test_docs.py`**: `test_the_near_miss_sample_amendment_names_the_sample` — the heading,
   Type 1, the append-only line, the 20 ids (hardcoded set) extracted from the sample block, the
   public task, 336/21 tasks/20 private/1 public/52/51 private, the outcome-selected disclosure,
   "No count has been measured", "§ 3 baseline remains unspent", the log row; cross-pin the 20 to
   `tasks/local-ledger.json` (all present) and `tasks/heldout/source-b.json` (none held out).
3. **The sheet** (`docs/planning/torch-mps-series/night-door/runbook.md`):
   - a pre-step block creating `$REPO/tasks/local/near-miss` by symlinking the 20 manifests
     (donor-a/donor-b split);
   - the probe block: `--probe 20`, `--tasks $REPO/tasks/local/near-miss`, no `--dev-subset`,
     every other flag unchanged;
   - the check-probe block: `--probe 20`;
   - the probe prose: 20 private + 1 public = 21 tasks × 16 = 336 draws; § 10.27's 20 ids; the
     8B night's 51 private `NOT_SOLVED` across 20 tasks + 1 public; the sample is
     outcome-selected; the 20 are oracle-fittable, the 12 `NO_ORACLE` tasks are outside; the
     harness rule vs § 10.27 GO (at least one of the 336); `check-probe` exit 0 is not the GO;
   - the night block unchanged (full corpus, five dev ids, remine).
4. **`tests/test_torch_mps_runbook_guards.py`**: update the probe test to § 10.27 (20 ids, root,
   `--probe 20`, 336/21, no `--dev-subset` on the probe); the prep block's symlink ids = the 20;
   the dev-id test applies to the night only; rewrite the no-`NO_ORACLE` disclosure; keep the
   two decisions, the 52-task night denominator, the supervisor and the offline mirror.
5. **The finding correction** (`docs/planning/torch-mps-series/finding.md`): a dated blockquote
   correcting "51 `NOT_SOLVED` across 51 tasks" to 51 private across 20 tasks + 1 public (52),
   naming § 10.27.
6. **The roadmap note** (`docs/ROADMAP.md` § 14 M1): a dated correction naming § 10.27 and scoping
   a GO to the sample, not the corpus.
7. **Write-up:** `CHANGELOG.md` Unreleased, `docs/STATUS.md`, `CLAUDE.md`.

## Out-of-scope

Running the probe; the base/runtime/precision; `K`, `R`, the held-out document, the verifier, the
gate, the corpus; a `check-probe` id pin; the MPS hang.

## Acceptance (test-first)

- The docs test fails before § 10.27 exists and passes after; the extracted 20-id set equals the
  expected set exactly; every id is in the committed ledger and none is held out.
- The sheet guard fails on the old `--probe 16`/donor roots and passes on the near-miss root/
  `--probe 20`; the prep block's 20 symlinks are the § 10.27 ids; the night still passes the five
  dev ids and no `--probe`.
- `uv run pytest tests/test_docs.py tests/test_torch_mps_runbook_guards.py -q`, `ruff`, `mypy`
  green; no GPU.

## Draft § 10.27

```markdown
### 10.27 The § 10.25 probe's near-miss sample is named — 2026-11-05

**Type 1 (§ 8.1): pins the inputs of a measurement, committed before the probe it governs runs.**
It introduces no success threshold, rewords nothing in § 1, § 4 or § 6, and **does not edit
§ 10.25 or § 10.26**: this document is append-only. What changes is the sample: the § 10.25
16-task sample produced one near-miss in 208 evaluable draws, so the repair was barely exercised.
This probe draws the 8B night's near-miss population instead.

**The correction.** The finding's phrase "51 `NOT_SOLVED` across 51 tasks" counted draws, not
tasks. The journals of `torch-8b-night-001` record **51 private `NOT_SOLVED` draws across 20
private tasks**, plus **1** on the public task (`pallets__flask-4045`) — **52** draws in total.
The 8B night has no ledger; its per-draw journals are the provenance.

**The sample.** The 20 private tasks with at least one `NOT_SOLVED` in `torch-8b-night-001`, plus
the public task:

- `donor-a-2f4e497580ff`, `donor-a-34daf85182d5`, `donor-a-4731e32044c5`,
  `donor-a-12a1d8e4d766`, `donor-a-5e25b106874c`, `donor-a-f100a90e47f2`,
  `donor-a-955d9a079c16`, `donor-a-a93fe36d6e85`, `donor-a-d601ff2d0ec0`,
  `donor-a-99c0e0464c21`, `donor-a-37a91266029a`, `donor-a-df207b27e82c`,
  `donor-a-c32d7c672465`, `donor-a-6d35bb3a4d17`, `donor-a-3326ca8a116d`,
  `donor-b-c3e132b7469b`, `donor-b-0fe4582aeac1`, `donor-b-c57246c7841a`,
  `donor-b-cc7d3f520f1c`, `donor-b-ce6425d3101a`,

plus `pallets__flask-4045`. That is 21 tasks at `K = 16` — **336 draws**. The five repair-night
near-miss tasks (`donor-a-34daf85182d5`, `donor-b-ce6425d3101a`, `donor-a-2f4e497580ff`,
`donor-a-4731e32044c5`, `donor-a-12a1d8e4d766`) are a subset; the sample is the full 8B
near-miss population. None of the 20 is in the § 10.16 held-out membership.

**The sample is outcome-selected, and that is stated.** The 20 tasks were chosen because they
produced a `NOT_SOLVED` in an already-run night. That is the population the repair targets, not a
random sample and not the corpus. A GO is evidence on these 21 tasks only; it is not a corpus
claim, and it is not a headline. The GO rule is unchanged: **GO iff at least one of the 336 draws
is strict-`PASS`**. The 20 tasks are all oracle-fittable; the 12 `NO_ORACLE` tasks are outside
the sample.

**What does not change.** The base and revision, the runtime and precision, `K = 16` (§ 10.19),
`R = 3` (§ 10.8), `R_repair = 2` (§ 10.23), the failure-class repair vocabulary (§ 10.25), the
score-both-ways verifier, the gate rule and its exits, and the held-out document and its digest.

**Comparability.** Every figure measured under § 10.25, § 10.24, § 10.23, § 10.21, § 10.22,
§ 10.20, § 10.10 or an arm is **non-comparable** to any figure measured under this probe: a
different sample (or a different repair vocabulary, or different weights) sits between them.

**No report home.** The gate record stays gitignored under `runs/`; the finding lives under
`docs/planning/torch-mps-series/`; no `reports/` directory is created.

**What is not claimed.** No count has been measured under this probe. The sample may produce
fewer near-misses at the new seed; a zero is a legitimate NO-GO. The § 3 baseline remains unspent,
nothing here claims the probe selects a strict-`PASS`, and a NO-GO returns the lever to a human,
never to a loosened verifier.
```

Log row:

```markdown
| 2026-11-05 | The 8B night's near-miss population is named as the § 10.25 follow-up probe: 20 private tasks + the public task, 336 draws (§ 10.27) | 1 — pins the inputs of a measurement | Yes |
```
