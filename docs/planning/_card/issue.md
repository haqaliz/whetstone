# Card — p3-promotion-gate

## Brief

Build P3 — the never-regress promotion gate (`docs/ROADMAP.md` § 4, P3): `whetstone gate
--candidate X --incumbent Y` returns exactly one of `promoted` / `rejected` / `UNVERIFIED`,
plus `whetstone check-leakage` (zero overlap between the training set and the held-out set),
and the unverified rate appears in every eval's output. Port the sibling project's coverage
rule (ROADMAP § 7, `corpus/metrics.py`) with `UNVERIFIED` kept in the denominator, never
dropped.

Acceptance criteria, written first (repo is test-first):

1. The three-exit differential, on fixtures: known-better → `promoted`; known-worse →
   `rejected`; deliberately incomplete eval → `UNVERIFIED` and **not** promoted.
2. Deterministic retry discipline: each unverified task retries a fixed `R` times with
   identical seed and inputs; a task that verifies on retry is verified.
3. Coverage-reporting liveness rule: coverage drops, tasks never vanish from the
   denominator; if any task is still unverified after `R` retries the whole evaluation
   reduces to `UNVERIFIED` — not `promoted`, and not `rejected` either.
4. `whetstone check-leakage` exits 0 — zero overlap between the training set and the
   held-out set.

Caveats the dig must meet: `PREREGISTRATION.md` § 7.1 (held-out split size and
stratification) and § 7.2 (retry count `R`) both close **in P3, by dated amendment
committed before the measurement they govern runs** — the held-out split design and the `R`
mechanism are part of this unit's scope, not an afterthought. No real candidate/incumbent
checkpoint pair has ever existed (the night has not run), so the gate's liveness is tested on
fixture checkpoints; the loop's checkpoint hashing (`loop/sft.py` `verify_checkpoint`,
`loop/night.py:436`) exists precisely so the gate can re-hash and compare the bytes it
compares. The reward path (`src/whetstone/verify/`, `tasks/`, `patch.py`, `attribution.py`)
must stay byte-untouched.

## Source

Inline brief (no GitHub issue — slug id, `feat p3-promotion-gate`), handed off from the
`whetstone-next` session (2026-08-24).
