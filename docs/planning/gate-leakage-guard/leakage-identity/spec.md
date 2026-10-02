# Spec — leakage-identity

**Core loop element:** ③. **Slice:** `check-leakage` matches by sha12 and accepts a ledger-free run.

## In scope
- Identity extraction from a task id (trailing 12 hex), per source; unrecognisable id → refusal.
- Run input accepted with `dataset.json` alone, with a stated notice.

## Out of scope
- Corpus loading, repo/commit comparison; any change to exit-code meaning.

## Acceptance criteria (tests first)
1. Disjoint sha12 sets exit 0.
2. **Adversarial:** a training id `legacy-a-X` against held-out `donor-a-X` exits 1 and names both
   ids. The same fixture exits 0 under the pre-change exact-string comparison (pinned in the test).
3. A training id without a trailing sha12 exits 2.
4. A run with `dataset.json` and no `ledger.json` is checked, with the notice printed; a run with
   neither exits 2.
5. Same sha12 in different sources is not an overlap.
6. Regression fixture mirroring night-001's real shape (4+1+1 examples over three tasks, one
   held out) exits 1.

## Open questions
- Exact output wording for the notice; follow `check_leakage.py` conventions.

## Amendments after the review gate
- AC3's refusal message names the re-mint cause and the need for an amendment.
- The output states the residual: "no shared task identity" is not "no contamination".

## Amendment 2 (2026-10-03, user-approved)
- AC7: a source-A-only training set (no source B example) exits 2 with a refusal stating that
  nothing was compared; it never exits 0. A training set with zero examples remains exit 0.
