# PRD — repair-evidence

**Unit:** `feat/repair-evidence/aliz`. **Source:** inline brief, `docs/planning/_card/issue.md`.
**Understanding:** `docs/planning/repair-evidence/understanding.md`. **Status:** small follow-on to
`probe-sample-pin`; no number is measured.

## Problem statement

The § 10.25 probe's one near-miss spent the two-attempt repair budget, and the final verdict
stayed `NOT_SOLVED` — but the transcript contains **nothing** from the repair. `score`'s repair
loop calls `Retry.generate_repair`, which delegates to `Sealed` and skips `_record`
(`src/whetstone/bakeoff/retry.py:254-262`). A repair measurement therefore shows the first graded
completion only; the repair prompts and completions — the evidence of what the repair actually
generated — are lost. On the one real near-miss, the transcript has one row (`attempt=1`,
`decision="graded"`); there is no record of the two repair draws.

The same gap exists in the non-retry composition: with `retries=False`, `Draw.generate_repair`
falls back to `Recording.generate` and writes the repair as a second `"graded"` row, which
silently breaks the one-graded-row invariant.

## Goals & success metrics

- A near-miss under `--repair 2` writes the first attempt's rows **plus one `"repair"` row per
  repair draw**; a run with `--repair 0` is byte-identical to today.
- `Transcript.replay()` returns the **last** row for a key, so a repaired rollout's keyed record is
  the repair completion that produced the final verdict — not the failed first completion.
- Every existing transcript still replays unchanged: `retry`/`graded` rows are untouched, a
  trailing `"retry"` is still refused, and the seven-field codec is unchanged.
- `uv run pytest`, `uv run ruff check .` and `uv run mypy src/` exit 0. No GPU run.

## Requirements

### Must-have

1. **A repair decision.** Add `"repair"` to the `Decision` vocabulary (`diffcheck.py:50`) and to
   the transcript's runtime vocabulary. `Retry.generate_repair` records its prompt and completion
   through the same `_record` seam as a retry, with `decision="repair"`.
2. **Last-wins stays last-wins.** `Transcript.replay()` already keys by `(candidate, task_id)` and
   keeps the last row; a trailing `"repair"` is legal, and the keyed record is the final repair
   completion. The trailing-`"retry"` refusal stays exactly as it is.
3. **The reader refuses an unknown decision.** `replay()` (or the decoder) accepts only `retry`,
   `graded` and `repair`; anything else is `TranscriptUnreadable` by name. This is the vocabulary
   guard that makes the new value meaningful, and every existing transcript passes it.
4. **The non-retry composition.** `Recording` gains `generate_repair`: resolve the task from the
   frozen contract, generate once, append a `"repair"` row. An unfrozen repair prompt delegates
   unrecorded, exactly as `Recording.generate` does.
5. **The first row stays.** The first attempt's `"graded"` row is not deleted or rewritten. The
   transcript says "what was decided when this row was written"; the repair rows follow it, and
   the journal's `Rollout` remains the final verdict.
6. **No new schema field.** Repair rows carry `attempt=1`; the repair sequence is the file order,
   and the `decision` value distinguishes them. The seven-field codec is unchanged, so old and new
   rows read through the same decoder.
7. **Tests:** a near-miss under `repair=2` leaves two `"repair"` rows after the graded row; a
   repair that solves leaves the repair completion as the keyed record; a repair prompt outside
   the frozen contract writes no row and raises `ContractChanged`; the `Recording` path records a
   repair row; an old `retry`/`graded` transcript replays unchanged; an unknown decision is
   refused.
8. **Write-up:** `CHANGELOG.md` (Unreleased), `docs/STATUS.md`, `CLAUDE.md`, and a note in the
   § 10.25 finding that the evidence gap is closed. No `PREREGISTRATION.md` or `ROADMAP.md`
   change — no measurement input or phase moves.

### Should-have

- The `Transcribed.decision`/`Transcript`/`RecordingGenerator` docstrings state what a repair row
  means and that it can be the keyed record. The `RecordingGenerator`'s "one row per key" claim is
  narrowed to the no-repair case.
- A test that `attribution`/`night_autopsy` read the repair completion as the final one (the
  consumer they already use), so the last-wins change is pinned at the reader boundary and not
  only in the transcript unit.

### Nice-to-have

- A `repair` counter in `docs/`/the card? No: the file order is the sequence; a field would be a
  schema change for no evidence gain.

## Technical considerations

- **The repair prompt is already frozen.** `freeze(repair=True)` poses `repair_prompt(first)` and
  every `(fail_to_pass node, FAILURE_OUTCOMES)` variant under the first prompt's task
  (`run.py:483-489`). `_record`'s `prompt_hash` lookup resolves the repair prompt; an unfrozen one
  returns without a row, matching the existing retry delegation.
- **The repair loop has no transcript handle.** The recording belongs in the wrapper
  (`Retry`/`Recording`), not `score`; `score`'s final `Rollout` carries the verdict and the
  `generation_seconds` of the last attempt.
- **Last-wins is the semantic choice.** `night._select` trains on the replayed completion; a
  repaired solve must train on the repair completion, and a failed repair must not be selected.
  `attribution`/`autopsy`/`night_autopsy` classify the completion the final verdict was computed
  on. The locatability-family readers only see `NOT_APPLIED` keys, which cannot have repairs.
- **No reward/gate movement.** `score`'s verification path is untouched; the transcript is
  evidence.

## Risks & open questions

- **The exact-sequence tests** (`retry/retry/graded`, "all replay values graded") become "a repair
  row may follow the graded row"; the trailing-`retry` invariant is unchanged. The unit must edit
  those tests with the code, never loosen them.
- **A repair row is not "final".** The wrapper cannot know whether `score` will issue another
  repair; the last row is final by position. The docstrings must say "repair draw", and the
  journal's `Rollout` is the verdict.
- **The non-retry path was latent, not hypothetical.** `Draw.generate_repair` falls back to
  `Recording.generate` today and writes a duplicate graded row. Adding `Recording.generate_repair`
  fixes it; a test must pin it.
- **Old readers reading new files** still see the repair row as the keyed record (last-wins). That
  is the intended semantics, but it changes what `attribution`/`autopsy` classify for a repaired
  rollout; the should-have test pins it.
- **No new field means `attempt` is not a repair index.** The file order is the sequence; a reader
  that needs the index counts repair rows. That is enough for the evidence question.

## Out of scope

- A new near-miss-rich probe, the test-output-carrying seal redesign, a base/approach change, or
  the MPS hang.
- The reward path, the gate rule and exits, the corpus, the held-out document, `K`, `R`, the
  § 10.25 inputs.
- A transcript schema version or a new required field.
- A `reports/` home.

## Aspect decomposition

One aspect: **`repair-row`** — transcript/retry/recording code, tests, and the write-up. The unit
is small; a second aspect would be overhead.

---

## Self-critique (prd-generator workflow)

**🟡 The last-wins consequence is wider than the transcript.** It changes what the loop trains on
and what three offline readers classify. The PRD states it; the plan must pin it with a reader
test, not only a transcript test.

**🟡 `attempt=1` on every repair row is a compromise.** It keeps the seven-field codec, but a
reader cannot tell the first repair from the second except by file order. For the evidence
question — what did the repair generate — that is enough; for a future repair analysis that wants
to join a repair to its trigger, the prompt text carries the trigger and the order carries the
sequence.

**🟢 Scope and guardrails.** No reward, gate, corpus, held-out, `K`, `R`, GPU or egress. The
transcript is evidence; the `Rollout` is still the verdict.

**The question I would want answered before greenlighting this:** if a repair solves the task, the
keyed record becomes the repair completion and `night._select` trains on it — is that the text we
want in the training set, or should the training set carry the first attempt's prompt with the
repair completion? This PRD assumes the former: the repair prompt is the question that produced
the winning patch, and training on it is the honest pair.
