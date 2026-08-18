# The larger-base arm — a new candidate, declared non-comparable

This document reports the larger-base arm: the declared source-B set scored under the same hardened generation contract § 10.4 discloses, with the declared development subset excluded from both sources before anything runs, and with a **new candidate** — a change to the model revision, which is one of the five pinned inputs (`PREREGISTRATION.md:131-132`), and a change to a pinned input invalidates a series and starts a new one (`PREREGISTRATION.md:133-135`). So the arm's figures are a **new series**, declared non-comparable to all three existing homes (`PREREGISTRATION.md` § 10.6): `reports/baseline/` remains the only home of the baseline's figures, `reports/format-hardening/` the only home of the hardened arm's, `reports/easier-stratum/` the only home of the probe's, and this directory the only home of the arm's — neither is a competing home for the same figure.

A figure measured on one side of a changed pinned input may not be compared with one measured on the other.

The arm is a yield test: it measures whether strict-PASS training data exists on the declared set at a larger base. It is not the pinned baseline of `PREREGISTRATION.md:126-128`, which stands unmeasured and may still be measured exactly once, it is not the held-out split of § 7.1, which remains open until P3, and it is not a base-selection closure — it produces evidence only.

## The candidate

**The contract.** template SHA-256 `f5d431a1fe2cebd6089a9408a4f5bb9a7060f2c38645e766ad7a2ebb540c5cc9`; sampler greedy: argmax over the final logprob axis (mx.argmax(logprobs, axis=-1)); token budget 1024; extractor version extract_patch@3e91bab8c123; retrieval oracle; development subset `belay-2e149603209a`, `belay-353359e9ac6e`, `belay-3e3051c4192a`, `belay-844db07ed482`, `belay-9dba3ea557f5`; retry budget 2; retry template SHA-256 `0ce3496235180696d715740fc517c05ed9c30f5ceb7a6c625e854a106bac7a2b`; diagnosis vocabulary version `4b5022c093b6cd7708dfff99840964c7617066f1f8e8669003a9c0d954ee91fd`.

| Figure | `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` |
|---|---|
| `solved` | 1 of 62 |
| `coverage` | 49 of 62 |
| `unverified` | 13 of 62 |
| `N` | 0 of 62 |
| `no diff` | 0 of 62 |
| `patch apply` | 37 of 62 |
| `patch scope` | 0 of 62 |
| `not solved` | 11 of 62 |

These counts are stated under the contract's fields above: a count and the contract that produced it belong together. `N` is the harness's own WEAK-PASS/STRICT-FAIL differential (`PREREGISTRATION.md:96-100`). The `N of M` cells are counted over the arm's own denominator — the harness's per-candidate denominator, which for a complete arm equals the declared source-B set less the dev-subset exclusions — 61 private + 1 public = 62 per candidate. The excluded ids are the declared development subset (`belay-2e149603209a`, `belay-353359e9ac6e`, `belay-3e3051c4192a`, `belay-844db07ed482`, `belay-9dba3ea557f5`).

**Token spend.** Generation 16002.9 seconds, summed over the arm's rollouts from the run's own cost records.

**The candidate.** The arm scores `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` — the candidate the runbook's resolution block names before anything runs. The series statement lives in the runbook and in this directory; this document points at them and never restates a count from either, so the candidate has exactly one home for its figures.

**The breakdowns.** The classifier counts behind these figures live in the gitignored home `runs/larger-base-preanalysis/comparison.md`; this document points at them and never restates them, so a classifier count has exactly one home.

Recorded on 2026-08-18 (declared by the operator, never read from a clock).