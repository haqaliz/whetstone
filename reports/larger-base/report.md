# The larger-base arm — a new candidate, declared non-comparable

This document reports the larger-base arm: the declared source-B set scored under the same hardened generation contract § 10.4 discloses, with the declared development subset excluded from both sources before anything runs, and with a **new candidate** — a change to the model revision, which is one of the five pinned inputs (`PREREGISTRATION.md:131-132`), and a change to a pinned input invalidates a series and starts a new one (`PREREGISTRATION.md:133-135`). So the arm's figures are a **new series**, declared non-comparable to all three existing homes (`PREREGISTRATION.md` § 10.6): `reports/baseline/` remains the only home of the baseline's figures, `reports/format-hardening/` the only home of the hardened arm's, `reports/easier-stratum/` the only home of the probe's, and this directory the only home of the arm's — neither is a competing home for the same figure.

A figure measured on one side of a changed pinned input may not be compared with one measured on the other.

The arm is a yield test: it measures whether strict-PASS training data exists on the declared set at a larger base. It is not the pinned baseline of `PREREGISTRATION.md:126-128`, which stands unmeasured and may still be measured exactly once, it is not the held-out split of § 7.1, which remains open until P3, and it is not a base-selection closure — it produces evidence only.

**No count is measured here: the arm has not run.** Per-candidate verdict counts, the contract's fields and the arm's token spend are rendered into this directory by the report door after the arm runs. Until then this document holds no figure of its own and restates none from `reports/baseline/`, `reports/format-hardening/` or `reports/easier-stratum/`.

**The candidate.** The arm scores `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` — the candidate the runbook's resolution block names before anything runs. The series statement lives in the runbook and in this directory; this document points at them and never restates a count from either, so the candidate has exactly one home for its figures.

**The breakdowns.** The classifier counts behind these figures live in the gitignored home `runs/larger-base-arm/`; this document points at them and never restates them, so a classifier count has exactly one home.

Recorded on 2026-08-15 (declared by the operator, never read from a clock).