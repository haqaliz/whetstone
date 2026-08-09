# PRD — `p2-format-hardening`

**Card:** `docs/planning/p2-format-hardening/card.md` · **Dig:**
`docs/planning/p2-format-hardening/understanding.md` (three parallel agent digs)
**Upstream:** `docs/planning/p2-diff-autopsy/finding.md` (`:43-49` — the wall is formatting),
`dig-transcripts.md:318` (the named interventions), `p2-yield-probe/prd.md` (R3–R8, D2–D9,
and the correction at `:65-89`), `PREREGISTRATION.md` § 10.1, `docs/ROADMAP.md` § 4.

---

## 1. The problem

The P1 pivot signal fired on the premise that *expert iteration has nothing to bootstrap
from* (`docs/ROADMAP.md:387-389`). The yield-probe correction demanded a fourth fix be
proposed only after someone read the unparseable diffs (`p2-yield-probe/prd.md:84-89`);
the autopsy then measured that read and found a **formatting wall, not a reasoning wall**
(`p2-diff-autopsy/finding.md:43-49`): the candidates *can* write a diff git accepts and
almost never do, dying in three per-model dialects (`im-start-loop`, `hunk-dies-early` with
its three deaths, `hunk-count-mismatch`) before any fix could be graded. The finding names a
**format-hardening response** as the untested intervention and says nothing about whether it
raises any count (`finding.md:106-107`).

P2 proper (`whetstone run --night`, rejection sampling) is **blocked on this question**
(`p2-diff-autopsy/prd.md:269-270`). Nothing in this slice is P2 proper.

## 2. What is already decided upstream (not re-litigated)

| Decided | Where |
|---|---|
| The reward is a pytest exit status; no model on the reward path | `CLAUDE.md`, `docs/ROADMAP.md` § 2 |
| The generation contract is not a pinned input, and it moves the numbers | `PREREGISTRATION.md:333-354` |
| Any report publishing a governed figure states its contract and declares non-comparability | `PREREGISTRATION.md:356-361` |
| Search/replace converters are withdrawn — two contract fixes falsified | `p2-yield-probe/prd.md:65-89` |
| A zero is a publishable outcome; no threshold is introduced | `p2-yield-probe/prd.md:188-192` (R9); `PREREGISTRATION.md:171` |
| `src/whetstone/verify/`, `patch.py`, `attribution.py` are frozen byte-identical on this branch | card AC2 (`card.md:38-39`); `p2-diff-autopsy/prd.md:132-136, 152-157, 186-190` |
| The extractor never repairs; the extractor's privates may be imported, never copied | `patch.py:20-35`; `dig-code.md:48-51` |
| `whetstone bakeoff` must not exist as a CLI subcommand | `run.py:7-13`; card AC5 |
| Figures about a model live in exactly one home; nothing is restated | `tests/bakeoff/test_report.py:961-994`; `CLAUDE.md` |
| The autopsy's taxonomy is complete over its corpus; a future shape is `unrecognised-shape` until read | `p2-diff-autopsy/finding.md:108-110` |
| `PREREGISTRATION.md` § 7.3 (which base) stays open and may not be closed after the measurement | `PREREGISTRATION.md` § 8.1 |

## 3. Decisions taken in this slice

**D1 — Build a validator + retry pair; re-adopt no converter.** *(interview decision)* The
evidence constrains the three named interventions differently: a validator alone converts
nothing (it can classify and trigger, never author); retry needs a changed prompt because
greedy decoding is deterministic — same prompt, same bytes (`mlx_runtime.py:91`,
`run.py:123-127`); prompt-side hardening alone likely never touches the 7B's `im-start-loop`
collapse. Search/replace converters are **not** re-adopted: withdrawn on the yield-probe's
own evidence, and the R5 credulity trap is their centre (`p2-yield-probe/prd.md:154-168`).

**D2 — Machinery TDD-first, then the measured arm.** *(interview decision)* The slice ships
the validator and the retry wrapper as tested code, then runs the hardened contract over the
declared source-B set (same shape as arm A: 63 tasks × 3 candidates, `--tasks` per donor +
`--public/--pool/--funnel/--weights/--out/--workspace/--timeout/--recorded-on`, `--journal`
and `--transcript` both passed — the AC7 lesson), and delivers the **measured before/after
cause breakdown** via the autopsy instrument over the stored transcripts. The "before" is the
two already-autopsied stored runs (`runs/arm-a/`, `runs/budget-2048/`, 2026-08-09); the
"after" is this slice's arm. No reproduction requirement against `reports/baseline/`: the
hardened contract is non-comparable by design (D4's argument), so D2a-style reproduction does
not apply to it.

**D3 — Retry policy: parse-refusals only, budget 2.** *(interview decision)* A retry is
triggered only when the validator finds **diff-shaped output that git would refuse to parse**
— `hunk-count-mismatch`, `hunk-dies-early` with the `fence-cut`/`bare-line` deaths, and
`header-without-hunk` (the full trigger list is fixed in the validator's contract, below).
Non-triggers, by evidence: `im-start-loop` / loop-dominated output (nothing content-side
converts it), `end-of-output` (budget truncation — *inferred*, never measured; a retry would
burn budget on missing content), and `well-formed` (it must reach git and be graded).
**Scope refusals never trigger a retry**: a held-path diff parses fine — it is STRICT's
`patch-scope` that refuses it, and that refusal is the counted outcome, not a format problem
for the model to have another go at. Budget 2 = at most two retry attempts per
`(candidate, task)`, a disclosed contract field.

**D4 — The new report is a new directory, argued, not listed.** *(interview decision)* The
arm publishes into a **new `reports/format-hardening/`** directory (`report.md`,
`report.json`, `cost.json`), carrying both arms with the contract each was measured under and
the non-comparability sentence (`report.py:92-95`). The one-home guard is amended **twice,
in lock-step** — `tests/bakeoff/test_report.py:961-994` and the opposite-sign copy at
`tests/bakeoff/test_transcript_locality.py:73-101` — and only with the D6 argument in each
docstring: *the two directories measure different generation contracts and are declared
non-comparable, so neither is a competing home for the same figure.* A silent list extension
is refused. If that argument cannot be made honestly, the fallback (R-f of the yield probe,
`p2-yield-probe/prd.md:223`) is a second labelled contract section inside
`reports/baseline/` — the interview chose the directory shape, so the fallback is the named
consequence of failing to argue.

**D5 — A declared dev subset for the new contract.** *(interview decision)* The retry
template and the validator thresholds are developed against real task context, so the arm
declares 3–5 source-B task ids via `--dev-subset` — named in this PRD's implementation
before the run, refused by `ScoredDevSubset` if any reaches the scored set
(`report.py:139-145, 385-397`), and excluded from both sources before anything runs
(`run.py:910-929`). It may not be the P1 three (`p2-yield-probe/prd.md:114-117` D7).

**D6 — Attempts are recorded, and the frozen tools stay frozen.** *(interview decision +
constraint)* With retries there are multiple completions per `(candidate, task)`. The
**graded path** keeps the existing transcript schema exactly — one record per
`(candidate, task)`, the *decided* (final) completion — because `attribution.py` and
`autopsy.py` replay over that schema, and both are frozen (card AC2). Every attempt and the
retry decision (attempt index, per-attempt `prompt_sha256`, cause, `retry | no-retry`) are
recorded in a **new gitignored attempts log** (schema `whetstone-retries/1`, under a
gitignored root, refused under `--out` like transcripts). A new **pure replay function** in
the new bakeoff module re-derives, from the attempts log alone, the same decided completion
per `(candidate, task)` byte-for-byte — the R1 discipline extended to the retry decision.
The autopsy classifies the decided completions exactly as it classifies any transcript.

**D7 — `PREREGISTRATION.md` gains a § 10.4, Type 2.** The arm publishes a governed figure
(PASS counts under the new contract), so § 10.4 is added exactly per
`p2-yield-probe/prd.md:119-122`: disclosures only (the new contract — retry budget, retry
template hash, diagnosis vocabulary — and the non-comparability of the two reports), a row in
the log table (`PREREGISTRATION.md:308-312`), nothing above § 10 edited, no placeholder, no
proportion in any spelling (`tests/test_docs.py:554-604`). It closes no § 7 item — in
particular **not § 7.3** (this slice selects no base).

**D8 — The retry prompt stays inside the seal, which forces a finite diagnosis
vocabulary.** `Sealed` refuses any prompt whose hash is not in the frozen `posed` map
(`run.py:240-252`), so **every possible retry prompt must be pre-rendered at freeze time**.
The retry prompt = first-attempt prompt + a fixed retry instruction + exactly one sentence
from a **finite, fixed diagnosis vocabulary** (one sentence per trigger shape; no
completion-derived numbers — a number in a sentence would make the prompt set unbounded and
the seal un-freezable). `freeze` (`run.py:408-450`) pre-renders `|tasks| × (1 +
|vocabulary|)` prompts. A diagnosis sentence change is a template change: it moves a contract
field and voids the run, like any other template edit.

**The composition, stated correctly.** The retry wrapper must wrap a *sealed* generator and
yield exactly one decided completion, so the recorder sees one record per
`(candidate, task)` and every internal retry prompt still passes through `Sealed`:
`Recording(Retry(Sealed(engine)))`. A composition with `Sealed` outside `Retry` would let
the retry prompts bypass the seal, and a wrapper that yields every attempt would give the
frozen transcript schema multiple records per `(candidate, task)` (corrected by this slice's
self-critique, § 8). Retry's internal calls each go through `Sealed`; a retry prompt missing
from the frozen set raises `ContractChanged` and aborts the run, like any mid-run template
edit. The transcript record carries the **decided attempt's** prompt and completion; the
retry prompts live in the attempts log (D6). The one-method `Generator` seam is preserved:
`Retry` is a wrapper, and the decisions that matter (which attempt is decided) are pure and
replayable (R3).

**D9 — The generation contract gains the retry fields.** `GenerationContract`
(`report.py:175-199`) gains `retry_budget: int` (2), `retry_template_sha256: str`, and
`diagnosis_vocabulary_version: str`. Retrieval becomes a field too (yield-probe D9,
`p2-yield-probe/prd.md:124-128`): it stays **oracle** — this is the machine-readability fix
so two contracts can be told apart programmatically, which is what § 10.1 asks for. The
published baseline artifacts are static and are not regenerated.

## 4. Requirements

### R1 — The validator: classify-only, deterministic, offline-sound

A new module `src/whetstone/bakeoff/diffcheck.py` (name to confirm in tech-plan) classifies a
completion's diff against the autopsy's own fine causes, with these properties:

- Uses `patch.py`'s walker **by identity** (import the privates, never copy —
  `dig-code.md:48-51`); the parse decision is made by **real git** (`git apply --numstat -z -`
  on the extracted diff — the parse-vs-apply split of `test_attribution.py:144-162, 372-409`),
  with config scrubbed (`GIT_CONFIG_GLOBAL=/dev/null`).
- Returns exactly one of: `well-formed` (git parses it), or a named trigger cause
  (`hunk-count-mismatch`, `hunk-dies-early` with detail `fence-cut`/`bare-line`,
  `header-without-hunk`), or a named non-trigger (`im-start-loop`, `end-of-output`
  [truncation-inferred, labelled], `no-diff`, `unrecognised-shape`).
- **Never modifies the diff it classifies.** A held-path edit passes through unmodified and
  reaches STRICT, which refuses it as `patch-scope` (R4). The validator has no authoring
  power: no re-anchoring, no re-casing, no dropping, no re-counting.
- Deterministic: same completion → same verdict, tested; stdlib-only, no inference imports,
  no `mlx_runtime`/`run.py` imports (its own no-inference AST walk, the
  `attribution.py`/`autopsy.py` pattern — `dig-code.md:266-271`).
- Truncation is **inferred from shape** and labelled as such (`finding.md:81-84`); the
  validator never claims a measured token cap.

### R2 — The retry wrapper: Generator-seam, sealed, budgeted

A new wrapper on the one-method `Generator` seam (`generator.py:46-70`; the wrapper pattern
of `Recording`/`RecordingGenerator`, `transcript.py:167-225`):

- Sits inside the seal: `Recording(Retry(Sealed(engine)))` — the retry wrapper wraps the
  sealed generator, every retry prompt is pre-frozen (D8), and the recorder sees exactly one
  record per `(candidate, task)`: the decided attempt's prompt and completion.
- Issues at most `retry_budget` (2) retries per `(candidate, task)`, only for trigger causes
  (D3). The retry prompt = first-attempt prompt + fixed retry instruction + one finite
  diagnosis sentence, and carries the **whole prior completion** (the 3B rollover lesson,
  `dig-transcripts.md:363-366` — a rollover is extractor-invisible today).
- Never retries a scope refusal, never retries an inferred truncation, never retries a
  `well-formed` diff.
- The deciding completion is the last attempted completion, and the decision is a pure
  function of (attempts, validator verdicts) — replayable (R3).

### R3 — Attempts log + replay function

- New gitignored attempts log, schema `whetstone-retries/1`: per `(candidate, task)` —
  every attempt with its own `prompt_sha256`, the validator verdict per attempt, and the
  decision (`retry | no-retry` + budget consumed). Refused under `--out` (the transcript
  refusal precedent, `run.py:886-907`); documented homes asserted gitignored.
- The replay function re-derives the same decided completion per `(candidate, task)` from
  the log alone; a test asserts stored-log replay is byte-identical to the live run (the
  R1 identity discipline, `test_attribution.py:181-195`, extended).
- The **transcript keeps its existing schema** (decided completions only) so
  `attribution.py` and `autopsy.py` run unchanged; the autopsy classifies the hardened arm's
  transcript completely — zero `unrecognised-shape` or a named divergence finding (the
  instrument's own contract, `finding.md:108-110`).

### R4 — Anti-credulity (the centre of this slice, R5 inherited)

The validator and retry wrapper together must never convert a caught cheat into an uncaught
one:

- A held-path edit survives validator + retry **unmodified**, so STRICT fires the
  `patch-scope` sub-verdict specifically and the rollout is counted `OUT_OF_SCOPE`
  (`scoring.py:512-529`) — the published caught-hack floor stays true (`report.py:113-116`).
- The test is watched failing against a credulous validator first
  (`CONTRIBUTING.md:56-60`), asserts **the sub-verdict is `patch-scope`**, and uses the
  fixture shapes that actually produce the differential (`WEAK == PASS, STRICT == FAIL` at
  `patch-scope` — `tests/bakeoff/test_scoring.py:557-590` is the record-level pin).
- The retry never observes held-path content: the diagnosis carries no file paths beyond the
  diff's own headers, and nothing in the retry machinery uses `task.test_blobs` as a
  sanitisation list.

### R5 — The measured arm

- **Offline pre-analysis, before any GPU spend**: replay the two stored transcripts through
  the validator and count, per trigger shape, how many stored records the trigger policy
  would actually have retried — and how many parse-refusals are `end-of-output`
  (truncation-inferred, never retried) or `im-start-loop`. This names the **conversion
  ceiling** (the retry-eligible subset of the dig's 84 `WOULD_NOT_PARSE` records,
  `dig-transcripts.md:324-327`) before the run, and confirms the trigger list rather than
  assuming it. A ceiling near zero is a finding that outranks the arm and halts it (the D2a
  discipline applied to this slice's own premise).
- One generation pass, hardened contract, over the declared source-B set × 3 candidates,
  minus the D5 dev subset; the exact run flags as in D2. Weights and corpus read by absolute
  path from the primary checkout (never copied into the worktree); an empty workspace per
  run.
- Outputs (all gitignored): `runs/format-hardening-arm/` with `transcript.jsonl`,
  `retries.jsonl`, `journal.jsonl`; then `attribution` and `autopsy` over the decided
  completions; the cause breakdown is the deliverable and lives in the gitignored homes —
  the published report points at them rather than restating them (the one-home rule for
  classifier counts, `finding.md:89-92`).
- A **flat before/after is a valid, publishable outcome** — the report states it plainly
  (R9 of the yield probe). No threshold is introduced.

### R6 — The report

- `reports/format-hardening/{report.md,report.json,cost.json}`, both arms, each with its
  contract fields (D9) and the non-comparability sentence; the one-home guard amended twice
  with the D6 argument (D4).
- **The comparison discloses token spend.** The hardened arm spends up to 3 draws of 1024
  tokens per task (initial + budget 2) against arm-a's single draw; the report states each
  arm's total token spend per task and per candidate, so a bucket shift cannot be misread as
  "the model got better at formats" when it was "the harness bought three draws". The
  retry-eligible ceiling from the pre-analysis (R5) is reported alongside the after
  breakdown, as the number the arm was measured against.
- Nothing under `reports/baseline/` is touched; no figure from either directory is restated
  in `CLAUDE.md`, `docs/ROADMAP.md`, the CHANGELOG, or any planning document.
- The run ledger records pinned seeds (greedy — none), retry budget, diagnosis vocabulary,
  model revisions, task set, and tool versions.

### R7 — Reward-path stasis

- `src/whetstone/verify/`, `src/whetstone/bakeoff/patch.py`, and
  `src/whetstone/bakeoff/attribution.py` are byte-identical to `origin/master` on this
  branch; the existing guards (`test_autopsy_guards.py:126-143`,
  `test_autopsy_partition.py:539-558`) keep passing, and `attribution.py` gains its own
  diff-stat pin (card AC2).
- `GUARDED_ROOTS` is not widened; all new code lands in `src/whetstone/bakeoff/` — already
  the single `EXEMPT` entry with a written reason (`test_reward_path_scope_is_partitioned.py:100-117`),
  so **no guard file changes**.
- `whetstone bakeoff` stays a nonexistent subcommand (card AC5).

### R8 — Governance

- `PREREGISTRATION.md` § 10.4 exists (D7): Type 2, log-table row, disclosures only, closes
  nothing, no placeholder, no proportion in any spelling.
- The retry fields (D9) are disclosed in the report's contract block; the report states that
  its figures may not be compared with `reports/baseline/`.

## 5. Acceptance criteria

Every one is a command that exits 0 or an artifact that exists.

1. `uv run pytest` green; `ruff check .`, `mypy src/`, `whetstone --help` all exit 0
   (`CONTRIBUTING.md:50`).
2. **R4**: a held-path edit flows through the validator + retry pipeline, the diff is
   byte-identical to what the model wrote, STRICT returns `patch-scope`, the rollout is
   `OUT_OF_SCOPE` — watched failing against a credulous validator first; the WEAK/STRICT
   differential is asserted on the same fixture.
3. **R7**: diff-stat tests assert `src/whetstone/verify/`, `patch.py`, and `attribution.py`
   are unchanged relative to `origin/master`; the reward-path guard and its scope partition
   pass unchanged.
4. **R3**: a stored attempts log replays to the same decided completions as the live run;
   the autopsy over the hardened arm's transcript completes with zero `unrecognised-shape`
   (or the named-divergence finding the instrument's contract requires).
5. **R6**: `reports/format-hardening/report.md` and `report.json` exist, carry both arms,
   the D9 contract fields, and the non-comparability sentence; the one-home guard is amended
   twice with the D6 argument in its docstring (`test_report.py:961` and
   `test_transcript_locality.py:73-101`).
6. **R8**: `PREREGISTRATION.md` § 10.4 exists with a log-table row, contains no placeholder
   and no proportion in any spelling (`tests/test_docs.py:554-604`).
7. **R5**: the offline pre-analysis ran over the two stored transcripts and the retry-eligible
   ceiling is named in the gitignored breakdown before the arm; the arm ran —
   `runs/format-hardening-arm/` holds transcript, attempts log, and journal (asserted
   gitignored); the before/after cause breakdown exists in the gitignored homes and the
   report points at them.
8. **R2/D8**: a test asserts every retry prompt issued at runtime is present in the frozen
   prompt set (the seal held), and that a mid-run retry-template edit aborts the run.
9. `whetstone bakeoff` remains absent from the CLI.

## 6. Risks

| # | Risk | Mitigation |
|---|---|---|
| R-a | **Retry prompts break the seal** — a diagnosis carrying completion-derived numbers makes the prompt set unbounded and unfreezable | D8: finite, fixed diagnosis vocabulary; every prompt pre-rendered at freeze; the seal-held test (AC8) |
| R-b | **The validator disagrees with git's parser on the same bytes** (the autopsy's own lesson, `finding.md:53-77`) | All walk rules fixture-tested against real git (`GIT_CONFIG_GLOBAL=/dev/null`); `patch.py`'s walker reused by identity, never re-implemented |
| R-c | **The arm shows no conversion** — the after-breakdown is flat | Pre-committed publishable outcome (D2/R5); the report states it plainly; no threshold exists to miss |
| R-d | **Multi-attempt transcripts break the frozen attribution/autopsy replay** | D6: decided completions in the existing schema; attempts in a separate log; replay function re-derives the decision |
| R-e | **Retry burns GPU budget on unfixable shapes** | D3: triggers restricted to parse-refusals; `im-start-loop` and inferred truncation never retry |
| R-f | **The one-home argument is refused at review** | D4 names the fallback: a second labelled contract section inside `reports/baseline/` |
| R-g | **Dev tasks leak into the scored set** | D5: `--dev-subset` + `ScoredDevSubset` refusal, both directions; ids named before the run |
| R-h | **The retry gives the model extra chances to hide a scope violation** | D3: scope refusals never trigger a retry; R4's pipeline test asserts the refusal is `patch-scope`, not silence |
| R-i | **`report.py`/`run.py`/`scoring.py` changes regress the baseline contract's behaviour** | The published baseline artifacts are static; the full suite (725 tests) must stay green; any contract-shape test change is reviewed as part of D9 |

## 7. Out of scope

- **All of P2 proper**: no rollout loop, no rejection sampling, no LoRA, no training, no
  checkpoint (`whetstone run --night` remains blocked until this slice's measurement lands).
- **Any change to `src/whetstone/verify/`, `patch.py`, or `attribution.py`** — the reward,
  the extractor, and the attributor are frozen (R7).
- **Search/replace or any diff-authoring converter** — withdrawn on evidence (D1).
- **A prompt-side hardening of the first-attempt template** (`_RESPONSE_FORMAT` stays
  byte-identical; the retry template is the only new prompt).
- **Closing `PREREGISTRATION.md` § 7.3** (which base), the held-out split (§ 7.1), and the
  retry count `R` (§ 7.2 — the retry budget here is a generation-contract field, not the
  gate's retry count).
- **Explaining the 7B loop's cause** and **re-classifying `im-start-loop`** — the validator
  names the shape; it does not diagnose the model.
- **Anything touching the network or a model** in the validator/replay machinery — offline,
  stdlib-only; only the arm's generation pass calls a model, locally.

## 8. Self-critique

Ran through the generator's critique against this document.

| Dimension | Rating | Note |
|---|---|---|
| Problem Definition | 🟢 | The wall is measured, not asserted (`finding.md:43-49`); P2 proper is blocked by name on this question (`p2-diff-autopsy/prd.md:269-270`) |
| Success Metrics | 🟡 | No invented numbers — the before/after is a measured breakdown, and a flat result is pre-committed; the token-spend asymmetry between arms (1 draw vs up to 3) is disclosed (R6) but the "before" and "after" remain different-spend comparisons, which a reader can still misread without the disclosure sentence |
| User Understanding | 🟢 | The operator persona, consistent with the repo's own persona notes (`p2-diff-autopsy/prd.md:297-301`) |
| Scope Clarity | 🟢 | In/out explicit; search/replace refused by name; the first-attempt template is byte-identical; `§ 7.3` stays open |
| Edge Cases & Risks | 🟢 | Nine risks; R-a (unfreezable prompts) and R-b (validator-vs-git divergence) are the named hard parts, each with a fixture-first mitigation |
| Stakeholder Alignment | 🟢 | Solo project; the review gate is the approval |
| Feasibility Signal | 🟡 | The wrapper composition was written backwards in the first draft (D8) and corrected here — the recorder/seal interaction is the slice's sharpest edge; no effort estimate, stated as unknown rather than guessed |
| Reward Integrity & Never-Regress | 🟢 | `verify/` frozen by AC2 and by guard tests; the anti-credulity test asserts the specific `patch-scope` sub-verdict; scope refusals never retry; no § 7.3 close; nothing leaves the box |

**The top gaps, stated as findings:**

🔴 **The recorder/seal composition is the slice's sharpest edge and it is now corrected in
the text, but its consequence deserves a sentence of its own.** With
`Recording(Retry(Sealed(engine)))`, the transcript's prompt field is the decided attempt's
prompt while the graded completion comes from that same attempt — self-consistent only if
the retry wrapper yields the decided (prompt, completion) pair to the recorder. A wrapper
that yields the bare completion would pair a first-attempt prompt with a retry completion
and lie about which prompt was graded; tech-plan must pin the decided-pair contract first,
with the watched-failing test.

🟡 **The trigger list was set before it was measured.** D3's trigger set is grounded in the
dig's 84 `WOULD_NOT_PARSE` partition (45 + 39, `dig-transcripts.md:324-327`), but the
retry-eligible *subset* — excluding `end-of-output` truncation and `im-start-loop` — has not
been counted. R5's offline pre-analysis is the fix: it names the conversion ceiling before
any GPU spend, and a near-zero ceiling halts the arm (the D2a discipline applied here).

🟡 **Token-spend asymmetry.** The hardened arm buys up to 3× the tokens per task; the
before/after is a comparison of contracts, not of models. R6's disclosure (per-arm total
token spend + the ceiling) is the mitigation; without the sentence, a converted bucket reads
as a model gain.

**The question I would want answered before greenlighting this:** *If the offline
pre-analysis over the two stored transcripts shows that the retry-eligible subset of the 84
parse-refusals is a minority — most deaths are `end-of-output` truncation or `im-start-loop`
— is the full GPU arm still the right spend, or does the slice stop at machinery plus
pre-analysis and defer the arm until a prompt-side change makes the retry's ceiling worth
the run?* The PRD's answer is pre-committed: the pre-analysis is mandatory and a near-zero
ceiling halts the arm (R5) — but the decision of *what counts as worth the run* is the
review gate's call, made now rather than after the run.
