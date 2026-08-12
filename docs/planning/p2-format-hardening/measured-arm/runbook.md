# Runbook — the measured format-hardening arm

**Phase 2 of the `measured-arm` aspect.** Spec: `spec.md` (D-arm1..D-arm4).
Plan: `plan_20260809.md` Phase 2. Executed by the **operator** (aliz), on the primary
checkout's machine; the post-run analysis is deterministic and agent-verifiable (D-arm3).

**Before this runbook was written, the ceiling was measured** (Phase 1, `preanalysis.py`):
retry-eligible **118**, inferred-truncation **5**, ceiling **113** across the two stored arms
(per candidate: arm-a 14B 37/34, 3B 43/42, 7B 0/0; budget-2048 14B 38/37 — the gitignored
document is `runs/format-hardening-preanalysis/ceiling.json`). The ceiling is **not near
zero**, so the arm proceeds. The 7B candidate's zero is its own halt signal: retries cannot
convert a loop collapse, and the run below still sweeps it because the baseline contract did —
the before/after comparison needs the same matrix.

## The dev subset (D-arm2, named before the run)

`belay-2e149603209a belay-353359e9ac6e belay-3e3051c4192a belay-844db07ed482 belay-9dba3ea557f5`

These are the tasks whose prompts the retry template was tuned against: they are retry-eligible
in **both** stored runs' autopsy records (the Phase 1 pre-analysis's `dev_subset_candidates`
intersection), so the tuning corpus covered their failure shapes. The ids are excluded from
**both** sources before anything runs (`conduct` partitions first, `run.py:540-542`), an id
matching no task is refused (`UnknownDevSubset`), and the report's `ScoredDevSubset` backstop
refuses the publication if any dev id ever reached a scored set. All five are verified present
in the corpus (`tasks/local/belay/*.json`).

## Before you run

1. **`uv sync --extra mlx` in the worktree** — generation needs the mlx extra; without it the
   run dies at first generation with `MlxUnavailable`, whose message names the fix
   (`src/whetstone/bakeoff/mlx_runtime.py:261-270`).
2. **The workspace must be empty at start** — delete `runs/format-hardening-workspace` and let
   the run recreate it; the rule is documentation-only in code (`run.py:753-759`), and a
   reused or partially-deleted workspace degrades silently into `UNVERIFIED`/`UNPROVISIONED`,
   never loudly.
3. **Evidence is machine-level** — the run's outputs live under the primary's gitignored
   `runs/`; evidence is never copied between checkouts.
4. **The five dev-subset ids are verified present in `tasks/local/belay/` before launch**, so
   the `UnknownDevSubset` refusal cannot fire at launch time.

## The command

**Run with CWD at the primary checkout (`/Users/aliz/dev/at/whetstone`), executing the branch code via its project (`uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-measured-arm-run`):**

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-measured-arm-run \
  python -m whetstone.bakeoff.run \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/belay \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/contig \
  --public /Users/aliz/dev/at/whetstone/tasks/public/instances \
  --pool /Users/aliz/dev/at/whetstone/tasks/public/pool.json \
  --funnel /Users/aliz/dev/at/whetstone/tasks/public/ineligible.json \
  --weights /Users/aliz/dev/at/whetstone/weights \
  --out runs/format-hardening-arm \
  --workspace runs/format-hardening-workspace \
  --timeout 900 \
  --recorded-on <declared-at-run-time> \
  --retries \
  --dev-subset belay-2e149603209a \
  --dev-subset belay-353359e9ac6e \
  --dev-subset belay-3e3051c4192a \
  --dev-subset belay-844db07ed482 \
  --dev-subset belay-9dba3ea557f5 \
  --journal runs/format-hardening-arm-evidence/journal.jsonl \
  --transcript runs/format-hardening-arm-evidence/transcript.jsonl
```

Every flag verified against `run.py`'s parser (`build_parser`, `run.py:691-839`) at write time.
Notes on the choices:

- **CWD at the primary checkout** — the run's `--out`, workspace, journal and transcript are
  relative `runs/` paths; executed from the primary they land in the primary's gitignored
  store, which the post-run commands read — the arm writes where the post-run reads. The
  branch code is executed via its project, never by running from the worktree root.
- **The donor roots are `belay/` (21 tasks) and `contig/` (45 tasks)** — the miner's
  per-donor directories, verified on disk. The plan draft's `donor-a`/`donor-b` placeholder
  names do not exist; the pseudonymous names are `belay` (donor B, 21) and `contig`
  (donor A, 45), 66 tasks total. `load_tasks` refuses the parent directory, so each donor is
  named separately.
- **`--public` is the instances directory** (`tasks/public/instances/`, holding
  `pallets__flask-4045.json`), `--pool` and `--funnel` are the committed ledger paths. Source A
  is published beside source B always; neither source may appear alone.
- **`--timeout 900`** — seconds allowed per verification. The yield-probe docs do **not**
  record the value arm-a used, so no precedent exists to copy; the choice is grounded in the
  measured evidence instead: the P1 cost record (`reports/baseline/cost.json`) shows total
  verification of 183 s (3B), 8 s (7B), 197 s (14B) across 64 tasks plus control — seconds per
  verification, including provisioning. 900 s is headroom against a genuinely hung
  verification without letting one eat the night, and a timeout is `UNVERIFIED`, never `FAIL`.
- **`--retries`** — the arm's switch (aspect 2 composition), off by default; this run is the
  first to opt in. The contract it freezes carries the retry budget, template digest and
  diagnosis vocabulary (`contract-report` fields), so the report states the hardened contract
  rather than implying it.
- **The transcript and journal live in `runs/format-hardening-arm-evidence/`, NOT inside
  `--out`.** The plan draft's placeholder put them under `runs/format-hardening-arm/`, which
  the harness refuses: `--out` is the published directory, and a transcript inside it is
  private donor code staged for publication by a path default (`TranscriptNotPrivate`,
  `run.py:939-960`, asserted end-to-end in `test_run_transcript.py`). The report lands in
  `runs/format-hardening-arm/` (gitignored), the evidence in the sibling gitignored root.
- **Workspace rules:** `runs/format-hardening-workspace` must be **empty** at start (delete it
  and let the run recreate it; the run is not resumable from a partially deleted workspace),
  and it is never inside `--out`. The run is **not** resumable across a deleted workspace.
- **`--recorded-on` is an input, never the clock**: the operator types the date the run
  starts; the value is declared at run time, never read from a clock.

## Expected runtime

The yield probe's measured **~1.5 h** for the baseline contract (spec D-arm3, a measured figure
labeled as such) is a **floor**: retries add generation time — up to three draws per
retry-eligible task instead of one — stated as **unknown** rather than guessed. Plan for a
night.

## Halt conditions

1. **Any provisioning or checkout failure** — the "uniform-across-candidates" tell: a failure
   hitting every candidate identically is a harness defect, not a finding about the bases.
   Stop, fix, restart from the empty workspace.
2. **The ceiling near zero** — not the case here (113), but the discipline stands: a run whose
   pre-analysis shows nothing to convert is not run (PRD R5).
3. **Any `UnstubbedPrompt`-style failure** — a retry prompt the frozen contract does not carry
   raises `ContractChanged` through the seal and **aborts the run**; that is a template moved
   after freeze, and the run is void, not repaired.
4. **Never reuse a workspace.** A fresh run is a fresh empty workspace.

## Killed-run restart

A run killed mid-retry can leave a trailing `"retry"` record on the transcript; replay refuses
it as corruption, never repaired (`src/whetstone/bakeoff/transcript.py:190-198`). A
`ContractChanged` abort voids the run with no recovery — by design, the freeze seal. Restart
procedure:

1. **Quarantine the dead evidence directory by name** — e.g. move
   `runs/format-hardening-arm-evidence/` to `runs/format-hardening-arm-evidence-dead-<date>/`.
2. **Fresh empty workspace** — delete `runs/format-hardening-workspace`; a fresh run is a
   fresh empty workspace (halt 4).
3. **Fresh journal and transcript paths** — the restart's `--journal`/`--transcript` name a
   new evidence directory (e.g. `runs/format-hardening-arm-evidence-2/`); never append to the
   dead transcript, never reuse the dead paths.
4. Re-run the arm command unchanged apart from the paths above.

## Expected artifacts (all gitignored)

- `runs/format-hardening-arm/{report.md,report.json,cost.json}` — the hardened arm's report,
  with the retry contract fields and the non-comparability sentence (aspect 3 writer).
- `runs/format-hardening-arm-evidence/{journal.jsonl,transcript.jsonl}` — AC7's discipline:
  journal + transcript make the rerun per-task checkable.
- The ceiling document it was measured against: `runs/format-hardening-preanalysis/ceiling.json`.

## Post-run analysis (agent-verifiable, offline)

**Run with CWD at the primary checkout** (`/Users/aliz/dev/at/whetstone`), not the worktree
root: the primary owns the gitignored store, and the analysis tooling refuses an `--out`
outside the documented gitignored roots — `autopsy`, `preanalysis` and `comparison` gate
(`IGNORED_OUT_ROOTS`, `src/whetstone/bakeoff/autopsy.py:716`, imported by identity);
`attribution` does not gate (AC2-pinned, its output is intermediate), so its `--out` is
operator discipline — so a relative `runs/` path must resolve to the primary's. Execute the
worktree's branch code via its project:

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-measured-arm-run \
  python -m whetstone.bakeoff.attribution \
  --transcript runs/format-hardening-arm-evidence/transcript.jsonl \
  --out runs/format-hardening-arm-evidence/attribution.json \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/belay \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/contig

uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-measured-arm-run \
  python -m whetstone.bakeoff.autopsy \
  --transcript runs/format-hardening-arm-evidence/transcript.jsonl \
  --attribution runs/format-hardening-arm-evidence/attribution.json \
  --out runs/diff-autopsy/format-hardening-arm-evidence.json

uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-measured-arm-run \
  python -m whetstone.bakeoff.comparison \
  --journal runs/arm-a/journal.jsonl \
  --journal runs/budget-2048/journal.jsonl \
  --journal runs/format-hardening-arm-evidence/journal.jsonl \
  --autopsy runs/diff-autopsy/arm-a.json \
  --autopsy runs/diff-autopsy/budget-2048.json \
  --autopsy runs/diff-autopsy/format-hardening-arm-evidence.json \
  --preanalysis runs/format-hardening-preanalysis/ceiling.json \
  --out runs/format-hardening-preanalysis/comparison.json

uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-measured-arm-run \
  python -m whetstone.bakeoff.comparison --render-report \
  --arm baseline --journal runs/arm-a/journal.jsonl \
    --contract reports/baseline/report.json \
  --arm hardened --journal runs/format-hardening-arm-evidence/journal.jsonl \
    --contract runs/format-hardening-arm/report.json \
  --breakdown-home runs/format-hardening-preanalysis/comparison.md \
  --recorded-on <declared-at-run-time> \
  --out reports/format-hardening
```

(The `--recorded-on` date is the declared date — typed at run time by the operator, an input
never read from a clock.)

Then verify:

1. **Zero `unrecognised-shape`** in the autopsy output, or the named-divergence finding the
   instrument requires (`finding.md:108-110`) — a taxonomy correction, not a pass.
2. **Mapping violations zero** (the fine→coarse assertion; a contradiction is reported, never
   reconciled).
3. The before/after breakdown — both stored arms and the new arm, per candidate, assembled
   by `whetstone.bakeoff.comparison` (schema `whetstone-comparison/1`) into the gitignored
   `runs/format-hardening-preanalysis/comparison.md` home; the trigger mapping is re-derived
   by identity and asserted against the pre-analysis's decisions — a contradiction exits
   nonzero, never reconciled.
4. The report (`reports/format-hardening/`) is assembled by `--render-report` with both
   contracts, both token spends, the ceiling the arm was measured against (113), the
   non-comparability sentence, and the pointer to the breakdowns — **never restating a
   classifier count**; the door refuses a missing journal, an unproven control, or zero arms.

The public instance's rollout is expected to attribute as `UNATTRIBUTED` (no donor commit, no
checkout root named for it) — the same named gap the stored runs carry, never a skipped row.
