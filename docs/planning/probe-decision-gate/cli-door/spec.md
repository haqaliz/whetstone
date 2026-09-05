# Spec — cli-door

**Unit:** `probe-decision-gate` · **Aspect:** `cli-door` · **Date:** 2026-09-05
**Source:** `docs/planning/probe-decision-gate/prd.md` (requirements 1, 2, 10).

## Problem slice and user outcome

The `whetstone check-probe --run <runs/id>` subcommand: the operator-chain surface for the
`check-core` decision, modeled on `whetstone check-leakage` exactly (parser registration,
function-local handler, four-code contract, no fifth). The command is how the night-door sheet
holds night #1's go/no-go; it is the **fifth** documented partition-guard edge, grown in a diff,
never silently.

## In-scope requirements

- `check-probe` subcommand in `build_parser()` with `--run` (required, `type=Path`) and a
  description stating the exit codes in prose (the `_GATE_DESCRIPTION`/check-leakage shape).
- Handler `run_check_probe_cli(args) -> int`:
  - function-local `from whetstone.loop.check_probe import REFUSALS, disclosure, run_check`;
  - `except REFUSALS` → stderr `whetstone check-probe: {refusal}`, `return USAGE_ERROR`;
  - print `disclosure(report)` lines; `return PASS_EXIT` if `report.proceed` else `FAIL_EXIT`.
- The **fifth** partition-guard edge:
  - `_DOCUMENTED_EDGES` (`tests/test_reward_path_scope_is_partitioned.py:154-159`) gains
    `(Path("whetstone/cli.py"), "whetstone.loop.check_probe")`;
  - the `EXEMPT["loop"]` reason (`:120-147`) "exactly FOUR documented edges" → FIVE, with the
    new handler's sentence written, watched failing first;
  - the stale edge-count docstrings in `cli.py` (`run_gate_cli` "exactly two",
    `run_check_leakage_cli` "only three", `run_report_cli` "only four") and the module
    docstring's command list (`cli.py:27-37`) are corrected in the same commit.
- The module docstring guard (`tests/loop/test_morning_cli.py:212-239`) must pass: the new
  subcommand is named in `cli.py`'s module docstring and appears in help.
- Tests: process-boundary exit codes (0 / 1 / 2) through `cli.main(argv)` in the
  `test_check_leakage_cli.py` shape; a flag-surface pin (exactly `["--help", "--run"]`);
  identity assertion `check_probe` imports by identity; no-fifth-code contract.

## Out-of-scope boundaries

- The module's decision logic and its tests are `check-core`.
- The night-door runbook and its guard are `runbook` — this aspect only wires the command.

## Acceptance criteria (testable, written first)

1. `cli.main(["check-probe", "--run", <probe-dir>])` → `PASS_EXIT` for a valid probe,
   `FAIL_EXIT` for a named violation, `USAGE_ERROR` for a refusal — asserted at the process
   boundary, each failure naming the condition.
2. The parser exposes exactly `["--help", "--run"]` for `check-probe`.
3. `_DOCUMENTED_EDGES` has exactly five entries; the EXEMPT reason says FIVE; each of the four
   stale edge-count docstrings in `cli.py` is corrected and the module docstring names
   `check-probe`.
4. `test_the_reward_path_reaches_the_exempt_packages_by_exactly_the_documented_edges` and
   `test_the_documented_edges_into_the_exempt_packages_are_function_local` pass with the new
   edge — each proven able to fail against a planted change.
5. `test_the_module_docstring_names_every_subcommand_that_exists` and the help-listing test
   pass.
6. `uv run pytest` full suite green; `ruff`/`mypy` clean.

## Dependencies and sequencing

- After `check-core` (the module must exist before the handler imports it).
- Before `runbook` (the sheet may not be edited ahead of the command it would then disagree
  with).

## Open questions or risks

- None beyond the PRD's: the fifth edge is mechanical and must land as one diff (guard +
  handler + docstrings together), never piecemeal.
- Exit-code mapping is fixed: `0` = proceed, `1` = violation, `2` = refusal. There is no
  `UNVERIFIED` — the command reads documents.