# Runbook — the easier-stratum probe

**Phases 1 and 2 of the `probe-run` aspect.** Spec: `spec.md` (A1–A6). Plan:
`plan_20260814.md`. Executed by the **operator** (aliz), on the primary checkout's machine;
the post-run analysis is deterministic and agent-verifiable (A5).

## The candidate resolution (A2, resolved before this run, never at execution time)

Read from the stored pre-analysis document `runs/format-hardening-preanalysis/ceiling.json`
(gitignored, primary checkout — read-only, never copied into a worktree):

- `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` — retry-eligible 37, ceiling 34 (arm-a);
  retry-eligible 38, ceiling 37 (budget-2048) → **retained**.
- `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit` — retry-eligible 43, ceiling 42 (arm-a) →
  **retained**.
- `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` — retry-eligible 0, **ceiling 0** in both
  stored runs, its `im-start-loop` wall → **excluded by name**.

**The exclusion rule (pre-committed, `prd.md:93-103`): a candidate with a measured zero
retry-eligible ceiling — retry-eligible 0 and ceiling 0 — is excluded by name.** The excluded
name appears in no `--only` value; the retained pair is expressed as exactly two `--only`
flags in the arm command. A `--only` name matching nothing or several is refused, never
resolved (`UnknownCandidate`, `run.py:400-404`), and the two retained repo ids share no
name-prefix (`run.py:396` matches by containment), so the flags cannot collide as substrings.
The names and facts here are the stored document's, never invented at execution time.

## The dev subset (declared, and its resolution for this run)

The hardened contract's declared dev ids (`measured-arm/runbook.md:15-25`) — the tasks
whose prompts the retry template was tuned against, retry-eligible in both stored runs'
autopsy records — are:

`belay-2e149603209a belay-353359e9ac6e belay-3e3051c4192a belay-844db07ed482 belay-9dba3ea557f5`

**None of them is a member of the committed stratum** (`tasks/stratum/easier.json` — the
band excluded them), so **all five are excluded by membership**: none is scored by this run.
The overlay that would declare them is vacuous and the harness refuses vacuous declarations
by name: an id matching nothing in the stratum-filtered universe dies at launch
(`UnknownDevSubset`, `run.py:1038-1046`), observed 2026-08-15 when this sheet first carried
them. The arm command therefore declares **no dev subset**; the report's dev-subset field is
empty, and the exclusion's evidence is the committed stratum document's membership rather
than an overlay. The `ScoredDevSubset` backstop still refuses publication if any dev id ever
reached a scored set.

## Before you run

1. **`uv sync --extra mlx` in the worktree** — generation needs the mlx extra; without it the
   run dies at first generation with `MlxUnavailable`, whose message names the fix
   (`src/whetstone/bakeoff/mlx_runtime.py:261-270`).
2. **The workspace must be empty at start** — delete
   `/Users/aliz/dev/at/whetstone/runs/easier-stratum-workspace` and let the run recreate it;
   the rule is documentation-only in code (`run.py:753-759`), and a reused or partially-deleted
   workspace degrades silently into `UNVERIFIED`/`UNPROVISIONED`, never loudly.
3. **Evidence is machine-level** — the run's outputs live under the primary's gitignored
   `runs/`; evidence is never copied between checkouts.
4. **No dev overlay is declared, by the membership's own exclusion.** The five declared
   dev ids are verified **outside** the stratum's membership (`tasks/stratum/easier.json`),
   so the arm carries no `--dev-subset` flag and the `UnknownDevSubset` refusal cannot fire
   at launch time (it fired once, on 2026-08-15, against the sheet that still declared
   them).
5. **The stratum document is verified present and committed at its path** —
   `/Users/aliz/dev/at/whetstone/tasks/stratum/easier.json`, the aspect-1 document (schema
   `whetstone-stratum/1`). The loader refuses by name a document whose digest no longer
   matches (`StratumDigestMismatch`), and a degenerate or tiny stratum is a usage error or a
   finding, never a widened band (`prd.md:218-221`).
6. **The arm block's `--only` values equal the retained pair** from the resolution block above
   — `tests/test_probe_runbook_guards.py` holds the sheet to it, and the operator re-checks
   by eye here.

## The command

**Run with CWD at the primary checkout (`/Users/aliz/dev/at/whetstone`), executing the branch code via its project (`uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-stratum-probe-execution`):**

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-stratum-probe-execution \
  python -m whetstone.bakeoff.run \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/belay \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/contig \
  --public /Users/aliz/dev/at/whetstone/tasks/public/instances \
  --pool /Users/aliz/dev/at/whetstone/tasks/public/pool.json \
  --funnel /Users/aliz/dev/at/whetstone/tasks/public/ineligible.json \
  --stratum /Users/aliz/dev/at/whetstone/tasks/stratum/easier.json \
  --weights /Users/aliz/dev/at/whetstone/weights \
  --only mlx-community/Qwen2.5-Coder-14B-Instruct-4bit \
  --only mlx-community/Qwen2.5-Coder-3B-Instruct-4bit \
  --out /Users/aliz/dev/at/whetstone/runs/easier-stratum \
  --workspace /Users/aliz/dev/at/whetstone/runs/easier-stratum-workspace \
  --timeout 900 \
  --recorded-on <declared-at-run-time> \
  --retries \
  --journal /Users/aliz/dev/at/whetstone/runs/easier-stratum-evidence/journal.jsonl \
  --transcript /Users/aliz/dev/at/whetstone/runs/easier-stratum-evidence/transcript.jsonl
```

Every flag verified against `run.py`'s parser (`build_parser`, `run.py:691-901`) at write
time. Notes on the choices:

- **Writable paths are absolute** — `--out`, `--workspace`, `--journal` and `--transcript`
  name their files under the primary's gitignored `runs/` outright, so no part of the run
  depends on CWD. This is not decoration: the workspace is built as `workspace / digest` and
  provisioned by subprocesses whose CWD is not the run's (`run.py:546`), so a relative
  workspace does not resolve there — every environment build fails, every rollout is
  `UNPROVISIONED`, and the control arm proves nothing. **The measured arm died exactly this
  way on 2026-08-12** (`HarnessNotProven`, `measured-arm/finding.md:31-45`); the absolute
  forms above are the same correction, and `tests/test_probe_runbook_guards.py` refuses a
  relative writable path from now on. The post-run commands keep relative `runs/` paths:
  those tools run in-process from the primary CWD, which the stored runs' analysis already
  proved.
- **`--stratum` names the committed document** — the probe scores exactly the stratum's
  19-task membership from the loaded source-B corpora, before the contract is frozen, so the
  seal and the scored set cover the subset. Source A is still scored in full; both sources
  always publish together.
- **`--only` is passed exactly twice, with the retained pair from the resolution block** —
  the excluded candidate's share is not spent. The two names share no prefix, so the
  containment match (`run.py:396`) cannot collide.
- **The donor roots are `belay/` (21 tasks) and `contig/` (45 tasks)** — the miner's
  per-donor directories, verified on disk; `load_tasks` refuses the parent directory, so
  each donor is named separately.
- **`--public` is the instances directory** (`tasks/public/instances/`, holding
  `pallets__flask-4045.json`), `--pool` and `--funnel` are the committed ledger paths.
- **`--timeout 900`** — seconds allowed per verification, the measured arm's own choice
  carried over unchanged: headroom against a genuinely hung verification without letting one
  eat the night; a timeout is `UNVERIFIED`, never `FAIL`.
- **`--retries`** — the hardened contract's switch (budget 2, `retry.py:63`), off by default
  and explicitly on here; the frozen contract carries the retry budget, template digest and
  diagnosis vocabulary, so the report states the hardened contract rather than implying it.
- **The transcript and journal live in `runs/easier-stratum-evidence/`, NOT inside `--out`.**
  `--out` is the published directory, and a transcript inside it is private donor code staged
  for publication by a path default (`TranscriptNotPrivate`, `run.py:939-960`). The report
  lands in `runs/easier-stratum/` (gitignored), the evidence in the sibling gitignored root.
- **Workspace rules:** `/Users/aliz/dev/at/whetstone/runs/easier-stratum-workspace` must be
  **empty** at start (delete it and let the run recreate it; the run is not resumable from a
  partially deleted workspace), and it is never inside `--out`.
- **`--recorded-on` is an input, never the clock**: the operator types the date the run
  starts; the value is declared at run time, never read from a clock.

## Expected runtime

Stated as **unknown**, never guessed: two candidates, retries add up to three draws per
retry-eligible task on the stratum subset instead of one. Plan for a night; the excluded
candidate's share is not spent.

## Halt conditions (A3)

1. **Any provisioning or checkout failure hitting every candidate uniformly** — the
   uniform-across-candidates tell is a harness defect, not a finding about the bases
   (`HarnessNotProven`, `sweep.py:41-47, 160-183`): stop, fix, restart from the empty
   workspace. The dead evidence is quarantined by name, never deleted.
2. **`ContractChanged`** — a retry prompt the frozen contract does not carry raises through
   the seal and **aborts the run** (`freeze`, `run.py:410-465`): the run is **void, no
   recovery**, by design.
3. **Never reuse a workspace.** A fresh run is a fresh empty workspace.

## Killed-run restart

A run killed mid-retry can leave a trailing `"retry"` record on the transcript; replay
refuses it as corruption, never repaired (`src/whetstone/bakeoff/transcript.py:190-198`). A
`ContractChanged` abort voids the run with no recovery. Restart procedure:

1. **Quarantine the dead evidence directory by name** — move
   `/Users/aliz/dev/at/whetstone/runs/easier-stratum-evidence/` to
   `/Users/aliz/dev/at/whetstone/runs/easier-stratum-evidence-dead-<date>/`; never delete it
   (the 2026-08-12 precedent keeps its dead directory in place).
2. **Fresh empty workspace** — delete `/Users/aliz/dev/at/whetstone/runs/easier-stratum-workspace`;
   a fresh run is a fresh empty workspace (halt 3).
3. **Fresh journal and transcript paths** — the restart's `--journal`/`--transcript` name a
   new evidence directory (e.g. `/Users/aliz/dev/at/whetstone/runs/easier-stratum-evidence-2/`);
   never append to the dead transcript, never reuse the dead paths.
4. Re-run the arm command unchanged apart from the paths above.

## Expected artifacts (all gitignored)

- `runs/easier-stratum/{report.md,report.json,cost.json}` — the probe's own report, under
  the hardened contract's fields (retry budget, template digest, diagnosis vocabulary,
  retrieval oracle, dev subset) and the changed-task-set declaration.
- `runs/easier-stratum-evidence/{journal.jsonl,transcript.jsonl}` — journal + transcript make
  the rerun per-task checkable.
- The resolution document it was measured against:
  `runs/format-hardening-preanalysis/ceiling.json`.
- The workspace scratch.

## Post-run analysis (agent-verifiable, offline)

**Run with CWD at the primary checkout** (`/Users/aliz/dev/at/whetstone`), not the worktree
root: the primary owns the gitignored store, and the analysis tooling refuses an `--out`
outside the documented gitignored roots — `autopsy`, `preanalysis` and `comparison` gate
(`IGNORED_OUT_ROOTS`, `src/whetstone/bakeoff/autopsy.py:716`, imported by identity);
`attribution` does not gate (AC2-pinned, its output is intermediate), so its `--out` is
operator discipline. Execute the worktree's branch code via its project:

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-stratum-probe-execution \
  python -m whetstone.bakeoff.attribution \
  --transcript runs/easier-stratum-evidence/transcript.jsonl \
  --out runs/easier-stratum-evidence/attribution.json \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/belay \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/contig

uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-stratum-probe-execution \
  python -m whetstone.bakeoff.autopsy \
  --transcript runs/easier-stratum-evidence/transcript.jsonl \
  --attribution runs/easier-stratum-evidence/attribution.json \
  --out runs/diff-autopsy/easier-stratum-evidence.json

uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-stratum-probe-execution \
  python -m whetstone.bakeoff.preanalysis \
  --autopsy runs/diff-autopsy/arm-a.json \
  --autopsy runs/diff-autopsy/budget-2048.json \
  --autopsy runs/diff-autopsy/format-hardening-arm-evidence.json \
  --autopsy runs/diff-autopsy/easier-stratum-evidence.json \
  --out runs/easier-stratum-preanalysis/ceiling-with-probe.json

uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-stratum-probe-execution \
  python -m whetstone.bakeoff.comparison \
  --journal runs/easier-stratum-evidence/journal.jsonl \
  --autopsy runs/diff-autopsy/easier-stratum-evidence.json \
  --preanalysis runs/easier-stratum-preanalysis/ceiling-with-probe.json \
  --out runs/easier-stratum-preanalysis/comparison.json

uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-stratum-probe-execution \
  python -m whetstone.bakeoff.comparison --render-stratum-report \
  --arm easier-stratum \
  --journal runs/easier-stratum-evidence/journal.jsonl \
  --contract runs/easier-stratum/report.json \
  --stratum-doc /Users/aliz/dev/at/whetstone/tasks/stratum/easier.json \
  --breakdown-home runs/easier-stratum-preanalysis/comparison.md \
  --recorded-on <declared-at-run-time> \
  --out reports/easier-stratum
```

(The `--recorded-on` date is the declared date — typed at run time by the operator, an input
never read from a clock.)

Then verify:

1. **Zero `unrecognised-shape`** in the autopsy output, or the named-divergence finding the
   instrument requires — a taxonomy correction, not a pass.
2. **Mapping violations zero** (the fine→coarse assertion; a contradiction is reported, never
   reconciled).
3. **The pre-analysis extension is mandatory, not optional** — the comparison asserts the
   trigger mapping against the pre-analysis document's per-run decisions, and a run without
   declared decisions is refused by name (`comparison.py:548-557`); the stored ceiling
   (`ceiling.json`) covers only the two stored runs, so the probe's run requires the extended
   document (`ceiling-with-probe.json`) over **all four** autopsy documents first — the
   pre-analysis step above includes the probe's own. The extended document's combined ceiling
   is a different measurement over a different record set than the halt-check ceiling in the
   resolution block; the two are never fused.
4. **The comparison's run set is the probe's alone** — one journal, one autopsy, one extended
   document — so the stored runs' classifier counts keep their single home
   (`runs/format-hardening-preanalysis/`); a run with no `INTACT` probe is refused by name
   (`comparison.py:536-544`), exit 2, nothing written.
5. **The report** (`reports/easier-stratum/`) is assembled by `--render-stratum-report` — the
   aspect-3 door (exactly one arm group; `--stratum-doc` is a pointer, never parsed) — with
   the hardened contract fields, the changed-task-set declaration, the non-comparability
   sentence, the per-arm token spend, and the pointer to the breakdown home — **never
   restating a classifier count**. The door refuses a missing journal, an unproven control, or
   a wrong arm-group count.

**Refusals are the instruments' own, named here**: a comparison without an `INTACT` probe
(`comparison.py:536-544`) or without declared decisions (`comparison.py:548-557`) exits 2 with
nothing written; autopsy and pre-analysis refuse a published `--out` (`autopsy.py:851-855`,
`preanalysis.py:467-472`); attribution refuses a missing transcript (`attribution.py:465-473`).

The public instance's rollout is expected to attribute as `UNATTRIBUTED` (no donor commit, no
checkout root named for it) — the same named gap the stored runs carry, never a skipped row.
