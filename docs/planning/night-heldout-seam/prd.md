# PRD — night-heldout-seam

**Unit:** `night-heldout-seam` · **Branch:** `feat/night-heldout-seam/aliz` · **Written:** 2026-10-10.
**Source:** the `whetstone-next` handoff (2026-10-10), as the inline brief in
`docs/planning/_card/issue.md`; the dig is `docs/planning/_card/understanding.md`.
**Core loop element:** ③ the never-regress promotion gate — at the exclusion its inputs carry;
② the nightly loop's launch chain. ① the reward does not change: nothing under `verify/`,
`tasks/`, or the gate's rule, exits and retry discipline moves.

## Problem Statement

The night runbook (`docs/planning/p2-rollouts/night-door/runbook.md`) is the operator's sheet
for the next night, and it still describes the pre-§ 10.16 world. The corpus was re-minted
under `--label` and the held-out split re-derived (`PREREGISTRATION.md` § 10.16, 2026-09-27);
`heldout-scorable` updated the *gate* runbook for the new document and never touched the
*night* sheet, so the sheet now disagrees with the code it runs:

1. **The five `--dev-subset belay-*` ids no longer exist.** Every id is `donor-b-<sha12>`/
   `donor-a-<sha12>` now. `_partition` refuses an id matching no task
   (`UnknownDevSubset`, `src/whetstone/bakeoff/run.py:1033-1052`) for probe and night alike —
   the sheet fails on its first command.
2. **The sheet never passes `--heldout`.** A night run verbatim draws the 12 held-out members;
   the training set is then *guaranteed* non-clean against `tasks/heldout/source-b.json`,
   `check-leakage` refuses it at the gate step, and M2's exit criterion — `whetstone gate`
   returns `promoted`/`rejected` on a real pair (`docs/ROADMAP.md` § 14) — stays unreachable.
   The portability-arm checkpoint (4 of 6 examples on a held-out task,
   `docs/planning/gate-leakage-guard/finding.md`) is the same leak made concrete.
3. **The sheet names artifacts that already exist.** `--run-id probe-001` and
   `--run-id night-001` point at real runs in the primary checkout: probe-001's ledger is
   `whetstone-run/1`, refused by every reader (so the sheet's own `check-probe` step commands
   a refusal today), and night-001's documents are covered by the never-rewrite rule. The
   sheet's own "Declare the inputs" text already says run ids are operator-typed — the
   hardcoded ids contradict it.

**Evidence it is real:** the sheet commands fail verbatim (stale ids → `UnknownDevSubset`);
no line of the runbook excludes the held-out membership; `git log` shows the sheet untouched
since 2026-09-05 (`c77cf2a`), predating the re-mint (2026-09-27).

## Goals & Success Metrics

Success is a night sheet whose commands run verbatim against today's corpus and commit the
night to the post-§ 10.16 pinned inputs, plus guards that would have caught the staleness.

- **Measurable:** every night-sheet command passes the parser and names only ids present in
  the re-minted corpus; the probe and night commands each pass `--heldout`; the guard suite
  fails against the current stale sheet and passes against the new one.
- **Measurable, downstream (a target, not a result):** the *next* night, run from this sheet,
  produces a training set that `whetstone check-leakage --run <it> --heldout
  $REPO/tasks/heldout/source-b.json` accepts with exit 0. This unit does not run that night;
  it makes the sheet from which the night can be launched honestly. No projected yield, no
  invented number appears anywhere in this unit.
- **Carried explicitly:** this unit produces no candidate and no number; it must not be
  written up as advancing yield (the § 14 zero is M1's, and M1's whole-function measurement is
  the operator's pending decision).

## User Personas & Scenarios

The operator (the founder, at the primary checkout, before a night): follows the sheet
verbatim — now it works. A future reader re-deriving the chain: reads a sheet that says which
pre-registered documents the night was pinned to and why the two dev ids that overlap the
held-out band are stated rather than dropped.

## Requirements

### Must-have

1. **`--heldout` on both commands.** The probe command and the night command each pass
   `--heldout $REPO/tasks/heldout/source-b.json`. The CLI keeps the flag optional by design
   ("off by default: the night is today's night, byte for byte" — `cli.py:415-428`); the
   sheet is the surface that commits the real night to the pinned input. No parser change.
2. **Post-mint dev ids.** The five dev ids appear in their `donor-b-*` form
   (`2e149603209a`, `353359e9ac6e`, `3e3051c4192a`, `844db07ed482`, `9dba3ea557f5`) in both
   commands; no `belay-`/`contig-` id appears in any command. The set is unchanged — decided
   with the operator, 2026-10-10.
3. **The overlap stated.** The sheet states that two dev ids —
   `donor-b-353359e9ac6e` and `donor-b-3e3051c4192a` — are held-out members under § 10.16,
   that a declared dev id inside the held-out band is exclusion, never a refusal
   (`night.py:227-230`), and that the gate still scores them (the gate has no dev exclusion —
   the eval is exactly the held-out membership, `gate.py:760, 1604-1615`).
4. **The § 10.16 pin and digest read-back.** The sheet cites `PREREGISTRATION.md` § 10.16
   (Type 1, 2026-09-27) and the scorable rule, and holds a digest read-back halt — the
   ledger's held-out record must name the digest of the committed
   `tasks/heldout/source-b.json` — mirroring the gate runbook's Step-5 wording
   (`docs/planning/p3-promotion-gate/gate-runbook/runbook.md:264-267`) and its guard's tests
   (`tests/test_gate_runbook_guards.py:802-894`). No live § 10.7 citation survives.
5. **Corrected denominator.** The "61 private + 1 public = 62" sentence becomes false twice
   over; the sheet states the re-derived draw: **51 private (66 − 5 dev − 10 held-out not
   already dev-excluded) + 1 public = 52 tasks**, each drawn `K` times, and says why
   (exclusion order: dev overlay first, held-out second).
6. **Run ids are operator-declared.** Probe and night `--run-id` are
   `<declared-at-run-time>`, and the sheet never names `probe-001` or `night-001` as a run id
   (they are real artifacts; probe-001's ledger is refused by every reader; night-001's
   documents are never rewritten). The probe-decision-gate's fresh-id rule — a killed probe
   restarts under a new `--run-id` — is stated in the sheet's own words. Path references in
   the sheet's prose follow the declared ids — including the post-probe `check-probe --run`
   path, which resolves from the *same declared probe run id*, and the post-night read-back
   paths (`runs/nights/<run-id>/…`, `checkpoints/<run-id>/…`).
7. **A post-night leakage step.** The night sheet commands `whetstone check-leakage --run
   <the night's run> --heldout $REPO/tasks/heldout/source-b.json` in "After the night", and
   halts on any non-zero exit. Document-only, no GPU; it names a seam failure at the source,
   before a checkpoint exists. (Decided with the operator, 2026-10-10; the gate runbook keeps
   its own Step 3 — two commanders are belt and braces, and the second costs nothing.)
8. **Watched-failing guards.** The guard suite (`tests/test_night_runbook_guards.py`) grows
   one assertion per new requirement — refuse a `belay-`/`contig-` id, refuse a missing
   `--heldout`, refuse a live § 10.7 citation, refuse a missing § 10.16 sentence, refuse
   `probe-001`/`night-001` as run ids, refuse a missing `check-leakage` step, refuse the
   stale denominator sentence — and every new assertion is **shown failing against the
   current stale sheet** before the new sheet exists (the repo's watched-failing discipline).
   The suite's *existing* pins that assert the old sheet's content (`DECLARED_DEV`,
   `test_every_declared_dev_id_is_passed_and_matches_the_hardened_contract`, and the
   block-parsing tests that read the command blocks) are reconciled in the same unit —
   deliberately, one pin at a time, never by weakening an assertion; every pin the new sheet
   cannot satisfy is either updated to the new honest statement or refused by the new sheet,
   and the reconciliation is visible in the commits.
9. **Docs ship with the unit.** `docs/STATUS.md` entry, `CHANGELOG.md` `Unreleased`,
   `docs/ROADMAP.md` M2 correction — in the same commit as the sheet+guards change, per the
   repo's rule that a claim and the code that makes it true arrive together.

### Should-have

10. The sheet's header/framing ("the first night") is updated where it now commands a *next*
    night from a tree that has already run one: the "Candidate resolution" prose cites the
    historical evidence; the run-id guidance is the operator's. No historical sheet is
    rewritten — the larger-base, format-hardening and probe-run sheets record completed runs.
11. **A live suite test pins the five dev ids against the machine corpus** — the second
    staleness in a month of the same class (#62's lesson): a corpus re-mint must fail the
    suite, not only the sheet's reader. The test loads `tasks/local/` and asserts each dev id
    exists and the two overlap ids are held-out members, skipping in CI with the reason named
    (the heldout-recomputation test's precedent); it fails loudly in the primary checkout on
    the next re-mint.

### Nice-to-have

12. A `check-probe` step prose note that the probe's own ledger will be `whetstone-run/3`
    (sealed) and that `check-probe` reads it through the verifying reader (its refusal of the
    historical `/1` probe-001 ledger is the reason the run id must be fresh).

## Non-Functional Requirements

- **No code changes under `src/`.** The parser, the loop, the reward, the gate and the
  leakage check are byte-identical when this merges. The deliverable is a sheet and the
  guards that hold it.
- The suite stays green (`uv run pytest -q`), ruff and mypy clean on the touched files.

## Technical Considerations

- **Exclusion order** (`night.py:249-261`): dev overlay first, held-out second — so the
  denominator arithmetic (R5) is an exact consequence of shipped code, not of the sheet's
  taste.
- **The digest read-back (R4) is the gate runbook's own pattern**: the loader refuses a
  doctored or superseded document by name (`HeldoutDigestMismatch` etc.,
  `heldout.py:251-280`); the sheet's halt sentence makes the operator compare the ledger's
  held-out record to the committed document rather than trust a side-channel.
- **`UNVERIFIED` discipline is untouched.** No sheet step may restate an unverified outcome
  as a pass; the zero-yield outcome stays a published result, not a halt (runbook's own
  Halt condition 4, unchanged).
- **Reward-hacking surface:** none — no reward, no judge, no model opinion anywhere. The
  adversarial shape of this unit is *the sheet itself*: a sheet that looks right but excludes
  via `--dev-subset` alone (no held-out record in the ledger), or drops the two overlap ids
  silently, or names a historic run id — each is refused by the guards by name.

## Risks & Open Questions

- **A future corpus re-derivation changes 66/12 and breaks the pinned denominator sentence —
  deliberately.** The guard pins the sentence *and* the arithmetic; a changed corpus is a
  halt, exactly as a changed held-out document is. Stated, not softened. Should-have 11
  makes the same breakage fail the suite in the primary checkout, not only a sheet reader.
- **The rewrite may contradict pins in the existing guard suite** — its block-parsing tests
  read the command blocks verbatim and its prose pins quote the sheet's sentences. The
  reconciliation is part of the `guards` aspect (R8), in both directions: the new assertions
  fail against the old sheet, and any old pin the new sheet cannot honestly satisfy is
  updated deliberately on the record, never weakened.
- **No real run exercises the new sheet in this unit.** The suite can pin the sheet's text
  and the parser's flags, not a GPU night. The honest limit is stated in the unit's STATUS
  entry.
- **Open (small):** the exact placement of the `check-leakage` step within "After the night"
  (before or after the checkpoint re-hash — the plan decides; neither touches what the step
  proves) and the exact run-id prose the guard pins (chosen from the gate runbook's wording
  pattern in the plan).

## Out of Scope

- Any change under `src/` — in particular making `--heldout` required, or changing
  `check-leakage`, `check-probe`, the gate, the held-out loader, or the reward.
- The four malformed-checkpoint-shapes defect, `card`-on-untrained, per-side seal disclosure
  in `GateOutcome`, the one-writer-test hardening — the standing open follow-ups
  (`docs/STATUS.md`, 0.20.0/0.21.0 entries); named alternates, not this unit.
- The whole-function measurement (M1), raising `K`, the portability CPU dtype, producing a
  candidate, running a gate, or spending the § 3 baseline — all the operator's.
- Rewriting any historical sheet (larger-base, format-hardening, probe-run, baseline) — they
  record completed runs.
- The version bump, tag and release.
- Any number that is not produced by the verifier or a document it sealed.

## Aspects (proposed)

1. **`guards`** — the extended guard suite: the new refusals (R2, R3-left half, R4, R5, R6,
   R7, R8) demonstrated watched-failing against the current sheet; the deliberate
   reconciliation of the suite's existing pins (R8); the live dev-ids corpus test (S11).
   Owns R8 first, RED against the stale sheet.
2. **`sheet`** — the runbook rewrite per R1-R7, R10, N12. Owns GREEN for the guards.
3. **`docs`** — STATUS, CHANGELOG `Unreleased`, ROADMAP M2 correction. Lands last, in the
   same commit as the write-up rule requires.

**Sequencing:** `guards` first (RED), then `sheet` (GREEN), then `docs`; the release commit
and tag are separate and outside this unit.