# Spec — write-up (aspect 2 of torch-baseline-door)

**PRD:** `../prd.md`. Docs only; it lands after the code is green, in the same PR.

## Problem slice

The repository's contract is that a capability is written up in the same commit that lands it
(`CLAUDE.md:81-85`). The new door changes what a measured baseline artifact carries and what
the operator can run, so the changelog, the status history and the main-series follow-up note
must say so — and must say, in the same breath, that **no number is measured** and that the
Torch baseline remains unspent until the § 10.25 probe settles the base.

## In-scope requirements

1. `CHANGELOG.md` under `[Unreleased]`: the door's `--runtime`, the backend provenance, the two
   refusals, the unchanged series key, and the explicit "no number is claimed" sentence.
2. `docs/STATUS.md`: an appended entry in the repository's register, naming the unit, the
   evidence/artifact fields, the declaration compatibility and the unspent measurement.
3. `CLAUDE.md` status block: one appended sentence in the same register, keeping the existing
   status paragraph intact.
4. `docs/planning/torch-mps-series/understanding.md` (and/or `prd.md`): a dated correction to
   the "§ 3 baseline is a follow-up" note — it is built in `torch-baseline-door`; the
   measurement is still unspent. Append, do not rewrite the history.
5. No `reports/` change, no figure, no runbook change to the MLX sheet.

## Acceptance criteria

- The changelog entry exists under `[Unreleased]` and contains no count.
- The `docs/STATUS.md` entry names the unit and the unspent measurement.
- The `CLAUDE.md` status block names the door and does not claim a run.
- The `torch-mps-series` note is a dated correction, not an edit of the original sentence.
- `tests/test_docs.py` and any status guard stay green.

## Out of scope

- The operator's Torch baseline sheet and the measurement itself.
- Any amendment to `PREREGISTRATION.md`.
