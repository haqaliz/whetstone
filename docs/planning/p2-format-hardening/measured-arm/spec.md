# Spec — `measured-arm` (aspect 4 of `p2-format-hardening`)

**Boundary:** the offline pre-analysis (the conversion ceiling), the operator runbook for
the hardened arm, the post-run attribution/autopsy, the before/after cause breakdown, and
the report's final assembly. Depends on aspects 1–3.

## Problem slice

The slice's deliverable is a measured before/after cause breakdown, and the measurement
must be *pre-committed*: the ceiling is named before any GPU spend, the arm runs under a
declared contract, and the breakdown is compared against the two stored baseline runs — as
evidence, never as a promise.

## Decisions

- **D-arm1 — The pre-analysis is a code step, not a hand-read.** A small pure module
  (`src/whetstone/bakeoff/preanalysis.py`) reads the two stored autopsy outputs
  (`runs/diff-autopsy/{arm-a,budget-2048}.json` — gitignored, primary checkout, read by
  absolute path) and applies the trigger mapping (aspect 1) to every record, counting per
  candidate and per trigger: the retry-eligible subset of the dig's 84 `WOULD_NOT_PARSE`
  records (`dig-transcripts.md:324-327`), the `end-of-output`/`im-start-loop` non-trigger
  remainder, and — the **ceiling** — the count of retry-eligible records that a retry could
  plausibly convert (retry-eligible minus records whose death is inferred truncation; the
  exact definition is written in the module docstring and is a finding's property, never a
  promise). A ceiling near zero halts the arm (PRD R5: the D2a discipline).
- **D-arm2 — Dev subset named before the run.** The 3–5 task ids excluded via `--dev-subset`
  are chosen during the pre-analysis (the tasks whose prompts the retry template was tuned
  against) and written into the runbook before the arm starts; `ScoredDevSubset` enforces.
- **D-arm3 — The run is operator-executed, the measurement is agent-verified.** The arm is a
  GPU pass (≈1.5 h+ per the yield probe's measure — a measured figure, labeled as such) —
  the plan documents the runbook; the *analysis* after it (attribution, autopsy, breakdown,
  report assembly) is deterministic, offline, and verifiable by the agents team.
- **D-arm4 — The before/after is a comparison of contracts.** The baseline arm (stored
  runs, autopsied 2026-08-09) and the hardened arm differ in contract and in token spend
  (1 draw vs up to 3 per task) — the report states both contracts, both spends, and the
  non-comparability sentence; a bucket shift is reported as a contract effect, never as a
  model gain (PRD R6).

## In-scope requirements

- `src/whetstone/bakeoff/preanalysis.py` — stdlib-only, deterministic, offline: reads the
  autopsy outputs' fine causes, applies the trigger mapping, writes the ceiling document
  under a gitignored root (refused under published output — the autopsy's own rule,
  `autopsy.py:727-745` pattern); its own no-inference AST walk.
- The runbook (`docs/planning/p2-format-hardening/measured-arm/runbook.md`): exact
  commands, all required flags (`--tasks` per donor, `--public/--pool/--funnel/--weights/
  --out/--workspace/--timeout/--recorded-on`, `--journal` + `--transcript`, `--dev-subset`
  ids), weights/corpus by absolute path from the primary checkout, empty workspace per run,
  the retry-enabled composition (aspect 2), expected artifacts, halt conditions (ceiling
  near zero; any `UnstubbedPrompt`-style failure), and the AC7 discipline (journal +
  transcript so the rerun is per-task checkable).
- Post-run analysis (deterministic): `attribution` → `autopsy` over the new transcript
  (decided completions, zero `unrecognised-shape` or the named-divergence finding the
  instrument requires), then the before/after breakdown — both stored arms and the new arm,
  in the gitignored homes.
- The report: `reports/format-hardening/` (aspect 3's writer), both arms, contract fields,
  token-spend disclosure, the ceiling the arm was measured against, the non-comparability
  sentence, and the pointer to the breakdowns.
- Final gates: full suite green, `ruff`/`mypy` clean, diff-stat pins intact, `§ 10.4`
  guards green.

## Acceptance criteria (tests written first, where code)

1. `uv run pytest tests/bakeoff/test_preanalysis.py` green — the trigger mapping applied to
   synthetic autopsy records counts correctly; a near-zero ceiling is distinguishable from
   a real one; the document is written only under a gitignored root.
2. The runbook exists with all flags, the dev-subset ids, and the halt conditions.
3. Post-run: the new transcript autopsies with zero `unrecognised-shape` (or the named
   divergence); the breakdown compares the stored arms and the new arm per candidate.
4. The report exists in `reports/format-hardening/` (guard green), carries both contracts,
   both token spends, the ceiling, and the non-comparability sentence.
5. No baseline figure is restated anywhere outside `reports/baseline/`.

## Out of scope

- The validator, retry, transcript, contract, and report machinery — aspects 1–3.
- Any change to `verify/`, `patch.py`, `attribution.py`.
- Closing `PREREGISTRATION.md` § 7.3, setting a threshold, or predicting any count.

## Open questions / risks

- The ceiling definition (which retry-eligible records are "plausibly convertible") is a
  judgement written into `preanalysis.py`'s docstring before the run — it is a finding's
  property and the report states it, never a promise.
- Whether `header-without-hunk` is a trigger is decided by the pre-analysis evidence and may
  move the mapping (aspect 1 parameterised it for exactly this).
- The arm's runtime is the yield probe's measured ~1.5 h for the baseline contract; retries
  add generation time — stated as unknown rather than guessed.
