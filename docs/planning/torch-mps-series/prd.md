# PRD — torch-mps-series

**Unit:** `feat/torch-mps-series/aliz` · **Written:** 2026-10-20 · **Type:** feature, off the
reward path. **Source:** the inline brief in `docs/planning/_card/issue.md`. **Understanding:**
`docs/planning/torch-mps-series/understanding.md`.

## Problem Statement

The MLX series emits an **MLX adapter**, loadable only on Apple Silicon. The product requirement is
a model **everyone can use**. The MPS arm proved the cross-platform path locally: a Torch/PEFT LoRA
on the Mac's MPS sealed a v2 checkpoint (`torch`/`mps`/`float16`) and produced a 2.1 MB PEFT
adapter that any `transformers`/`peft` stack can load. That arm was a demo (0.5B, night #1's 6
leaked examples, `check-leakage` exit 1), not a model.

The dig found five concrete gaps between the arm and a real Torch/MPS series:

1. **No runtime flag.** `run --night` has no way to name the runtime; with both MLX and Torch
   installed, `backend.detect()` raises `AmbiguousBackend` and the run door **tracebacks**.
2. **The 7B fit is unproven.** The 7B fp16 weights (~15.2 GB) fit the 25.6 GB MPS headroom
   steady-state (~16.8 GB with the 0.5B-calibrated overhead), but the trainer loads to CPU and then
   moves to MPS; the 0.5B peak is consistent with a double copy, which for 7B is ~31 GB — above
   the headroom. A `CapacityExceeded` would write no checkpoint.
3. **The MLX 4-bit weights are not Torch-loadable.** A plain HF 7B base must be fetched (~15.2
   GB) and added to `weights/provenance.json`; `--only` must be the full `Qwen/...` id.
4. **The night sheet is MLX-specific and single-sheet-guarded.** A Torch block in the MLX sheet
   fails `tests/test_night_runbook_guards.py` (exactly two door blocks, one retained `--only`), and
   the MLX sheet **excludes the 7B by name** — the exact base the MPS series retains.
5. **The § 3 baseline door is MLX-only.** A Torch/MPS **gate decision** is reachable; a
   Torch/MPS **§ 1 headline** is not without a code change, and is a follow-up.

## What this unit is — and is not

This unit ships the **series**: the Type 1 amendment, the runtime-selection and MPS-load fixes, the
Torch/MPS night sheet and its guard, and the write-up. The **night itself is operator-run after the
merge** (it fetches the 7B, runs the 7B `train-arm` fit pre-flight, the probe and the night), and
the finding is a follow-up commit. It does **not** change the reward, the gate rule, the corpus,
the held-out document, or the MLX series.

It claims **no number**. Whether a 7B Torch/MPS night selects a strict-`PASS` is the operator's
measurement; the 7B class has historically produced zero on this task family, and a zero is a
valid outcome.

## Goals & Success Metrics

A merged, green tree in which:

- **The series is pinned.** A Type 1 § 10.20 amendment names the new main series — Torch/PEFT,
  `mps`, `float16`, the 7B HF base and immutable revision — declares every figure non-comparable
  to the MLX series and the arm, keeps the held-out document unchanged, and records the 32B/MLX
  series as a separate, non-retired evidence series. A dated roadmap correction records the change.
- **The runtime is nameable.** `whetstone run --night --runtime torch` runs Torch on a machine
  with both runtimes installed; an unavailable runtime is a named exit-2 refusal, never a
  traceback. The same flag exists on `train-arm`.
- **The 7B load path is honest.** The Torch loader requests `low_cpu_mem_usage=True` (and, if the
  installed stack supports it, a direct-to-device load), so the CPU→MPS transient is not the
  deciding factor. A test pins the keyword; the 7B pre-flight is the measurement.
- **The sheet is a command sheet, not prose.** A Torch/MPS sheet and its own guard pin the 7B HF
  base (retained, not excluded), `--runtime torch`, the torch-only environment, the MPS backend
  read-back, the MPS headroom, the 52-task denominator, the held-out document, the resume rule and
  the finding home.
- **The write-up is honest.** STATUS/CHANGELOG in the same commit: the series landed, the night is
  unrun, no number is claimed; the 7B zero and load-transient risks are stated.

## Requirements

### Must-have

**M1 — the amendment and the roadmap.**
Append `### 10.20` to `PREREGISTRATION.md` (Type 1, dated), in the § 10.10/§ 10.11/§ 10.18 shape:
the new main series (Torch/PEFT, `mps`, `float16`, the 7B HF repo id and immutable revision, per-file
hashes in `weights/provenance.json`); the held-out document and `document_digest` unchanged; `K =
16`, `R = 3` unchanged; the non-comparability sentence naming weights, runtime, device, kernels and
precision, ending "the old series is not extended"; the 32B/MLX series remains a separate,
non-retired series; no `reports/` home (the finding lives under `docs/planning/`, the gate record
stays gitignored); no training has run, no count is claimed. Add the amendment-log row. Add a
dated `> **Corrected …**` blockquote to `docs/ROADMAP.md` § 13/§ 14 recording the new main series
and preserving the old 32B/CPU-ceiling sentences. A `tests/test_docs.py` guard cross-pins the
amendment's base/revision to the sheet and `float16` to `DEVICE_PRECISION["mps"]`.

**M2 — `--runtime {mlx,torch}` on the two doors.**
Add the flag to `run --night` and `train-arm`. With it, `backend.detect(prefer=…)` is called; an
unavailable runtime is a named exit-2 refusal; a mixed environment without the flag is a clean
exit-2 refusal (the `AmbiguousBackend`/`NoBackend` classes must be in the doors' refusal tuples or
caught explicitly — currently `run --night` tracebacks). With one runtime installed and no flag,
behaviour is unchanged. Tests: a mixed fake environment selects the named runtime; an unavailable
runtime refuses; a mixed environment with no flag refuses cleanly; the single-runtime path is
byte-identical to today's.

**M3 — the MPS load path.**
In `torch_runtime.torch_trainer` and `_load_torch`, request `low_cpu_mem_usage=True`; if the
installed `transformers`/`accelerate` supports a direct `device_map={"": device}`, use it behind a
narrow helper. A test injects a fake `AutoModelForCausalLM.from_pretrained` and asserts the
keyword(s); a live 7B test is not in the suite (the weights are fetched by the operator). The
honest limit is in the docstring: the keyword reduces the transient; the 7B pre-flight is the
measurement.

**M4 — the Torch/MPS sheet and guard.**
`docs/planning/torch-mps-series/night-door/runbook.md` with the probe and night blocks: the same
corpus, dev subset, held-out document, `check-probe --heldout`, `--timeout 900`, absolute paths,
operator-declared ids/seed/date, the resume rule, the re-mine block; but `--runtime torch`, the
7B HF `--only`, a torch-only environment (`uv run --extra torch` or an equivalent), the MPS
backend read-back (name/device/precision), the MPS headroom and the 52-task denominator, and the
finding home. `tests/test_torch_mps_runbook_guards.py` imports the command-independent helpers by
identity and pins the new properties; it does **not** edit the MLX guard, and it does **not** copy
the 7B exclusion.

**M5 — the write-up.**
A `docs/STATUS.md` entry and a `CHANGELOG.md` `Unreleased` entry in the same commit: the series,
the runtime flag, the load path and the sheet landed; the **night is unrun**; **no number** is
claimed; the 7B zero risk and the load-transient risk are stated; the baseline/headline is a
follow-up. Add a `tests/test_docs.py` write-up guard in the k16 shape.

**M6 — nothing on the reward path moves.**
`src/whetstone/verify/`, `tasks/`, `tasks/heldout/source-b.json`, the corpus and the gate rule are
byte-unchanged; the adversarial and reward-path suites stay green. The only source files that move
are `src/whetstone/loop/backend.py` (if the refusal tuples need it), `src/whetstone/cli.py`,
`src/whetstone/loop/torch_runtime.py` and the door/refusal wiring.

### Should-have

**S1 — the 7B fit pre-flight (operator, after merge).** Fetch `Qwen/Qwen2.5-Coder-7B-Instruct` at
a pinned revision, then run `train-arm` with the 7B base and night #1's 6 examples. A green
capacity probe proves the 7B fits MPS; `CapacityExceeded` routes to the load fix or a 3B fallback.
This is the only measurement that settles the transient risk.

**S2 — the sheet's backend read-back.** Because `check-probe` does not pin the backend, the sheet
instructs the operator to read `ledger.backend.name == "torch"`, `device == "mps"`,
`precision == "float16"`; a later unit may add a `--backend` pin to `check-probe`.

### Nice-to-have

**N1 — a `check-probe --backend torch/mps/float16` pin**, with tests, if the code slice is small
enough. Otherwise the sheet read-back is the slice.

## Acceptance Criteria (testable, written first)

1. **Runtime flag.** A mixed environment with `--runtime torch` selects Torch; `--runtime mlx`
   selects MLX; an unavailable runtime is exit 2; a mixed environment with no flag is a clean
   exit-2 refusal (not a traceback); a single-runtime environment with no flag behaves exactly as
   today. Tests for `run --night` and `train-arm`.
2. **Load path.** A fake `from_pretrained` records `low_cpu_mem_usage=True` (and the direct-device
   keyword where used) for the trainer and the generator/gate loader.
3. **Amendment.** The § 10.20 text and log row exist; the cross-pin test passes; the roadmap
   correction is dated and the old sentences are preserved as quotations.
4. **Sheet guard.** The new guard passes; the 7B HF base is retained; the MLX guard is untouched;
   the sheet names `--runtime torch`, the torch-only environment, the MPS backend read-back, the
   headroom and the 52-task denominator; no worktree is named; no `/reports/` path appears.
5. **Write-up.** `docs/STATUS.md`/`CHANGELOG.md` say the night is unrun and claim no number; the
   write-up guard passes.
6. **No movement.** The reward-path/held-out/corpus byte-identity holds; the full suite, `ruff`
   and `mypy` are green.
7. **Operator acceptance (follow-up, not this PR).** The 7B fetch and `train-arm` pre-flight pass;
   the probe exits 0; the night writes a ledger and, if it selects, a sealed Torch/MPS PEFT
   checkpoint; `check-leakage` exits 0; `gate` returns `promoted`/`rejected` on the Torch/MPS
   pair; the finding records the partition and the universal artifact (or the zero).

## Out of scope / guardrails

- **No § 3 baseline or § 1 headline for the new series.** The baseline door is MLX-only; that is a
  follow-up unit with a code change. This unit's exit is the first **gate decision**, not a delta.
- **No 14B/32B on MPS.** The 14B fp16 (~29.5 GB) exceeds the 25.6 GB headroom; the 32B is not
  considered.
- **No MLX change.** The 32B/MLX series, its sheet, its reports and its night are untouched; it is
  a separate, non-retired series.
- **No new `reports/` home.** The gate record is gitignored; the finding is under `docs/planning/`.
- **No reward/gate/corpus/held-out change.** The same STRICT verifier and sandbox; `UNVERIFIED`
  never wins.
- **No egress.** The private corpus stays local; the 7B is public weights.
- **No number.** The night is unrun; the 7B zero risk is stated.

## Risks and flagged gaps

🔴 **The 7B load transient may exceed the MPS headroom.** Steady-state ~16.8 GB fits 25.6 GB; the
current CPU→MPS double copy would be ~31 GB. The `low_cpu_mem_usage`/direct-device fix is a
necessary-condition change; the 7B `train-arm` pre-flight is the only measurement. If it refuses,
the choices are a 3B base (fits, historically zero), a further load-path fix, or accepting the
capacity finding.

🔴 **The 7B class has historically produced zero strict-`PASS`** on this task family in the MLX
arm; the only measured nonzero is the 32B. A zero under the new series is a valid published
outcome; the response is not a looser verifier.

🟡 **The § 3 baseline/headline is not reachable through the shipped door.** The baseline engine is
MLX-only and names `mlx-lm` in its provenance. This unit scopes the gate decision; the headline is
a follow-up.

🟡 **`check-probe` does not pin the backend.** A mis-provisioned Torch run could record MLX and
still pass. The sheet's read-back is the slice; a code pin is N1.

🟡 **The runtime flag is a new CLI surface.** It is off the reward path; the partition guard and the
door tests must be updated in the same commit.

🟡 **The 15.2 GB 7B fetch.** Public weights, no egress of private data; it is an operator step and
may take time on a slow link (x131's link measured ~0.3 MB/s; the Mac's link is the variable).

🟡 **The primary `.venv` is mixed and has a broken `datasets`/`huggingface_hub` pair** from the
arm's ad-hoc installs. The sheet and the operator use a torch-only `uv` environment
(`uv run --extra torch` or a fresh torch-only venv), not the primary venv.

## Aspects

1. `series-amendment/` — M1: § 10.20, the log row, the roadmap correction, the docs guard.
2. `runtime-selection/` — M2, M3: the `--runtime` flag, the refusal mapping, the MPS load path,
   their tests.
3. `night-sheet/` — M4, M5: the Torch/MPS sheet and guard, the write-up, the docs.
4. `operator-run/` — S1, S2, AC7: the 7B fetch, the fit pre-flight, the probe, the night, the gate,
   the finding (operator-executed after merge; no production code).

## Open questions (for the review gate)

1. **The base.** 7B HF (recommended: the only class that fits MPS and has a chance; the pre-flight
   gates the fit) vs 3B (fits safely, historically zero). The 14B is excluded by headroom.
2. **The load fix.** Include `low_cpu_mem_usage` + a direct-device attempt now (recommended) or run
   the 7B pre-flight first and fix only if it refuses? The fix is small and reduces the risk; the
   pre-flight remains the measurement.
3. **The series designation.** The Torch/MPS 7B becomes the new **main** series, with the 32B/MLX
   series separate (recommended), or the Torch/MPS series is a second arm beside the MLX main
   series? The user's universality requirement points to the former.
4. **The baseline follow-up.** Confirm that this unit stops at the gate decision and the § 3
   baseline/headline is a separate unit (recommended), rather than expanding this unit to the
   MLX-only baseline door.
