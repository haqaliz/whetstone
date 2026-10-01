# Understanding — edit-contract-finding (2026-09-30)

Sources: `docs/planning/_card/issue.md` (the whetstone-next handoff brief, verbatim),
`docs/planning/patch-representation/finding.md`, `docs/ROADMAP.md` § 13/§ 14, and a code dig
across the worktree (file:line citations below).

## What the work is really asking

Five nights across three base sizes have selected **zero** strict-PASS rollouts. The largest
single cause is that git refuses the diffs the model writes — the model decides what to change
and then fails to *transcribe* it (context lines and offsets from memory). The
`patch-representation` unit (issue #64) measured the first candidate direction — search/replace
— and got **NO-GO**: the pinned base's refused diffs mostly do not quote the file exactly
(`finding.md:10-17`), and the near-misses (lines skipped, indentation shifted, the model's own
edit quoted as the original) are exactly what an exact-anchor contract cannot forgive without
the harness choosing the model's answer (`finding.md:35-49`; the M10 doctrine,
`patch-representation/prd.md:117-121`).

The finding names one direction the evidence does not rule out (`finding.md:84-92`): **a
representation that never asks the model to quote existing code at all** — e.g. the prompt
shows a **numbered source listing** and the model addresses **line ranges** and writes
replacement text; the **harness** renders the diff. It is a lead, not a proposal, and it
"would need its own finding before any amendment".

This unit is that finding. Its shape mirrors `patch-representation` exactly: a **pre-committed
GO/NO-GO rule** (written and committed before any rollout runs), exposed as a command exit
(0 GO / 1 NO-GO / 2 refusal, following `check-probe` and `locatability`); an **offline,
deterministic, stdlib-only instrument** off the reward path (same boundary as
`bakeoff/locatability.py`); a **committed finding** whose counts live only in gitignored
`runs/`. On NO-GO the unit ships instrument + finding (+ the reason-field polish) and nothing
else. On GO it additionally ships the parser/converter (exact location, never repair,
all-or-nothing, scope-before-location), a `NOT_LOCATED`-equivalent covered outcome, adversarial
tests asserting the STRICT/WEAK differential stays intact, and a Type 1 amendment
(`PREREGISTRATION.md` § 10.x) committed before any night records `edit_format = line-range`.

## The decisive difference from locatability: there is no stored evidence

`locatability.py` classified a **finished** run's transcripts
(`locatability.py:289-295,323-334`). No run has ever prompted under a numbered-listing
contract, so this unit must spend a **small real bake-off** on the pinned base
(`mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, § 10.10) under the new prompt, then classify
its output. Cost bounds from committed metadata: ≈ 258 s/task of generation on the 32B
(`reports/larger-base/cost.json`; `reports/larger-base/report.md:26`); a ~10-task run is
roughly 45–60 minutes of generation plus control-arm/verification time, bounded first by a
D7 timing probe (`run.py:598-610`, `runbook.md:51-98`). The run is the operator's GPU pass,
commanded from a runbook (the `measured-arm-run` precedent); the unit ships the machinery and
the rule, and the finding records the outcome.

## Affected areas (anchored)

- **The response contract seam:** `bakeoff/rendering.py:131-142` `_RESPONSE_FORMAT` (the diff
  response-format text) inside `render_prompt` (`:176-248`); byte-determinism rule `:25-36`;
  `prompt_hash` `:267-279`. A numbered-listing contract adds a second spelling here. The prompt
  is sealed before any engine exists — `freeze` digests every posed prompt (`run.py:418-473`)
  and `Sealed` aborts on an un-frozen prompt (`run.py:234-262`).
- **A new extractor:** the numbered-listing parser mirrors `bakeoff/patch.py:148-187`
  (`extract_patch` → `Extracted | NoDiff`); the "locate, never author" doctrine
  (`patch.py:20-28`) and the no-empty-string rule (`patch.py:8-18`) carry over. The harness
  *renders* the unified diff; `verify_strict`/`verify_weak` keep receiving a plain diff string
  (`scoring.py:454-516`; `verify/repo.py:87-118` is the reward-path boundary — unchanged).
- **The outcome surface:** `Outcome` enum (`scoring.py:87-130`); `_classify`
  (`scoring.py:519-536`); `report.tally` (`report.py:426-453`); `_UNCOVERED` set
  (`report.py:60`), imported by identity in `gate.py:99` and `night.py:41`; exhaustive tests
  (`tests/loop/test_dataset.py:84-91`, `tests/loop/test_gate.py:149-161`,
  `tests/loop/test_run_ledger.py:170-178`, `tests/bakeoff/test_honest_number_report.py:47-50`,
  `baseline.py:849-860`). A `NOT_LOCATED`-equivalent is a scored-zero (covered) member — never
  `_UNCOVERED`, never a win.
- **Provenance:** `extractor_version` is a digest over `patch.py`'s source (`run.py:1133-1141`);
  a new renderer needs its own digest or the recorded version will not move when the contract
  changes. `GenerationContract` (`report.py:177-218`) carries `prompt_sha256`; recorded in the
  ledger (`ledger.py:313-323`), per rollout (`scoring.py:184`), re-read by the honest/morning
  reports (`honest_report.py:237-247`, `morning.py:177-221`). No `edit_format` field exists
  anywhere today.
- **The instrument template:** `bakeoff/locatability.py` — spec fixed before the run
  (`locatability.py:12-15`), classes `:146-172`, worst-first per-rollout `:207-221`, exit map
  0/1/2 `:305-306`, refusal paths `:337-363`; spec shape at
  `docs/planning/patch-representation/locatability-finding/spec.md`; import guards
  `tests/bakeoff/test_locatability_cli.py:230-255`.
- **The driver:** `python -m whetstone.bakeoff.run` (`run.py:741-901` flags), deliberately not a
  `whetstone` subcommand (`run.py:7-13`); weights must be verified + local (`weights.py:134-181`);
  the pinned runtime is `PINNED_MLX_LM = "0.31.3"` (`mlx_runtime.py:74`).
- **What must not break:** reward path stays inference-free and one-way
  (`tests/test_no_inference_on_reward_path.py:104-109`; partition guard
  `tests/test_reward_path_scope_is_partitioned.py`); journal/transcript codecs are strict
  field-by-field (`journal.py:134-203`, `transcript.py:273-310`); the retry discipline replays
  recorded bytes (`gate.py:1337-1404`); the morning reader refuses unknown ledger fields
  (`morning.py:207-221`); no changes under `verify/` or `tasks/` (the card's guardrail, and the
  reward-path amendment registry `reward-path-amendments.json` is not for this).

## Ambiguities / open questions for the interview

1. **The measurement's population and scope.** How many tasks, drawn how (a fixed, pre-committed
   subset — which? the stratum? dev-subset?); one greedy attempt per task (K=1, matching the
   locatability population of graded attempts); retries 0.
2. **The classifier's classes under the new contract.** What exactly does "addresses real lines"
   mean (range within the file's line count at `base_commit`?); what does "grammatical
   replacement" mean as an offline structural check (non-empty? parses with `ast.parse`? a
   syntax-only proxy, never semantics); which classes (UNCLASSIFIED stays in the denominator);
   how the prompt-format refusal shapes are classified.
3. **The exact GO rule.** The inequality, the denominator (all rollouts of the population,
   refusals included), and its "e.g." status — the brief's "GO iff > half the sampled rollouts
   address real lines and produce grammatical replacements" is a suggestion, the rule is this
   unit's to fix and pre-commit.
4. **New-file creation is outside line-range addressing** (no lines to address). Declare it out
   of scope for the measurement (population = existing files only) and note it in the finding.
5. **The reason-field polish (NO-GO's third deliverable).** `NOT_APPLIED`'s `detail` already
   ships (0.15.0, `scoring.py:506-509`). What polish remains — `NO_DIFF`'s reason? the
   `UNCLASSIFIED` reasons? draws-directory acceptance (PRD S2)? Must be named precisely or cut.
6. **Measurement-run provenance.** The run's `prompt_sha256` will be new (it must be — that is
   the point); no amendment precedes the *measurement* (the amendment is committed only on GO,
   before any *night* records `edit_format`). The finding must state the non-comparability.
7. **Weights.** `weights/` is machine-level and gitignored; the run points at the primary
   checkout's copy by absolute path (never fetched inside a worktree).

## Contradictions and guardrail checks

- **No contradiction found between the brief and the code.** The brief's constraints (no
  `verify/`/`tasks/` changes; reward path and gate rule byte-identical; counts only in
  gitignored `runs/`) are all enforceable with existing machinery — the locatability precedent
  ships all three.
- **Reward stays execution-grounded:** STRICT/WEAK are byte-identical; the converter only
  renders a diff that STRICT re-executes against restored operator-held tests. On GO, the
  differential tests (STRICT rejects AND WEAK accepts) are the acceptance floor, and the
  scope-before-location rule keeps `N` honest (a held-path attempt is refused by STRICT itself,
  never labelled by the converter).
- **`UNVERIFIED` is never a win:** `NOT_LOCATED`-equivalent is a covered not-solved outcome;
  gate semantics, `R`, and the decision table are untouched.
- **Local-first:** the measurement run is on the pinned base already on this machine; nothing
  leaves the box. No judge anywhere: the instrument is a structural, pre-committed rule.
- **Type 1 discipline:** the amendment (§ 10.x) is committed *before* any night records the new
  `edit_format`, only on GO, and names a non-comparable home — exactly § 8.1's shape.
- **Core-loop element:** ② the nightly improvement loop — the generation contract that
  produces rollouts. It touches ① only at the seam where an edit becomes the patch STRICT
  grades, and ① does not change.