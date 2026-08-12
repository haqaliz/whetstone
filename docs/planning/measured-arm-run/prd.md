# PRD — measured-arm-run

**Unit:** `feat/measured-arm-run/aliz` · **Written:** 2026-08-12 · **Source:** inline brief
(`docs/planning/_card/issue.md`) + dig (`docs/planning/_card/understanding.md`) · **Preceded by:**
`docs/planning/p2-format-hardening/` (aspects: diffcheck, retry-loop, contract-report, measured-arm)
and `docs/planning/format-hardening-measurement/` (completed 2026-08-10, R-c hold).

## Problem Statement

The format-hardening response to P1's fired pivot signal is built, verified, and **unmeasured**.
The measured-arm finding holds the decision explicitly — *"The arm itself has not run. It is the
operator's GPU pass, commanded from the runbook"* (`measured-arm/finding.md:54-73`) — and the
evidence directory it names (`runs/format-hardening-arm-evidence/`) does not exist. Until the arm
runs, `reports/format-hardening/` stays a declaration (`"arms": []`), the before/after cause
breakdown stays unspent, and the roadmap's P2 fork stays undecided: P2's rollouts
(`docs/ROADMAP.md` § 4 P2) have no training data unless the hardened contract yields strict-PASS
rollouts, and that is exactly the premise the arm re-tests. The status quo is not a risk, it is a
stopped pipeline: everything downstream of the measurement is blocked on the run.

## Goals & Success Metrics

The unit's success is the **measured before/after**, end to end:

1. **The runbook is executable again** — every stale path repointed, every flag re-verified
   against `run.py`'s parser, internally consistent (the arm's outputs land where the post-run
   chain reads them).
2. **The arm ran** — the evidence directory exists with journal + transcript; the run's report
   exists under its `--out` with the retry contract fields (this is an artifact, not a claim).
3. **The post-run chain completed** — attribution, autopsy (zero `unrecognised-shape`, or a
   named divergence), comparison breakdown (zero mapping violations, or a named violation;
   exit nonzero, never reconciled).
4. **The two-contract report is rendered** into `reports/format-hardening/` with both arms'
   verdict counts, per-arm token spend, the ceiling the arm was measured against, the
   non-comparability sentence, and the pointer to the gitignored breakdowns — never restating a
   classifier count.
5. **The finding is written** — from hold to measured before/after, stating per-candidate walls
   and the P2 fork decision; `CLAUDE.md` status block and `CHANGELOG.md` updated **in the same
   commit** (plan `:112-115`).

**No numeric target is introduced and none may be added.** A flat before/after — the retries
converting nothing the stored arms didn't — is a valid, publishable outcome (R-c,
`p2-format-hardening/prd.md:310`, `:235-236`); the report states it plainly and no threshold
exists to miss. `PREREGISTRATION.md` is **untouched** (format-hardening-measurement PRD R5:
`prd.md:169-176`) — § 10.4 already discloses the hardened contract and the non-comparable
two-report declaration.

## User Personas & Scenarios

- **Operator (aliz, the founder):** runs the ~night GPU pass from the refreshed runbook; the
  post-run analysis is "deterministic, offline, and verifiable by the agents team" (D-arm3,
  `measured-arm/spec.md:29-32`). What the operator wants is a runbook that cannot be misread:
  one command, every flag verified, every path real, every halt condition stated.
- **The next unit (P2 rollouts):** consumes the finding's fork decision — whether the hardened
  contract produces strict-PASS rollouts. What it wants is a finding that states the before/after
  in words and points at the gitignored numbers, without restating a single one of them.
- **A stranger auditing the repo:** must be able to re-derive the report from the pinned inputs.
  What they want is `reports/format-hardening/` whose report points at the evidence and whose
  numbers were produced by the named commands, not hand-typed.

## Requirements

### Must-have

- **M1 — Runbook refresh, grounded in the 54bea44 pattern.** Repoint the arm command's run CWD
  (`runbook.md:29`, currently `feat-p2-format-hardening` — the one command the previous
  correction missed) and all four post-run `uv run --project` targets
  (`runbook.md:120,127,133,144`, currently `feat-format-hardening-measurement`) onto this
  unit's worktree. Extend the pattern to the arm command: **CWD at the primary checkout,
  branch code via `uv run --project <worktree>`**, so `--out`, `--workspace`, `--journal`,
  `--transcript` all resolve into the primary's gitignored `runs/` — the run writes where the
  post-run reads, and the evidence survives worktree cleanup. Fix the stale dev-subset citation
  (`runbook.md:22` cites `run.py:951`; the partition is `run.py:540-542`).
- **M2 — Locality claim made honest.** `runbook.md:115-116` asserts the analysis tooling
  refuses an `--out` outside the gitignored roots; true of `autopsy`, `preanalysis`,
  `comparison` (`autopsy.py:716`, roots imported by identity) but **not** of `attribution.py`
  (no gate, `attribution.py:518-520`). Narrow the claim to name the three gated tools. Decision
  recorded: no gate is added to `attribution.py` — it is an AC2-pinned path
  (byte-identical to `origin/master`), its output is intermediate, and the gate exists to
  protect published artifacts.
- **M3 — Operator checkpoint.** The plan stops for the operator's GPU pass; the run's
  `--recorded-on` and the render's `--recorded-on` are **declared at run time** (input, never
  the clock — confirmed by the user, 2026-08-12).
- **M4 — Post-run chain, executed and verified.** Attribution → autopsy → comparison breakdown,
  per the runbook's verify steps (`runbook.md:159-171`): zero `unrecognised-shape` **or** the
  named-divergence finding; zero mapping violations **or** a named violation with nonzero exit.
- **M5 — Report door.** `--render-report` into `reports/format-hardening/` with both arms
  (baseline + hardened), both contracts, both token spends, the non-comparability sentence, and
  the breakdown pointer. A missing journal, unproven control, or zero arms is refused by name —
  the committed declaration is never re-rendered and a half-truth render is refused.
- **M6 — Finding + status in one commit.** `finding.md` rewritten from hold → measured
  before/after (per-candidate walls in words, the P2 fork decision, numbers only in the
  gitignored breakdowns); `CLAUDE.md` status block and `CHANGELOG.md` updated in the same
  commit that lands any runbook or taxonomy correction the measurement surfaced (plan `:112-115`).
  The finding restates no classifier count — it points at the breakdown home — and it states
  the fork decision per the pre-committed rule (R8).
- **M7 — The fork-decision rule, pre-committed (the unit's own pre-registration).** Before the
  arm runs, the rule that converts the measurement into a direction: per candidate, the
  retry-eligible parse refusals the arm's transcript converts into well-formed or better
  (graded or retried-then-graded patches) against the ceiling the pre-analysis measured decides
  the P2 fork. **A flat arm** — the retries converting nothing the stored arms didn't — means
  the format-hardening response is exhausted, and the next unit is the roadmap's own named
  fork (an easier task stratum or a larger base, `docs/ROADMAP.md:387-389`), **never** a fourth
  generation-contract change. The rule is written into the plan before the run and quoted in the
  finding; the finding argues no outcome beyond it.
- **M8 — Killed-run restart procedure in the runbook.** A run killed mid-retry can leave a
  trailing `"retry"` record that replay refuses as corruption, never repaired
  (`transcript.py:190-198`); the journal resumes but the workspace never does
  (`runbook.md:80-82`). The refreshed runbook states the restart explicitly: fresh empty
  workspace, **fresh** journal and transcript paths (never append to the dead transcript), the
  dead evidence directory quarantined by name, and the plain statement that a
  `ContractChanged` abort voids the run — a night of GPU time is not recoverable, which is why
  the freeze seal exists.

### Should-have

- **S1 — Defect response, test-first.** If the measurement surfaces a defect (nonzero
  `unrecognised-shape` = taxonomy gap; mapping violation), fix **in this unit**: a
  watched-failing fixture first, then the correction, then re-run the analysis (confirmed by the
  user, 2026-08-12). `src/whetstone/bakeoff/` stays untouched otherwise.
- **S2 — Runbook hygiene.** The runbook's "before you run" block gains the missing pieces the
  run depends on: `uv sync --extra mlx` in the worktree (generation fails with `MlxUnavailable`
  naming it otherwise, `mlx_runtime.py:261-270`), the empty-workspace discipline restated
  (documentation-only today — no code refusal, `run.py:753-759`), and a note that evidence is
  machine-level and never copied between checkouts.
- **S3 — The runbook is a guarded artifact.** A test (e.g. `tests/test_docs.py` or a sibling)
  parses the runbook's command block and asserts every flag it names exists in `build_parser` —
  the re-verification M1 demands becomes machine-checked, not a one-time hand-check. The
  previous correction missed `runbook.md:29` precisely because nothing checked the runbook
  against reality (commit `54bea44` pattern).

### Nice-to-have

- **N1 — The `header-without-hunk` trigger parameter.** The one parameter exists for the
  pre-analysis to flip `header_without_hunk_is_trigger` (`preanalysis.py:14-17`); the stored
  pre-analysis did not flip it and the arm does not change the trigger mapping. Revisit only if
  the arm's data makes a case — and never silently: a flip is a contract change with its own
  tests.

## Technical Considerations

**Core-loop element:** ② nightly improvement loop — but as *measurement*, not machinery: the arm
tests whether the format-hardened generation contract produces strict-PASS rollouts, i.e. the
premise of P2. Element ⑤ (local + private) holds by construction: a local GPU pass; transcripts
and journals are gitignored, refused under `--out` (`TranscriptNotPrivate`, `run.py:939-960`).

**Reward surface: untouched.** Nothing in this unit modifies the reward. The AC2 pins assert
`src/whetstone/verify/`, `src/whetstone/bakeoff/patch.py`, `src/whetstone/bakeoff/attribution.py`
byte-identical to `origin/master` (`tests/bakeoff/test_format_hardening_frozen.py:35-39`) and
must keep passing; `docs/ROADMAP.md` § 3's guarantee — *the operator-held tests, as the operator
wrote them, genuinely ran and genuinely passed* — is unchanged. The generation contract stays
sealed: a mid-run template edit raises `ContractChanged` and aborts the run, never repaired.

**Data & contracts:** the run's contract sidecar (with `retry_budget`, `retry_template_sha256`,
`diagnosis_vocabulary_version`, `retrieval`) lands in the run's `--out` report; the render reads
it by identity. The dev-subset is excluded from both sources before anything runs
(`_partition`, `run.py:540-542`), an unknown id is refused (`UnknownDevSubset`), and the report
backstops any leak (`ScoredDevSubset`).

**Cheat surface (this unit's own):** the unit can only cheat itself — by rendering a report the
arm didn't produce. The defence is structural: the report door refuses a missing journal, an
unproven control, or zero arms, and the committed `reports/format-hardening/` is written by
`--render-report` alone, never by hand. The residue is operator discipline (halt conditions),
which is what the runbook exists to pin down.

## Risks & Open Questions

- **The arm is flat** — pre-committed as a valid, publishable outcome (R-c); the finding and
  report state it plainly, and the fork rule (M7) converts it to a direction. Not a risk, a
  possible result.
- **The run surfaces a taxonomy gap** (`unrecognised-shape` > 0) or a mapping violation — named
  responses exist (S1); the divergence is reported, never reconciled.
- **The run's runtime is unknown** above the measured floor (~1.5 h; the yield probe's figure,
  `runbook.md:85-90`); retries add up to three draws per retry-eligible task. Plan for a night;
  the workspace is not resumable from a partially deleted tree (`runbook.md:80-82`), and a
  killed run's restart procedure is M8.
- **Uniform-across-candidates failure** (provisioning/checkout) = harness defect, not a finding
  about the bases — halt condition 1; stop, fix, restart from an empty workspace.
- **A `ContractChanged` abort voids the run with no recovery** — by design (the freeze seal),
  stated plainly in the refreshed runbook (M8); the operator accepts this before the run.
- **Open: nothing.** The dig's four questions (run CWD, dates, defect response, evidence
  locality) are resolved: 54bea44 pattern, declare at run time, fix test-first, primary-store
  only. The remaining unknowns are the measurement's own content.

## Out of Scope

- P2 rollouts — `whetstone run --night`, LoRA-SFT, the training-set tests
  (`docs/ROADMAP.md` § 4 P2) — deferred until the arm's measurement decides the fork.
- The held-out split (`PREREGISTRATION.md` § 7.1) — a P3 concern; the arm uses the declared
  dev-subset mechanism that already exists.
- Any change to the retry trigger mapping, the diagnosis vocabulary, or the generation
  contract itself (frozen; a flip would be its own contract change).
- Any change to `verify/`, `patch.py`, or `attribution.py` (AC2-pinned), except the test-first
  taxonomy correction S1 names if the measurement demands it.
- Any PREREGISTRATION amendment (R5 forbids it; § 10.4 already discloses).
- Committing evidence: transcripts contain the user's own code and are refused under any
  published path. Only the rendered report (both arms' verdict counts under their contracts)
  is committed, under `reports/format-hardening/`.
