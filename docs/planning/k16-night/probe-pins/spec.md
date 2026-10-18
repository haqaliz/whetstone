# Spec — probe pins (M2, M3)

**Aspect:** `probe-pins` · **Unit:** `k16-night` · **PRD:** `../prd.md` M2/M3 · **Date:** 2026-10-18

## Purpose

The probe is the night's cheap go/no-go. Today it decides only whether every draw's control arm
is `PASS` and the seed map is non-empty. It does **not** decide that the probe ran the declared
draw budget (`sampling.K`) or excluded the committed held-out split. Both facts are in the probe's
ledger and both are currently checked by an operator's eye on the sheet.

## Required behaviour

### M2 — the declared budget

`check_probe.run_check(run)` compares the ledger's `draws` to `whetstone.loop.sampling.K`,
imported by identity. A mismatch is a **named violation** (`proceed=False`, exit 1), naming the
expected and recorded values. The check never contains a literal `16`.

### M3 — the declared split

`check_probe.run_check(run, heldout=path)` — and `whetstone check-probe --heldout <doc>` — compares
`ledger["task_set"]["heldout"]["document_digest"]` to the digest of the committed document,
computed by `whetstone.loop.heldout.document_digest_of` after the document passes
`heldout.read_document` (both by identity, the same functions the night uses; the data directory
`tasks/heldout/` is not a module path).

- matching digest → no effect on the decision;
- a ledger with no held-out record, or a different digest → **named violation** (exit 1), naming
  both digests (or the absence);
- a `--heldout` path that is unreadable, not JSON, or fails the held-out loader → **refusal**
  (exit 2), because it is an operator error, not a fact about the probe. A named
  `HeldoutUnreadable` is added to `REFUSALS`.

The document is loaded — and therefore refused — **before** the budget violation is reported:
refusals come first, so a mistyped `--heldout` path is exit 2 even when the probe's budget is
also wrong. The two facts are independent; the operator should see the typo rather than a budget
finding that sends them to the wrong place.

The flag is optional at the module level for callers that only want the budget pin, but the night
sheet always passes it; `tests/test_night_runbook_guards.py` holds the sheet.

### The sheet

`docs/planning/p2-rollouts/night-door/runbook.md`'s `check-probe` block gains
`--heldout $REPO/tasks/heldout/source-b.json`. The prose rule is extended to name the budget and
the digest; the existing rule (control `PASS` every draw, non-empty seed map) is unchanged.

## Non-goals

- No change to the ledger schema, the night's own held-out handling, or the held-out document.
- No change to the gate, the reward path, or the corpus.
- The pin only **tightens** the pre-committed rule; it never loosens it and never adds a new way
  to proceed.

## Acceptance

- A probe at `draws == K` proceeds; a probe at `K - 1` is a named violation naming both values.
- `--heldout` with a matching digest proceeds; a mismatched digest and a missing record are named
  violations; an unreadable document is a refusal.
- The sheet's check-probe block passes `--heldout $REPO/tasks/heldout/source-b.json`, and a guard
  fails if the flag is dropped.
- All tests are watched failing against the current code/the old sheet.
