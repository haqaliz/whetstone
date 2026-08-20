# Spec — sampling (aspect 1 of p2-rollouts)

**PRD:** `../prd.md`. **Branch:** `feat/p2-rollouts/aliz`. This aspect makes the harness *sample*
and *select*: the seeded k-attempt generator, the strict-PASS dataset, the run ledger, and the
determinism proof. It does not train and does not ship the CLI door (aspects `sft`, `night-door`).

## Problem slice and user outcome

The bake-off produces one greedy attempt per (candidate, task) and no training data. This aspect
turns "the 32B can solve a task" (`finding.md:41-43`) into a repeatable, verifiable selection
machinery: `k` seeded attempts per task, only rollouts the STRICT verifier passed kept, everything
recorded so a re-run with the same seed is byte-identical. The user outcome is the first training
set the project has ever held, proven to be strict-PASS by construction.

## In-scope requirements

1. **Seeded sampled generator** in `src/whetstone/loop/`: a `Generator` (`generator.py:46-70`)
   implementation that draws `k` attempts per prompt using `mlx_lm`'s categorical sampler, applying
   `seed = hash(run_seed, task_id, attempt)` to global `mx.random` before each draw, serially. **The
   sampling index is the attempt index** (draw i of k is attempt i; `transcript.py:73-117`'s
   one-based within-(candidate, task) semantics), and the `Retry` wrapper composes **outside a single
   draw** — a retry reuses the draw's seed (its prompt is a pure function of `(first prompt,
   trigger)`, `retry.py:81`) and consumes no new seed, so a (candidate, task) key has exactly one
   seed-to-attempt numbering. The sampler and the per-attempt seed derivation are recorded in
   provenance (the `mlx_runtime.py:134-142` discipline: what generates is fixed at construction and
   disclosed). Greedy behavior for k=1 must equal the bake-off's current greedy decode
   (`mlx_runtime.py:118-131`).
2. **k as a declared constant** `K = 8` in `loop` code (pre-committed; never a run knob). A test
   asserts the constant exists and is used, so a later run cannot silently vary per-attempt sampling
   (`test` names `K` and the `seed` derivation).
3. **Strict-PASS dataset extraction** reading `Outcome.SOLVED` **by identity** from
   `report.tally` (`report.py:425-452`) / `Rollout` records (`scoring.py:133-199`) — never a
   re-derived "solved". The dataset record carries: task_id, source, prompt_sha256, completion
   hash, the recorded verdict (strict PASS), the per-attempt seed, and the control-arm status of the
   run it came from.
4. **Selection rule, explicit and adversarial:** only `outcome is Outcome.SOLVED` is trainable;
   `UNVERIFIED`, `UNPROVISIONED`, `NO_ORACLE`, `NOT_APPLIED`, `OUT_OF_SCOPE`, `NOT_SOLVED`,
   `NO_DIFF` are not. A test asserts the full classification is enumerated (the partition is
   complete against `Outcome`'s members) and that a synthetic `UNVERIFIED`/`FAIL` rollout is refused
   as training data.
5. **Run ledger** (`hashes and verdicts, never contents`, the `tasks/ledger.py:74-96` shape) under
   the run's gitignored `runs/<id>/`: run seed, `K`, per-task per-attempt seeds, model revision,
   task set (with the dev overlay), tool versions, per-source counts, unverified count, coverage —
   the pre-registered pinned inputs (`PREREGISTRATION.md:131-132`).
6. **Determinism test** (exit criterion 3, `docs/ROADMAP.md:402`): same run seed + frozen contract +
   stub generator → byte-identical dataset, run twice in the test. A second test asserts the
   per-attempt seed derivation is a pure function of `(run_seed, task_id, attempt)`.
7. **Control discipline inherited:** a run whose control arm is unproven (no `INTACT` probe,
   `sweep.rankable` refusal, `sweep.py:160-183`) produces no dataset — nothing trainable from an
   unproven harness.
8. **Dev overlay and both sources:** the five declared dev ids are excluded (`runbook.md:135-139`);
   source A scored in full; both sources' counts appear in the ledger (publish-together,
   `PREREGISTRATION.md:142-147`).

## Out-of-scope boundaries

- No training, no adapter, no checkpoint emission (aspect `sft`).
- No CLI changes (aspect `night-door`).
- No change to `src/whetstone/verify/`, `patch.py`, `attribution.py` (AC2 pins) or
  `src/whetstone/tasks/`; no change to `bakeoff/` reward-path machinery. The loop package is
  partitioned `EXEMPT` (PRD § Confirmed decisions) — the only committed change outside `loop/`
  and `tests/` is the partition-guard extension in `tests/`.

## Acceptance criteria (testable)

- AC1: `src/whetstone/loop/` is `EXEMPT` in `test_reward_path_scope_is_partitioned.py` with a
  written reason; the one-way dependency assertion covers it; `test_no_inference_on_reward_path.py`
  still passes.
- AC2: the seeded generator, with a stub engine, produces exactly `k` attempts whose recorded
  per-attempt seeds equal `hash(run_seed, task_id, attempt)` for every attempt (property test over
  several tasks).
- AC3: every dataset record has `outcome is Outcome.SOLVED` and a recorded strict `Status.PASS`
  (the exit-criterion-2 test, `docs/ROADMAP.md:401-402`); a synthetic non-PASS rollout is refused.
- AC4: determinism — same seed, twice, byte-identical dataset (exit criterion 3).
- AC5: the ledger records run seed, `K`, per-attempt seeds, model revision, task set, tool versions
  (exit criterion 4); a test asserts the fields are present and the ledger carries no file contents
  (a canary asserts no source-code text appears in the ledger).
- AC6: `uv run pytest` green; ruff and mypy over `src/` green.

## Dependencies and sequencing

- Depends on nothing unshipped; reuses `bakeoff` machinery by identity (freeze/seal, control,
  scoring, tally). The partition-guard extension lands with this aspect (it is the first thing a
  new package forces).
- Sequence: partition guard → sampled generator → dataset extraction → ledger → determinism tests.
- Feeds aspect `sft` (the dataset format it consumes) and aspect `night-door` (the run layout).

## Open questions / risks

- Whether per-attempt sampling must also record the *drawn tokens* (transcript-style) or only the
  completion hash. (Recommended: transcript-style recording, reusing the transcript codec — the
  determinism test then has a byte-level record to compare.)
- Global `mx.random` is machine-global: a concurrent process could perturb draws. Mitigation is the
  worktrees skill's serialize-the-GPU rule, stated in the runbook (aspect `night-door`), never a
  code fix inside this aspect.