# Understanding — p2-easier-stratum (dig synthesis)

**Written:** 2026-08-14, in the `feat/p2-easier-stratum/aliz` worktree, after three parallel
dig agents (corpus/manifest surface, bake-off run surface, honesty-constraint surface).
**Source:** `docs/planning/p2-easier-stratum/card.md` (the `whetstone-next` handoff brief).

> **Artifacts live here rather than in `docs/planning/_card/`** following the precedent set by
> `docs/planning/p2-diff-autopsy/card.md:14-21`: the `_card` path is the measured-arm-run unit's
> live-cited home (`docs/planning/measured-arm-run/prd.md:4`) and is not a safe place for this
> unit's documents.

## 1. What the work is really asking

The measured-arm finding pre-committed the fork (`docs/planning/p2-format-hardening/measured-arm/finding.md`
§ 5, applying rule M7 from `docs/planning/measured-arm-run/prd.md`): format hardening is exhausted as a
yield lever, and the next unit is **an easier task stratum or a larger base** — never a fourth
generation-contract change. The P2 premise under test is *training data exists*: a strict-PASS yield
> 0 on the declared source-B set (`docs/ROADMAP.md:398-407`). Measured twice (baseline bake-off, hardened
arm), the yield is zero; the wall behind formatting is fix quality. This unit re-tests the premise from
the task side: define difficulty **a priori**, restrict the probe to an easier stratum, and measure the
yield there. The verdict is a yield test, not a headline: zero is a publishable outcome (yield-probe
PRD R9), and the larger-base arm is the named next response if the premise is refuted again.

## 2. What the dig established (grounded)

- **No difficulty concept exists anywhere** — code or docs. Grep across `src/`, `tests/`,
  `docs/planning/` finds only the fork sentence restated (`docs/ROADMAP.md:388-389, 405`;
  `src/whetstone/bakeoff/selection.py:40-44`). The axis must be invented a priori by this unit,
  in code, before any rollout, and it may never be verdict-derived (`PREREGISTRATION.md:171-177`;
  `selection.py:1-25`).
- **Manifest signals are fixed at mint time and predate every rollout** — the only per-task data
  that is both discriminating and not outcome-derived. Census of all 66 source-B manifests
  (`tasks/local/`, gitignored, in the primary): `fail_to_pass` cardinality `{1: 23, 2: 16, 3: 7,
  4: 3, 5: 6, 6: 4, 8: 4, 10: 2, 15: 1}`; `pass_to_pass` 0 (2 tasks) to 227; `test_blobs`
  `{1: 38, 2: 23, 3: 3, 4: 2}`; `environment.pins` `{16: 8, 19: 37, 40: 21}` (belay 40, contig
  16/19); `import_roots` exactly 1 in all 66; donors split belay 21 / contig 45 (21 belay
  manifests carry the `tests/conftest.py` floor blob, contig none). Manifest schema is **closed**
  (`src/whetstone/verify/task.py:77-90`): a new per-task field is a contract change; `provenance`
  is the only free-form slot (str→str).
- **The reference (gold) patch is not stored** in source-B manifests, recipes, or the ledger.
  It is deterministically re-derivable from the donor at `provenance.commit`/`parent` —
  `src/whetstone/bakeoff/sources.py:260-287` already does this for the control arm
  (`control.py:195-256`), and the bake-off's oracle retrieval already reads the reference patch's
  non-test files. So a reference-fix-shape difficulty axis (hunks/files/lines) is computable
  offline and a priori, but requires the donor repo (machine-level, at the manifest's `repo_url`),
  which the brief's "provably computable from the manifest alone" does not strictly permit.
- **No inclusion filter exists on the run side.** The run surface
  (`python -m whetstone.bakeoff.run`, `run.py:691-886`) restricts tasks by whole-directory
  `--tasks`, positional `--probe N`, and `--dev-subset` (exclusion-only, unknown-id-refused
  `UnknownDevSubset`, `run.py:963-982`). A stratum inclusion filter is new; the contract SHA and
  `Conducted.scored` audit trail automatically cover whatever subset is scored (`run.py:410-465`).
- **The one-home guard is the binding constraint.** `reports/` must hold **exactly** six files
  (`tests/bakeoff/test_report.py:1353-1399`; opposite-sign twin
  `tests/bakeoff/test_transcript_locality.py:73-114`). The only recorded permission to move the
  guard is the D6 argument — different generation contracts (`yield-probe prd.md:106-112`).
  A stratum report under the **same** contract over a **changed task set** needs a new argument
  (the changed-pinned-input ground, `PREREGISTRATION.md:131-138`), written into both guard
  docstrings, and the § 10.4 precedent pairs a new committed home with a Type-2 amendment
  (append-only; nothing above § 10 edited; log row). This is **genuinely undecided in the docs**
  — the unit must decide and pre-commit it.
- **Both sources always publish together** (`PREREGISTRATION.md:142-143`): the probe run scores
  source A's 1 instance as well as the source-B stratum. Dev-subset mechanics (exclusion from
  both sources pre-freeze, `UnknownDevSubset`, `ScoredDevSubset` backstop) are proven
  (`tests/bakeoff/test_dev_subset_mechanism.py`).
- **AC2 pins**: `src/whetstone/verify/`, `src/whetstone/bakeoff/patch.py`,
  `src/whetstone/bakeoff/attribution.py` byte-identical to `origin/master` — the reward is not
  touched by this unit; the brief restates the pin.
- **test_runbook_guards.py is hard-wired to the measured-arm runbook** (`test_runbook_guards.py:39`).
  A stratum probe's operator sheet is a new runbook, not covered by the existing guard.

## 3. Contradictions and open questions surfaced by the dig

1. **"Manifest alone" vs. reference-fix shape.** The brief demands membership "provably computable
   from the manifest alone"; the strongest a priori difficulty signal (size of the correct fix) is
   derived from the donor at the parent commit, not from the manifest. Tension between strictness of
   the guarantee and quality of the axis — **resolved 2026-08-14 by the operator: reference-fix
   shape is the primary axis**, read as "manifest provenance + the pinned donor state it names".
2. **Which contract the probe runs under.** The hardened contract (retries, `--retries` off by
   default, budget 2) is the current machinery and its preanalysis ceiling is measured; the baseline
   contract is the published shape with three candidates. The choice decides what the stratum report
   may claim about comparability (the D6 ground applies only if the contracts differ). **Resolved:
   the hardened contract, with the two trigger-eligible candidates** (the loop-collapse candidate
   excluded by name on its measured zero retry-eligible ceiling).
3. **Stratum membership rule and size.** e.g. `fail_to_pass == 1` selects 23 of 66. One signal or a
   pre-committed rule combining several (pins, blobs, f2p)? Select from the 66, or re-mint easier
   tasks (the brief says "select or re-mint"; re-minting grows the corpus beyond the declared 66 and
   changes the status claim). **Resolved: select from the 66; re-mint is a named next step, not this
   unit.**
4. **Report home and amendment.** New committed home `reports/easier-stratum/` + guard move on the
   changed-task-set argument + Type-2 amendment (§ 10.5), vs. the R-f fallback (labelled section in
   an existing home), vs. gitignored-only probe evidence. **Resolved: new home + amendment, with the
   fixed ordering in PRD M12 (amendment + guard move + declaration land together before the run).**
5. **Decision rule must be pre-committed, mirroring M7.** Yield > 0 → premise supported (P2 proceeds
   with the loop's first slice on the easy stratum); yield == 0 → premise refuted (larger-base arm is
   the named next response). A pre-committed fork rule, never a success threshold
   (`PREREGISTRATION.md:171-177`).
6. **The axis itself is an assumption.** "Smaller correct fix ⇒ easier for a small model" is not
   measured by anything yet; a zero on the easiest stratum could mean the axis failed or the premise
   failed, and the two route different next arms. PRD M13's falsification check (the finding must
   state which, on the autopsy/attribution read) is the pre-committed response.

## 4. Placement on the core loop and guardrail check

- **Core loop element ② (nightly improvement loop)** — this unit re-tests the loop's premise
  (training data exists) from the task side. Element ① (verifier) is **untouched**: the reward stays
  a pytest exit status; `verify/`, `patch.py`, `attribution.py` stay byte-identical; no reward-path
  module gains an inference import. The gate (③) and report (④) are untouched; `UNVERIFIED` semantics
  unchanged.
- **Guardrails**: no verifier loosening (roadmap forbids by name); no LLM judge anywhere; no data or
  training leaves the box (donors and evidence stay local; the stratum is computed from the local
  corpus); nothing a better base would make redundant (a stratum + difficulty axis is a durable
  corpus asset); one task family (source-B python repo bug-fixing, difficulty varies only).
- **Demand**: internal — the fork is the roadmap's own pre-committed next unit, chosen on measured
  evidence.

## 5. Affected areas (once built)

- New: `src/whetstone/tasks/` or `src/whetstone/bakeoff/` — a difficulty axis module (a priori
  rule, pure, deterministic, no inference) + a stratum selector producing a declared membership
  document; a run-side inclusion filter (new flag consuming the stratum document, refusal for
  unknown ids mirroring `UnknownDevSubset`).
- Tests: the stratum rule's membership (computable, manifest-grounded), the run-side filter
  (inclusion + refusal + report denominators), the one-home guard extension (both docstrings'
  arguments), the runbook guard for a new runbook, amendment/pin guards.
- Docs: `docs/planning/p2-easier-stratum/` (prd, spec, plan, runbook, finding), a Type-2 amendment
  (§ 10.5) if a new committed report home lands, the report door or a new renderer, and
  `CHANGELOG.md`.
- Evidence: gitignored `runs/` (probe journal/transcript/attribution/autopsy/preanalysis/comparison)
  — the only home of classifier/ceiling counts.
