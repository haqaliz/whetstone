# Understanding — p3-promotion-gate

**Dig date:** 2026-08-24 · **Branch:** `feat/p3-promotion-gate/aliz` · **Dig agents:** two explore
agents in parallel — one mapping the gate's building blocks in `src/whetstone/`, one extracting the
P3 contract from `docs/ROADMAP.md`, `PREREGISTRATION.md`, and `CHANGELOG.md`. All citations below
were verified against the worktree at `d65dc0d` (v0.7.0).

## What P3 really is

The never-regress promotion gate: decide, from two model checkpoints and a held-out verified set,
whether a candidate may replace an incumbent. Three exits only — `promoted` / `rejected` /
`UNVERIFIED` — and `UNVERIFIED` is never collapsed into `promoted` (ROADMAP.md:426-427). The gate
rule, verbatim (ROADMAP.md:420-424):

```
promote iff  solved_new > solved_old
        AND  regressed  == 0
        AND  unverified == 0
```

Plus gate liveness (ROADMAP.md:429-443): deterministic retry of each unverified task a fixed `R`
times with identical seed and inputs; coverage reported, never silently excluded (the sibling's
`corpus/metrics.py` rule, `UNVERIFIED` kept in the denominator — the label trap half declined as
inapplicable, ROADMAP.md:539); if any task is still unverified after `R`, the **whole evaluation**
reduces to `UNVERIFIED`; the unverified rate is reported from the first eval onward, and a gate that
cannot fire is answered by a more reliable sandbox, never a looser gate.

## What the gate builds on (verified, file:line)

- **Checkpoints** — `loop/sft.py`: `write_checkpoint` (:400), `verify_checkpoint(directory) ->
  Checkpoint` (:453). Schema `whetstone-checkpoint/1`; per-file sha256 plus a digest-of-digests
  (`Checkpoint.digest`), the value "the one P3's gate will name when it says which two checkpoints
  it compared" (sft.py:274-276). The gate re-hashes both sides before comparing — documented intent
  (sft.py:24-29, night.py:436-438). `CheckpointUnverified` (:92-98) is the refusal.
- **Run ledger** — `loop/ledger.py`, schema `whetstone-run/1`: records `checkpoint.digest`,
  `dataset.digest`, `run_seed`, `model{repo_id,revision}`, `tool_versions`, applied `seeds`,
  per-draw counts `(denominator, unverified, solved)`, and `dataset{examples, denominator,
  unverified, coverage}`.
- **The single definition of solved** — `Outcome.SOLVED` (`bakeoff/scoring.py:98`), computed by
  `report.tally` (report.py:425-452); the loop imports it by identity (`dataset.py:49`
  `TRAINABLE = Outcome.SOLVED`). The gate's `solved_new`/`solved_old` must reduce to the same
  member object.
- **Verdict semantics** — `verify/verdict.py`: `_RANK` puts `UNVERIFIED` (2) above `PASS` (0);
  `reduce(verdicts)` is worst-status-wins; empty → `UNVERIFIED`. The gate's `UNVERIFIED` exit must
  use this reduction, not a local max.
- **CLI** — `cli.py:build_parser()` (:130-377) + `main()` (:612-650); no stubs (cli.py:11). Four
  exit codes 0/1/2/3 (PASS/FAIL/USAGE/UNVERIFIED, cli.py:64-84). The gate's three exits map
  promoted→0, rejected→1, UNVERIFIED→3. The one-edge guard
  (`tests/test_reward_path_scope_is_partitioned.py:145,437-525`) documents exactly one
  function-local edge (`cli.py → whetstone.loop.night`). A gate that only verifies (no inference)
  can live in the guarded root like `run_verify` does.
- **Coverage counts already exist** — `report.tally.covered = denominator - unverified`; rendered
  as "count of denominator" (`_over`, report.py:1180-1182), never a bare rate. The unverified
  **rate** is not computed anywhere yet (ROADMAP.md:441-442, 451 require it in every eval output).

## What does not exist (the new surface)

- No held-out split — `PREREGISTRATION.md` § 7.1 is open until P3, by dated amendment committed
  **before the split is used to score anything** (:244). The train/valid split in
  `loop/dataset.py` is training-side only, and `test.jsonl` is deliberately absent
  (dataset.py:77-82).
- No `whetstone gate`, no `whetstone check-leakage`, no training-set/held-out overlap check. The
  only existing "leakage" check is dev-subset-vs-scored (`report.build_report` → `ScoredDevSubset`,
  report.py:502-514), a different boundary.
- No `R` retry mechanism. The bake-off's retry wrapper (`bakeoff/retry.py`) is a generation-contract
  retry, not the gate's verification retry.
- No nightly run has ever happened, so no real candidate/incumbent pair exists — the gate is built
  and tested on fixture checkpoints; its liveness is genuinely exercised only once real nights exist.

## The contract that constrains the design

- **Held-out split (§ 7.1)** — size/stratification depends on the corpus's difficulty distribution,
  which has not been measured; if the corpus is too small to support a split without a degenerate
  set, that outcome is itself the published finding — the response is a larger or stratified corpus,
  never a headline computed on the training set. A committed, digest-guarded document (the stratum
  precedent: `tasks/stratum/easier.json`, loader fail-closed by name) is the natural shape.
- **Retry count `R` (§ 7.2)** — to be set from the observed unverified rate, never guessed; closed
  by a dated amendment committed before the first gated evaluation. The **mechanism** ships with a
  declared `R`; the value may be revisited once real nights produce an observed rate.
- **Base (§ 7.3)** — STILL OPEN; the 32B is evidence only, and § 7.3 closes by a Type 1 amendment
  before the measurement it governs runs. The § 3 baseline (scored on the held-out split, measured
  once) is unspent. **Scope decision for the PRD:** the ROADMAP's four P3 exit criteria do not
  themselves require closing § 7.3 or taking the baseline measurement — those are P4's. This unit
  closes § 7.1 and § 7.2 and builds the gate; whether it also takes the § 3 baseline measurement is
  an open scope question (likely no — P4's report needs both sources' final scores, and the held-out
  split existing does not force the single-shot baseline to be spent in this unit).
- **Amendments** — append-only, dated, their own change, recorded in the log. Type 1 = closes a § 7
  open item under § 8.1 (committed before the measurement it governs); Type 2 = adds a disclosure.
  **No Type 1 amendment has ever been made** — P3's § 7.1/§ 7.2 closures would be the first two.
- **Guardrails** — never a looser verifier/gate; `UNVERIFIED` never a win and never rendered as
  `PASS`; no number the verifier didn't produce; both sources published together; local by default;
  reward path (`src/whetstone/verify/`, `tasks/`, `patch.py`, `attribution.py`) byte-untouched.

## Core-loop placement

Element ③ **never-regress promotion gate** — the gate is the third element of the core loop, and it
is where the project's "never ship a regressed checkpoint" claim is enforced in code. It changes the
gate, so it must state what counts as a win (STRICT `PASS` on the held-out set, `Outcome.SOLVED` by
identity) and confirm `UNVERIFIED` counts as **not** a win. It does not touch the reward path: the
verifier stays execution-grounded and byte-untouched.

## Open questions to put to the interview

1. Does the held-out split apply to source A as well as source B? (The headline is source-B; source
   A is one instance and is always scored in full — precedent from the stratum/dev overlay.)
2. How does the night learn the held-out set? A `--heldout` flag consuming a committed document (the
   stratum precedent), applied at the partition seam before freeze, so training never sees held-out
   tasks — or does the gate alone know the split, leaving training leakage undetected until
   `check-leakage` runs?
3. Does this unit also take the § 3 baseline measurement, or is the single-shot baseline P4's?
4. The gate's inputs: two checkpoint directories + the held-out document. How is the incumbent
   pinned — a `checkpoints/<id>/` path, or a "current best" pointer that is itself a promotion
   artifact?
5. What exactly does "identical seed and inputs" mean for a verification retry — the run's recorded
   per-task seeds replayed against the same held-out checkout?
6. Where does the gate's own output go — does it write a promotion record (gitignored) that a later
   report/`whetstone gate` invocation consumes as incumbent provenance?
