# Spec — measurement-run

**Slug:** `edit-contract-finding` · **Aspect:** `measurement-run` · **PRD:** § 4.1 (M1–M9)
**Written:** 2026-09-30 · **Core-loop element:** ② nightly improvement loop — the generation
contract.

## Problem slice

No run has ever prompted under a numbered-listing / line-range edit contract, so whether the
pinned base can *address* such a listing is unknown. This aspect builds the measurement: a
renderer + parser for the numbered-listing format, a driver that spends one small real bake-off
on the pinned base (16 pre-committed tasks, greedy, no verifier entry, control arm required),
an offline addressability instrument with a rule fixed **before** the run and exposed as a
command exit, the pre-committed spec, the operator's runbook, and the finding. On NO-GO this
aspect is the whole unit: nothing is built beyond it, and no amendment is made.

## In scope

- The numbered-listing renderer (off the reward path, byte-deterministic, held tests never
  rendered into the prompt) and the `EDIT`-block parser (never repairs).
- A renderer seam in `bakeoff/scoring.py`: an injectable renderer whose default is
  `render_prompt`, so every existing caller's behaviour is byte-identical.
- The measurement driver `python -m whetstone.bakeoff.measure`: one greedy attempt per task
  (`K = 1`, retries 0), journal + transcript + run manifest in the standard codecs, control arm
  required (no evidence, no verdict, refusal exit if not intact), population pinned by identity
  (the spec's 16 ids), no verifier entry, no `reports/` output.
- The addressability instrument `python -m whetstone.bakeoff.addressability`: offline,
  stdlib-only, deterministic; classes `UNCLASSIFIED > MALFORMED > NO_FILE > OUT_OF_RANGE >
  ADDRESSABLE` (worst-first); syntax-only `ast.parse` gate on replacements; sub-counts reported
  never decisive; decision rule **GO iff `count(ADDRESSABLE) * 2 > population`**; exits
  0 GO / 1 NO-GO / 2 refused.
- The committed spec (this file's rule content) and the operator's runbook (guarded).
- The committed finding (operator's pass; separate commit; counts only in gitignored `runs/`).

## Out of scope

- Any change under `verify/` or `tasks/`; any change to STRICT, WEAK, the gate rule or `R`.
- Any change to `rendering.py`, `run.py`, `night.py` — a NO-GO must leave them byte-identical.
- The `numbered-listing-contract` aspect (PRD § 4.2) and the amendment (PRD § 4.3) — GO-gated.
- Running a night under the new format; new-file creation; fuzzy/repair location; retries.

## Acceptance criteria (written first — they are the failing tests)

1. **Renderer**: the numbered listing contains every line of every oracle source file at
   `base_commit`, numbered 1-based, byte-deterministic across processes and hash seeds; a held
   test path is refused by name, never rendered into the prompt (the `HeldTestInSources`
   precedent). Test: `tests/bakeoff/test_line_range.py`.
2. **Parser**: an `EDIT`-block completion parses to path + range + replacement; malformed
   blocks (missing path, unparsable range, unclosed replacement) are named refusal classes,
   never repaired, never dropped while others proceed. Test: same file.
3. **Seam**: `scoring.score`'s default renderer path is byte-identical to master (the existing
   suite stays green); an injected renderer reaches the generator. Tests:
   `tests/bakeoff/test_measure_driver.py`.
4. **Driver**: with a stub generator (model-free), the driver writes manifest + journal +
   transcript over exactly the pinned 16-task population; a task-set mismatch is a refusal
   (exit 2, no evidence); a run whose control arm is not intact on every draw produces no
   evidence and no verdict (refusal); the verifier is never entered (no STRICT/WEAK call for
   any rollout — asserted by seam spy). Tests: `tests/bakeoff/test_measure_driver.py`.
5. **Instrument — classes**: each class fires on a fixture (real lines → `ADDRESSABLE`; end
   beyond EOF / start > end / overlapping ranges → `OUT_OF_RANGE`; unknown path → `NO_FILE`;
   garbage → `MALFORMED`; unreachable evidence → `UNCLASSIFIED` and **stays in the
   denominator**); worst-first severity (one `OUT_OF_RANGE` block + one `ADDRESSABLE` block →
   `OUT_OF_RANGE`); a replacement that fails `ast.parse` → not `ADDRESSABLE`; sub-counts
   (non-importable replacements; blocks addressing paths outside the oracle listing) reported
   beside the partition, never moving a class. Tests: `tests/bakeoff/test_addressability.py`.
6. **Instrument — the rule and exits**: the strict-majority inequality is a constant in code,
   cross-pinned to the committed spec's sentence (the `locatability` output-schema pattern);
   exit 0 iff `ADDRESSABLE * 2 > population`, else 1; refusals (missing manifest/transcript,
   empty population, task-set mismatch, unreadable corpus) exit 2 with a named reason and write
   nothing. Determinism: same inputs → byte-identical output. Tests:
   `tests/bakeoff/test_addressability_cli.py`.
7. **NO-GO hygiene — adversarial**: the measurement can never be read as a win — no outcome
   the driver records or the instrument emits is `SOLVED` or any covered verdict, and the
   reward-path guards are green: the AST inference walk, the partition guard, the one-way
   import test, and `tests/bakeoff/reward_amendments.py` (nothing under `verify/` moved).
   Tests: `tests/test_no_inference_on_reward_path.py` (unchanged, still green),
   `tests/bakeoff/test_generator_contract.py` (unchanged).
8. **Runbook**: the runbook pins the spec citation, the population, the exact commands, and
   the digest-equality halt (a changed spec or population is a halt, never a rerun); a guard
   test refuses a live citation to a wrong rule. Test: `tests/bakeoff/test_measure_runbook_guards.py`.
9. **Finding**: `docs/planning/edit-contract-finding/measurement-run/finding.md` states the
   decision, the population size, the proxies (syntax-only grammaticality; necessary condition,
   never a yield prediction; the run's `prompt_sha256` is new and comparable to nothing prior),
   and on NO-GO records that nothing was built. (Doc — verified by review, not by test.)

## Dependencies and sequencing

1. Renderer + parser (pure; no dependencies).
2. Scoring seam + driver (depends on 1; the seam default keeps master behaviour).
3. Instrument + command (depends on 1 for parsing; reads manifest + transcript from 2).
4. Spec + runbook + guards (the rule content of this spec is cross-pinned by the instrument's
   constants; committed before the operator's run).
5. The operator's run + the finding (separate commit; the runbook commands it; GPU is
   machine-level and serialized; weights pointed at by absolute path from the primary checkout).

## Open questions / risks

- Journal rows under the measurement carry `outcome = UNVERIFIED` with a `detail` stating the
  run never grades; consumers must not read the field as a verdict — the spec (below) states
  it, and the finding restates it. (The manifest, not the journal, is the instrument's source
  of truth for population and candidate.)
- The `EDIT`-block markers are fixed in this aspect's format section (below); the GO-gated
  contract aspect may refine wording but must keep the parseable grammar.
- R1 (proxy): no stored evidence; the run is the operator's pass, ~45–60 min generation on the
  pinned base plus control/verification (16 × ≈ 258 s/task, `reports/larger-base/cost.json`).
- R9 (better bases): the instrument and contract are harness assets that persist as bases
  improve; the rule sets no threshold and the amendment (on GO) says so.

---

## The pre-committed rule (this is what the spec pins — committed before any rollout runs)

- **Population.** The 16 tasks: the easier-stratum document's `membership`
  (`tasks/stratum/easier.json`, by digest), minus the held-out document's `membership`
  (`tasks/heldout/source-b.json`, by digest). Overlap, by identity:
  `donor-a-6884ed72a9e9`, `donor-a-c6e4d4c4de87`, `donor-a-c7cee63e3cab`. A run whose task set
  differs from this list is refused. A held-out member is never a rollout target.
- **Run.** One greedy attempt per task (`K = 1`), retries 0, candidate
  `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` (PREREGISTRATION.md § 10.10), numbered-listing
  prompt, no verifier entry, control arm intact on every draw required.
- **Format (measurement).** A completion contains one or more blocks:
  `EDIT <repository-relative path>:<start>-<end>` followed by a replacement section opened by
  `<<<<<<< REPLACE` and closed by `>>>>>>> END`. Blocks may sit inside one fenced block.
- **Classes, worst-first.** `UNCLASSIFIED` (evidence unreachable; stays in the denominator) →
  `MALFORMED` (no block could be parsed) → `NO_FILE` (named path absent at `base_commit`) →
  `OUT_OF_RANGE` (start > end, start < 1, end > the file's line count at `base_commit`, or
  ranges on one file overlap) → `ADDRESSABLE` (every block's range names existing,
  non-overlapping lines and every replacement text parses with `ast.parse`).
- **Decision.** GO iff `count(ADDRESSABLE) * 2 > population`; otherwise NO-GO. The rule is a
  go/no-go for building the contract — never a claim about yield, never a grade of correctness.
- **Sub-counts (reported, never decisive).** Replacements that parse but the file would not
  import; blocks addressing a path outside the oracle listing's set (classified by file
  existence at `base_commit`).
- **Proxies disclosed in the finding.** Syntax-only grammaticality; addressability is a
  necessary condition for the contract to help, not a prediction; the run's `prompt_sha256` is
  new and the figures are comparable to nothing prior.