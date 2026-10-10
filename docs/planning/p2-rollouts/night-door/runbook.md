# Runbook — the next night (`whetstone run --night`)

**Unit:** `p2-rollouts` · **Aspect:** `night-door` · **Branch:** `feat/p2-rollouts/aliz` ·
**Run from:** the primary checkout. Every path below is anchored to `$REPO`, so export it
first — an exported variable expands before the command runs, which is what makes the path the
subprocess receives absolute:

```bash
export REPO=/absolute/path/to/whetstone   # the primary checkout, not a worktree
```

The operator's own path is not written here: a committed sheet that names one publishes a
home directory, and a reader re-deriving this run has a different one.

The operator's sheet for the next night of the improvement loop. Every command here is run
verbatim. A command sheet that disagrees with the code it runs fails at three in the morning, in a
run nobody can undo, so `tests/test_night_runbook_guards.py` refuses the disagreements first: the
flags are checked against the shipped parser, the writable paths must be absolute, no worktree may
be named, the declared dev ids must match the ones the arms declared, the held-out document must be
passed by both doors, and every run id must be the operator's own declaration.

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

## The held-out set (pinned before the run)

The held-out source-B split is fixed by `PREREGISTRATION.md` § 10.16 (Type 1, 2026-09-27),
re-derived under the scorable rule — a member is held out only if its oracle can be built under
the declared budget, the exclusion sealed in the document's rule digest. The document both door
commands below pass is `tasks/heldout/source-b.json` (schema `whetstone-heldout/1`, 12 members),
committed and consumed, never recomputed.

Two of the five declared dev ids — `donor-b-353359e9ac6e` and `donor-b-3e3051c4192a` — are
held-out members under that split, so the commands below keep them in `--dev-subset` while also
passing the document whose membership holds them: both rules exclude them from training. A
declared dev id inside the held-out band is **exclusion, never** a refusal (`night.py:227-230`) —
the dev overlay applies first and the held-out membership second (`night.py:249-261`) — and the
ids stay in `--dev-subset`, because dropping them would silently shrink the exclusion. The gate
still scores them: its eval is exactly the held-out membership, and it has no dev exclusion.

**Read the ledger's held-out record back.** Every run that passed `--heldout` — the probe and the
night alike — carries a held-out record in its `ledger.json`: the document digest and the
membership count, never the membership. Its `document_digest` **must equal the digest of the
committed** `tasks/heldout/source-b.json`; a change is a halt, never a rerun. A digest that does
not match is the run telling you it excluded a different split than the one pre-committed, and a
rerun under the changed document would train against a band nobody pre-registered.

## Before the night

1. **Serialize the GPU.** `mlx-lm` samples from process-global `mx.random` state, so a second
   process drawing on the same device perturbs this run's draws. That is a machine-level
   constraint and deliberately not a code fix: run one night at a time, and no other MLX work
   beside it. The determinism claim (same seed → byte-identical training set) is scoped to a
   machine running one night.
2. **Empty the workspace.** `$REPO/runs/<night-run-id>-workspace` must not exist or must be
   empty (the probe's own `$REPO/runs/<probe-run-id>-workspace` likewise, before its command).
   The run is not resumable from a partially deleted workspace.
3. **Declare the inputs.** `--run-id`, `--run-seed` and `--recorded-on` are typed by the operator
   before the run and written down here in the operator's own log. None of them is read from a
   clock or generated: a generated id makes two invocations of the same documented command
   produce two run directories nobody chose, and a generated seed makes the ledger's
   reproducibility claim uncheckable. This sheet declares **two** run ids, because the probe and
   the night are two runs: first `<probe-run-id>` for the probe, then `<night-run-id>` for the
   night — distinct tokens, never one reused for both.
4. **Run the probe first.** The chain is validated cheaply before a night is committed to.

## The probe pass

**Run with CWD at the primary checkout (`$REPO`):**

```bash
uv run whetstone run --night \
  --probe 2 \
  --tasks $REPO/tasks/local/donor-b \
  --tasks $REPO/tasks/local/donor-a \
  --public $REPO/tasks/public/instances \
  --pool $REPO/tasks/public/pool.json \
  --weights $REPO/weights \
  --only mlx-community/Qwen2.5-Coder-32B-Instruct-4bit \
  --runs $REPO/runs/night-probe \
  --checkpoints $REPO/checkpoints/night-probe \
  --workspace $REPO/runs/<probe-run-id>-workspace \
  --timeout 900 \
  --recorded-on <declared-at-run-time> \
  --run-id <probe-run-id> \
  --run-seed <declared-at-run-time> \
  --heldout $REPO/tasks/heldout/source-b.json \
  --dev-subset donor-b-2e149603209a \
  --dev-subset donor-b-353359e9ac6e \
  --dev-subset donor-b-3e3051c4192a \
  --dev-subset donor-b-844db07ed482 \
  --dev-subset donor-b-9dba3ea557f5
```

The probe draws `K` attempts at the first two source-B tasks and **writes no checkpoint** — a
probe that trained would produce a candidate from a self-chosen subset. What it proves is the
chain: the weights re-hash, the frozen contract, the control arm, the held-out exclusion, the
seeded draws, the per-draw journals and transcripts, the selection, and the ledger. This probe's
ledger will be `whetstone-run/3` (`LEDGER_SCHEMA`), and `check-probe` reads it through the same
verifying reader the gate uses; the first probe run's `whetstone-run/1` ledger is refused by every
reader, which is why this probe's id is fresh, never a reused one.

```bash
uv run whetstone check-probe \
  --run $REPO/runs/night-probe/<probe-run-id>
```

The decision is the command's exit: `whetstone check-probe` reads the run directory the probe
block wrote (`runs/night-probe/<probe-run-id>/ledger.json`) against the rule below. Exit 0 — the
probe satisfies the rule; proceed to the night. Exit 1 — a named harness finding (which
draw/source, or an empty seed map); no night runs behind it. Exit 2 — a refusal an operator can
fix by retyping; never a verdict about the probe.

**Decision rule (pre-committed): the night proceeds iff the probe completes with the control arm
`PASS` on every draw and a non-empty seed map.** A killed probe is **never resumed** —
restart it fresh under a new `--run-id`; a killed **night** still resumes unchanged (below).

## The night

```bash
uv run whetstone run --night \
  --tasks $REPO/tasks/local/donor-b \
  --tasks $REPO/tasks/local/donor-a \
  --public $REPO/tasks/public/instances \
  --pool $REPO/tasks/public/pool.json \
  --weights $REPO/weights \
  --only mlx-community/Qwen2.5-Coder-32B-Instruct-4bit \
  --runs $REPO/runs/nights \
  --checkpoints $REPO/checkpoints \
  --workspace $REPO/runs/<night-run-id>-workspace \
  --timeout 900 \
  --recorded-on <declared-at-run-time> \
  --run-id <night-run-id> \
  --run-seed <declared-at-run-time> \
  --heldout $REPO/tasks/heldout/source-b.json \
  --dev-subset donor-b-2e149603209a \
  --dev-subset donor-b-353359e9ac6e \
  --dev-subset donor-b-3e3051c4192a \
  --dev-subset donor-b-844db07ed482 \
  --dev-subset donor-b-9dba3ea557f5
```

Every flag verified against the shipped parser (`whetstone.cli.build_parser`) at write time.
Notes on the choices:

- **Denominator: 51 private (66 − 5 dev − 10 held-out not already dev-excluded) + 1 public = 52
  tasks, each drawn `K` times.** The exclusion order is dev overlay first, held-out second
  (`night.py:249-261`): the five declared dev ids leave both sources before anything is drawn,
  then the 12 held-out members leave what remains — 10 of them, the other 2 already in the dev
  band. Source A is always drawn against in full, and both sources always publish together.
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
  `runs/nights/<night-run-id>/draws/draw-NN.journal.jsonl` and `draw-NN.transcript.jsonl` — one
  pair per draw index, because both files are keyed `(candidate, task)` and `K` draws of one task
  share that key exactly. A single file would silently keep the last draw and discard the rest.
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
index has its own journal under `runs/nights/<night-run-id>/draws/`, every completed
`(task, draw)` pair replays verbatim, and the control arm recorded beside it is reused rather than
re-run — so a resumed night produces the record set an uninterrupted one would have produced. Do
**not** delete the run directory to "start clean": that discards the paid-for draws and changes the
experiment. Do delete and recreate the workspace if it is in an unknown state.

## After the night

Read, in this order:

1. `runs/nights/<night-run-id>/ledger.json` — the pinned inputs, the seed map, the held-out record
   (the committed document's digest and the membership count, which **must equal the digest of the
   committed** `tasks/heldout/source-b.json`; a change is a halt, never a rerun), the per-draw
   harness status and counts, the dataset digest, and the checkpoint digest or the reason there is
   none.
2. `runs/nights/<night-run-id>/dataset.json` — the selected examples, each carrying its recorded
   strict-PASS verdict. Every one of them, or the exit-criterion test is lying.
3. `runs/nights/<night-run-id>/data/train.jsonl` — what a trainer actually read.
4. `checkpoints/<night-run-id>/provenance.json` — base revision, dataset digest, run seed, training
   args, tool versions, the capacity probe's record, and the validation sentence.

Then run the leakage check — at the seam, after the night and before the gate reads the candidate:

```bash
uv run whetstone check-leakage \
  --run $REPO/runs/nights/<night-run-id> \
  --heldout $REPO/tasks/heldout/source-b.json
```

Exit 0 means source-B examples were compared and none shared a task identity with the held-out
membership. A leak exits 1 and names the task; a refusal exits 2 and names the reason (a missing or
unreadable dataset, a tampered held-out document, a digest mismatch) — either way, halt here,
before a checkpoint exists, rather than at the gate. A night with no training example at all stays
exit 0 — nothing trained, nothing to leak, disjoint by truth — while a set holding source-A
examples and no source-B example is a refusal, because nothing was compared against the membership.
The gate runbook's Step 3 checks the same link at the other end, against the checkpoint: two
commanders, belt and braces.

Then re-verify the candidate's bytes before anything else reads them:

```bash
uv run python -c "from pathlib import Path; from whetstone.loop.sft import verify_checkpoint; print(verify_checkpoint(Path('$REPO/checkpoints/<night-run-id>')).digest)"
```

**Nothing here is published.** The night's counts live in its own gitignored run directory, which
is their only home; `reports/` gains no directory from this unit, and no figure from this night may
be restated anywhere. The four published report homes measured different things and remain the only
homes of their own figures.
