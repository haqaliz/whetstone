# Format-hardening arm — two generation contracts, declared non-comparable

This document reports the format-hardening arm: the declared source-B set scored under a hardened generation contract — the retry-augmented contract — beside the arm that ran the baseline contract. The two directories measure different generation contracts and are declared non-comparable (`PREREGISTRATION.md` § 10.4): `reports/baseline/` remains the only home of the baseline's figures, and this directory is the only home of the hardened arm's — neither is a competing home for the same figure.

A figure measured on one side of a changed pinned input may not be compared with one measured on the other.

## Arm: baseline

**The contract.** template SHA-256 `b7d6d3d4052db5e95a4e8eaa65d2728176406c580e260c4b637442ff333cd1ae`; sampler greedy: argmax over the final logprob axis (mx.argmax(logprobs, axis=-1)); token budget 1024; extractor version extract_patch@3e91bab8c123; retrieval oracle; development subset `belay-0cfbb1590a70`, `belay-0f8651175ef8`, `belay-0fe4582aeac1`.

| Figure | `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` | `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit` | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` |
|---|---|---|---|
| `solved` | 0 of 64 | 0 of 64 | 0 of 64 |
| `coverage` | 52 of 64 | 51 of 64 | 52 of 64 |
| `unverified` | 12 of 64 | 13 of 64 | 12 of 64 |
| `N` | 0 of 64 | 0 of 64 | 0 of 64 |
| `no diff` | 0 of 64 | 1 of 64 | 43 of 64 |
| `patch apply` | 43 of 64 | 50 of 64 | 8 of 64 |
| `patch scope` | 0 of 64 | 0 of 64 | 0 of 64 |
| `not solved` | 9 of 64 | 0 of 64 | 1 of 64 |

These counts are stated under this arm's own contract fields above: a count and the contract that produced it belong together.

**Token spend.** Generation 5320.2 seconds, summed over this arm's runs from the run's own cost records.

## Arm: hardened

**The contract.** template SHA-256 `f5d431a1fe2cebd6089a9408a4f5bb9a7060f2c38645e766ad7a2ebb540c5cc9`; sampler greedy: argmax over the final logprob axis (mx.argmax(logprobs, axis=-1)); token budget 1024; extractor version extract_patch@3e91bab8c123; retrieval oracle; development subset `belay-2e149603209a`, `belay-353359e9ac6e`, `belay-3e3051c4192a`, `belay-844db07ed482`, `belay-9dba3ea557f5`; retry budget 2; retry template SHA-256 `0ce3496235180696d715740fc517c05ed9c30f5ceb7a6c625e854a106bac7a2b`; diagnosis vocabulary version `4b5022c093b6cd7708dfff99840964c7617066f1f8e8669003a9c0d954ee91fd`.

| Figure | `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` | `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit` | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` |
|---|---|---|---|
| `solved` | 0 of 62 | 0 of 62 | 0 of 62 |
| `coverage` | 49 of 62 | 50 of 62 | 50 of 62 |
| `unverified` | 13 of 62 | 12 of 62 | 12 of 62 |
| `N` | 0 of 62 | 0 of 62 | 0 of 62 |
| `no diff` | 5 of 62 | 12 of 62 | 41 of 62 |
| `patch apply` | 31 of 62 | 38 of 62 | 8 of 62 |
| `patch scope` | 0 of 62 | 0 of 62 | 0 of 62 |
| `not solved` | 13 of 62 | 0 of 62 | 1 of 62 |

These counts are stated under this arm's own contract fields above: a count and the contract that produced it belong together.

**Token spend.** Generation 16693.1 seconds, summed over this arm's runs from the run's own cost records.

**The breakdowns.** The classifier counts behind these figures live in the gitignored home `runs/format-hardening-preanalysis/comparison.md`; this document points at them and never restates them, so a classifier count has exactly one home.

Recorded on 2026-08-12 (declared by the operator, never read from a clock).