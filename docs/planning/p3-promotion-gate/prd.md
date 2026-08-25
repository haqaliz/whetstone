# PRD — P3: The Never-Regress Promotion Gate

**Unit:** `p3-promotion-gate` · **Branch:** `feat/p3-promotion-gate/aliz` · **Written:** 2026-08-24
**Source:** `docs/planning/_card/issue.md` (handoff from `whetstone-next`, 2026-08-24) + dig at
`docs/planning/_card/understanding.md`. All contract language is quoted from `docs/ROADMAP.md` and
`PREREGISTRATION.md`; the dig verified every building block at `d65dc0d` (v0.7.0).

## 1. Problem Statement

The project's guardrail #2 is *"never regress — a new checkpoint ships only when it **provably**
beats the last on a held-out **verified** set"* (`CLAUDE.md`), and the never-regress promotion gate
is core-loop element ③. Today the gate does not exist: `cli.py:11` says so explicitly, there is no
held-out split (`PREREGISTRATION.md` § 7.1 names it open until P3), no retry count `R` (§ 7.2 open),
and no `check-leakage` command. P2 shipped everything the gate compares — hashed checkpoints with a
`verify_checkpoint` re-hash built "so P3's gate can check the bytes it compares"
(`loop/sft.py:24-29`, `night.py:436-438`) — so the dependency is met and the machinery is buildable
now, test-first on fixture checkpoints. Without the gate, nothing can ever be promoted on evidence:
the nightly loop produces candidates, and there is no code that decides, with a proof, whether a
candidate may replace the incumbent.

## 2. Goals & Success Metrics

The gate rule, fixed by the roadmap (verbatim, `docs/ROADMAP.md:420-427`):

```
promote iff  solved_new > solved_old
        AND  regressed  == 0
        AND  unverified == 0

Three exits only: promoted / rejected / UNVERIFIED. UNVERIFIED is never collapsed into promoted.
```

**Exit criteria** (the roadmap's own, `docs/ROADMAP.md:445-451`):

1. `uv run whetstone gate --candidate X --incumbent Y` returns one of the three exits.
2. Tests: known-better → `promoted`; known-worse → `rejected`; deliberately incomplete eval →
   `UNVERIFIED` and **not** promoted.
3. `uv run whetstone check-leakage` exits 0 — zero overlap between the training set and the held-out
   set.
4. The unverified rate appears in every eval's output.

**Gate liveness** (the four items the design must honor, `docs/ROADMAP.md:429-443`):

1. **Deterministic retry.** Each unverified task retries a fixed `R` times with identical seed and
   inputs. A task that verifies on retry is verified.
2. **Coverage is reported, never silently excluded.** Following the sibling project's
   `corpus/metrics.py`: unverified tasks lower *coverage*; they never vanish from the denominator.
   Dropping them is the 100%-precision-by-construction lie.
3. **The eval's own verdict.** If any task is still unverified after `R` retries, the whole
   evaluation reduces to `UNVERIFIED`: not promoted, and not rejected either, because no comparison
   was actually made.
4. **Liveness is itself a measurement.** The unverified rate is reported from the first eval onward.
   If the gate proves unable to fire, **the fix is a more reliable sandbox, never a looser gate.**

**Pre-registration closures (both by dated Type 1 amendment, § 8.1):**

- **§ 7.1 (held-out split)** — closed by a dated amendment committed **before the split is used to
  score anything**. If the corpus proves too small to support a non-degenerate split, *that outcome
  is itself the published finding* — the response is a larger or stratified corpus, never a headline
  computed on the training set (`PREREGISTRATION.md:242-247`).
- **§ 7.2 (retry count `R`)** — closed by a dated amendment committed **before the first gated
  evaluation**; `R` is "to be set from the observed unverified rate rather than guessed"
  (`PREREGISTRATION.md:249-253`). The mechanism ships with a declared `R`; the value is revisable
  only by a further amendment once real nights produce an observed rate.

**No numeric success threshold** is set or implied (`PREREGISTRATION.md:171`). No figure about a
model appears in any committed artifact of this unit.

## 3. User Personas & Scenarios

- **The operator (founder).** Runs `whetstone run --night`, gets a candidate checkpoint, then runs
  `whetstone gate --candidate checkpoints/<new>/ --incumbent checkpoints/<old>/ --heldout
  tasks/heldout/source-b.json`. The gate answers, with a proof it can demonstrate: promoted (exit 0),
  rejected (exit 1), or UNVERIFIED (exit 3 — no comparison was actually made, so nothing ships). The
  promotion record accumulates the verified-improvement trail.
- **The sceptic.** The whole premise is "proves it didn't cheat." The sceptic reads the promotion
  record: the two checkpoint digests (re-hashed), the held-out document digest, the verdict counts
  over their denominator, the retry outcome, and the exit. Everything names its evidence; nothing is
  a bare number.

## 4. Requirements

### Must-have

1. **Held-out document** — a committed, digest-guarded document declaring the source-B held-out
   membership (the `tasks/stratum/easier.json` precedent: schema, rule digest, per-task difficulty,
   membership, refusals, `document_digest`; loader fail-closed by name). Stratified on the
   already-measured per-task difficulty the stratum document carries for all 66 tasks
   (`tasks/stratum/easier.json`: files / hunks / added+deleted lines). Source B only — source A is
   always scored in full (the dev-overlay and stratum precedent). **The non-degeneracy rule is
   pre-committed in the spec before the split is computed** (a minimum held-out count and a
   per-stratum floor, fixed the way the stratum band was fixed) — a degenerate corpus is the § 7.1
   published finding, written and committed, never a criterion tuned after the fact.
2. **§ 7.1 Type 1 amendment** — dated, its own change, recorded in the log, committed **before the
   split is used to score anything** (`PREREGISTRATION.md:242-247`, § 8.1).
3. **Night exclusion** — `whetstone run --night` consumes the held-out document at the partition
   seam, **before** the contract is frozen (the `--stratum` precedent): held-out ids never reach
   rollouts, never reach the trainable partition, and are excluded from both denominators. The
   held-out document is a pinned input of the run, recorded in the ledger.
4. **`whetstone gate --candidate X --incumbent Y --heldout <doc>`** — exactly one of the three exits:
   - Re-verify both checkpoints via `verify_checkpoint` (identity-imported from `loop/sft.py`);
     `CheckpointUnverified` refuses the run by name.
   - Score both checkpoints on the held-out tasks through the STRICT verifier (the reward, as
     `run_verify` invokes it — the gate lives in the guarded root; no inference, no new edge into an
     exempt package).
   - **Deterministic retry**: each unverified task retries a fixed `R` times with identical seed and
     inputs (the run's recorded per-task seeds); a task that verifies on retry is verified.
   - Reduce per-task verdicts through `verify/verdict.py`'s `reduce` (worst-status-wins, UNVERIFIED
     above PASS — imported, never re-decided); coverage computed with the sibling rule (UNVERIFIED
     kept in the denominator; the label trap declined as inapplicable, `ROADMAP.md:539`).
   - Apply the gate rule; exit codes `promoted`→0, `rejected`→1, `UNVERIFIED`→3 (the existing four
     exit codes, `cli.py:64-84`; no fifth).
   - The unverified rate appears in the gate's output — as a count over its denominator, per the
     pre-registration's "Every rate carries its denominator" (`PREREGISTRATION.md:157`).
   - **Both sources together**: the gate's output reports source A's verdicts (the one public
     instance, scored in full — the always-scored-in-full precedent) beside the held-out source-B
     counts, both denominators disclosed, per "Both sources are always published together"
     (`PREREGISTRATION.md:142-147`).
   - **Edge cases asserted, not accidental**: candidate and incumbent being the same checkpoint
     (solved_new == solved_old → `rejected`, by the `>` term) is a test; a held-out set of zero is
     refused by name; the incumbent's training provenance is declared out of the gate's question —
     the gate guards the **candidate's** training provenance (night exclusion + `check-leakage`),
     while the first incumbent is the § 3 pinned baseline (trained on nothing) and later incumbents
     were themselves gate-promoted.
5. **Promotion record** — a gitignored record (the `runs/` discipline) written by the gate:
   candidate digest, incumbent digest, held-out document digest, verdict counts over the
   denominator, retry outcome, `R`, tool versions, the exit. It is the accumulated
   verified-improvement record; nothing in it is published.
6. **`whetstone check-leakage`** — exits 0 iff the training set (a run's `dataset.json` task ids)
   and the held-out set are disjoint; a non-zero overlap is named, not counted. Covers both sources'
   denominator rule as declared.
7. **§ 7.2 Type 1 amendment** — `R` declared a priori (proposed `R = 3`), the mechanism
   parameterized from one declared constant, the amendment dated and committed before the first
   gated evaluation (`PREREGISTRATION.md:249-253`).
8. **Gate runbook + guard** — the operator's sheet for the first real gated evaluation (the
   night-door precedent, `docs/planning/p2-rollouts/night-door/runbook.md`), held by its own guard
   test: the exact gate invocation, the fixture-checkpoint verification sequence, the promotion
   record's documented home, and the liveness measurement (the unverified rate reported from the
   first eval onward). The first real evaluation is scripted, never improvised.

### Should-have

9. A `docs/planning/p3-promotion-gate/` written-up status block in `CLAUDE.md` and a `CHANGELOG.md`
   entry, landed in the same commits as the code (the repo's "capability and write-up arrive
   together" contract).

### Nice-to-have

10. `whetstone gate` accepting `--retry R` override for operator experiments — **declined** unless a
   real need appears: `R` is a pinned input, and a CLI override makes the amendment meaningless.
   Keep `R` a module-level declared constant only.

## 5. Technical Considerations

### Core-loop placement

Element ③ **never-regress promotion gate**. The gate changes what may ship, not what the reward
measures: the reward stays the STRICT verifier's execution-grounded exit status, byte-untouched.
What counts as a win is fixed by identity: `Outcome.SOLVED` from `bakeoff/scoring.py`, the same
member the loop's `TRAINABLE` imports (`loop/dataset.py:49`) and `report.tally` computes
(`report.py:435`). `UNVERIFIED` counts as **not** a win — the gate's `UNVERIFIED` exit is a third
outcome, never a promotion.

### Integration points (all verified in the dig)

- **Checkpoints:** `loop/sft.py:400` `write_checkpoint`, `:453` `verify_checkpoint`,
  `Checkpoint.digest` is the compare key (`sft.py:274-276`).
- **Ledger:** `loop/ledger.py` schema `whetstone-run/1` — `checkpoint.digest`, `dataset.digest`,
  `run_seed`, `model.revision`, `tool_versions`, applied `seeds` (the per-task seeds the retry
  replays), per-draw `(denominator, unverified, solved)` counts.
- **Verdicts:** `verify/verdict.py` `reduce` — imported by identity; the gate must not re-decide the
  honesty contract.
- **Coverage:** `report.tally`'s `covered = denominator - unverified` (`report.py:373-382`) is the
  existing shape; the gate reports the same counts over the same denominator.
- **CLI:** `cli.py:build_parser()` / `main()`; `gate` and `check-leakage` are new subcommands with
  no stubs; the four exit codes are shared, no fifth.
- **Stratum precedent:** `tasks/stratum/easier.json` + its fail-closed loader and the run-side
  `--stratum` filter are the templates for the held-out document and the night exclusion.
- **Dev-subset precedent:** exclusion happens at the partition seam before freeze; `UnknownDevSubset`
  refusal posture carries over (an id matching nothing is refused by name).
- **Reward-path guards:** `src/whetstone/verify/`, `src/whetstone/tasks/`, `patch.py`,
  `attribution.py` stay byte-untouched (the AC2 pins). The gate and `check-leakage` live in the
  guarded root; the one-edge guard (`test_reward_path_scope_is_partitioned.py`) is untouched.

### The gate-specific honesty surface (what can go wrong and what catches it)

| Risk | Defence |
|---|---|
| Held-out tasks leak into training | Night excludes them pre-freeze; `check-leakage` proves it; a leak fails the build |
| The gate compares bytes it never read | `verify_checkpoint` on both sides, `CheckpointUnverified` refusal |
| The gate "promotes" on an incomplete eval | After `R` retries, one unverified task reduces the whole eval to `UNVERIFIED` (item 3) |
| Unverified tasks vanish from the denominator | Coverage counts keep them; the report renders count-over-denominator (item 2) |
| A second notion of "solved" drifts in | `Outcome.SOLVED` imported by identity; a second notion is asserted away |
| `R` becomes a free CLI knob and the amendment a formality | `R` is a declared constant, not a flag |
| The gate is only ever tested on fixtures that flatter it | Adversarial fixtures: an incomplete eval, a doctored checkpoint, a leaked training set — each must fail |

### Locality

Everything runs on the machine. The held-out document, promotion records, and checkpoints are local
and gitignored; the held-out document's committed artifact carries counts and membership digests,
never task contents (the ledger's locality discipline, walked with a canary).

## 6. Risks & Open Questions

1. **`R`'s declared value is a priori.** No observed unverified rate exists (no night has run); the
   larger-base finding reported a qualitative "material unverified rate" (32B timing vs timeout).
   Proposed `R = 3`, recorded by the § 7.2 amendment; revision requires a further amendment grounded
   in a measured rate. **This is the nearest feasibility risk**: if the real rate is high, `R` may
   need to grow — the mechanism must make that a one-constant diff plus an amendment, never a CLI
   knob.
2. **The held-out split may be degenerate.** § 7.1 anticipates it: a corpus too small for a
   non-degenerate split is a published finding, not a worked-around number. The design must compute
   the split and be prepared to write that finding.
3. **The gate's liveness is untested against reality until a night runs.** Fixture checkpoints prove
   the three-exit differential; they cannot prove the gate will fire on real nights. State this in
   the unit's write-up; the pivot signal (persistently high unverified rate after retries → sandbox
   reliability becomes the next phase, `ROADMAP.md:453-454`) is the roadmap's own handling of it.
4. **The § 3 baseline measurement is deliberately not spent here** (P4's, requiring § 7.3 closure).
   The split must be sized and documented so it can later support that single-shot measurement
   without redesign.
5. **What "identical seed and inputs" means for a verification retry** — the run's recorded applied
   seeds replayed against the same held-out checkout. If a retry's checkout differs, the retry is a
   different experiment; the design must pin the checkout (same task manifest + same reference
   state) per retry.

## 7. Out of Scope

- **The § 3 baseline measurement** (the untrained open base scored on the held-out set — "measured
  once, re-measured never" stays unspent; P4's, and it depends on § 7.3 closing, which this unit
  does not attempt).
- **Closing § 7.3** (naming the base). The 32B remains "the first candidate with evidence", not a
  pinned base.
- **The morning report / dashboard** (element ④ — post-horizon).
- **Any change to the verifier, the reward path, or the sandbox.** A gate that cannot fire is
  answered by a more reliable sandbox, never a looser gate — but that is a *later* unit, not this
  one.
- **A second task family, distillation, GRPO** (post-horizon).
- **`--retry R` as a CLI flag** (see § 4, nice-to-have 9).

## 8. Proposed Aspect Decomposition

1. `heldout` — the held-out document: the pre-committed non-degeneracy rule, difficulty
   stratification, membership, digest, fail-closed loader, the § 7.1 Type 1 amendment.
2. `night-integration` — the night consumes the document at the partition seam; held-out ids never
   reach rollouts or the trainable partition; ledger records it.
3. `gate-core` — `whetstone gate`: checkpoint verification, held-out scoring, verdict reduction,
   the gate rule, the three exits, the promotion record, source A reported beside source B.
4. `retry-discipline` — the deterministic `R`-retry mechanism (identical seeds, one declared
   constant, the § 7.2 Type 1 amendment).
5. `check-leakage` — the overlap check and its CLI door.
6. `gate-runbook` — the operator's sheet for the first real gated evaluation and its guard test.