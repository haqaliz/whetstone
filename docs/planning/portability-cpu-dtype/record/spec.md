# Spec — record

**Aspect of:** `portability-cpu-dtype` (`docs/planning/portability-cpu-dtype/prd.md`) ·
**Written:** 2026-10-11 · **Order:** independent of `dtype` (records whatever it declares).

## Problem slice

The precision that trained a checkpoint and produced a run's rollouts is **recorded nowhere**:
`Backend` (`src/whetstone/loop/backend.py:93-131`) has no precision field,
`TrainingArgs.recorded()` is runtime-agnostic, and neither the checkpoint nor the ledger names a
dtype. A fp32 and a bf16 checkpoint therefore carry byte-identical provenance, and the gate
(`gate.refuse_cross_backend`, `gate.py:311-332`) cannot tell them apart. Record the precision on
the `Backend` record so the non-comparability § 13 names became enforceable.

## In scope

- `Backend` gains an **optional, last** field `precision: str | None = None` (so every existing
  construction, in `backend.py:241,269` and in tests, stays valid).
- `Backend.recorded()` (`:118-131`) emits `"precision"`.
- `_describe_torch` (`:250-275`) fills it from `torch_device()` + `DEVICE_PRECISION`
  (function-local import, matching the module's import discipline).
- `_describe_mlx` (`:234-247`) leaves it `None` — MLX's precision is declared nowhere here, and
  inventing one is an unverified claim.
- The precision reaches the evidence through the single `recorded()` writer: the checkpoint's
  `backend` block (`sft.write_checkpoint`, `sft.py:786`) and the run ledger's (`ledger.py:397`).
- The gate's comparability is pinned: a bf16-vs-fp32 pair is refused by the **existing** whole-dict
  `==` (`gate.py:323`) — no gate-logic change.

## Out of scope

- Any change to `gate.py`'s logic, the decision table, `R = 3`, or `unverified == 0`.
- The generator's `provenance()` (`torch_runtime.py:358-379`) — run-level attribution through the
  `Backend` record is the surface (PRD "S0 resolved").
- A checkpoint schema bump: the five top-level body keys are unchanged; the nested key changes the
  `backend` claim's bytes only.

## Acceptance criteria

- **AC2 (PRD M2):** `_describe_torch`'s `precision` equals `DEVICE_PRECISION[device]`; `_describe_mlx`'s
  is `None`.
- **AC3 (PRD M2):** the `recorded()` key-set test is updated deliberately (watched failing first)
  and pins `precision`; `recorded()` on `Backend(precision="bfloat16")` returns `"bfloat16"`.
- **AC4 (PRD M3):** the checkpoint `backend` block and the run-ledger `backend` block carry the
  precision; `verify_checkpoint` still verifies with the nested key (no schema bump).
- **AC5 (PRD M4):** `refuse_cross_backend` raises `MismatchedBackend` for two records differing
  only in `precision`; does not raise for same-precision; still exempts `backend is None`
  (untrained incumbent) and a checkpoint with no `backend`.

## Dependencies & sequencing

- Can land before or after `dtype`; both are code. Land before `amendment` (which pins the
  recorded shape).
- `test_backend.py:150-176`'s exact-key assertion is the one test deliberately updated — on the
  record, watched failing first (the repo's convention).

## Open questions / risks

- The "absence is an unknown, not a mismatch" exemption (`gate.py:318-320`) applies to a checkpoint
  with **no** `backend` block; it is not extended to a `backend` block missing `precision`. The
  real comparisons are: new-torch vs old-v1-torch → refused (correct); MLX vs MLX → equal;
  untrained → exempt. AC5 pins each.
