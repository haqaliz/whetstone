# Spec — execution (measured-arm-run)

**Aspect of:** `docs/planning/measured-arm-run/prd.md` · **Written:** 2026-08-12
**Requirements source:** PRD M1-M8, S1-S3, N1, and the out-of-scope list.

## Problem slice

The format-hardening arm is built, runbooked, and unrun. This aspect executes it and lands the
measured before/after: refreshed runbook → operator GPU pass → post-run analysis chain →
two-contract report → after-finding, in a single unit whose acceptance is artifacts and exit
codes, never narratives.

## In-scope

1. **Runbook refresh (M1, M2, M8, S2):** repoint `runbook.md:29` (arm command CWD) and
   `runbook.md:120,127,133,144` (`uv run --project` targets) onto the unit's worktree, using the
   54bea44 pattern — CWD at the primary checkout, branch code via `uv run --project <worktree>` —
   so `--out`, `--workspace`, `--journal`, `--transcript` all resolve into the primary's gitignored
   `runs/`. Fix the stale dev-subset citation (`run.py:951` → `run.py:540-542`). Narrow the
   locality claim to the three tools that actually gate (`autopsy`, `preanalysis`, `comparison`;
   `attribution.py` has no gate and stays pinned). Add the killed-run restart procedure (M8) and
   the before-you-run block (S2: `uv sync --extra mlx`, empty-workspace discipline, evidence is
   machine-level). Replace placeholder dates with "declared at run time".
2. **Runbook guard test (S3):** a test that parses the runbook's command block and asserts
   (a) every flag named exists in `build_parser` (`src/whetstone/bakeoff/run.py`), and (b) the
   worktree paths are structurally consistent — exactly one worktree path across the arm command
   and the post-run commands, under `.claude/worktrees/`, with the arm command's CWD at the
   primary checkout. Written test-first: today's runbook is RED (two different worktree names).
3. **The arm run (M3):** the operator executes the refreshed command from the primary checkout.
   `--recorded-on` declared at run time. All artifacts gitignored; none committed.
4. **Post-run chain (M4):** attribution → autopsy → comparison breakdown, with the runbook's
   verify steps: zero `unrecognised-shape` **or** a named-divergence finding; zero mapping
   violations **or** a named violation with nonzero exit. A surfaced defect is fixed test-first
   in this unit (S1).
5. **Report + finding (M5, M6, M7):** `--render-report` into `reports/format-hardening/` with
   both arms; `finding.md` from hold → measured, per the pre-committed fork rule (M7), restating
   no classifier count; `CLAUDE.md` status + `CHANGELOG.md` in the same commit.

## Out-of-scope

- P2 rollouts, the held-out split, the promotion gate, any generation-contract or trigger-mapping
  change (except an S1 taxonomy correction the measurement demands).
- Changes to `verify/`, `patch.py`, `attribution.py` (AC2-pinned) beyond an S1 correction.
- Any PREREGISTRATION amendment (R5: untouched).
- Committing evidence (transcripts quote the user's own code; refused under any published path).

## Acceptance criteria (testable)

- **AC1:** `tests/test_runbook_guards.py` exists; it was RED on the pre-refresh runbook (two
  distinct worktree names) and GREEN after the refresh. It is deterministic, offline, stdlib-only,
  and passes on CI (no absolute machine paths asserted as existing).
- **AC2:** the refreshed `runbook.md` names exactly one worktree, and the arm command's CWD is
  the primary checkout (the 54bea44 pattern). No stale `feat-p2-format-hardening` /
  `feat-format-hardening-measurement` reference remains in the runbook's command sections.
- **AC3:** `runs/format-hardening-arm-evidence/{journal.jsonl,transcript.jsonl}` exist, and the
  run's report exists under its `--out` with the retry contract fields
  (`retry_budget`, `retry_template_sha256`, `diagnosis_vocabulary_version`, `retrieval`).
- **AC4:** attribution, autopsy, and comparison documents exist; the autopsy carries zero
  `unrecognised-shape` **or** a named-divergence finding; the comparison reports zero mapping
  violations **or** a named violation (nonzero exit, never reconciled).
- **AC5:** `reports/format-hardening/{report.md,report.json,cost.json}` render both arms
  (baseline + hardened) with both contracts, both token spends, the ceiling the arm was measured
  against, the non-comparability sentence, and the breakdown pointer — and the door refused any
  half-truth render on the way (no missing journal / unproven control / zero arms passed).
- **AC6:** `finding.md` states the measured before/after per the M7 rule, quotes the rule, and
  restates no classifier count; `CLAUDE.md` status block and `CHANGELOG.md` updated in the same
  commit as the report render.
- **AC7:** full suite green (`uv run pytest`), `ruff` and `mypy` clean, `tests/test_docs.py` and
  the one-home guards green, and the AC2 pins hold (`git diff --stat origin/master -- src/whetstone/verify/ src/whetstone/bakeoff/patch.py src/whetstone/bakeoff/attribution.py` empty).

## Dependencies & sequencing

- The dig verified all prerequisites: every runbook flag exists in `build_parser`
  (`run.py:691-839`), the five dev-subset ids exist, the corpus (belay 21, contig 45) and
  weights (three candidates) are in the primary, and the evidence directory does not exist.
- Sequencing: refresh → guard test (RED→GREEN) → operator run → post-run chain → report/finding.
  The operator run is the human checkpoint (D-arm3: the analysis after it is agent-verifiable).

## Open questions / risks

- The measurement's own content (flat arm, taxonomy gap, mapping violation) — each has a named
  response (R-c / S1 / M4), none is a blocker.
- The arm's runtime above the measured floor (~1.5 h) is unknown; plan for a night.
