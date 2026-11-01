# feat probe-sample-pin

**Source:** inline brief from the `whetstone-next` pick (2026-10-31), grounded in
`PREREGISTRATION.md` § 10.25, `docs/planning/torch-mps-series/finding.md`, and the shipped
`probe-backend-pin` unit.

## Brief

The § 10.25 repair probe is the only unrun measurement, and the Torch/MPS sheet currently runs a
2-task probe while the amendment pins a 16-task, 272-draw measurement. Add an optional
`--probe N` pin to `whetstone check-probe` that compares the ledger's `task_set.probe` and names
a mismatch as exit-1, leaving the unpinned decision byte-identical; a pin can only add a
violation. Align the sheet's probe and check-probe blocks to `--probe 16`, state both decisions
(the command's harness rule and § 10.25's yield GO: at least one strict-`PASS` of 272), and
replace the stale "raise K" halt text.

## Acceptance

- `whetstone check-probe --probe N` compares the ledger's `task_set.probe` to `N`; a mismatch or a
  full night is a named exit-1 violation; no pin is byte-identical to today; a pin never turns a
  failing probe green.
- The Torch/MPS sheet's probe block runs `--probe 16` (the § 10.25 sample: 16 private + 1 public
  at `K = 16` = 272 draws), and its `check-probe` block passes `--probe 16`.
- The sheet states both decisions distinctly: the command's harness rule (control `PASS` on every
  draw, non-empty seed map, declared budget, held-out digest, backend pins) and § 10.25's yield GO
  (at least one strict-`PASS` of the 272 draws). A zero yield is a NO-GO even when `check-probe`
  exits 0.
- The stale "the next response is to raise K" halt text is replaced with § 10.25's rule: a NO-GO
  returns the lever to a human, never to a loosened verifier.
- The sheet guard pins `--probe 16`, the roots order, and the derived sample count; the sample's
  16 ids are derived from the committed `tasks/local-ledger.json` + `tasks/heldout/source-b.json`
  + the five declared dev ids, or a § 10.26 Type 1 amendment names them before the probe.
- Full suite, ruff and mypy green; no GPU run; the reward, gate, corpus, held-out document, `K`,
  `R` and the § 10.25 inputs are untouched.

## Caveat

The ledger records `task_set.probe` as an integer and counts, not the 16 ids
(`src/whetstone/loop/ledger.py`). `--probe 16` therefore pins the sample size, not its identity;
the sample is positional (15 surviving `donor-b-*` plus the first surviving `donor-a-*`), and a
corpus change before the probe silently shifts it. If the dig finds the positional rule
under-specified, append a § 10.26 Type 1 amendment naming the sample before anything runs.
