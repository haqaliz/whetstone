# PRD — pascal-4bit

**Unit:** `pascal-4bit`. **Branch:** `feat/pascal-4bit/aliz`. **Source:** inline brief, after the
x202 pre-flight. **Understanding:** `docs/planning/pascal-4bit/understanding.md`. **Status:**
amendment, provenance and operator sheet; no probe or night is run, and no count is measured.

## Problem statement

The main series runs on the founder's own host `x202` — 3× NVIDIA GTX 1080 8 GB, one GPU — and
that host is Pascal (`sm_61`). It has no native bf16, and the pinned `torch 2.14.1+cu130` build
has no kernels for it. The series cannot draw a token there as pinned.

Two facts were measured on x202 before this unit:

- `torch 2.14.1+cu126` runs fp32/fp16/bf16 on the GTX 1080. It is the same torch version the
  series pinned, with the CUDA build changed to the Pascal-capable one.
- The pinned base `Qwen/Qwen3-8B` at revision `b968826d9c46dd6066d109eabc6255188de91218` loads
  **4-bit NF4** with `bnb_4bit_compute_dtype=bfloat16`, at **6.07 GB VRAM** of 7.92 GiB, and
  `whetstone.loop.torch_runtime.TorchGenerator` generates through the existing `quantize.json`
  sidecar path **with no loader change**: **6.75 new tokens/s**, 64 tokens in 9.5 s.

So the main series can move to x202 at 4-bit, provided the amendment names the CUDA build, the
precision, the sidecar and the sample before the measurement runs — and provided the provenance
records the quantization, so a 4-bit run cannot later be read as a full-precision bf16 one.

## Goals & success metrics

- `PREREGISTRATION.md` § 10.28 (Type 1, 2026-11-23) pins: x202, one GPU, `torch 2.14.1+cu126`,
  the unchanged base/revision, 4-bit NF4 with bf16 compute via `quantize.json`, the measured
  6.75 tokens/s and 6.07 GB, the sample and the GO.
- The sample is § 10.27's 20 private + public **minus the two macOS-only tasks**
  `donor-b-c57246c7841a` and `donor-b-cc7d3f520f1c`: **18 private + the public task = 19 tasks ×
  K = 16 = 304 draws**, `--probe 18`.
- `TorchGenerator.provenance()` records `"quantization"` — `""` with no sidecar, otherwise a
  deterministic compact string (`"nf4/bf16/double"`).
- The x202 operator sheet carries the setup, the 30-link prep root, the probe, `check-probe` and
  the full 52-task night, all guarded by tests.
- No probe, no night, no GPU job and no count in this unit.

## Requirements

### Must-have

1. **§ 10.28.** Append a Type 1 amendment after § 10.27 and a 4-column log row after the § 10.27
   row. It does not edit any existing section. It states the move, the precision and sidecar, the
   two excluded ids and their Darwin reasons, the 304-draw sample, the unchanged K/R/repair/
   verifier/gate/held-out document, the GO, the non-comparability, the MPS series not retired,
   the corpus-removal rule, and that no count is measured and § 3 is unspent.
2. **Provenance.** One new key in `TorchGenerator.provenance()`, built from the declared sidecar
   fields; no loader, sampler, gate or sample-list change.
3. **The sheet.** `docs/planning/pascal-4bit/night-door/runbook.md`: env block (PATH, caches,
   HF home, dynamo/compile disable, mirrors), setup (gcc/g++, `uv sync --extra torch`, cu126
   wheel, `snapshot_download`, sidecar, donor clones), the 30-link near-miss root, `--probe 18`,
   `check-probe --device cuda --precision bfloat16 --probe 18`, and the full-corpus night.
4. **Guards.** `tests/test_pascal_4bit_runbook_guards.py` pins the sheet; `tests/test_docs.py`
   pins § 10.28 and its log row; the provenance tests pin the two sidecar outcomes.
5. **Write-up.** `CHANGELOG.md` Unreleased, `docs/STATUS.md`, and a dated correction in
   `docs/ROADMAP.md` § 14 M1.

### Should-have

- The sheet states that `--precision bfloat16` is the compute dtype while the weights are 4-bit
  NF4, and names the sidecar, so the recorded precision cannot be read as full precision.
- The sheet names the finding's home and the corpus-removal rule.

### Nice-to-have

- A `check-probe` quantization pin. Declined: the provenance key is the record, and `check-probe`
  compares the backend, not the weight format. Adding a pin would be a loader/ledger change.

## Out-of-scope

Running the probe or the night; any GPU job; touching `runs/`; the loader, the sampler, the gate,
the reward, the corpus or the sample lists; the held-out document; `K`, `R`, `R_repair`; retiring
or extending the MPS series; re-measuring any MPS figure.

## Technical considerations

- **The sidecar is already the switch.** `quantization_config()` reads
  `weights/<base>/quantize.json`; `load_weights` accepts it as an extra file beside the 15
  recorded ones. The unit adds no load path.
- **The provenance is the guard against a precision restatement.** `--precision bfloat16` names
  the compute dtype; `"quantization": "nf4/bf16/double"` names the weights. The string is built
  from declared fields, so file key order cannot move it.
- **x202 is a Linux host.** The two Darwin-only tasks cannot be scored there, hence the 18. The
  other 18 are all oracle-fittable and none is held out.

## Acceptance (test-first)

- The provenance tests fail on the missing key before the implementation and pass after; the
  no-sidecar case is `""`; key order does not change the value.
- The runbook guard fails on a missing/stub sheet (wrong `--probe`, dev subset, relative paths,
  worktree, caffeinate, missing exclusions or mirrors) and passes on the real sheet.
- The docs test fails before § 10.28 and passes after; the log row is after § 10.27's.
- `uv run pytest ...`, `ruff` and `mypy` green; no GPU and no run.
