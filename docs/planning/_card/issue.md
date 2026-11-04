# feat repair-evidence

**Source:** the `whetstone-next` handoff after the § 10.25 probe result (`docs/planning/torch-mps-series/finding.md`, 2026-11-02).

## Brief

The § 10.25 probe returned NO-GO with **one** near-miss. The one near-miss spent the two-attempt
repair budget, and the final verdict stayed `NOT_SOLVED` — but the repair completions are **not in
the transcript**: `Retry.generate_repair` bypasses `_record`, so a repair run records the budget
and the final verdict, not what the repair generated. That makes any repair measurement
un-auditable.

Record every repair prompt and completion in the transcript with a decision distinct from the
first attempt and its retries, keep every existing transcript readable, and prove that a
near-miss under `--repair 2` leaves the first graded row plus one row per repair, with the final
verdict carried by the journal's graded rollout. The reward, gate, corpus, held-out document,
`K`, `R` and the § 10.25 inputs do not move.

## Acceptance

- `Retry.generate_repair` records the repair prompt and completion, with a stable marker that
  distinguishes a repair from a retry of the first prompt.
- A near-miss under `--repair 2` produces the first attempt's rows plus **two** repair rows; a
  run with `--repair 0` is byte-identical to today.
- Existing transcripts (`probe-003`, the repair night, the § 10.25 probe) still read through the
  verifying reader; the schema addition is backward-compatible or the reader tolerates the old
  shape by name.
- The transcript's retry invariant is not weakened: every retry has a following graded row, and
  a repair row is never mistaken for a retry or for the graded row.
- A repair prompt outside the frozen contract raises `ContractChanged` and writes no row, exactly
  as a retried prompt outside it does.
- Full suite, ruff and mypy green; no GPU run.

## Caveat

The transcript's `attempt`/`decision` fields and the reader's `records` invariant were built for
the completion-retry loop, not for repairs. The dig must decide whether a repair is a new
`decision`, a separate row stage, or a distinct attempt namespace — and whether the offline
`attribution`/`autopsy` readers should consume repair rows or ignore them. Do not weaken the
retry invariant to make the repair fit.
