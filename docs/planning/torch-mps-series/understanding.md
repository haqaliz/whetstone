# Understanding — torch-mps-series

**Unit:** `feat/torch-mps-series/aliz` · **Written:** 2026-10-20 · **Source:** the inline brief in
`docs/planning/_card/issue.md`.

## What the work is really asking

The MLX series emits an **MLX adapter**, loadable only on Apple Silicon. The user needs a model
**everyone can use**. The MPS arm proved the cross-platform path locally: a Torch/PEFT LoRA on a
0.5B HF base trained in ~21 minutes on the Mac's MPS, sealed a v2 checkpoint (`torch`/`mps`/
`float16`, digest `075bf0fe…`), and produced a 2.1 MB PEFT adapter that any `transformers`/`peft`
stack can load. That arm is a demo: it trained on night #1's 6 examples and `check-leakage` exits
1 (4 of 6 touch `donor-a-c6e4d4c4de87`).

This unit plans the **Torch/PEFT main series on the Mac's MPS**: a 7B-class HF base, a Type 1
pre-registration amendment, a Torch/MPS night sheet, the runtime-selection and MPS-load fixes the
dig found, and the write-up. The night itself is operator-run after the code merges; the finding
is a follow-up. The MLX 32B series remains a separate, Apple-only evidence series and is not
retired.

## Evidence from the dig (all citations in the worktree)

**The base must be 7B-class HF, not the MLX 4-bit directories.**
- The on-disk `weights/Qwen2.5-Coder-{3,7,14,32}B-Instruct-4bit` are **MLX format** (packed U32
  weights + scales/biases, `config.json` declares MLX 4-bit quantization). `torch_runtime` calls
  `AutoModelForCausalLM.from_pretrained` directly and has no MLX dequantization path.
- A plain HF 7B (`Qwen/Qwen2.5-Coder-7B-Instruct`) must be fetched: ~15.2 GB fp16/bf16, through
  `weights.fetch` (resolves `main` to an immutable sha, records per-file hashes, rewrites
  `weights/provenance.json`). `--only` must be the full `Qwen/...` id: the substring matcher would
  also match `mlx-community/...-4bit` and refuse as two candidates.

**The 7B fits the steady-state MPS headroom; the load transient is the risk.**
- The arm records `device_memory_bytes = 30,150,672,384` and `headroom_bytes = 25,628,071,526`
  (0.85 × device). 7B fp16 weights ≈ 15.23 GB; 14B ≈ 29.54 GB → the 14B is refused even
  steady-state.
- Calibrated from the 0.5B probe (2.51 GB peak, ~0.99 GB weights), the non-weight overhead is
  ~1.53 GB, so the 7B steady-state is ~16.8 GB — inside the 25.6 GB headroom.
- **But** `torch_trainer` loads with no `device_map`/`low_cpu_mem_usage` and then moves the model
  to MPS; on unified memory the 0.5B peak is consistent with a double copy (2 × weights). If 7B
  doubles, the peak is ~31 GB — above the headroom, and `CapacityExceeded` writes no checkpoint.
  The code has no mitigation today. This is the single biggest feasibility risk, and the **7B
  `train-arm` pre-flight** (6 examples) is the measurement that settles it.

**Runtime selection is a real CLI gap.**
- `backend.detect()` refuses when both `mlx` and `torch` are importable (`AmbiguousBackend`). The
  `run --night` parser has **no** `--runtime`/`--backend`/`--device` flag, and the handler does
  not catch `AmbiguousBackend`/`NoBackend`, so the run door **tracebacks** instead of exiting 2.
  `train-arm` refuses cleanly (it catches `RuntimeError`). The primary venv now has both.
- `run_night` already accepts a `runtime=` argument programmatically; the missing piece is the
  CLI. A torch-only venv is the current workaround; a `--runtime {mlx,torch}` flag is the clean
  fix and is small and testable.

**The gate can decide a Torch/MPS pair; the § 3 baseline door cannot.**
- `gate_engine_for` dispatches on the candidate's recorded backend; an untrained incumbent is
  exempt from `MismatchedBackend` and follows the candidate's engine (`torch_gate_engine` loads
  the base alone). A Torch/MPS candidate vs an untrained Torch/MPS incumbent works.
- The gate does **not** check candidate/incumbent base identity, and does not bind the host to the
  recorded device/precision; run the gate on the same MPS host and quote the checkpoint's
  provenance.
- The § 3 baseline door is **MLX-only** (`baseline_engine` imports `mlx_lm`; the CLI hardcodes
  it) and its `tool_versions()` names `mlx-lm` unconditionally. A Torch/MPS baseline/headline is a
  **follow-up unit**, not this one. This unit's exit is the first **gate decision** for the new
  series, not a published delta.

> **Corrected 2026-10-28, when `torch-baseline-door` landed.** The paragraph above describes the
> tree before the follow-up: the § 3 baseline door now accepts `--runtime {mlx,torch}`, dispatches
> `torch_runtime.torch_gate_engine` on an untrained checkpoint, and records the backend in the
> sealed evidence and artifact. The **measurement itself remains unspent** — § 12 puts it last,
> and the § 10.25 probe still decides whether the 8B base survives. The § 1 headline remains a
> later operator step; the door only makes it possible.

**The night sheet must be its own sheet.**
- `tests/test_night_runbook_guards.py` is hardcoded to one sheet and asserts exactly two door
  blocks and one retained `--only`. A Torch block in the MLX sheet fails it.
- The precedent is one guard module per sheet (`test_probe_runbook_guards.py`,
  `test_larger_base_runbook_guards.py`, `test_gate_runbook_guards.py`), importing the
  command-independent helpers by identity and re-pinning the door-specific ones.
- The MLX sheet **excludes the 7B by name** for a measured zero ceiling. The Torch/MPS sheet must
  **retain** the 7B-class base; copying the exclusion would exclude the intended candidate.
- `check-probe` pins the budget, held-out digest, harness and seed map, but **not the backend**. The
  Torch sheet must read `ledger.backend.name/device/precision` back itself, or the unit adds a
  backend pin to `check-probe` (a code change; the sheet read-back is the smaller slice).
- A **probe writes no checkpoint and never reaches the capacity probe**; the probe validates the
  generation/verifier chain, not MPS training fit. The 7B `train-arm` pre-flight is the fit check.

**The held-out split does not move.** It is derived from the task corpus, not the base; § 10.16's
document (schema, membership, digest) is unchanged by a runtime/base change. The new night consumes
the same `tasks/heldout/source-b.json` and records the same digest. The training pool is the same
committed 66-task corpus; at K=16 the denominator is the sheet's 52 (51 private + 1 public) unless
the re-mine adds tasks.

## Contradictions surfaced — flag, do not paper over

**1. "The 32B MLX base is the main series" vs a universal-model main series.** Every amendment
since § 10.10 restates the 32B/MLX pin as the main series. § 10.10 itself says the base remains
swappable and a change is a further Type 1 amendment. The resolution must be stated, not edited
in: **the Torch/MPS 7B series becomes the new main series; the 32B/MLX series remains a separate,
non-comparable evidence series, not retired.** The roadmap needs a dated correction blockquote,
not an in-place edit.

**2. The MLX sheet excludes the 7B; the MPS series retains it.** The exclusion is a measured
statement about the MLX 7B's zero ceiling, not about MPS/7B. The new sheet must say why it retains
the 7B (the only class that fits MPS headroom) and must not copy the exclusion. The zero risk is
real: the 7B class has produced zero strict-`PASS` on this task family in the MLX arm; the only
nonzero is the 32B.

**3. The probe is not a fit check.** The probe writes no checkpoint and returns before the capacity
probe. A green probe does not prove the 7B fits MPS; the first fit check is training. The unit adds
a **7B `train-arm` pre-flight** on night #1's 6 examples before the night, so a `CapacityExceeded`
is discovered in minutes rather than after a 40-hour night.

**4. The § 3 baseline/headline is not reachable through the shipped door.** The baseline engine is
MLX-only and its provenance names `mlx-lm`. This unit scopes the **gate decision**; the baseline
and P4 headline for the Torch/MPS series are a follow-up unit with a code change. Saying otherwise
would overclaim.

## Core-loop placement

Element **② the nightly improvement loop** (a second production runtime, a universal artifact) and
element **③ the never-regress gate** (a Torch/MPS candidate against a Torch/MPS untrained
incumbent). The reward (①) is untouched: the same STRICT verifier, Seatbelt sandbox, operator-held
tests and held-out document.

## Decisions for the PRD / review gate

1. **Base:** 7B HF (`Qwen/Qwen2.5-Coder-7B-Instruct`) — the only class that fits MPS and has a
   chance; 3B is safer on fit but historically zero; 14B does not fit. Recommended: 7B, with the
   pre-flight as the fit gate and a documented fallback to 3B if it refuses.
2. **Runtime flag:** add `--runtime {mlx,torch}` to `run --night` (and `train-arm`) with a clean
   exit-2 refusal; this is a small, testable must-have. Recommended: yes.
3. **MPS load path:** add `low_cpu_mem_usage=True` and, if supported, a direct-to-device load; pin
   the kwargs in a test; the 7B pre-flight measures the real peak. Recommended: yes, as a
   must-have necessary-condition fix, with the honest caveat that only the pre-flight measures it.
4. **Series designation:** the Torch/MPS 7B becomes the new main series; the 32B/MLX series remains
   separate. Recommended: yes, by § 10.20 + a dated roadmap correction.
5. **Scope:** the amendment, the runtime flag, the load fix, the new sheet + guard, and the
   write-up. The 7B fetch, pre-flight, probe, night, gate and finding are operator-run after the
   merge. The § 3 baseline/headline is a follow-up. Recommended: yes.
