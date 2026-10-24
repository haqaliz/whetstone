# PRD — base-14b (Qwen3-14B NF4 QLoRA)

## Problem

The 8B series answered its question: **0 strict-PASS in 816 private draws** (206 real diffs in 624
evaluable draws), no checkpoint. It broke the format wall and did not solve. The main series needs
a larger base that still fits this Mac.

## Evidence already in hand (2026-10-24)

- `Qwen/Qwen3-14B` @ `40c069824f4251a91eefaf281ebe4c544efd3e18`, Apache-2.0, 14.8B,
  `Qwen3ForCausalLM`; the plain HF snapshot is on disk (28 GB), provenance written.
- The 4-bit path is proven on MPS: bitsandbytes 0.50.2 loads NF4, generates, and takes LoRA
  gradients with PEFT (`prepare_model_for_kbit_training`).
- MPS fit probe on the 14B NF4: **peak 17.67 GB** against the **25.63 GB** headroom
  (`fits: True`), 8 steps in 984 s (~123 s/step).
- The 30B-A3B-fp16 route is excluded on this machine: 61 GB checkpoint, 36 GB unified memory.

## What changes

1. § 10.22 (Type 1) pins Qwen3-14B @ `40c06982…`, NF4 storage (double quantization, `float16`
   compute), torch 2.14.1, and the unchanged held-out/K/R/verifier/gate. § 10.21 (the 8B) stays
   byte-intact and its series stays separate and non-retired.
2. The Torch/MPS sheet names the 14B, the `quantize.json` sidecar and the measured fit; both door
   commands pass `--only Qwen/Qwen3-14B`.
3. The guards pin the amendment, its log row and the sheet cross-pin; the sheet guard pins the
   sidecar and NF4.

## Non-goals

- No threshold, no reworded § 1/§ 4/§ 6, no new report home.
- No change to the verifier, the gate, the corpus or the held-out split.
- No training before the format pre-flight returns GO.

## Acceptance

- § 10.22 exists, is Type 1, and carries the base, revision, NF4, fit, unchanged inputs,
  non-comparability and "no training has run".
- The amendment log has the § 10.22 row.
- The sheet's two door blocks pass `--only Qwen/Qwen3-14B` and name the sidecar.
- The guards and the full suite are green.
- The format pre-flight (`--probe 8`, K=16) is run and its GO/NO-GO recorded in the finding.
