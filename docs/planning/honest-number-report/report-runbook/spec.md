# Spec — report-runbook (aspect 5 of honest-number-report)

## Problem slice

The report render is the last step of the operator chain (`docs/ROADMAP.md:652-656`: § 7.3
amendment → baseline spend → night #1 → night #2 → first gated evaluation → the P4 report →
the finding). The machinery exists (aspects 1-3) and the home exists (aspect 4); the operator
needs a sheet that scripts the render without drifting — held by its own guard on the
baseline-runbook precedent (`tests/test_baseline_runbook_guards.py`: flags pinned to the
shipped parser **by identity**, absolute writable paths, exactly one worktree and no stale
one, no re-run-to-confirm phrasing, machinery verified on fixture evidence before the real
render).

## In-scope

- `docs/planning/honest-number-report/report-runbook/runbook.md` — the operator's sheet:
  the render command(s) with the real flag surface (pinned to aspect 3's parser), absolute
  paths, the evidence pointers (the sealed baseline artifact, the promotion record, both
  checkpoints), the § 4 shape sentence, the decision-semantics statement (promoted /
  rejected / UNVERIFIED each render a defined document), the refusal sentences (series
  disagreement, unmeasured baseline — "refused by name, nothing written"), and the
  post-render chain (the finding; the number's narrative home is the finding, per the
  baseline runbook's precedent).
- `tests/test_honest_number_runbook_guards.py` — the guard, on the baseline-runbook
  pattern: shared parse helpers by identity (`_bash_blocks`, `_named_paths`, `_worktree_name`
  from the existing runbook-guard modules; `STALE_WORKTREES` from the gate-runbook guard),
  flags against `honest_report.build_parser()` by identity, absolute writable paths, exactly
  one worktree and no stale one, the fixture-verification-first ordering (the aspect 2/3
  suites before the real render), the "no re-render to confirm" discipline (the
  `RERUN_PHRASES` register), and the § 4/decision sentences present.
- The sheet states three things the machinery does not decide: the render waits for the
  first gated evaluation (two nights precede it); a killed render resumes nothing (fresh
  `--run-id`); the number is stated in the finding, never invented in the sheet.

## Out-of-scope

- The operator GPU passes themselves (baseline spend, nights, the gated eval) — their
  runbooks already exist (baseline measurement-run, night-door, gate-runbook).
- Any figure in the sheet — the sheet is committed before the render, like every runbook in
  this repository.
- The morning-report unit and its own edge.

## Acceptance criteria

1. The sheet's door and flags match aspect 3's shipped parser by identity (the guard parses
   the sheet's bash blocks and asserts every flag exists in `honest_report.build_parser()`);
   a flag the parser doesn't define fails the guard.
2. Every writable path in the sheet is absolute; exactly one worktree is named; no stale
   worktree name appears.
3. The sheet runs the fixture suites (aspects 1-3's tests) before the real render
   (ordered via `text.index`).
4. The refusal discipline is present ("refused by name, nothing written", series
   disagreement, unmeasured baseline) and no `RERUN_PHRASES` phrasing ("re-render to
   confirm", "run it again", "confirm the number").
5. The § 4 shape sentence and the decision-semantics statement appear; the UNVERIFIED case
   is stated as a published outcome ("no comparison was made").
6. The guard was watched failing against a deliberately wrong stub sheet (relative paths,
   a fake flag, a stale worktree, a re-render instruction, missing refusal sentences)
   before the real sheet existed — the module docstring records the watch.
7. The sheet contains no `\d+ of \d+` figure in any spelling.

## Dependencies & sequencing

- Depends on: aspect 3 (the parser surface the guard pins against) — the sheet and its
  guard cannot exist before the door does.
- Fifth and last of the aspects; nothing consumes it.

## Open questions

- None — the guard's pinned properties are the baseline-runbook pattern applied to aspect
  3's surface.