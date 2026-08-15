# Spec — runbook-and-guard (larger-base-arm)

**Written:** 2026-08-15. **PRD:** `docs/planning/larger-base-arm/prd.md` (requirements 1–5;
acceptance criteria 1–3, 9, 12).

## Problem slice

The arm is operator-executed from a sheet, and the sheet's correctness is held by a guard.
The probe sheet (`docs/planning/p2-easier-stratum/probe-run/runbook.md`) is now a frozen
historical pin (the measured-arm precedent); this unit writes a **new** sheet at
`docs/planning/larger-base-arm/runbook.md` — content differs materially from the probe's:
no `--stratum` (the full declared source-B set), the dev overlay restored, one new
candidate, a mandatory probe pass. The new guard module pins the sheet the way the probe
guard pins its own, importing the parse helpers by identity from
`tests/test_probe_runbook_guards.py`.

## In scope

- `docs/planning/larger-base-arm/runbook.md`: the operator's sheet —
  - **The candidate resolution (A2)**: `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`
    retained and named (the next rung on the measured family; no measured ceiling, so the
    zero-ceiling rule does not apply), `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit`
    excluded by name under the zero-ceiling rule (`p2-easier-stratum/prd.md:97-99`), the
    block stating the retained/excluded reasoning and the rule.
  - **Before you run**: the 32B weights fetch into the primary's `weights/` + recording in
    `provenance.json` (human-run, the one declared network exception,
    `docs/ROADMAP.md:574-576`); `uv sync --extra mlx` in the worktree; workspace empty and
    fresh; evidence machine-level, never copied between checkouts; the dev overlay declared
    (the five ids, each matching a loaded task or the run refuses).
  - **The probe pass (D7)**: `--probe` on the 32B over the runbook's declared sample of N
    tasks, publishing cost and no counts, before the arm; the pre-committed decision rule:
    the arm proceeds iff the probe completes on all N sampled tasks and the probe's
    published peak bytes leave the runbook-stated headroom below the machine's RAM;
    otherwise the capacity finding fires and the arm does not run.
  - **The arm command**: hardened contract (`--retries`, budget 2), no `--stratum`, the
    five declared dev ids as `--dev-subset`, `--only` exactly once (the 32B), absolute
    writable paths, CWD at the primary checkout, journal and transcript in a sibling
    gitignored evidence directory (never under `--out`), `--recorded-on` declared at run
    time. Denominator stated: 61 private (66 − 5 dev) + 1 public = 62.
  - **Halt conditions**: uniform `HarnessNotProven` → stop/fix/restart from an empty
    workspace; `ContractChanged` → run void, no recovery; never reuse a workspace; the
    probe's capacity verdict.
  - **Killed-run restart**: quarantine dead evidence by name, never delete; fresh paths;
    the arm command unchanged apart from paths.
  - **The post-run chain**: attribution → autopsy → the mandatory pre-analysis extension
    over **all five** autopsy documents (arm-a, budget-2048, format-hardening-arm-evidence,
    easier-stratum-evidence, larger-base-evidence) → comparison (INTACT control required) →
    the larger-base report door (`--render-larger-base-report`).
  - The sheet names exactly one worktree: `.claude/worktrees/feat-larger-base-arm`.
- `tests/test_larger_base_runbook_guards.py`: the guard —
  - `STALE_WORKTREES` = the probe guard's tuple **plus** `feat-stratum-probe-execution`.
  - The parse helpers imported from `tests/test_probe_runbook_guards.py` **by identity**
    (asserted `is`; the pinned module byte-untouched).
  - The seven properties (absolute writable paths, every arm flag in `build_parser`,
    worktree-shaped `--project` targets, exactly one worktree everywhere, arm CWD at the
    primary, no stale name anywhere, anti-vacuity parse — anti-vacuity re-pointed at the new
    arm's shape: `--retries`, `--only`, `--dev-subset`, `--probe` present; `--stratum`
    absent), plus:
  - The A2 resolution rule (the 32B named in the resolution block; the 7B named there and
    in no `--only` value; the block states the zero-ceiling rule).
  - The probe-pass-first property (the probe command appears before the arm command).
  - The restored dev overlay (every declared `--dev-subset` id matches a loaded task of the
    primary's corpora).
  - The five-autopsy pre-analysis step.

## Out of scope

- Any change to `tests/test_probe_runbook_guards.py` or `tests/test_runbook_guards.py`
  (both byte-untouched).
- Any change to the probe sheet (a frozen historical pin).
- Any change to `src/whetstone/` (the sibling aspect `report-home` owns the report
  machinery; `run.py`'s surface needs no change).

## Acceptance criteria (tests written first, `CONTRIBUTING.md:56-60`)

1. **RED watched first**: with the new guard's `STALE_WORKTREES` extended and its `RUNBOOK`
   bound to the probe sheet as it exists, the stale-name test fails naming
   `feat-stratum-probe-execution` — the RED is observed, never assumed.
2. After the new runbook lands and `RUNBOOK` flips to it, the same suite is GREEN: the seven
   properties, the A2 rule, the probe-pass-first rule, the dev-overlay rule, the
   five-autopsy step — over the whole file, prose included.
3. `tests/test_probe_runbook_guards.py` and `tests/test_runbook_guards.py` unchanged-GREEN
   (byte-untouched).
4. The runbook's commands are executable from disk: `uv run --project
   .claude/worktrees/feat-larger-base-arm python -m whetstone.bakeoff.run --help` and the
   same for attribution, autopsy, preanalysis, comparison (exit 0).
5. The dev-overlay ids named in the runbook all resolve against the primary's loaded
   corpora (the guard checks them the way `test_every_declared_dev_id_is_a_stratum_member`
   checks the probe's).
6. AC2 pins hold; `uv run ruff check .` and `uv run mypy src/` exit 0; full suite green.

## Dependencies & sequencing

- Independent of `report-home`; the runbook names `--render-larger-base-report`, which the
  sibling aspect ships — the guard checks only the run door's parser, so no ordering
  constraint; final "executable from disk" verification happens after both aspects land.
- RED is watched against the probe sheet before the new sheet exists.

## Open questions

- The probe sample N and the headroom in the probe-pass decision rule are runbook constants,
  decided by the operator at run time and stated in the sheet (mirroring `--recorded-on`'s
  declared-at-run-time posture) — the guard asserts the rule is *present*, not its values.
