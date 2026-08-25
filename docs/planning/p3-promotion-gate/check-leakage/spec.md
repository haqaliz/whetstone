# Spec — check-leakage (aspect 5 of p3-promotion-gate)

**PRD:** `../prd.md`. **Branch:** `feat/p3-promotion-gate/aliz`. This aspect ships the roadmap's
exit criterion: `uv run whetstone check-leakage` exits 0 — zero overlap between the training set
and the held-out set (`docs/ROADMAP.md:449-450`).

## Problem slice and user outcome

The night excludes held-out tasks at the partition seam (aspect 2), but exclusion alone is a
behaviour; the roadmap demands a **proof**. The user outcome: a command that takes a run's training
set and the held-out document, asserts disjointness, names any overlap instead of counting it, and
exits accordingly.

## In-scope requirements

1. **The command** `whetstone check-leakage --run <runs/<id>> --heldout <doc>` (the run's
   `dataset.json` task ids are the training set; the held-out document is aspect 1's committed
   artifact). It lives in `src/whetstone/loop/check_leakage.py` (exempt) with a **third documented,
   function-local edge** from `cli.py` — the partition guard extended test-first alongside
   `gate-core` (aspect 3, AC5), each edge proven able to fail against a planted import.
2. **Disjointness is proven, not counted.** An overlap names the ids — a named violation, never a
   bare count — and exits nonzero (1). Disjoint → exit 0. The verdict is printed as a count over
   its denominator: "0 of N training examples touch a held-out task" — every rate carries its
   denominator (`PREREGISTRATION.md:157`).
3. **The loader by identity.** The held-out loader (aspect 1) is imported by identity; a doctored
   document, a hand-edited membership, an unknown field, or a digest mismatch refuses the run by
   name before any comparison.
4. **Refusals by name.** A `runs/<id>/dataset.json` that does not parse, a run directory that is
   not a night-written run (no ledger), a held-out set of zero, and a training set of zero (an
   empty training set is trivially disjoint — the check succeeds, and the output says so) are each
   handled by name, never silently.
5. **Both sides' denominators.** Source B's held-out membership is the check's subject; source A's
   training examples (public source tasks in the dataset) are reported beside it — both sources'
   overlap status disclosed, per "both sources always published together" (`PREREGISTRATION.md:142-147`).
6. The path walks inference-free.

## Out-of-scope boundaries

- No prevention — prevention is aspect 2's partition seam; this aspect proves it.
- No gate decision, no promotion record.
- No change to `src/whetstone/verify/`, `src/whetstone/tasks/`, `patch.py`, `attribution.py`.

## Acceptance criteria (testable)

- AC1: a fixture run whose training set is disjoint from the held-out document exits 0 and prints
  the count over its denominator.
- AC2: a fixture run with one held-out task in its training set exits nonzero and **names the id** —
  watched failing first against a version that only counts.
- AC3: a doctored held-out document refuses by name; an unparseable dataset refuses by name; a
  run directory without a ledger refuses by name.
- AC4: an empty training set exits 0 and states it; a held-out set of zero refuses by name.
- AC5: the partition guard holds — exactly three documented function-local edges (night, gate,
  check-leakage), a fourth fails the build.
- AC6: `uv run pytest` green; ruff and mypy over `src/` green; the AC2 pins byte-identical.

## Dependencies and sequencing

- Depends on aspect 1 (the loader by identity) and on the dataset document schema
  (`loop/dataset.py`, `whetstone-training-set/1` — read by identity, never re-parsed).
- Sequence: the seam with `gate-core`'s guard update → the check core + fixtures → the CLI door →
  the named-violation adversarial test.
- Feeds: the operator's post-night chain (aspect 6's runbook) and P4's report.

## Open questions / risks

- Whether the training set should be the dataset document's examples or the ledger's task set —
  the dataset document records what was actually trained on (the strict-PASS selection), which is
  the honest subject; the plan decides and asserts the choice.
- A leaked training set found by this command is evidence of an aspect-2 regression — the plan
  should wire the finding's wording so a nonzero exit is actionable, not merely alarming.