# Spec — runbook

**Unit:** `probe-decision-gate` · **Aspect:** `runbook` · **Date:** 2026-09-05
**Source:** `docs/planning/probe-decision-gate/prd.md` (requirement 7; risks: resume semantics).

## Problem slice and user outcome

The operator's sheet for night #1 gains the go/no-go as a **command**, and the prose
pre-commitment becomes the thing the sheet actually runs. The decision-rule paragraph in
`docs/planning/p2-rollouts/night-door/runbook.md:78-80` (the "night proceeds iff" sentence)
is replaced by a `whetstone check-probe --run …` step, the "Read
`runs/night-probe/probe-001/ledger.json` before going further" sentence becomes the command's
exit, and a new sentence forbids **resuming a probe** (a killed probe restarts fresh with a new
run id — it is cheap, first-N private tasks; a killed *night* still resumes unchanged). The
sheet is rewritten code-first, and `tests/test_night_runbook_guards.py` gains this unit's own
pin.

## In-scope requirements

- The runbook's probe-pass section:
  - the third bash block invokes `uv run --project <worktree> whetstone check-probe --run
    /Users/aliz/dev/at/whetstone/runs/night-probe/probe-001` — the same worktree, absolute
    `--run`, naming the probe run dir the preceding block wrote (`--runs
    /Users/aliz/dev/at/whetstone/runs/night-probe`, `--run-id probe-001`);
  - the block appears **before** the night's block in the sheet;
  - the decision-rule paragraph states the two conditions in the pre-committed words (control
    arm `PASS` on every draw; non-empty seed map) and what each exit means (0 → proceed;
    1 → named harness finding, no night behind it; 2 → a refusal to fix, not a verdict);
  - the no-probe-resume sentence states the probe/night restart distinction.
- The guard extension (`tests/test_night_runbook_guards.py`), written first and watched
  failing:
  - the module docstring's "Six properties" → seven;
  - a new test pinning the `check-probe` block: exists, is a bash block, is before the night
    block; its only flag is `--run` (against the shipped `check-probe` parser surface);
    the `--run` value is absolute and points at `runs/night-probe/probe-001`; the two
    condition sentences and the no-resume sentence are present;
  - the existing pins survive unchanged: `_door_blocks` still exactly two (both
    `whetstone run --night`), one worktree named everywhere (the check-probe block uses the
    same worktree), retained/excluded candidates, five dev ids, the zero-yield/raise-K/loosen
    prose, "Nothing here is published", no `/reports/` paths.

## Out-of-scope boundaries

- The command's implementation and its exit-code contract are `check-core` + `cli-door`.
- No change to the killed-*night* restart semantics, the halt conditions, or what a probe is.
- No change to the guard's shared parse helpers (`_bash_blocks`, `_named_paths`,
  `_worktree_name` — imported by identity, untouched).

## Acceptance criteria (testable, written first)

1. The runbook contains a `check-probe` bash block before the night block, with `--run` only,
   absolute, pointing at `/Users/aliz/dev/at/whetstone/runs/night-probe/probe-001`.
2. The decision-rule paragraph states both conditions in the pre-committed words and the
   exit meaning (0 proceed / 1 no night / 2 not a verdict); a paragraph that drops a condition
   or the exit meaning fails the pin.
3. The no-probe-resume sentence is present and distinguishes probe (restart fresh) from night
   (resume unchanged).
4. The guard's seven-property suite is green; every existing pin (the six) passes unchanged.
5. Each new assertion is proven able to fail against a deliberately wrong stub sheet (no
   `check-probe` block, `--run` relative, `--run` pointing at the night's dir, missing
   condition sentence, resume sentence claiming a probe resumes) before the real sheet
   satisfies it.
6. Full `uv run pytest` green.

## Dependencies and sequencing

- After `check-core` and `cli-door` — the sheet may not be edited ahead of the command it
  would then disagree with (the `gate-untrained-incumbent` rule).
- The guard's flag-surface pin reads `build_parser()`, so it also proves the command exists.

## Open questions or risks

- The probe's `--run` path must match the preceding block's `--runs` + `--run-id` exactly
  (`runs/night-probe/probe-001`); a mismatch is exactly the drift the guard exists to catch,
  so the pin asserts the joined path.
- The exit-1 meaning must not claim the gate *measures* anything new — the sheet should say a
  named harness finding means no night runs behind it, and a refusal (exit 2) is a command to
  fix, not a verdict about the probe.