# Spec — measurement-door (aspect 2 of baseline-measurement)

**PRD:** `../prd.md`. **Branch:** `feat/baseline-measurement/aliz`. This aspect is the door
that scores the single baseline checkpoint on the held-out split — `run_gate` for one side.

## Problem slice and user outcome

The § 3 baseline must be **scored** — the untrained base's patches on the 12 held-out tasks
plus source A, through both verifiers, with the gate's liveness discipline, so the committed
baseline `solved`, coverage and `N` are measured exactly once. Nothing today scores a single
checkpoint: the gate compares two, and its `SideCounts` carry no `N`
(`gate.py:290-317, 1116-1125`). The user outcome: `python -m whetstone.loop.baseline` runs the
measurement, writes its evidence to a gitignored home, and refuses a second measurement of the
same series by name.

## In-scope requirements

1. **`baseline_engine`** — the one new machine seam, in `src/whetstone/loop/baseline.py`:
   loads `weights.local_dir` at the checkpoint's revision **without** an adapter path (the
   untrained base has none), wrapped in gate's `_CheckpointGenerator` **by identity**
   (`gate.py:487-524`) with `sampler_for(1)`'s greedy sampler **by identity** — so a baseline
   draw and a gate eval are one experiment. Every `mlx` import function-local; the factory is
   smoke-tested only (exists, callable, no `mlx` import at module scope), never invoked by
   tests — every test injects the stub engine (the `gate_engine` precedent, `gate.py:453-455`).
2. **The measurement core `measure()`** — the gate's order of operations, one side:
   `_refuse_published_root(runs, "--runs")` by identity (`night.py:617-639`) → `HF_HUB_OFFLINE`
   → heldout document through `read_document` + `document_digest_of` **by identity** →
   task roots (`load_task_roots`, `load_tasks` by identity) → held-out tasks via gate's
   `_heldout_tasks` **by identity** (the unknown-id refusal holds) → `verify_checkpoint` by
   identity → `load_weights` → `_base_for` **by identity** (the `NoBaseWeights` posture) →
   engine → `_CompletionRecorder` → `_score_side` **by identity** over `(*heldout_tasks,
   *public_tasks)` → `_retry_side` **by identity** over held-out tasks only (`RETRY_COUNT` by
   identity; source A scored in full, unretried and stated — the gate's own discipline,
   `gate.py:1007-1009`).
3. **Counts via `report.tally` by identity** (`report.py:425-452`) over the post-retry
   rollouts — the one place each published figure is defined, and the only place `N`
   (`weaker_wins`) exists (`report.py:443-447`): `denominator`, `solved`, `unverified`,
   `covered`, `failed`, `weaker_wins`. The source-B headline `N` is over the **held-out**
   rollouts; source A's weak-vs-strict differential is carried per-instance, never as a rate
   (`PREREGISTRATION.md:149-155`).
4. **Evidence document** (gitignored `runs/<run-id>/`): per-task rollouts (task_id, outcome,
   strict/weak statuses, prompt_sha256, completion_sha256, seconds), the retry facts (the
   declared `R`, per-task `before`/`after`/`retries_used`, the set that outlasted the budget),
   the counts, tool versions — hashes and verdicts, **never contents** (locality canary; the
   gate's promotion-record discipline, `gate.py:711-784`).
5. **Measured-once guard (write side) + the minimal artifact reader**:
   `read_series_identity(path)` — fail-closed read of the committed artifact's `schema`,
   `checkpoint.digest` and `heldout.document_digest` (unreadable/absent/wrong-schema → refused
   by name, never treated as absent). `measure()` refuses a second measurement when an
   artifact exists at `--out` whose series identity matches the current run's (checkpoint
   digest + held-out document digest) — naming the first artifact. A **different** series (a
   changed pinned input, e.g. a new base revision) is § 3's legitimate new series
   (`PREREGISTRATION.md:133-135`), allowed, with the change recorded in the new artifact.
   Aspect 3's full loader composes this reader by identity rather than re-reading.
6. **The module door** (`python -m whetstone.loop.baseline`): flags `--weights`, `--checkpoint`,
   `--heldout`, `--tasks` (repeatable roots), `--public`, `--runs`, `--workspace`, `--out`,
   `--timeout`, `--recorded-on` (an input, never the clock), `--run-id` (operator-declared),
   `--pool`, `--max-tokens`. Refusals → exit 2; a completed measurement → exit 0 **whatever
   the score** (coverage is disclosed, never a failure — the baseline is the anchor, not a
   verdict). `--out` refused under a gitignored root by name (the `refuse_committed_out`
   posture, `heldout.py:667-689`); `--runs` refused under a published root
   (`_refuse_published_root` by identity); all writable paths absolute (the runbook-guards
   discipline).
7. **Killed-run behavior, stated**: the artifact is written only at the end of a successful
   measurement, so a killed run leaves gitignored evidence and no artifact; a re-run uses a
   fresh `--run-id`, and a half-written artifact is refused by `read_series_identity` by
   schema, never repaired (the gate's stated behavior).

## Out-of-scope boundaries

- The committed artifact's **writer and full loader** — aspect 3 (`reports/baseline-measurement/`,
  schema `whetstone-baseline/1`).
- Any change to the gate's modules, the reward path, or `cli.py` (this door is a module
  door — the partition guard's documented-edge count is untouched).
- The control arm (measurement-only, per the PRD decision), and the capacity probe (the
  32B's fit is already measured by the larger-base arm).

## Acceptance criteria (test-first; refusals watched failing first)

1. `baseline_engine` is callable, function-local-`mlx`, and constructs a `Generator` whose
   sampler is `sampler_for(1)` by identity (smoke test); a stub engine drives every other test.
2. `measure()` scores held-out + source A, and the retry discipline fires **only** on
   `_UNCOVERED` outcomes (a FAIL stays FAIL — the seam is not credulous), budget `R` by
   identity from `gate.RETRY_COUNT`.
3. The counts equal `report.tally`'s over the same rollouts, `N` included (`weaker_wins` by
   identity); source A's per-instance weak/strict outcome is carried, never a rate.
4. Refusals: `--runs` under `reports/`; `--out` under a gitignored root; a checkpoint whose
   base the weights root does not hold (`NoBaseWeights`); a held-out membership id matching no
   loaded task (the loader's refusal, named with the loaded ids) — each exit 2 with the
   refusal named.
5. Measured-once: a same-series artifact already at `--out` → refused, naming the first
   artifact; a different-series artifact (different checkpoint digest) → allowed, the change
   recorded; an unreadable artifact at `--out` → refused by name, never treated as absent.
6. The evidence document carries hashes and verdicts only — the locality canary planted in a
   task's held blob/problem statement cannot reach it, and the runs home is asserted
   gitignored.
7. `--recorded-on` is an input (a run without it is refused); two invocations with the same
   inputs produce byte-identical evidence (determinism).
8. The AC2 pins and the partition guard hold (no `cli.py` change, no reward-path change).

## Dependencies and sequencing

Aspect 2 of 4 (after `baseline-checkpoint`, before `baseline-report`). Consumes:
`write_baseline_checkpoint`/`Checkpoint.untrained` (aspect 1, landed); gate's private scoring
and retry pieces **by identity**; `report.tally`. Aspect 3 consumes `measure()`'s result and
`read_series_identity` by identity.

## Open questions / risks

- **`mlx_lm` without `adapter_path`** — the one seam the tree has never exercised
  (`gate_engine` always passes it, `gate.py:472-476`). If `mlx_lm==0.31.3` refuses a
  base-only load, the fallback is the stub adapter written by the baseline writer — decided
  at the smoke test, never a loosened verifier.
- **The engine's `label`**: `baseline:{digest[:12]}`, matching the gate's side-label shape.
- **Series identity** is exactly `(checkpoint digest, held-out document digest)` — the
  environment pins and tool versions are recorded in the artifact's provenance (aspect 3) and
  are part of § 3's pinned inputs, but the *refusal* keys on the two digests; a change to
  either is the § 3 invalidation trigger in code.