# Spec — gate-runbook (aspect 2 of gate-untrained-incumbent)

**PRD:** `../prd.md`. **Branch:** `feat/gate-untrained-incumbent/aliz`. This aspect makes the
operator's sheet for the first gated evaluation agree with the shipped dispatch: one night
plus the untrained base, never two nights, and never a night-001 incumbent.

## Problem slice and user outcome

`docs/planning/p3-promotion-gate/gate-runbook/runbook.md` is the operator's sheet for the
first evaluation that decides whether a night's candidate may replace the incumbent. It was
written when the first incumbent was a second night (runbook.md:36-39, 45-47, 88-89).
`docs/ROADMAP.md:663-671` reordered the launch path: the first incumbent is **the untrained
base**, materialized by the checkpoint writer, and the sheet must describe the code this unit
ships or it fails after a night has already been spent producing the candidate
(runbook.md:6-12). User outcome: an operator following the sheet gates night #1's candidate
against the untrained base in one night, with the sheet's commands verified against the
shipped parser and the replacement wording held by the guard.

## In-scope requirements

1. **The sheet's code references move to this unit's branch/worktree.** Header (runbook.md:3-4)
   and every `--project` value (`feat-p3-promotion-gate`) become this unit's worktree
   (`feat-gate-untrained-incumbent`), so Step 1's fixture verification runs the code the sheet
   describes.
2. **The incumbent is the materialized untrained base.** Candidate-resolution block
   (runbook.md:36-39): incumbent = an absolute path the operator materializes with
   `sft.write_baseline_checkpoint` **before** the gate (mirror the baseline measurement
   runbook's Step 2 command shape —
   `docs/planning/baseline-measurement/measurement-run/runbook.md:66-78` — its own path, e.g.
   `/Users/aliz/dev/at/whetstone/checkpoints/incumbent-base-001`; the § 3 checkpoint may not
   exist yet, since the baseline spend now runs *after* the first gated evaluation). The gate
   command's `--incumbent` (runbook.md:88-89) names that path.
3. **The "needs two nights" paragraph (runbook.md:45-47) is replaced.** New wording states:
   the first gated evaluation needs **one** night — the candidate is night #1's checkpoint and
   the incumbent is the untrained base the night started from — and states the § 3 boundary in
   words: this is the gate's incumbent, **not** the § 3 baseline measurement; different roles,
   different homes (`docs/ROADMAP.md:678-683`); a disagreement between the two figures is
   published as a finding, never reconciled.
4. **"Before the gate" (runbook.md:49-61) gains the materialization step**, and Step 4
   (read the record back, runbook.md:167-182) gains the sentence that the incumbent digest in
   the record is the constant untrained digest (`sha256("")` over the empty file set — the
   same value for every untrained base, which is why the candidate side is refused and the
   record is read by role, not by digest).
5. **The guard moves with the sheet** (`tests/test_gate_runbook_guards.py`):
   - `WORKTREE` (line 59) becomes `feat-gate-untrained-incumbent`;
     `feat-p3-promotion-gate` joins `STALE_WORKTREES` (60-68).
   - A new pin, `test_the_sheet_names_the_untrained_base_as_the_first_incumbent`, asserts:
     the materialization command (`write_baseline_checkpoint`) appears in a bash block whose
     checkpoint path is absolute; the `--incumbent` value in the gate command is not a night
     checkpoint (no `night-` in that value) and equals the materialized path; the replacement
     sentence appears ("untrained base" + the § 3 boundary); "two nights" does **not** appear.
     **Watched failing against a deliberately wrong stub sheet first** (a sheet that still
     says "two nights", a night-001 incumbent, or no materialization step — each must fail).
6. **All nine existing pins stay green against the edited sheet** — flags ⊆ parser,
   absolute paths, exactly one (new) worktree and no stale one, `R` by identity, record home,
   machinery-verified-before-real ordering, liveness sentence, no-rerun phrasing, the
   check-leakage block. The fixture-verification command (runbook.md:72-75) may gain the
   new gate test files if Phase 1 added any (the dispatch tests live in the existing files,
   so it is expected to stay as-is).

## Out-of-scope boundaries

- No code change — aspect 1 owns `gate.py`/`baseline.py`/`cli.py`. This aspect edits the
  sheet **after** aspect 1's code exists (code first, `docs/ROADMAP.md:670-673`).
- No other runbook: the night door, the baseline measurement, the honest-number report and
  the morning report sheets are untouched.
- No `PREREGISTRATION.md` § 10 amendment (this publishes nothing and adds no series).
- No change to the gate rule, the exits, or the halt conditions' substance — only the
  incumbent resolution and its wording.

## Acceptance criteria (testable)

- AC1: the edited sheet passes every existing guard test and the new pin; each new assertion
  was watched failing against a deliberately wrong stub sheet first.
- AC2: the sheet names exactly one worktree — this unit's — and `feat-p3-promotion-gate` is
  refused as stale.
- AC3: the gate command's `--incumbent` is the materialized untrained base path (absolute,
  not a night checkpoint), and the materialization block's checkpoint path is absolute.
- AC4: the replacement paragraph contains the one-night sentence and the § 3 boundary, and
  "two nights" appears nowhere.
- AC5: `uv run pytest tests/test_gate_runbook_guards.py -q` green; `uv run ruff check .`
  green.

## Dependencies and sequencing

- Depends on aspect 1 (`engine-dispatch`) being merged to the branch first: the sheet
  describes the dispatch, and the fixture-verification step runs the gate suites that prove
  it.
- Sequence: guard stub-sheet RED → guard pin GREEN (on the stub, then on the real sheet as
  edited) → sheet edits in the order the pins demand → full guard green.
- Feeds: the launch path's first gated evaluation (operator-executed, post-merge).

## Open questions / risks

- The materialized incumbent path's exact name — the sheet decides it (e.g.
  `checkpoints/incumbent-base-001`); the guard pins the *shape* (absolute, not a night
  checkpoint, same in the gate command and the materialization block), never the literal.
- The candidate resolution block's § 7.3 posture: the sheet must keep stating that the 32B is
  the runbook-resolved candidate and that § 7.3 stays open (mirror the baseline runbook's
  candidate-resolution wording, runbook.md:16-30) — folded into the replacement wording.