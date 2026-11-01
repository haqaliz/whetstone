# Spec — probe-pin (probe-sample-pin)

**PRD:** `../prd.md`. **Branch:** `feat/probe-sample-pin/aliz`. **Date:** 2026-10-31.

## Problem slice

`whetstone check-probe` can pin the backend but not the declared sample size. The § 10.25 probe
is a 16-task/272-draw measurement; a 2-task probe must not pass its door. Add an optional
`--probe N` pin that compares the ledger's `task_set.probe`, names a mismatch as exit 1, and
leaves the unpinned decision byte-identical.

## In-scope

1. **`run_check`** (`src/whetstone/loop/check_probe.py`): keyword-only `probe: int | None = None`.
   - Rename the local `probe = _probe_of(...)` to `declared` (or `recorded_probe`) so the pin
     does not shadow the recorded value; update every `_report(probe=...)` site.
   - Build `backend_pins` from `runtime`/`device`/`precision` and use **that** as the backend
     enable switch; build the reported `pins` as
     `(("probe", str(probe)), *backend_pins)` when the sample pin is passed, else `backend_pins`.
   - After the held-out check and before the backend checks, compare `declared != probe` and
     return `proceed=False` with a violation naming both values, e.g.
     `declared sample is 2 tasks, not the pinned 16`. A matching pin proceeds to the existing
     checks unchanged.
   - A full night / non-int `task_set.probe` still raises `NotAProbe` (exit 2) before the pin
     comparison.
2. **`ProbeReport`**: no new field; `probe` remains the recorded declared size and `pins` gains
   `("probe", "<n>")` first when passed. `disclosure` already prints `probe:` and `pins:`; add
   nothing unless the line order needs the probe pin first (it will render first automatically).
3. **CLI** (`src/whetstone/cli.py`):
   - `check-probe --probe <n>`, `type=int`, optional, `metavar="<n>"`, help: "the probe's declared
     sample size; a different recorded size is a named violation (exit 1), and a run that is not
     a probe at all remains a refusal (exit 2)."
   - Add the sample pin to the parser description's exit-1 list.
   - Pass `probe=args.probe` in `run_check_probe_cli`.
4. **Tests** (`tests/loop/test_check_probe.py`, `tests/loop/test_check_probe_cli.py`):
   - `test_a_matching_probe_pin_proceeds` — `_probe_run(..., probe=16)`, `run_check(run,
     probe=16)`: `proceed`, `pins == (("probe", "16"),)`.
   - `test_a_probe_of_another_sample_is_a_named_violation` — `probe=2` vs pin 16: not proceed,
     violation names `2` and `16`, `pins == (("probe", "16"),)`.
   - `test_a_probe_pin_does_not_require_a_backend_block` — a `/2` ledger with no backend,
     `probe=16`, pin 16: proceeds (the split-switch regression).
   - `test_no_probe_pin_keeps_the_old_decision` — `probe=2`, no pin: proceeds, `pins == ()`.
   - `test_a_full_night_under_a_probe_pin_is_a_refusal` — a full-night ledger plus `probe=16`
     still raises `NotAProbe` (exit 2), not a violation.
   - `test_disclosure_shows_the_probe_pin` — `pins: probe=16`.
   - CLI: `test_the_probe_pin_passes_through`, `test_a_probe_pin_mismatch_exits_one`,
     `test_a_probe_pin_mismatch_does_not_require_a_recorded_backend` (the sheet passes all pins,
     but the command must not couple them), and update
     `test_the_check_probe_flag_surface` to include `--probe` in the sorted list.
   - The existing no-pin tests must pass unchanged; a pin can only add a violation.

## Out-of-scope

- The sheet and § 10.26 (separate aspects).
- The reward, gate, corpus, held-out document, `K`, `R`, the § 10.25 inputs, the MPS hang.
- Adding sample ids to the ledger (`whetstone-run/4`).
- A `--probe` flag on any other command.

## Acceptance (test-first)

- A matching pin proceeds; a mismatch is exit 1 and names both values; a full night is exit 2;
  no pin is byte-identical to today.
- `--probe` alone does not activate the backend check; `--probe` + `--runtime torch` still does.
- The CLI exposes exactly `--run`, `--heldout`, `--runtime`, `--device`, `--precision`,
  `--probe`, `--help`.
- The focused suites, `ruff` and `mypy` are green.

## Sequencing

After `sample-amendment`, before `sheet-alignment` (the sheet guard asserts the parser exposes
`--probe`).
