# Spec — gate-runbook (aspect 6 of p3-promotion-gate)

**PRD:** `../prd.md`. **Branch:** `feat/p3-promotion-gate/aliz`. This aspect ships the operator's
sheet for the first real gated evaluation — the night-door precedent — and its guard. It also
carries the unit's write-up (`CLAUDE.md` status block, `CHANGELOG.md` entry), landed in the same
commits as the code.

## Problem slice and user outcome

Every prior arm shipped a guard-held runbook (night-door, probe-run, larger-base). Without one, the
first real candidate arrives after a night run and the operator improvises the gate invocation —
the liveness measurement (unverified rate reported from the first eval onward,
`docs/ROADMAP.md:441-442`) would start with an unmeasured, hand-rolled eval. The user outcome: a
scripted, guarded sequence for the first real gated evaluation.

## In-scope requirements

1. **The runbook** at `docs/planning/p3-promotion-gate/gate-runbook/runbook.md`, opening with the
   verification sequence (fixture-checkpoint verification first — the gate's own
   `verify_checkpoint` exercised on a known-good fixture pair, so a machinery regression is caught
   before any GPU is spent), then the real pair's command: `whetstone gate --candidate
   <checkpoints/<new>/absolute-path> --incumbent <checkpoints/<old>/absolute-path> --heldout
   tasks/heldout/source-b.json`, CWD rule, halt conditions, killed-run restart, the promotion
   record's documented home, and the post-run chain (check-leakage over the night that produced the
   candidate, the promotion record read-back, the liveness sentence with the unverified rate stated
   as a count over its denominator).
2. **The guard** at `tests/test_gate_runbook_guards.py`, on the
   `tests/test_night_runbook_guards.py` precedent (the probe-runbook guard imports its parse
   helpers from the measured-arm module by identity — the gate guard imports the parse helpers from
   the night-runbook guard's module by identity where they exist, asserted `is`, pinned module
   byte-untouched): every `--candidate`/`--incumbent`/`--heldout` value is an absolute path; the
   command uses the shipped flags (pinned to the parser, so a flag rename breaks the guard); the
   retry count named is `R` as declared (aspect 4's constant, by identity); the promotion record's
   home is the gitignored home (aspect 3); the sheet states the liveness sentence (the unverified
   rate appears in every eval's output). Watched failing against a deliberately wrong stub sheet
   (relative paths, a stale flag, a renamed home) before the real sheet exists.
3. **The write-up.** `CLAUDE.md`'s status block and `CHANGELOG.md` gain the P3 entries in the same
   commits as the code they describe (the repo's "capability and write-up arrive together"
   contract); the write-up names the residual honestly: the gate's liveness is fixture-proven until
   a real night produces a candidate, `R = 3` is declared a priori, and the § 3 baseline stays
   unspent for P4.

## Out-of-scope boundaries

- No GPU pass in this unit — the runbook scripts the operator's first real evaluation; it does not
  run it.
- No report home, no published figure.
- No change to the shipped gate, retry, or check-leakage machinery — this aspect scripts and
  guards them.

## Acceptance criteria (testable)

- AC1: the runbook is executable from disk: every command's flags exist in the shipped parser
  (guard), every path is absolute (guard), the retry count and the promotion-record home match the
  shipped constants by identity (guard).
- AC2: the guard was watched failing against a deliberately wrong stub sheet (relative writable
  paths, a stale flag, a renamed home) before the real sheet existed.
- AC3: `CLAUDE.md` and `CHANGELOG.md` describe the shipped gate, retry, held-out split, and
  check-leakage in the same commits that ship them; no figure about a model appears outside the
  documented homes.
- AC4: `uv run pytest` green; ruff and mypy over `src/` green.

## Dependencies and sequencing

- Depends on aspects 1, 3, 4, 5 (the flags, constants, and homes the sheet pins).
- Sequence: stub sheet + guard (watched failing first) → real sheet → write-up (CLAUDE.md +
  CHANGELOG.md) → full suite.
- Feeds: the operator's first real gated evaluation (post-merge) and P4.

## Open questions / risks

- The first real gated evaluation needs a real candidate, which needs a night run — the runbook is
  written before either exists; its verification sequence (fixture pair first) is what keeps the
  first real eval from being the first test of the machinery.
- Whether the runbook names the incumbent policy (explicit path) or a candidate-resolution block
  (the A2 precedent) — the PRD chose explicit paths; the sheet must not reintroduce a "current
  best" pointer by the back door.