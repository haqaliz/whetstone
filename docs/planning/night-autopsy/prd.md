# PRD — night-autopsy

**Unit:** `feat/night-autopsy/aliz` · **Written:** 2026-10-19 · **Type:** feature, off the reward
path. **Source:** the inline brief in `docs/planning/_card/issue.md`. **Understanding:**
`docs/planning/night-autopsy/understanding.md`.

## Problem Statement

A finished night's ledger (`whetstone-run/3`) records, per draw and per source, only
`(denominator, unverified, solved)` and the control arm's status (`ledger.py:193-210`). It records
**no cause** for any rollout. The per-rollout facts — `outcome`, `strict`, `weak`,
`verdict_kinds`, `detail`, `prompt_sha256` — live only in the per-draw journals
(`journal.py:142-166`), and `Journal.replay()` reconstructs the real `Rollout` objects.

The K = 16 night is the next real execution (`docs/planning/k16-night/`). Its most likely outcome
is a zero strict-`PASS` yield, and the one task that ever solved repeatedly is a held-out member,
so the zero is confounded. To choose the next lever — a new representation, a base change, a
task-pool change, or accepting the finding — the operator needs the night's failure partition.
Today that means hand-joining stored transcripts to journals: exactly what night #1's 83%
patch-application failure required, and the `NOT_APPLIED` reason field was added only after the
cost was paid (`docs/STATUS.md`, `patch-representation`).

No existing command covers this. `bakeoff.attribution` reads **one** transcript file
(`attribution.py:434`) and never reads a night's journals or ledger; a night writes **K**
transcripts (`draws.py:53`, `:81-89`). `bakeoff.autopsy` **requires** an `whetstone-attribution/1`
sidecar (`autopsy.py:711`, `:843`) that no night writes. `check_probe` reads the ledger and checks
each journal **exists**, never its content (`check_probe.py:308-342`).

## What this unit is — and is not

A read-only, deterministic, inference-free **instrument**: it reads one **complete** night run and
emits its failure partition. It does not run a night, generate anything, or grade anything. It
changes no reward, gate, corpus or held-out document, and it publishes no number about a model,
so no `PREREGISTRATION.md` amendment is required.

**It does not increase yield.** It is the instrument that makes a zero route to a named cause
instead of a hand-join. The K = 16 night remains the operator's run; this unit claims nothing
about its outcome.

## Goals & Success Metrics

A merged, green tree in which:

- **A night's partition is a command.** `python -m whetstone.bakeoff.night_autopsy --run
  runs/nights/<id>` emits a deterministic per-draw, per-task partition whose every count comes
  from the run's own evidence.
- **The partition reconciles with the ledger, by identity.** The module reconstructs the journal
  `Rollout`s and calls `run_ledger.counts_of` — the ledger's own definition — requiring equality
  with every `DrawRecord`; a disagreement is a named refusal, never reconciled.
- **The taxonomy is reused, not re-spelled.** `scoring.Outcome` for the coarse classes;
  `attribution.Cause` for why a patch never applied; `autopsy`'s fine classes for malformed patch
  shapes — all by identity.
- **Nothing leaks and nothing is published.** Output is refused outside the gitignored roots; no
  `reports/` home is added; no model, no network.

## Requirements

### Must-have

**M1 — the reader and the door.**
`src/whetstone/bakeoff/night_autopsy.py`, with
`python -m whetstone.bakeoff.night_autopsy`:
`--run <runs/nights/<id>>` (required), `--tasks <corpus-root>` (repeatable, optional; the
`attribution` checkout layer), `--out <path>` (optional; defaults to the run directory). It reads
the ledger through `ledger.read` by identity (sealed v3), then each declared draw's
`draw-NN.journal.jsonl` through `Journal.replay()` and `draw-NN.transcript.jsonl` through
`Transcript.replay()`, using `draws.evidence_paths` and `night.EVIDENCE_DIR` by identity.

**M2 — the partition and the reconciliation.**
Per draw and per task: the `Rollout.outcome` (the `scoring.Outcome` vocabulary by identity); for
`NOT_APPLIED` and `NO_DIFF`, the `attribution.Cause` computed from that rollout's stored
completion (pure layer always; the checkout layer with `--tasks`), with an explicit `UNATTRIBUTED`
bucket; for malformed patch shapes, the `autopsy` fine class by identity; for `SOLVED`, the
`dataset.trainable` predicate by identity. The module then computes `run_ledger.counts_of` over
the reconstructed rollouts per draw and **requires** it to equal the ledger's
`DrawRecord.counts` (summed across sources); a disagreement is a refusal naming the draw and both
triples. The `dataset.json`'s selected examples are read when present and reconciled with the
`trainable` count.

**M3 — refusals, by name, exit 2.** A run directory without a ledger; a ledger-declared draw whose
journal or transcript is missing or unparsable; a partition that disagrees with the ledger; an
`--out` outside `runs/`, `reports/local/`, `checkpoints/`, `tasks/local/`, `_sandbox/` (the
`autopsy.refuse_published_out` shape, checked before anything is read). No partial partition is
ever rendered. `NO_ORACLE`/`UNPROVISIONED` rollouts have a journal row and no transcript row and
are **counted**, never treated as incompleteness.

A declared draw's **transcript file** is a completeness requirement (a missing file is a
refusal). A rollout inside an existing transcript that has **no row** for its `(candidate,
task_id)` — a `NOT_APPLIED`/`NO_DIFF` row whose completion cannot be found — is `UNATTRIBUTED`
with a named detail, never a refusal and never folded into an adjacent cause: the question could
not be asked, and the honest bucket says so.

`--out` defaults to `<run>/night-autopsy.json` and is locality-checked either way; a run whose
own directory is outside the gitignored roots is refused.

**M4 — the document and the render.**
A JSON document (schema `whetstone-night-autopsy/1`) carrying the run id, the draw count, the
per-draw and per-task partition, the `unattributed` count, the reconciliation result, and the
disclosures (source is not per-rollout; the pure-layer `UNATTRIBUTED` when `--tasks` is absent).
A markdown render beside it, a pure function of the partition. Both are deterministic and
byte-identical across invocations and `PYTHONHASHSEED` 0/1. The document is **unsealed** — it is
analysis, not a claim document; sealing is for checkpoints, ledgers and datasets.

**M5 — guards.**
A per-module no-inference AST walk over the module and its test, in the `attribution`/`autopsy`
shape, with an anti-vacuity control. Identity assertions for every reused fact (`Cause`,
`NO_DIFF_MARKERS`, `attribute`, `classify_completion`, `ledger.read`, `LEDGER_FILE`,
`evidence_paths`, `EVIDENCE_DIR`, `scoring.Outcome`, `dataset.trainable`, `counts_of`).
`sweep.rankable` is **not** among them: `source` is not recorded per rollout, so a per-source
`Sweep` cannot be reconstructed, and gating the partition on the harness would refuse the
broken-harness nights that most need reading. `src/whetstone/verify/`, `tasks/`, the held-out
document and the gate rule stay byte-unchanged; the reward-path and adversarial suites stay
green. No `whetstone` subcommand, so `tests/test_reward_path_scope_is_partitioned.py` is
untouched.

**M6 — the write-up.** A `docs/STATUS.md` entry and a `CHANGELOG.md` `Unreleased` entry in the same
commit as the code, stating what the instrument does and that it claims no number. Update
`README.md` only if its status table would otherwise deny a built capability (it likely needs no
change).

### Should-have

**S1 — a demonstration on fixtures.** A complete synthetic night (a real `Ledger` written through
`run_ledger.write`, K journals written through `Journal`, K transcripts through `Transcript`, plus
a `dataset.json`) proves the partition and the reconciliation; the fixture is the guard's carrier
because night-001 cannot be used (below).

**S2 — the night-001 limit, documented.** The only stored night has **no ledger**; the module
refuses it by name. The understanding note records the manual partition (303 `NOT_APPLIED`, 96
`NO_ORACLE`, 78 `NOT_SOLVED`, 7 `NO_DIFF`, 6 `UNVERIFIED`, 6 `SOLVED`) and the STATUS entry says
the first real use is the K = 16 night.

### Nice-to-have

**N1 — a `--summary-only` flag** that prints the per-draw partition to stdout for a quick read,
while still writing the documents. Optional.

## Acceptance Criteria (testable, written first)

1. A fixture complete night yields the expected partition, and every class count equals the
   hand-written expectation; the reconciliation passes.
2. A journal whose rollouts do not match the ledger's `DrawRecord.counts` is refused, exit 2,
   naming the draw and both triples.
3. A run without a ledger, a declared draw with no journal, a declared draw with no transcript, and
   an unparsable evidence line are each refused, exit 2, naming the artefact.
4. `NO_ORACLE` rollouts (journal row, no transcript row) are counted in the partition and do not
   trigger a completeness refusal.
5. `--out` outside the gitignored roots is refused before anything is read.
6. The JSON and markdown outputs are byte-identical across two invocations and under
   `PYTHONHASHSEED` 0/1.
7. Identity assertions and the no-inference AST walk pass; `Makefile`/CI commands untouched.
8. `uv run pytest -q`, `uv run ruff check .`, `uv run mypy src/` exit 0; `src/whetstone/verify/`,
   `tasks/`, `tasks/heldout/source-b.json` and the gate rule are byte-unchanged.

## Out of scope / guardrails

- **No yield, no model, no GPU.** The instrument reads stored files.
- **No new `reports/` home.** The one-home guard's 21 committed artifacts do not move.
- **No `whetstone` subcommand.** The door is `python -m whetstone.bakeoff.night_autopsy`, so the
  guarded→`bakeoff` edge count stays zero.
- **No taxonomy re-spelling.** A cause the taxonomy cannot name is `UNATTRIBUTED`.
- **No partial renders.** A run missing its ledger or a declared draw's evidence is refused.
- **No reward or gate change.** `UNVERIFIED` is rendered as itself.

## Risks and flagged gaps

🔴 **The only stored night cannot be analysed, and the first real use is a future run.**
Night-001 has no ledger (the old training defect) and is refused. The fixture is the proof; the
K = 16 night is the first real partition. Stated, not hidden.

🟡 **`source` is not on disk per rollout.** The partition is keyed by draw and task; the ledger's
per-source counts remain the source truth. Disclosed in the document.

🟡 **The coarse cause is incomplete without `--tasks`.** Without a corpus root, "parsed but did not
apply" is indistinguishable from "would not parse" in the checkout layer; the module reports the
pure layer and an explicit `UNATTRIBUTED`, never a guess.

🟡 **A v1 or v2 ledger.** `ledger.read` refuses v1 and reads v2 unsealed; the instrument inherits
that exactly, with no schema bump.

🟡 **The reconciliation could refuse a real run whose ledger was written from a different draw set.**
That is the intended behaviour: the ledger is the completeness authority.

## Aspects

1. `autopsy-core/` — M1, M2, M3, M5: the reader, partition, reconciliation, door, JSON document,
   refusals and guards.
2. `render-and-writeup/` — M4, M6, S1, S2: the markdown render, determinism tests, the fixture
   demonstration, the STATUS/CHANGELOG write-up.

## Open questions (for the review gate)

1. **A ledgerless "unreconciled" mode?** The PRD recommends refusal only: the repo renders no
   partial partition, and the K = 16 night (the target) writes a ledger even when training fails.
2. **Seal the document?** The PRD recommends unsealed, like the other analysis instruments; seals
   are for claim documents.
3. **`--out` default.** The PRD recommends defaulting to `<run>/night-autopsy.json` and
   `night-autopsy.md`, with an explicit `--out` still refused outside the gitignored roots.
