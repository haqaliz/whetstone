# PRD — repair-arm (8B, bounded repair draws)

## Problem

The 8B fp16 series is the only stable runtime on this machine (35 h, no hang) and produced **206
real diffs in 624 evaluable draws** — but **0 strict-PASS**. Of those diffs, **51 applied cleanly and
failed their tests**: the near-misses. The existing retry is completion-triggered and sealed before
verification, so it never fires on an applied-but-failed patch.

The 14B NF4 path is dead here: the pre-flight produced 7 draws, all `NO_DIFF`, at ~9 min/draw, then
hung in an uninterruptible Metal wait (`_local_scalar_dense_mps`; #86). The 30B does not fit the
machine's memory. The repair is the next lever.

## What changes

- **The repair contract (§ 10.23, Type 1):** after a `NOT_SOLVED`, the run may re-ask up to
  `R_repair = 2` times. The repair prompt is the first prompt plus a fixed instruction that the
  patch applied and the tests failed — **no test output and no prior completion**, so it is a pure
  function of the first prompt and the seal pre-poses it. Every repair is re-verified by the same
  STRICT verifier; a repaired pass is a strict-`PASS`.
- **The probe rule, committed before the probe:** `run --night --probe 8 --repair 2` on the 8B,
  8 private + 1 public × K=16 = 144 draws; **GO iff at least one draw is strict-`PASS`**. A GO is
  the first solve evidence under the repair contract, not a model claim.
- The ledger publishes `repair_budget` and `repair_template_sha256`; old sidecars parse with the
  no-repairs state.
- The Torch/MPS sheet returns to the 8B and passes `--repair 2` on both doors.

## Non-goals

- No test output or prior completion in the prompt (the seal's finiteness, B1).
- No loosened verifier, no lower threshold, no change to § 1/§ 4/§ 6, the held-out set, K, R, the
  corpus or the gate.
- No full night before the probe returns GO.

## Acceptance

- `--repair N` re-asks only after `NOT_SOLVED`, bounded, and the repaired verdict is the record.
- `freeze(repair=True)` poses the repair prompt under its task; a run without it is byte-identical
  to the no-repairs contract.
- The ledger's `GenerationContract` carries the budget and the template digest.
- § 10.23 and the log row are committed before the probe; the sheet and guards pin the repair.
- The probe's GO/NO-GO is recorded in the finding with its counts.

## Cost

The 8B is ~2.5 min/draw at fp16; a repair fires on ~6% of draws and adds up to two more draws each,
so the probe is ~4–5 h and a night ~40 h. The probe is the gate.
