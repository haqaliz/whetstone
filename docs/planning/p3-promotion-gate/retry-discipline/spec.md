# Spec — retry-discipline (aspect 4 of p3-promotion-gate)

**PRD:** `../prd.md`. **Branch:** `feat/p3-promotion-gate/aliz`. This aspect ships the gate's
liveness mechanism — the deterministic retry of unverified tasks — and the § 7.2 Type 1 amendment
that closes the retry count `R`.

## Problem slice and user outcome

`unverified == 0` is the honest term in the gate rule, but transient failures (flaky test, sandbox
timeout, disk pressure) make it nonzero on most real evals, and a gate demanding exactly zero would
never fire (`docs/ROADMAP.md:429-443`). The user outcome: each unverified task retries a fixed `R`
times with identical seed and inputs, a task that verifies on retry is verified, and `R` is a
declared constant — never a CLI knob — closed by the § 7.2 amendment.

## In-scope requirements

1. **The mechanism.** `RETRY_COUNT = 3` — a declared constant in the gate module (aspect 3), never
   a flag. Each held-out task whose verification produced no verdict retries up to `R` times with
   **identical seed and inputs**: the run's recorded per-attempt seed replayed against the same
   held-out checkout (the same task manifest and reference state — a retry on a different checkout
   is a different experiment). A task that verifies on retry is verified; a task still unverified
   after `R` retries keeps the eval `UNVERIFIED` through `verdict.reduce` (item 3 of gate liveness:
   the whole evaluation reduces to `UNVERIFIED` — not promoted, not rejected).
2. **Recording.** The retry outcome is recorded in the promotion record: retries used per task,
   the retry count `R` that governed, and the final unverified set. The unverified rate is reported
   from the first eval onward (`docs/ROADMAP.md:441-442`) — the gate's output always carries it,
   fixture evals included.
3. **Determinism.** The retry sequence is deterministic given the seed and inputs: same seed → same
   retry sequence, asserted by a test (the night's cross-process determinism precedent).
4. **The § 7.2 Type 1 amendment.** A dated entry in `PREREGISTRATION.md` § 10 closing § 7.2 under
   § 8.1 (Type 1), committed as its own change, before the first gated evaluation. It states
   `R = 3` declared a priori ("to be set from the observed unverified rate rather than guessed" —
   with no observed rate yet, the value is declared and the revision path is a further amendment
   grounded in a measured rate, never a code edit alone). No proportion in any spelling; nothing
   above § 10 edited; `tests/test_docs.py` stays green.
5. **Adversarial proof.** A deliberately credulous retry (one that retries a FAIL as if it might
   become PASS, or retries with a changed seed) is proven to lose the differential: the gate must
   never convert a FAIL into a win — retries apply only to *no-verdict* outcomes, never to FAIL,
   and a retried FAIL stays FAIL.

## Out-of-scope boundaries

- No change to the generation-contract retry (`bakeoff/retry.py`) — that is a different mechanism
  with a different purpose; this is the verification retry.
- No `--retry R` CLI flag (the PRD declines it: a CLI override makes the amendment meaningless).
- No change to `src/whetstone/verify/`, `src/whetstone/tasks/`, `patch.py`, `attribution.py`.

## Acceptance criteria (testable)

- AC1: a fixture task that verifies only on its second attempt is verified after the retry and the
  eval proceeds (promoted/rejected per the rule).
- AC2: a task unverified after `R` retries makes the whole eval `UNVERIFIED` — not promoted, not
  rejected — and the retry count used is recorded.
- AC3: a FAIL is never retried into a win; retries fire only on no-verdict outcomes (the credulous
  retry loses the differential, watched failing first).
- AC4: same seed → same retry sequence, asserted.
- AC5: the § 7.2 Type 1 amendment is in `PREREGISTRATION.md` § 10, dated, recorded in the log with
  type "1 — closes an open item", and `tests/test_docs.py` stays green with it in place.
- AC6: `uv run pytest` green; ruff and mypy over `src/` green.

## Dependencies and sequencing

- Depends on aspect 3's scoring seam (the retry wraps per-task verification within the gate).
- Sequence: the seam contract → the retry wrapper + determinism test → the recording fields →
  the credulous-retry adversarial test → the § 7.2 amendment.
- Feeds: `gate-core`'s decision path, `gate-runbook`'s liveness statement.

## Open questions / risks

- `R = 3` is a priori by necessity (no observed rate exists; the larger-base finding reported the
  rate qualitatively). If the real unverified rate is high, the revision path must be exercised —
  a measured-rate amendment, stated in the runbook so the operator knows the mechanism before the
  first real eval.
- "Identical inputs" must pin the checkout per retry; the plan must define how the held-out
  checkout is reused (the same sandboxed checkout, or a byte-identical clone) and assert it.