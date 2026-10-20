# Spec — series-amendment

**Aspect:** `series-amendment` · **Unit:** `torch-mps-series` · **PRD:** `../prd.md` M1 ·
**Date:** 2026-10-20

## Purpose

Pin the new main series in the pre-registration **before** the night that records it, and record
the change in the roadmap without rewriting history.

## The pinned inputs

| Input | Value |
|---|---|
| Base | `Qwen/Qwen2.5-Coder-7B-Instruct` |
| Revision | `c03e6d358207e414f1eca0bb1891e29f1db0e242` (resolved 2026-10-20) |
| Runtime | `torch` + PEFT, device `mps`, precision `float16` (`DEVICE_PRECISION["mps"]`) |
| Adapter | PEFT `adapter_model.safetensors` |
| Held-out | `tasks/heldout/source-b.json`, document digest `6b5fbd49…` — **unchanged** |
| K / R | `16` / `3` — **unchanged** |

## Required text

Append `### 10.20 <title> — 2026-10-20` to `PREREGISTRATION.md`, in the § 10.10/§ 10.11/§ 10.18
shape:

1. the bold **Type 1 (§ 8.1): pins the inputs of a new series, committed before the training it
   governs runs** line; no success threshold; no rewording of § 1, § 4 or § 6; it **does not edit
   § 10.10**;
2. the base and revision, per-file hashes in `weights/provenance.json`, re-hashed before a token is
   generated;
3. the runtime/device/precision and the adapter format;
4. the held-out document and digest unchanged, `K = 16`, `R = 3` unchanged;
5. the non-comparability paragraph naming weights, runtime, device, kernels and precision, ending
   **"the old series is not extended"**;
6. the 32B/MLX series remains a **separate, non-retired** evidence series;
7. **no `reports/` home**: the gate record is gitignored, the finding lives under `docs/planning/`;
8. **no training has run, no count is claimed**, the § 3 baseline remains unspent, and *"accept the
   finding"* remains legitimate;
9. the amendment-log row.

## The roadmap

A dated `> **Corrected 2026-10-20 …**` blockquote in `docs/ROADMAP.md` § 13/§ 14 records the new
main series and preserves the old 32B/CPU-ceiling sentences as quotations (the § 10.18/§ 10.19
precedent). Never an in-place edit.

## The guard

`tests/test_docs.py` gains a § 10.20 test in the § 10.18/§ 10.19 shape:

- the Type 1 line, the no-threshold/no-rewording line, the non-comparability sentence, "the old
  series is not extended", "No training has run", "the § 3 baseline remains unspent";
- the base id and revision equal the Torch/MPS sheet's;
- `float16` equals `torch_runtime.DEVICE_PRECISION["mps"]`;
- the amendment-log row is present;
- no proportion/figure appears in the amendment or the sheet.

## Non-goals

- No § 3 baseline or § 1 headline (the baseline door is MLX-only; follow-up).
- No edit to § 10.10 or the MLX series' reports.
- No new `reports/` home.
