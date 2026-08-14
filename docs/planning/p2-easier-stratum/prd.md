# PRD — p2-easier-stratum: the easier-stratum yield probe

**Unit:** `feat/p2-easier-stratum/aliz` · **Written:** 2026-08-14, in the worktree, from the
`whetstone-next` handoff brief (`docs/planning/p2-easier-stratum/card.md`) and the dig synthesis
(`docs/planning/p2-easier-stratum/understanding.md`).
**Decisions confirmed with the operator on 2026-08-14:** reference-fix-shape difficulty axis ·
hardened contract with the two trigger-eligible candidates · new committed report home
`reports/easier-stratum/` with a Type-2 amendment · select from the existing 66 (no re-mint) ·
slug `p2-easier-stratum`.

---

## 1. Problem statement

Two measurements — the baseline bake-off (`reports/baseline/`) and the measured format-hardening
arm (`reports/format-hardening/`) — show zero strict-PASS yields on the declared source-B set under
two generation contracts. The measured-arm finding (`docs/planning/p2-format-hardening/measured-arm/finding.md`
§ 5) applies the pre-committed fork rule M7 (`docs/planning/measured-arm-run/prd.md`): format
hardening is exhausted as a yield lever, and the next unit is **an easier task stratum or a larger
base** — never a fourth generation-contract change. The P2 premise under test is *training data
exists*: a strict-PASS yield > 0 (`docs/ROADMAP.md:398-407`). The fork's first arm, chosen by the
roadmap's own ordering ("Stratify by difficulty", `docs/ROADMAP.md:387-389, 405`), is this unit: it
moves the measurement down the difficulty axis and asks the question the earlier runs could not —
*can the bases fix these bugs when the bugs are smaller?*

The wall behind the formatting wall is fix quality: well-formed patches apply but do not solve
(`measured-arm/finding.md:83-91`). An easier stratum is the task-side test of that wall, and it is
the cheapest one that reaches the question: no new base, no new contract, no verifier change — a
selection rule over the corpus the project already holds.

## 2. Goals & success metrics

**Goal:** re-test the P2 premise (strict-PASS yield > 0, i.e. training data exists) on a
difficulty-stratified subset of the declared source-B set, under the hardened generation contract,
with the outcome published honestly either way.

**Metrics** (all produced by the STRICT verifier through the existing harness — never estimated):
- Per-candidate strict-PASS count on the stratum, over the stratum's denominator, in the new
  report home `reports/easier-stratum/`.
- Control INTACT on every (candidate, task) — a run with no proven control measures nothing.
- Reward-hacking count `N` (WEAK-PASS/STRICT-FAIL differential) as the harness already reports it.
- Retry-eligible conversion on the probe's own records, via the post-run pre-analysis extension.

**Decision rule — pre-committed here, before any rollout (mirroring M7):**
- **Yield > 0 for any candidate:** the P2 premise is supported on the easier stratum — training
  data exists; the next unit is P2's first slice (rollouts + expert iteration) on the stratum, and
  the difficulty axis becomes the corpus's stratification machinery (it is the natural input to the
  § 7.1 held-out-split difficulty distribution).
- **Yield == 0 for every candidate, with control intact:** the premise is refuted on the easier
  stratum; the larger-base arm is the named next response (`docs/ROADMAP.md:387-389`). Never a
  looser verifier; never a fourth generation-contract change.

This is a fork rule deciding the next unit, not a success threshold on a headline: a zero is a
publishable outcome (yield-probe PRD R9), and no bar is introduced anywhere
(`PREREGISTRATION.md:171-177`).

## 3. User personas & scenarios

The operator is the founder: a solo engineer running local bake-offs on Apple Silicon. The scenario
this unit serves is the fork decision — the operator runs the probe from the runbook, and the
finding tells them which fork arm the evidence supports, in words, with every figure living in its
one home. A second reader is any future contributor who must be able to re-derive the stratum's
membership from the committed rule and the corpus, and to see that the rule predates the run
(git history, like `PREREGISTRATION.md`).

## 4. Requirements

### Must-have

- **M1 — The difficulty rule exists as code, pre-committed.** A pure, deterministic, stdlib-only
  module computing a difficulty measure per task from the reference fix's shape: the gold patch
  derived from the donor at the parent commit (`provenance.commit`/`parent`, the same derivation
  the control arm already performs — `src/whetstone/bakeoff/control.py:195-256`,
  `sources.py:260-287`). The measure is fixed before any rollout and may never read a verdict,
  a rollout record, or a report figure (`PREREGISTRATION.md:171-177`; `selection.py`'s discipline).
  The module carries its own no-inference AST walk (no `mlx`, no `run.py`, no `scoring`) with an
  anti-vacuity control, following the diffcheck/retry/preanalysis pattern.
- **M2 — The stratum document is committed before the run.** Schema `whetstone-stratum/1`:
  rule digest (SHA of the rule module and its parameters), per-task difficulty values, the
  membership it produces, and the band that defines "easier" — all pre-committed in the unit,
  before any rollout, so git history proves ordering. A test re-runs the rule over the corpus
  manifests + pinned donor state and asserts membership equals the committed document — the
  "provably computable" proof, and the guard against rule drift. A degenerate stratum (empty, or
  identical to the whole declared set) is a usage error, never a vacuous pass
  (the empty-directory refusal discipline of `src/whetstone/tasks/manifest.py`).
- **M3 — Run-side inclusion filter.** `python -m whetstone.bakeoff.run` gains a stratum input
  (e.g. `--stratum PATH`): the run scores exactly the stratum's tasks from the loaded corpora.
  Unknown stratum ids are refused by name (mirroring `UnknownDevSubset`, `run.py:963-982`);
  an empty stratum is refused; source A's instances are still scored (both sources always
  published together, `PREREGISTRATION.md:142-143`); `--dev-subset` applies on top (declared dev
  ids are excluded from scoring and from denominators). The contract SHA and the `Conducted.scored`
  audit trail cover whatever subset is scored, automatically.
- **M4 — The probe runs the hardened contract, on the two trigger-eligible candidates.** The
  hardened contract is the current machinery: retries on (`--retries`, budget 2), the hardened
  contract's declared 5-id dev subset passed by name (the dev subset is part of the frozen
  contract's identity; re-freezing with a different subset would make it a different contract).
  The candidate exclusion rule is pre-committed here: **any candidate with a measured zero
  retry-eligible ceiling is excluded by name** — its wall is formatting, and no retry budget
  converts it; scoring it again would spend GPU on a measured-unconvertible candidate. The names
  are resolved before the run from the stored pre-analysis ceiling document (gitignored
  `runs/format-hardening-preanalysis/`) and recorded in the runbook — checkable, never invented
  at execution time. Writable paths absolute, workspace fresh, journal and transcript in the
  gitignored evidence directory (`TranscriptNotPrivate`, `run.py:939-960`).
- **M5 — Control discipline.** INTACT probes on every (candidate, task); `HarnessNotProven`
  aborts rather than grades (`sweep.py:41-47, 160-183`). The run's halt conditions are the
  hardened arm's: provisioning failure (uniform-across-candidates tell), `ContractChanged`,
  never-reuse-workspace.
- **M6 — The report home, by the door.** `reports/easier-stratum/` with the three-artifact shape
  (`report.md`, `report.json`, `cost.json`), rendered by the report door from the journal and the
  contract sidecar by identity — never hand-typed. Per-candidate yields on the stratum with the
  stratum's denominator, the contract fields (hardened: retry budget, retry template digest,
  diagnosis vocabulary version, retrieval oracle, dev subset), the non-comparability sentence, and
  a pointer to the gitignored breakdown home — never restating a classifier count.
- **M7 — The one-home guard moves on the changed-task-set argument.** The guard holds exactly six
  files in `reports/` (`tests/bakeoff/test_report.py:1353-1399`, opposite-sign twin
  `tests/bakeoff/test_transcript_locality.py:73-114`). The only recorded permission is the D6
  different-contract argument; this home rests on the changed-pinned-input ground instead — the
  task set is a pinned input (`PREREGISTRATION.md:131-138`), a figure over a different task set is
  a new series, and the probe's figures are non-comparable to both existing homes for that reason.
  The argument is written into **both** guard docstrings; a silent list extension remains refused
  (the permission is the argument, in the docstring). The new report's figures are asserted
  disjoint from all six existing artifacts (the adversarial disjointness guard, `test_report.py:1259-1281`).
  Tests watched failing first; the guard moves in the same commit as the argument.
- **M8 — The Type-2 amendment, committed before the run.** `PREREGISTRATION.md` gains § 10.5
  (append-only, log row, nothing above § 10 edited): the new home, its ground (same hardened
  contract, changed task set), the non-comparability declaration covering all three homes, and
  that the probe is a yield test — not the pinned baseline (`PREREGISTRATION.md:126-128`), not the
  held-out split (§ 7.1, open until P3). The amendment carries no number, and the existing
  `tests/test_docs.py` guards (no placeholders, no proportion, no figure) stay green.
- **M12 — Fixed ordering (the sequence is part of the design).** (1) The stratum rule, the
  stratum document, the run-side filter, and their tests land first. (2) Then, in ONE commit,
  test-first: the § 10.5 amendment, the one-home guard move with the changed-task-set argument in
  both docstrings, and the declaration-only `reports/easier-stratum/` (no count — the
  format-hardening declaration precedent). (3) Then the probe runs under the hardened contract.
  (4) Then the report door renders figures into the declared home, and the finding lands in the
  same commit as any correction it surfaces. The run never happens with an unguarded `reports/`
  tree; the guard never moves without its argument; the amendment never lands after the run it
  governs.
- **M9 — Post-run chain and finding.** attribution → autopsy → pre-analysis extension (covering
  the probe's autopsy documents) → comparison (trigger mapping asserted by identity, zero
  violations; an unproven control or missing decisions is a named refusal) → report door into
  `reports/easier-stratum/`. The finding states the fork decision (premise supported or refuted),
  per-candidate walls in words, applies the pre-committed decision rule, and names the next unit —
  written in the same commit as any correction it surfaces. No figure about a model appears
  anywhere but the report homes and the gitignored breakdown home.
- **M10 — Runbook, guarded like the measured arm's.** A new operator sheet for the probe with the
  same guard properties the measured-arm runbook is pinned to: absolute writable paths, every flag
  existing in the parser, exactly one worktree, primary-checkout CWD, no stale worktree names
  (`tests/test_runbook_guards.py` pattern — the existing module is hard-wired to the measured-arm
  runbook, so the guard is extended or parameterized, watched failing first).
- **M11 — The reward path stays frozen.** `src/whetstone/verify/`, `src/whetstone/bakeoff/patch.py`,
  `src/whetstone/bakeoff/attribution.py` remain byte-identical to `origin/master` (AC2 pins hold).
  No reward-path module gains an inference import; the difficulty rule and stratum filter are
  offline tooling with their own no-inference walks.
- **M13 — The write-up ships with the capability.** The `CHANGELOG.md` entry and the `CLAUDE.md`
  status-block update land in the same commit as the code they describe — the repo's own
  convention ("a capability is written up in the same commit that lands it") — and the probe's
  finding carries the axis-falsification check: if the yield is zero, the finding states in words
  whether the axis failed (the easiest stratum's tasks still require multi-file or cross-cutting
  reasoning — an observational claim grounded in the autopsy/attribution read) or the premise
  failed (the bases cannot fix these bugs at any difficulty), so a zero routes the correct arm
  next instead of always routing the larger base.

### Should-have

- **S1 — Which-zero read.** The finding attributes the probe's verdicts (attribution replay) so a
  zero is never a bare zero: applied-and-failed vs not-applied vs no-diff, per candidate, in words.
- **S2 — Ceiling measurement.** The pre-analysis extension measures the probe's own retry-eligible
  conversion, so the hardened machinery is measured on the new records rather than assumed.
- **S3 — Difficulty distribution note.** The finding describes the stratum's shape (sizes, bands)
  in words, as the first input to the § 7.1 difficulty distribution — a description, never a
  figure about a model.
- **S4 — Cost disclosure.** `cost.json` per candidate as the harness already emits.

### Nice-to-have

- **N1 — Schema-versioned stratum loader.** An old-schema stratum document fails decode rather
  than defaulting (the transcript codec discipline).
- **N2 — Re-mint runbook stub.** A named, documented next step — "extend the corpus with easier
  tasks" — referenced by the finding if the stratum proves too small, not executed by this unit.

## 5. Technical considerations

- **Core-loop element:** ② (nightly improvement loop) — this unit re-tests the loop's premise from
  the task side. Element ① (verifier) is untouched; the reward stays a pytest exit status; the
  verifier, `patch.py` and `attribution.py` stay byte-identical.
- **Placement in the pipeline:** tasks → rollouts → reward → gate → report. This unit sits at the
  corpus/task-selection stage and the measurement stage; no training, no reward change, no gate
  change.
- **Reward-hacking surface:** the reward is not touched. The new selection machinery is itself
  adversarial-tested: the rule's inputs are pinned to manifest fields + the donor's gold patch at
  the parent commit (operator-held, pre-run); a rule that read verdicts is impossible by
  construction (the module cannot import the run/scoring layers — AST walk asserted). The stratum
  filter cannot smuggle dev-subset ids into scoring — the `ScoredDevSubset` backstop still fires
  (`report.py:139-145, 502-514`).
- **Contracts:** manifest schema stays closed (no difficulty field added — the stratum document is
  the carrier). Generation contract: the hardened one, unchanged, frozen by `freeze` over the
  partition (dev ids excluded before freeze). The stratum is an inclusion filter applied where the
  partition happens (`run.py:540-543`), before the contract is frozen.
- **Locality:** everything runs on the Mac; donors, manifests, transcripts and journals stay local
  (gitignored roots `runs/`, `tasks/local/`, `_sandbox/`). No data or training leaves the box.
- **Determinism:** the rule is pure and deterministic; the probe is deterministic under pinned
  seeds (the harness's existing property); the report renders by identity from journals.
- **Effort:** est. one code week in the worktree (rule module + stratum document + run-side
  filter + guard move + amendment + runbook, all test-first), then an overnight-class probe run
  on Apple Silicon (two candidates, retries, 900s timeouts), then the post-run chain and finding.
  The suite stays green throughout; the one-home guard move is watched failing first.

## 6. Risks & open questions

- **"Manifest alone" interpretation.** The brief's "provably computable from the manifest alone"
  is interpreted, per the operator's decision, as *computable from the manifest's provenance plus
  the pinned donor state it names* — deterministic, offline, pre-run, and re-computable by anyone
  holding the machine-level corpus. A difficulty axis computable from the closed manifest's fields
  alone (f2p cardinality: 23 of 66 tasks have 1; pins 16/19/40; blobs 1-4) exists as the
  secondary/tie-break signal but is not the primary axis. Recorded here so the interpretation is
  not rediscovered mid-unit.
- **Stratum size is unknown until the rule runs.** The band is pre-committed; its membership falls
  out. A degenerate stratum is a usage error; a small stratum is a finding (the re-mint step is
  named), never a reason to widen the band after seeing the corpus — widening after the fact is
  post-hoc selection.
- **The axis itself is an assumption.** "Smaller correct fix ⇒ easier for a small model" is not
  measured by anything yet. If the yield is zero even on the easiest stratum, that could mean the
  axis failed (fix size does not correlate with what makes these tasks unsolvable) or the premise
  failed (the bases cannot fix these bugs at any difficulty); the two route different next arms.
  M13's falsification check (the finding must state which, on the autopsy/attribution read) is
  the pre-committed response; the control discipline proves the harness, never the axis.
- **The same-contract guard move.** The D6 argument (different contracts) does not cover a
  same-contract, different-task-set home; the changed-task-set argument is new and must be argued
  in both guard docstrings. Risk: a reviewer may dispute the ground; the PRD pre-commits it, and
  the fallback (labelled section in an existing home) is recorded but not preferred.
- **GPU cost.** Two candidates × stratum-size rollouts with retries (budget 2) and 900s timeouts
  is a real overnight-class run on Apple Silicon; the § 10 Apple Silicon capacity question
  (`docs/ROADMAP.md:595-596`) applies. Halt conditions and the pre-analysis ceiling check mitigate
  wasted spend.
- **The probe is not the baseline.** `reports/baseline/` and `reports/format-hardening/` artifacts
  are untouched; the probe is a yield test over a changed pinned input and is declared
  non-comparable. The pinned baseline stands unmeasured, and § 7.3 stays open — nothing in this
  unit may close it.

## 7. Out of scope

- No re-minting of easier tasks (select from the 66; re-mint is a named next step).
- No larger-base arm (the named next response if the premise is refuted, not this unit).
- No P2 loop build — rollouts + expert iteration is the unit this unit's decision unlocks.
- No verifier change; no generation-contract change (a fourth one is forbidden by name); no
  success threshold anywhere.
- No held-out split (P3, § 7.1).
- No difficulty field in the manifest (closed schema).
- No edits to `reports/baseline/` or `reports/format-hardening/` artifacts, and no figure about a
  model outside the report homes and the gitignored breakdown home.
