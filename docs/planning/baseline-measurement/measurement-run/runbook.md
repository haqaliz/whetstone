# Runbook — the § 3 baseline measurement (`python -m whetstone.loop.baseline`)

**Unit:** `baseline-measurement` · **Aspect:** `measurement-run` · **Branch:**
`feat/baseline-measurement/aliz` · **Worktree:**
`/Users/aliz/dev/at/whetstone/.claude/worktrees/feat-baseline-measurement`

The operator's sheet for the single GPU pass that spends the `PREREGISTRATION.md` § 3
baseline — the untrained open base scored on the held-out split, **measured once,
re-measured never** (`PREREGISTRATION.md:129-135`). Every command here is run verbatim. A
sheet that disagrees with the code it runs fails after the number is gone, so
`tests/test_baseline_runbook_guards.py` refuses the disagreements first: the flags are
checked against `baseline.build_parser`, every writable path must be absolute, exactly one
worktree may be named, and the sheet must state the measured-once discipline as the refusal
it is.

## Candidate resolution (decided before the run)

**`mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`** is the runbook-resolved candidate — the
base the night runbook retained on its evidence
(`docs/planning/p2-rollouts/night-door/runbook.md`): the only candidate with evidence, the
first nonzero strict-PASS yield this harness has ever measured, and the fork rule
pre-committed in the larger-base arm's PRD routed to the rollouts slice on exactly that
result (`docs/planning/larger-base-arm/finding.md`). The revision is the one recorded in the
weights root's provenance (`/Users/aliz/dev/at/whetstone/weights/provenance.json`).

**§ 7.3 stays open.** This measurement fixes the series the § 3 baseline is measured over;
it is not a base selection, and nothing in this sheet closes the pre-registration's "which
open base" question. The 32B is *the first candidate with evidence* — never a base the
pre-registration has pinned — and § 7.3 closes only by a Type 1 amendment before the
measurement it governs runs.

## Before you run

1. **`uv sync --extra mlx` in the worktree** — generation needs the mlx extra; without it
   the run dies at first generation with `MlxUnavailable`, whose message names the fix
   (`src/whetstone/bakeoff/mlx_runtime.py:261-270`).
2. **Verify the machinery first** (Step 1 below). A machinery regression must be found
   before the single spend is committed to it.
3. **Empty the workspace.** `/Users/aliz/dev/at/whetstone/runs/baseline-001-workspace`
   must not exist or must be empty. The measurement resumes nothing.
4. **Materialize the untrained checkpoint** (Step 2 below) — the aspect-1 writer, from the
   weights root's provenance.
5. **Evidence is machine-level.** The measurement's outputs live under the primary's
   gitignored `runs/`; evidence is never copied between checkouts. The weights root is
   `/Users/aliz/dev/at/whetstone/weights`.
6. **Declare the inputs.** `--recorded-on` and `--run-id` are typed by the operator and
   written down in the operator's own log. Neither is read from a clock or generated: a
   record that dated or named itself would differ between two renders of the same documented
   command. `--recorded-on` is an input, never the clock.

## Step 1 — verify the machinery on the fixture suites

The door's own suites run the whole path — the held-out loader, the checkpoint re-hash, the
scoring harness, the retry discipline, the evidence writer and the render door — under the
stub engine, on fixtures. This costs no GPU and takes a few minutes. **Halt if this is not
green**: a red fixture suite means the door is not the door this sheet describes, and no
result it produces on the real pass may be recorded.

**Run with CWD at the primary checkout (`/Users/aliz/dev/at/whetstone`):**

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-baseline-measurement \
  pytest tests/loop/test_baseline_door.py tests/loop/test_baseline_document.py tests/bakeoff/test_baseline_report.py -q
```

## Step 2 — materialize the untrained checkpoint

The aspect-1 writer (`sft.write_baseline_checkpoint`; the module has no door) records the
untrained base as a `whetstone-checkpoint/1` provenance over no adapter, from the weights
root's provenance — the 32B's `repo_id` and its immutable revision:

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-baseline-measurement \
  python -c "from pathlib import Path; from whetstone.loop.ledger import tool_versions; from whetstone.loop.sft import write_baseline_checkpoint; write_baseline_checkpoint(Path('/Users/aliz/dev/at/whetstone/checkpoints/baseline-001'), repo_id='mlx-community/Qwen2.5-Coder-32B-Instruct-4bit', revision='<the revision recorded in /Users/aliz/dev/at/whetstone/weights/provenance.json>', tool_versions=tool_versions())"
```

The directory must be empty at materialization — the writer refuses a checkpoint that would
record an adapter beside a base that never trained.

## Step 3 — the measurement

**Run with CWD at the primary checkout (`/Users/aliz/dev/at/whetstone`), executing the
branch code via its project:**

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-baseline-measurement \
  python -m whetstone.loop.baseline \
  --weights /Users/aliz/dev/at/whetstone/weights \
  --checkpoint /Users/aliz/dev/at/whetstone/checkpoints/baseline-001 \
  --heldout /Users/aliz/dev/at/whetstone/tasks/heldout/source-b.json \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/belay \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/contig \
  --public /Users/aliz/dev/at/whetstone/tasks/public/instances \
  --pool /Users/aliz/dev/at/whetstone/tasks/public/pool.json \
  --runs /Users/aliz/dev/at/whetstone/runs \
  --workspace /Users/aliz/dev/at/whetstone/runs/baseline-001-workspace \
  --out /Users/aliz/dev/at/whetstone/reports/baseline-measurement \
  --timeout 900 \
  --recorded-on <declared-at-run-time> \
  --run-id baseline-001
```

Every flag verified against the module's own parser (`baseline.build_parser`) at write time.
Notes on the choices:

- **The scored set is the held-out membership (12 of 66, `tasks/heldout/source-b.json`)
  plus source A in full** — both sources always published together
  (`PREREGISTRATION.md:142-147`), source A scored once and unretried.
- **The retry discipline is the gate's** — `R = 3` by identity, applied to the held-out
  membership only; a held-out task still unverified after `R` stays unverified **in the
  denominator** (coverage, never a silent drop — `PREREGISTRATION.md:111-114`).
- **Writable paths are absolute.** `--runs`, `--workspace` and `--out` name their
  directories outright, so no part of the run depends on CWD. The workspace is built as
  `workspace / digest` and provisioned by subprocesses whose CWD is not the run's — a
  relative workspace does not resolve there, every environment build fails, and every
  rollout is `UNPROVISIONED`. The measured arm died exactly this way on 2026-08-12.
- **`--runs` may not be inside a `reports/` directory**, and `--out` may not be under a
  gitignored root — both refused by name before anything loads.
- **A same-series artifact at `--out` is a refusal, never a warning to proceed.** The
  measured-once guard keys on the series — the base identity and the held-out document
  digest — and a second measurement of the same series is refused by name
  (`BaselineAlreadyMeasured`). A **changed** pinned input (a new base revision, a new
  held-out split) is § 3's legitimate new series (`PREREGISTRATION.md:133-135`), recorded
  as a new measurement — the old series is never extended.
- **`--timeout 900`** — the arms' own choice carried over unchanged. A timeout is
  `UNVERIFIED`, never `FAIL`. The larger-base finding disclosed a material unverified rate
  at this timeout; expect it here too, expect it to be *reported* beside the coverage, and
  do not respond to it by loosening the check.
- **`--recorded-on` is an input, never the clock.**

## Halt conditions

1. **Exit 2 — a refusal.** The message names the cause: a same-series artifact at `--out`,
   a `--runs` root inside `reports/`, an `--out` under a gitignored root, a checkpoint that
   cannot be re-hashed, a held-out document whose digest does not match its contents, a
   membership id that matches no loaded task, or weights whose provenance the disk does not
   support. Fix the named thing and re-run with a **fresh `--run-id`**. Do not edit a
   document to make a refusal go away; a digest mismatch means the document was changed
   after it was sealed, and the response is to find out by whom.
2. **A zero solved count is not a halt.** It is a valid, publishable baseline —
   `docs/ROADMAP.md:470-471` fixes the pivot signal as none, and the engine working and the
   empirical claim being established are two different milestones.
3. **Coverage below 12 of 12 is not a halt.** A held-out task still unverified after `R`
   retries lowers coverage; the baseline publishes the lower coverage with the count over
   its denominator, never a silent drop (`PREREGISTRATION.md:111-114`). The roadmap's
   response to a gate that cannot fire — a more reliable sandbox, never a looser gate —
   applies to later evals, not to this measurement.

## A killed run

The measurement resumes nothing — it re-runs from the start, and a re-run with the same
`--run-id` would overwrite the killed run's evidence under `runs/<run-id>/`. Restart with a
**fresh `--run-id`** (`baseline-002`, …) and keep both records. The evidence writer only
writes at the end of a successful measurement; a half-written artifact is refused by
schema, never repaired. Do delete and recreate the workspace if it is in an unknown state.

## After the measurement — the post-run chain

Read, in this order:

1. **The evidence** — `runs/baseline-001/evidence.json`
   (`whetstone-baseline-run/1`): the base identity from the checkpoint's provenance, both
   sources' counts, the retry records and the tool versions. Hashes and verdicts only — no
   prompt, completion or patch text.
2. **The render door** — turn the evidence into the committed artifact:

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-baseline-measurement \
  python -m whetstone.loop.baseline \
  --render /Users/aliz/dev/at/whetstone/runs/baseline-001/evidence.json \
  --checkpoint /Users/aliz/dev/at/whetstone/checkpoints/baseline-001 \
  --out /Users/aliz/dev/at/whetstone/reports/baseline-measurement \
  --recorded-on <declared-at-run-time>
```

   The render re-hashes the checkpoint, reads the series from the evidence, and writes the
   three artifacts through the aspect-3 writer. The measured-once discipline holds here
   too: a same-series artifact already at `--out` is refused by name, never a second
   render.

3. **The finding** — the operator's own commit: the measured artifact
   (`reports/baseline-measurement/`) is committed with the finding that records the
   measurement. The number itself is the operator's single spend, and the finding is where
   it is stated; nothing in this sheet is a figure about a model.

## Outcomes

- **A zero solved count is a valid, publishable baseline** (`docs/ROADMAP.md:470-471`): the
  engine working and the empirical claim being established are two different milestones.
- **Coverage below 12 of 12 is disclosed, never a halt**: the lower coverage is published
  with the count over its denominator, and `UNVERIFIED` never leaves the denominator
  (`PREREGISTRATION.md:111-114`).
- **`--recorded-on` is an input, never the clock.** The date the artifact declares is the
  date the operator typed, in the operator's own log.
- **Measured once, re-measured never.** A same-series artifact at `--out` is refused by
  name; the number is not re-run to be checked, and it is not re-run because a later result
  looked disappointing (`PREREGISTRATION.md:129-132`).