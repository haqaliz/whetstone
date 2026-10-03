# Spec — runbook-and-finding

**Core loop element:** ③ (operator chain). **Slice:** the sheet and the committed finding.

## In scope
- Runbook: names the candidate's night, runs `check-leakage` before `whetstone gate`, halts on
  non-zero, corrects drifted ROADMAP citations; says who writes up a gate finding.
- `docs/planning/gate-leakage-guard/finding.md`: night-001 vs `tasks/heldout/source-b.json`,
  `check-leakage` output verbatim, "no gate was run".
- STATUS.md, CHANGELOG.md, ROADMAP § 14 M2 updated in the same commit.

## Out of scope
- Running the gate; any figure not produced by `check-leakage`.

## Acceptance criteria (tests first)
1. Guard: the sheet has a `check-leakage` block ahead of the gate block, and says to halt on non-zero.
2. Guard: no stale `ROADMAP.md:<line>` citation points at a line that does not contain the cited rule.
3. Guard: the sheet names how the candidate's night is identified.
4. The finding's exit code and overlap line equal a fresh `check-leakage` run (checked when the
   primary checkout's artefacts are present; skipped loudly otherwise).
5. The finding contains no `promoted`/`rejected` verdict and no percentage.
6. Existing `tests/test_gate_runbook_guards.py` and docs tests stay green.
