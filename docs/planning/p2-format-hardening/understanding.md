# Understanding — `p2-format-hardening`

**Dig date:** 2026-08-09 · **Digs:** three parallel read-only agents over the worktree
(generation-contract side, measurement/report side, verifier boundary) · **Upstream:**
`docs/planning/p2-diff-autopsy/finding.md` (the wall is formatting, `:43-49`),
`dig-transcripts.md:318` (the named interventions), `p2-yield-probe/prd.md` (R3–R8, D2–D9).

---

## 1. What the work is really asking

The autopsy proved the pivot signal's premise was never tested: the rollouts died as
**format**, not as reasoning — three per-model dialects (`im-start-loop`, `hunk-dies-early`
with its three deaths, `hunk-count-mismatch`) all violate the diff grammar git parses. The
fourth fix the yield-probe correction demanded (`p2-yield-probe/prd.md:84-89`) is a
**format-hardening response on the generation contract** — the side the yield probe left
open. The deliverable is a *measured before/after cause breakdown via the autopsy
instrument*, never a predicted count (`finding.md:106`; card AC: "not a raised count").

Core-loop element: this is **harness infrastructure between ① the verifier and ② the
improvement loop** — it converts "git would not read this diff" rollouts into rollouts the
STRICT verifier actually grades, which is what unblocks P2 proper (`p2-diff-autopsy/prd.md:269-270`
calls `whetstone run --night` blocked on this question). The reward itself is untouched by
construction (card AC2 freezes `src/whetstone/verify/`).

## 2. The seams, mapped (from the dig)

The generation flow is `generate` → `extract_patch` → (`NoDiff` → `NO_DIFF`, never reaches a
verifier) → `_verify` → STRICT then WEAK (`scoring.py:432-449`). Three named seams:

- **Prompt side** — `_RESPONSE_FORMAT` (`rendering.py:131-142`) already says "a single
  unified diff, inside one fenced block tagged `diff`" with the file-header pair; it does
  not demand `diff --git` headers or structured output. The template is sealed by
  `Contract`/`Sealed` (`run.py:408-450`, `240-252`): **any template edit is a new generation
  contract** — `prompt_sha256` moves, and figures under it are non-comparable with
  `reports/baseline/`. The patch-scope rule is stated to every candidate identically and
  never names which files are held (`rendering.py:94-104`).
- **Extraction seam** — `scoring.py:435-442`: between "a diff was located" and "the verifier
  is entered". `patch.py`'s extractor is **frozen by identity** (card AC2; its privates may
  be imported, never copied: `dig-code.md:48-51`). The extractor's only repair is a final
  `\n` (`patch.py:313-320`); its never-repair rule (`patch.py:20-35`) is the prose half of
  the R5 credulity constraint.
- **Generator seam** — `generator.py:46-70` (one method, deliberately). Wrappers are the
  established composition pattern: `Sealed` → `Recording` → `RecordingGenerator`
  (`run.py:548-556`, `transcript.py:167-225`). Retry would live here. **Greedy sampling is
  deterministic** (`SAMPLER = "greedy: argmax"`, `mlx_runtime.py:91`; no seeds, `run.py:123-127`):
  a retry with the same prompt returns the same bytes, so retry requires a *changed prompt*
  (failure feedback) — which is a new contract under the seal.

## 3. The wall's three shapes, and what each intervention can touch

| Shape | Cause (per dig) | What a validator sees | What can convert it |
|---|---|---|---|
| `im-start-loop` (7B) | chat-template token loop; nothing diff-shaped | no header at all | only prompt/sampler-side; nothing content-side converts it |
| `hunk-dies-early` | bare-line death / fence-cut / end-of-output (the last is pure budget truncation, *inferred*) | hunk starts, body stops | a one-shot *repair* could re-count a fence-cut; truncation cannot be repaired (content is missing) |
| `hunk-count-mismatch` | invented counts; git's parser never stops → "corrupt patch" | counts ≠ body | mechanically fixable **if** the walker can re-count — but repairing is authoring (`patch.py:20-28`) and the frozen `patch.py` walker is the only ground truth |

Constraint set from the dig:
- **Nothing may be silently skipped.** A converter that skips an unresolvable edit is the
  R5 failure: oracle sources deliberately exclude every held path
  (`rendering.py:151-161`, `sources.py:371-391`), so a held-path edit has **no anchor
  content**; "skip what cannot be resolved" converts a caught cheat into an uncaught one
  (`p2-yield-probe/prd.md:154-168`). The R5 acceptance test asserts the specific sub-verdict
  `patch-scope`, watched failing against a credulous converter first.
- **No finish reason exists.** `mlx_runtime.generate` returns a bare `str`
  (`mlx_runtime.py:206-232`); truncation is *inferred from shape*, never measured
  (`finding.md:81-84`). Any detector claiming a measured truncation would overclaim.
- **The autopsy replay must stay aligned.** If the converter changes what counts as a diff,
  the offline replay (`autopsy.py:322-333`) and attribution must run the *same* converter,
  or AC3 (zero `unrecognised-shape`) breaks. Extractor identity is pinned
  (`test_autopsy_partition.py:522-537`).
- **A stricter prompt must not break extractor tolerance tests.** `test_extraction.py`
  pins fence-label tolerance and bare-diff acceptance (`:373-395`); a prompt that *demands*
  a fence is fine (the extractor stays lenient), an extractor that *requires* one is not
  (patch.py is frozen).

## 4. What a new-contract run must carry (measurement side)

- **Run protocol** (`python -m whetstone.bakeoff.run`): `--tasks/--public/--pool/--funnel/
  --weights/--out/--workspace/--timeout/--recorded-on` all required; `--journal` AND
  `--transcript` both passed (AC7 lesson: per-task checkable afterwards); `--transcript`
  must be outside `--out`; `--dev-subset` for the contract's own excluded tasks. Weights and
  corpus read by absolute path from the primary checkout (never copied into the worktree);
  workspace must be an empty path per run.
- **Attribution then autopsy**: `attribution --transcript ... --out ... [--tasks ...]`
  (schema `whetstone-attribution/1`), then `autopsy --transcript ... --attribution ... --out
  runs/diff-autopsy/<arm>.json` (schema `whetstone-autopsy/1`; `--out` must be under a
  gitignored root, refused otherwise — `autopsy.py:727-745`).
- **Report**: `GenerationContract` carries `prompt_sha256, sampler, max_tokens,
  extractor_version, dev_subset` (`report.py:175-199`); retrieval is a hard-coded module
  constant (`report.py:67-75`) — yield-probe D9 would make it a field ("a machine-readability
  fix so two contracts can be told apart"). Non-comparability sentence pre-quoted
  (`report.py:92-95`). The one-home guard is asserted **twice, in lock-step**:
  `tests/bakeoff/test_report.py:961-994` and the opposite-sign copy in
  `tests/bakeoff/test_transcript_locality.py:73-101`; both must be amended together with the
  D6 argument ("the two directories measure different generation contracts and are declared
  non-comparable") in the docstring. Fallback if the argument cannot be made honestly: a
  second contract section *inside* `reports/baseline/` (yield-probe R-f, `prd.md:223`).
- **Dev subset**: `ScoredDevSubset` refuses any task the contract was developed against
  (`report.py:139-145`, `385-397`); the new contract needs its own declared subset, not the
  P1 three (`p2-yield-probe/prd.md:114-117` D7).
- **PREREGISTRATION**: § 10.4 (Type 2 amendment, log-table row at `:308-312`) if a governed
  figure is published; closes no § 7 item; no placeholder, no proportion in any spelling
  (`tests/test_docs.py:554-604`).

## 5. Guardrails the slice must not trip

- **Reward stays execution-grounded**: `verify/` byte-identical to `origin/master` (AC2;
  the existing guard `tests/bakeoff/test_autopsy_guards.py:126-143` extends to `patch.py`
  at `test_autopsy_partition.py:539-558`; `attribution.py` gets its own diff-stat pin — the
  card's AC2 is that pin).
- **`whetstone bakeoff` must not exist as a CLI subcommand** (`run.py:7-13` — `cli.py` is
  the guarded reward entrypoint).
- **New code lands in `src/whetstone/bakeoff/`** — the single `EXEMPT` entry, no guard-file
  changes (`test_reward_path_scope_is_partitioned.py:100-117`); its own no-inference AST
  walk (the `attribution.py`/`autopsy.py` pattern, `FORBIDDEN_IMPORT_ROOTS`); no
  `mlx_runtime`/`run.py` imports in offline code (`dig-code.md:266-271`).
- **Held-path edits stay countable**: a scope-violation diff must still reach STRICT and be
  refused as `patch-scope` → `OUT_OF_SCOPE` (`scoring.py:512-529`), so it counts in the
  published caught-hack floor (`report.py:113-116` would otherwise become false).
- **The differential / N is untouched**: one diff flows to both WEAK and STRICT
  (`scoring.py:475, 494`); N = WEAK-PASS-and-STRICT-FAIL stays the definition.

## 6. The decision the interview must settle (evidence-led, per the dig)

The dig names three interventions and the evidence constrains them differently:

1. **Pre-verifier diff validator** (safe direction: classify, never author). Converts
   nothing by itself — its value is (a) a retry trigger, (b) a *measured* malformed-cause
   count at the moment of grading (today the cause is known only offline, post-hoc, via
   autopsy). It must not be credulous in either direction: dropping a held-path hunk is the
   R5 failure; reporting "truncated" as measured is an overclaim.
2. **Malformed-output retry** (Generator wrapper + changed prompt with failure feedback).
   The only mechanism that can *convert* `hunk-count-mismatch`/`hunk-dies-early`-without-
   truncation rollouts into content-eligible ones — if the model can comply with a
   corrective instruction. Deterministic greedy means the retry prompt must differ (the
   diagnosis appended). The retry must see the whole completion (the 3B rollover lesson,
   `dig-transcripts.md:363-366`). A bounded retry budget is a contract field; no finish
   reason means the truncation-triggered retry may just burn budget — acceptable if named.
3. **Structured/fenced-output prompt change** (stricter `_RESPONSE_FORMAT`). Cheap, moves
   `prompt_sha256` (new contract), risk of merely shifting the violation mode
   (`p2-yield-probe/prd.md:221` R-d); `im-start-loop` is unlikely to be touched by it.
   Search/replace converters are **not re-adopted**: withdrawn on the yield-probe's own
   evidence (`p2-yield-probe/prd.md:65-89` correction) and the credulity trap is their
   centre.

The likely shape of the slice (to be confirmed in the interview): a **validator + retry**
pair on the generation contract, a new report for the new contract (non-comparability
declared, one-home guard amended by D6 argument), a fresh dev subset, a `§ 10.4` amendment,
and the measured arm: run the hardened contract over the declared source-B set, autopsy the
transcript, and publish the before/after cause breakdown — where "after" is declared
non-comparable, not "better".

## 7. Open questions for the interview

1. Which interventions does the slice build — validator only, validator + retry, or all
   three (incl. prompt-side spec)? (The dig's evidence: validator alone converts nothing;
   retry needs a changed prompt; prompt-side alone likely misses `im-start-loop`.)
2. Does the slice run the bake-off arm (≈1.4 h+ per the yield probe's measure) or build the
   machinery and validate it on the stored transcripts first? (Card AC3 says "the run
   persists raw generations" — the run is in scope.)
3. Retry budget and trigger policy (which shapes trigger a retry, and what the retry prompt
   carries) — a contract field, disclosed.
4. Dev-subset choice for the new contract (which task ids are excluded as "developed
   against").
5. Report shape: new directory under `reports/` (D6 argument) vs. second contract section
   inside `reports/baseline/` (R-f fallback) — the interview decides; the one-home guard
   moves only with the argument in its docstring.
6. Whether `im-start-loop` (7B) records are in scope at all — a prompt-side fix is the only
   lever and it may not move the bucket.
