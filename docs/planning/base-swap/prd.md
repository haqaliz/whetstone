# PRD — base-swap (Qwen3-8B)

## Problem

The main Torch/MPS series is pinned to `Qwen/Qwen2.5-Coder-7B-Instruct` (§ 10.20). Its last
valid-partition night produced **613 `NO_DIFF` of 816 private rollouts and zero solved**. The
runtime, the verifier, the gate and the universal PEFT artifact are proven; the base's edit-format
following is the wall.

## Evidence already in hand (2026-10-22)

- `Qwen/Qwen3-8B` @ `b968826d9c46dd6066d109eabc6255188de91218`, Apache-2.0, 8.19B,
  `Qwen3ForCausalLM` — a text-only HF model, so the shipped Torch loader needs no change.
- MPS fit probe: peak **8.96 GB** against the **25.63 GB** headroom (`fits: True`), ~118 s/step.
- Format pre-flight (`torch-8b-probe-001`, 8 private + 1 public × K=16 = 144 draws), rule committed
  before the run: **GO iff ≥4 of the 8 private tasks produce ≥1 non-`NO_DIFF` rollout**.
  Result **GO**: **6 of 8** private tasks produced a real diff. The other two were `NO_ORACLE`
  (oracle budget exceeded on a single large file) and contribute nothing.
  Totals: `NO_DIFF` 74, `NOT_APPLIED` 34, `NO_ORACLE` 32, `NOT_SOLVED` 4, **`SOLVED` 0**.
- A GO is **format conformance only**. It does not claim a solve, a model or a delta.

## What changes

1. `PREREGISTRATION.md` gains **§ 10.21** (Type 1): the main series' base moves to Qwen3-8B at the
   pinned revision. Runtime, device, precision, held-out document, `K = 16`, `R = 3`, corpus,
   verifier and gate are unchanged. § 10.20 is not edited; the 7B Torch/MPS series stays a
   separate, non-retired evidence series and is not extended.
2. The Torch/MPS sheet (`docs/planning/torch-mps-series/night-door/runbook.md`) names the same base
   and revision, and both door commands pass it in `--only`.
3. The sheet and its guard test cite § 10.21 and the 8B revision, so document, sheet and command
   cannot drift.

## Non-goals

- No threshold, no reworded § 1/§ 4/§ 6, no new report home.
- No change to the verifier, the gate, the corpus or the held-out split.
- No proposal PDFs: this is an internal Type 1 pin of an input, decided by a pre-committed rule,
  not a stakeholder-facing feature.
- No claim that the night will select a candidate: the pre-flight solved nothing, so a zero
  strict-PASS yield remains a legitimate published outcome.

## Acceptance

- § 10.21 exists, is Type 1, and carries the base, revision, unchanged inputs, non-comparability
  and "no training has run" statements.
- The amendment log has the § 10.21 row.
- The sheet's two door blocks pass `--only Qwen/Qwen3-8B` exactly once and name the revision.
- `tests/test_docs.py` pins § 10.21 and cross-pins the base/revision against the sheet;
  `tests/test_torch_mps_runbook_guards.py` pins the same candidate and revision.
- The full suite is green before the night is launched.
- The night (`torch-8b-night-001`) is a separate operator run and is not part of this change.
