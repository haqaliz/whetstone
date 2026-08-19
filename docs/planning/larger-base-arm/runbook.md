# Runbook — the larger-base arm

**Phase 1 of the `runbook-and-guard` aspect.** Spec: `runbook-and-guard/spec.md`. Plan:
`runbook-and-guard/plan_20260815.md`. PRD: `prd.md` (requirements 1–5). Executed by the
**operator** (aliz), on the primary checkout's machine; the post-run analysis is
deterministic and agent-verifiable.

## The candidate resolution (A2, resolved before this run, never at execution time)

The fork rule pre-committed by the easier-stratum unit routes the pivot's next response to a
larger base (`p2-easier-stratum/prd.md:44-55`) — never a looser verifier, never a fourth
generation-contract change — and the probe's finding recorded the per-candidate residuals
this arm faces (`p2-easier-stratum/probe-run/finding.md:48-53`): the 14B candidate's
`hunk-count-mismatch` wall persisted even under the retry budget (its retry-triggered cause,
still present after the budget was spent), and the 3B candidate's `hunk-dies-early` and
`no-diff` causes remained small. Neither is this arm's wall: the retained candidate has no
stored records to carry them.

- `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` — the next rung on the measured family
  (3B/7B/14B all measured; the 32B verified present on Hugging Face 2026-08-15, MLX 4-bit,
  18.4 GB, apache-2.0). It has **no measured ceiling** — no stored run ever scored it — so
  the zero-ceiling rule does not apply to it → **retained**.
- `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` — retry-eligible 0, **ceiling 0** in both
  stored runs, its `im-start-loop` wall → **excluded by name**.

**The exclusion rule (pre-committed, `p2-easier-stratum/prd.md:97-99`): a candidate with a
measured zero retry-eligible ceiling — retry-eligible 0 and ceiling 0 — is excluded by name.
The rule applies to any candidate with a measured ceiling of zero; the retained candidate
has no measured ceiling, so the rule does not apply to it.** The excluded name appears in no
`--only` value; the retained candidate is expressed as exactly one `--only` flag in the arm
command. A `--only` name matching nothing or several is refused, never resolved
(`UnknownCandidate`, `run.py:400-404`). The names and facts here are the stored documents',
never invented at execution time.

## The dev subset (declared, and its resolution for this run)

The hardened contract's declared dev ids (`p2-format-hardening/measured-arm/runbook.md:15-25`)
— the tasks whose prompts the retry template was tuned against, retry-eligible in both stored
runs' autopsy records — are:

`belay-2e149603209a belay-353359e9ac6e belay-3e3051c4192a belay-844db07ed482 belay-9dba3ea557f5`

**All five are members of the committed corpus** (`tasks/stratum/easier.json` — the 66-id
declared source-B corpus, schema `whetstone-stratum/1`, loaded by the very loader the run
consumes), so the overlay is restored **non-vacuously**: each declared id matches a loaded
task and excludes it from **both** sources before anything runs (`conduct` partitions first,
`run.py:540-542`); an id matching no task is refused (`UnknownDevSubset`); and the report's
`ScoredDevSubset` backstop refuses publication if any dev id ever reached a scored set. The
probe's vacuous-overlay history is the correction's record: its sheet first carried these
same five ids, the harness refused the vacuous declaration at launch on 2026-08-15
(`UnknownDevSubset`), and the probe corrected to declaring none because the band excluded
all five — membership was the exclusion. On the **full declared set** the five ids are
members, so the overlay is declared, not dropped.

## Before you run

1. **Fetch the 32B weights into the primary's `weights/`** —
   `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` (MLX 4-bit, 18.4 GB) is fetched by hand in
   the **primary checkout** and recorded in `weights/provenance.json` — the one declared
   network exception (`docs/ROADMAP.md:574-576`), human-run, never by the arm. The recorded
   revision is immutable and every file is re-hashed before a token is generated; an
   unverified fetch is refused by name (`weights.py`).
2. **`uv sync --extra mlx` in the worktree** — generation needs the mlx extra; without it the
   run dies at first generation with `MlxUnavailable`, whose message names the fix
   (`src/whetstone/bakeoff/mlx_runtime.py:261-270`).
3. **The workspace must be empty at start** — delete
   `/Users/aliz/dev/at/whetstone/runs/larger-base-arm-workspace` and let the run recreate it;
   the rule is documentation-only in code (`run.py:753-759`), and a reused or partially-deleted
   workspace degrades silently into `UNVERIFIED`/`UNPROVISIONED`, never loudly.
4. **Evidence is machine-level** — the run's outputs live under the primary's gitignored
   `runs/`; evidence is never copied between checkouts.
5. **The dev overlay is declared, and its ids verified members of the loaded corpus** — the
   five ids above are checked against the committed document by the guard, so the
   `UnknownDevSubset` refusal cannot fire at launch time.
6. **The arm block's `--only` value equals the retained candidate** from the resolution block
   above — `tests/test_larger_base_runbook_guards.py` holds the sheet to it, and the operator
   re-checks by eye here.

## The probe pass (D7, before the arm)

**Run with CWD at the primary checkout (`/Users/aliz/dev/at/whetstone`), executing the branch code via its project (`uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-larger-base-arm`):**

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-larger-base-arm \
  python \
  -m whetstone.bakeoff.run \
  --probe <N-declared-at-run-time> \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/belay \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/contig \
  --public /Users/aliz/dev/at/whetstone/tasks/public/instances \
  --pool /Users/aliz/dev/at/whetstone/tasks/public/pool.json \
  --funnel /Users/aliz/dev/at/whetstone/tasks/public/ineligible.json \
  --weights /Users/aliz/dev/at/whetstone/weights \
  --only mlx-community/Qwen2.5-Coder-32B-Instruct-4bit \
  --out /Users/aliz/dev/at/whetstone/runs/larger-base-probe \
  --workspace /Users/aliz/dev/at/whetstone/runs/larger-base-probe-workspace \
  --timeout 900 \
  --recorded-on <declared-at-run-time>
```

`--probe N` runs only the first N source-B tasks (`run.py:959-1006`): it times and publishes
what they cost (`probe.json` under `--out`) and publishes **no counts** — a probe derives not
one verdict. The invocation is split after `python` so the guard's arm-block resolver can
tell the two run-door commands (this probe, the arm below) apart. N — the sample size — is
declared by the operator before the probe runs, and the probe's `--out` and `--workspace`
are the probe's own, never the arm's.

**The decision rule (pre-committed): the arm proceeds iff the probe completes on all N
sampled tasks and the probe's published peak bytes leave the stated headroom below the
machine's RAM (36 GiB).** The headroom is declared by the operator with N, before the probe
runs. A probe that fails, or whose peak leaves no headroom, fires the **capacity finding**
and the arm does not run: the bound is published as a finding, never worked around, and no
fallback candidate is pre-committed (`prd.md:61-64`). The machine's 36 GiB against the
weights' 18.4 GB is the ROADMAP § 10 open question; the probe settles it by measurement.

## The arm command

**Run with CWD at the primary checkout (`/Users/aliz/dev/at/whetstone`), executing the branch code via its project (`uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-larger-base-arm`):**

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-larger-base-arm \
  python -m whetstone.bakeoff.run \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/belay \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/contig \
  --public /Users/aliz/dev/at/whetstone/tasks/public/instances \
  --pool /Users/aliz/dev/at/whetstone/tasks/public/pool.json \
  --funnel /Users/aliz/dev/at/whetstone/tasks/public/ineligible.json \
  --weights /Users/aliz/dev/at/whetstone/weights \
  --only mlx-community/Qwen2.5-Coder-32B-Instruct-4bit \
  --out /Users/aliz/dev/at/whetstone/runs/larger-base-arm \
  --workspace /Users/aliz/dev/at/whetstone/runs/larger-base-arm-workspace \
  --timeout 900 \
  --recorded-on <declared-at-run-time> \
  --retries \
  --dev-subset belay-2e149603209a \
  --dev-subset belay-353359e9ac6e \
  --dev-subset belay-3e3051c4192a \
  --dev-subset belay-844db07ed482 \
  --dev-subset belay-9dba3ea557f5 \
  --journal /Users/aliz/dev/at/whetstone/runs/larger-base-arm-evidence/journal.jsonl \
  --transcript /Users/aliz/dev/at/whetstone/runs/larger-base-arm-evidence/transcript.jsonl
```

Every flag verified against `run.py`'s parser (`build_parser`, `run.py:691-901`) at write
time. Notes on the choices:

- **Denominator: 61 private (66 − 5 dev) + 1 public = 62.** The five declared dev ids are
  excluded from **both** sources before anything runs; source A is always scored in full, and
  both sources always publish together.
- **No stratum restriction — the full declared source-B set.** This arm scores the pivot
  signal's own set (`docs/ROADMAP.md:387-389`); the probe's 19-task band is not carried over.
- **Writable paths are absolute** — `--out`, `--workspace`, `--journal` and `--transcript`
  name their files under the primary's gitignored `runs/` outright, so no part of the run
  depends on CWD. This is not decoration: the workspace is built as `workspace / digest` and
  provisioned by subprocesses whose CWD is not the run's (`run.py:546`), so a relative
  workspace does not resolve there — every environment build fails, every rollout is
  `UNPROVISIONED`, and the control arm proves nothing. **The measured arm died exactly this
  way on 2026-08-12** (`HarnessNotProven`, `measured-arm/finding.md:31-45`); the absolute
  forms above are the same correction, and `tests/test_larger_base_runbook_guards.py` refuses
  a relative writable path from now on. The post-run commands keep relative `runs/` paths:
  those tools run in-process from the primary CWD, which the stored runs' analysis already
  proved.
- **`--only` is passed exactly once, with the retained candidate from the resolution block** —
  the excluded candidate's share is not spent.
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
- **The transcript and journal live in `runs/larger-base-arm-evidence/`, NOT inside `--out`.**
  `--out` is the published directory, and a transcript inside it is private donor code staged
  for publication by a path default (`TranscriptNotPrivate`, `run.py:939-960`). The report
  lands in `runs/larger-base-arm/` (gitignored), the evidence in the sibling gitignored root.
- **Workspace rules:** `/Users/aliz/dev/at/whetstone/runs/larger-base-arm-workspace` must be
  **empty** at start (delete it and let the run recreate it; the run is not resumable from a
  partially deleted workspace), and it is never inside `--out`.
- **`--recorded-on` is an input, never the clock**: the operator types the date the run
  starts; the value is declared at run time, never read from a clock.

## Expected runtime

Measured, not guessed, by the 2026-08-18 run: **~4.7 hours** for the full matrix (61 private
tasks × up to three draws where retry-eligible + control probes, 900 s timeouts) — the probe
pass's own per-task cost extrapolates to about this, and the night's cost record is the
measured value. The probe pass bounds it before any re-run; the run is a single night either
way.

## Halt conditions

1. **Any provisioning or checkout failure hitting every candidate uniformly** — the
   uniform-across-candidates tell is a harness defect, not a finding about the base
   (`HarnessNotProven`, `sweep.py:41-47, 160-183`): stop, fix, restart from the empty
   workspace. The dead evidence is quarantined by name, never deleted.
2. **`ContractChanged`** — a retry prompt the frozen contract does not carry raises through
   the seal and **aborts the run** (`freeze`, `run.py:410-465`): the run is **void, no
   recovery**, by design.
3. **Never reuse a workspace.** A fresh run is a fresh empty workspace.
4. **The probe's capacity verdict.** The probe must have completed on all N sampled tasks
   within the stated headroom — a probe that failed or exceeded it fires the capacity finding
   and the arm does not run (`prd.md:61-64`); a run that proceeds past a failed probe
   measures nothing but a machine under stress.

## Killed-run restart

A run killed mid-retry can leave a trailing `"retry"` record on the transcript; replay
refuses it as corruption, never repaired (`src/whetstone/bakeoff/transcript.py:190-198`). A
`ContractChanged` abort voids the run with no recovery. Restart procedure:

1. **Quarantine the dead evidence directory by name** — move
   `/Users/aliz/dev/at/whetstone/runs/larger-base-arm-evidence/` to
   `/Users/aliz/dev/at/whetstone/runs/larger-base-arm-evidence-dead-<date>/`; never delete it
   (the 2026-08-12 precedent keeps its dead directory in place).
2. **Fresh empty workspace** — delete `/Users/aliz/dev/at/whetstone/runs/larger-base-arm-workspace`;
   a fresh run is a fresh empty workspace (halt 3).
3. **Fresh journal and transcript paths** — the restart's `--journal`/`--transcript` name a
   new evidence directory (e.g. `/Users/aliz/dev/at/whetstone/runs/larger-base-arm-evidence-2/`);
   never append to the dead transcript, never reuse the dead paths.
4. Re-run the arm command unchanged apart from the paths above.

## Expected artifacts (all gitignored)

- `runs/larger-base-arm/{report.md,report.json,cost.json}` — the arm's own report, under the
  hardened contract's fields (retry budget, template digest, diagnosis vocabulary, retrieval
  oracle, dev subset) and the changed-candidate-set declaration.
- `runs/larger-base-arm-evidence/{journal.jsonl,transcript.jsonl,attribution.json}` — journal
  + transcript + attribution make the rerun per-task checkable.
- `runs/larger-base-probe/probe.json` — the D7 capacity record that gated the arm.
- `runs/diff-autopsy/larger-base-arm-evidence.json` — this arm's autopsy document, joining the
  stored four.
- `runs/larger-base-preanalysis/{ceiling-with-arm.json,comparison.json}` — the extended
  ceiling and the before/after comparison.
- The workspace scratch.

## Post-run analysis (agent-verifiable, offline)

**Run with CWD at the primary checkout** (`/Users/aliz/dev/at/whetstone`), not the worktree
root: the primary owns the gitignored store, and the analysis tooling refuses an `--out`
outside the documented gitignored roots — `autopsy`, `preanalysis` and `comparison` gate
(`IGNORED_OUT_ROOTS`, `src/whetstone/bakeoff/autopsy.py:716`, imported by identity);
`attribution` does not gate (AC2-pinned, its output is intermediate), so its `--out` is
operator discipline. Execute the worktree's branch code via its project:

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-larger-base-arm \
  python -m whetstone.bakeoff.attribution \
  --transcript runs/larger-base-arm-evidence/transcript.jsonl \
  --out runs/larger-base-arm-evidence/attribution.json \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/belay \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/contig

uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-larger-base-arm \
  python -m whetstone.bakeoff.autopsy \
  --transcript runs/larger-base-arm-evidence/transcript.jsonl \
  --attribution runs/larger-base-arm-evidence/attribution.json \
  --out runs/diff-autopsy/larger-base-arm-evidence.json

uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-larger-base-arm \
  python -m whetstone.bakeoff.preanalysis \
  --autopsy runs/diff-autopsy/arm-a.json \
  --autopsy runs/diff-autopsy/budget-2048.json \
  --autopsy runs/diff-autopsy/format-hardening-arm-evidence.json \
  --autopsy runs/diff-autopsy/easier-stratum-evidence.json \
  --autopsy runs/diff-autopsy/larger-base-arm-evidence.json \
  --out runs/larger-base-preanalysis/ceiling-with-arm.json

uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-larger-base-arm \
  python -m whetstone.bakeoff.comparison \
  --journal runs/larger-base-arm-evidence/journal.jsonl \
  --autopsy runs/diff-autopsy/larger-base-arm-evidence.json \
  --preanalysis runs/larger-base-preanalysis/ceiling-with-arm.json \
  --out runs/larger-base-preanalysis/comparison.json

uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-larger-base-arm \
  python -m whetstone.bakeoff.comparison --render-larger-base-report \
  --arm larger-base-arm \
  --journal runs/larger-base-arm-evidence/journal.jsonl \
  --contract runs/larger-base-arm/report.json \
  --breakdown-home runs/larger-base-preanalysis/comparison.md \
  --recorded-on <declared-at-run-time> \
  --out reports/larger-base
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
   (`ceiling.json`) covers only the two stored runs, so this arm's run requires the extended
   document (`ceiling-with-arm.json`) over **all five** autopsy documents first — arm-a,
   budget-2048, format-hardening-arm-evidence, easier-stratum-evidence and this arm's own
   larger-base-evidence — and the pre-analysis step above includes all of them. The extended
   document's combined ceiling is a different measurement over a different record set than
   the halt-check ceiling in the resolution block; the two are never fused.
4. **The comparison's run set is the arm's alone** — one journal, one autopsy, one extended
   document — so the stored runs' classifier counts keep their single home
   (`runs/format-hardening-preanalysis/`); a run with no `INTACT` probe is refused by name
   (`comparison.py:536-544`), exit 2, nothing written.
5. **The report** (`reports/larger-base/`) is assembled by `--render-larger-base-report` —
   the report-home aspect's door (exactly one arm group; a missing journal, an unproven
   control or a wrong arm-group count is refused by name) — with the hardened contract
   fields, the changed-candidate-set declaration, the non-comparability sentence, the per-arm
   token spend, and the pointer to the breakdown home — **never restating a classifier
   count**.

**Refusals are the instruments' own, named here**: a comparison without an `INTACT` probe
(`comparison.py:536-544`) or without declared decisions (`comparison.py:548-557`) exits 2 with
nothing written; autopsy and pre-analysis refuse a published `--out` (`autopsy.py:851-855`,
`preanalysis.py:467-472`); attribution refuses a missing transcript (`attribution.py:465-473`).

The public instance's rollout is expected to attribute as `UNATTRIBUTED` (no donor commit, no
checkout root named for it) — the same named gap the stored runs carry, never a skipped row.
