# Spec — night-sheet

**Aspect:** `night-sheet` · **Unit:** `torch-mps-series` · **PRD:** `../prd.md` M4/M5 ·
**Date:** 2026-10-20

## Purpose

A command sheet for the Torch/MPS series, held by its own guard, so the operator runs the series
the amendment pinned rather than a hybrid of the MLX sheet and good intentions.

## The sheet

`docs/planning/torch-mps-series/night-door/runbook.md`.

**Environment.** `uv run --extra torch whetstone …`; `--runtime torch` on both doors. The primary
venv may hold both runtimes; the flag names Torch. One night at a time, because the Torch path
seeds `torch.manual_seed` globally.

**Probe block.** `--probe 2`; the two donor roots; the public instances and pool; `--weights
$REPO/weights`; `--only Qwen/Qwen2.5-Coder-7B-Instruct`; `--runs $REPO/runs/torch-mps-probe`;
`--checkpoints $REPO/checkpoints/torch-mps-probe`; `--workspace
$REPO/runs/<torch-probe-run-id>-workspace`; `--timeout 900`; `--recorded-on`/`--run-id`/
`--run-seed`; `--heldout $REPO/tasks/heldout/source-b.json`; the five dev ids. No re-mine.

**Night block.** The same flags without `--probe`, plus the re-mine block (`--remine $DONOR
--remine-label donor-a --remine-out $REPO/tasks/local/remined --remine-limit 5`), distinct roots
and a distinct run id.

**The candidate is retained, not excluded.** The MLX sheet excludes the 7B by name; this sheet
retains the 7B HF base and states why (the only class that fits the MPS headroom). The MLX 4-bit
directories are not Torch-loadable; the 14B/32B are excluded by the 25.6 GB MPS headroom.

**The MPS read-back.** After the probe and the night, read `runs/<id>/ledger.json` and confirm
`backend.name == "torch"`, `backend.device == "mps"`, `backend.precision == "float16"`. `check-probe`
does not pin the backend; this read-back is the sheet's own check.

**The fit caveat.** The probe writes no checkpoint and never reaches the capacity probe; it
validates the generation/verifier chain, not MPS training. The 7B `train-arm` pre-flight is the fit
measurement; a `CapacityExceeded` there routes to the load fix or the 3B fallback.

**Denominator.** 52 tasks (51 private + 1 public) at `K = 16`, unless the re-mine grows the pool;
the sheet states the arithmetic and the held-out exclusion order.

**Resume.** A killed probe restarts fresh under a new id; a killed night restarts the same command
with the same `--run-id`/`--run-seed` and replays its draw journals. Do not delete the run
directory.

**Finding home.** `docs/planning/torch-mps-series/finding.md`; raw counts stay in the gitignored
`runs/`; no `reports/` path.

## The guard

`tests/test_torch_mps_runbook_guards.py`, importing `_bash_blocks`, `_named_paths`,
`_worktree_name` (and the anchoring helper) from `tests/test_runbook_guards.py` by identity. It
pins: exactly two door blocks; every flag exists in the shipped parser; the writable roots are
absolute; no worktree is named; `--runtime torch` on both doors; `--only` is the 7B HF id and no
`mlx-community` value appears; the torch-only environment prefix; the MPS read-back sentence; the
7B fit caveat; the 52-task denominator; the five dev ids; the held-out document on both doors and
on `check-probe`; the resume rule; the re-mine block; the operator-declared ids; the finding home;
no `/reports/` value; the § 10.20 citation. It does **not** edit the MLX guard and does **not**
copy its 7B exclusion.

## The write-up

`docs/STATUS.md` and `CHANGELOG.md` in the same commit: the series, the runtime flag, the load
path and the sheet landed; the **night is unrun**; **no number** is claimed; the 7B zero and
load-transient risks are stated; the baseline/headline is a follow-up. A `tests/test_docs.py`
guard in the k16 shape.
