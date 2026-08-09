# Spec — `measured-analysis` (aspect of `format-hardening-measurement`)

**PRD:** `docs/planning/format-hardening-measurement/prd.md` · **Understanding:**
`docs/planning/format-hardening-measurement/understanding.md`
**Upstream:** `docs/planning/p2-format-hardening/measured-arm/plan_20260809.md` (Phases 3–4),
`runbook.md` (post-run section), `spec.md` (D-arm3, D-arm4).

## Problem slice

The post-run analysis chain the measured-arm runbook names does not exist. This aspect builds
it: the deterministic, offline, stdlib-only before/after comparison (the runbook's "Phase 3
comparison tooling"), the report-assembly door (the first production caller of the shipped
`report.build_contract_comparison`/`write_comparison`), and the committed docs that close the
slice (finding, CLAUDE.md status, CHANGELOG).

## In scope

- `src/whetstone/bakeoff/comparison.py` (new): CLI `python -m whetstone.bakeoff.comparison`
  with two modes — the breakdown mode and `--render-report`.
- `tests/bakeoff/test_comparison.py` (new): RED first, synthetic fixtures.
- Gitignored outputs under `runs/format-hardening-preanalysis/`: the `whetstone-comparison/1`
  JSON document and `comparison.md` (the runbook's named home), plus the door's real render
  into `reports/format-hardening/` when the arm has run.
- `docs/planning/p2-format-hardening/measured-arm/finding.md`, the CLAUDE.md status-block
  rewrite (incl. the stale no-tags claim fix), the CHANGELOG entries.

## Out of scope

- Any change to `src/whetstone/verify/`, `patch.py`, `attribution.py` (frozen, byte-identical).
- Any autopsy taxonomy change; any change to `preanalysis.py`'s semantics or output shape.
- P2 proper, § 7.3, the held-out split, the gate retry count, prompt-side hardening.
- Adding or removing a file under `reports/` (the six-file one-home list is pinned).
- The operator's GPU arm itself.

## Acceptance criteria (testable; tests written before code)

1. `uv run pytest tests/bakeoff/test_comparison.py` green — written RED first.
2. The breakdown mode over synthetic autopsy + journal + pre-analysis fixtures: per-arm
   per-candidate cause counts; per-arm rollout tallies and denominators; per-arm generation
   seconds; the per-record trigger mapping **asserted against the pre-analysis document's
   decisions** (a planted mismatch → named violation in the document and exit nonzero, never
   smoothed); a journal whose control shows no `INTACT` probe → refused with the reason named;
   a stem mismatch between `--journal` and `--autopsy` → exit 2; `--out` under a published
   path → refused before anything is read (exit 2); byte-identical output across invocations.
3. Real-data verification: run over the stored arms (`runs/diff-autopsy/{arm-a,budget-2048}.json`,
   `runs/{arm-a,budget-2048}/journal.jsonl`, `runs/format-hardening-preanalysis/ceiling.json`
   by absolute path from the primary checkout) — produces the gitignored
   `runs/format-hardening-preanalysis/comparison.{json,md}` with zero mapping violations (the
   stored runs' contract), and the render is byte-identical across invocations.
4. The report door on synthetic arms: renders exactly
   `reports/format-hardening/{report.md,report.json,cost.json}` into a test directory; the
   hardened arm's section carries the retry trio and the baseline arm's does not; both token
   spends appear in prose and `cost.arms[].generation_seconds`; the non-comparability
   sentence is present; a planted `N of M` collision with `reports/baseline/` fails the
   disjointness guard; an empty journal or an unproven control refuses with the reason named.
5. The committed `reports/format-hardening/` stays the declaration (three files, arms empty)
   — the arm has not run; nothing published claims a figure it didn't produce.
6. `docs/planning/p2-format-hardening/measured-arm/finding.md` exists, states the hold
   decision, and contains no figure about a model.
7. Full suite green; `ruff check .`, `mypy src/`, `whetstone --help` exit 0; the one-home
   guards and `tests/test_docs.py` green; diff-stat pins prove `verify/`, `patch.py`,
   `attribution.py` unchanged.

## Dependencies / sequencing

Phases 1 → 2 → 3 → 4, sequential. Reuses by identity: `preanalysis.analyze_document` /
`combine` / `refuse_published_out` / `is_inferred_truncation`; `diffcheck.trigger_of_cause`;
`journal.Journal(path).replay()`; `report.tally`, `GenerationContract.parse`, `ContractArm`,
`build_contract_comparison`, `write_comparison`; `autopsy.IGNORED_OUT_ROOTS`. No network, no
model, no env vars; all fixtures synthetic and offline.

## Open questions

- Exact JSON field layout of `whetstone-comparison/1` — resolved in the plan via fixture-first
  TDD; the top-level fields are named there.
- The door's `--recorded-on` is an input, never the clock (the runbook precedent).
