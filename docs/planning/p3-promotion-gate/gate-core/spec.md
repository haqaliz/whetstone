# Spec — gate-core (aspect 3 of p3-promotion-gate)

**PRD:** `../prd.md`. **Branch:** `feat/p3-promotion-gate/aliz`. This aspect ships the gate itself:
`whetstone gate --candidate X --incumbent Y --heldout <doc>` returning exactly one of the three
exits, with the promotion record as its output.

## Problem slice and user outcome

Two hashed checkpoints exist and nothing decides, with a proof, whether one may replace the other.
The user outcome is the roadmap's exit criterion: `uv run whetstone gate` returns one of the three
exits, a deliberate incomplete eval is never promoted, and the promotion record names the bytes it
compared.

## In-scope requirements

1. **Placement and the partition guard.** The gate reaches `mlx_lm` (scoring a checkpoint means
   generating a patch per held-out task, then STRICT-verifying it — the bake-off's own loop) and
   composes exempt-package machinery by identity, so the gate body lives in
   `src/whetstone/loop/gate.py` (exempt, on the `loop` precedent). `cli.py` gains a **second
   documented, function-local edge** (`whetstone.loop.gate`), and
   `tests/test_reward_path_scope_is_partitioned.py` is updated test-first — the edge list and the
   `EXEMPT` entry extended, each new edge watched failing against a planted import, and the guard
   still refuses any further edge. The gate composes, never re-decides:
   - `loop/sft.py`'s `verify_checkpoint` **by identity** — both checkpoints re-hashed before
     anything compares (`CheckpointUnverified` refuses the run by name, naming the checkpoint).
   - the held-out loader (aspect 1) **by identity** — `HeldoutDigestMismatch` refuses the run.
   - `verify/verdict.py`'s `reduce` **by identity** — worst-status-wins, UNVERIFIED above PASS.
   - the single definition of solved: `Outcome.SOLVED` **by identity** (`report.tally`'s member),
     so the gate's solved counts cannot drift from the loop's trainable definition.
2. **The decision core is a pure function.** Given per-task outcome maps for candidate and
   incumbent over the held-out membership, it returns exactly one of `promoted` / `rejected` /
   `UNVERIFIED` per the roadmap rule (`promote iff solved_new > solved_old AND regressed == 0 AND
   unverified == 0`, `docs/ROADMAP.md:420-427`) after the retry discipline (aspect 4) has run. The
   pure core is tested on outcome-map fixtures — the three exits, the `>` term (equal solved counts
   is `rejected`, not a tie-break), a candidate==incumbent comparison is `rejected` by the `>`
   term (asserted test, not accident), and one still-unverified task reduces the whole eval to
   `UNVERIFIED` (`docs/ROADMAP.md:438-440`).
3. **Scoring.** For each held-out task, generate a patch per checkpoint through the harness
   (greedy sampler, seeded — the recorded per-task seeds; `sampler_for(1)` by identity so a
   single-draw gate eval and the bake-off are one experiment), apply, STRICT-verify, record
   `Outcome`. Scoring composes the existing harness (`sweep.rankable`, journal/transcript record
   per (side, task)) — no new generation logic.
4. **Both sources together.** The gate's output reports source A's verdicts (the one public
   instance, scored in full) beside the held-out source-B counts, both denominators disclosed
   (`PREREGISTRATION.md:142-147`).
5. **Coverage and the unverified rate.** Coverage computed with the sibling rule — UNVERIFIED kept
   in the denominator (the label trap declined as inapplicable, `ROADMAP.md:539`); the unverified
   rate appears in the gate's output as a count over its denominator (`PREREGISTRATION.md:157`).
6. **The promotion record.** Written to a gitignored home `runs/promotions/<id>.json`, schema
   `whetstone-promotion/1`: candidate digest, incumbent digest, held-out document digest, per-side
   verdict counts over the denominator, unverified counts, retries used, `R`, the exit, tool
   versions, `recorded_on` (an input, never the clock — the arms' rule). The record is local
   evidence, never published; its home is asserted gitignored.
7. **Exit codes.** `promoted`→0, `rejected`→1, `UNVERIFIED`→3 (the existing four-code contract,
   `cli.py:64-84`; no fifth). Refusals (`CheckpointUnverified`, `HeldoutDigestMismatch`, a
   held-out set of zero, an unparseable checkpoint directory) → 2.
8. **Refusals by name**: a held-out set of zero is refused, never vacuous; a checkpoint that is not
   a night-written checkpoint (no provenance) is refused by name.

## Out-of-scope boundaries

- No retry mechanism (aspect 4) — but the decision core's `unverified` term is the seam it wraps.
- No § 3 baseline measurement, no § 7.3 closure, no report home, no published figure.
- No change to `src/whetstone/verify/`, `src/whetstone/tasks/`, `patch.py`, `attribution.py`.
- The gate does not run itself on real checkpoints in this unit — fixtures prove the differential;
   the operator's sheet (aspect 6) scripts the first real evaluation.

## Acceptance criteria (testable)

- AC1: `whetstone gate --candidate <fixture> --incumbent <fixture> --heldout <doc>` returns each of
  the three exits from fixture outcome maps: known-better → `promoted` (0); known-worse →
  `rejected` (1); deliberately incomplete eval → `UNVERIFIED` (3) and **not** promoted — asserted
  through the CLI, not just the pure core.
- AC2: a doctored checkpoint (provenance digest mismatch) refuses by name and never reaches the
  decision; a hand-edited held-out document refuses by name.
- AC3: candidate==incumbent is `rejected`; equal solved counts is `rejected`; one still-unverified
  task makes the whole eval `UNVERIFIED`.
- AC4: the gate writes `runs/promotions/<id>.json` on every non-refusal run, and its home is
  asserted gitignored; the record carries both digests, the held-out digest, counts over the
  denominator, retries used, `R`, the exit, tool versions.
- AC5: the partition guard is extended test-first — exactly two documented function-local edges
  into exempt packages (night, gate), each proven able to fail against a planted import; a third
  edge fails the build.
- AC6: the reward-path AST guard stays green with the gate in place (no inference import in any
  guarded module; the gate's own no-inference walk covers its non-GPU paths).
- AC7: `uv run pytest` green; ruff and mypy over `src/` green; the AC2 pins byte-identical.

## Dependencies and sequencing

- Depends on aspect 1 (`heldout` loader by identity). Composes aspects 3–4's seam: the retry
  discipline wraps the per-task scoring, so the scoring seam is defined here and consumed there.
- Sequence: partition guard update (test-first) → pure decision core + fixtures → scoring
  composition → CLI + exit codes → promotion record → both-sources output.
- Feeds: `retry-discipline` (the seam), `gate-runbook` (the operator's sheet), P4.

## Open questions / risks

- Scoring a checkpoint is a GPU pass (generation per held-out task per side). The fixture harness
  uses the stub generator; the real cost is the operator's runbook question (aspect 6), and the
  runbook must script the verification sequence before the real pair.
- Whether `check-leakage` shares `gate.py` or is its own module — the partition guard counts edges
  by module; decide in the plan (this spec assumes `loop/check_leakage.py`, a third documented
  edge).