# Aspect spec — docs

**Unit:** `night-heldout-seam` · **Aspect:** `docs` · **PRD:** `docs/planning/night-heldout-seam/prd.md`.

## Problem slice

The repo's rule: a capability and its write-up land in the same commit, so the claim and the
code arrive together and neither outlives the other. This unit's capability is a sheet and
its guards; its write-up is the three named documents.

## In-scope requirements (PRD R9)

- `docs/STATUS.md`: a newest-entry block naming the unit, what shipped (the sheet aligned to
  § 10.16: ids, `--heldout`, run-id declarations, denominator, the leakage step, the watched-
  failing guards, the live dev-id test), what it does not claim (no candidate, no number, no
  real run from the new sheet; the zero-yield outcome and the night itself remain the
  operator's), and the deliberate limit (the suite pins the sheet's text, not a GPU night).
- `CHANGELOG.md` `Unreleased`: a short Added/Changed entry for 0.22.0.
- `docs/ROADMAP.md`: a dated correction appended to § 14's M2 block (the night sheet is
  aligned to § 10.16; M2's exit criterion stays open — no gate decision exists).
- No other document is edited, unless the guards' reconciliation exposes a stale sentence
  that names the night sheet's flags — then that sentence is corrected in the docs aspect and
  disclosed in the commit.

## Out-of-scope boundaries

- No edit to historical sheets or reports; no edit to `CLAUDE.md`'s status block (STATUS is
  the log; CLAUDE.md references it).
- No version bump, tag, or release (separate release commit, per precedent).

## Acceptance criteria

1. The STATUS entry states the unit's honest limit — no real night or probe ran from the new
   sheet, and no number is claimed — in its own words.
2. The ROADMAP correction names § 10.16 and keeps M2's exit criterion open.
3. The CHANGELOG entry ships under `Unreleased` and describes only what the tree now does.
4. Nothing under `src/` and no published report changes in this unit's diff.

## Dependencies and sequencing

Last aspect: consumes `guards` + `sheet`; lands in the same commit as the final sheet/guard
change, per the write-up rule.