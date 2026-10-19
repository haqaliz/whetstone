# feat night-autopsy — turn a finished night into named causes

**Source:** inline brief, derived from the `whetstone-next` handoff and the M1→M2→M3 plan
(2026-10-19). No GitHub issue exists for this slug. Branch `feat/night-autopsy/aliz`, worktree
`.claude/worktrees/feat-night-autopsy`.

## Brief

Build a read-only, deterministic, inference-free command that reads a **finished night's** run
directory (`runs/nights/<id>/` — its `ledger.json`, `draws/draw-NN.journal.jsonl` and
`draw-NN.transcript.jsonl`) and reports, per draw and per task, why each rollout did or did not
become a training example. The night's ledger records counts — `(denominator, unverified,
solved)` per draw and the control arm's status — but never the *cause* of a non-solved rollout.
When the K=16 night returns zero selected examples, the operator needs to know which wall
accounted for the draws: a patch git refused (and why), a patch that applied but did not pass,
a task whose oracle exceeds the sealed budget, a harness/control failure, a timeout.

The project has learned this twice by hand. Night #1's 83% patch-application failure was
recovered by joining stored transcripts to journals by hand, and the repair itself
(`NOT_APPLIED` carrying git's own reason) was a later unit. `bakeoff/attribution.py` already
turns a **bakeoff run's** stored completions into the cause taxonomy, and `bakeoff/autopsy.py`
joins it to the fine shape of each completion. This unit is the night-layout equivalent: the
same taxonomy, the same evidence, pointed at the nightly loop's own directory shape, so a zero
costs a file read instead of another night or a hand-join.

Nothing is generated, nothing is graded, nothing is published. The reward path, the gate rule
and `tasks/` do not move.

## Acceptance criteria (written first)

1. A door (module and/or `whetstone` subcommand) reads one night run directory and emits a
   deterministic partition: per draw, and per task, the counts of solved / not-applied (with
   the cause) / applied-but-failed / oracle-refused / harness-refused / unverified, with every
   count read from the run's own transcript and journal.
2. The taxonomy is `bakeoff.attribution`'s, imported **by identity** — including its
   `patch.py` bijection guard — never re-spelled; a cause the taxonomy cannot name is
   `UNATTRIBUTED` and stays in the denominator.
3. A run missing its ledger, a transcript, or a journal is refused by name (exit 2), never
   silently partial: the ledger is the completeness authority, as `check-probe` treats it.
4. No inference import, no model, no network; a no-inference AST walk covers the new module and
   its door, in the shape of the existing bakeoff guards.
5. The night's ledger reader is `ledger.read` by identity; a v1/v2 ledger keeps its existing
   behaviour (v3 sealed; v2 unsealed; v1 refused). No schema bump.
6. `src/whetstone/verify/`, `tasks/`, the held-out document and the gate rule are byte-unchanged;
   the existing reward-path and adversarial suites stay green.

## Core-loop placement

Serves element **② the nightly improvement loop** by making its failures legible; it changes
neither the reward (①) nor the gate (③). `UNVERIFIED` is never rendered as a pass anywhere in the
output.

## Roadmap grounding

- `docs/ROADMAP.md` § 14 M1: the exit criterion is a night that selects ≥ 1 strict-`PASS`; the
  only identified lever on a zero is the edit representation, now spent in three measured forms
  (`docs/planning/whole-function-edit-finding/measurement-run/finding.md` § 6). A zero at
  K = 16 must route to the correct lever from evidence.
- `docs/STATUS.md`, night #1: 83% of rollouts died on patch application, recovered by hand; the
  `NOT_APPLIED` reason was added only later (`patch-representation`).
- `src/whetstone/bakeoff/attribution.py` and `autopsy.py`: the existing taxonomy and join, for
  bakeoff runs — the reusable half this unit points at the night layout.
- `docs/planning/k16-night/`: the run this instrument is built for; the finding template already
  requires the per-draw counts, and this adds the cause partition beside them.

## Related issues (context only)

- **#64** (open) — patch-application wall; its three proposed representation directions are
  measured NO-GO, which is why diagnosis of a K=16 zero matters more than a fourth contract.
- **#62** (open) — held-out split keyed on task id; out of scope.
