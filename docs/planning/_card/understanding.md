# Understanding — measured-arm-run

**Dig date:** 2026-08-12 · **Branch:** `feat/measured-arm-run/aliz` · **Dig agents:** CLI-surface verification + stale-surface map (both re-verified against the worktree at `v0.4.0`).

## What this work really is

The measured-arm slice (`docs/planning/p2-format-hardening/measured-arm/`) shipped all its
machinery and stopped at the operator's GPU pass: the finding holds the decision — *"The arm
itself has not run"* (`finding.md:54-73`) — and `runs/format-hardening-arm-evidence/` does not
exist. This unit executes the runbook end to end and lands the measured before/after: the arm's
report, the evidence directory, the post-run analysis chain, and the after-finding that states
the P2 fork decision. It is a **measurement unit**, not a feature build — the code changes are
doc/runbook corrections, plus code only if the measurement surfaces a defect (the runbook's own
verify steps name the two: `unrecognised-shape` → taxonomy correction; mapping violation →
named divergence).

## Grounding (file:line, re-verified)

- **Deliverable contract:** D-arm1..D-arm4 (`measured-arm/spec.md:16-37`); plan Phase 2
  (operator run, `plan_20260809.md:53-80`), Phase 3 (post-run analysis, `:82-99`), Phase 4
  (report + finding + status in one commit, `:101-118`). **No PREREGISTRATION amendment**
  (format-hardening-measurement PRD R5: `prd.md:169-176`) — § 10.4 already discloses the
  hardened contract.
- **Pre-committed flat outcome:** R-c (`p2-format-hardening/prd.md:310`, `:235-236`) — a flat
  before/after is valid, publishable, no threshold to miss.
- **The hold:** `measured-arm/finding.md:54-73`; evidence homes `finding.md:89-97`.
- **P2 fork:** `docs/ROADMAP.md` § 4 P2 (exit criteria + pivot signal).

## The CLI surface (agent-verified against `run.py` at HEAD)

Every flag in the runbook's arm command exists in `build_parser` (`src/whetstone/bakeoff/run.py:691-839`)
with matching semantics: `--tasks` ×2 (belay 21, contig 45 — verified on disk), `--public`,
`--pool`, `--funnel`, `--weights` (three candidates, re-hashed before generation),
`--timeout 900`, `--recorded-on` (input, never the clock), `--retries` (off by default; the
arm opts in), `--dev-subset` ×5 (all five ids present; three-layer exclusion, `UnknownDevSubset`
refusal, `ScoredDevSubset` backstop), `--journal` + `--transcript` (transcript refused under
`--out` — `TranscriptNotPrivate`, `run.py:939-960`). The contract seal (`ContractChanged` abort)
and the finite diagnosis vocabulary are intact.

## What the dig surfaced (the unit's real content)

1. **Stale worktree paths — the 54bea44 pattern, one missed line.** The runbook's arm command
   still runs from `feat-p2-format-hardening` (`runbook.md:29`), and all four post-run
   `uv run --project` targets name `feat-format-hardening-measurement` (`runbook.md:120,127,133,144`).
   Neither worktree exists. The previous correction (commit `54bea44`) established the pattern:
   CWD at the primary checkout (owns the gitignored store), branch code via
   `uv run --project <worktree>`. **Line 29 was the one command that correction missed.** The
   fix extends the pattern to the arm command itself: run with CWD at the primary, project from
   this worktree, so the run's `--out`, `--workspace`, `--journal`, `--transcript` land in the
   primary's `runs/` — otherwise the run writes into the worktree and the post-run reads the
   primary, which is internally inconsistent as written.
2. **One stale code citation:** `runbook.md:22` cites `run.py:951` for the dev-subset
   partition; the partition is now `run.py:540-542`. Semantics unchanged.
3. **One over-broad claim:** `runbook.md:115-116` says the analysis tooling refuses an `--out`
   outside the gitignored roots; true of `autopsy`, `preanalysis`, `comparison` (roots
   `("runs/", "reports/local/", "checkpoints/", "tasks/local/", "_sandbox/")`, `autopsy.py:716`)
   but **not** of `attribution.py` (no locality gate, `attribution.py:518-520`). Decision: narrow
   the runbook claim rather than add the gate — `attribution.py` is an AC2-pinned path
   (byte-identical to `origin/master`), and the gate exists to protect published artifacts;
   attribution's output is intermediate. A docs fix keeps the pin and the claim honest.
4. **Workspace rules are documentation-only** (empty at start, never inside `--out`): no code
   refusal; reuse degrades silently into `UNVERIFIED`/`UNPROVISIONED`. Operator discipline,
   already the runbook's halt conditions — unchanged.
5. **`reports/format-hardening/` is declaration-only today**: `"arms": []`, no counts
   (`report.json`), rendered by `--render-report` with both arms once the arm lands.

## Affected areas

- `docs/planning/p2-format-hardening/measured-arm/runbook.md` — the refresh (paths, citation,
  locality claim).
- `docs/planning/p2-format-hardening/measured-arm/finding.md` — the hold → measured after.
- `reports/format-hardening/{report.md,report.json,cost.json}` — declaration → rendered.
- `CLAUDE.md` status block + `CHANGELOG.md` — same-commit write-up (plan `:112-115`).
- `src/whetstone/bakeoff/*` — **untouched unless the measurement surfaces a defect** (AC2 pins
  and the one-home guard stay intact; a taxonomy correction would be test-first).

## Core-loop placement

Element ① (verifier) and ② (loop) are both touched only as *measurement*: the arm tests whether
the format-hardened generation contract yields strict-PASS rollouts — the premise of P2's
rollouts (the roadmap's P2 pivot signal). Element ⑤ (local) is honored by construction: the run
is a local GPU pass; transcripts/journal are gitignored and refused under `--out`. The reward
stays execution-grounded: nothing here touches `verify/` (AC2-pinned), and the retry trigger
mapping is the frozen finite vocabulary.

## Open questions for the interview

- **Q1 — Arm-run CWD:** adopt the 54bea44 pattern for the arm command itself (CWD primary,
  `uv run --project <worktree>`), so all artifacts accumulate in the primary's gitignored
  store? (Recommended — matches the post-run chain and survives worktree cleanup.)
- **Q2 — `--recorded-on` and render dates:** the runbook's are `2026-08-09` (arm) /
  `2026-08-10` (render). These are operator inputs. For this unit, use the unit's declared
  date (2026-08-12) or keep the runbook's dates as-is? (Dates are inputs, never the clock —
  but a render dated before the arm's recorded date would be odd; decide in the plan.)
- **Q3 — Scope of code work:** code changes only if the measurement surfaces a defect
  (taxonomy gap → watched-failing fixture first), else docs + commands only?
- **Q4 — Worktree ephemerality:** the worktree is removed after merge; all evidence lives in
  the primary's `runs/` (never copied between checkouts — provenance rule). Confirm no
  evidence may be committed to the repo (only the report, which is the render of both
  contracts, is committed under `reports/format-hardening/`).
