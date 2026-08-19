# Understanding — p2-rollouts

**Dig date:** 2026-08-19 · **Branch:** `feat/p2-rollouts/aliz` · **Dig agents:** one explore agent
mapping the whole P2 surface (`run.py`/`transcript`/`control`/`weights`/`scoring`/`verify`/`tasks`/
`cli.py`, the AST guards, the AC2 pins, `PREREGISTRATION.md`), verified in the worktree at
`origin/master`; the mlx-lm LoRA/generation surface read from the installed `mlx-lm==0.31.3`
(the pinned version).

## What this work really is

P2's first slice (`docs/ROADMAP.md:393-407`) — the **nightly improvement loop**, core-loop element
②, the first code this project ships that produces *training data*. The fork rule pre-committed in
the larger-base PRD routed here: yield > 0 with control intact → "the next unit is P2's first slice
(rollouts + expert iteration), and the finding names the 32B as the first candidate with evidence"
(`docs/planning/larger-base-arm/prd.md:45-53`, applied at `finding.md:47-53`). The improvement
method and runtime are locked, not open: "sample *k* per task, keep only strict-PASS rollouts,
LoRA-SFT on those. Every training example is verified-by-construction" — MLX end-to-end
(`docs/planning/roadmap-and-task-family/prd.md:61,63`).

The unit's acceptance criteria are the ROADMAP's P2 exit criteria, verbatim:

- `uv run whetstone run --night` produces `runs/<id>/` with a ledger and a candidate under
  `checkpoints/<id>/` (`docs/ROADMAP.md:399-400`)
- a test asserts **every** example in the training set carries a recorded strict-PASS verdict
  (`:401-402`)
- a determinism test: same seed → byte-identical training set (`:402`)
- the ledger records pinned seeds, model revision, task set, tool versions (`:403`)

## Grounding (file:line, re-verified)

- **The contract the loop runs under:** the hardened contract § 10.4 (retries on, retrieval
  oracle, the five declared dev ids) — `docs/planning/larger-base-arm/runbook.md:120-149`
  (denominator 61 private + 1 public). Weights pinned at
  `d1e3b690c8e225d7795bccddf971ca6be68b2012` (`finding.md:20-22`).
- **"Solved" has exactly one definition:** `record.outcome is Outcome.SOLVED` in `report.tally`
  (`src/whetstone/bakeoff/report.py:425-452`); `Rollout` records at `scoring.py:133-199`. The
  training-set extractor must read this by identity, never re-derive it.
- **Control discipline:** `sweep.rankable` refuses a run whose harness is unproven
  (`sweep.py:160-183`) — training data must come from runs with INTACT control.
- **Pinned inputs:** seeds, model revision, task set, environment pins, tool versions are the
  pre-registered pinned inputs (`PREREGISTRATION.md:131-132`); the ledger must record exactly
  these. P2's training data is **not** the held-out split — § 7.1 is open until P3
  (`:242-247`), and nothing trained on may later be quoted as held-out.
- **AC2 pins:** `src/whetstone/verify/`, `src/whetstone/bakeoff/patch.py`,
  `src/whetstone/bakeoff/attribution.py` byte-identical to `origin/master`
  (`tests/bakeoff/test_format_hardening_frozen.py:35-39`). The reward path does not move.

## What the dig surfaced (the unit's real content)

1. **The generator seam does not sample — this is the central seam.** The bake-off's entire
   decode rule is one greedy attempt per (candidate, task), with `_SEEDS` recording *why there is
   no seed* (`run.py:133-137`); `generator.py:46-70` exposes one method (`generate(prompt)`); the
   sampler is fixed at construction (`mlx_runtime.py:118-131,134-142`). P2's "sample k per task
   with pinned seeds" is a **new Generator implementation** (seeded categorical sampling), and
   the one-method seam plus the protocol's determinism note (`generator.py:15-22`) were designed
   exactly so this can be added without widening. Pinned caveat: mlx-lm 0.31.3's sampling draws
   from **global** `mx.random` state — `categorical_sampling` takes no seed — so per-attempt
   seeds must be applied by the wrapper before each draw (`mlx_lm.sample_utils.categorical_sampling`,
   `make_sampler`; documented at `docs/planning/p1-baseline-bakeoff/understanding.md:211-213`).
   Seeded-global-state determinism needs an ordering discipline (one sampler instance, serial
   draws, seed applied per attempt) for the byte-identical re-run test to hold.
2. **`whetstone run --night` touches a guarded root.** `cli.py` is in `GUARDED_ROOTS`
   (`tests/test_no_inference_on_reward_path.py:104-109`), and `run.py:7-13` documents why the
   bake-off is deliberately *not* a subcommand: an `mlx_lm`-importing implementation must live in
   an EXEMPT package, never in `cli.py`. A new `src/whetstone/loop/` package forces a partition
   decision (`tests/test_reward_path_scope_is_partitioned.py:100-117,210-230`): EXEMPT with the
   `bakeoff` precedent (imports mlx_lm legitimately, one-way dependency — the reverse import is
   banned at `:356-389`), or land the loop inside `bakeoff/` itself. The existing `cli.py`
   subcommand surface is exactly two commands (`verify`, `mine` — `cli.py:122,142`) and the
   exit-code contract is 0/1/2/3 (`cli.py:53-74`).
3. **Training data is the user's private code — locality is inherited, not invented.** The
   transcript is refused under `--out` (`run.py:1009-1030`, `TranscriptNotPrivate`); the
   gitignored roots are pre-declared including `/checkpoints/` and `/runs/` (`.gitignore:20-24`,
   `autopsy.py:716`); the committed-evidence shape is `tasks/ledger.py:74-96` — "hashes and
   verdicts, never contents". The training set and any derived artifacts obey the same rule:
   gitignored roots only, the committed side is hashes/verdicts. The checkpoint that is *the*
   candidate is run state, not a publishable artifact.
4. **The unverified rate is a selection problem before it is a report problem.** The 32B runs
   at ~6 tok/s against the 900 s timeout and left a material minority of tasks without a verdict
   (`finding.md:76-81`). Selection must distinguish `Outcome.SOLVED` (train) from everything
   else, with `UNVERIFIED` explicitly **not** trainable — the exit-criterion test is exactly this
   guard — and the run's output must disclose the unverified count beside the training-set size
   (coverage stays in the denominator; `docs/ROADMAP.md:423-435` is the P3 discipline, but the
   disclosure starts here).
5. **LoRA training memory is unmeasured — the D7 pattern applies to this slice, not the arm.**
   The 32B probe pass measured *inference* fit (~8 GiB resident for the 18.4 GB snapshot;
   `finding.md:25-31`). Training adds optimizer/adapters/grads. mlx-lm 0.31.3's LoRA surface is
   confirmed present: `mlx_lm.lora.train(model, optimizer, train_dataset, ...)` with
   `TrainingArgs` (batch_size, iters, max_seq_length, adapter_file, grad_checkpoint,
   grad_accumulation_steps) in `mlx_lm.tuner.trainer`; the dataset format is a directory of
   `train.jsonl`/`valid.jsonl`/`test.jsonl`, one JSON object per line (`text` or `messages`
   format), via `mlx_lm.tuner.datasets.load_local_dataset`. A D7-style capacity probe (N small,
   declared headroom) must precede the first full-night SFT. **Open question for the interview:
   does this unit's first slice end at the dataset + `run --night` door, with the SFT aspect
   carrying its own probe, or is one unit responsible for the full loop?** The ROADMAP exit
   criterion 1 requires a checkpoint under `checkpoints/<id>/`, so the SFT is inside P2's scope;
   the unit may decompose into aspects.
6. **No `k` is pre-committed anywhere.** The roadmap says "sample *k* attempts per task"
   (`docs/ROADMAP.md:395`) and the pivot names "raise *k*" (`:405-406`), but no number exists in
   any planning file. The interview must decide how k is set (a declared constant in code, pre-commit
   discipline like the runbook's `N = 3` probe values — declared before the run, never after) and
   how per-attempt seeds derive from a single run seed (seed = hash(run_seed, task_id, attempt) or
   an explicit sequence — must be recorded in the ledger for the determinism test).
7. **The contract seal, retries, and weights pinning are inherited by composition, not
   re-implemented.** `freeze()`/`Sealed`/`ContractChanged` (`run.py:418-473,199-262`),
   `Retry` (off by default, `--retries`), `Weights.verify()` re-hashes every run (`weights.py:184-230`),
   `GenerationContract` carries the retry trio + retrieval (`report.py:175-217`). A loop run whose
   prompts are not the frozen set must refuse before any generation — same discipline, and the
   loop's contract must be **the same GenerationContract machinery** so its figures are comparable
   to the arm's (the D6 argument; any new contract shape is a § 10 amendment, never silently new).
8. **Determinism scope:** the exit criterion is "same seed → byte-identical training set" — the
   *set*, not the whole run. Seeds + the frozen contract + the offline environment pins make the
   set deterministic; the test must reproduce it with a stub generator (no model) and, for the
   real runtime, the run's own journal must record the seed-to-attempt map.

## Affected areas

- New: sampled generator (seeded, k attempts) — either in `bakeoff/` or a new EXEMPT package.
- New: training-set extraction + ledger (hashes/verdicts, never contents) + the `run --night` door.
- New: LoRA-SFT adapter (dataset builder, train invocation, adapter output under `checkpoints/`).
- `cli.py` (guarded): the `run --night` subcommand dispatch — the body stays EXEMPT.
- `tests/`: exit-criteria tests (strict-PASS-only, determinism, ledger fields), partition-guard
  extension if a package is added, locality tests, adversarial selection tests (UNVERIFIED/FAIL
  rollouts are refused as training data).
- `.gitignore` already pre-declares the roots; `docs/planning/{slug}/` planning artifacts.
- **Untouched:** `src/whetstone/verify/`, `patch.py`, `attribution.py` (AC2 pins); the reward
  path stays byte-identical.

## Core-loop placement

Element ② (nightly improvement loop) — the first real production of training data, verified by
construction. Element ③ (gate) is untouched — no promotion logic here, and `UNVERIFIED` is never
training data, so it can never become a hidden win. Element ⑤ (local) by construction: mlx-lm on
the Mac, weights already local, dataset under gitignored roots, nothing leaves the box. The reward
stays execution-grounded: selection reads `Outcome.SOLVED` from the verifier's own records; no
model opinion anywhere on the path.

## Open questions for the interview

- **Q1 — Unit scope:** does this unit deliver the whole P2 exit-criteria set (sampling → dataset →
  SFT → `run --night`), or slice 1a (sampling + dataset + ledger + determinism) with the SFT as a
  second aspect within the unit? (Recommended: one unit, two aspects — dataset first, SFT second —
  each with its own spec; the D7-style capacity probe belongs to the SFT aspect.)
- **Q2 — Where the loop lives:** new `src/whetstone/loop/` (EXEMPT, `bakeoff` precedent) vs.
  inside `bakeoff/`? (The bakeoff is documented as the operator tool, and the loop is product
  surface; but EXEMPT with one-way dependency is the established mechanism either way.)
- **Q3 — `k` and seeds:** what k (declared constant, pre-committed, no per-run knob that a run
  could tune) and how per-attempt seeds derive from the run seed?
- **Q4 — The SFT capacity probe:** D7-style declared probe (N, headroom) before the first full
  night — same declaration discipline as the arms?
- **Q5 — Checkpoint identity:** the trained adapter under `checkpoints/<id>/` — does the ledger
  hash it (weights-style `verify()` re-hash) so a checkpoint is reproducible evidence, and does
  its provenance name the base revision + dataset digest + training args?
