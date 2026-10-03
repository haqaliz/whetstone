# Understanding — gate-first-decision (2026-10-02)

Sources: `docs/planning/_card/issue.md` (the whetstone-next handoff, verbatim),
`docs/ROADMAP.md` § 14 (M2), `PREREGISTRATION.md` § 10.16, the gate runbook
(`docs/planning/p3-promotion-gate/gate-runbook/runbook.md`) and its guard
(`tests/test_gate_runbook_guards.py`), `src/whetstone/loop/check_leakage.py`,
`src/whetstone/loop/gate.py`, `src/whetstone/cli.py`, and a read-only look at the primary
checkout's gitignored `runs/` and `tasks/`.

## What the work is really asking

M2's exit criterion (`docs/ROADMAP.md:910`) is that `whetstone gate` returns `promoted` or
`rejected` on a real pair and `whetstone check-leakage` exits 0. The held-out set is now
scorable (§ 10.16), and no candidate has scored against it. The handoff proposed using the one
trained adapter (0.5B, 6 night-001 examples) against its untrained base.

## Findings that change the unit

1. **The existing adapter is contaminated against the re-derived held-out set.** Compared by
   the 12-hex sha12 that survives the re-mint, night-001's `legacy-a-c6e4d4c4de87` is
   `donor-a-c6e4d4c4de87`, a held-out member. That task supplies **4 of the 6** training
   examples (verified directly against `runs/nights/night-001/dataset.json` and
   `tasks/heldout/source-b.json`). The other two examples (`34daf85182d5`, `c3e132b7469b`)
   are not held out. Issue #42's four tasks are none of the 6 and none of the 12.
2. **`check-leakage` cannot see it.** It compares exact `task_id` strings
   (`check_leakage.py`, `check_overlap`). The re-mint renamed `legacy-a-*`/`legacy-b-*` to
   `donor-a-*`/`donor-b-*`, so on night-001's ids it would report **disjoint (exit 0)** — a
   false clean on exactly the case it exists for. Separately it refuses (exit 2, `NotARun`)
   because `runs/nights/night-001/` has no `ledger.json`.
3. **The gate record does not name what trained the candidate.** `runs/promotions/<id>.json`
   holds candidate/incumbent digests, held-out digest, per-side counts, decision, retries and
   tool versions (`gate.py:900-942`) but not the training-dataset digest, base repo_id or
   revision. Nothing ties a verdict to the night's `dataset.json`.
4. **The runbook is written for a different pair.** It materialises a 32B incumbent
   (`incumbent-base-001`), gates `checkpoints/night-002`, leaks against `runs/night-002`, and
   its roadmap cites have drifted (rule now ~`ROADMAP.md:431`). It never says which night
   trained the candidate, and "who writes the finding" is undefined (it authorises nothing in
   `reports/`).
5. **Exit codes differ from the brief.** `whetstone gate`: 0 promoted, 1 rejected, 3
   `UNVERIFIED`, 2 refusal. `check-leakage`: 0/1/2.

## Contradictions flagged, not papered over

- The brief's AC1 ("refuse a gate run if check-leakage would not exit 0") would, applied
  honestly, **refuse this adapter** — which is the right answer, and makes the unit's first
  deliverable a sound leakage guard rather than a verdict.
- Issue #42 states the held-out 12 are all donor-A; the committed document has three
  `donor-b-*` members. Not investigated further; does not affect the contamination finding.

## Guardrails

- Reward untouched: still deterministic re-execution. The gate's decision rule and the
  `unverified == 0` requirement are untouched; § 8.3 forbids narrowing them.
- `UNVERIFIED` and a refusal remain non-promoting. A contaminated `promoted` would be a
  fabricated win; this is why the leakage fix is on the critical path.
- Nothing leaves the box. Checkpoints and `runs/` are not copied into the worktree.

## Open questions for the requirements interview

See the interview; the scope decision (what to do about the contaminated adapter) is the
first.
