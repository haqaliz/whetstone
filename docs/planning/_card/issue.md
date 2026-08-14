# Card — stratum-probe-execution

## Brief

The easier-stratum probe — the fork gate after P1's fired pivot signal — has all its
machinery shipped (0.6.0) but has not run: `reports/easier-stratum/report.md` holds the
declaration-only state and `runs/` has no evidence directory. The runbook
(`docs/planning/p2-easier-stratum/probe-run/runbook.md`) is stale on master: every
`uv run --project` target names the deleted `feat-p2-easier-stratum` worktree, and the
guard never existence-checks a path, so the sheet is green while its commands fail.

First slice, test-first: add `feat-p2-easier-stratum` to `STALE_WORKTREES` in
`tests/test_probe_runbook_guards.py` and watch it go RED against the current sheet, then
refresh the runbook onto the unit's fresh worktree (per the whetstone-worktrees
convention), keeping the A2 resolution block and the retained/excluded candidate pins
intact.

Then the operator executes the arm (overnight, GPU), runs the post-run chain verbatim
(attribution → autopsy → the mandatory pre-analysis extension over all four autopsy
documents → comparison → the stratum-report door), and writes the finding that applies
the pre-committed fork rule (probe-run spec A6): yield > 0 → P2 loop next on the
stratum; yield == 0 with control intact → larger-base arm, with the M13
axis-falsification check stated in words on the autopsy/attribution read.

Acceptance: the guard suite green with the RED watched first, the runbook's commands
executable from disk (no dead worktree path anywhere), the post-run chain's refusals
all named and passing, and no figure about a model anywhere outside
`reports/easier-stratum/` and the gitignored breakdown home.

## Source

Inline brief (no GitHub issue — slug id, `feat stratum-probe-execution`).
