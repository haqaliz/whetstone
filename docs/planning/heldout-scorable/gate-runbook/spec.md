# Spec — gate-runbook (aspect 5 of heldout-scorable)

**Aspect dir:** `docs/planning/heldout-scorable/gate-runbook/` · **Written:** 2026-09-27.
**Source:** `docs/planning/heldout-scorable/prd.md` (must-have 8),
`docs/planning/heldout-scorable/amendment/spec.md` (§ 10.16),
`docs/planning/heldout-scorable/rederivation/spec.md` (the final document).
**Core loop element:** ③ gate (the operator's chain).

## Problem slice

The gate runbook (`docs/planning/p3-promotion-gate/gate-runbook/runbook.md`) is the
operator's instruction sheet for the next gated evaluation — the first one that can reach a
decision. It cites the held-out split as "fixed by `PREREGISTRATION.md` § 10.7 (Type 1,
2026-08-24, closing § 7.1)" (`runbook.md:209-211`) — a statement that is now false: the
split is re-derived by § 10.16 under the scorable rule. The sheet must be rewritten
code-first (the established discipline: the guard's new pin is written first and watched
failing against a stub sheet, then the sheet is edited to satisfy it).

## In scope

- `docs/planning/p3-promotion-gate/gate-runbook/runbook.md` — the held-out paragraphs
  (step 5's digest statement `:209-211`, and anywhere the split's provenance is named):
  cite § 10.16, name the scorable rule (a member is held out only if its oracle can be
  built under the declared budget; the exclusion is by class, sealed in the document's
  rule digest), and state the § 3 series consequence where the sheet's own new-series
  paragraph lives (the baseline-measurement sheet's phrasing is the model: a changed
  held-out split is § 3's legitimate new series, never an extension).
- `tests/test_gate_runbook_guards.py` — the new pins, RED first (watched failing against a
  deliberately wrong stub sheet, then against the real sheet as edited): the § 10.16
  citation present; § 10.7 no longer cited as live; the scorable-rule sentence present;
  the digest-equality halt (step 5) unchanged in discipline.
- `docs/STATUS.md` — the unit's appended entry (the repo's rule: a capability is written up
  in the same commit that lands it; this aspect is the last to land). It records: the
  gate-liveness defect (#60) and its closure — the re-derived split (§ 10.16), the re-minted
  corpus (#62 pairing), the loader's fail-closed supersession, and the honest remainder:
  the gate has still not produced a `promoted`/`rejected` decision (no candidate has scored
  against the new document), and a `rejected` 0-0 remains a valid first outcome.
- `CHANGELOG.md` — the unit's `[Unreleased]` entries (the repo's release-record discipline).

## Out of scope

The gate's code and semantics (untouched by design); the amendment (§ 10.16, landed);
the re-derived document (landed); any other runbook (the night door, baseline, honest-number
sheets reference the held-out document only through the gate's — verify, do not assume).

## Acceptance criteria (testable, written first)

- **AC1.** The guard's new pins are written first and fail against a deliberately wrong stub
  sheet and against the current sheet (RED), then pass against the edited sheet (GREEN).
- **AC2.** The sheet cites § 10.16 as fixing the split; the § 10.7 citation is gone from the
  sheet's live instructions (history in git; never edited out of a past record).
- **AC3.** The sheet names the scorable rule (exclusion by class under the declared budget;
  rule digest sealed in the document) in the paragraph where the split's provenance is
  stated.
- **AC4.** The sheet's halt conditions still name the digest-equality refusal (a changed
  document is a halt, never a rerun) — unchanged discipline, pinned.
- **AC5.** `docs/STATUS.md` gains the appended entry in the same commit as the runbook edit;
  `CHANGELOG.md` gains the `[Unreleased]` entries; neither edits history.
- **AC6.** The full suite stays green; the other launch-chain sheets are untouched.

## Dependencies & sequencing

Depends on aspects 2-4 (the amendment number, the final document, the rule). Final aspect:
`STATUS.md`/`CHANGELOG.md` land here, per the repo's rule that status is written in the
commit that ships the capability.

## Open questions / risks

- **Which other sheets cite the split's provenance.** The night door and honest-number
  sheets reference the held-out document as an input path, not as a provenance citation —
  verify with a grep; if one cites § 10.7 as live, it is in scope of this aspect (its own
  guard suite updates with it, RED first).
- **The honest remainder.** The runbook and STATUS must not imply the gate has fired since
  `gate-001`: no candidate has scored against the new document. The next run is the first
  that can reach a decision.