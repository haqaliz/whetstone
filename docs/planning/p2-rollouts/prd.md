# PRD — p2-rollouts

**Written:** 2026-08-19 (planning, before any rollout). **Slug:** `p2-rollouts` · **Branch:**
`feat/p2-rollouts/aliz`. The unit is P2's first slice (`docs/ROADMAP.md:393-407`), routed here by
the pre-committed fork rule (`docs/planning/larger-base-arm/prd.md:45-53`, applied at
`finding.md:47-53`). Acceptance criteria are the ROADMAP's P2 exit criteria, quoted verbatim in
§ Goals.

## Problem statement

The harness can measure bases but cannot train anything. The bake-off's entire decode rule is one
greedy attempt per (candidate, task) with no seed (`src/whetstone/bakeoff/run.py:133-137`) —
deliberately, per P1's D3 (one greedy attempt for comparability). The larger-base arm then produced
the **first nonzero strict-PASS yield the harness has ever measured** (`finding.md:41-43`), which
is the fork rule's evidence that training data exists. But nothing exists to *collect* it: no
sampling, no strict-PASS dataset, no training step, no checkpoint, no `run --night` door. The
project's namesake — the nightly improvement loop (core-loop element ②) — is unbuilt, and the
first honest number (P4) is unreachable without it.

## Goals & success metrics

The ROADMAP's P2 exit criteria, verbatim, are this unit's acceptance criteria:

1. `uv run whetstone run --night` produces `runs/<id>/` with a ledger and a candidate under
   `checkpoints/<id>/` (`docs/ROADMAP.md:399-400`)
2. A test asserts **every** example in the training set carries a recorded strict-PASS verdict
   (`:401-402`) — `UNVERIFIED` is never training data
3. A determinism test: same seed → byte-identical training set (`:402`)
4. The run ledger records pinned seeds, model revision, task set, tool versions (`:403`)

Additional success properties this unit commits to:

- **Locality.** The training set is the user's private donor code: it lives under gitignored roots
  only; the committed side is hashes and verdicts, never contents (the `tasks/ledger.py:74-96`
  discipline).
- **Disclosure.** The run's output reports the unverified count and the coverage beside the
  training-set size, from the first eval onward (`docs/ROADMAP.md:430-435`).
- **Reward path immovable.** `src/whetstone/verify/`, `src/whetstone/bakeoff/patch.py`,
  `src/whetstone/bakeoff/attribution.py` stay byte-identical to `origin/master`
  (`tests/bakeoff/test_format_hardening_frozen.py:35-39`).
- **No judge, no loosened check.** The dataset is selected from the verifier's own records
  (`report.tally`: `outcome is Outcome.SOLVED`, the one definition, `report.py:425-452`). Low
  yield is answered by raising `k`, never by weakening the verifier (`docs/ROADMAP.md:405-406`).

## Confirmed decisions (interview, 2026-08-19)

- **Scope:** the whole P2 slice, decomposed into three aspects (`sampling`, `sft`, `night-door`).
- **Package home:** new `src/whetstone/loop/`, partitioned `EXEMPT` on the `bakeoff` precedent
  (imports `mlx_lm` legitimately; the reward path can never reach it —
  `tests/test_reward_path_scope_is_partitioned.py:100-117,210-230`).
- **k:** a declared constant `K = 8` in code, pre-committed here before any rollout — never a
  per-run knob (M7b: per-task/per-run knobs are how a harness ends up optimising on its own scored
  outcome). Rationale: a small multiplier of the current k=1 probe; the run's own yield-vs-unverified
  read is the evidence, and "raise k" remains the named response to low yield. **No model figure is
  asserted by this number.**
- **Seeds:** one run seed; per-attempt seed `= hash(run_seed, task_id, attempt)` — deterministic,
  recorded in the ledger. **The sampling index *is* the attempt index**: draw i of k is attempt i
  and the seed derives from it. The `Retry` wrapper composes **outside** a single draw — a retry
  reuses the draw's seed (its prompt is a pure function of `(first prompt, trigger)`,
  `retry.py:81`), so retries consume no new seed and the recorded attempt numbering is unambiguous
  (`transcript.py:73-117`'s one-based within-(candidate, task) semantics). mlx-lm 0.31.3 samples
  from **global** `mx.random` state (no `seed=` kwarg: `mlx_lm.sample_utils.categorical_sampling`),
  so the sampled generator applies the seed before each draw and draws serially; the determinism
  test runs the same seed twice and asserts a byte-identical dataset.
- **SFT capacity:** a D7-style declared probe (small N of training steps, stated headroom against
  the 36 GiB) gates the first full-night SFT — declared before it runs, never after
  (the arms' discipline; `finding.md:25-31` measured inference fit only).
- **Checkpoint identity:** `checkpoints/<id>/` is hashed weights-style — a `provenance.json` plus
  re-hashable files (the `weights.py:184-230` `verify()` pattern) so P3's gate can re-verify the
  bytes it compares.
- **Contract:** the loop runs the hardened contract § 10.4 discloses (retries on, retrieval
  oracle, the five declared dev ids excluded; `docs/planning/larger-base-arm/runbook.md:120-149`),
  through the **same `GenerationContract` machinery** — a new contract shape would be a § 10
  amendment, never silently new.

## User personas & scenarios

Solo founder (operator) running the machine overnight. Scenario: run `whetstone run --night` from
the primary checkout; wake to `runs/<id>/` (journal, ledger, transcript), a strict-PASS dataset of
recorded verdicts, and `checkpoints/<id>/` holding a hashed LoRA adapter whose provenance names the
base revision, dataset digest, seeds, and training args. The dataset is the first training data;
nothing it contains may later be quoted as held-out (`PREREGISTRATION.md:242-247`).

## Requirements

### Must-have

- `src/whetstone/loop/` sampled generator: `k` attempts per (task, source) under the frozen
  contract, per-attempt seed applied before each draw, greedy-retained-by-default semantics for the
  control arm untouched (control arm stays the bake-off's own one-attempt probe — `control.py:340-469`).
- Strict-PASS dataset extraction reading `report.tally`'s `Outcome.SOLVED` **by identity** — never a
  re-derived notion of "solved".
- A dataset record that is deterministic given (run seed, contract, task set, tool versions) and
  the exit-criterion-2 test asserting every example carries a recorded strict-PASS verdict.
- A run ledger (hashes and verdicts, never contents) recording pinned seeds, model revision, task
  set, tool versions — the pre-registered pinned inputs (`PREREGISTRATION.md:131-132`).
- LoRA-SFT via `mlx_lm.lora.train` (pinned `mlx-lm==0.31.3`), dataset in the library's local format
  (`train.jsonl`/`valid.jsonl`/`test.jsonl`, `text`/`messages`), adapter + config + provenance
  emitted under `checkpoints/<id>/` and hashed weights-style.
- A D7-style capacity probe in the SFT aspect, declared before the full night, gating it.
- `whetstone run --night` as a new subcommand dispatching into `loop` (the `mlx_lm`-importing body
  never lives in `cli.py` — `run.py:7-13`), honoring the existing 0/1/2/3 exit-code contract
  (`cli.py:53-74`).
- The unverified rate and coverage disclosed beside the training-set size in the run's output.

### Should-have

- Per-source breakdown in the ledger/dataset (source B headline; source A always scored in full —
  both published together, `PREREGISTRATION.md:142-147`).
- A `valid` split for SFT drawn deterministically from the strict-PASS dataset (never from
  `UNVERIFIED`), with its own recorded verdicts.
- The runbook/guard holding the night command's shape, on the `test_larger_base_runbook_guards.py`
  precedent.

### Nice-to-have

- A dry-run `--probe` mode for the loop (small k, declared) mirroring the bake-off's probe
  short-circuit (`run.py:598-610`).

## Technical considerations

- **Reuse by identity, never copy.** The loop composes: `freeze`/`Sealed`/`ContractChanged`
  (`run.py:418-473`), `Weights.verify()` (`weights.py:184-230`), `control.probe` + `sweep.rankable`
  (`sweep.py:160-183`), `report.tally` for `Outcome.SOLVED`, the transcript locality rules
  (`run.py:1009-1030`). The one seam that is genuinely new is the sampled generator, and it is
  exactly what the one-method `Generator` protocol was designed to allow (`generator.py:15-22`).
- **Partition guard.** `src/whetstone/loop/` is added to `EXEMPT` with a written reason; the
  one-way dependency assertion (`test_reward_path_scope_is_partitioned.py:356-389`) extends to it.
- **mlx-lm 0.31.3 surface (verified at the pinned version).** Sampling: `mlx_lm.generate(model,
  tokenizer, prompt, ..., sampler=make_sampler(...))`; `categorical_sampling` reads global
  `mx.random` state. LoRA: `mlx_lm.lora.train(model, optimizer, train_dataset, args=TrainingArgs(...))`
  in `mlx_lm.tuner.trainer`; datasets via `mlx_lm.tuner.datasets.load_local_dataset` (directory of
  `train.jsonl`/`valid.jsonl`/`test.jsonl`). Adapter output is an adapter file
  (`adapters.safetensors`) + config.
- **Capacity.** Inference probe showed ~8 GiB resident for the 18.4 GB snapshot (`finding.md:25-31`).
  Training adds optimizer/adapters/grads — unmeasured, hence the mandated probe.
- **Determinism.** Per-attempt seeds are applied to global MLX state in a fixed serial order; the
  dataset extractor is pure over the recorded verdicts. The determinism test (exit criterion 3) is
  the guard.
- **Environment pins.** Each task verifies under its own manifest `environment`; the loop inherits
  `Interpreters` (`scoring.py:287-354`) unchanged.

## Risks & open questions

- **SFT memory is the nearest feasibility risk** — gated by the declared probe; a failed probe is a
  published capacity finding, never worked around (the arms' rule).
- **Small dataset.** k=8 over 61 private tasks at ~6 tok/s is a long night and may still yield a
  small strict-PASS set. The response is raise k, never a loosened check; a tiny dataset is a valid
  outcome (P4 has no pivot signal). **The degenerate-valid-split rule is pre-committed in the SFT
  spec (aspect 2): a valid split below a floor fraction of the strict-PASS set is *no valid split*,
  stated in the checkpoint's provenance — never a silently-validated checkpoint.**
- **Global-state seeding.** `mx.random` is process-global; the serial seed-apply discipline must
  hold or the determinism test fails loudly. Residual: another process sharing the device could
  perturb draws — a documented machine-level constraint (serialize runs, the worktrees skill's GPU
  rule).
- **`run --night` touches a guarded root (`cli.py`).** The subcommand is thin dispatch only; all
  `mlx_lm`-reaching code lives in the EXEMPT `loop` package.
- **Open:** the valid-split fraction; the night's token budget; whether the SFT aspect's probe N and
  the night's k interact (resolved in the aspect spec).

## Out of scope

- The never-regress promotion gate (P3), the held-out split (§ 7.1, P3), the first honest number
  and its report home (P4), the dashboard, distillation, a second task family, Linux portability.
- Any looser verifier, any LLM-judge reward, any change to `src/whetstone/verify/`, `patch.py`,
  `attribution.py`, or `src/whetstone/tasks/`.
- Base selection: § 7.3 closes only by a Type 1 amendment before P3's baseline; this unit names the
  32B as the candidate with evidence and runs it, nothing more.