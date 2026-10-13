# Spec — dtype

**Aspect of:** `portability-cpu-dtype` (`docs/planning/portability-cpu-dtype/prd.md`) ·
**Written:** 2026-10-11 · **Order:** first (the amendment pins this constant by name).

## Problem slice

The Torch runtime declares `DEVICE_PRECISION["cpu"] = "float32"`
(`src/whetstone/loop/torch_runtime.py:53-57`), which caps the CPU-only portability arm at a 3B
base (`docs/ROADMAP.md:784-787`). Move it to `"bfloat16"` and pin the declaration so it cannot
drift silently.

## In scope

- `DEVICE_PRECISION["cpu"]` → `"bfloat16"` (`torch_runtime.py:56`).
- A test pinning the **exact value of every declared device** — not merely key presence
  (the existing test at `tests/loop/test_torch_trainer.py:176-187` only checks presence).
- Correction of the module docstring (`torch_runtime.py:50-52`), which justifies `float32` with a
  **fp16** claim ("A CPU run in fp16 is arithmetic that silently produces nothing useful") —
  bf16 is not fp16 and keeps fp32's exponent range. The corrected docstring must not claim bf16
  is faster or better (no measured basis).

## Out of scope

- Recording the precision in evidence — aspect `record`.
- Any base change, the amendment, or a run. `src/whetstone/verify/` and `tasks/` are untouched.

## Acceptance criteria

- **AC1 (PRD M1):** `tests/loop/test_torch_trainer.py` asserts
  `torch_runtime.DEVICE_PRECISION == {"cuda": "bfloat16", "mps": "float16", "cpu": "bfloat16"}`,
  watched failing against `"float32"` first. The existing key-presence test stays green.
- The two read sites (`torch_runtime.py:138`, `:396`) are unchanged — they already index the map.

## Dependencies & sequencing

- No code prerequisite. Must land before the `amendment` aspect (which cross-pins `bfloat16`).
- `record` is independent (it records whatever the map declares).

## Open questions / risks

- None blocking. bf16's CPU viability is decided by the arm's probe/night, not here — this aspect
  only moves the declaration and its pin.
