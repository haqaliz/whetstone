# PRD — probe-backend-pin

**Unit:** `feat/probe-backend-pin/aliz`. **Source:** inline brief, `docs/planning/_card/issue.md`.
**Understanding:** `docs/planning/probe-backend-pin/understanding.md`. **Status:** small
follow-on to `torch-mps-series`; no number is measured.

## Problem statement

`whetstone check-probe` is the door in front of the § 10.25 probe. It decides from the ledger's
control fold, seed map, declared budget and held-out digest — not from the runtime the probe
actually ran under (`src/whetstone/loop/check_probe.py:1-31`). The ledger records that runtime
(`ledger.py:405`), and the Torch sheet reads it back by eye
(`docs/planning/torch-mps-series/night-door/runbook.md:88-90`), but a mis-provisioned run that
recorded `mlx` would still pass the command today. The `torch-mps-series` PRD names the code
follow-up as N1: "a `check-probe --backend torch/mps/float16` pin, with tests"
(`docs/planning/torch-mps-series/prd.md:126-132`).

## Goals & success metrics

- The door can refuse a probe whose recorded runtime, device or precision is not the declared
  one, by name, before the GO/NO-GO is read.
- With no pins the command's decision and output are unchanged.
- The Torch sheet passes the three pins; its guard no longer claims the door is silent about
  the backend.
- No measurement, number or threshold is added; the § 10.25 amendment is untouched.

## Requirements

### Must-have

1. **`run_check` pins.** Keyword-only `runtime: str | None`, `device: str | None`,
   `precision: str | None`. With any pin:
   - the ledger's `backend` must be a mapping; absence or malformation is a named violation;
   - `runtime` compares through `backend.family` (so `torch-*` is Torch), not string equality;
   - `device` and `precision` compare exactly;
   - a mismatch names the recorded and pinned values in the violation.
2. **The report carries what was checked.** `ProbeReport` gains `backend` (the recorded block or
   `None`) and `pins` (the non-empty pins, in a stable order). `disclosure` prints the pins and
   the recorded backend; the violation line is unchanged in shape.
3. **The CLI names the flags.** `whetstone check-probe --runtime {mlx,torch} --device <str>
   --precision <str>`, all optional, passed through to `run_check`; the exact flag-surface test
   grows by exactly these three.
4. **The sheet and its guard.** `docs/planning/torch-mps-series/night-door/runbook.md`'s
   `check-probe` block passes `--runtime torch --device mps --precision float16`; the read-back
   sentence becomes "check-probe pins it too; the read-back is the cross-check", and
   `tests/test_torch_mps_runbook_guards.py` is updated watched-failing-first.
5. **No new exit code.** A pin mismatch is a violation (1); an unreadable run/ledger/held-out
   document remains a refusal (2). The v2 tolerance path still decides without pins; with a pin
   and no backend it is a violation.

### Should-have

- A disclosure line for a refused probe that still has a backend, so the operator sees the
  recorded value beside the violation.

### Nice-to-have

- A `--backend` convenience spelling. Declined: three explicit pins match the repo's flag style
  and name the three pinned inputs directly.

## Out-of-scope

- Running the § 10.25 probe; changing its base, budget, held-out document or GO rule.
- The reward path, the gate rule, the corpus, `K`, `R`, or any `reports/` home.
- A general backend pin for `check-leakage` or the baseline door.

## Risks & open questions

- **The v2 tolerance path.** A `/2` ledger may carry no backend; the pin must refuse it as a
  violation rather than crash. A `/3` ledger missing the required block is already refused by
  the ledger reader.
- **The guard's old sentence.** The Torch sheet guard explicitly asserts the door does not pin
  the backend. That is a deliberate premise change: the test must be edited with the sheet,
  never deleted, and the read-back must remain.
- **The pin is a check, not a measurement.** It cannot fix a mis-provisioned run; it can only
  stop the next step from reading its GO/NO-GO.

## Aspect decomposition

One aspect: **`probe-door`** — code, tests, sheet and guard. The write-up is part of the same
aspect; the unit is too small for a second.
