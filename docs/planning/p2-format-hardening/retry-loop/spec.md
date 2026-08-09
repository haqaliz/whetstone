# Spec — `retry-loop` (aspect 2 of `p2-format-hardening`)

**Boundary:** the `Retry` wrapper on the Generator seam, the retry-prompt builder, the
freeze extension that keeps every retry prompt inside the seal, and the `run.py`
composition wiring. Depends on `diffcheck` (validator + transcript schema).

## Problem slice

The validator classifies; the retry converts. The wrapper must re-ask the model, bounded
and only when the evidence says the attempt was convertible, with a prompt that the run's
own seal will accept — which forces the retry prompt to be a pure function of
`(task, trigger)` (PRD D8).

## Decisions (amendments to PRD D8/R2, code-grounded)

- **B1 — The retry prompt does NOT carry the prior completion.** PRD R2's "carries the whole
  prior completion" is amended: any completion-derived content makes the prompt set
  unbounded, and the seal (`run.py:240-252`) refuses prompts whose hash is not in the frozen
  `posed` map — so the retry prompt is `first-attempt prompt + fixed retry instruction +
  one finite diagnosis sentence`, pre-renderable at freeze time (D8's own formulation wins
  over R2's sentence). The 3B rollover lesson (`dig-transcripts.md:363-366`) is discharged by
  the validator instead: loop/rollover shapes are non-triggers by the autopsy's own
  precedence (a real diff's state outranks the loop).
- **B2 — Composition: `Retry(Recording(Sealed(engine)))`.** Recording sits *inside* Retry so
  every attempt is recorded (the user's interview decision — every attempt in the
  transcript, aspect 1), and Sealed stays innermost so every prompt, first and retry, passes
  through the frozen-set check. The run.py property "Recording outside Sealed so the
  recorder sees refused prompts" (`run.py:546-552`) is preserved: Recording is still outside
  Sealed; a seal-refused prompt raises `ContractChanged` through Recording (no record — the
  record-follows-generation rule) and Retry (no further attempts), aborting the run as it
  does today.
- **B3 — Scope refusals can never be retried structurally.** The wrapper is upstream of the
  verifier and only ever sees the validator's verdicts; a held-path edit is a
  `well-formed` (or trigger-shaped) diff — in the trigger case the retry may run, and the
  retried diff still touches the held path (nothing in the pipeline drops content, aspect 1
  A3), so STRICT's `patch-scope` still fires and the rollout is counted `OUT_OF_SCOPE`.
- **B4 — Budget 2, a contract field.** At most two retries per `(candidate, task)`; the
  decision is a pure function of `(attempts so far, validator verdicts)` — replayable.
  A retry is issued iff `trigger_of(verdict)` is a trigger AND `attempts < 1 + budget` AND
  the retry prompt's hash is in the frozen set (checked by Sealed itself).

## In-scope requirements

- `src/whetstone/bakeoff/retry.py`: `RETRY_INSTRUCTION` (fixed text), `retry_prompt(prompt,
  trigger)` (pure: prompt + instruction + `diagnosis_of(trigger)`), `Retry` — a
  `Generator` wrapper with `inner`, `validator` (defaults to `trigger_of(classify_completion
  ...)` — actually: validator = `trigger_of` applied to `classify_completion(text)`), and
  `budget: int = 2`. `generate(prompt)`: attempt 0 → record attempt+decision via inner;
  loop while trigger and budget remains: build retry prompt, `inner.generate(retry_prompt)`
  (which records it); the last completion is returned. Deterministic by construction (pure
  decision + greedy inner).
- `src/whetstone/bakeoff/run.py`:
  - `freeze` (`:408-450`) pre-renders retry prompts: per task, per trigger, `retry_prompt(
    render_prompt(...), trigger)` added to `posed` (`setdefault` — one task's prompts map to
    that task). The contract SHA therefore covers the retry vocabulary (a template edit
    moves it — the D8 property).
  - The entrant loop composition (`:546-556`) becomes `Recording(Retry(Sealed(engine)))`'s
    inside-out twin `Retry(Recording(Sealed(engine)))` — wait, B2 names the final shape;
    the loop constructs `Sealed(engine)` → `Recording(...)` → `Retry(...)` per candidate.
  - The transcript records gain `attempt` + `decision` (aspect 1) — the retry wrapper (or
    the recorder) sets them; the recorder derives `task_id` from each attempt's
    `prompt_sha256` via `contract.posed` (the existing mechanism — retry prompts map to the
    same task).
- Tests:
  - Retry-prompt finiteness: every retry prompt generated in a run is present in the frozen
    `posed` map (the seal-held test, PRD AC8); a mid-run retry-template edit aborts
    (`ContractChanged`).
  - `Retry` unit tests over `StubGenerator` (which raises `UnstubbedPrompt` on an unstubbed
    prompt — a retry prompt must be stubbed for the test): trigger path issues exactly
    budget retries then stops; non-trigger issues none; well-formed issues none; budget
    exhaustion stops; exceptions propagate untouched (the `sweep` discipline,
    `sweep.py:109-112`).
  - Replay: a run's decided completions equal `Transcript.replay()` (last per key,
    `decision == "graded"`).
- No-inference AST walk over `retry.py` (it may import `diffcheck`, `autopsy`,
  `generator`, `rendering.prompt_hash` — never `mlx`/`run.py`/`scoring`).

## Acceptance criteria (tests written first)

1. `uv run pytest tests/bakeoff/test_retry.py` green; the no-inference walk green.
2. The seal-held test: with a frozen contract, every prompt the composed generator issues —
   first attempts and all retries — has its hash in `contract.posed`; editing the retry
   template after freeze aborts the run (`ContractChanged`), asserted end-to-end through
   `freeze` + the wrapper.
3. Deterministic replay: given the same `StubGenerator` table and the same prompts, the
   decided completions and the transcript records (attempt indices, decisions) are
   byte-identical across two runs.
4. Budget discipline: a completion that triggers on every attempt issues exactly
   `1 + budget` generations (3 with budget 2) and returns the last; never more.
5. A held-path edit that happens to be trigger-shaped is retried, and the decided diff still
   touches the held path — STRICT refuses it `patch-scope` (cross-aspect with diffcheck).

## Out of scope

- The validator's mapping and vocabulary — aspect `diffcheck`.
- Contract fields (`retry_budget`, `retry_template_sha256`, `diagnosis_vocabulary_version`)
  in `GenerationContract` — aspect `contract-report` (the constants live here; the fields
  are published there).
- The arm, the pre-analysis, the breakdown — aspect `measured-arm`.
- Any change to `verify/`, `patch.py`, `attribution.py`.

## Open questions / risks

- The retry wrapper needs the retry template's SHA-256 available to the report — expose it
  from `retry.py` as a computed constant (hash of the instruction + vocabulary sentences);
  `contract-report` publishes it.
- `Recording`'s per-attempt `task_id` derivation depends on retry prompts being in `posed` —
  if a diagnosis sentence is ever added without the freeze extension, the seal aborts every
  run loudly (good — the failure mode is named, not silent).
