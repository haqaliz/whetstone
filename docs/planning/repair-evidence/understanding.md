# Understanding — repair-evidence

**Unit:** `feat/repair-evidence/aliz` · **Written:** 2026-11-03 · **Source:**
`docs/planning/_card/issue.md`, from the § 10.25 probe finding.

## What the work is really asking

The § 10.25 probe's one near-miss spent the two-attempt repair budget and converted none, but
**none of the repair prompts or completions are in the transcript**. `score`'s repair loop calls
`Retry.generate_repair`, which delegates to `Sealed` and skips `_record` (`retry.py:254-262`).
The transcript therefore shows the first graded completion only; a repair measurement cannot
show what the repair generated. The unit closes that evidence gap, without changing the reward,
the gate, the corpus, the held-out document, `K`, `R` or the § 10.25 inputs.

## Current code, precisely

- **The transcript has no version tag.** A row is exactly seven fields — `candidate`, `task_id`,
  `prompt_sha256`, `prompt`, `completion`, `attempt`, `decision` — encoded/decoded field by field
  (`transcript.py:91-112,273-310`). `decision` is an unvalidated `str`; the `Decision` Literal
  (`diffcheck.py:50`) is `"retry" | "graded"` and only types `Retry._record`.
- **`Transcript.replay()`** is the only reader (`transcript.py:153-199`): keyed by
  `(candidate, task_id)`, **last row wins**; a trailing `decision == "retry"` is refused because
  a retry must have a following record. There is no `records` accessor, no schema tag.
- **`Retry.generate`** records the retry rows (`"retry"`) before the next prompt and the last row
  as `"graded"` (`retry.py:231-252`). **`Retry.generate_repair`** calls
  `self.inner.generate(prompt)` and records nothing (`:254-262`).
- **`score`'s repair loop** (`scoring.py:477-499`) calls `generate_repair` up to `repair` times
  after `NOT_SOLVED`, re-verifies, and returns the final `Rollout`. The repair prompt is in the
  frozen `posed` map when `freeze(repair=True)` (`run.py:483-489`), so `_record`'s prompt-hash
  lookup would resolve it.
- **Composition:** `Draw → (Retry | Recording) → Sealed → engine` (`draws.py:233-253`). `Retry`
  is the only writer of retry rows; `Recording`/`RecordingGenerator` writes one `"graded"` row
  and has no `generate_repair`. With `retries=False` and `repair>0`, `Draw.generate_repair` falls
  back to `Recording.generate` and writes the repair as a second `"graded"` row (`sampling.py:225-236`)
  — a latent duplicate-graded path.
- **Consumers:** every reader calls `replay()`. `night._select` trains on the replayed completion;
  `attribution`/`autopsy`/`night_autopsy` classify the replayed completion; the locatability-family
  readers only see `NOT_APPLIED` keys, which cannot have repairs. A repair row last therefore
  becomes the completion those readers use — which is the right one for the final verdict, but it
  changes the exact-sequence tests (`test_run_transcript.py:468`, `test_transcript_retries.py:75-105`,
  `test_retry.py:515-587`).

## The real design choice

1. **Repair row vocabulary + replay.** A new `decision="repair"` row, last-wins: the final repair
   completion becomes the keyed record; `night._select` trains on the winning repair; the offline
   readers classify the completion the final verdict was computed on. Old transcripts read
   unchanged (the decoder accepts any string, but `replay` only refuses a trailing `"retry"`).
   This is the semantically correct choice, but it is a vocabulary change every reader inherits.
2. **Evidence-only repair rows.** Keep `replay()` on the last `"graded"` row and expose repair
   rows separately. This preserves every consumer, but a repaired solve would train on the
   **failed first completion** — wrong.
3. **A new optional `repair` field.** Explicit repair index; old seven-field rows read if the
   decoder tolerates absence. More schema surface, and the repo's transcript codec deliberately
   refuses defaults for missing columns, so this needs a careful compatibility branch.

The smallest complete change is **1** plus a `Recording.generate_repair` (or a guard that repair
requires the `Retry` composition): one new decision value, one `_record` call, the reader's
trailing-`retry` rule updated, and the exact-sequence tests extended. The `attempt` field stays
the first prompt's attempt; repair rows are ordered by file position. No new field.

## Core-loop placement

**② the nightly improvement loop's evidence.** The reward (①) and the gate (③) are untouched:
`score` still re-executes and the final `Rollout` is unchanged. The transcript is evidence, not
the reward path.

## Contradictions and risks surfaced

- **Last-wins is load-bearing.** A repair row after the graded row silently changes what
  `night._select` trains on and what `attribution`/`autopsy`/`night_autopsy` classify. That is the
  desired semantics for a repaired rollout, but it must be stated and tested, not discovered.
- **The old exact-sequence tests** (`retry/retry/graded`, "all replay values graded") become
  "repair rows may follow the graded row"; the trailing-`retry` invariant stays.
- **`--no-retries --repair N`** today records a duplicate `"graded"` row; the unit must either add
  a `Recording.generate_repair` or refuse the combination by name.
- **A repair row is not "graded".** The final repair completion is the one `score` re-verified, but
  the row cannot know whether it is the last repair; the journal's `Rollout` carries the final
  verdict. The transcript vocabulary must say "repair draw", not "final".
- **No schema tag.** The unit should not add a required field; the existing decoder's no-default
  rule is deliberate. The new decision value is the compatibility-preserving path.

## Affected areas

`src/whetstone/bakeoff/transcript.py` (docstrings/invariant), `retry.py` (`generate_repair`,
`_record`), `diffcheck.py` (`Decision`), `scoring.py` (only if the repair attempt index is needed),
`tests/bakeoff/test_retry.py`, `test_transcript*.py`, `test_run_transcript.py`,
`test_scoring.py`, `tests/bakeoff/test_retry_seal.py`; possibly `src/whetstone/loop/draws.py` /
`sampling.py` for the `Recording` path; write-up in `CHANGELOG.md`, `docs/STATUS.md`, `CLAUDE.md`.
