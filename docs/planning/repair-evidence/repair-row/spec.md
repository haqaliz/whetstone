# Spec — repair-row (repair-evidence)

**PRD:** `../prd.md`. **Branch:** `feat/repair-evidence/aliz`. **Date:** 2026-11-03.

## Problem slice

`Retry.generate_repair` generates a repair completion and records nothing; `Recording` has no
repair path and records the fallback as a duplicate `"graded"` row. A repair measurement cannot
show what the repair generated, and a repaired solve would leave the keyed transcript record on
the failed first completion. The unit records every repair draw and makes the last row the keyed
record, without touching the reward.

## In-scope

1. **Vocabulary.** Add `"repair"` to `diffcheck.Decision` and to a runtime `DECISIONS` set in
   `transcript.py`. A test asserts the two agree.
2. **Writer, retry composition.** `Retry.generate_repair` delegates to `Sealed`, then calls
   `self._record(prompt, completion, attempt=1, decision="repair")` before returning. `_record`
   already resolves the frozen task and no-ops for an unfrozen prompt.
3. **Writer, non-retry composition.** `Recording.generate_repair` resolves the task from
   `contract.posed`, calls the inner generator, and appends a `Transcribed` with
   `decision="repair"`, `attempt=1`; an unfrozen prompt delegates unrecorded.
4. **Reader.** `Transcribed.__post_init__` refuses a decision outside `DECISIONS` by name;
   `Transcript.replay()` keeps last-wins and continues to refuse a trailing `"retry"`. A trailing
   `"repair"` is the keyed record.
5. **Docstrings.** `Transcribed.decision`, `Transcript`, `RecordingGenerator`'s "one row per key"
   claim, and `Retry.generate_repair` state the repair-row meaning and the last-wins consequence.
6. **Tests.** A near-miss with `repair=2` leaves one graded row plus two repair rows; the keyed
   record is the last repair completion; a repair that solves is what `replay()` returns; a repair
   prompt outside the frozen contract raises `ContractChanged` and writes no row; the `Recording`
   path records one repair row; an old `retry`/`graded` transcript replays unchanged; an unknown
   decision is refused; the read-side `attribution`/`night_autopsy` test uses the repair completion
   as the final one.
7. **Write-up.** `CHANGELOG.md` Unreleased, `docs/STATUS.md`, `CLAUDE.md`, and a dated note in the
   § 10.25 finding that the evidence gap is closed. No `PREREGISTRATION.md`, `ROADMAP.md`, or
   `pyproject.toml` change.

## Out-of-scope

The near-miss-rich probe, the test-output seal redesign, base/approach changes, the MPS hang; the
reward, gate, corpus, held-out document, `K`, `R`, the § 10.25 inputs; a transcript schema version
or a new required field.

## Acceptance (test-first)

- `Retry`/`Recording` with `repair=2` write two `"repair"` rows after the first `"graded"` row; the
  last row's completion is the one `score` re-verified.
- `replay()` returns the repair completion for a repaired key; a trailing `"retry"` is still
  `TranscriptUnreadable`; an unknown decision is `TranscriptUnreadable`.
- Old transcripts (the § 10.25 probe, the repair night, the probe-003 ledger's transcripts) replay
  unchanged; a `--repair 0` run is byte-identical.
- A repair prompt outside the frozen contract raises `ContractChanged` and writes no row.
- `uv run pytest tests/bakeoff/ tests/loop/ -q`, `ruff`, `mypy` green; no GPU.

## Sequencing

One code slice (vocabulary + writers + reader), then the reader-boundary test and the write-up.
The transcript format has no version tag, so the change is the new decision value only — no field,
no version bump.
