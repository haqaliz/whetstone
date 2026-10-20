# Spec — runtime-selection

**Aspect:** `runtime-selection` · **Unit:** `torch-mps-series` · **PRD:** `../prd.md` M2/M3 ·
**Date:** 2026-10-20

## Purpose

Make the runtime nameable on a machine with both MLX and Torch installed, and stop the Torch
loader from paying a CPU→MPS double copy that the 7B cannot afford.

## M2 — the `--runtime` flag

- Add `--runtime {mlx,torch}` to `whetstone run --night` (`cli.py:264-504`) and
  `whetstone train-arm` (`cli.py:811-868`). The parser uses the literal choices; a test
  cross-pins them to `backend.MLX`/`backend.TORCH` without a module-scope import in `cli.py` (the
  partition guard's function-local-edge rule).
- `run_night` gains `prefer: str | None = None` and calls
  `backend_runtime.detect(prefer=prefer)` when no `runtime` record is passed. `run_arm` gains the
  same. The CLI handlers pass `prefer=args.runtime`; they do **not** import `whetstone.loop.backend`
  at module scope, so `tests/test_reward_path_scope_is_partitioned.py`'s edge list is unchanged.
- `night.REFUSALS` gains `backend.AmbiguousBackend` and `backend.NoBackend`, so
  `whetstone run --night` catches them and returns `USAGE_ERROR` (2) with a named message instead
  of a traceback. `train-arm` already catches `RuntimeError`; add the same named exits to its
  tests.
- With one runtime installed and no flag, behaviour is byte-identical to today.

## M3 — the MPS load path

- In `torch_runtime.torch_trainer` (`:148-150`) and `_load_torch` (`:408-410`), pass
  `low_cpu_mem_usage=True` to `AutoModelForCausalLM.from_pretrained`.
- Optional, only if a live 0.5B MPS check confirms it: a narrow `device_map={"": device}` direct
  load. The spec does **not** require it; the pre-flight measures whether the keyword is enough.
- A test injects a fake `AutoModelForCausalLM.from_pretrained` and asserts the keyword; the
  docstring states the honest limit: the keyword reduces the transient, the 7B `train-arm`
  pre-flight is the measurement.

## Non-goals

- No change to the reward path, the gate, the sampler, the precision map, or the MLX code.
- No automatic fallback from a missing runtime: an unavailable runtime refuses; it never silently
  picks another.
- No new `cli` module-scope import; the partition guard stays untouched.

## Acceptance

- A mixed environment with `--runtime torch` selects Torch; `--runtime mlx` selects MLX.
- A mixed environment with no flag is a named exit 2, not a traceback; an unavailable runtime is
  a named exit 2.
- A single-runtime environment with no flag behaves as today.
- The trainer and loader pass `low_cpu_mem_usage=True`.
- `ruff`, `mypy`, the partition guard and the existing loop suites are green.
