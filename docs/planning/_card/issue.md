# feat gate-first-decision — run the gate on a real checkpoint pair and commit the decision

**Core loop element:** ③ the never-regress promotion gate (the operator's chain). The reward
(①) does not change.
**Roadmap:** M2 of `docs/ROADMAP.md` § 14 — "Make the gate able to answer" (issues #60, #62);
follow-on of `docs/planning/heldout-scorable/`.
**Source:** inline brief — the `whetstone-next` handoff (2026-10-02). No GitHub issue exists
for this unit.

## Brief

The handoff brief from `whetstone-next` (2026-10-02), verbatim:

> M2's exit criterion (docs/ROADMAP.md § 14) is that `whetstone gate` returns promoted/rejected
> on a real checkpoint pair. The heldout-scorable unit made the held-out set scorable
> (docs/planning/heldout-scorable/gate-runbook/runbook.md); no candidate has scored against it
> yet. Use the existing 0.5B adapter (checkpoints/portability-arm on x131) vs its untrained
> base, via the gate's untrained-incumbent dispatch. Caveat to dig first: the adapter was
> trained on night-001's 6 strict-PASS examples from the pre-re-mint corpus. Determine whether
> any of them now fall in the re-derived held-out split by running `whetstone check-leakage`,
> and whether issue #42's non-reproducing tasks touch the split. Acceptance criteria, written as
> tests/guards first: (1) the runbook guard refuses a gate run if check-leakage would not exit 0
> or the adapter's training digest is not recorded in the evaluation; (2) the committed finding
> states the verdict and exit code verbatim from `whetstone gate`, with counts from the ledger
> only; (3) UNVERIFIED, rejected and refusal outcomes each have a documented, non-promoting
> record path, with no verifier loosening; (4) STATUS.md, the CHANGELOG and ROADMAP § 14 M2 are
> updated in the same commit as the finding, and no number appears that the verifier didn't
> produce. The GPU/CPU run itself is operator-executed; plan the sheet, not the result.

## Known caveats carried in from the handoff (unverified until Phase 2)

- The only trained adapter was built from night-001's 6 strict-PASS examples on the
  pre-re-mint corpus; the re-mint changed task identifiers and re-rolled the split, so some
  of those 6 may now be held-out. Unchecked.
- Issue #42 (four source-B tasks do not reproduce on Linux) may make some of the 6 examples
  non-re-derivable on x131.
- `rejected`, `UNVERIFIED` and a refusal are all valid outcomes; the gate is not to be tuned
  toward `promoted`.
- `docs/planning/_card/understanding.md` in the primary checkout carries uncommitted edits
  from the previous unit; they were deliberately not carried into this worktree.
