# feat probe-backend-pin

**Source:** inline brief from the `whetstone-next` pick (2026-10-29), following the
`torch-mps-series` PRD's own N1 follow-up.

## Brief

`whetstone check-probe` decides the § 10.25 probe's GO/NO-GO from one ledger, but it pins only
the draw budget, the held-out digest, the control fold and the seed map. The ledger records the
runtime under which the probe actually ran (`whetstone-run/3`'s `backend` block), and the § 10.25
probe is a Torch/MPS `float16` run — but a mis-provisioned run that recorded `mlx` would pass the
door today. The Torch sheet reads the backend back by eye; the command's exit should be the check.

Add optional `--runtime {mlx,torch}`, `--device` and `--precision` pins to
`whetstone check-probe`. When any is passed, the ledger's recorded backend must exist and match;
a mismatch or a missing block is a named violation (exit 1), never a pass. With no pins the
command behaves exactly as before. The Torch sheet passes all three; the MLX sheet does not.

## Acceptance

- `run_check` accepts the three optional pins, compares the recorded `backend` block and adds
  the pins and the recorded backend to `ProbeReport` / `disclosure`.
- Runtime comparison goes through `backend.family` (the legacy `torch-*` spelling is tolerated);
  device and precision compare exactly.
- A missing backend block under a pin is a named violation, not a refusal and not a traceback.
- The CLI exposes the three flags, passes them through, and its exact flag-surface test is
  updated.
- The Torch sheet's `check-probe` block passes all three; its guard's "check-probe does not pin
  the backend" premise is replaced by "it pins it too; the read-back remains a cross-check."
- No reward, gate, held-out, budget, seed, corpus or § 10.25 input change. No measurement run.
