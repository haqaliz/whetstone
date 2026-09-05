# Spec — check-core

**Unit:** `probe-decision-gate` · **Aspect:** `check-core` · **Date:** 2026-09-05
**Source:** `docs/planning/probe-decision-gate/prd.md` (requirements 1-6, 8-9; risks).

## Problem slice and user outcome

The module that turns the pre-committed probe decision rule into a deterministic answer:
`src/whetstone/loop/check_probe.py` reads **one** probe run directory and returns a
`ProbeReport` — `proceed` iff (a) every draw's control fold is `PASS` and (b) the recorded
seed map is non-empty — else a named violation. Modeled on `check_leakage.py`: a pure,
read-only, inference-free decision over documents; refusals by name; nothing runs, nothing is
generated, nothing is published.

## In-scope requirements

- `run_check(run: Path) -> ProbeReport` — the decision, as a pure function of one run directory.
- `ProbeReport` — `proceed: bool`, `violation: str | None`, and the counts the decision was
  read from (`draws`, `draws_recorded`, `sources`, `probe`, `seeds`).
- `disclosure(report) -> tuple[str, ...]` — human lines stating the decision and the counts.
- `REFUSALS` — a closed tuple of named refusals + trailing `ValueError`, each exit-2 by name:
  - `NotARun` — the run directory holds no `ledger.json`;
  - `LedgerUnreadable` — via `ledger.read` by identity (schema gate, `ledger.py:211-224`);
  - `NotAProbe` — `task_set.probe` is not an int (a full night);
  - `IncompleteRun` — `draws_recorded` missing a declared draw or a source; or a draw's
    journal file absent.
- The control condition: every `draws_recorded[].harness[source] == Status.PASS` (the fold —
  the pre-committed rule's exact words), compared against `Status` by identity.
- The seed-map condition: the recorded `seeds` array is non-empty (`len > 0`), literal.
- Journal files are checked for **existence only** (`evidence_paths` by identity), never
  parsed — content is the night's own record, not a new bar.
- Composition by identity (asserted `is` in a test): `SOURCES` from `whetstone.loop.night`,
  `LEDGER_FILE`/`LedgerUnreadable`/`read` from `whetstone.loop.ledger`, `Status` from
  `whetstone.verify.verdict`, `evidence_paths` from `whetstone.loop.draws`.
- No inference import on the module or its tests (a per-file AST walk in the `check_leakage`
  shape).

## Out-of-scope boundaries

- The CLI subcommand (`check-probe` parser + handler + partition-guard edge) is `cli-door`.
- The night-door runbook rewrite and its guard extension are `runbook`.
- No per-task journal `INTACT` enforcement; no re-derivation of the seed map; no yield bar.
- Not the promotion gate: `decide()`, the three exits, retry discipline untouched.

## Acceptance criteria (testable, written first)

1. A valid probe fixture (`probe` int, complete `draws_recorded` with every source `PASS`,
   non-empty `seeds`, journals present) → `proceed is True`, `violation is None`.
2. A doctored ledger with one `harness[source]` not `PASS` → `proceed is False`, `violation`
   names the attempt **and** the source (never just "failed").
3. A doctored ledger with an empty `seeds` array → `proceed is False`, `violation` names the
   seed map.
4. A full night's ledger (`probe` null) → `NotAProbe`, named.
5. A directory with no `ledger.json` → `NotARun`, named.
6. `draws_recorded` with fewer entries than `draws`, or an entry missing a declared source →
   `IncompleteRun`, named with the counts.
7. A declared draw whose journal file is absent → `IncompleteRun`, named with the draw.
8. `REFUSALS` is closed by a trailing `ValueError` (an unforeseen crash is a named exit-2,
   never a traceback).
9. The no-inference walk sees the imports (anti-vacuity control).
10. Every identity composition is asserted `is`, and each is proven able to fail against a
    planted replacement.

## Dependencies and sequencing

- Ships first (`cli-door` and `runbook` both depend on the decision existing).
- Depends on the shipped ledger schema, `Status`, `SOURCES`, and `evidence_paths` — all read
  by identity, none modified.

## Open questions or risks

- Journal **content** is never parsed (existence only) — a journal full of corrupt lines still
  "exists". This is deliberate: the ledger is the completeness authority, the journal is
  corroboration. State it in the module docstring; do not silently grow a parser.
- The exit-1 control case is unreachable from a genuinely-written ledger (the night aborts
  before writing one) — the fixture is a doctored document, and the module docstring must say
  the check is a document assertion, never a claim to measure control.