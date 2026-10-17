# feat raise-k — raise the declared `sampling.K`

**Source:** inline brief (no GitHub issue exists for this slug; `gh issue view raise-k`
returns `invalid issue format`, and the open-issue list is only #62 and #64, neither of
which is this work). Branch `feat/raise-k/aliz`, worktree `.claude/worktrees/feat-raise-k`.
Derived from the accepted `whetstone-next` handoff (2026-10-17).

## Brief

Raise the declared `sampling.K` (`src/whetstone/loop/sampling.py:79`) from `8` to a new
pre-registered value as a **Type 1 `PREREGISTRATION.md` § 10.x amendment** committed before
the night that tests it — the last untried pre-committed response to the fired P2 pivot,
per `docs/ROADMAP.md` § 13:775 and
`docs/planning/whole-function-edit-finding/measurement-run/finding.md` § 6. `K` must stay a
module constant and never become a flag (a `--k` must be refused), in the shape of the
`portability-cpu-dtype` unit's `DEVICE_PRECISION` change. The caveat: § 14:1017-1018
demotes this lever and the unit measures nothing (the night is operator-run), so the
amendment must state non-comparability of every prior series and claim no yield. Acceptance
criteria (written first, watched failing): (1) a test pins the new `K` value and refuses any
CLI flag that would set it; (2) the § 10.x amendment pins the new `K`, names the
non-comparability, and carries its amendment-log row; (3) the night-door runbook is updated
and its guard re-pinned; (4) `src/whetstone/verify/`, `tasks/`, the held-out document and
the gate rule are byte-unchanged and the reward-path suites stay green.

## Core-loop placement

Advances core-loop element **② the nightly improvement loop**. The reward path (①) is
untouched: K only sets how many seeded draws each task gets; the reward is still the STRICT
verifier's re-execution. The gate (③) is untouched: `UNVERIFIED` still counts as not a win.

## Roadmap grounding

- `docs/ROADMAP.md` § 4, P2 pivot signal: *"if strict-PASS yield is ~0 across the corpus
  there is no training data. Stratify by difficulty or raise k — do not weaken the check to
  manufacture wins."* Stratification was tested and exhausted (night #4, § 13); the CPU
  dtype response shipped (`PREREGISTRATION.md` § 10.18); **raise k is the remaining one.**
- `docs/ROADMAP.md` § 13:775: *"Raising k remains untried: `K = 8` is a declared constant
  and never a flag, so a change is a Type 1 amendment rather than an operator's choice."*
- `docs/ROADMAP.md` § 14:862-887 (M1) and § 14:1017-1018 (the demotion — see the caveat).
- `docs/planning/whole-function-edit-finding/measurement-run/finding.md` § 6: the two
  remaining untried pre-committed responses are raise k and the portability arm's CPU dtype.
- `docs/STATUS.md:1365-1367`: *"raising it is the roadmap's named response to a low yield,
  as a diff before a night."*
- Night #1's clustering evidence (`docs/STATUS.md:1713-1716`): one task solved 4 of its 8
  draws while 47 of 49 others solved none — the mechanism raise k multiplies.

## Related issues (context only)

- **#64** (open) — 83% of night-006's rollouts died on patch application; over half were
  well-formed diffs whose context did not match. Documents the wall M1 exists to clear; its
  own proposed representation directions are spent NO-GO, which is why raise k is the
  remaining response to the same signal.
- **#62** (open) — the held-out split is keyed on the task id; out of scope here.
- **#60 / § 10.16** (closed) — the held-out split re-derivation; out of scope here.
- Precedent units: `portability-cpu-dtype` (`PREREGISTRATION.md` § 10.18, a declared
  runtime input read as a pinned generation-contract input), `close-base-7.3`
  (`§ 10.10`, a Type 1 amendment committed before the night it governs).
