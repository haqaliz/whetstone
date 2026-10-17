# Spec — `declaration` (raise-k)

**Aspect:** the constant moves and is pinned; the budget stays a non-flag; the budget reaches
the evidence without becoming a gate comparability key.
**Source:** `docs/planning/raise-k/prd.md` (M1–M4, AC1–AC4).

## Problem slice

`sampling.K = 8` (`src/whetstone/loop/sampling.py:79`) is the loop's declared draw budget. It
moves to `16`. Downstream, three properties must hold and none may drift: the value is pinned
by a test; the `run --night` door still exposes no way to set the budget; the budget is
recorded in the ledger by identity; and the budget is **not** a gate comparability key.

## In scope

- Change `K` to `16`.
- Pin the exact value in `tests/loop/test_sampling.py`.
- Widen the no-flag guard to refuse **any** budget option on the `run` parser (`--k` today,
  `--draws` newly).
- Assert the night's recorded `Ledger.draws` is `K` for a night with no override.
- Assert `draws`/`K` is absent from the `Backend` record, and that a candidate/incumbent pair
  differing only in draw budget is not refused by the gate's backend comparison.

## Out of scope

- The night, the run ledger's schema (no bump), `verify/`, `tasks/`, the held-out document,
  the gate's rule, `TEMPERATURE`/`TOP_P`/the sampler shape.

## Acceptance criteria (testable, watched failing first)

- **AC1.1** `sampling.K == 16` (exact int), failing against `8`.
- **AC1.2** The existing `K` guard's `isinstance(K, int) and K >= 2` and `run_night`'s
  `draws` default `is K` assertions are retained.
- **AC1.3** `_cli_flags()` for the `run` subparser contains neither `--k` nor `--draws`; the
  test is watched failing against a planted `--draws` on `build_parser()`.
- **AC1.4** A night that passes no `draws` override records `Ledger.draws == sampling.K`.
- **AC1.5** `"draws" not in Backend(...).recorded()` (and no `K`/`k` key); the gate's
  `refuse_cross_backend` does not raise for a pair whose `Backend`s differ only in a
  hypothetical draw-budget field (i.e. the shipped `Backend` has no such field to differ on).

## Dependencies / sequencing

First aspect. `amendment` depends on this (it pins the constant by name).

## Open questions / risks

- AC1.4 may collapse into the existing default-`is`-`K` assertion plus `ledger.py:403`; the
  plan states the exact assertion to add so it is a real RED.
- The `--draws` widening must be scoped to the `run` subparser (the probe narrows draws
  internally at `ledger.py:226`, never via a CLI flag).
