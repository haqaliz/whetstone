# Spec — `probe-run` (aspect 4 of `p2-easier-stratum`)

**Boundary:** the probe runbook + its guards + the operator's execution + the post-run chain +
the finding. Nothing here computes difficulty (aspect 1), filters the run (aspect 2), or owns a
report home (aspect 3). The aspect's code is the runbook and its guard tests; the probe itself
is operator-executed on GPU (the `measured-arm-run` precedent), and the finding plus the
post-run chain are its deliverables.

## Problem slice

The fork decision needs a measurement: a strict-PASS yield on an easier stratum, under the
hardened contract, with control intact. Everything the measurement consumes exists — the run
surface (`build_parser`, `run.py:691-839`) with the hardened switches (`--retries` 828-837,
`--dev-subset` 773-781, `--only` 794-804) and, from aspect 2, the stratum filter; the control
discipline enforced by the harness itself (`rankable` raises `HarnessNotProven`,
`sweep.py:41-47, 160-183`; `harness_status`, `control.py:472-494`); the post-run chain
exercised once already (`measured-arm/runbook.md:157-236`). What does not exist: the operator's
sheet for a stratum probe, a guard over it (`test_runbook_guards.py:39` hard-wires the
measured-arm runbook), the resolution of which candidates to score, and the finding that
applies the pre-committed decision rule (`prd.md:44-55`).

## Decisions (code-grounded)

- **A1 — The guard is extended, not parameterized: a sibling module importing the parse
  helpers by identity.** New `tests/test_probe_runbook_guards.py`; `tests/test_runbook_guards.py`
  is left untouched. Grounds: the helpers are already text-parameterized — every one takes the
  runbook text or its parsed blocks as its argument (`test_runbook_guards.py:47-53, 56-110`);
  only `RUNBOOK` (:39) and `STALE_WORKTREES` (:41) are globals, which is exactly what a second
  module re-binds. The existing module is a frozen historical pin whose docstring narrates the
  relative-workspace defect it caught (:1-29, :154-172) and which is referenced by the finding
  as the correction that landed test-first (`measured-arm/finding.md:40-45`) — a parameterized
  rewrite would rewrite the pin that already paid for itself. One parse implementation, shared
  by import, matches the repo's identity discipline (`diffcheck` imports
  `classify_completion` by identity; the comparison re-derives the trigger mapping by identity,
  `comparison.py:548-557`). Watched failing first.
- **A2 — Candidate resolution is a runbook block, never a code surface.** The exclusion rule
  is pre-committed in the PRD (`prd.md:93-103`: any candidate with a measured zero
  retry-eligible ceiling is excluded by name); the names are resolved **before the run** from
  the stored pre-analysis ceiling document (`runs/format-hardening-preanalysis/ceiling.json`,
  gitignored) and recorded in the runbook's opening block — checkable, never invented at
  execution time. The arm command expresses the retained pair as two `--only` flags
  (`run.py:794-804`; a name matching nothing or several is refused, `UnknownCandidate`,
  `run.py:400-404`). A new guard property ties the sheet to the rule: every `--only` value is a
  name the resolution block records, and the excluded candidate is named in the resolution
  block and in no `--only` value.
- **A3 — Halt conditions are the hardened arm's, restated for this run (PRD M5).** Uniform
  provisioning/checkout failure is a harness defect — every candidate fails identically, the
  control arm proves nothing, `HarnessNotProven` aborts rather than grades (`sweep.py:41-47,
  160-183`). A retry prompt the frozen contract does not carry raises `ContractChanged` through
  the seal and voids the run, no recovery (`freeze`, `run.py:410-465`). A workspace is never
  reused. The candidate-exclusion check happens before the run, in the runbook.
- **A4 — Evidence layout mirrors the measured arm, all paths absolute.** `--out`
  `runs/easier-stratum/`, evidence in the sibling gitignored root
  `runs/easier-stratum-evidence/` (`TranscriptNotPrivate`, `run.py:939-960` — the harness
  refuses a transcript inside `--out`), workspace `runs/easier-stratum-workspace`; every
  writable path absolute, because the workspace is built as `workspace / …` and provisioned by
  subprocesses whose CWD is not the run's (`run.py:546`, `_workspace` `run.py:1040-1043`) — the
  relative-path death of 2026-08-12 (`measured-arm/finding.md:31-45`).
- **A5 — Post-run chain per PRD M9, with the stored runs' numbers kept in their own home.**
  attribution → autopsy → pre-analysis extension over **all four** autopsy documents (the
  extension is mandatory: the comparison refuses a run without declared decisions by name,
  `comparison.py:548-557`) → comparison over **the probe's** journal + autopsy + the extended
  document (INTACT refusal, `comparison.py:536-544`) → report door into `reports/easier-stratum/`
  (`comparison.py:1093-1146`). The comparison's run set is the probe's alone, so the stored
  runs' classifier counts keep their single home; the extended document's combined ceiling is a
  different measurement over a different record set than the halt-check ceiling, never fused
  (the `ceiling-with-arm` precedent, `measured-arm/runbook.md:227-228`).
- **A6 — The finding applies the pre-committed fork rule and carries the M13 check.**
  Yield > 0 for any candidate → premise supported, P2's first slice next on the stratum; yield
  == 0 with control intact → premise refuted, larger-base arm next (`prd.md:44-55`). If zero,
  the finding states in words whether the axis failed (the easiest stratum's tasks still demand
  multi-file or cross-cutting reasoning — an observational claim grounded in the
  autopsy/attribution read) or the premise failed (`prd.md:155-162`), so a zero routes the
  correct arm instead of always routing the larger base.

## In-scope requirements

- `docs/planning/p2-easier-stratum/probe-run/runbook.md` — the operator's sheet: the
  resolution block (candidate names, the ceiling facts they were resolved on, the exclusion
  rule), the arm command (hardened contract: `--retries`, the five declared dev ids, the
  stratum document, `--only` × 2; CWD at the primary checkout), workspace and evidence rules,
  halt conditions, killed-run restart, expected artifacts, post-run chain commands.
- `tests/test_probe_runbook_guards.py` — the guard module (A1) pinning the same properties the
  measured-arm module pins — writable paths absolute (:154-172), every arm flag in
  `build_parser()` (:175-194), every `uv run --project` target worktree-shaped (:197-215),
  exactly one worktree named everywhere (:218-246), arm CWD at the primary checkout (:249-266),
  no stale worktree names anywhere (:269-282) — plus the A2 candidate-resolution property.
- The post-run chain and the finding per A5/A6; the probe itself is operator-executed.

## Acceptance criteria (tests written first)

1. `uv run pytest tests/test_probe_runbook_guards.py tests/test_runbook_guards.py` green, and
   the new module's RED pass is watched first — the guard written against a deliberately wrong
   stub runbook (relative writable paths, no `--stratum`, a stale worktree name) must fail
   before the real runbook exists (`CONTRIBUTING.md:56-60`).
2. The guard properties hold for the new runbook: `--out`/`--workspace`/`--journal`/
   `--transcript` absolute; every flag the arm block passes exists in `build_parser()` with the
   parser-side pins `--stratum`, `--retries`, `--only` present; every `uv run --project` target
   a `.claude/worktrees/<name>` path; exactly one worktree name across the arm CWD line and all
   post-run targets; the arm CWD line names the primary checkout; the stale names
   (`feat-measured-arm-run`, `feat-p2-format-hardening`, `feat-format-hardening-measurement`)
   appear nowhere in the file.
3. The candidate-resolution rule is guarded: the runbook's resolution block names the retained
   pair and the excluded candidate with its zero-ceiling fact; the arm block's `--only` values
   equal the retained pair; the excluded name appears in no `--only` value.
4. Halt conditions are stated in the runbook: uniform provisioning failure (harness defect —
   stop, fix, restart from the empty workspace), `ContractChanged` (run void, no recovery),
   never-reuse-workspace; the killed-run restart procedure names quarantine-by-name, never
   deletion.
5. The post-run chain's refusals are the instruments' own, named in the runbook: the
   comparison refuses a run with no `INTACT` probe (`comparison.py:536-544`) or no declared
   decisions (`comparison.py:548-557`) — exit 2, nothing written; autopsy and pre-analysis
   refuse a published `--out` (`autopsy.py:851-855`, `preanalysis.py:467-472`); attribution
   refuses a missing transcript (`attribution.py:465-473`).
6. The finding applies the decision rule (yield > 0 → premise supported, P2 loop next on the
   stratum; yield == 0 with control intact → premise refuted, larger-base arm next), carries
   the M13 axis-falsification check stated in words on the autopsy/attribution read, and
   contains no figure about a model — those live only in `reports/easier-stratum/` and the
   gitignored breakdown home.

## Out of scope

- The difficulty rule, the stratum document, and the run-side filter — aspects 1–2.
- The one-home guard move, the § 10.5 amendment, and the declaration-only
  `reports/easier-stratum/` — aspect 3.
- The GPU run itself is operator-executed; its acceptance is the evidence directory, the
  rendered report, and the finding.
- Any change to `src/whetstone/verify/`, `patch.py`, `attribution.py` (the AC2 pins hold); no
  report path renders anything the harness did not produce; no fourth generation-contract
  change, ever (`prd.md:44-55`).

## Open questions / risks

- **The stratum document's path and membership are aspect 2's.** The runbook's `--stratum`
  path is written against the landed artifact and verified at write time; the guard is
  structural and never existence-checks a path. A degenerate or tiny stratum is a usage error
  or a finding, never a widened band (`prd.md:218-221`).
- **GPU cost is overnight-class and unmeasured for this matrix** — two candidates, retries
  (budget 2, `retry.py:63`), 900 s timeouts. Stated as unknown, plan for a night
  (`prd.md:232-235`); the excluded candidate's share is not spent.
- **The axis assumption.** A zero on the easiest stratum could mean the axis failed or the
  premise failed; the two route different next arms. M13's check is the pre-committed response,
  and the control discipline proves the harness, never the axis (`prd.md:222-227`).
- **The `--only` names must not collide as substrings.** The two retained repo ids share no
  name-prefix (`run.py:396` matches by containment); the runbook uses the full ids, and the
  guard pins the resolution block's names to the `--only` values.
