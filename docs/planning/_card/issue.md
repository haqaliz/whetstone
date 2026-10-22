# feat base-swap — Qwen3-8B

**Source:** inline brief, from the 2026-10-22 base research and the 7B wall. Branch
`feat/base-swap/aliz` (created 2026-10-22), worktree `.claude/worktrees/feat-base-swap`.

## Why this base

The 7B (`Qwen/Qwen2.5-Coder-7B-Instruct`) produced **613 `NO_DIFF` of 816** private rollouts and
**zero solved** in its last valid-partition observation; the runtime and the universal PEFT
artifact are proven. The failure is the base's edit-format following, not the harness.

`Qwen/Qwen3-8B` @ `b968826d9c46dd6066d109eabc6255188de91218`, Apache-2.0, `Qwen3ForCausalLM`,
8.19B. It is a text-only HF model, so the existing Torch loader works unchanged. The MPS fit
probe passed: **peak 8.96 GB** against the 25.63 GB headroom (`fits: True`), ~118 s/step. It was
not present on the Mac, x131 (only the 0.5B; unreachable earlier, and 15 GB/no GPU), or x118
(empty); it was fetched to the primary `weights/` on 2026-10-22.

## The format pre-flight — rule committed before the probe

Run `whetstone run --night --probe 8` on the 8B: the first 8 private tasks after the dev/held-out
exclusion, plus the one public task, at `K = 16` (9 tasks × 16 = 144 rollouts). It writes no
checkpoint; the journals are the evidence.

**GO iff at least 4 of the 8 private probe tasks have at least one rollout whose outcome is not
`NO_DIFF` across their 16 draws.** `NO-GO` otherwise.

- The threshold is **format conformance**, not yield: a GO says the base produces a diff at all;
  it claims no solve, no model and no delta.
- The 8 private tasks are source B (the headline); the public task's outcome is reported beside.
- A task with zero non-`NO_DIFF` rollouts contributes nothing to the count, even if its
  `NO_DIFF` rollouts are well-formed prose.
- On `NO-GO`, the next candidates are Qwen3.5-9B (needs a multimodal loader change) or
  Qwen3-Coder-30B-A3B 4-bit (needs QLoRA support); do **not** run a night on the 8B.

## If GO

The unit becomes: the Type 1 § 10.21 amendment pinning Qwen3-8B (runtime/device/precision
unchanged, held-out/K/R unchanged, non-comparable to the 7B and MLX series), the Torch/MPS sheet's
`--only` and model/revision, the night, `check-leakage`, the gate vs the untrained 8B, `card`/
`fuse`, and the finding. A zero at the night is still a valid outcome.

## Acceptance (the unit)

1. The pre-flight rule is committed before the probe; the partition is read from the journals and
   the GO/NO-GO is stated with its counts.
2. On GO: § 10.21 pins the base/revision; the sheet and its guard name the 8B; the night writes a
   ledger and, if it selects, a sealed Torch/MPS PEFT checkpoint.
3. On GO and a checkpoint: `check-leakage` exit 0; the gate returns one of its three exits; the
   finding and the universal artifact.
4. On NO-GO: a finding records the partition and the candidate rejection; no night, no checkpoint,
   no number.
