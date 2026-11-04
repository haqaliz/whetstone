# feat near-miss-sample

**Source:** the `whetstone-next` step after the § 10.25 probe (`docs/planning/torch-mps-series/finding.md`, 2026-11-02) and the repair-evidence unit.

## Brief

The § 10.25 probe's 16-task sample produced **one** near-miss in 208 evaluable draws, so it barely exercised the repair. The 8B night's journals record **51 private `NOT_SOLVED` draws across 20 private tasks**, plus **1** on the public task — 52 draws in total, not "51 tasks". Pre-register a § 10.27 Type 1 amendment naming those 20 private tasks and the one public task as the next repair probe: 21 tasks × `K = 16` = **336 draws**, with the GO unchanged (at least one strict-`PASS`). The sample is outcome-selected from an already-run night, and the amendment must say so: a GO is evidence on this sample only, not the corpus.

The Torch/MPS sheet's probe pass becomes the § 10.27 near-miss sample: a pre-step symlinks the 20 manifests into `tasks/local/near-miss`, the probe draws `--probe 20` against that root, and `check-probe --probe 20` decides the harness. The night block stays the full 51+1 corpus. This is an amendment + sheet + guards unit: no runtime, reward, gate, corpus, held-out, `K` or `R` change.

## Acceptance

- § 10.27 names the 20 private ids and `pallets__flask-4045`, states 21 tasks / 336 draws / 52 near-misses (51 private + 1 public), the outcome-selected disclosure, the GO, the non-comparability and that no count has been measured.
- The docs guard derives the 20 from the amendment and cross-pins them to `tasks/local-ledger.json` (all present) and `tasks/heldout/source-b.json` (none held out).
- The sheet's probe block symlinks the 20 into `tasks/local/near-miss`, runs `--probe 20 --tasks $REPO/tasks/local/near-miss`, and passes `--probe 20` to `check-probe`; the night block is unchanged.
- The sheet guard pins the 20 ids, the symlink root, `--probe 20`, 336/21 tasks, § 10.27, the two decisions and the corrected no-`NO_ORACLE` disclosure.
- Full suite, ruff and mypy green; no GPU run.

## Caveat

The sample is **outcome-selected**: the 20 tasks are the ones that produced a `NOT_SOLVED` in `torch-8b-night-001`, and the 8B night has no ledger — its journals are the provenance. A GO on this sample is not a corpus claim. The finding's earlier "51 `NOT_SOLVED` across 51 tasks" is corrected to 51 private draws across 20 tasks plus 1 public; the amendment records the correction.
