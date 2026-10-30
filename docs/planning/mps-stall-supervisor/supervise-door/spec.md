# Spec — supervise-door (mps-stall-supervisor)

**PRD:** `../prd.md`. **Branch:** `feat/mps-stall-supervisor/aliz`.

## In-scope

1. `src/whetstone/loop/supervise.py` (new, stdlib only):
   - `STALL_SCHEMA = "whetstone-stall/1"`, `STALL_FILE = "stalled.json"`,
     `DEFAULT_STALL_SECONDS = 5400.0`, `POLL_SECONDS = 5.0`;
   - `without_supervise(argv)` strips `--supervise` and `--stall-seconds` (both spellings);
   - `child_command(argv)` builds the `sys.executable -c "from whetstone.cli import main;
     raise SystemExit(main())"` command;
   - `last_write(draws) -> tuple[int, Path | None]` over `*.journal.jsonl` and
     `*.transcript.jsonl`;
   - `supervise(*, command, run, run_id, recorded_on, stall_seconds, poll_seconds=POLL_SECONDS)
     -> int`: spawn, poll, kill on stall, marker, child code, KeyboardInterrupt cleanup.
2. `src/whetstone/loop/night.py`: `supervise_night(*, argv, runs, run_id, recorded_on,
   stall_seconds)` — `_refuse_published_root(runs, "--runs")`, `without_supervise`,
   `child_command`, `supervise(run=runs/run_id, ...)`.
3. `src/whetstone/cli.py`: `--supervise`, `--stall-seconds`; `run_night(args, *, argv=None)`; the
   parent branch; the `--stall-seconds`-without-`--supervise` usage error; `main` passes the raw
   argv.
4. The Torch sheet's probe and night blocks; `tests/test_torch_mps_runbook_guards.py`.
5. Tests: `tests/loop/test_supervise.py` (pure), `tests/loop/test_night_cli.py` (delegation +
   usage error). The existing night tests are unchanged.

## Out-of-scope

The root-cause fix; the probe/night run; a reward/gate/corpus change; a sixth `cli.py` edge.

## Acceptance (test-first)

- A child that writes a journal then exits 0 → 0; no marker.
- A child that sleeps without writing, stall 0.2 s → 2; marker schema/fields; child gone.
- A child that exits 1 → 1; a child killed by an unrelated signal → 1; no marker.
- A run with an old journal, then a fresh journal before the threshold → 0 (spawn baseline).
- `without_supervise` removes the flags in both spellings; `child_command` is the documented
  `-c` form; `supervise_night` refuses a `--runs` under `reports/`.
- `cli.main(["run","--night",...,"--supervise","--stall-seconds","12"])` delegates with 12,
  the run id/date and a stripped argv; `--stall-seconds` alone exits 2.
- The Torch sheet blocks pass `--supervise --stall-seconds 5400`; the guard pins them.
- `uv run pytest`, `mypy src`, `ruff check src tests` green.
