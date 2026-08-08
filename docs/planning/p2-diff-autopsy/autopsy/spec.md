# Aspect spec — autopsy (the classifier)

**Feature:** `p2-diff-autopsy` · **PRD:** `docs/planning/p2-diff-autopsy/prd.md`
**Covers:** the whole slice — one aspect: `src/whetstone/bakeoff/autopsy.py`, its tests, the
`verify/`-untouched guard, the operator step, and the finding.

---

## Why this aspect exists

The yield-probe correction demanded a fourth fix be proposed only after someone read the
stored completions (`prd.md:84-89`). The read is done by hand (`dig-transcripts.md`); the
autopsy turns it into a reproducible measurement: a deterministic, stdlib-only, offline
classifier that assigns every stored completion exactly one grounded content-shape cause,
asserts the fine→coarse mapping against the run's own `attribution.json`, and writes
breakdowns only into gitignored artifacts.

## In-scope

- `src/whetstone/bakeoff/autopsy.py`: the fine pass (markers, loop, hunk walk, precedence),
  the fine→coarse mapping and its per-record assertion, the breakdown, and the CLI.
- `tests/bakeoff/test_autopsy*.py`: fixtures, determinism, precedence, mapping, refusals,
  the AST no-inference walk, the `verify/`-untouched diff-stat guard.
- The operator step: run the autopsy over both stored runs (by absolute path into the
  primary checkout), write breakdowns to gitignored roots, verify zero `unrecognised-shape`,
  write the divergence-vs-dig report.
- `docs/planning/p2-diff-autopsy/finding.md`: the committed finding — walls, not numbers.

## Out-of-scope boundaries

- Nothing under `src/whetstone/verify/`, `patch.py`, `attribution.py`, or the reward-path
  guards moves (imports only).
- No checkout layer, no `git apply`, no `--tasks` flag: coarse causes come from the run's
  own `attribution.json` (D3).
- No format-hardening fix, no re-measured PASS counts, no `reports/` additions, no
  `PREREGISTRATION.md` amendment.
- No network, no model, no new dependency.

## Acceptance criteria (testable — written first, watched failing where adversarial)

1. Every primary cause and every marker has a fixture — a synthetic replica of an observed
   shape, never a verbatim completion — and classifying a fixture twice yields identical
   `(cause, detail, markers)` (PRD AC4; determinism).
2. The precedence table's orderings hold: loop-dominant NoDiff → `im-start-loop`; loop +
   well-formed diff → `well-formed` with `loop-present` marker; walk-ended-with-counts-
   remaining in the first hunk → `hunk-dies-early` with the correct death detail; a body
   extending beyond declared counts → `hunk-count-mismatch`; header-without-hunk →
   `header-without-hunk`; an unrecognisable completion → `unrecognised-shape` by name
   (PRD AC5). A planted unrecognisable shape fails the completeness control; a marker
   detector with no fixture fails.
3. The fine→coarse mapping is a pure dict; a missing entry fails the suite; a record whose
   recorded coarse cause contradicts its fine cause is reported as a divergence — watched
   failing against a credulous mapping first (PRD AC6). `UNATTRIBUTED` is always allowed.
4. The CLI refuses a non-gitignored `--out` before any analysis; a missing transcript or
   attribution file exits 2 with the reason named; `git check-ignore` answers "ignored" for
   the documented breakdown root (PRD AC7, trailing-slash form).
5. The AST walk over `autopsy.py` and its test asserts no inference import, with an
   anti-vacuity control that sees the imports the modules actually make (PRD AC8).
6. The new guard: `git diff --stat origin/master -- src/whetstone/verify/` is empty —
   written first and watched failing (PRD AC2; D8).
7. The fine pass uses `patch.py`'s own functions by identity — `extract_patch` and its
   privates imported, never copied — and `patch.py` has no diff on this branch (PRD AC3).
8. The operator step: breakdowns for both stored runs exist under gitignored roots with
   schema `whetstone-autopsy/1`, zero `unrecognised-shape`, and the divergence-vs-dig list
   written beside them (PRD AC9).
9. `docs/planning/p2-diff-autopsy/finding.md` exists, names the wall and the supported
   roadmap response, carries the four disclosures (truncation inferred; dig counts
   provisional; breakdown gitignored and authoritative; the held-test-aimed diff is
   attempt-shaped, not a counted hack), and contains no figure about a model (PRD AC10).

## Dependencies and sequencing

- Phase 1 (markers + loop) → Phase 2 (hunk walk + precedence) → Phase 3 (mapping + records)
  → Phase 4 (CLI + locality + document) are one chain.
- Phase 5 (the `verify/`-untouched guard + the AST walk tests) is independent — parallel.
- The operator step and `finding.md` come after the full gate is green.
- Nothing else in `docs/planning/` blocks this aspect: `patch.py`, `transcript.py`,
  `attribution.py`, and the guards it depends on are all shipped.

## Open questions or risks

- The `hunk-dies-early` ↔ `hunk-count-mismatch` margin is fuzzy (`dig-transcripts.md` § 5
  Q1): the mechanical rule is "first-hunk death → dies-early; any later-hunk death or
  extends-beyond → count-mismatch", and divergence from the dig's 45/39 split is reported
  as a finding, never reconciled (PRD D1, D9).
- Truncation (`hunk-dies-early` with death `end-of-output`) is inferred from shape — the
  breakdown labels it *inferred* (PRD D5).
- `no-diff` fixtures are `inherited-not-observed` (the category is the extractor's
  vocabulary, not an observed record) — labelled as such (PRD § 8 gap 2).
