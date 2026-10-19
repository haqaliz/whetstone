# Spec — autopsy-core

**Aspect:** `autopsy-core` · **Unit:** `night-autopsy` · **PRD:** `../prd.md` M1–M3, M5 ·
**Date:** 2026-10-19

## Purpose

Read one complete night run and emit its failure partition, reconciled against the ledger.

## Module and door

- `src/whetstone/bakeoff/night_autopsy.py`.
- `python -m whetstone.bakeoff.night_autopsy --run <runs/nights/<id>> [--tasks <root>]... [--out <path>]`.
- Exit codes: `0` a partition was produced; `2` a refusal. No `1`/`3`: this is a report, not a
  go/no-go.

## Inputs, read by identity

| Fact | Imported from |
|---|---|
| ledger document + reader | `whetstone.loop.ledger.LEDGER_FILE`, `ledger.read` |
| per-draw evidence paths | `whetstone.loop.draws.evidence_paths` |
| the evidence directory name | `whetstone.loop.night.EVIDENCE_DIR` |
| journal codec | `whetstone.bakeoff.journal.Journal` (`replay()` → `Step.rollout`) |
| transcript codec | `whetstone.bakeoff.transcript.Transcript` (`replay()` → `Transcribed`) |
| coarse outcome vocabulary | `whetstone.bakeoff.scoring.Outcome` |
| patch-cause taxonomy | `whetstone.bakeoff.attribution.Cause`, `NO_DIFF_MARKERS`, `attribute`, `extract_patch` |
| fine patch shape | `whetstone.bakeoff.autopsy.classify_completion` (pure) |
| solved predicate | `whetstone.loop.dataset.trainable` |
| reconciliation definition | `whetstone.loop.ledger.counts_of` |
| output locality | `whetstone.bakeoff.autopsy.refuse_published_out` / `IGNORED_OUT_ROOTS` |

`sweep.rankable` is deliberately **not** reused: `source` is not recorded per rollout, so a
per-source `Sweep` cannot be reconstructed, and gating on the harness would refuse the
broken-harness nights that most need reading.

## Behaviour

1. **Refuse before reading** if `--out` (resolved) is outside the gitignored roots.
2. **Read the ledger** (`ledger.read`). A missing or unreadable ledger is a refusal naming the run.
3. **For every `DrawRecord` attempt**, read `draw-NN.journal.jsonl` and `draw-NN.transcript.jsonl`.
   A missing or unparsable file is a refusal naming the draw and the file. An empty transcript is
   valid (a draw whose tasks all failed before generation).
4. **Build the rows**: for every `Step.rollout`, a row keyed `(attempt, task_id)` carrying
   `outcome` (the `Outcome` member by identity), `strict`, `weak`, `verdict_kinds`, `detail`, and
   `trainable = dataset.trainable(rollout)`.
5. **Cause the refusals**: for a row whose outcome is `NOT_APPLIED` or `NO_DIFF`, look up that
   draw's `Transcribed` for `(candidate, task_id)` and call `attribution.attribute(record,
   checkout)`; `checkout` is a throwaway materialisation of the task from `--tasks` when given,
   else `None` (pure layer only). Record the `Cause`, or `UNATTRIBUTED` when the taxonomy cannot
   name it. With no `--tasks`, a cause that needs the checkout layer is `UNATTRIBUTED` and the
   document discloses why. A row with **no transcript row at all** in an existing transcript is
   `UNATTRIBUTED` with a named detail — never a refusal, never folded into a neighbour — because
   the question could not be asked.
6. **Reconcile, never reconcile away**: per draw, `run_ledger.counts_of` over that draw's
   `Rollout`s must equal the sum of the ledger's `DrawRecord.counts`; globally, the same over all
   draws must equal the ledger's `dataset` `denominator`, `unverified` and `examples`. A
   disagreement is a refusal naming the draw and both triples. `source` is not per-rollout; the
   reconciliation is over totals and the document discloses the limit.
7. **Write the document**: `whetstone-night-autopsy/1`, unsealed, JSON, deterministic. Default
   path `<run>/night-autopsy.json`, or `--out`; the locality check runs on whichever resolves.

## Refusals (exit 2, each by name)

`NotARun` (no ledger), `IncompleteRun` (a declared draw missing its journal or transcript),
`UnreadableEvidence` (an unparsable journal/transcript line), `CountDisagreement` (the partition
does not equal the ledger), `PublishedOut` (an `--out` outside the gitignored roots). No partial
partition is written for any of them.

## Non-goals

- No night execution, no generation, no grading, no model, no network.
- No `whetstone` subcommand; no change to the reward path, `tasks/`, the held-out document, or
  the gate.
- No seal on the document.
