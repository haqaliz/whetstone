# PRD — honest-number-report (P4 slice 2)

**Unit:** P4 slice 2, the next unit named by the launch path (`docs/ROADMAP.md:647-651`, § 12).
**Branch/worktree:** `feat/honest-number-report/aliz` · `.claude/worktrees/feat-honest-number-report`.
**Date:** 2026-08-27. **Decisions:** confirmed in the requirements interview (2026-08-27) — the
four fork points at the end of this document are **decided**, not open.

## Problem Statement

The launch path ends at **the first honest number** (`docs/ROADMAP.md:637-640`): a published
report that instantiates `PREREGISTRATION.md` § 4's pre-registered shape — for **both sources**,
baseline score, final score, delta, `N_baseline`, `N_final`, coverage, and the full provenance
block — plus P4's exit criterion 3, "the harness is public and reproduces the reported number
from the pinned inputs" (`docs/ROADMAP.md:462-468`).

Today every piece of that document exists as machinery except the document itself:

- The **baseline** ("before") is ready: the § 3 baseline machinery shipped in P4 slice 1
  (`docs/planning/baseline-measurement/`), and `loop/baseline.py`'s `read_baseline_document`
  is documented verbatim as "what the P4 report writer will read" (`baseline.py:316-325`).
- The **final score** ("after") exists in the gate's promotion record (`whetstone-promotion/1`,
  `runs/promotions/<id>.json`) — with **one gap the dig found, not in the brief**: the record
  has **no `weaker_wins` field**, so `N_final` has no on-disk source anywhere
  (`docs/planning/_card/understanding.md`, "The 'before' is ready; the 'after' has one gap").
- **No report writer, no report door, no report home exists** for the § 4 shape. The one
  adversarial guard proves it must be **new** rather than an extension:
  `test_the_p4_headline_skeleton_is_refused` (tests/bakeoff/test_report.py:323) forbids the
  bake-off report from instantiating the shape.

Who is this for? The **operator** (the author) — the report render is the last step of the
operator chain (`docs/ROADMAP.md:652-656`: § 7.3 amendment → baseline spend → night #1 → night
#2 → first gated evaluation → **the P4 report** → the finding). And the **future reviewer of
the pre-registration**, who must be able to check that the published headline is the
pre-registered one, measured on the declared series, from the sealed evidence.

Evidence the problem is real: P4's exit criteria 1 and 3 are unmet; the launchable milestone
has no document to live in; the morning report pulled into the launch path (`docs/ROADMAP.md:657-661`)
has no substrate. Nothing else in the tree builds this — the baseline-report spec defers it
explicitly: "The P4 report writer (final score + delta + both `N`s) — a later slice; this
aspect only anchors the 'before'" (`docs/planning/baseline-measurement/baseline-report/spec.md:84-85`).

## Goals & Success Metrics

1. **The § 4 shape renders.** A report exists containing, for **both** sources: baseline
   score, final score, delta, `N_baseline`, `N_final`, coverage, and the full provenance block
   (pinned seeds, model revision, task set, tool versions) — P4 exit criterion 1
   (`docs/ROADMAP.md:462-465`), in the § 4 shape (`PREREGISTRATION.md:57-72, 140-167`).
2. **The number reproduces.** P4 exit criterion 3: the harness reproduces the reported number
   from the pinned inputs — asserted at the count level (the report is a pure, deterministic
   function of the two sealed evidence documents; byte-identical across invocations and
   processes under `PYTHONHASHSEED` 0/1; the promotion record's counts re-verified
   consistent: `solved + failed + unverified == denominator`, unverified stays in the
   denominator).
3. **No half-truth render.** Every render without an arm that ran, a proven control, a
   measured baseline, or series agreement is refused by name, nothing written.
4. **The home is single.** `reports/honest-number/` becomes the only home of the delta/final
   series' figures; the one-home guard moves a sixth time on the argued series basis; the
   § 10.9 Type 2 amendment is committed **before any figure exists**.
5. **Zero reward-path touch.** `src/whetstone/verify/`, `patch.py`, `attribution.py`
   byte-identical to `origin/master` (AC2 pins); the partition guard unchanged (module doors
   only, no `cli.py` edge).

**Success is not** the value of the number. A zero or negative delta is a valid, publishable
outcome — P4 has no pivot signal (`docs/ROADMAP.md:470-472`), and the number itself is the
operator's spend, never the code's.

## User Personas & Scenarios

- **The operator (the author).** Renders the report after the first gated evaluation, per the
  unit's runbook. Scenario the runbook scripts: the report door reads the sealed baseline
  artifact and the promotion record, re-verifies the checkpoint, asserts series agreement,
  writes the three artifacts into `reports/honest-number/`; a mismatch or a missing piece is
  refused by name with nothing written.
- **The future reviewer of the pre-registration.** Opens `reports/honest-number/report.md` and
  checks: both sources present; source A per-instance; every rate carries its denominator;
  the delta reads as the count change over the held-out split under the same series; the § 4
  shape matches `PREREGISTRATION.md`; the figures re-derive from the sealed evidence
  (the harness-reproduces-the-number check).
- **The P4 report writer's own successor — the signed morning report.** `whetstone report
  --last-night` (`docs/ROADMAP.md:657-661`) renders this unit's writers; the morning report is
  a **separate follow-on unit** and out of scope here.

## Requirements

### Must-have

1. **Promotion record carries `N_final`** (`src/whetstone/loop/gate.py`): `SideCounts` gains
   `weaker_wins` (the `report.tally` definition of `N` by identity — `weak is PASS and strict
   is FAIL`), recorded at scoring time when the Rollout records are at hand; the
   `whetstone-promotion/1` schema is documented with the new field; the record remains
   written-never-read *by the gate* but gains the fail-closed reader this unit's door
   consumes. A doctored record (unknown fields, counts that don't sum to the denominator,
   `weaker_wins > denominator`, digest-missing) is refused by name.
2. **The report writer** (`src/whetstone/bakeoff/report.py`, on the five-writer precedent):
   `build_honest_number_report` / `write_honest_number_report`, schema
   `whetstone-honest-number/1`, three-artifact shape (report.md/report.json/cost.json),
   reusing `_row`, `_over`, `_contract_fields`, `_contract_block`, `_counts`, `tally` **by
   identity** (monkeypatch-proven), pure and deterministic, declaration-only state
   ("**No count is measured here: the report has not run.**", writer-generated, no `N of M`),
   locality discipline (counts, verdicts, provenance — never task contents).
3. **The § 4 shape**: headline `+a of b held-out tasks (baseline c of b, final d of b) /
   coverage e of b / N: f at baseline, g at final` over source B's held-out split; source A
   per-instance, never a rate, both sources always in the same document
   (`PREREGISTRATION.md:140-155`); every rate carries its denominator; a zero or negative
   delta rendered as plainly as a positive one. **Whose counts are "final" is the gate
   decision's function** (gate-resolution, 2026-08-27): `promoted` → final = the candidate's
   held-out counts; `rejected` → final = the **incumbent's** counts (nothing shipped — the
   candidate's counts are disclosed beside them as the rejected attempt); `UNVERIFIED` → **no
   headline at all**: the document states the decision and both sides' counts with "no
   comparison was made", never a delta that reads as a win. Coverage renders on both sides;
   the headline's `e` is the final side's `covered`.
4. **The report door** (`src/whetstone/loop/honest_report.py`, module door, `python -m
   whetstone.loop.honest_report`): composes `read_baseline_document`, the new promotion-record
   reader, and `sft.verify_checkpoint` **by identity**; refuses by name, nothing written,
   exit 2: an unmeasured baseline (`measured: false`), a missing/unreadable evidence
   document, a failed checkpoint re-hash, **series disagreement** (the promotion record's
   `heldout.document_digest` or the candidate checkpoint's base identity ≠ the baseline
   series — the delta is not a delta, `PREREGISTRATION.md:92-94`), **an incumbent whose
   checkpoint provenance declares a different base than the candidate's** (two nights on
   different bases means the gate compared incomparables — refused, gate-resolution
   2026-08-27), and a gitignored `--out` (the `_refuse_published_root`/`refuse_committed_out`
   posture by identity). A clean render exits 0. A `--render-declaration` mode writes the
   pre-run state. No fifth exit code.
5. **The baseline "before" is read, never restated from another home**: the baseline-side
   figures in the report are the sealed artifact's own counts, through the fail-closed loader
   by identity, asserted byte-equal to the artifact's figures — the disjointness exception
   this unit argues.
6. **The one-home guard moves a sixth time** (tests/bakeoff/test_report.py:1941-1957 and
   tests/bakeoff/test_transcript_locality.py:134-150 in lock-step; `_ALL_HOMES` at
   test_report.py:1322-1327; figures-level disjointness scans + planted-overlap controls):
   the argument recorded in both docstrings, the new home's declaration-only artifacts
   committed first, the new home's own disjointness scan (refusing figures from the four
   existing homes) and planted control.
7. **The § 10.9 Type 2 amendment** (`PREREGISTRATION.md` § 10, before any figure): discloses
   the loop's generation contract — seeded categorical sampler — as the final-side contract
   (CLAUDE.md pre-commits: "the amendment belongs to whichever later unit first publishes a
   figure measured under it"), declares `reports/honest-number/` the only home of the
   delta/final series, states the "no count is claimed here" sentence, introduces no success
   threshold, rewords nothing above § 10, and adds no proportion in any spelling.
8. **The harness-reproduces-the-number check** (P4 exit criterion 3): the report's figures
   re-derive from the two sealed evidence documents; byte-identity asserted in-process and
   across subprocesses under `PYTHONHASHSEED` 0/1; the promotion record's counts
   re-verified consistent on read.
9. **The runbook** (`docs/planning/honest-number-report/report-runbook/runbook.md`): the
   operator's sheet for the report render (post-run chain: behind the first gated evaluation,
   after the baseline spend and the two nights), held by its own guard on the
   baseline-runbook precedent (`tests/test_baseline_runbook_guards.py`: flags pinned to the
   shipped parser by identity, absolute writable paths, exactly one worktree and no stale one,
   the § 4 shape sentence, no re-render-to-confirm phrasing, machinery verified on fixture
   evidence before the real render).

### Should-have

- The report's markdown opens with a pointer to the operator's finding (the number's
  narrative home is the finding, per `docs/planning/baseline-measurement/measurement-run/runbook.md:181-184`).

### Nice-to-have

- None — the unit is already at the repo's established size (5 aspects, on the
  baseline-measurement precedent).

## Technical Considerations

- **Where things live (all in exempt packages, zero partition-guard change):** writer in
  `src/whetstone/bakeoff/report.py` (all five writers live there); door in
  `src/whetstone/loop/honest_report.py` (module door — `python -m`; the comparison.py
  three-mode precedent is the *shape*, but the P4 report has no contract arms, so
  `build_contract_arms` does not apply); the promotion-record reader in
  `src/whetstone/loop/gate.py` (the record's own docstring names this reader: "named so a
  later reader has one answer to 'what shape is this file'", gate.py:97). No `cli.py` edge —
  the morning report's `whetstone report` subcommand belongs to its own follow-on unit.
- **Import direction:** `report.py` never imports `whetstone.loop.*` (cycle — the loop
  imports the report; the `_BASELINE_EVIDENCE_SCHEMA`-as-declared-string precedent,
  report.py:1112-1117). The writer takes the baseline/final counts as plain values; the door
  reads the evidence documents and feeds them.
- **Determinism:** no clock, no ledger, fixed serialization order, `json.dumps(indent=2,
  sort_keys=True) + "\n"`; `recorded_on` is an input, never the clock.
- **The `N` definition is the single one:** `report.tally`'s `weaker_wins` by identity, and
  `_N_SENTENCE` ("{count} rollouts a weaker check would have scored as wins.") by identity —
  never a new sentence, never a rate.
- **The `UNVERIFIED` discipline:** an `UNVERIFIED` promotion-record decision renders as
  `UNVERIFIED` — the report states the decision and its counts, never a delta that reads as a
  win; the headline's denominator keeps unverified tasks in it (coverage is reported, never
  silently excluded, `PREREGISTRATION.md:111-114`).
- **The loop's sampler contract** (seeded categorical, `sampling.K = 8`) differs from every
  published contract (greedy); the § 10.9 amendment discloses it. It is not a pinned input
  (`PREREGISTRATION.md` § 10.1), so the delta against the same series' baseline remains
  legitimate; the amendment states that plainly.
- **Series agreement is checked on the candidate's base identity** (from the checkpoint's
  provenance via `verify_checkpoint` by identity) plus the promotion record's
  `heldout.document_digest`, against the baseline artifact's `series`
  (repo_id/revision/heldout_digest). Mismatch → refuse by name (decided).

## Risks & Open Questions

- **R1 (retired by decision):** `N_final` had no on-disk source. Decided: the promotion
  record gains `weaker_wins`; the record is written-never-read by the gate, so no reader
  breaks; schema bump documented. Residual: promotion records written by the future operator
  chain are the first with the field — the reader refuses a record missing it by name, never
  defaults.
- **R2 (retired by decision):** the report home + amendment. Decided: new
  `reports/honest-number/` + § 10.9 Type 2 in this unit, before any figure.
- **R3 (retired by decision):** series mismatch. Decided: refuse by name.
- **R4 (open, stated):** the gate's per-task scoring seam records no per-task outcomes in the
  promotion record (only counts). The reproducibility check is therefore **count-level**:
  re-derivation from the sealed counts + consistency assertions. Rollout-level re-scoring is
  out of scope (it would re-run the machine) and is stated, never blurred. If a future unit
  needs rollout-level reproduction, the seam is `gate._score_one` and the recorded
  first-attempt completion hashes.
- **R5 (open, stated):** the trained checkpoint's provenance must carry `base: {repo_id,
  revision}` for series agreement to be checkable; `sft.verify_checkpoint`'s trained shape
  already declares the base (the baseline checkpoint writer proves the untrained shape);
  asserted in the suite with fixture checkpoints, never assumed. The door verifies **both**
  checkpoints — candidate and incumbent — and refuses a base mismatch between them
  (gate-resolution 2026-08-27).
- **R6 (open, stated):** the § 7.3 Type 1 amendment (pinning the fine-tuned base) and the
  operator GPU passes stay outside this unit; the report renders their fruits, never
  pre-empts them.

## Out of Scope

- **The signed morning report** (`whetstone report --last-night`) — a separate follow-on unit
  in the launch path (`docs/ROADMAP.md:657-661`); this unit is its substrate.
- **The § 7.3 Type 1 amendment** and all operator GPU passes (baseline spend, night #1,
  night #2, first gated evaluation) — the operator chain (`docs/ROADMAP.md:652-656`).
- **Rollout-level re-scoring / re-measurement** — the measured-once discipline
  (`PREREGISTRATION.md:121-138`) is enforced by the baseline's guard, never re-run by this
  unit.
- **Any `cli.py` subcommand / partition-guard change** — module doors only; the
  `test_reward_path_scope_is_partitioned` edge count stays at exactly three.
- **The dashboard, distillation, a second task family** — post-horizon
  (`docs/ROADMAP.md:588-593`).
- **A looser verifier, an LLM-judge reward, base-model training, data egress** — guardrails,
  not scope.

## Aspect Decomposition (proposed)

1. **`promotion-record-n`** — `SideCounts.weaker_wins` in gate.py, schema documented, the
   fail-closed reader (`read_promotion_record`) with its refusals.
2. **`report-writer`** — `build_honest_number_report` / `write_honest_number_report` in
   report.py: schema, § 4 shape, helpers by identity, declaration state, determinism, the
   loader-by-identity baseline-figure exception and the disjointness scan.
3. **`report-door`** — `loop/honest_report.py`: evidence composition by identity, the
   refusals (unmeasured baseline, missing evidence, unverifiable checkpoint, series
   disagreement, gitignored `--out`), exit discipline, `--render-declaration`, and the
   harness-reproduces-the-number assertions at the door.
4. **`amendment-and-home`** — § 10.9 Type 2 amendment; the one-home guard's sixth move (both
   docstrings, both file lists, `_ALL_HOMES`, planted controls); the committed
   declaration-only artifacts.
5. **`report-runbook`** — the operator's sheet + its guard (`tests/test_honest_number_runbook_guards.py`).

## Decisions (confirmed in the interview, 2026-08-27)

1. **N_final source:** extend the promotion record (`SideCounts.weaker_wins`) — recommended,
   accepted.
2. **Home + amendment:** new `reports/honest-number/` + § 10.9 Type 2 amendment in this unit,
   before any figure — recommended, accepted.
3. **Delta-series mismatch:** refuse by name — recommended, accepted.

## Gate resolutions (approved 2026-08-27, folded from the self-critique)

4. **The headline's "final" is the gate decision's function:** `promoted` → candidate;
   `rejected` → incumbent (candidate disclosed as the rejected attempt); `UNVERIFIED` → no
   headline, "no comparison was made". Never a delta that reads as a win.
5. **The incumbent's base is checked too:** both checkpoints' provenance must declare the
   same base as the baseline series; a mismatch is refused by name.
6. **Coverage renders on both sides;** the headline's `e` is the final side's `covered`.