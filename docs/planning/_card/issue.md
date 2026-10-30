# feat mps-stall-supervisor

**Source:** inline brief from the `whetstone-next` alternate (2026-10-30), grounded in the
`torch-mps-series` finding.

## Brief

The 8B night hit an MPS out-of-memory on the public task after ~35 h and hung; a resume failed on
a corrupted attention mask, and a second resume hung. The 14B NF4 pre-flight hung on the eighth
draw in an uninterruptible Metal wait (`_local_scalar_dense_mps`); the 900 s draw timeout could
not fire because the process was not runnable. The finding's conclusion: the defect must be fixed
before any next night, and a probe/night must not be lost to it.

Add an optional `--supervise` (with `--stall-seconds`) to `whetstone run --night`. The parent
process supervises the real night as a child in its own process group, watches the run's per-draw
journal mtimes, and if no journal is written for the declared interval, kills the child group,
writes a `whetstone-stall/1` marker under the gitignored run directory, and exits 2 with a named
message. A healthy child's exit code is passed through unchanged; a resumed run is not killed for
its old journals. With no `--supervise` the night is byte-for-byte today's night.

This contains the hang; it does not fix the root cause (the MPS/transformers mask path). No probe
or night is run by this unit.

## Acceptance

- `whetstone run --night --supervise --stall-seconds 3600` runs the night as a child and returns
  its exit code; a stall kills the child group and writes `runs/<id>/stalled.json` (schema
  `whetstone-stall/1`, run id, declared date, stall seconds, child pid, last journal, last write
  ns, observed seconds, signal), then returns 2.
- A healthy child that writes journals and exits is passed through; no marker.
- A child that exits 1/3 is passed through; a child killed by an unrelated signal is a failure (1).
- A resumed run with old journals is not killed before the interval; the spawn is the baseline.
- `--stall-seconds` without `--supervise` is a usage error; the child argv has the supervisor flags
  stripped so it cannot recurse.
- The Torch sheet's probe and night blocks pass `--supervise --stall-seconds 3600`; the guard pins
  them. The full suite, mypy and ruff are green. The reward, gate, corpus, held-out document,
  `K`, `R` and the § 10.25 inputs are untouched.
