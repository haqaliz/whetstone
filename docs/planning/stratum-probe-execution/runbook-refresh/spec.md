# Spec — `runbook-refresh` (aspect of `stratum-probe-execution`)

**Boundary:** the code phase only — the guard edit and the runbook rename that make the
probe's sheet executable from disk against this unit's worktree. The operator phases (the
arm run, the post-run chain, the finding, the report render) are executed per the existing
probe-run plan (`docs/planning/p2-easier-stratum/probe-run/plan_20260814.md:97-189`) and are
not built here.

## Problem slice

The sheet shipped in 0.6.0 names the worktree deleted at merge: 7 occurrences of
`.claude/worktrees/feat-p2-easier-stratum` (`runbook.md:64, 67, 189, 196, 202, 210, 217`),
all of which fail on disk. The guard is structural — it never existence-checks a path
(`test_probe_runbook_guards.py:240-241`) and its `STALE_WORKTREES`
(`test_probe_runbook_guards.py:46-50`) lacks the dead name — so the refresh is only
falsifiable if the stale-list edit lands first and is watched RED. Every positive guard
property is name-agnostic (dig-verified), so the rename alone would pass without proving
anything.

## In-scope requirements

1. `"feat-p2-easier-stratum"` joins `STALE_WORKTREES` in
   `tests/test_probe_runbook_guards.py` — RED against the current sheet, watched
   (`test_no_stale_worktree_name_survives_anywhere` fails, naming the dead name).
2. The runbook's 7 occurrences are renamed to `.claude/worktrees/feat-stratum-probe-execution`
   — the guard suite goes GREEN.
3. All existing guard properties hold after the refresh; the A2 resolution block and its
   pins (`RETAINED` / `EXCLUDED` / zero-ceiling rule) are byte-preserved in substance.
4. Nothing under `src/whetstone/` changes; `tests/test_runbook_guards.py` (the frozen
   measured-arm pin) is byte-untouched; the AC2 pins hold.
5. The sheet is executable against the unit's worktree project: `--help` exits 0 for
   `run`, `attribution`, `autopsy`, `preanalysis`, `comparison` via
   `uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-stratum-probe-execution`.

## Out of scope

- The operator phases (run, post-run chain, finding, report render) — executed, not built;
  the runbook and the probe-run plan already spell them out.
- Any runbook content change beyond the worktree rename (no merge-timing note, no
  rewording of the "Before you run" section unless the rename breaks it).
- Any change to `src/whetstone/verify/`, `patch.py`, `attribution.py`; any fourth
  generation-contract change.
- Editing the historical planning docs of the previous unit (`plan_20260814.md` etc.) or
  the frozen `tests/test_runbook_guards.py`.

## Acceptance criteria (tests written first, `CONTRIBUTING.md:56-60`)

1. RED watched: with only the `STALE_WORKTREES` edit in place,
   `uv run pytest tests/test_probe_runbook_guards.py::test_no_stale_worktree_name_survives_anywhere`
   fails and names `feat-p2-easier-stratum` in the assertion output.
2. GREEN: after the rename, `uv run pytest tests/test_probe_runbook_guards.py` passes
   (all 9 tests, zero skips).
3. `uv run pytest tests/test_runbook_guards.py` is unchanged-GREEN (byte-untouched pin).
4. `git grep -n "feat-p2-easier-stratum" docs/planning/p2-easier-stratum/probe-run/runbook.md`
   returns nothing; `git grep -n "feat-stratum-probe-execution" docs/planning/p2-easier-stratum/probe-run/runbook.md`
   returns 7 lines (the CWD prose line and the six command lines).
5. `uv run ruff check .` and `uv run mypy src/` exit 0.
6. Executability: `uv run --project <worktree> python -m whetstone.bakeoff.<mod> --help`
   exits 0 for `run`, `attribution`, `autopsy`, `preanalysis`, `comparison` — run from the
   primary CWD, exactly as the sheet's commands do.
7. The full suite stays green: `uv run pytest -q` (1001 passed, 3 skipped as of 0.6.0 —
   no regressions, no new skips).

## Dependencies and sequencing

- Requires nothing but the worktree (created in Phase 0, `uv sync` done) and the existing
  0.6.0 tree. The worktree's venv already exists.
- The guard edit precedes the runbook edit — the RED is the proof the guard can see the
  dead name at all.

## Open questions / risks

- The `--help` executability checks are the closest the code phase comes to "did the sheet
  run" — they prove the module surface, not the run itself. The run's outcome is the
  operator phase's; a failed night is quarantined per the runbook's halt conditions, never
  silently retried.
- The rename makes the sheet stale again at THIS unit's merge — accepted pattern (measured
  arm precedent); the next refresh extends the stale list once more.
