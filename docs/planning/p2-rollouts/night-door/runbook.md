# Runbook — the first night (`whetstone run --night`)

**Unit:** `p2-rollouts` · **Aspect:** `night-door` · **Branch:** `feat/p2-rollouts/aliz` ·
**Worktree:** `/Users/aliz/dev/at/whetstone/.claude/worktrees/feat-p2-rollouts`

The operator's sheet for the first night of the improvement loop. Every command here is run
verbatim. A command sheet that disagrees with the code it runs fails at three in the morning, in a
run nobody can undo, so `tests/test_night_runbook_guards.py` refuses the disagreements first: the
flags are checked against the shipped parser, the writable paths must be absolute, exactly one
worktree may be named, and the declared dev ids must match the ones the arms declared.

## Candidate resolution (decided before the run)

**Retained: `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`.** It is the only candidate with
evidence: the larger-base arm measured the first nonzero strict-PASS yield this harness has ever
produced, and the fork rule pre-committed in that unit's PRD routed here on exactly that result
(`docs/planning/larger-base-arm/finding.md`). Rejection sampling needs a base that can solve
*something*; a base measured at zero has nothing to reject-sample from.

**Excluded by name: `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit`**, for its measured zero
retry-eligible ceiling in both stored runs (its `im-start-loop` wall) — the same pre-committed
rule the probe and the larger-base arm applied. It appears in no `--only` value below.

`--only` is passed exactly once. A night trains **one** candidate: two would produce two
checkpoints in one run directory, or one checkpoint trained on a pooled dataset whose base nobody
could name, and the door refuses both (`ManyCandidates`).

## Before the night

1. **Serialize the GPU.** `mlx-lm` samples from process-global `mx.random` state, so a second
   process drawing on the same device perturbs this run's draws. That is a machine-level
   constraint and deliberately not a code fix: run one night at a time, and no other MLX work
   beside it. The determinism claim (same seed → byte-identical training set) is scoped to a
   machine running one night.
2. **Empty the workspace.** `/Users/aliz/dev/at/whetstone/runs/night-001-workspace` must not
   exist or must be empty. The run is not resumable from a partially deleted workspace.
3. **Declare the inputs.** `--run-id`, `--run-seed` and `--recorded-on` are typed by the operator
   before the run and written down here in the operator's own log. None of them is read from a
   clock or generated: a generated id makes two invocations of the same documented command
   produce two run directories nobody chose, and a generated seed makes the ledger's
   reproducibility claim uncheckable.
4. **Run the probe first.** The chain is validated cheaply before a night is committed to.

## The probe pass

**Run with CWD at the primary checkout (`/Users/aliz/dev/at/whetstone`), executing the branch code via its project (`uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-p2-rollouts`):**

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-p2-rollouts \
  whetstone run --night \
  --probe 2 \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/belay \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/contig \
  --public /Users/aliz/dev/at/whetstone/tasks/public/instances \
  --pool /Users/aliz/dev/at/whetstone/tasks/public/pool.json \
  --weights /Users/aliz/dev/at/whetstone/weights \
  --only mlx-community/Qwen2.5-Coder-32B-Instruct-4bit \
  --runs /Users/aliz/dev/at/whetstone/runs/night-probe \
  --checkpoints /Users/aliz/dev/at/whetstone/checkpoints/night-probe \
  --workspace /Users/aliz/dev/at/whetstone/runs/night-probe-workspace \
  --timeout 900 \
  --recorded-on <declared-at-run-time> \
  --run-id probe-001 \
  --run-seed <declared-at-run-time> \
  --dev-subset belay-2e149603209a \
  --dev-subset belay-353359e9ac6e \
  --dev-subset belay-3e3051c4192a \
  --dev-subset belay-844db07ed482 \
  --dev-subset belay-9dba3ea557f5
```

The probe draws `K` attempts at the first two source-B tasks and **writes no checkpoint** — a
probe that trained would produce a candidate from a self-chosen subset. What it proves is the
chain: the weights re-hash, the frozen contract, the control arm, the seeded draws, the
per-draw journals and transcripts, the selection, and the ledger. Read
`runs/night-probe/probe-001/ledger.json` before going further.

**Decision rule (pre-committed): the night proceeds iff the probe completes with the control arm
`PASS` on every draw and a non-empty seed map.** A probe whose control arm proved nothing is a
harness finding, and no night runs behind it.

## The night

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-p2-rollouts \
  whetstone run --night \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/belay \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/contig \
  --public /Users/aliz/dev/at/whetstone/tasks/public/instances \
  --pool /Users/aliz/dev/at/whetstone/tasks/public/pool.json \
  --weights /Users/aliz/dev/at/whetstone/weights \
  --only mlx-community/Qwen2.5-Coder-32B-Instruct-4bit \
  --runs /Users/aliz/dev/at/whetstone/runs/nights \
  --checkpoints /Users/aliz/dev/at/whetstone/checkpoints \
  --workspace /Users/aliz/dev/at/whetstone/runs/night-001-workspace \
  --timeout 900 \
  --recorded-on <declared-at-run-time> \
  --run-id night-001 \
  --run-seed <declared-at-run-time> \
  --dev-subset belay-2e149603209a \
  --dev-subset belay-353359e9ac6e \
  --dev-subset belay-3e3051c4192a \
  --dev-subset belay-844db07ed482 \
  --dev-subset belay-9dba3ea557f5
```

Every flag verified against the shipped parser (`whetstone.cli.build_parser`) at write time.
Notes on the choices:

- **Denominator: 61 private (66 − 5 dev) + 1 public = 62 tasks, each drawn `K` times.** The five
  declared dev ids are excluded from **both** sources before anything is drawn; source A is always
  drawn against in full, and both sources always publish together.
- **`K` is not a flag.** It is a declared constant in `whetstone.loop.sampling`, pre-committed
  before any night. Raising it is the roadmap's named response to a low strict-PASS yield — as an
  edit to that line, in a diff, before a night, never as an argument on a command that has already
  run once.
- **Retries are ON by default** and there is no `--retries` flag to pass: the hardened contract is
  the one the evidence for this candidate was produced under. `--no-retries` is the opt-out, and
  the ledger records which contract ran.
- **Writable paths are absolute.** `--runs`, `--checkpoints` and `--workspace` name their
  directories under the primary's gitignored roots outright, so no part of the run depends on CWD.
  This is not decoration: the workspace is built as `workspace / digest` and provisioned by
  subprocesses whose CWD is not the run's, so a relative workspace does not resolve there — every
  environment build fails, every rollout is `UNPROVISIONED`, and the control arm proves nothing.
  The measured arm died exactly this way on 2026-08-12.
- **The journals and transcripts are not flags.** They live at
  `runs/nights/night-001/draws/draw-NN.journal.jsonl` and `draw-NN.transcript.jsonl` — one pair per
  draw index, because both files are keyed `(candidate, task)` and `K` draws of one task share that
  key exactly. A single file would silently keep the last draw and discard the rest.
- **`--runs` and `--checkpoints` may not be inside a `reports/` directory.** A night writes the
  user's own private donor code — the prompts and completions in its transcripts, the training set
  built from them, and an adapter trained on that set — and `reports/` is the one directory in this
  tree an outside reader is expected to read. The door refuses it (`TranscriptNotPrivate`).
- **`--timeout 900`** — the arms' own choice carried over unchanged: headroom against a genuinely
  hung verification without letting one eat the night. A timeout is `UNVERIFIED`, never `FAIL`, and
  `UNVERIFIED` is never training data. The larger-base arm disclosed a material unverified rate at
  this timeout; expect it here too, expect it to be *reported* beside the training-set size, and do
  not respond to it by loosening the check.
- **`--recorded-on` is an input, never the clock.**

## Expected runtime

Unmeasured, and deliberately not guessed. The larger-base arm measured ~4.7 hours for one greedy
attempt over this task set; this night draws `K` attempts per task, so the generation cost scales
with `K` while the control arm's cost does not (one probe per task, not one per draw). **The probe
pass is what bounds it** — read its ledger's own per-draw records before committing the night.

## Halt conditions

1. **Any provisioning or checkout failure hitting every draw uniformly** — the uniform tell is a
   harness defect, not a finding about the base (`HarnessNotProven`). Stop, fix, restart from the
   empty workspace. The dead evidence is quarantined by name, never deleted.
2. **`ContractChanged`** — a prompt the frozen contract does not carry reached the seal. The run is
   void under M7b and must be restarted from a single contract; do **not** resume it, because half
   its draws would answer a different question from the other half.
3. **`CapacityExceeded`** — the LoRA capacity probe measured a peak above the declared headroom.
   That is a **published capacity finding** about this machine and this base, not a configuration
   to adjust: gradient checkpointing and gradient accumulation were pre-committed and are already
   on. The night still completes, writes its ledger and its dataset, and records the finding; it
   writes no checkpoint.
4. **A zero strict-PASS yield.** This is **not** a halt: it is a legitimate, published outcome. The
   night completes, writes no checkpoint, states the empty outcome in the ledger, and exits
   non-zero. The response is to raise `K` — in a diff, before the next night — never to loosen what
   counts as a win.

## A killed night

Restart the **same command, unchanged**, including the same `--run-id` and `--run-seed`. Each draw
index has its own journal under `runs/nights/night-001/draws/`, every completed `(task, draw)` pair
replays verbatim, and the control arm recorded beside it is reused rather than re-run — so a
resumed night produces the record set an uninterrupted one would have produced. Do **not** delete
the run directory to "start clean": that discards the paid-for draws and changes the experiment.
Do delete and recreate the workspace if it is in an unknown state.

## After the night

Read, in this order:

1. `runs/nights/night-001/ledger.json` — the pinned inputs, the seed map, the per-draw harness
   status and counts, the dataset digest, and the checkpoint digest or the reason there is none.
2. `runs/nights/night-001/dataset.json` — the selected examples, each carrying its recorded
   strict-PASS verdict. Every one of them, or the exit-criterion test is lying.
3. `runs/nights/night-001/data/train.jsonl` — what a trainer actually read.
4. `checkpoints/night-001/provenance.json` — base revision, dataset digest, run seed, training
   args, tool versions, the capacity probe's record, and the validation sentence.

Then re-verify the candidate's bytes before anything else reads them:

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-p2-rollouts \
  python -c "from pathlib import Path; from whetstone.loop.sft import verify_checkpoint; print(verify_checkpoint(Path('/Users/aliz/dev/at/whetstone/checkpoints/night-001')).digest)"
```

**Nothing here is published.** The night's counts live in its own gitignored run directory, which
is their only home; `reports/` gains no directory from this unit, and no figure from this night may
be restated anywhere. The four published report homes measured different things and remain the only
homes of their own figures.
