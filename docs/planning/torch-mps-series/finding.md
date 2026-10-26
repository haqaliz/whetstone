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

## The 14B NF4 pre-flight — 2026-10-24

`torch-14b-probe-001` (Qwen3-14B, NF4 through `bitsandbytes` 0.50.2, torch 2.14.1, `--probe 8`)
produced **7 draws, all `NO_DIFF`**, at about 9 minutes per draw, then hung on the eighth: no
journal write for 64+ minutes, process state uninterruptible (`U+`), and a `sample` showing the
same `_local_scalar_dense_mps` path as the 8B crash (#86). The 900 s draw timeout could not fire.
The 4-bit path is unusable on this machine regardless of its format; § 10.22's series is **not
extended**, and no night was run under it. The fit had passed (17.67 GB peak against the 25.6 GB
headroom); the failure is the runtime, not the memory.

## The repair arm — 2026-10-25/26

§ 10.23 returns the main series to the 8B with a bounded repair contract (`R_repair = 2`): after a
patch applies and the tests fail, the run re-asks with a pre-posed repair prompt that carries the
verdict and **not** the test output. The probe rule, committed before the probe: **GO iff at least
one of the 144 probe draws is strict-`PASS`**.

Two probe launches (`torch-8b-repair-probe-001`, `-002`) voided on a harness defect: the repair
generation re-entered the completion-retry wrapper and asked for a nested retry prompt the freeze
had never posed; `Sealed` raised `ContractChanged` and stopped the runs (41 and 26 draws). Both are
quarantined and produced no result. The fix (#92, #93) makes the repair one attempt, through both
wrapper layers, and is pinned by a `Draw → Retry` composition test — the shape `score()` actually
sees. `torch-8b-repair-probe-003` is the measurement; its result is recorded here when it returns.
