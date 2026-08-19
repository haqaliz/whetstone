# PRD — larger-base-arm

**Written:** 2026-08-15. **Source:** inline brief (`docs/planning/_card/issue.md`), handed off
by the `whetstone-next` session; built on the fork rule pre-committed by the easier-stratum
unit (`docs/planning/p2-easier-stratum/prd.md:44-55`) and the probe's finding
(`docs/planning/p2-easier-stratum/probe-run/finding.md`).

## Problem Statement

The fork's first arm — the easier-stratum probe — ran and published (merged 2026-08-15,
PR #13): **yield == 0 for every candidate, with control intact**, on the pre-committed
stratum under the hardened contract. The pre-committed decision rule
(`p2-easier-stratum/prd.md:49-51`) therefore fires: the premise is refuted on the easier
stratum and **the larger-base arm is the named next response** — never a looser verifier,
never a fourth generation-contract change. The probe's M13 read (`probe-run/finding.md:34-53`)
is decisive for this arm's design: **premise failure, not axis failure** — the formatting
wall receded, well-formed patches applied, and none turned the tests green ("git read it,
applied it, and the tests still fail"). The axis is not the binding constraint, so the
response is a larger base on the **declared source-B set** — the pivot signal's own set
(`docs/ROADMAP.md:387-389`) — not an even-easier stratum.

The arm is a measurement: it re-tests the P2 premise (strict-PASS training data exists) when
the base is one rung larger, through the same harness, and its finding routes the next unit.
Nothing about it changes the reward, the gate semantics, or the generation contract.

## Goals & Success Metrics

**Goal:** measure the strict-PASS yield of a 32B-class open coder base on the declared
source-B set under the hardened contract, with the outcome published honestly either way,
and apply the pre-committed fork rule in the finding.

**Metrics** (all produced by the STRICT verifier through the existing harness — never
estimated):

- Per-candidate strict-PASS count on the declared set, over the harness's own denominator, in
  the new report home `reports/larger-base/`.
- Control INTACT on every (candidate, task) — a run with no proven control measures nothing.
- Reward-hacking count `N` (WEAK-PASS/STRICT-FAIL differential) as the harness already
  reports it.
- The 32B's retry-eligible conversion on its own records, via the post-run pre-analysis
  extension.
- A `--probe` timing/capacity pass (D7) on the 32B before the full arm commits a night.

**Decision rule — pre-committed here, before any rollout (mirroring M7/M13):**

- **Yield > 0:** the P2 premise is supported at a larger base — training data exists; the
  next unit is P2's first slice (rollouts + expert iteration), and the finding names the 32B
  as the first candidate with evidence. Base *selection* is not made here: § 7.3 closes only
  by a Type 1 amendment committed **before** the measurement it governs runs
  (`PREREGISTRATION.md:261-276`), which is P3's baseline — the finding names the evidence and
  routes that closure, it does not perform it.
- **Yield == 0, with control intact:** the premise is refuted at the larger base too — both
  of the roadmap's named responses are then exhausted (an easier stratum, a larger base;
  `docs/ROADMAP.md:387-389`). The finding states that in words, with the M13-style check
  (premise vs. axis) on the autopsy/attribution read. **The next unit is pre-committed
  here, before any rollout: raise *k*** (`docs/ROADMAP.md:405-406` — the P2 pivot's other
  named response, never run) — **never** a looser verifier and **never** a fourth
  generation-contract change. The task-family re-scope is flagged in the finding as the
  alternative fork, for the operator's decision at the next unit's review gate; the finding
  does not choose it after seeing the zero.
- **Probe failure (capacity/timing):** the 32B does not fit or cannot sustain the run on
  this machine — the capacity bound is published as a finding, never worked around
  (`report.py:1184-1186`; `docs/ROADMAP.md:594-596`); the finding names capacity as the
  blocker and the next unit re-picks the candidate.

This is a fork rule deciding the next unit, not a success threshold on a headline: a zero is
a publishable outcome, and no bar is introduced anywhere (`PREREGISTRATION.md:171-177`).

## Personas & Scenarios

The operator (aliz): runs the probe pass and the arm from the runbook tonight, on the primary
checkout with the branch code via this unit's worktree; wakes up to the finding that decides
the roadmap's next unit. A later agent: executes the post-run chain commands verbatim,
offline and deterministic, read-only against the primary's gitignored runs.

## Requirements

**Must-have (code phase — Phase 6, test-first):**

1. **The runbook and its guard, on the unit's worktree.** The probe sheet
   (`docs/planning/p2-easier-stratum/probe-run/runbook.md`) becomes a frozen historical pin
   (the measured-arm precedent); this unit writes a **new** sheet at
   `docs/planning/larger-base-arm/runbook.md` — content differs materially from the probe's:
   no `--stratum`, the dev overlay restored, one new candidate, a mandatory probe pass — and
   a new guard module `tests/test_larger_base_runbook_guards.py` that imports the parse
   helpers from `tests/test_probe_runbook_guards.py` **by identity** (asserted `is`; the
   pinned module byte-untouched), with `feat-stratum-probe-execution` joining
   `STALE_WORKTREES`. **RED watched first** (the new guard against the probe sheet as it
   exists, naming the dead worktree — `CONTRIBUTING.md:56-60`), GREEN after the new sheet.
2. **The candidate resolution (A2) pre-committed in the runbook.** The arm scores
   `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` — the next rung on the measured family
   (3B/7B/14B all measured; verified present on Hugging Face 2026-08-15, MLX 4-bit, 18.4 GB,
   apache-2.0) — as exactly one `--only` value. The 7B stays **excluded by name** under the
   zero-ceiling rule (`p2-easier-stratum/prd.md:97-99`): it has a measured ceiling of zero,
   and the rule applies to any candidate with one; the 32B has no measured ceiling, so the
   rule does not apply to it. The resolution block states the retained/excluded reasoning;
   every `--only` value is a name the block records, the excluded name appears in no `--only`
   value.
3. **The probe pass (D7) precedes the arm, with a pre-committed decision rule.** The
   runbook opens with the timing/capacity pass: `--probe` on the 32B (`run.py:959-1006` —
   time and publish what they cost, publish no counts) **on the runbook's declared sample of
   N tasks** before the full arm commits a night. The runbook states N and the criterion:
   the arm proceeds iff the probe completes on all N sampled tasks **and** the probe's
   published peak bytes leave the headroom the runbook states below the machine's RAM; a
   probe that fails or exceeds it fires the capacity finding and the arm does not run. The
   36 GiB machine vs 18.4 GB weights is the ROADMAP § 10 open question, settled by
   measurement. The weights fetch itself is a "before you run" step: the 32B is fetched into
   the primary's `weights/` and recorded in `provenance.json` (immutable revision, re-hashed
   before a token is generated) — human-run, the one declared network exception
   (`docs/ROADMAP.md:574-576`).
4. **The arm command is the hardened contract on the declared set.** `--retries` (budget 2,
   the § 10.4 contract — never a fourth change), **no** `--stratum` (the full declared
   source-B set), the **five declared dev ids restored** as `--dev-subset` (non-vacuous on
   the full set — the probe's none-declared state was stratum-scoped; each id must match a
   loaded task or the run is refused), `--only` exactly once, absolute writable paths,
   workspace fresh and empty, CWD at the primary checkout, journal and transcript in a
   sibling gitignored evidence directory (never under `--out` — `TranscriptNotPrivate`),
   `--recorded-on` declared at run time. Denominator: 61 private (66 − 5 dev) + 1 public = 62
   per candidate; source A always scored in full, both sources publishing together.
5. **The post-run chain, extended to five autopsy documents.** attribution → autopsy → the
   **mandatory** pre-analysis extension over **all five** autopsy documents (arm-a,
   budget-2048, format-hardening-arm-evidence, easier-stratum-evidence, larger-base-evidence)
   → the comparison (INTACT control required, exit 2 otherwise) → the new report door mode.
6. **The report home, by the door.** `reports/larger-base/` with the three-artifact shape
   (report.md / report.json / cost.json, schema `whetstone-larger-base-report/1`), rendered
   by `report.build_larger_base_report` / `write_larger_base_report` — deterministic and
   pure, reusing `_row`, `_over`, `tally`, `_contract_fields`, `_contract_block`, `_counts`
   **by identity** — and by the report door's third mode `--render-larger-base-report` in
   `comparison.py` (exactly one arm group, `build_contract_arms` reused unchanged, the
   stratum-mode shape of refusals, `--render-report` and `--render-stratum-report` untouched,
   the modes mutually exclusive). The committed artifacts are the declaration — no count, no
   contract fields, "**No count is measured here: the arm has not run.**" — generated by the
   writer, never hand-typed.
7. **The one-home guard admits the third home on the changed-candidate-set argument.**
   Model revision is one of the five pinned inputs (`PREREGISTRATION.md:131-132`), so the
   arm's figures are a new series, declared non-comparable to all existing homes — a third
   admission ground (D6: different contract; § 10.5: changed task set; now: changed candidate
   set) in **both** docstring twins (`tests/bakeoff/test_report.py` and
   `tests/bakeoff/test_transcript_locality.py`), the artifact list extended to twelve, the
   planted-overlap control proved able to fail, a silent list extension refused.
8. **`PREREGISTRATION.md` § 10.6** (Type 2, dated 2026-08-15): discloses the arm — the same
   hardened contract and the same declared task set under a changed pinned input (model
   revision), a new series declared non-comparable to all three existing homes,
   `reports/larger-base/` the only home of its figures, what the arm is not (not the pinned
   baseline of § 3, not the held-out split of § 7.1, not a base-selection closure — it
   produces evidence only). With its row in the amendment log; nothing above § 10 edited, no
   placeholder, no proportion in any spelling (`tests/test_docs.py`).
9. **Nothing under the reward path moves.** `src/whetstone/verify/`, `patch.py` and
   `attribution.py` byte-identical to `origin/master` (AC2 pins); `run.py`'s surface is
   unchanged (the arm needs no new flag); the existing report homes' artifacts are static and
   are not regenerated.

**Must-have (operator phases — executed, not built):**

10. The probe pass runs, then the arm runs verbatim (hardened contract, declared set, dev
    overlay, one candidate, absolute writable paths, `--recorded-on` declared at run time).
11. The post-run chain runs verbatim: attribution → autopsy → the mandatory pre-analysis
    extension over all five autopsy documents → comparison → the larger-base report door.
12. The finding applies the fork rule above with the M13-style check in words (premise vs.
    axis on the autopsy/attribution read), states the capacity outcome (the probe's
    cost record), and the rendered report lands in `reports/larger-base/` before the unit
    merges. No figure about a model appears anywhere outside the report home and the
    gitignored breakdown home.
13. `CLAUDE.md`'s status block is refreshed to the post-probe state plus this unit, in the
    landing commit (it currently ends at "Phase 1 of probe-run"; the file's own rule: a
    capability is written up in the same commit that ships it).

## Acceptance Criteria (tests written first, `CONTRIBUTING.md:56-60`)

1. `uv run pytest tests/test_larger_base_runbook_guards.py` — **RED** against the probe
   sheet as it exists at the start of the code phase (naming `feat-stratum-probe-execution`,
   which has joined `STALE_WORKTREES`), watched not assumed; **GREEN** after the new runbook.
2. The guard pins the seven properties (absolute writable paths, every arm flag in
   `build_parser`, worktree-shaped `--project` targets, exactly one worktree everywhere, arm
   CWD at the primary, no stale name anywhere, anti-vacuity parse) **plus** the A2
   resolution rule (the 32B retained and named in the resolution block, the 7B excluded and
   in no `--only` value), the probe-pass-first property (the probe command appears before the
   arm command), the restored dev overlay (every declared id matches a loaded task), and the
   five-autopsy pre-analysis step.
3. `uv run pytest tests/test_probe_runbook_guards.py` and `tests/test_runbook_guards.py` are
   unchanged-GREEN (both pinned modules byte-untouched).
4. `uv run pytest tests/bakeoff/test_report.py tests/bakeoff/test_transcript_locality.py`
   pass with the twelve-artifact list and the third admission ground in both docstrings; the
   planted-overlap control (a deliberately added artifact under `reports/`) fails the guard.
5. `uv run pytest tests/test_docs.py` — § 10.6 present, dated, no placeholder, no proportion
   in any spelling; the amendment log row present.
6. `uv run pytest tests/bakeoff/test_report.py::test_…pins` and the AC2 pin tests — the
   reward path byte-identical to `origin/master`; a planted edit to `verify/`, `patch.py` or
   `attribution.py` fails them.
7. `uv run ruff check .` and `uv run mypy src/` exit 0; the full suite green.
8. The new report door mode's surface is pinned by its own tests, in the stratum mode's
   shape: exactly one arm group (zero and two refused by name), `--breakdown-home` and
   `--recorded-on` required, mutual exclusion with `--render-report` and
   `--render-stratum-report`, the declaration-not-re-rendered refusal.
9. The runbook's commands are executable from disk: `uv run --project
   <worktree> python -m whetstone.bakeoff.run --help` and the same for attribution, autopsy,
   preanalysis, comparison (the new door mode in `--help`).
10. Operator phases (checked the same way, not tests): the post-run chain's refusals are the
    instruments' own and none fires — zero mapping violations, zero `unrecognised-shape`,
    `INTACT` control present, pre-analysis extension over all five autopsy documents — and
    the report door renders `reports/larger-base/` with counts, contract fields, and the
    non-comparability sentence.

## Technical Considerations

- **Core-loop element:** ② nightly improvement loop — the arm measures whether training data
  exists at a larger base; it is the premise test for P2, not a training run.
- **Reward untouched:** no change to the STRICT/WEAK verifiers, the executed-node-id
  assertion, the provenance boundary, or `N`. The arm is graded through the existing harness
  with the control discipline enforced by the harness itself (`sweep.py:41-47, 160-183`). No
  judge, no policy is generated here.
- **Gate semantics untouched:** `UNVERIFIED` stays above `PASS`; the arm publishes verdict
  counts, never a promotion.
- **Contract untouched:** the hardened contract of § 10.4 (retries, budget 2, same templates,
  retrieval oracle) is the arm's contract by elimination — the pre-committed rule forbids a
  fourth change. The dev overlay is the § 10.4 overlay restored (the probe's none-declared
  state was stratum-scoped; on the declared set the five ids are members).
- **Locality:** the run reaches the machine-level stores by absolute path only — the
  primary's `tasks/local/`, `weights/`, `runs/` — never by copying them into the worktree
  (whetstone-worktrees discipline). The weights fetch for the 32B is human-run in the primary
  checkout (the one declared network exception, `docs/ROADMAP.md:574-576`); `provenance.json`
  records the immutable revision and every file is re-hashed before a token is generated.
- **Merge timing:** per the M12 ordering and the measured-arm/stratum-probe precedents (run
  before merge, finding in the same commit as its corrections), the arm executes on this
  branch while the worktree lives. The new sheet will name a dead worktree again after this
  unit merges — the accepted, guarded pattern; the next refresh extends the stale list
  (`stratum-probe-execution/prd.md:135-136`).
- **The guard is the test:** all positive properties are name-agnostic, so the stale-list
  edit is the only change that makes the refresh falsifiable — that is why it must land RED
  first.
- **Capacity is measured, never assumed:** the machine has 36 GiB RAM and the 32B 4-bit
  weights are 18.4 GB — feasible, but the `--probe` pass settles it before a night is spent;
  a capacity failure is a published finding, never worked around.
- **The zero→next-unit rule is pre-committed, not decided after the fact:** yield == 0 with
  control intact routes to raise *k* (the roadmap's last untried named response), with the
  task-family re-scope flagged for the operator's review-gate decision — the finding does not
  choose a next unit after seeing the zero.

## Risks & Open Questions

- **The night can fail and must be quarantined, not buried.** The halt conditions are the
  runbook's own (uniform `HarnessNotProven` → stop/fix/restart from an empty workspace;
  `ContractChanged` → run void, no recovery; never reuse a workspace); dead evidence is moved
  aside by name, never deleted.
- **GPU cost is unmeasured** for a 32B matrix (one candidate × 61 private tasks × up to 3
  generations + control probes, 900 s timeouts) — stated as unknown, plan for a night; the
  probe pass bounds it first.
- **Capacity is the nearest feasibility risk:** 18.4 GB of weights plus KV cache on 36 GiB.
  If the probe dies, the arm does not run and the finding publishes the capacity bound —
  there is **no** fallback candidate pre-committed (the fork rule names the arm, not a
  ladder of bases).
- **§ 7.3's closure path is unspecified in the tree** (it said "Closed in P1"; P1 selected
  nothing). This unit does not resolve it: the finding may name the 32B as the first
  candidate with evidence, and the closure itself is a Type 1 amendment before P3's baseline
  (`PREREGISTRATION.md:261-276`).
- **Run timing is the operator's call.** The precedent is on-branch-before-merge; the
  operator confirms at the review gate whether tonight is the night.
- **A zero is a finding, not a failure** — but the finding must state in words whether the
  premise failed at the larger base too (M13-style), so a zero routes the correct next unit.

## Out of Scope

- Any P2 loop code (`whetstone run --night`, training-set recording, determinism test) —
  its premise is exactly what the arm settles.
- Any runbook content improvement beyond this arm's sheet (the probe sheet is a frozen
  historical pin; no merge-timing note is added to either).
- Any change to `src/whetstone/verify/`, `patch.py`, `attribution.py`; any fourth
  generation-contract change, ever (`p2-easier-stratum/prd.md:49-51`).
- Any second candidate, any fallback ladder, any re-scoring of the 14B/3B/7B on this
  contract (their figures are static in their own homes).
- The held-out split (§ 7.1), the retry count R, the P3 gate, the report/dashboard — named
  elsewhere on the roadmap; not this unit.
- Closing § 7.3 — the arm produces evidence; the closure is a separate amendment before P3.
