# PRD — mps-stall-supervisor

**Unit:** `feat/mps-stall-supervisor/aliz`. **Source:** `docs/planning/_card/issue.md`.
**Understanding:** `docs/planning/mps-stall-supervisor/understanding.md`. **Status:** containment
for the recorded MPS hang; no probe or night is run.

## Problem statement

A night's process can hang in an uninterruptible Metal call. The 8B night hit an MPS OOM on the
public task after ~35 h and hung; a resume failed on a corrupted attention mask and a second resume
hung (`docs/planning/torch-mps-series/finding.md:42-61`). The 14B NF4 pre-flight hung on the
eighth draw; the 900 s draw timeout could not fire because the process was not runnable
(`:75-83`). An in-process timeout cannot break this; a parent process can. Today a hang loses the
run's final ledger and any remaining draws, and the operator has to notice by eye.

## Goals & success metrics

- `whetstone run --night --supervise --stall-seconds N` runs the night as a supervised child and
  returns its exit code when healthy.
- A journal-inactivity stall kills the child's process group, writes a `whetstone-stall/1` marker
  under the gitignored run home, and exits 2 with a named message.
- A resumed run is not killed for its pre-existing journals; the spawn is the baseline.
- With no `--supervise`, the night is today's night byte-for-byte.
- No reward, gate, corpus, held-out, `K`, `R` or § 10.25 input change; no new exit code.

## Requirements

### Must-have

1. **A pure supervisor** (`src/whetstone/loop/supervise.py`, stdlib only):
   - spawns a command with `start_new_session=True`;
   - polls the run's `draws/*.journal.jsonl` and `*.transcript.jsonl` mtimes;
   - uses `max(last_write, spawn_wall_ns)` as the baseline, so a resumed run's old evidence does
     not trigger an immediate kill;
   - when `now - baseline >= stall_seconds`, kills the process group with `SIGKILL`, writes the
     marker atomically, prints the reason, and returns 2;
   - returns the child's exit code when it exits (a negative signal code from an unrelated killer
     is a failure, 1);
   - kills the child on `KeyboardInterrupt` and re-raises.
2. **The marker** `runs/<run-id>/stalled.json`, schema `whetstone-stall/1`: `run_id`,
   `recorded_on` (operator input), `stall_seconds`, `child_pid`, `last_journal` (path or null),
   `last_write_ns` (0 for none), `observed_after_seconds`, `signal` (`SIGKILL`). Written
   atomically; never outside the run home.
3. **The night binding** (`src/whetstone/loop/night.py`): `supervise_night(...)` refuses a
   published `--runs` root by identity, strips the supervisor flags from the child argv, builds
   `[sys.executable, "-c", "from whetstone.cli import main; raise SystemExit(main())", *argv]`,
   and calls the pure supervisor. Reached through the existing `whetstone.loop.night` edge, never
   a new `cli.py -> whetstone.loop.supervise` edge.
4. **The CLI**: `run --night` gains `--supervise` (store_true) and `--stall-seconds <seconds>`
   (float, default 5400 when supervising). `main` passes the raw argv to `run_night`; the handler
   delegates to `supervise_night` when `--supervise`; `--stall-seconds` without `--supervise` is a
   usage error. The child argv has `--supervise` and `--stall-seconds` + value stripped.
5. **The sheet**: the Torch/MPS probe and night blocks pass `--supervise --stall-seconds 5400`;
   the guard pins the flags. The MLX sheet is untouched.
6. **Tests**: a healthy child passes through; a stalled child is killed and the marker written;
   a failure code passes through; an old-journal resume is not killed; an unrelated signal is a
   failure; the argv stripper; the CLI delegation and the `--stall-seconds` usage error; the
   sheet guard.

### Should-have

- A `stall:` disclosure line from the parent naming the marker and the resume instruction.
- The marker's `last_journal` path for the operator.

### Nice-to-have

- A per-draw generation timeout in the runtime. Declined: the Metal call is uninterruptible; the
  parent is the only reliable breaker.

## Out-of-scope

- Fixing the MPS OOM / corrupted attention mask / `_local_scalar_dense_mps` root cause.
- Any reward, gate, corpus, held-out, `K`, `R` or § 10.25 change.
- Running the probe or a night.
- A process supervisor for any other command.

## Risks & open questions

- **A legitimate long verification** can go over an hour without a journal write; the default
  5400 s clears the `--timeout 900` × retries worst case, and the operator can raise it. A stall
  at the boundary is a false positive; the resume replays the journals.
- **A child killed by the OS** (OOM killer) is a failure (1), not a stall; the parent cannot tell
  the cause apart from the signal code and does not write a stall marker.
- **`SIGKILL` of the process group** also kills the sandbox verification subprocesses; the run is
  resumed, and those task verdicts are recomputed. That is the correct trade for a hang.
- **The parent's own crash** leaves the child running; the parent is small and has no model code.
  A future `--detach` is not built.

## Aspect decomposition

One aspect: **`supervise-door`** — the pure supervisor, the night binding, the CLI, the sheet and
the tests.
