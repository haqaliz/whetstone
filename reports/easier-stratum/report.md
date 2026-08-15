# The easier-stratum probe — a changed task set, declared non-comparable

This document reports the easier-stratum probe: the declared source-B set scored under the hardened generation contract § 10.4 discloses, restricted to the pre-committed difficulty stratum declared in the stratum document this report points at below. The stratum's tasks are a **different task set** than the one either existing home measured, and the task set is one of the five pinned inputs (`PREREGISTRATION.md:131-132`) — a change to a pinned input invalidates a series and starts a new one (`PREREGISTRATION.md:133-135`) — so the probe's figures are a **new series**, declared non-comparable to both existing homes (`PREREGISTRATION.md` § 10.5): `reports/baseline/` remains the only home of the baseline's figures, `reports/format-hardening/` the only home of the hardened arm's, and this directory the only home of the probe's — neither is a competing home for the same figure.

A figure measured on one side of a changed pinned input may not be compared with one measured on the other.

The probe is a yield test: it measures whether strict-PASS training data exists on the stratum. It is not the pinned baseline of `PREREGISTRATION.md:126-128`, which stands unmeasured and may still be measured exactly once, and it is not the held-out split of § 7.1, which remains open until P3.

## The stratum

**The contract.** template SHA-256 `f81e95f6085140a3523ac207126c4f9f879a015df203d5f3de5c994414af48dc`; sampler greedy: argmax over the final logprob axis (mx.argmax(logprobs, axis=-1)); token budget 1024; extractor version extract_patch@3e91bab8c123; retrieval oracle; development subset none declared; retry budget 2; retry template SHA-256 `0ce3496235180696d715740fc517c05ed9c30f5ceb7a6c625e854a106bac7a2b`; diagnosis vocabulary version `4b5022c093b6cd7708dfff99840964c7617066f1f8e8669003a9c0d954ee91fd`.

| Figure | `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` | `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit` |
|---|---|---|
| `solved` | 0 of 20 | 0 of 20 |
| `coverage` | 16 of 20 | 17 of 20 |
| `unverified` | 4 of 20 | 3 of 20 |
| `N` | 0 of 20 | 0 of 20 |
| `no diff` | 0 of 20 | 2 of 20 |
| `patch apply` | 10 of 20 | 15 of 20 |
| `patch scope` | 0 of 20 | 0 of 20 |
| `not solved` | 6 of 20 | 0 of 20 |

These counts are stated under the contract's fields above: a count and the contract that produced it belong together. `N` is the harness's own WEAK-PASS/STRICT-FAIL differential (`PREREGISTRATION.md:96-100`). The `N of M` cells are counted over the probe's own denominator — the harness's per-candidate denominator, which for a complete probe equals the stratum's declared size less the dev-subset exclusions. The stratum document's declared membership is pointed at below, never restated.

**Token spend.** Generation 2808.4 seconds, summed over the probe's rollouts from the run's own cost records.

**The stratum document.** The pre-committed difficulty stratum this probe scores is declared in `/Users/aliz/dev/at/whetstone/tasks/stratum/easier.json` — its rule digest and its membership — and the probe's runbook names it before anything runs. This document points at it and never restates a count from it, so the stratum's membership has exactly one home.

**The breakdowns.** The classifier counts behind these figures live in the gitignored home `runs/easier-stratum-preanalysis/comparison.md`; this document points at them and never restates them, so a classifier count has exactly one home.

Recorded on 2026-08-15 (declared by the operator, never read from a clock).