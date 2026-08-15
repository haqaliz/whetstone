# PRD — stratum-probe-execution

**Written:** 2026-08-15. **Source:** inline brief (`docs/planning/_card/issue.md`), built on
the probe-run unit's shipped artifacts (`docs/planning/p2-easier-stratum/probe-run/`).

## Problem Statement

The easier-stratum probe is the fork gate after P1's fired pivot signal: its strict-PASS
yield decides between P2 (rollouts + expert iteration on the stratum) and the larger-base
arm (`p2-easier-stratum/prd.md:44-55`). All of its machinery shipped in 0.6.0 — the stratum
document, the run-side filter, the report home, and the operator's sheet with its guard
(`CHANGELOG.md:16-103`) — but **the probe has not run**: `reports/easier-stratum/report.md:9`
holds the declaration-only state, and `runs/` holds no evidence directory.

The blocker is the sheet itself. Every command in the runbook
(`docs/planning/p2-easier-stratum/probe-run/runbook.md`) executes the branch code "via its
project" and names the worktree the 0.6.0 branch lived in — `.claude/worktrees/feat-p2-easier-stratum`,
7 occurrences (`runbook.md:64, 67, 189, 196, 202, 210, 217`) — and that worktree was
deleted when the branch merged (the worktree directory is empty; only the primary and this
unit's worktree exist). The guard never existence-checks a path — structural by design
(`tests/test_probe_runbook_guards.py:240-241`) — and its stale list lacks the dead name
(`test_probe_runbook_guards.py:46-50`), so the suite is green while every command in the
sheet fails with "project not found". The fork gate is stuck behind a sheet that cannot be
executed.

This is the same move the measured-arm unit made, one unit later: the measured arm ran on
its branch (finding committed 2026-08-12 20:22, merged 20:46) and its historical runbook
keeps naming its dead worktree as a frozen pin. The probe runbook's refresh is that pattern
repeated.

## Goals & Success Metrics

- The runbook's commands execute from disk: every `uv run --project` target names this
  unit's live worktree (`.claude/worktrees/feat-stratum-probe-execution`), and the guard
  proves it — RED watched first when `feat-p2-easier-stratum` joins `STALE_WORKTREES`, GREEN
  after the rename.
- The probe runs (operator-executed, a night of GPU), the post-run chain completes with the
  instruments' own refusals all passing — zero mapping violations, zero
  `unrecognised-shape`, `INTACT` control present — and the report door renders figures into
  `reports/easier-stratum/`.
- The finding lands on the branch applying the pre-committed fork rule (`prd.md:44-55`)
  with the M13 axis-falsification check stated in words (`p2-easier-stratum/prd.md:222-227`).
- No figure about a model anywhere outside `reports/easier-stratum/` and the gitignored
  breakdown home (`runs/easier-stratum-preanalysis/comparison.md`).
- **No target yield is set**: the probe measures; a zero is a publishable outcome
  (`p2-easier-stratum/prd.md:53-55`). Success is a runnable sheet, a completed run, and an
  honest finding.
- **Done-state:** the finding names the next unit per the fork rule (P2's first slice on
  the stratum, or the larger-base arm), so a later reader of `docs/planning/` knows which
  arm the roadmap's fork resolved to.

## Personas & Scenarios

The operator (aliz): runs the arm command verbatim from the runbook tonight, in the primary
checkout with the branch code via this unit's worktree, wakes up to the finding that decides
the roadmap's next unit. A later agent: executes the post-run chain commands verbatim,
offline and deterministic, read-only against the primary's gitignored runs.

## Requirements

**Must-have (code phase — Phase 6, test-first):**

1. `feat-p2-easier-stratum` joins `STALE_WORKTREES` in `tests/test_probe_runbook_guards.py`
   — the guard must go RED against the current sheet first (watched, `CONTRIBUTING.md:56-60`).
2. The runbook's 7 path occurrences (`runbook.md:64, 67, 189, 196, 202, 210, 217`) are
   renamed to `.claude/worktrees/feat-stratum-probe-execution` — the suite goes GREEN.
3. Every existing guard property holds after the refresh: absolute writable paths, all arm
   flags in `build_parser()`, worktree-shaped `--project` targets, exactly one worktree name
   everywhere, arm CWD at the primary checkout, no stale name anywhere (anti-vacuity parse
   still passes).
4. The A2 resolution block and its pins are preserved untouched: `RETAINED` pair and
   `EXCLUDED` candidate as the arm's `--only` values, the zero-ceiling exclusion rule stated
   (`test_probe_runbook_guards.py:271-312`).
5. Nothing under `src/whetstone/` changes — the AC2 pins hold (verify/, patch.py,
   attribution.py byte-identical to origin/master); the bake-off machinery is untouched.

**Must-have (operator phases — executed, not built):**

6. The arm runs verbatim (hardened contract: `--stratum`, `--retries`, `--only` × 2,
   absolute writable paths, `--recorded-on` declared at run time). **Corrected
   2026-08-15 at launch, landed test-first:** the sheet's five declared dev ids are not
   stratum members, the harness refused the vacuous declaration (`UnknownDevSubset`), and
   the corrected arm declares no dev subset — the membership is the exclusion (guard
   extended; see `probe-run/finding.md`).
7. The post-run chain runs verbatim: attribution → autopsy → the mandatory pre-analysis
   extension over all four autopsy documents → comparison → the stratum-report door.
8. The finding applies the fork rule (yield > 0 → P2's first slice on the stratum;
   yield == 0 with control intact → larger-base arm) with the M13 axis check, and the
   rendered report lands in `reports/easier-stratum/` before the unit merges.

**Should-have:**

9. The runbook's "Before you run" section stays correct for the new worktree (the
   `uv sync --extra mlx` note is already worktree-agnostic — verify, don't rewrite).

## Acceptance Criteria (tests written first, `CONTRIBUTING.md:56-60`)

1. `uv run pytest tests/test_probe_runbook_guards.py` — the suite is **RED** against the
   sheet as it exists at the start of Phase 6, the moment `feat-p2-easier-stratum` joins
   `STALE_WORKTREES` (watched, not assumed).
2. After the runbook rename: the same suite is **GREEN**, and
   `uv run pytest tests/test_runbook_guards.py` is unchanged-GREEN (the measured-arm pin is
   byte-untouched).
3. `uv run ruff check .` and `uv run mypy src/` exit 0 (nothing under `src/` changed — a
   planted edit to `verify/`, `patch.py` or `attribution.py` fails the AC2 pin tests).
4. `git grep -n "feat-p2-easier-stratum" docs/planning/p2-easier-stratum/probe-run/runbook.md`
   finds nothing, and the full-suite stale-name check (guard) passes over the whole sheet.
5. The runbook's arm command and post-run commands are executable against the unit's
   worktree project (`.claude/worktrees/feat-stratum-probe-execution`) — verified by
   `uv run --project <worktree> python -m whetstone.bakeoff.run --help` and the same for
   attribution, autopsy, preanalysis, comparison.
6. Operator phases (not tests, but checked the same way): the post-run chain's refusals are
   the instruments' own and none fires — zero mapping violations, zero `unrecognised-shape`,
   `INTACT` control present, pre-analysis extension over all four autopsy documents — and
   the report door renders `reports/easier-stratum/` with counts, contract fields, and the
   non-comparability sentence.

## Technical Considerations

- **Core-loop element:** ② nightly improvement loop — the probe measures whether training
  data exists; it is the premise test for P2, not a training run itself.
- **Reward untouched:** no change to the STRICT/WEAK verifiers, the executed-node-id
  assertion, the provenance boundary, or `N`. The probe is graded through the existing
  harness with the control discipline enforced by the harness itself
  (`sweep.py:41-47, 160-183`). No judge, no policy is generated here.
- **Gate semantics untouched:** `UNVERIFIED` stays above `PASS`; the probe publishes verdict
  counts, never a promotion.
- **Locality:** the run reaches the machine-level stores by absolute path only — the
  primary's `tasks/local/`, `weights/`, `runs/` — never by copying them into the worktree
  (whetstone-worktrees discipline). The GPU is machine-level; the run is serialized with any
  other local work.
- **Merge timing:** per the plan's M12 ordering (`p2-easier-stratum/prd.md:130-138`) and the
  measured-arm precedent (run before merge, finding in the same commit as its corrections),
  the probe executes on this branch while the worktree lives. The sheet will name a dead
  worktree again after this unit merges — that is the accepted, guarded pattern; the next
  refresh extends the stale list.
- **The guard is the test:** all positive properties are name-agnostic
  (`test_probe_runbook_guards.py:182-251`), so the stale-list edit is the only change that
  makes the refresh falsifiable — that is why it must land RED first.

## Risks & Open Questions

- **The night can fail and must be quarantined, not buried.** The halt conditions are the
  runbook's own (uniform `HarnessNotProven` → stop/fix/restart from an empty workspace;
  `ContractChanged` → run void, no recovery); dead evidence is moved aside by name, never
  deleted (`runbook.md:140-166`).
- **GPU cost is unmeasured** for this matrix (two candidates × retries, 900 s timeouts) —
  stated as unknown, plan for a night (`p2-easier-stratum/prd.md:232-235`).
- **Run timing is the operator's call.** The precedent is on-branch-before-merge; the
  operator confirms at the review gate whether tonight is the night. A merged sheet would
  need a second refresh — an avoidable cost, and out of scope here.
- **Stale-name completeness:** `feat-p2-easier-stratum` is the only dead worktree name in
  the live sheet (dig-verified); the two historical runbooks are frozen pins by design.
- **A zero is a finding, not a failure** — but the finding must state in words whether the
  axis failed or the premise failed (M13), so a zero routes the correct arm.

## Out of Scope

- Any P2 loop code (`whetstone run --night`, training-set recording, determinism test) —
  its premise is exactly what the probe settles.
- The larger-base arm — the fork's other branch, contingent on a zero yield.
- Any runbook content improvement beyond the worktree rename (no merge-timing note; the
  measured-arm sheet carries none).
- Any change to `src/whetstone/verify/`, `patch.py`, `attribution.py`; any fourth
  generation-contract change, ever (`p2-easier-stratum/prd.md:44-55`).
- The held-out split (§ 7.1), the retry count R, the P3 gate, the report/dashboard — named
  elsewhere on the roadmap; not this unit.
