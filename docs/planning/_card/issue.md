# Card — probe-decision-gate

**Type:** feat · **Branch:** `feat/probe-decision-gate/aliz` · **Owner:** aliz
**Source:** inline brief (no GitHub issue exists; produced by the `whetstone-next` handoff, 2026-09-05)

## Brief

Build the pre-committed probe decision gate as a command, so night #1's go/no-go is a
command exit and never a narrative judgement. The night-door runbook
(`docs/planning/p2-rollouts/night-door/runbook.md:78-80`) already fixes the rule — control
arm PASS on every draw and a non-empty seed map — and this unit encodes it, modeled on
`check_leakage`: read-only over a probe's run directory, the four-code contract, a named
violation (which draw's control failed / empty seed map), and a refusal for a non-probe or
unreadable ledger. Caveat: the runbook is guard-pinned, so rewrite its go/no-go paragraph
in the same unit, code first, and enforce exactly the two pre-committed conditions, nothing
more. Acceptance criteria, written first and watched failing: a fixture probe with a BROKEN
control exits 1 naming it; an empty seed map exits 1; a full night's ledger (probe null)
exits 2; a control-INTACT probe with non-empty seeds exits 0; the runbook guard is extended
to pin the new step; ruff/mypy/full pytest stay green with the reward path frozen.

## Notes from the handoff

- The launch-path operator chain (`docs/ROADMAP.md` § 12, corrected 2026-09-01) is the
  whole remaining plan: night #1 → first gated evaluation (candidate: night #1's
  checkpoint; incumbent: the untrained base) → baseline spend → P4 report → finding. Every
  step is operator-executed; this unit is the last buildable code that de-risks the most
  expensive, least certain, least reversible step (the night) and reads no number.
- The decision rule is pre-committed prose at `docs/planning/p2-rollouts/night-door/runbook.md:78-80`:
  *"the night proceeds iff the probe completes with the control arm `PASS` on every draw and
  a non-empty seed map."* It is currently enforced by an operator reading the ledger — a
  narrative judgement, against the roadmap's own exit-criteria principle
  (`docs/ROADMAP.md:278`: *"a command that exits 0 or an artifact that exists — never a
  narrative judgement"*).
- The shipped CLI already distinguishes unproven control (`UNVERIFIED_EXIT`) from a probe
  with no candidate (`FAIL_EXIT`) but not the aggregate go/no-go (`src/whetstone/cli.py:783-840`).
- The model to follow is `check_leakage` (`src/whetstone/loop/check_leakage.py`): read-only
  over documents, four-code contract, names the violation, no `UNVERIFIED` because it runs
  nothing. The runbook edit follows the `gate-untrained-incumbent` precedent — sheet
  rewritten in the same unit, code first (`CHANGELOG.md` v0.12.0).
- The unit must not add a bar to the pre-committed decision rule and must not weaken it.
  Two design questions for the dig/PRD: (1) a separate read-only command vs. a `--probe`
  exit-code change (the "exit answers is there a candidate" contract at `cli.py:796-801`
  constrains the latter); (2) CLI subcommand (a 6th partition-guard edge) vs. a module door
  like `check_leakage`'s siblings.