# PRD — probe-decision-gate

**Branch:** `feat/probe-decision-gate/aliz` · **Date:** 2026-09-05 · **Owner:** aliz
**Source:** `docs/planning/_card/issue.md` (inline brief from the `whetstone-next` handoff) +
`docs/planning/_card/understanding.md` (dig). **Slug confirmed:** `probe-decision-gate`.

## Problem statement

The night-door runbook pre-commits night #1's go/no-go in prose — *"the night proceeds iff
the probe completes with the control arm `PASS` on every draw and a non-empty seed map"*
(`docs/planning/p2-rollouts/night-door/runbook.md:78-80`) — and an operator enforces it
today by reading the probe's ledger by eye. The launch path's most expensive, least certain,
least reversible step (the night, ~40h and unmeasured, behind a probe whose control proved
nothing = a wasted `HarnessNotProven` night) is therefore gated by a **narrative judgement**,
against the roadmap's own exit-criteria principle: *"a command that exits 0 or an artifact
that exists — never a narrative judgement"* (`docs/ROADMAP.md:278`). The pre-commitment
exists; the command that holds it does not.

This is the last buildable unit that de-risks the operator chain and reads no number. It is
**not** the promotion gate (③): `decide()`, the three exits, and the retry discipline are
untouched.

## Goals & success metrics

- Night #1's go/no-go is a **process exit**, never an eyeball read: `whetstone check-probe
  --run <runs/id>` answers "does the probe satisfy the pre-committed rule?" deterministically.
- The decision rule is enforced **exactly as pre-committed** — two conditions, nothing more
  and nothing less. No bar is added, none is weakened.
- Success is measured by the exit-code contract and the adversarial fixtures, not a narrative:
  - a control-`INTACT` probe with a non-empty recorded seed map → exit 0 (proceed);
  - a probe whose ledger records a non-`PASS` draw harness, or an empty recorded seed map →
    exit 1, naming the violation;
  - a non-probe run, an unreadable ledger, or an incomplete run directory → exit 2, by name;
  - the go/no-go paragraph in the runbook is rewritten to point at the command, code first.

## User personas & scenarios

- **The operator (aliz), before night #1.** Runs the probe pass, then `whetstone check-probe
  --run <probe dir>` instead of reading the ledger by eye. Exit 0 → proceed to the night.
  Exit 1 → a named harness finding; no night runs behind it. Exit 2 → retype/fix the command.
- **A later reader of the launch path.** The pre-committed rule is now a command whose exit
  is checked into the runbook's sheet, so the go/no-go survives operator fatigue and can be
  audited.

## Requirements

### Must-have

1. **`whetstone check-probe --run <runs/id>`** — a read-only command over one run directory
   (`src/whetstone/loop/check_probe.py`, modeled on `check_leakage.py`). Reads documents,
   runs nothing, generates nothing.
2. **The exit-code contract** (`cli.py:82-93`, no fifth code, no `UNVERIFIED`):
   - `0` — the decision rule holds (proceed to the night);
   - `1` — a named violation: a draw whose harness fold is not `PASS`, or an empty recorded
     seed map;
   - `2` — a refusal an operator can fix by retyping: not a probe run, unreadable ledger,
     incomplete run directory.
   - Rationale for no `UNVERIFIED`, matching `check_leakage` (`cli.py:911-912`): *"this
     command reads documents rather than running anything, so it either answers or refuses."*
3. **"A probe run" is identified by the ledger, fail-closed**: `task_set.probe` is an int,
   `checkpoint.digest` is null, and `checkpoint.absent` states the probe. A full night's
   ledger (`probe` null) is refused by name (`NotAProbe`, exit 2) — a decision gate over a
   run that was never a probe would prove nothing about the night.
4. **Control condition**: every draw's harness fold is `PASS`. Read from
   `ledger.json`'s `draws_recorded[].harness` per draw per source — the fold, the rule's
   exact words (`bakeoff/control.py:472-494`). A non-`PASS` value is exit 1 naming the
   draw/source. The per-task `INTACT`/`BROKEN`/`SKIPPED` detail in the journals is **not**
   a separate bar (reading it as one would re-litigate what "control arm PASS" means); the
   journals are read only to prove each draw actually ran (completeness, a refusal concern,
   never a criterion).
5. **Seed-map condition**: the **recorded** `seeds` array in `ledger.json` is non-empty —
   recorded-only, never re-derived. An empty array is exit 1. **The rule's words are literal:
   `len(seeds) > 0`, nothing more.** The gate deliberately does not grow into a coverage
   assertion (every `(task_id, attempt)` seeded) — that would be a new bar the pre-committed
   rule never set. Decision (confirmed 2026-09-05): a killed **probe** is never resumed — the
   runbook now forbids it (a killed probe restarts fresh, a different run id; it is cheap,
   first-N private tasks). This closes the fully-replayed-resume edge (`draws.py:176-179`,
   `sampling.py:203-214`) by fiat rather than by loosening the check.
6. **Readability/completeness refusals** (exit 2), each by name: no `ledger.json` (`NotARun`);
   ledger unreadable / wrong schema (`LedgerUnreadable` via `ledger.read`, `ledger.py:211-224`);
   `draws_recorded` missing a declared draw or a source (`IncompleteRun`); a journal file
   missing/unreadable for a declared draw (`JournalUnreadable`). A schema-valid-but-empty
   state is a different fact from an absent one — refuse, never default (the `check_leakage`
   discipline, `check_leakage.py:250-268`).
7. **The runbook is rewritten in the same unit, code first** (the
   `gate-untrained-incumbent` precedent, `CHANGELOG.md` v0.12.0): the decision-rule paragraph
   at `runbook.md:78-80` becomes the `check-probe` step (a third bash block in the sheet), the
   "Read `runs/night-probe/probe-001/ledger.json`" sentence is replaced by the command, and a
   sentence forbidding probe resume is added. **The third block is a different command
   (`whetstone check-probe --run …`), not a second `run --night` invocation** — so the guard's
   `_door_blocks` count (`test_night_runbook_guards.py:175`, keyed on `DOOR = "whetstone run
   --night"`, `:50`) stays exactly two, and the extension is a **new** test pinning the
   `check-probe` block: its command, its `--run` flag against the shipped `check-probe` parser
   surface, the absolute `--run` value naming the probe's own run directory, its position
   before the night block, and the two-condition decision sentence and the no-probe-resume
   sentence. `tests/test_night_runbook_guards.py` gains this as the unit's own pin (the
   module docstring's "Six properties" → seven), written and watched failing first.
8. **Adversarial tests, not just happy-path ones** (the verifier discipline applied to a
   decision gate): a doctored probe ledger with a `BROKEN`/non-`PASS` draw harness → exit 1
   naming it; a doctored probe ledger with an empty `seeds` array → exit 1; a full night's
   ledger (`probe` null) → exit 2; a directory with no ledger → exit 2; an incomplete
   `draws_recorded` → exit 2; the control-`INTACT` + non-empty-seeds fixture → exit 0. Each
   failure names the *specific* condition, so a refusal for an unrelated reason cannot read
   as the decision.
9. **No inference import on the new path** — a per-file no-inference AST walk for
   `check_probe.py` and its tests, in the `check_leakage` shape (`test_check_leakage.py:356-380`).
10. **CLI wiring**: the `check-probe` subcommand follows `check-leakage` exactly — parser
    registration with the exit codes stated in the description, a handler with a
    **function-local** import of the loop module (`cli.py:895-924`), and the module docstring's
    command list + the stale edge-count docstrings updated. This is the **fifth** documented
    partition-guard edge: `_DOCUMENTED_EDGES`
    (`tests/test_reward_path_scope_is_partitioned.py:154-159`) and the `EXEMPT["loop"]` reason
    (`:120-147`) grow together, in a diff, never silently.

### Should-have

- `disclosure` output states the two conditions and the counts it read them from, so an exit
  code is never an unexplained number (the `check_leakage` disclosure shape,
  `check_leakage.py:198-226`).

### Nice-to-have

- None identified.

## Technical considerations

- **Composition by identity, never re-decision** (the house rule): `ledger.read` for the
  schema gate (`ledger.py:211-224`), the two source names from `whetstone.loop.night`
  (`SOURCES`, `night.py`), `Status`/`"PASS"` from the verdict vocabulary — imported by
  identity, asserted `is` in a test.
- **The decision is a pure function of one run directory.** `run_check(run: Path) ->
  ProbeReport`, with `ProbeReport` carrying `proceed: bool`, the named violation (draw /
  source / seed-map) when one exists, and the counts it was read from. No clock, no network,
  no GPU.
- **The fold is always `PASS` on a genuinely-written ledger** (`sweep.rankable` aborts with
  `HarnessNotProven` before the ledger is written, `sweep.py:160-183`; the night exits 3 with
  no ledger, `cli.py:828-830`). The exit-1 control case is therefore a *document* assertion —
  it catches a doctored ledger or a future regression in the night's own rankable gate, the
  same "regression in the partition seam" argument `check_leakage` makes
  (`check_leakage.py:221-225`). State this in the module docstring; do not claim the gate
  measures something the night already guarantees.
- **Reward path frozen**: `src/whetstone/verify/`, `patch.py`, `attribution.py` are untouched
  (asserted byte-identical where the plan already pins them).

## Risks & open questions

- **The exit-1 control case is unreachable from a genuinely-written ledger** (see below). The
  value of the check is the formal go/no-go + the document assertion, not a new measurement —
  this is stated, never papered over. The hard question, answered: *what does the gate protect
  that the night does not already enforce?* (a) It converts a prose pre-commitment into an
  auditable process exit — the entire point of the unit; (b) it proves the evidence document
  is coherent before ~40h commits to a night behind it; (c) it catches a doctored ledger or a
  future regression in the night's own `rankable` gate (`sweep.py:160-183`). It never claims
  to *measure* control — the night already does that, at exit 3 with no ledger
  (`cli.py:828-830`).
- **Exit 0 is yield-independent and must stay that way.** A zero-strict-PASS probe with the
  control proven and a non-empty seed map is **exit 0** — the rule has exactly two conditions,
  and a zero yield is a separate, published outcome (the night's own halt condition 4,
  `runbook.md:161-164`). The gate is a harness door, never a yield bar; any future drift
  toward "no wins → don't proceed" is a new rule and must fail review.
- **Resume semantics now differ for probes vs nights.** The runbook's killed-*night* restart
  (same command, same `--run-id`, resumed draws) is untouched; only a killed *probe* restarts
  fresh. The runbook must state the distinction in words so the two sheets cannot be confused.
- **A hand-edited ledger is a genuine adversary.** The gate reads the ledger as written; a
  doctored-but-schema-valid ledger that swaps `probe` to null (turning a probe into a "night"
  → exit 2) or empties `seeds` (→ exit 1) is refused by the gate's own conditions. Like
  `check_leakage`'s held-out digest, the defense is the gate + git history, never a claim of
  read-blindness.
- **No guard pin currently holds the decision-rule paragraph** (verified: `test_night_runbook_guards.py`
  references none of its strings), so the rewrite breaks nothing — but the extension to three
  door blocks, with the third a different command, is mandatory in the same commit.

## Out of scope

- **Not the promotion gate (③).** `decide()`, the three exits, the retry discipline, and the
  promotion record are untouched.
- **Not an automated night gate.** The night does not refuse to start without a passing
  `check-probe`; the sheet orders the steps and the operator runs them. A check the command
  could silently turn green by omission is no check.
- **Not a module door** (`python -m whetstone.loop.check_probe`) — decided 2026-09-05: the CLI
  subcommand, for the operator-chain surface consistency with `check-leakage`.
- **No re-derivation of the seed map** — decided 2026-09-05: recorded-only, and the runbook
  forbids probe resume so the recorded map is always non-empty on a valid probe.
- **No per-task journal `INTACT` enforcement** — the fold is the pre-committed rule's words.
- **No yield bar.** A zero-strict-PASS probe with the harness proven and seeds recorded is
  exit 0; the gate is a harness door, and a zero yield is the night's own published outcome.
- **No change to what a probe is**: `--probe N` still narrows to the first N private tasks and
  writes no checkpoint (`night.py:248-249, 495-500`).
- **No publishing**: `runs/` is gitignored; `reports/` gains nothing; no `PREREGISTRATION.md`
  § 10 amendment (this publishes no series).

## Aspects (decomposition)

1. **`check-core`** — `src/whetstone/loop/check_probe.py`: `run_check`, `ProbeReport`,
   `disclosure`, `REFUSALS`, and the adversarial + fixture test suite.
2. **`cli-door`** — the `check-probe` subcommand: parser, function-local handler, the fifth
   partition-guard edge (`_DOCUMENTED_EDGES` + `EXEMPT["loop"]` reason), the module-docstring
   command list, and the stale edge-count docstrings; CLI tests.
3. **`runbook`** — the night-door sheet: the decision-rule paragraph becomes the `check-probe`
   step, the no-probe-resume sentence, and `test_night_runbook_guards.py` extended two→three
   door blocks.

Sequencing: `check-core` → `cli-door` → `runbook` (the sheet may not be edited ahead of the
command it would then disagree with).