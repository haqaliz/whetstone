# Understanding — pascal-4bit

**Unit:** `pascal-4bit` · **Written:** 2026-11-23 · **Source:** inline brief, after the x202
pre-flight and § 10.27's near-miss sample.

## What the work is really asking

The main series must run on the founder's own host `x202`, because that is where the private
corpus lives and where the series is expected to continue. The host is Pascal: 3× NVIDIA GTX 1080
8 GB, only GPU 0 used. It has no native bf16, and the pinned `torch 2.14.1+cu130` has no kernels
for `sm_61`. As pinned, the series cannot draw there at all.

The brief carries two measured facts from x202:

| Measurement | Value |
|---|---|
| `torch 2.14.1+cu126` on the GTX 1080 | fp32/fp16/bf16 run; same torch version, different CUDA build |
| `Qwen/Qwen3-8B` at `b968826d…` in 4-bit NF4, bf16 compute | 6.07 GB VRAM of 7.92 GiB, **6.75 new tokens/s** (64 tokens in 9.5 s) |

The 4-bit load uses the existing `quantize.json` sidecar path: `TorchGenerator` already reads
`weights/<base>/quantize.json`, and `whetstone.bakeoff.weights.load_weights` accepts the sidecar as
an extra file beside the 15 recorded ones. **No loader change is needed.** The unit's `src/` change
is only the provenance key: without it, a 4-bit run records `--precision bfloat16` and can be read
as full-precision bf16.

## The precision, stated once

`--precision bfloat16` is the **compute dtype**. The weights are **4-bit NF4**, declared by the
sidecar:

```json
{"bnb_4bit_quant_type": "nf4", "bnb_4bit_compute_dtype": "bfloat16", "bnb_4bit_use_double_quant": true}
```

`TorchGenerator.provenance()` will record `"quantization": "nf4/bf16/double"` for this base, and
`""` for the 8B base without a sidecar. The value is built from the declared fields, never from
the file's bytes, so key order cannot move it.

## The sample and why it is 18, not 20

§ 10.27 named 20 private tasks with a `NOT_SOLVED` in `torch-8b-night-001`, plus
`pallets__flask-4045`. Two of the 20 cannot be scored on Linux:

- `donor-b-c57246c7841a` — **3 of its 5 declared tests are `@darwin_only`** in
  `tests/test_replay_batch_server_rooting.py`.
- `donor-b-cc7d3f520f1c` — `pytestmark = pytest.mark.skipif(sys.platform != "darwin", ...)` in
  `tests/test_verify_cli.py`.

They remain in the corpus and in § 10.27. This probe's sample excludes them by id, leaving
**18 private + the public task = 19 tasks × K = 16 = 304 draws**, `--probe 18`.

The near-miss root carries **30 links = 18 sample + 12 held-out**, because the committed held-out
document must match a loaded task or the door refuses a split that excludes nothing. The exclusion
runs before the probe draws; the 12 are loaded and excluded, never drawn.

## Current mechanism

- `whetstone run --night --probe N` narrows the loaded private set after the dev overlay and the
  held-out exclusion. A training-only root of symlinks is the existing way to select ids.
- `check-probe --probe N` pins the ledger's declared sample size; `--runtime torch --device cuda
  --precision bfloat16` pins the backend. `check-probe` exit 0 is the **harness rule**, not the GO.
- § 10.28's GO is unchanged: at least one of the 304 draws is strict-`PASS`.

## Core-loop placement

**② the nightly improvement loop's evidence.** The reward (①), the gate (③) and the report (④)
are untouched. No loader, sampler, gate, corpus, held-out, `K`, `R` or `R_repair` change.

## Contradictions surfaced

- **The series' pinned CUDA build cannot run on its own host.** `cu130` has no `sm_61` kernels;
  the same torch version at `cu126` does. The amendment changes the CUDA build, not the version
  or the base, and says so.
- **The recorded precision is not the weight precision.** The backend records
  `precision=bfloat16`; the weights are 4-bit. The provenance key is the correction, not a new
  backend field.
- **The two macOS-only tasks are in § 10.27 but not scoreable here.** The amendment excludes them
  by id and keeps § 10.27 intact; it does not reword the earlier section.

## What is explicitly not claimed

No probe or night has run. No count, yield, delta or model exists. The MPS series is not retired
and its figures are not restated; every figure here is non-comparable to MPS and to a
full-precision bf16 CUDA figure. The § 3 baseline remains unspent.

## Operator boundary

The private corpus runs on the founder's own x202, and every file added there is removed after the
measurement. The sheet is `docs/planning/pascal-4bit/night-door/runbook.md`; the finding's home is
`docs/planning/pascal-4bit/finding.md`. No `reports/` directory is created.
