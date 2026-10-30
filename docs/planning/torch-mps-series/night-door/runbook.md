# Runbook — the Torch/MPS night (`whetstone run --night --runtime torch`)

**Unit:** `torch-mps-series` · **Aspect:** `night-sheet` · **Branch:** `feat/torch-mps-series/aliz`
· **Run from:** the primary checkout. Every path below is anchored to `$REPO`, so export it
first — an exported variable expands before the command runs, which is what makes the path the
subprocess receives absolute:

```bash
export REPO=/absolute/path/to/whetstone   # the primary checkout, not a worktree
export DONOR=/absolute/path/to/your/donor/checkout   # the repo the night re-mines new commits from
```

The operator's own path is not written here: a committed sheet that names one publishes a home
directory, and a reader re-deriving this run has a different one. `$DONOR` is declared for the same
reason — the donor is one operator's checkout, and the night mines whatever that operator points
the anchor at rather than a path committed into the sheet.

This is the Torch/MPS series' own sheet, not the MLX sheet with a flag changed. The MLX sheet pins
a 32B MLX directory and excludes the 7B by name; this series retains an 8B **HF** base under a
bounded repair contract, runs Torch
on the Mac's MPS, and emits a PEFT adapter any `transformers`/`peft` stack can load. The two
series are non-comparable in weights, runtime, device, kernels and precision, and no figure from
one may be restated as the other's.

## The environment and the runtime

Every command runs under `uv run --extra torch`, the torch-only environment. The primary `.venv`
may hold both runtimes — it carries the arm's ad-hoc installs — so `--runtime torch` is passed on
both doors rather than detected: with both engines importable, an unnamed runtime is a clean exit-2
refusal, and a silently substituted MLX run would not be the series the amendment pinned.

Run one night at a time. The Torch path seeds `torch.manual_seed` globally, so a second process
drawing in the same session perturbs this run's draws. The determinism claim (same seed →
byte-identical training set) is scoped to a machine running one night.

The torch floor is **2.14.1**. The 8B night ran 2.14.0 and lost its Metal command buffer after
~35 h (`kIOGPUCommandBufferCallbackErrorOutOfMemory`), then failed deterministically on a corrupted
attention mask (#86). 2.14.1 ran the 8B pre-flight's 144 draws without either failure, and every
draw now calls `torch.mps.empty_cache()`. A ledger recording a lower torch version is a halt.

Both door commands are wrapped in `caffeinate -dimsu`: the public task is processed last, and a
sleeping Mac dropped the network after 832 rollouts on two separate nights. `-s` holds only while
the machine is on **power**; `-d/-i/-m/-u` still apply on battery, but a night is committed to on
AC.

## Candidate resolution (retained, decided before the run)

**Retained: `Qwen/Qwen3-8B` at revision
`b968826d9c46dd6066d109eabc6255188de91218`.** It is the plain HF 8B base, retained because the
14B NF4 path failed its pre-flight (7/7 `NO_DIFF` at ~9 min/draw, then an uninterruptible Metal
hang; § 10.23) and the 8B is the only measured stable runtime here: 35 hours, no hang, 206 real
diffs in 624 evaluable draws, and 51 patches that applied and failed. The repair contract is the
change: after a `NOT_SOLVED`, the run re-asks up to twice with a pre-posed repair prompt (the first
prompt plus the verdict, never the test output), and the same STRICT verifier decides. The base's
MPS fit was measured under § 10.21: 8.96 GB against the 25.6 GB headroom at ~118 s/step. `--only`
is passed exactly once, with the full `Qwen/...` id: a night trains **one** candidate, and the
shorter id would also match an on-disk MLX 4-bit directory in the substring matcher and be refused
as two candidates.

The MLX sheet's 7B exclusion is **not** copied here. It is a measured statement about the MLX
4-bit directory's zero ceiling on the MLX series, not about Torch/MPS on this series' HF base.

Excluded: the 14B NF4 (the pre-flight hang, § 10.22/§ 10.23); the 30B-A3B fp16 is ~61 GB against
36 GB of unified memory. The on-disk `*-4bit` directories are MLX format and are not Torch-loadable;
this series never points `--only` at one.

The base is already fetched — ~16.4 GB through `whetstone.bakeoff.weights.fetch` into
`$REPO/weights`, with per-file hashes in `weights/provenance.json`; the door re-hashes every named
file, and a mismatch refuses the run.

## The held-out set (unchanged by the runtime or the base)

`PREREGISTRATION.md` § 10.23 (Type 1, 2026-10-25) pins this series: Torch/PEFT, `mps`, `float16`,
the 8B HF repo and revision, and the bounded repair contract, and declares every figure
non-comparable to the 8B-without-repairs, 14B, 7B and MLX series. The
held-out document and its `document_digest` are **unchanged** from `PREREGISTRATION.md` § 10.16
(Type 1, 2026-09-27), which re-derived the split under the scorable rule — a member is held out
only if its oracle can be built under the declared budget.

The document both doors pass is `tasks/heldout/source-b.json` (schema `whetstone-heldout/1`),
committed and consumed, never recomputed. Two of the five dev ids below —
`donor-b-353359e9ac6e` and `donor-b-3e3051c4192a` — are members of it: they stay in `--dev-subset`
while the document is also passed, because both rules exclude them and dropping either would
silently shrink the exclusion. A declared dev id inside the held-out band is exclusion, never a
refusal.

## The MPS read-back (after the probe and after the night)

Read `runs/.../<run-id>/ledger.json` and confirm `backend.name == "torch"`,
`backend.device == "mps"` and `backend.precision == "float16"`. `check-probe` pins it too
(`--runtime torch --device mps --precision float16`); this read-back remains the cross-check,
because a pin can only compare what the ledger records. A mismatch is a halt, never a rerun under
the same id. A digest that does not match the committed document is the same halt: the run excluded
a different split than the one pre-registered.

## The 8B fit caveat (read before committing a night)

The probe draws against a declared sample and writes no checkpoint; it returns before the LoRA
capacity probe. It does not validate training — the generation/verifier chain is what it proves.
The 8B fit was measured by the `train-arm` pre-flight under § 10.21: a peak of 8.96 GB against
the 25.6 GB headroom
(`fits: True`) at about 118 s/step. A `CapacityExceeded` still writes no checkpoint and records
the finding; it never loosens the capacity check. Do not read a green probe as proof that the
repair selects a candidate.

## Before the night

1. **Empty the workspace.** `$REPO/runs/<torch-night-run-id>-workspace` must not exist or must be
   empty except the pre-warmed public digest dir (below); the probe's own must not exist or must be
   empty before its command. The run is not resumable from a partially deleted workspace.
2. **Declare the inputs.** `--run-id`, `--run-seed` and `--recorded-on` are typed by the operator
   before the run and written down in the operator's own log. None is read from a clock or
   generated. This sheet declares **two** run ids — `<torch-probe-run-id>` for the probe, then
   `<torch-night-run-id>` for the night — distinct tokens, never one reused for both.
3. **Run the probe first.** The chain is validated cheaply before a night is committed to.

## Going offline (before the probe)

The one public task (`pallets__flask-4045`) is processed last; both lost nights cloned it after
the Mac had slept and the network dropped. The run therefore takes the task's repository from a
local mirror, explicitly, and holds the machine awake.

The mirror is refreshed by hand — the only network use on this sheet:

```bash
git clone --mirror https://github.com/pallets/flask.git "$REPO/runs/flask-mirror.git"
export WHETSTONE_REPO_MIRRORS=$(printf '{"https://github.com/pallets/flask.git":"%s/runs/flask-mirror.git"}' "$REPO")
export UV_OFFLINE=1
```

If the mirror already exists, refresh it with `git -C "$REPO/runs/flask-mirror.git" fetch --all
--prune` instead of cloning. The `printf` builds the JSON with `$REPO` already expanded, so the
mapping the verifier subprocesses inherit is absolute. The mirror is an operator input, never
`~/.gitconfig`: the verifier still nulls the global and system config. It must contain the task's
`base_commit`; a stale mirror fails the detached checkout by name rather than silently reaching
GitHub. `UV_OFFLINE=1` makes a cold uv cache fail loudly before the run instead of reaching an
index mid-night.

## The probe pass

**Run with CWD at the primary checkout (`$REPO`):**

```bash
caffeinate -dimsu uv run --extra torch whetstone run --night \
  --probe 2 \
  --runtime torch \
  --repair 2 \
  --supervise \
  --stall-seconds 5400 \
  --tasks $REPO/tasks/local/donor-b \
  --tasks $REPO/tasks/local/donor-a \
  --public $REPO/tasks/public/instances \
  --pool $REPO/tasks/public/pool.json \
  --weights $REPO/weights \
  --only Qwen/Qwen3-8B \
  --runs $REPO/runs/torch-mps-probe \
  --checkpoints $REPO/checkpoints/torch-mps-probe \
  --workspace $REPO/runs/<torch-probe-run-id>-workspace \
  --timeout 900 \
  --recorded-on <declared-at-run-time> \
  --run-id <torch-probe-run-id> \
  --run-seed <declared-at-run-time> \
  --heldout $REPO/tasks/heldout/source-b.json \
  --dev-subset donor-b-2e149603209a \
  --dev-subset donor-b-353359e9ac6e \
  --dev-subset donor-b-3e3051c4192a \
  --dev-subset donor-b-844db07ed482 \
  --dev-subset donor-b-9dba3ea557f5
```

The probe writes no checkpoint — a probe that trained would produce a candidate from a self-chosen
subset. What it proves is the chain: the weights re-hash, the frozen contract, the control arm,
the held-out exclusion, the seeded draws, the per-draw journals and transcripts, the selection, and
the ledger. The stored `whetstone-run/3` record is read by `check-probe` through the verifying
reader the gate uses.

```bash
uv run --extra torch whetstone check-probe \
  --run $REPO/runs/torch-mps-probe/<torch-probe-run-id> \
  --heldout $REPO/tasks/heldout/source-b.json \
  --runtime torch \
  --device mps \
  --precision float16
```

The decision is the command's exit: `whetstone check-probe` reads the run directory the probe block
wrote (`runs/torch-mps-probe/<torch-probe-run-id>/ledger.json`) and, because the block passes
`--heldout`, compares the ledger's held-out digest to the committed document's. Exit 0 — the probe
satisfies the rule; proceed to the night. Exit 1 — a named finding (which draw/source, an empty
seed map, declared draws that are not `sampling.K`, a held-out digest that is not the committed
document's, or no held-out record at all); no night runs behind it. Exit 2 — a refusal an operator
can fix by retyping, including an unreadable `--heldout` document; never a verdict about the probe.

**Decision rule (pre-committed): the night proceeds iff the probe completes with the control arm
`PASS` on every draw and a non-empty seed map.** The declared draws must equal `sampling.K`
(`K = 16`, declared in `whetstone.loop.sampling`, never a flag), and the ledger's held-out record
must equal the digest of the committed `tasks/heldout/source-b.json`. A killed probe is **never
resumed** — restart it fresh under a new `<torch-probe-run-id>`; a killed **night** still resumes
unchanged (below).

## The pre-warm (after the probe, before the night)

The probe has already built the public task's digest dir. Copy it into the night workspace so
`provision` finds the checkout and the venv without a network:

```bash
mkdir -p "$REPO/runs/<torch-night-run-id>-workspace/environments"
cp -a "$REPO/runs/<torch-probe-run-id>-workspace/environments/b885fb84763091db" "$REPO/runs/<torch-night-run-id>-workspace/environments/"
```

The literal `b885fb84763091db` is the `Interpreters` key for the committed public manifest's pins
(python and pins only — the digest excludes the repo and commit), and a test cross-pins it. A
manifest pin change moves the digest, so the copy fails loudly instead of silently cloning. The
private tasks clone their local donors and need no pre-warm. The control arm and the oracle clone
into fresh destinations; those are covered by the mirror, not by this copy.

## The night

```bash
caffeinate -dimsu uv run --extra torch whetstone run --night \
  --runtime torch \
  --repair 2 \
  --supervise \
  --stall-seconds 5400 \
  --tasks $REPO/tasks/local/donor-b \
  --tasks $REPO/tasks/local/donor-a \
  --remine $DONOR \
  --remine-label donor-a \
  --remine-out $REPO/tasks/local/remined \
  --remine-limit 5 \
  --public $REPO/tasks/public/instances \
  --pool $REPO/tasks/public/pool.json \
  --weights $REPO/weights \
  --only Qwen/Qwen3-8B \
  --runs $REPO/runs/torch-mps \
  --checkpoints $REPO/checkpoints/torch-mps \
  --workspace $REPO/runs/<torch-night-run-id>-workspace \
  --timeout 900 \
  --recorded-on <declared-at-run-time> \
  --run-id <torch-night-run-id> \
  --run-seed <declared-at-run-time> \
  --heldout $REPO/tasks/heldout/source-b.json \
  --dev-subset donor-b-2e149603209a \
  --dev-subset donor-b-353359e9ac6e \
  --dev-subset donor-b-3e3051c4192a \
  --dev-subset donor-b-844db07ed482 \
  --dev-subset donor-b-9dba3ea557f5
```

Every flag verified against the shipped parser (`whetstone.cli.build_parser`) at write time. Notes
on the choices:

- **The night re-mines before it draws.** `--remine $DONOR` runs at the top of the night, before
  the corpus is loaded, so the set the generation contract freezes over is the grown one.
  `--remine-label` pairs by position with `--remine`, `--remine-out` names where new manifests
  land, and `--remine-limit` bounds how many candidates are attempted. The manifests land in a
  separate **training-only root** (`$REPO/tasks/local/remined`): it is gitignored and is **never**
  the committed corpus the held-out document is bound to. `--remine-limit 5` is the cost bound,
  not a target — mining is hours per candidate. A donor that mints nothing, is absent, or is
  unprovisionable is a no-op, never a failure: the night proceeds on the existing corpus and
  records an empty delta.
- **The probe does not re-mine.** Mining is hours, and the probe exists to validate the chain
  cheaply before a night is committed to. Its task set therefore differs from the night's by the
  re-mine delta; the pre-committed decision rule is about the control arm and the seed map, not
  the exact task set.
- **Denominator: 51 private (66 − 5 dev − 10 held-out not already dev-excluded) + 1 public = 52
  tasks, each drawn `K` times.** The exclusion order is dev overlay first, held-out second: the
  five declared dev ids leave both sources before anything is drawn, then the 12 held-out members
  leave what remains — 10 of them, the other 2 already in the dev band. A re-mine that adds tasks
  grows the denominator and is recorded in the ledger; the 52 is the committed corpus's count.
- **`K` is not a flag.** It is a declared constant in `whetstone.loop.sampling`. Raising it is the
  roadmap's named response to a low strict-PASS yield — as an edit to that line, in a diff, before
  a night, never as an argument on a command that has already run once.
- **Retries are ON by default**; there is no `--retries` flag to pass. The hardened contract is
  the one this night runs under, and the ledger records which contract ran.
- **`--timeout 900`** — headroom against a hung verification without letting one eat the night. A
  timeout is `UNVERIFIED`, never `FAIL`, and `UNVERIFIED` is never training data.
- **`--runs` and `--checkpoints` may not be inside a `reports/` directory.** A night writes the
  user's private donor code — prompts, completions, the training set and the adapter — and the
  door refuses that root for exactly this reason.
- **`--recorded-on` is an input, never the clock.** Writable paths are absolute or `$REPO`-anchored
  so no part of the run depends on CWD; the workspace is built and provisioned by subprocesses
  whose CWD is not the run's.

## A killed night

Restart the **same command, unchanged**, including the same `--run-id` and `--run-seed`. Each draw
index has its own journal under `runs/torch-mps/<torch-night-run-id>/draws/`, every completed
`(task, draw)` pair replays verbatim, and the control arm recorded beside it is reused rather than
re-run. Do **not** delete the run directory to "start clean": that discards the paid-for draws and
changes the experiment. Do delete and recreate the workspace if it is in an unknown state.

## After the night

Read, in this order:

1. `runs/torch-mps/<torch-night-run-id>/ledger.json` — the pinned inputs, the seed map, the
   held-out record (its digest **must equal** the digest of the committed
   `tasks/heldout/source-b.json`; a change is a halt, never a rerun), the per-draw harness status
   and counts, the dataset digest, and the checkpoint digest or the reason there is none.
2. `runs/torch-mps/<torch-night-run-id>/dataset.json` — the selected examples, each carrying its
   recorded strict-PASS verdict.
3. `runs/torch-mps/<torch-night-run-id>/data/train.jsonl` — what the trainer actually read.
4. `checkpoints/torch-mps/<torch-night-run-id>/provenance.json` — base revision, dataset digest,
   run seed, training args, tool versions, the capacity probe's record, and the validation
   sentence.

Then run the leakage check, at the seam, before the gate reads a candidate:

```bash
uv run --extra torch whetstone check-leakage \
  --run $REPO/runs/torch-mps/<torch-night-run-id> \
  --heldout $REPO/tasks/heldout/source-b.json
```

Exit 0 means source-B examples were compared and none shared a task identity with the held-out
membership; a leak exits 1 and names the task; a refusal exits 2 and names the reason. Either
non-zero exit halts here, before the gate.

## Halt conditions

1. **A uniform provisioning or checkout failure** hitting every draw — a harness defect, not a
   finding about the base. Stop, fix, restart from the empty workspace; quarantine the dead
   evidence by name, never delete it.
2. **`ContractChanged`** — a prompt the frozen contract does not carry reached the seal. The run
   is void and restarts from a single contract; do not resume it.
3. **`CapacityExceeded`** — the LoRA capacity probe measured a peak above the 25.6 GB headroom.
   That is a **published capacity finding** about this machine and this base, not a configuration
   to adjust: the night still completes, writes its ledger and dataset, records the finding, and
   writes no checkpoint.
4. **A zero strict-PASS yield.** This is **not** a halt: it is a legitimate, published outcome. The
   night completes, writes no checkpoint, states the empty outcome in the ledger, and exits
   non-zero. The 7B produced zero and so did the 8B (0 `SOLVED` in 816 private draws) without
   repairs; the repair contract is the response, and the probe may still yield zero. The next
   response is to raise `K` — in a diff, before the next night — never to loosen what counts as a
   win.

## The finding, and what is not published

The finding lives at `docs/planning/torch-mps-series/finding.md` — the gate decision, the
partition, the universal PEFT artifact, or the zero. The raw counts and the run's documents stay in
the gitignored `runs/` store, which is their only home. **Nothing here is published**: no
`reports/` path gains a directory from this series, and no figure from this night may be restated
as the MLX series' or as the arm's.
