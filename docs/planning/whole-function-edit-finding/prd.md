# PRD — whole-function-edit-finding

**Core-loop element:** ② the nightly improvement loop — the generation contract that produces
rollouts. It touches ① only at the seam where an edit becomes the patch STRICT grades, and ①
itself does not change.
**Roadmap:** M1 of `docs/ROADMAP.md` § 14 (issue #64, open), follow-on of
`docs/planning/edit-contract-finding/` and `docs/planning/patch-representation/`.
**Source:** `docs/planning/_card/issue.md` (the 2026-10-01 `whetstone-next` handoff brief,
verbatim) + the interview decisions of 2026-10-01 (prompt format, classifier ladder and GO
rule confirmed; reason-field polish cut).

---

## 1. Problem Statement

No night has ever selected a strict-PASS: five nights across three base sizes, zero yield
(`docs/ROADMAP.md:831-837`). M1 — the only identified lever on the zero — has now measured
**two** representation directions NO-GO, and the second measurement recorded the observation
that directs this unit:

- **search/replace** was NO-GO on the quoting question: the pinned base's refused diffs mostly
  do not quote the file exactly (`docs/planning/patch-representation/finding.md:10-17`).
- **numbered-listing / line-range** was NO-GO on the addressing-and-grammar question: 0 of 13
  prompted rollouts fully addressable (`docs/planning/edit-contract-finding/measurement-run/finding.md:14-22`).
- The observation: the model's failure is **not transcription of existing text — it is closing
  its own replacement blocks and writing replacement text that parses**
  (`finding.md:107-113`). The finding's named lead, verbatim: *"a format that reduces the
  replacement text's surface (e.g. whole-function replacement keyed by a name the model can
  state, where the harness finds the function's extent) is the kind of change this evidence
  does not already rule out — a lead, not a proposal, needing its own finding before any
  amendment."*

This unit is that finding. **It measures before it builds**: a pre-committed GO/NO-GO rule,
fixed and committed before any rollout runs; a small real bake-off on the pinned base
(`mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, `PREREGISTRATION.md` § 10.10) under a
whole-function prompt; an offline, deterministic, stdlib-only instrument off the reward path;
and a committed finding whose counts live only in gitignored `runs/`. **On NO-GO the unit
ships the instrument and the finding, and nothing else** — no contract, no amendment, and the
standard generation path (`rendering.py`, `run.py`, `night.py`) stays byte-identical. **On GO
it additionally ships the converter** (exact location, never repair, all-or-nothing,
scope-before-location), adversarial tests asserting the STRICT/WEAK differential stays intact,
and a Type 1 amendment (`PREREGISTRATION.md` § 10.x) committed **before** any night records
`edit_format = whole-function`.

**Evidence it is real:** the zero-yield bind (`ROADMAP.md:831-837`); night-006's 83%
`NOT_APPLIED` with 55% structurally valid diffs git refused (issue #64); both NO-GO findings
committed (v0.15.0, v0.17.0); the observation above (`finding.md:107-113`).

## 2. Goals & Success Metrics

- **The decision is produced by a pre-committed rule, never by narrative.** GO iff
  `count(RESOLVABLE) * 2 > population` — the rule, its population (the pinned 16) and the run
  parameters are fixed in the measurement spec **before any rollout runs**, and the rule
  sentence is cross-pinned into the instrument's output. The decision is a process exit:
  0 GO / 1 NO-GO / 2 refusal.
- **A committed finding** states the decision, the partition, the population-equality join
  check, the control arm's integrity, the disclosures (proxy sharpness, one exposure, a
  `prompt_sha256` comparable to nothing prior), what is not claimed, and the roadmap's
  remaining responses. Counts live only in gitignored `runs/`.
- **A NO-GO ships instrument + finding only** — nothing built beyond the measurement, no
  amendment made (the pre-committed consequence, executed by both precedents).
- **A GO unblocks M1's next step**: the contract aspect and the § 10.x amendment, committed
  before any night records `edit_format = whole-function`.
- **The rule is never a yield claim**: the measurement is a necessary condition —
  addressability, never a prediction (`edit-contract-finding/measurement-run/spec.md:129-130`).

## 3. User Personas & Scenarios

The founder/operator running M1: wants the loop to select a strict-PASS so the gate can
answer and a model can publish. Scenario: spend ~45–60 minutes of GPU from a guarded runbook
(the edit-contract cost bound: ≈ 258 s/task of generation on the 32B, `reports/larger-base/cost.json`),
read the finding, and either build the converter (GO) or record the direction as measured and
spent, with the pre-committed responses (raise *k*, CPU dtype) carried forward (NO-GO).

## 4. Requirements

### 4.1 Must — the measurement (aspect `measurement-run`, always built)

- **M1 — the whole-function renderer, off the reward path.** A sibling of
  `bakeoff/rendering.py:176` (`render_prompt`) and `bakeoff/line_range.py:127` (the
  numbered-listing precedent), plugged through the existing injectable seam
  (`scoring.score(renderer=...)`, `bakeoff/scoring.py:214,365-375,444`). The default
  `render_prompt` stays byte-identical. The prompt poses the problem statement plus the
  task's oracle source file(s); the model emits, per rollout, `EDIT <path>` + `FUNCTION
  <name>` + a fenced **replacement body**.
- **M2 — the format, as designed, not as hoped.** Whole-function replacement keyed by a name
  the model can state; the **harness finds the function's extent** (AST at `base_commit`) and
  renders the diff. The model writes the **body only** — the signature and decorators stay in
  the file, untouched, so the format never asks the model to transcribe existing code (the
  search/replace wall) or address lines (the numbered-listing wall). One function per rollout;
  scope is module-level `def` and `async def`; the extent includes the original decorators and
  signature. The remaining surface — writing a grammatical replacement body — is exactly the
  observation the last finding recorded, and exactly what the measurement tests.
- **M3 — the measurement driver.** Mirrors `python -m whetstone.bakeoff.measure`: K = 1
  greedy by identity (`sampler_for(1)`, `loop/sampling.py:235-236`), retries 0, `RUN_SEED = 1`
  declared never a flag, **the verifier never entered** (every row `UNVERIFIED` by design),
  the control arm probed per task and required `INTACT` on every draw or the run refuses and
  writes nothing, evidence written only on full success with the manifest last, named
  refusals exit 2 writing nothing, the population pinned by identity.
- **M4 — the population, pinned.** The same 16 as the edit-contract run — the easier-stratum
  band's 19 members minus the 3 held-out members that overlap (`donor-a-6884ed72a9e9`,
  `donor-a-c6e4d4c4de87`, `donor-a-c7cee63e3cab`), derived by identity from the two documents
  through their fail-closed loaders (`measure.py:102-108,296-299`). The three `NO_ORACLE`
  members (`donor-a-128bcb99b701`, `donor-a-16213e62eae1`, `donor-b-45740535725b`) get no
  prompt, stay in the denominator, and the rule claims no scorable filter (the edit-contract
  precedent, `finding.md:75-80`).
- **M5 — the offline instrument.** Stdlib-only, deterministic, off the reward path, on the
  `bakeoff/addressability.py` boundary. Worst-first ladder, confirmed 2026-10-01:
  `UNCLASSIFIED > MALFORMED > NO_FILE > AMBIGUOUS > UNKNOWN_FUNCTION > NOT_PARSEABLE >
  RESOLVABLE`. The parse gate is a standalone `ast.parse` of the body **wrapped in a synthetic
  `def`** — a full statement, so the fragment-sharpness disclosure of the numbered-listing
  proxy is narrower by design. Sub-counts reported beside and never decisive: splice-in-context
  (re-parse the file at `base_commit` with the body spliced) and outside-shown-set (a path the
  prompt did not show). The rule sentence is a module constant cross-pinned into every output
  document; empty population is refused, never decided.
- **M6 — the GO/NO-GO rule, pre-committed.** GO iff `count(RESOLVABLE) * 2 > population`,
  every class in the denominator, `UNCLASSIFIED` included. Fixed in the spec before any
  rollout runs; the decision is the command exit 0 GO / 1 NO-GO / 2 refusal.
- **M7 — the guarded runbook.** The operator's GPU pass commanded verbatim from the **primary
  checkout** with absolute paths (the `tests/bakeoff/test_measure_runbook_guards.py`
  precedent); GPU serialized machine-level; weights re-verified by sha256; halt on a changed
  pre-committed input; a killed run restarts fresh under a new run id. **The timing bound is
  pre-committed**: generation bounded from committed metadata (≈ 258 s/task on the 32B,
  `reports/larger-base/cost.json`), the sheet halts at roughly twice the bound — a runaway
  generation is a halt, never an operator's judgement.
- **M8 — the finding.** The edit-contract template: decision in the title; the rule
  restated; the partition in full with the population-equality join check; the control arm
  `INTACT` on every draw; completions described in words; corroboration beside and never
  pooled; disclosures (proxy sharpness, one exposure, `prompt_sha256` new — comparable to
  nothing prior); what is not claimed ("loosening a pre-committed rule to rescue a NO-GO is
  the exact move this project's discipline forbids"); roadmap placement naming the remaining
  pre-committed responses (raise *k*, the portability arm's CPU dtype) and any next lead.
  **On NO-GO it records that nothing was built and no amendment was made.** The finding is
  the operator's checkpoint: it can stop a GO, it cannot turn a NO-GO into a GO (the
  edit-contract precedent, M9). The reason-field polish is **cut** (interview decision
  2026-10-01): 0.15.0 already shipped `NOT_APPLIED`'s `detail`, and the edit-contract unit
  shipped no polish.

### 4.2 Must, on GO — the contract (aspect `whole-function-contract`, GO-gated)

- **M9 — the converter.** The harness resolves `FUNCTION <name>` to a unique module-level
  function in the named file at `base_commit`, takes its extent (decorators + signature from
  the original, body replaced), and renders the unified diff. **Never repair, all-or-nothing,
  scope-before-location**: a name that is absent, ambiguous, out of scope, or a path the task
  did not show is refused — never guessed, never repaired. The "locate, never author" doctrine
  (`patch.py:20-28`) and the no-empty-string rule (`patch.py:8-18`) carry over.
- **M10 — the reward stays byte-identical.** STRICT/WEAK keep receiving a plain rendered diff
  string (`scoring.py:458-465`); nothing under `verify/` or `tasks/` changes or imports the
  new modules; the AST inference guard, the partition guard and the one-way import test stay
  green; `tests/bakeoff/reward_amendments.py` (the `verify/` freeze) stays green.
- **M11 — adversarial tests.** The STRICT/WEAK differential is asserted per cheat fixture:
  a patch a weaker check would accept — e.g. a replacement that fixes the test file, or a
  `FUNCTION` name that lands on a held test's path — is rejected by STRICT and accepted by
  WEAK. "The converter accepts a correct replacement" is half a test.
- **M12 — the outcome surface.** A `NOT_LOCATED`-equivalent covered outcome joins the
  outcome partition: scored zero, never `_UNCOVERED`, never a win; the exhaustive-outcome
  tests (`tests/loop/test_dataset.py`, `test_gate.py`, `test_run_ledger.py`, the honest-number
  report) are extended, not patched.
- **M13 — provenance moves.** `extractor_version` becomes a digest over every module the
  selected contract's extraction path executes (the edit-contract PRD's M18), so the recorded
  version moves when the converter moves; an `edit_format` selector appears on the drivers
  (`diff` default / `whole-function`), byte-identical for existing callers.

### 4.3 Must, on GO — the amendment (aspect `amendment-10-x`, GO-gated)

- **M14 — `PREREGISTRATION.md` § 10.x, Type 1 (§ 8.1)**, committed before any night records
  `edit_format = whole-function`: pins the edit format, the prompt template SHA-256, the
  extractor version, retry budget 0, and names the non-comparable home (declaration only
  until a night runs). It states that figures under it are comparable to nothing prior, sets
  no threshold, carries the does-not-change clause (the § 10.10 base, the verifier, the gate's
  terms untouched) and the no-threshold/no-reword invariance, and points at the measurement
  finding for why it exists.
- **M15 — the shape guard, written first.** `tests/test_docs.py` asserts the amendment's
  presence, its Type 1 sentence, the § 9 log row, the does-not-change clause, and cross-pins
  the pinned fields against the code by identity — watched RED against the pre-amendment
  tree before the amendment lands (the § 10.16 precedent,
  `docs/planning/heldout-scorable/amendment/spec.md`).
- **M16 — the roadmap correction.** `docs/ROADMAP.md` carries a dated correction naming § 10.x
  where the axis's status was last recorded; `docs/STATUS.md` and `CHANGELOG.md` entries in
  the same commit as the capability.

### 4.4 Should

- **The finding names the next lead** if the evidence supports one (the precedent's § 6
  behaviour) — recorded as a lead, never a proposal.

## 5. Technical Considerations

- **The seam.** `scoring.score(renderer=...)` (`bakeoff/scoring.py:214,365-375,444`) is the
  injectable renderer seam; the measurement driver calls its renderer directly
  (`measure.py:355`) and never enters the verifier (`:8-12`). The default path is
  byte-identical (asserted by `tests/bakeoff/test_measure_driver.py:345-390`).
- **Provenance.** The run's `prompt_sha256` is new by construction (`prompt_hash`,
  `rendering.py:267-279`); `prompt_sha256` and `extractor_version` are pinned
  generation-contract fields (`ROADMAP.md:855-857`), which is why the amendment precedes any
  night — and why a NO-GO must not amend anything.
- **Population derivation.** Same two fail-closed documents as the edit-contract run
  (`tasks/stratum/easier.json`, `tasks/heldout/source-b.json`), same 16 by identity, same
  three `NO_ORACLE` members in the denominator.
- **Reward-hacking surface.** The measurement never enters the verifier, so there is nothing
  to game; the instrument is a structural, pre-committed rule with no model anywhere on it.
  The GO-gated converter keeps the boundary: scope-before-location means a held-path attempt
  is refused by STRICT itself, never labelled by the converter — `N` stays honest.
- **Local-first.** The measurement runs on the pinned base already on this machine;
  `weights/` is machine-level and the run points at the primary checkout's copy by absolute
  path; nothing leaves the box.
- **The gate.** Decision table, three exits, `unverified == 0`, `R = 3`, `UNVERIFIED`
  semantics: untouched. `UNVERIFIED` is never a win; the instrument's classes are never
  graded.

## 6. Risks & Open Questions

- **R1 — the parse proxy.** A wrapped standalone parse cannot judge a fragment that is
  grammatical only in context; splice-in-context is the sub-count beside it, and the finding
  discloses the proxy's sharpness (the numbered-listing disclosure, `finding.md:68-74`).
  Note the direction of the sharpness: a body that fails the wrapped parse but parses in
  context moves at most the `NOT_PARSEABLE` members; the proxy is never decisive. **A second
  sharpness, fixed before the run:** the gate is sharp at indentation — a body written at
  column 0 fails the wrapped parse even though the text parses when indented. The spec fixes
  the class assignment (a body at the wrong indentation is a format-grammar violation →
  `MALFORMED`, never `NOT_PARSEABLE`), and the finding discloses it. The harness never
  dedents, never repairs.
- **R2 — one exposure.** No run has prompted under this format; the base meets it once. NO-GO
  says the necessary condition did not hold on first exposure; it proves nothing about yield
  under any contract, and the finding says so.
- **R3 — NO-GO is a result, not a failure.** The direction is then measured and spent, the
  pre-committed responses (raise *k*, CPU dtype) carry forward, and the unit ships instrument
  + finding only.
- **R4 — the format's boundary is deliberate.** Body-only replacement cannot express
  signature-changing fixes; one function per rollout cannot express multi-function fixes.
  These are format bounds, disclosed in the finding, not defects to repair.
- **R5 — a better base would change the answer.** The measurement is pinned to the § 10.10
  base; a base change is a further Type 1 amendment, never a silent re-run.
- **Open questions:** none that the spec does not settle — the exact prompt wording and marker
  grammar are fixed in `measurement-run/spec.md` before any rollout runs, per M2/M6.

## 7. Out of Scope

- **No amendment on NO-GO** — the contract aspect (§ 4.2) and the amendment (§ 4.3) are
  GO-gated; a NO-GO leaves `PREREGISTRATION.md` at § 10.16 and the standard generation path
  byte-identical.
- **No changes under `verify/` or `tasks/`** — ever, in this unit.
- **No yield claim, no success threshold, no loosened rule** — the rule is pre-committed and
  the finding may not revise it to rescue a NO-GO.
- **Raise *k*, the CPU dtype, the night re-mining before it draws** — the roadmap's other
  responses and gaps; named, not built.
- **Multi-function or signature-changing edits, class-level replacement, new-file creation** —
  out of the format's scope for the measurement (R4).

## 8. Dependencies & Sequencing

- Depends on: the pinned base being verified locally (`weights/`, § 10.10 revision
  `d1e3b690c8e225d7795bccddf971ca6be68b2012`); the two sealed documents (`tasks/stratum/easier.json`,
  `tasks/heldout/source-b.json`); the edit-contract machinery as the template (driver,
  runbook guards, instrument boundary).
- Sequence: `measurement-run` (always) → the finding's decision gates § 4.2 and § 4.3 →
  on GO: `whole-function-contract` then `amendment-10-x` (the amendment committed before any
  night records the new `edit_format`).
- The aspects table:

| aspect | ships on | depends on |
|---|---|---|
| `measurement-run` | always | — |
| `whole-function-contract` | GO only | GO from `measurement-run` |
| `amendment-10-x` | GO only | `whole-function-contract` |