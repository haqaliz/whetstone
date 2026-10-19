# Spec — render-and-writeup

**Aspect:** `render-and-writeup` · **Unit:** `night-autopsy` · **PRD:** `../prd.md` M4, M6, S1,
S2 · **Date:** 2026-10-19

## Purpose

Turn the partition document into a page the operator reads at the morning, and write the unit up
in the same commit.

## The render

`render_markdown(document) -> str` is a **pure function of the partition document** — no file
reads, no clock, no environment. The door writes it beside the JSON: `<run>/night-autopsy.md` by
default, or the `--out` path with its suffix replaced. Byte-identical across invocations and
`PYTHONHASHSEED` 0/1.

The page carries, in order:

1. the run id, the declared draw budget (`draws`), the task count, and whether the run was a
   probe;
2. a per-draw table: one row per draw with the class counts (`solved`, `not_applied`, `not_solved`,
   `no_diff`, `no_oracle`, `unverified`, `unprovisioned`, `out_of_scope`) and the control arm's
   status;
3. a per-task table, worst-first by non-solved count: task id, draws, solved, and the dominant
   cause;
4. the disclosures, verbatim from the document: `source` is not per-rollout, and the
   `UNATTRIBUTED` count is what the taxonomy could not name (with the reason when `--tasks` was
   absent).

Every unflattering state renders as itself; nothing is smoothed, and no proportion is computed
that the document does not carry.

## The write-up

`docs/STATUS.md` gains a top entry and `CHANGELOG.md` an `Unreleased` entry in the same commit as
the code. They state what the instrument reads, that it refuses a run missing its ledger or a
declared draw's evidence, and that **it claims no number about any model**. The entry records the
night-001 limit: the only stored night has no ledger and is refused, so the first real partition
is the K = 16 night; the manual night-001 partition stays in the understanding note, not in the
STATUS entry.

`README.md`'s status table is checked; it likely needs no change (the instrument is a
`python -m` tool, not a `whetstone` subcommand). If its prose would deny the capability, update it
and the guard follows.

## Non-goals

- No committed report, no `reports/` home; both files are gitignored with the run.
- No new figure, no `PREREGISTRATION.md` amendment.
- No change to the partition document's schema or the core's reconciliation.
