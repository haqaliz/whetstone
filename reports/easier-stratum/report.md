# The easier-stratum probe — a changed task set, declared non-comparable

This document reports the easier-stratum probe: the declared source-B set scored under the hardened generation contract § 10.4 discloses, restricted to the pre-committed difficulty stratum declared in the stratum document this report points at below. The stratum's tasks are a **different task set** than the one either existing home measured, and the task set is one of the five pinned inputs (`PREREGISTRATION.md:131-132`) — a change to a pinned input invalidates a series and starts a new one (`PREREGISTRATION.md:133-135`) — so the probe's figures are a **new series**, declared non-comparable to both existing homes (`PREREGISTRATION.md` § 10.5): `reports/baseline/` remains the only home of the baseline's figures, `reports/format-hardening/` the only home of the hardened arm's, and this directory the only home of the probe's — neither is a competing home for the same figure.

A figure measured on one side of a changed pinned input may not be compared with one measured on the other.

The probe is a yield test: it measures whether strict-PASS training data exists on the stratum. It is not the pinned baseline of `PREREGISTRATION.md:126-128`, which stands unmeasured and may still be measured exactly once, and it is not the held-out split of § 7.1, which remains open until P3.

**No count is measured here: the probe has not run.** Per-candidate verdict counts, the contract's fields and the probe's token spend are rendered into this directory by the report door after the probe runs. Until then this document holds no figure of its own and restates none from `reports/baseline/` or `reports/format-hardening/`.

**The stratum document.** The pre-committed difficulty stratum this probe scores is declared in `tasks/stratum/easier.json` — its rule digest and its membership — and the probe's runbook names it before anything runs. This document points at it and never restates a count from it, so the stratum's membership has exactly one home.

**The breakdowns.** The classifier counts behind these figures live in the gitignored home `runs/easier-stratum-arm/`; this document points at them and never restates them, so a classifier count has exactly one home.

Recorded on 2026-08-14 (declared by the operator, never read from a clock).