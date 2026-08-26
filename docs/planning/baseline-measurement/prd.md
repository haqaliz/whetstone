# PRD — baseline-measurement (P4 slice 1)

**Unit:** `feat/baseline-measurement/aliz`. **Source:** inline brief from the
`whetstone-next` handoff (2026-08-26), `docs/planning/_card/issue.md`. **Dig:**
`docs/planning/_card/understanding.md`. **Status:** P4 slice 1; P1–P3 shipped on `master`
(v0.8.0).

## Problem statement

`PREREGISTRATION.md` § 3 commits to a **pinned baseline checkpoint** — the untrained open
base, scored on the held-out set by the STRICT verifier, provenance committed alongside —
**measured once, re-measured never**, plus a baseline `N` (the untrained base's weak-vs-strict
differential) that a final `N` is compared against (`PREREGISTRATION.md:121-138`;
`docs/ROADMAP.md:494-504`). Every P4 figure is a delta from this baseline (`solved_final -
solved_baseline`, `PREREGISTRATION.md:57-64`), so without it **no honest number can exist**:
a final score alone answers nothing, and a final `N` without the baseline's cannot answer
"did the loop learn to cheat more?" (`PREREGISTRATION.md:107-109`).

Today the protocol is **unspent and unbacked by code**: no baseline door, writer, or artifact
exists anywhere in `src/whetstone/` (dig § 10.1). The gate runbook names the missing piece
explicitly — the baseline "needs a checkpoint the night deliberately does not write"
(`docs/planning/p3-promotion-gate/gate-runbook/runbook.md:25-28`; a night that selected
nothing writes no checkpoint at all). The night has not run; this unit ships the "before"
**before anything trains** (`docs/ROADMAP.md:496-498`).

## Goals & success metrics

- **A baseline checkpoint exists** — the untrained open base (the 32B the night runbook
  resolves: `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`), materialized as a
  `whetstone-checkpoint/1` directory, re-hashable through `sft.verify_checkpoint` by identity.
- **A measurement door exists** — `python -m whetstone.loop.baseline` scores the single
  checkpoint on the held-out source-B membership (12 of 66, `tasks/heldout/source-b.json`)
  **and** source A in full (`pallets__flask-4045`), both sources published together
  (`PREREGISTRATION.md:142-147`), with STRICT and WEAK both run per rollout so baseline `N`
  is measured (`report.tally`'s `weaker_wins`, the one N definition, `report.py:443-447`).
- **A committed baseline artifact exists** — `reports/baseline-measurement/`, schema
  `whetstone-baseline/1`, whose loader refuses a second measurement by name (measured-once
  guard, watched failing first).
- **The measurement is operator-executed, exactly once** — runbook scripts the GPU pass;
  the number is spent by the operator, never by the code.

Success is the machinery + guard + runbook landing test-first; the *number* is the operator's
single spend, and its value is not a success criterion (a zero is a valid, publishable
baseline — `docs/ROADMAP.md:470-471`).

## User personas & scenarios

- **The operator (the author).** Runs the baseline measurement once on the Mac (36 GiB
  Apple Silicon, MLX), exactly as every arm in this repository has been run: worktree →
  runbook → GPU pass → post-run chain. The scenario the runbook scripts.
- **The P4 report writer (a later slice).** Reads the committed baseline artifact as the
  "before" of every delta. Needs the provenance block complete (§ 3 pinned inputs) and the
  counts over their denominators.
- **A future reviewer of the pre-registration.** Must be able to check "measured once" from
  the tree: the committed artifact, the amendment/ledger state, and the guard that refuses a
  second measurement.

## Requirements

### Must-have

1. **Baseline-checkpoint writer** (`src/whetstone/loop/`, on the `sft.py` pattern):
   - Materializes the untrained base as a `whetstone-checkpoint/1` directory: `provenance.json`
     declaring `untrained: true` and `base: {repo_id, revision}` (the immutable commit sha, as
     `Weights` carries — `src/whetstone/bakeoff/weights.py:117-118`), **no adapter files**.
   - `sft.verify_checkpoint` extended **by identity** to accept the untrained shape (empty
     adapter set allowed only when the provenance declares `untrained: true`); a trained
     checkpoint with an empty file set stays refused, and a doctored untrained checkpoint
     (missing provenance, wrong schema, base absent from the weights root) is refused by
     name — each watched failing first.
   - The base identity is recorded as a **pinned input**; the writer does **not** close
     `PREREGISTRATION.md` § 7.3 (which stays open — see Risks).
2. **Measurement door** (`python -m whetstone.loop.baseline` — module door, the
   `whetstone.loop.heldout` precedent; **not** a `whetstone baseline` subcommand, so the
   partition guard's documented-edge count is untouched):
   - Flags: `--weights`, `--checkpoint`, `--heldout` (consumed through the fail-closed loader
     **by identity**), `--tasks` (private root), `--public`, `--out` (refuses a gitignored
     root by name, the `refuse_committed_out` posture), `--recorded-on` (an input, never the
     clock), `--run-id` (operator-declared, the night/gate pattern).
   - Scores the held-out membership + source A through `scoring.score` (the existing
     both-verifiers path — `scoring.py:452-509`) with `sampler_for(1)`'s greedy sampler **by
     identity** (`sampling.py:232-233`), so a baseline draw and a gate eval are one experiment
     and the baseline figure is comparable to the gate's.
   - The gate's **retry discipline by identity** (`RETRY_COUNT`, replay-first-attempt,
     `_Replay` raising `RetryInputsChanged`) applies to `UNVERIFIED` tasks only — a verdict is
     final — so baseline and final scores are measured under the same liveness rule; a task
     still unverified after `R` stays unverified **in the denominator** (coverage, never
     silently dropped — `PREREGISTRATION.md:111-114`).
   - `N` computed through `report.tally`'s `weaker_wins` by identity over the raw `Rollout`s
     (the gate's `SideCounts` carry no `N` — dig § 10.3).
   - Run evidence (journals, transcripts — the user's own code back verbatim) goes to a
     gitignored home (`runs/<id>/`), refused under any published path by
     `_refuse_published_root` imported by identity.
   - The door refuses a **second measurement of the same series** by name: the guard keys on
     the series identity — the checkpoint digest and the held-out document digest recorded in
     an existing artifact at `--out`. Same series → refused, naming the first artifact
     (measured-once guard, write side, watched failing first). A changed pinned input (e.g. a
     new base revision — a new checkpoint digest) is a **new series**, which § 3's
     invalidation rule legitimately re-measures with the change recorded in the new artifact
     (`PREREGISTRATION.md:133-135`); the old series is never extended. The runbook states the
     killed-run behavior: a killed run resumes nothing — fresh `--run-id`, half-written
     artifacts refused by schema, never repaired (the gate's stated behavior).
   - `N`'s source asymmetry is explicit: the baseline `N` is counted over the **held-out
     source-B rollouts** (the headline — `PREREGISTRATION.md:107-109`); source A's
     weak-vs-strict differential is reported per-instance on the one instance, never as a
     rate (`PREREGISTRATION.md:149-155`).
3. **Committed baseline artifact** (`reports/baseline-measurement/`):
   - Schema `whetstone-baseline/1`, the deterministic pure writer pattern (`build_*` /
     `write_*` reusing `_row`, `_over`, `tally`, `_counts` by identity; `recorded_on` an input).
   - Contains, for **both** sources over their own denominators: baseline `solved`, coverage,
     `N` (with the `_N_SENTENCE` by identity), and the full § 3 provenance block — model
     revision, task set, environment pins (pointer, not contents), seeds, interpreter, tool
     versions — plus the generation contract fields (retry budget, retry template digest,
     diagnosis vocabulary digest, retrieval, sampler) per `PREREGISTRATION.md` § 10.1's
     reporting obligation.
   - Locality discipline: counts, verdicts, hashes, provenance — **never task contents**
     (canary walk, the heldout/ledger pattern).
   - **Loader side of the measured-once guard**: reading the artifact is fail-closed
     (schema/digest/field refusals by name), and the door's write side refuses when the
     artifact exists.
   - The **one-home guard moves a fifth time, on the changed-series argument** (a new pinned
     series: the § 3 baseline, explicitly not the base-selection bake-off —
     `report.py:1245`): the exact-file list in
     `tests/bakeoff/test_transcript_locality.py:122-135` and the disjointness scans in
     `tests/bakeoff/test_report.py` grow by the new home's three artifacts; the planted-overlap
     controls stay able to fail; the non-comparability sentence states what the baseline is not
     comparable to (the four existing homes) and what it is (the § 3 anchor).
   - Committed artifacts before the run are the declaration — "**No count is measured here:
     the baseline has not run.**" — generated by the writer, never hand-typed.
4. **Operator runbook** (`docs/planning/baseline-measurement/measurement-run/runbook.md`),
   held by `tests/test_baseline_runbook_guards.py` on the night/gate precedent: flags pinned
   to the shipped parser, absolute writable paths, exactly one worktree and no stale one, the
   candidate resolution (the 32B, stated as the runbook-resolved candidate and **not** a § 7.3
   closure), the machinery verified on fixture suites before the real pass, the measured-once
   discipline stated as a refusal not a warning, and the post-run chain (run evidence review →
   the report door rendering the committed artifact → the finding). Watched failing against a
   deliberately wrong stub sheet first.

### Should-have

- The checkpoint's provenance records `tool_versions` and the nominated interpreter, so the
  § 3 "interpreter and tool versions" requirement is met at the artifact of record.
- A `--dry-run`/pre-flight that verifies the weights root holds the base the checkpoint names
  (`NoBaseWeights` posture) before any GPU is spent.

### Nice-to-have

- A `--probe` capacity pass (the D7 pattern) declared before the real pass; **pre-committed
  on** if the 32B's peak is already measured by the larger-base arm (it is —
  `docs/planning/larger-base-arm/finding.md`), so this is likely a no-op documented in the
  runbook rather than built.

## Technical considerations

- **Composition, never re-decision**: `verify_checkpoint`, `read_document` (heldout),
  `scoring.score`, `sampler_for(1)`, `report.tally`/`_UNCOVERED`/`Outcome.SOLVED`,
  `gate.RETRY_COUNT`/`_Replay`, `_refuse_published_root`, `refuse_committed_out` — all
  imported by identity, each asserted `is` in a test.
- **The reward path is byte-untouched**: `src/whetstone/verify/`, `tasks/`, `patch.py`,
  `attribution.py` — the AC2 pins hold (the baseline *scores through* the verifier, never
  modifies it).
- **New machine seam**: a base-only generator (untrained checkpoint → `mlx_lm.utils.load`
  without an adapter path). Whether `mlx_lm==0.31.3` tolerates an adapter-less directory is
  unverified in-tree (dig § 10.5) — the seam is smoke-tested only, every test injects the
  stub engine (the `gate_engine` precedent, `gate.py:453-455`).
- **No new report home yet holds a figure**: `reports/baseline-measurement/` ships as the
  declaration until the operator spends the measurement and the door renders it.
- **Determinism**: the door's evidence and artifact are byte-deterministic for a given
  `--recorded-on`, seed and checkpoint (the gate's determinism discipline).

## Data model

- `whetstone-checkpoint/1` — existing schema; the untrained variant adds `untrained: true`
  to the provenance and permits an empty `files` list **only** in that variant (extension of
  `verify_checkpoint`, conditioned by name).
- `whetstone-baseline/1` — new committed artifact: `schema`, `recorded_on`, `checkpoint`
  `{digest, base:{repo_id, revision}, untrained: true}`, `heldout: {document_digest}`,
  `sides: {source-b|source-a → {denominator, solved, unverified, covered, failed, n}}`,
  `n` over the held-out source-B rollouts per the `N` definition, `generation_contract`
  (the hardened fields), `provenance` (the § 3 pinned inputs: model revision, task set,
  seeds, interpreter, tool versions), `tool_versions`.
- `whetstone-baseline-run/1` (gitignored run evidence) — journals per task, the raw
  `Rollout`s, transcripts; locality discipline as above.

## Risks & open questions

- **`mlx_lm` adapter-less load is unverified** (dig § 10.5): the base-only engine is the one
  machine seam; if `mlx_lm==0.31.3` refuses, the fallback is a stub adapter written by the
  baseline writer — a spec-level decision, tested by the smoke test, never a loosened
  verifier.
- **§ 7.3 stays open — deliberately.** The 32B is recorded as a pinned input; this unit does
  **not** close § 7.3 (which closes only by a Type 1 amendment before the measurement it
  governs runs — `PREREGISTRATION.md:266-268`). The artifact and the runbook state this
  explicitly; no § 10 amendment is made by this unit (the baseline is pre-authorized by § 3,
  not a new series requiring a disclosure).
- **The one-home guard moves a fifth time**: any new committed home under `reports/` fails
  `test_transcript_locality.py:122-135` and the disjointness scans until the list and both
  docstrings grow **on the argument** (new pinned series), with the planted-overlap controls
  re-proven able to fail.
- **`reports/baseline/` (the bake-off) is a different thing**: base selection, explicitly
  not the pinned baseline (`report.py:1245`). The new home's name (`baseline-measurement/`)
  and the non-comparability sentence keep the two apart; nothing in the new home restates a
  bake-off figure.
- **Coverage is a possible outcome, not a defect**: if a held-out task stays unverified
  after `R` retries, the baseline publishes the lower coverage with the count over its
  denominator — never a silent drop. **Hard question for the operator:** the larger-base
  finding disclosed a material unverified rate (a timing property of the 32B's speed against
  the verification timeout). If the baseline's coverage comes in below 12 of 12 after `R`
  retries, the baseline is still the pinned anchor — measured once, published with its
  coverage — and the roadmap's response to a gate that cannot fire (a more reliable sandbox,
  never a looser gate) applies to later evals, not to this measurement.
- **The measured-once guard's series key is the checkpoint digest + held-out document
  digest** (see Requirements): a same-series re-measurement is refused by name; a changed
  pinned input is a new series by § 3, with the change recorded. The exact field set of the
  series key is a spec-level decision, tested watched-failing-first.

## Out of scope

- The night run, the gate evaluation, and the P4 report writer (final score + delta + both
  `N`s) — later slices/operator steps.
- Closing `PREREGISTRATION.md` § 7.3.
- Any change to the reward path, the gate's decision rule, or the verifier.
- The signed morning report / dashboard (post-horizon, `docs/ROADMAP.md:588-593`).
- Source B beyond the held-out membership (the baseline measures the split, never the
  training set — a training-set score would be the headline's contamination, not its anchor).

## Aspect decomposition

1. **`baseline-checkpoint`** — the adapter-less checkpoint writer + the `verify_checkpoint`
   untrained extension, watched failing first.
2. **`measurement-door`** — `python -m whetstone.loop.baseline`: held-out + source A scoring,
   retry discipline by identity, `N` via `tally`, measured-once refusal (write side), run
   evidence locality.
3. **`baseline-report`** — the `reports/baseline-measurement/` home: schema, deterministic
   writer, declaration-only committed state, the one-home guard's fifth move.
4. **`measurement-run`** — the operator's runbook + `tests/test_baseline_runbook_guards.py`.

Sequencing: 1 → 2 → 3 → 4.