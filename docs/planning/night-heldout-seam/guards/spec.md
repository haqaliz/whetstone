# Aspect spec — guards

**Unit:** `night-heldout-seam` · **Aspect:** `guards` · **PRD:** `docs/planning/night-heldout-seam/prd.md`.
**Scope:** `tests/test_night_runbook_guards.py` (the night sheet's guard suite) plus one new
live suite test. Nothing under `src/` moves.

## Problem slice

The night sheet's guards still encase the pre-§ 10.16 sheet: `DECLARED_DEV` pins five
`belay-*` ids (`tests/test_night_runbook_guards.py:84-90`) and the block-parsing tests read
the command blocks as they are written today. Extend the suite so the staleness class — a
corpus re-mint, a split re-derivation, a run id that names a real artifact — is refused by
name, and so a future sheet editor cannot quietly regress the new pins.

## In-scope requirements (PRD R2-left, R3-left, R4, R5, R6, R7, R8; S11)

- Refuse a `belay-`/`contig-` id in any command block of the sheet.
- Require `--heldout $REPO/tasks/heldout/source-b.json` in the probe command **and** the
  night command.
- Refuse a live `§ 10.7` citation; require the `§ 10.16 (Type 1, 2026-09-27)` citation and
  the scorable-rule sentence; require the digest read-back halt sentence (the gate runbook's
  wording pattern).
- Refuse `probe-001`/`night-001` as run ids in either command.
- Require the `check-leakage --run … --heldout …` step in the "After the night" section.
- Require the corrected denominator sentence (51 private + 1 public = 52 tasks) and refuse
  the stale "62 tasks" arithmetic.
- Reconcile the suite's existing pins in both directions: every old pin the new sheet cannot
  honestly satisfy is updated deliberately on the record (commit-visible), never weakened;
  every new pin is shown **failing against the current stale sheet** before the new sheet
  exists (watched-failing, recorded as a named failure in the commits).
- The live test: load `tasks/local/` (primary checkout, skipping in CI with the reason named,
  on the heldout-recomputation precedent), assert the five dev ids exist as `donor-b-*`
  corpus members and the two overlap ids are held-out members of the committed document.

## Out-of-scope boundaries

- No production-code change; no parser change; no change to `test_gate_runbook_guards.py`
  (its own pins stay; it is the pattern source, not a target).
- The existing watched-failing demonstrations in other suites are not re-run here.

## Acceptance criteria (tests written first)

1. The new assertions fail against the current sheet, each naming the thing it refuses
   (recorded in the commit message of the RED step).
2. After the sheet rewrite, the whole extended suite passes against the new sheet.
3. The updated old pins are visibly deliberate (one commit, named in its message; no pin
   weakened — each new wording states what the new sheet actually does).
4. The live dev-id test passes in the primary checkout and skips (loudly, naming why) in a
   worktree/CI without `tasks/local/`.
5. `uv run pytest tests/test_night_runbook_guards.py -q` green; ruff and mypy clean on the
   touched test file.

## Dependencies and sequencing

First aspect: it owns the RED half. `sheet` consumes it for GREEN. The live test's corpus
assertions depend only on the primary checkout's `tasks/local/` and the committed
`tasks/heldout/source-b.json`.

## Open questions / risks

- The exact parse helpers the suite shares with sibling guard modules (`:224`) — the plan
  reads them before extending, so the new pins use the same shape.
- The live test must not require a GPU or a venv beyond the suite's own; `tasks/` loading is
  plain JSON reads — expected, verified at plan time.