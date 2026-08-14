# Understanding — stratum-probe-execution

## What this work really is

The probe-run unit's Phase 1 shipped in 0.6.0 (`CHANGELOG.md:16-38`): the operator's sheet
(`docs/planning/p2-easier-stratum/probe-run/runbook.md`) plus its guard
(`tests/test_probe_runbook_guards.py`). The sheet names the worktree the branch lived in
(`.claude/worktrees/feat-p2-easier-stratum`) — 7 occurrences: runbook.md:64, 67, 189, 196,
202, 210, 217 — and that worktree was deleted when the branch merged. The guard never
existence-checks a path (structural by design, `test_probe_runbook_guards.py:240-241`), so
the suite is green while every command in the sheet fails with "project not found".

This unit is the **same move the measured-arm unit made**, one unit later: re-point the live
sheet at the unit's own worktree (`.claude/worktrees/feat-stratum-probe-execution`, created
in Phase 0), add the superseded name to `STALE_WORKTREES` (RED first — the guard's stale
list is `("feat-measured-arm-run", "feat-p2-format-hardening",
"feat-format-hardening-measurement")`, `test_probe_runbook_guards.py:46-50`, and lacks
`feat-p2-easier-stratum` today), then the operator executes Phases 2–4 of the existing plan
(`plan_20260814.md:97-189`): the overnight arm run, the post-run chain, and the finding that
applies the pre-committed fork rule (`prd.md:44-55`).

## What was verified (dig, file-cited)

- The probe has **not** run: `reports/easier-stratum/report.md:9` holds the declaration
  ("No count is measured here: the probe has not run."); `report.json` has null
  generation_contract/per_candidate. CHANGELOG 0.6.0 claims machinery, not a run — the
  correct distinction.
- The branch `feat/p2-easier-stratum/aliz` is gone (only the remote-tracking ref remains);
  the worktree is deleted from disk.
- All guard properties are **name-agnostic** for the positive case: renaming the sheet to
  any `.claude/worktrees/<name>` path passes; the stale-list edit is what makes the refresh
  a real RED-first change.
- Merge timing: the run executes **on the branch, before merge**. Precedent:
  `measured-arm/finding.md:4` ("after the arm ran"), branch tip ad3d5ec 20:22 →
  merge 20:46 on 2026-08-12. The probe plan's M12 ordering (`prd.md:130-138`) and Phase 2–4
  text assume a live branch worktree. Historical runbooks keep naming dead worktrees after
  merge — that is the accepted pattern, and the next refresh extends the stale list again.
- Fork rule (`prd.md:44-55`): yield > 0 for any candidate → P2's first slice on the stratum;
  yield == 0 with control intact → larger-base arm. Never a looser verifier, never a fourth
  generation-contract change. M13 axis check (`prd.md:222-227`, spec A6): a zero must state
  in words whether the axis failed or the premise failed.
- No test file references `feat-p2-easier-stratum`; no file references
  `feat-stratum-probe-execution` in the committed tree.

## Affected areas

- `docs/planning/p2-easier-stratum/probe-run/runbook.md` — 7 path occurrences (rename).
- `tests/test_probe_runbook_guards.py` — `STALE_WORKTREES` (+ `feat-p2-easier-stratum`).
- Nothing under `src/whetstone/` — the bakeoff machinery (run, stratum filter, report door,
  comparison, autopsy, preanalysis) is untouched; the AC2 pins hold.
- Phases 2–4 (operator execution, post-run chain, finding, report render) are
  operator-executed per the existing plan; no new code.

## Core loop placement

Element ② (nightly improvement loop): the probe is the yield measurement that settles
whether the loop has training data (P2's premise). The reward is untouched — the STRICT
verifier grades by execution, no judge; the gate semantics (UNVERIFIED above PASS) are
untouched; nothing leaves the box (MLX local, source B in the primary's gitignored store,
reached by absolute path only).

## Open questions

1. **Run timing:** the precedent and the plan say the probe runs on this branch before
   merge. The operator executes it (a night of GPU); the wbf session's code phase lands
   only the refresh. Confirm the operator intends to run it on this branch (vs. merging
   the refresh first) — the precedent says on-branch.
2. **Scope minimalism:** nothing beyond the rename + stale-list edit + A2-pin preservation
   is in scope. Any other runbook improvement (e.g. documenting merge timing) is out —
   the measured-arm sheet carries no such note.
3. The `--recorded-on`, evidence paths, and candidate pins are all unchanged; the runbook
   keeps `feat-stratum-probe-execution` as its single worktree name everywhere (guard:
   exactly-one-worktree).
