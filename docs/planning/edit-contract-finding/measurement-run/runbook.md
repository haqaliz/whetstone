# Runbook — the measurement run (`python -m whetstone.bakeoff.measure`)

**Unit:** `edit-contract-finding` · **Aspect:** `measurement-run` · **Branch:** `feat/edit-contract-finding/aliz` ·
**Spec:** `docs/planning/edit-contract-finding/measurement-run/spec.md` — the pre-committed
rule this sheet commands. **Run from:** the primary checkout, after this unit merges. Every
path below is anchored to `$REPO`, so export it first — an exported variable expands before the
command runs, which is what makes the path the subprocess receives absolute:

```bash
export REPO=/absolute/path/to/whetstone   # the primary checkout, not a worktree
```

The operator's own path is not written here: a committed sheet that names one publishes a home
directory, and a reader re-deriving this run has a different one.

The operator's sheet for the unit's measurement: the driver spends one small real bake-off on
the pinned base under the numbered-listing prompt — the generation half of the edit-contract
finding — and the instrument classifies the completions by the pre-committed rule. Every
command here is run verbatim. A sheet that disagrees with the code it runs fails after a
GPU pass of an hour has been spent, so `tests/bakeoff/test_measure_runbook_guards.py` refuses
the disagreements first: the flags are checked against the shipped parsers, every path must be
absolute, the rule sentence and the population are pinned by identity, and the digest-equality
halt stands.

## What the run measures, and what it does not

The question the unit answers: **can the pinned base address a numbered listing?** The driver
prompts each of the 16 pre-committed tasks with a numbered listing of its oracle source files
and asks for `EDIT` blocks; the instrument classifies the completions by the pre-committed
ladder — `UNCLASSIFIED` (stays in the denominator) → `MALFORMED` → `NO_FILE` →
`OUT_OF_RANGE` → `ADDRESSABLE` — and decides by the strict-majority inequality the spec pins
before any rollout ran:

```
GO iff count(ADDRESSABLE) * 2 > population
```

The decision is the instrument's process exit: 0 GO / 1 NO-GO / 2 refused. A GO is a go/no-go
for **building the contract** — never a claim about yield, never a grade of correctness. The
proxies are disclosed in the finding: syntax-only grammaticality (`ast.parse`); addressability
is a necessary condition for the contract to help, never a prediction; and the run's
`prompt_sha256` is new — no run has ever prompted under a numbered-listing contract, so the
figures are comparable to nothing prior.

## Step 0 — preflight

1. **Serialize the GPU.** `mlx-lm` samples from process-global `mx.random` state, so a second
   process drawing on the same device perturbs this run's draws. That is a machine-level
   constraint and deliberately not a code fix: the machine-level GPU is serialized with any
   other run — one MLX process at a time, nothing else on the device beside it.
2. **Weights at the primary checkout.** `$REPO/weights` is machine-level, never fetched inside
   a worktree. The driver re-verifies every recorded sha256 in its provenance before a token
   is generated (`WeightsUnverified` is a refusal).
3. **`uv sync` once** in the checkout this sheet is executed from (at phase 5, the primary
   checkout, with this unit's code merged on `master`).
4. **The baseline suite is green**: `uv run pytest -q` — the suite this unit's phases left
   green is the floor the run starts from.

## Step 1 — the timing bound (the run is its own probe)

The plan's D7 discipline commands a cheap first pass before the real one. The driver has **no
probe path**: its population is pinned by identity — a task set that differs from the spec's 16
is refused, never narrowed — and no probe flag exists to invent here. So the run itself is the
bound, stated from committed metadata rather than guessed:

- `reports/larger-base/cost.json` records **16002.9 s** of generation, summed over that arm's
  rollouts (`reports/larger-base/report.md`, "Token spend");
- the PRD reads it as ≈ 258 s/task (M8), and the spec's R1 reads 16 × ≈ 258 s/task as
  **roughly 45–60 minutes of generation plus control-arm and verification time** (spec.md,
  "Open questions" — R1).
- The control fold adds one verifier probe per task under the `--timeout 900` headroom.

**Expected wall-clock:** ~45–60 minutes of generation plus the control fold — an evening's
hour, not a night. **Halt rule:** if generation grossly exceeds the committed bound (roughly
twice it, ~2 hours), stop and investigate: a throughput anomaly on a machine that is not the
one the cost was recorded on is a harness/machine finding, never a pass — and never a reason to
loosen the timeout.

## Step 2 — the measurement run

**Run with CWD at the primary checkout (`$REPO`):**

```bash
uv run python -m whetstone.bakeoff.measure \
  --tasks $REPO/tasks/local/donor-a \
  --tasks $REPO/tasks/local/donor-b \
  --stratum $REPO/tasks/stratum/easier.json \
  --heldout $REPO/tasks/heldout/source-b.json \
  --weights $REPO/weights \
  --only mlx-community/Qwen2.5-Coder-32B-Instruct-4bit \
  --workspace $REPO/runs/edit-contract-finding-workspace \
  --journal $REPO/runs/edit-contract-finding/journal.jsonl \
  --transcript $REPO/runs/edit-contract-finding/transcript.jsonl \
  --manifest $REPO/runs/edit-contract-finding/manifest.json \
  --recorded-on <declared-at-run-time> \
  --timeout 900
```

Every flag verified against the shipped parser (`measure.build_parser`) at write time. Notes on
the choices:

- **The population is not a flag.** It is the spec's pinned 16 — the stratum document's
  membership minus the held-out document's membership, by identity — and a run whose task set
  differs is refused (`PopulationMismatch`). The 16, as the spec names them:

  ```
  donor-a-128bcb99b701 donor-a-16213e62eae1 donor-a-2ef3383b0ce7
  donor-a-2f4e497580ff donor-a-34daf85182d5 donor-a-5e25b106874c
  donor-a-6005d7ec06f5 donor-a-7975de5439dc donor-a-b7c53b77453a
  donor-a-d601ff2d0ec0 donor-a-ec3af08b913d donor-a-f100a90e47f2
  donor-b-0f8651175ef8 donor-b-45740535725b donor-b-c57246c7841a
  donor-b-dbf19c8009dd
  ```

  A held-out member (`donor-a-6884ed72a9e9`, `donor-a-c6e4d4c4de87`, `donor-a-c7cee63e3cab`)
  is never a rollout target.
- **`--only` is passed exactly once, naming the pinned candidate**
  `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` (PREREGISTRATION.md § 10.10). The
  measurement is one base; a provenance naming several after selection is refused, never
  picked.
- **Writable paths are absolute.** `--workspace`, `--journal`, `--transcript` and `--manifest`
  name their files under the primary's gitignored `runs/` outright, so no part of the run
  depends on CWD. The workspace is built as `workspace / <sandbox>` and provisioned by
  subprocesses whose CWD is not the run's; the driver refuses a relative workspace by name
  (`RelativeWorkspace`), the runbook's known pitfall — the failure that killed the measured
  arm on 2026-08-12. **The workspace must not exist or must be empty at start**; the run is
  not resumable from a partially deleted workspace.
- **`--timeout 900`** — the night door's own value carried over unchanged: headroom against a
  genuinely hung verification without letting one eat the run. A timeout is `UNVERIFIED`,
  never a verdict — and the measurement never grades at all.
- **`--recorded-on` is an input, never the clock.** The run's id descends from the declared
  date, the candidate and the seed; a generated date would make two renders of the same
  documented command produce two run ids nobody chose.
- **The evidence home is gitignored.** `runs/edit-contract-finding/` is where the journal, the
  transcript and the manifest land — the transcript quotes the user's own donor code back
  verbatim, so it never enters the tree.
- **The run never enters the verifier for its rollouts.** Each journal row carries `outcome =
  UNVERIFIED` with the detail "measurement run — no grading performed by design"; the rows are
  not verdicts, and the manifest is the source of truth for population, candidate and prompt
  digests. The control arm is the real one — the same probe the night builds, through the
  shipped verifier — and the run refuses (`ControlNotIntact`) if the fold over every draw is
  not `PASS`, writing **no evidence**.

**Exit semantics.** Exit 0 only when all three are on disk: journal, transcript and manifest.
The three are written only when the whole run has succeeded — the manifest last, so its
existence is the exit-0 condition. A named refusal exits 2 with its reason on stderr and
**writes nothing**: a journal, transcript or manifest on disk is a document somebody quotes,
and it must not exist for a run that was void.

## Step 3 — the addressability instrument

Run after Step 2, still with CWD at the primary checkout. Offline, stdlib-only, deterministic —
no model, no network:

```bash
uv run python -m whetstone.bakeoff.addressability \
  --manifest $REPO/runs/edit-contract-finding/manifest.json \
  --transcript $REPO/runs/edit-contract-finding/transcript.jsonl \
  --tasks $REPO/tasks/local/donor-a \
  --tasks $REPO/tasks/local/donor-b \
  --stratum $REPO/tasks/stratum/easier.json \
  --heldout $REPO/tasks/heldout/source-b.json \
  --out $REPO/runs/edit-contract-finding/addressability.json
```

The instrument materialises two temp checkouts per task (~16 tasks) from the corpus dirs the
run used — the same gitignored `tasks/local/` roots — reads each completion's named files at
`base_commit`, classifies by the spec's ladder, and writes the document (schema
`whetstone-addressability/1`) with the partition, the sub-counts (replacements that parse but
the file would not import; blocks addressing a path outside the oracle listing), the rule
sentence, and the population. The manifest's task list must equal the pinned 16, and the
documents' digests must match the digests the manifest recorded — any disagreement is a
refusal.

**Exit semantics.** The decision is the process exit: 0 GO / 1 NO-GO / 2 refused. On exit 2
nothing is written and the finding is not written — investigate and re-run only with the same
inputs: the instrument is offline and deterministic, so a refusal names a fixable state (a
missing file, a changed document), never a verdict.

## Step 4 — the finding

On GO **or** NO-GO, write
`docs/planning/edit-contract-finding/measurement-run/finding.md`, stating:

- the decision and the exit (0 or 1);
- the population size (16);
- the partition in words, with the sub-counts beside it — never a table of the run's own
  counts, which live only in gitignored `runs/edit-contract-finding/`;
- the proxies: syntax-only grammaticality; addressability is a necessary condition, never a
  yield prediction; the run's `prompt_sha256` is new and comparable to nothing prior.

On **NO-GO**: record that nothing was built — the numbered-listing direction is also not the
wall, and the remaining roadmap responses are raising *k* and the portability arm's CPU dtype.
On **GO**: the checkpoint before the `numbered-listing-contract` aspect starts — the checkpoint
can stop a GO, it cannot turn a NO-GO into a GO.

**Counts live ONLY in gitignored `runs/edit-contract-finding/`** — this sheet's one home for
the run's figures, and counts never published into `reports/`.

## Halt conditions

1. **A changed pre-committed input.** The driver and the instrument both refuse a changed
   document by name: a changed spec, stratum document or held-out document is a halt, never a
   rerun. The population is pinned by identity, and a run over changed documents is a
   different experiment — find out by whom the document was changed.
2. **A driver refusal (exit 2).** The message names the cause: a relative workspace, a
   population that no longer subtracts to the pinned 16, a control fold not `PASS`, weights
   the disk does not support. A refusal is a halt, never a rerun with the inputs changed.
3. **A control fold not intact.** The run refuses and writes no evidence — nothing to read,
   nothing to classify. A verdict about a verifier that graded nothing is no verdict.
4. **Generation grossly exceeding the committed bound** (Step 1, ~2 hours). Stop and
   investigate; the machine is not the one the cost was recorded on. Never loosen the timeout
   to make it pass.
5. **An instrument refusal (exit 2).** Not a halt of the run's evidence — nothing is written
   and the finding is not written. Investigate the named reason and re-run only with the same
   inputs.

## A killed run

The driver appends at the end, deliberately: a killed run writes nothing, and restarting is
free. Delete and recreate the workspace (it may be in an unknown state) and run the **same
command, unchanged** — the same `--recorded-on`, the same paths — from the empty workspace.
Do not delete the run directory if the run completed: that discards the paid-for evidence.

## What this sheet does not authorise

- **No published figure.** Counts never published into `reports/`; the gitignored
  `runs/edit-contract-finding/` directory is their only home, and the finding states the
  decision, not the counts.
- **No loosening.** The timeout, the rule sentence, the population, the classes and the
  candidate are fixed; an amendment that would change any of them is a Type 1 amendment
  (PREREGISTRATION.md § 8.1), never a runbook edit.
- **No rerun loops.** A refused driver is never re-run until it passes; a changed document is
  a halt, never a rerun.
- **No second opinion.** One run, one instrument pass, one decision. The checkpoint on a GO
  can stop the contract aspect; it cannot revise the measurement.