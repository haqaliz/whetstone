# Finding — the Torch/MPS series on Qwen3-8B

**Run:** `torch-8b-night-001` · `recorded-on` 2026-10-22 · seed `20261022` · base
`Qwen/Qwen3-8B` @ `b968826d9c46dd6066d109eabc6255188de91218` (`PREREGISTRATION.md` § 10.21) ·
runtime Torch/MPS, `float16`.

This is the first night under § 10.21. It draws the 51 private source-B tasks and the one public
task at `K = 16`.

## The result

**51 private tasks × 16 = 816 draws. Zero strict-`PASS`.**

| outcome | draws |
|---|---|
| `NO_DIFF` | 416 |
| `NOT_APPLIED` | 155 |
| `NOT_SOLVED` | 51 |
| `NO_ORACLE` | 192 |
| `UNVERIFIED` | 2 |
| **`SOLVED`** | **0** |

- **All 39 evaluable private tasks produced at least one real diff** — a patch was extracted
  (`NOT_APPLIED` or `NOT_SOLVED`). The 8B clears the format wall the 7B did not: the 7B produced 10
  diffs in 816 draws; the 8B produced **206 in 624 evaluable draws** (~33%).
- **None passed the strict verifier.** 51 patches applied and failed their tests; 155 were refused
  by git; 416 outputs were prose.
- The 12 `NO_ORACLE` tasks (192 draws) exceed the 80,000-character oracle budget and produced no
  model output. They are excluded from the evaluable count, never counted as failures.
- The public task reached 7 of its 16 draws and then the harness failed (below). It is
  supplementary and is not part of the source-B count.

## No candidate

Zero strict-`PASS` means no training set: the night wrote **no checkpoint**, no dataset and no
model card. There is nothing to gate, fuse or publish. This is the pre-registered zero outcome
(§ 10.20/§ 10.21: a zero is legitimate), not a crash artefact — the 816 private draws completed
before the harness failure.

## The harness failure — a defect, not a result about the base

After ~35 h the process hit an MPS out-of-memory
(`kIOGPUCommandBufferCallbackErrorOutOfMemory`) on the public task and hung. A resume with the same
command, run id and seed replayed the completed pairs and then failed on the same public draw with a
corrupted attention mask:

```
torch.AcceleratorError: index 72340172838076673 is out of bounds for dimension with size 151936
  transformers/masking_utils.py:268 in _ignore_causal_mask_sdpa
```

A second resume hung at the same point (823/832, 0% CPU, no timeout firing).

Consequences:

- The run did **not** write `ledger.json`. The night is sealed only by its per-draw journals under
  `runs/torch-mps/torch-8b-night-001/draws/` (gitignored).
- The private 816 draws are complete; the public task is 7/16.
- **The defect must be fixed before any next night**: the long-run MPS memory growth and the public
  task's mask path. Neither is evidence about the base, and neither is a reason to change a
  success rule.

## What this does and does not say

- It says the 8B follows the edit format far better than the 7B, and still does not solve this
  corpus at `K = 16`. On 624 evaluable draws with zero solves, raising `K` alone is not supported.
- It does **not** claim a model, a delta or a gate decision. Nothing was promoted.
- The next lever is a base or approach change, decided in a new amendment: Qwen3.5-9B (needs a
  multimodal loader), Qwen3-Coder-30B-A3B 4-bit (needs QLoRA), or a different sampling/repair
  strategy. The MPS defect is a separate bug and is fixed first.

Raw counts and the per-draw journals stay in the gitignored `runs/` store; this finding is the
planning record.
