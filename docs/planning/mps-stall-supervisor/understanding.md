# Understanding — mps-stall-supervisor

**Unit:** `feat/mps-stall-supervisor/aliz` · **Written:** 2026-10-30 · **Source:**
`docs/planning/_card/issue.md`.

## What the work is really asking

A night's evidence is written per draw, but a Metal call can hang the whole process in an
uninterruptible wait. The finding records it twice: the 8B night hit an MPS OOM on the public task
after ~35 h and hung, a resume failed on a corrupted attention mask, and a second resume hung
(`docs/planning/torch-mps-series/finding.md:42-61`); the 14B NF4 pre-flight produced 7 draws and
then hung for 64+ minutes, process state `U+`, and the 900 s draw timeout could not fire
(`:75-83`). The repair night completed 832 draws, so the defect is intermittent — but a lost
measurement costs a night, and the next measurement (the § 10.25 probe) includes the public task.

The fix cannot be an in-process timeout: an uninterruptible Metal call does not return to Python.
The only reliable breaker is a **parent process** that can `SIGKILL` the child's process group.
The parent then writes a marker saying what happened, and the operator resumes from the journals
(the night already resumes by replaying them).

## Current code, precisely

- `whetstone run --night` is the `run` subparser (`cli.py:258-...`), handled by `run_night`
  (`cli.py:1164`), which imports `whetstone.loop.night` function-locally and calls `conduct_night`.
- `run_night` returns the child's `PASS_EXIT`/`FAIL_EXIT`/`UNVERIFIED_EXIT` and prints the
  night's disclosure (`cli.py:1194-1240`).
- The night writes per-draw journals under `runs/<run-id>/draws/<stem>.journal.jsonl` and
  transcripts beside them (`loop/draws.py:81-89`, `loop/night.py:...`); the ledger is written at
  the end. A killed process leaves the journals, which the next invocation replays.
- `night._refuse_published_root(runs, "--runs")` is the locality refusal (`loop/night.py`), and
  `whetstone.loop.night` is the **only** documented edge from `cli.py` into the loop package for
  this handler (`tests/test_reward_path_scope_is_partitioned.py:157-...`). A new direct
  `cli.py` import from `whetstone.loop.supervise` would be a sixth edge and fail that guard; the
  supervisor must be reached through `whetstone.loop.night`.
- The parser's `run` command is `whetstone run --night` (a flag, not a subcommand); the handler
  receives only the namespace, so the raw argv must be passed from `main` to rebuild the child
  command.
- The child must be a real `whetstone` invocation. There is no `__main__.py`; the console script
  is `whetstone.cli:main`. The portable child command is
  `[sys.executable, "-c", "from whetstone.cli import main; raise SystemExit(main())", *argv]`.
- The supervisor's clock: the marker's `last_write_ns` comes from the journal's `st_mtime_ns`
  (a machine fact); the stall decision uses a monotonic interval, with the spawn's wall time as
  the baseline so a resumed run's old journals cannot trigger an immediate kill.

## Core-loop placement

**② the nightly improvement loop's evidence** — a hang currently turns a run into no ledger and
no verdict. The supervisor turns it into a recorded interruption the operator can resume. The
reward (①), the gate (③) and the report (④) are untouched; no number is produced.

## Contradictions / risks

- **Containment, not a fix.** The root cause (MPS OOM/mask path) remains. The finding's sentence
  "the defect must be fixed before any next night" becomes "must be contained"; the write-up says
  so rather than claiming a fix.
- **A legitimate long verification could look idle.** The night's `--timeout 900` is per
  verification, and `R = 3` retries plus repair can spend over an hour without a journal write; a
  5400 s default clears that worst case. The flag is operator-declared, and the default is stated.
- **A child killed by an unrelated signal** (OOM killer) is a failure, not a stall; the parent
  returns 1 and does not write a stall marker. Only the parent's own timeout writes one.
- **The marker is local evidence**, under the gitignored run home; it is never published. It
  records the operator-declared `recorded_on`, not a generated date.
- **No new CLI exit code.** A stall is a refusal the operator can fix by resuming (2); a child
  failure keeps its code; a successful child returns 0/1/3 as before.

## Affected areas

`src/whetstone/loop/supervise.py` (new, stdlib only), `src/whetstone/loop/night.py` (bind the
supervisor + the published-root refusal), `src/whetstone/cli.py` (`--supervise`,
`--stall-seconds`, pass the raw argv, delegate), tests for the pure supervisor and the CLI, the
Torch sheet + guard, and the write-up.
