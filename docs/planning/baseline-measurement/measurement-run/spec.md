# Spec — measurement-run (aspect 4 of baseline-measurement)

**PRD:** `../prd.md`. **Branch:** `feat/baseline-measurement/aliz`. This aspect is the
operator's sheet for the GPU pass that spends the § 3 baseline — exactly once.

## Problem slice and user outcome

Every arm in this repository is operator-executed from a runbook held by a guard; the
baseline measurement is the next one. The measurement is **spent exactly once** — a sheet
that tells the operator the wrong flags, a relative writable path, or a "re-measure to
confirm" instruction fails after the number is gone. The user outcome: the operator runs one
documented command chain from the sheet, the machinery is proven on fixtures first, the
measurement lands in the committed artifact home, and the finding records it — with the
§ 7.3-open base identity stated, never closed.

## In-scope requirements

1. **The runbook** at `docs/planning/baseline-measurement/measurement-run/runbook.md`:
   - opens with the **candidate resolution** — the 32B
     (`mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, the revision the night runbook
     resolves) stated as the runbook-resolved candidate, **not** a § 7.3 closure (the sheet
     states "§ 7.3 stays open" and never calls the base "pinned"/"selected");
   - the arm command chain: `uv run --project <primary>` `python -m whetstone.loop.baseline`
     with `--weights`, `--checkpoint` (the untrained 32B checkpoint, materialized via the
     aspect-1 writer at `checkpoints/<id>/`), `--heldout tasks/heldout/source-b.json`,
     `--tasks` (the private root), `--public`, `--runs`, `--workspace`, `--out
     reports/baseline-measurement`, `--recorded-on <date>`, `--run-id <id>` — every writable
     path **absolute**; then the render chain: `python -m whetstone.loop.baseline --render
     <evidence> --out reports/baseline-measurement --recorded-on <date> --checkpoint …`;
   - the before-you-run block (mlx extra installed, empty workspace, machine-level evidence,
     the machinery verified on the fixture suites first);
   - the halt conditions (a same-series artifact at `--out` = refusal, not a warning);
   - the killed-run restart (fresh `--run-id`; a half-written artifact is refused by schema,
     never repaired);
   - the post-run chain (evidence review → the render door → the finding committing the
     measured artifact);
   - the outcomes stated: a zero solved-count and a coverage below 12 of 12 are valid,
     publishable baselines (`docs/ROADMAP.md:470-471`); `recorded_on` is an input.
2. **The guard** `tests/test_baseline_runbook_guards.py` on the gate-runbook precedent
   (extended, never parameterized): the shared parse helpers
   (`_bash_blocks`, `_named_paths`, `_worktree_name`) imported from `test_runbook_guards.py`
   **by identity** (asserted `is`); the flag surface pinned against
   **`whetstone.loop.baseline.build_parser`** (the module door — no `cli.py` involvement);
   the properties:
   1. the parse really reads the sheet (anti-vacuity);
   2. every flag the chain passes exists in `baseline.build_parser`;
   3. every writable path named is absolute;
   4. exactly one worktree named, no stale one;
   5. the measured-once discipline is stated as a **refusal** — the sheet nowhere tells the
      operator to re-measure, re-render, or "confirm" the number (re-measuring until it
      flatters is selecting on the outcome);
   6. the machinery is verified on the fixture suites before the real pass;
   7. the candidate resolution: the 32B named, "§ 7.3 stays open" present, and no
      pinned/selected-base phrasing;
   8. the coverage and zero-score outcomes stated as publishable, never a halt;
   9. the post-run chain present (render door + finding), the killed-run behavior stated
      (fresh `--run-id`), and `--recorded-on` stated as an input.
   Watched failing against a deliberately wrong stub sheet (relative writable paths, a flag
   the parser does not define, a stale worktree, a "re-measure to confirm" instruction, no
   § 7.3 sentence, no fixture verification) before the real sheet exists.

## Out-of-scope boundaries

- The GPU pass itself and the finding — operator-executed after the sheet lands (every arm
  in this repository is).
- Any change to the door, the writer, the guard's shared helpers, or `cli.py`.

## Acceptance criteria (test-first)

1. The runbook's command chain parses against `baseline.build_parser` (every flag exists).
2. Every writable path in the sheet is absolute; exactly one worktree is named, and no stale
   one.
3. The sheet states the measured-once refusal, the § 7.3-open sentence, the publishable
   zero/coverage outcomes, the killed-run behavior, `recorded_on` as an input, and the
   post-run chain — each pinned by the guard.
4. A deliberately wrong stub sheet is refused by the guard (watched failing first).
5. The shared parse helpers are `test_runbook_guards`'s own, by identity.
6. No production code changes anywhere — the guard and the sheet are the whole aspect.

## Dependencies and sequencing

Aspect 4 of 4 (after `baseline-report`). Consumes: `baseline.build_parser` (aspect 2/3), the
landed suites (the fixture verification block), the worktrees skill's naming.

## Open questions / risks

- **The checkpoint materialization step** is part of the runbook's before-block: the
  untrained 32B checkpoint is written via the aspect-1 writer from the weights root's
  provenance (repo_id + revision) — the sheet states the exact command or names the helper;
  the guard pins its flags if it is a command.
- **The runbook lives in this unit's own aspect directory**, on the gate-runbook precedent;
  the post-run finding is not built here (operator's).