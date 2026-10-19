# Understanding — night-autopsy

**Unit:** `feat/night-autopsy/aliz` · **Written:** 2026-10-19 · **Source:** the inline brief in
`docs/planning/_card/issue.md`.

## What the work is really asking

A finished night's ledger records counts — per draw, per source, `(denominator, unverified,
solved)` — plus the control arm's status. It records **no cause** for any rollout. The K = 16
night is the next real execution (`docs/planning/k16-night/`), and its most likely outcome is a
zero strict-`PASS` yield, confounded by the held-out exclusion of the one clustered task. When
that happens, the operator must decide which lever to pull — a new representation, a base change,
a task-pool change, or accepting the finding. Today that decision would require hand-joining
stored transcripts to journals, which is exactly how night #1's 83% patch-application failure was
diagnosed, and the `NOT_APPLIED` reason field was added only after that cost was paid.

This unit builds the instrument that makes the decision a file read: a read-only, deterministic,
inference-free command that reads one complete night run and reports *why* each rollout became or
did not become a training example.

## What exists, and why it does not cover this

- **`bakeoff/attribution.py`** (`:434`) takes exactly **one** `--transcript` file and never reads
  a journal or a ledger. A night writes **K** transcripts, one per draw (`draws.py:53`, `:81-89`).
  It partitions only why a completion never became a patch (`Cause`, `:75-120`).
- **`bakeoff/autopsy.py`** (`:832-847`) **requires** an `--attribution` document declaring
  `whetstone-attribution/1` (`:711`); no night writes one. It joins fine patch shapes to that
  sidecar.
- The night's per-rollout facts live in the per-draw **journal**: the `Step.rollout` block carries
  `outcome`, `strict`, `weak`, `verdict_kinds`, `executed`, `prompt_sha256` and `detail`
  (`journal.py:142-166`), and `Journal.replay()` reconstructs the real `Rollout` objects. No
  existing command reads a night's journals for causes.
- The ledger is the completeness authority but is counts-only (`ledger.py:193-210`); it cannot
  enumerate rollouts, and `Ledger.seeds` omits `NO_ORACLE`/`UNPROVISIONED` rollouts because those
  never reach generation (`scoring.py:416-448`).
- `check_probe` reads the ledger and checks each journal **exists**, never its content
  (`check_probe.py:308-342`) — deliberately.

**Conclusion:** no night-autopsy capability exists in any form, and it would not duplicate
`attribution`/`autopsy`; it sits downstream of both and must reuse them by identity.

## The evidence, on the one real night

Night #1 (`runs/nights/night-001/`, primary checkout) has `draws/draw-01..08` with 62 tasks per
draw (61 private + 1 public), a `dataset.json` reporting 496 denominator / 102 unverified / 6
solved, and **no `ledger.json`** (training raised before the ledger was written; the defect is
fixed in `night.py:667-699`). Its eight journals partition the 496 rollouts as

| class | count |
|---|---|
| `NOT_APPLIED` | 303 |
| `NO_ORACLE` | 96 |
| `NOT_SOLVED` | 78 |
| `NO_DIFF` | 7 |
| `UNVERIFIED` | 6 |
| `SOLVED` | 6 |

The counts live only in the gitignored `runs/nights/night-001/draws/` (`docs/STATUS.md` already
publishes the 83% headline). The point is that the partition is *recoverable from the journals* —
and today requires reading them by hand.

## Design constraints the dig established

1. **The door is a `python -m whetstone.bakeoff.night_autopsy` module**, like `attribution` and
   `autopsy`. A `whetstone night-autopsy` subcommand would create a guarded→`bakeoff` import edge,
   and `tests/test_reward_path_scope_is_partitioned.py:409-443` asserts that there are **zero**
   such edges, because the dependency direction is `bakeoff -> verify`. The module sits inside the
   already-exempt `bakeoff` package, so no partition-guard change is needed.
2. **Output is gitignored.** A partition quotes stored completions (private code), the `autopsy.py`
   case; the precedent refuses any `--out` outside `runs/`, `reports/local/`, `checkpoints/`,
   `tasks/local/`, `_sandbox/` (`autopsy.py:716`, `:727-745`). It must **not** add a `reports/`
   home: `tests/bakeoff/test_report.py` holds exactly 21 committed artifacts across seven homes.
3. **Reuse by identity, never re-spell:** `ledger.read`/`LEDGER_FILE`, `draws.evidence_paths`/
   `night.EVIDENCE_DIR`, `Journal`/`Step`, `Transcript`/`Transcribed`, `scoring.Outcome`,
   `dataset.trainable`, `run_ledger.counts_of`, `sweep.rankable`, and the attribution/autopsy
   taxonomy (`Cause`, `NO_DIFF_MARKERS`, `attribute`, `classify_completion`, `FINE_TO_COARSE`).
   `run_ledger.counts_of` is the reconciliation definition: the module calls it on the journal
   `Rollout`s and requires the result to equal the ledger's own `DrawRecord.counts`.
4. **`source` (private/public) is not on disk per rollout.** Neither the transcript record nor the
   journal `Step` carries it (`transcript.py:273-288`, `journal.py:134-167`). The partition is
   therefore keyed by draw and task, and the ledger's per-source counts remain the source-level
   truth; the module discloses this limit rather than guessing from a task id.
5. **`NO_ORACLE` is recorded before generation** (`scoring.py:436-442`), so it has a journal row and
   no transcript row; its `detail` is the budget reason. The partition must not treat a missing
   transcript for such a rollout as incompleteness.

## Contradictions surfaced — flag, do not paper over

**1. The only real night cannot be analysed by the complete mode, and that is honest.** Night #1
has no ledger, and the design requires one as the completeness authority. A ledgerless run is
**refused by name**, not rendered as a partial partition — the repo's rule is that a missing
measurement rendered as a measurement is how a partial breakdown reads as a complete one. The
instrument's first real use is the K = 16 night, whose ledger is written even when training or
checkpoint writing fails (the `k16-night` durability guard). The night-001 partition above is
quoted from a manual read of its journals, not produced by this module.

**2. The instrument explains; it does not increase yield.** It is a diagnostic on the critical
path's *decision*, not on the yield itself. Building it does not move M1's exit criterion. The
honest framing: without it, a K = 16 zero costs another hand-join and delays the lever choice;
with it, the zero routes to a named cause. It claims no number about any model.

**3. The coarse cause is only complete with a task checkout.** `attribution`'s pure layer names the
four `NO_DIFF` reasons; distinguishing "would not parse" from "parsed but did not apply" needs the
checkout layer (`--tasks`). The module supports the flag and, without it, reports the pure-layer
classification and an explicit `UNATTRIBUTED` bucket — never a silent promotion of one cause into
another.

## Core-loop placement

Serves element **② the nightly improvement loop** by making its outcome legible; it changes neither
the reward (①) nor the gate (③), and it renders `UNVERIFIED` as itself. It publishes no figure, so
no `PREREGISTRATION.md` amendment is required (the `resolvability`/`addressability`/`locatability`
precedent).

## Open questions for the PRD / review gate

1. **The refusal set.** A run without a ledger, a declared draw without a journal or transcript, an
   unparsable evidence line, and a partition that disagrees with the ledger are each refused by
   name. Does a ledgerless run get a second, explicitly-`unreconciled` mode (to analyse night-001),
   or is refusal the whole answer?
2. **The document shape.** A JSON document (`whetstone-night-autopsy/1`) plus a markdown render
   beside it in the run dir? Which counts are the checked spine, and does the module seal the
   document (the `seal` module) or leave it unsealed like the other instruments' outputs?
3. **The `--out` contract.** Required and refused outside the gitignored roots (the `autopsy`
   shape), or defaulted to the run directory?
