# Spec — `diffcheck` (aspect 1 of `p2-format-hardening`)

**Boundary:** the classify-only validator, the transcript's retry-aware schema, and the
anti-credulity proof. Nothing here generates, retries, or publishes.

## Problem slice

The format-hardening response needs an online classification of a completion's diff — at
grading time, before the verifier — that says exactly which of the autopsy's causes a
rollout is, so a retry can be triggered on the convertible ones and never on the others.
The taxonomy already exists and is git-agreeing by measurement
(`src/whetstone/bakeoff/autopsy.py:319 classify_completion`; `finding.md:69-71`); this
aspect reuses it **by identity** — import, never copy — so online verdicts and the offline
autopsy cannot disagree.

The transcript must also be able to hold more than one attempt per `(candidate, task)`
without breaking the two frozen consumers (`attribution.py`, `autopsy.py`), which both read
through `Transcript.replay()` — keyed, **last record wins** (`transcript.py:134-144`,
`attribution.py:471`, `autopsy.py:885`). That semantic is already the retry-decided selector.

## Decisions (amendments to PRD D6 and R1, code-grounded)

- **A1 — Every attempt lives in the transcript; no separate attempts log.** The frozen
  consumers use keyed last-wins `replay()`, so multi-record keys are safe by construction
  (`transcript.py:142-144` already documents "the later completion is the one the run would
  have carried forward and scored" — retries make that the ordinary case, not an anomaly).
  `Transcribed` gains `attempt: int` and `decision: str` fields via the module's own
  deliberate codec discipline (`transcript.py:228-258` — a new field breaks `_encode` first).
  The replay function of PRD R3 is `Transcript.replay()` itself; a test asserts the live
  run's decided completions equal `replay()`'s, byte-for-byte.
- **A2 — The validator's trigger decision is the taxonomy, not a second git pass.** The
  autopsy's fine causes were corrected until the walk agreed with git on every stored record
  (`finding.md:69-71`); the fuzzy margin (hunk-dies-early vs hunk-count-mismatch) was settled
  *as* the taxonomy. Running a fresh `git apply --numstat` at trigger time would introduce a
  second opinion on exactly that margin. PRD R1's git probe is amended: git is consulted in
  the measured-arm pre-analysis only, never in the online trigger decision.
- **A3 — The anti-credulity proof is end-to-end, sub-verdict-pinned.** A held-path edit must
  survive the validator byte-for-byte and reach STRICT, which refuses it as `patch-scope`
  → `Outcome.OUT_OF_SCOPE` (`scoring.py:512-529`), asserted as the specific sub-verdict, in
  both the well-formed and the malformed-hunk shapes (a malformed held-path diff still gets
  its retry, and the retry's diff still touches the held path — refusal happens at STRICT,
  never in the pipeline).

## In-scope requirements

- `src/whetstone/bakeoff/diffcheck.py`: `trigger_of(result)` — the fine cause → trigger
  mapping (triggers: `hunk-count-mismatch`, `hunk-dies-early` with death `bare-line` or
  `fence-cut`; non-triggers: `well-formed`, `im-start-loop`, `hunk-dies-early` with death
  `end-of-output`, `no-diff`, `unrecognised-shape`, `header-without-hunk` — pending the
  measured-arm pre-analysis, which may move `header-without-hunk`); `diagnosis_of(trigger)`
  — the finite, fixed diagnosis vocabulary (one sentence per trigger; no completion-derived
  numbers; sentences are constants, asserted no-format-args); `Decision` type.
- `src/whetstone/bakeoff/transcript.py`: `Transcribed` gains `attempt` and `decision`;
  codec updated; docstring's one-line-per-key contract rewritten for retries; `replay()`
  semantics unchanged.
- Anti-credulity test, watched failing against a credulous validator first
  (`CONTRIBUTING.md:56-60`): asserts the `patch-scope` sub-verdict specifically and the
  WEAK/STRICT differential on the same fixture.
- Diff-stat pins (PRD AC2): `src/whetstone/verify/`, `patch.py`, `attribution.py`
  byte-identical to `origin/master` — `attribution.py` gains its own guard (the missing
  pin).
- No-inference AST walk over `diffcheck.py` (the `attribution.py`/`autopsy.py` pattern);
  no `mlx`/`run.py` imports.

## Acceptance criteria (tests written first)

1. `uv run pytest tests/bakeoff/test_diffcheck.py tests/bakeoff/test_transcript_retries.py`
   green; the new modules' no-inference walk green.
2. A held-path edit (well-formed and malformed shapes) survives the validator byte-for-byte;
   the end-to-end rollout is `(Outcome.OUT_OF_SCOPE, Status.FAIL, Status.PASS)` with
   sub-verdict `patch-scope` — watched failing against a credulous validator first.
3. `git diff --stat origin/master -- src/whetstone/verify/ src/whetstone/bakeoff/patch.py
   src/whetstone/bakeoff/attribution.py` is empty (the AC2 pin, `attribution.py` included).
4. A stored multi-attempt transcript replays to exactly the live run's decided completions
   (last record per key, `decision == "graded"`).
5. Trigger mapping: one fixture per cause shape, both halves (triggered vs not), grounded in
   the dig's three dialects; `end-of-output` and `im-start-loop` asserted non-triggers.

## Out of scope

- The retry wrapper itself, the freeze extension, and `run.py` wiring — aspect `retry-loop`.
- Any published figure, any `reports/` change, the contract fields — aspect
  `contract-report`.
- The arm, the pre-analysis run, the before/after breakdown — aspect `measured-arm`.
- Any change to `verify/`, `patch.py`, `attribution.py`, or the reward-path guards.

## Open questions / risks

- Whether `header-without-hunk` stays a trigger depends on the pre-analysis evidence
  (`measured-arm`); the mapping is parameterised so the arm can move it without code churn.
- `test_run_transcript.py` and `test_transcript_locality.py` assert transcript behaviours
  that retries change (one-line-per-key) — they are amended deliberately in this aspect,
  never silently.
