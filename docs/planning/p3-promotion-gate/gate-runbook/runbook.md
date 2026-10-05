# Runbook — the first gated evaluation (`whetstone gate`)

**Unit:** `p3-promotion-gate` · **Aspect:** `gate-runbook` · **Branch:** `feat/gate-untrained-incumbent/aliz` ·
**Run from:** the primary checkout. Every path below is anchored to `$REPO`, so export it
first — an exported variable expands before the command runs, which is what makes the path the
subprocess receives absolute:

```bash
export REPO=/absolute/path/to/whetstone   # the primary checkout, not a worktree
```

The operator's own path is not written here: a committed sheet that names one publishes a
home directory, and a reader re-deriving this run has a different one.

The operator's sheet for the first evaluation that decides whether a night's candidate may
replace the incumbent. Every command here is run verbatim. A sheet that disagrees with the code
it runs fails *after* a night has already been spent producing the candidate, so
`tests/test_gate_runbook_guards.py` refuses the disagreements first: the flags are checked
against the shipped parser, every path must be absolute, the retry budget must be the declared
constant, the promotion record's home must be the documented one, and the sheet must state the
liveness measurement.

## What the gate decides, and what it does not

The rule is fixed by `docs/ROADMAP.md:431-433` and this sheet cannot soften it:

```
promote iff  solved_new > solved_old  AND  regressed == 0  AND  unverified == 0
```

Three exits: `promoted` → 0, `rejected` → 1, `UNVERIFIED` → 3. A refusal an operator can fix by
retyping is 2. **`UNVERIFIED` is never a promotion** — it means no comparison was actually made.

This sheet does **not** perform the `PREREGISTRATION.md` § 3 baseline measurement. That one
scores the untrained open base on the held-out split, is spent exactly once, and belongs to P4;
it also needs a checkpoint the night deliberately does not write (a night that selected nothing
writes no checkpoint at all). Nothing here consumes it.

## Candidate resolution (decided before the run)

Two explicit checkpoint paths, typed by the operator, and **no "current best" pointer**: a
symlink or a `latest/` directory would make the promotion record's provenance depend on the
state of a filesystem rather than on what the operator chose.

- **Candidate:** the checkpoint written by the night under evaluation —
  `$REPO/checkpoints/night-002`.
- **Incumbent:** the checkpoint the candidate must beat — the **untrained base** the night
  started from, materialized by the checkpoint writer in Step 2 below —
  `$REPO/checkpoints/incumbent-base-001`.

**§ 7.3 is closed** by the Type 1 amendment (`PREREGISTRATION.md` § 10.10). The incumbent is the 32B (`mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`),
the runbook-resolved candidate the night runbook retained on its evidence
(`docs/planning/p2-rollouts/night-door/runbook.md`): the only candidate with evidence, never a
base the pre-registration had pinned when this sheet was written. Materializing it as the
gate's incumbent is not a base selection; a change of base is a further Type 1 amendment.

**The candidate's night, and how it is found.** The gate takes a checkpoint and `check-leakage`
takes a run directory, and a leakage proof over any other night says nothing about this
candidate. The tie is the dataset digest: the night that trained the candidate is the one where
the checkpoint's `provenance.json` `dataset_digest` equals the night's `dataset.json` `digest`.
Step 3 hands `check-leakage` the checkpoint with `--checkpoint`, and the command compares the
two digests for you; write the night's id into the operator's log. For a **v2** checkpoint
(`whetstone-checkpoint/2`) the recorded digest is **sealed**: part of the checkpoint's own
digest, so the command reports the link as sealed. For a **v1** checkpoint it is **recorded, not
sealed**, and the command says so. Sealed means tamper-evidence against an edit that does not
also recompute the digest; it is not authentication, and it is not proof that the digest equals
the dataset the trainer read. The run's `dataset.json` is not sealed. None of this catches a
near-duplicate task (see Step 3). Here the candidate is `night-002`, and its night is
`$REPO/runs/nights/night-002` — the home the night door writes to.

Both are re-hashed by `verify_checkpoint` before anything is compared, so the decision is a
statement about the bytes on disk and not about the directory names above. A checkpoint whose
hash does not match its provenance refuses the run by name (exit 2).

The first gated evaluation therefore needs **one** night: the candidate is a single night's
checkpoint (the sheet's example types `night-002`) and the incumbent is the untrained base the night started from. This is the
gate's incumbent, **not** the § 3 baseline measurement: different roles, different homes
(`docs/ROADMAP.md:688-693`) — if the two figures disagree it is published as a finding,
never reconciled.

## Before the gate

1. **Serialize the GPU.** The gate generates one patch per held-out task per side through
   `mlx-lm`, which samples from process-global `mx.random` state. Run nothing else on the device
   beside it. The gate is greedy (`sampler_for(1)`), so this is about throughput and about not
   perturbing a concurrent night, not about the gate's own determinism.
2. **Empty the workspace.** `$REPO/runs/gate-001-workspace` must not exist
   or must be empty. The gate resumes nothing.
3. **Declare the inputs.** `--recorded-on` and `--run-id` are typed by the operator and written
   down in the operator's own log. Neither is read from a clock or generated: a record that dated
   or named itself would differ between two renders of the same documented command.
4. **Verify the machinery first** (below). A machinery regression must be found before a night's
   candidate is spent on it.
5. **Materialize the untrained incumbent** (Step 2 below) — the checkpoint writer, from the
   weights root's provenance.
6. **Prove the candidate's night did not leak** (Step 3 below) — before the gate, so a candidate
   that trained on the held-out membership is never scored against it.

## Step 1 — verify the machinery on the fixture pair

The gate's own suites run a known-better and a known-worse checkpoint pair through the whole
path — `verify_checkpoint`, the held-out loader, the scoring harness, the retry discipline and
the three exits — under the stub engine, on fixture checkpoints built by `write_checkpoint`
itself. This costs no GPU and takes a few minutes.

**Run with CWD at the primary checkout (`$REPO`):**

```bash
uv run pytest tests/loop/test_gate.py tests/loop/test_gate_cli.py tests/loop/test_gate_retry.py -q
```

**Halt if this is not green.** A red fixture suite means the gate is not the gate this sheet
describes, and no result it produces on the real pair may be recorded.

## Step 2 — materialize the untrained incumbent

The checkpoint writer (`sft.write_baseline_checkpoint`; the module has no door) records the
untrained base as a `whetstone-checkpoint/2` provenance over no adapter (every claim, `base`
among them, sealed into its digest), from the weights root's provenance — the 32B's `repo_id`
and its immutable revision:

```bash
uv run python -c "from pathlib import Path; from whetstone.loop.ledger import tool_versions; from whetstone.loop.sft import write_baseline_checkpoint; write_baseline_checkpoint(Path('$REPO/checkpoints/incumbent-base-001'), repo_id='mlx-community/Qwen2.5-Coder-32B-Instruct-4bit', revision='<the revision recorded in $REPO/weights/provenance.json>', tool_versions=tool_versions())"
```

The directory must be empty at materialization — the writer refuses a checkpoint that would
record an adapter beside a base that never trained.

## Step 3 — prove the candidate's night did not leak

The gate scores the held-out membership; this is what says that membership was never trained on,
and it runs **before** the gate: a candidate that trained on the held-out tasks, scored against
them, writes a promotion record for a comparison that was never fair. `docs/ROADMAP.md:459-460`
makes the clean exit a P3 exit criterion in its own right. Run it over the night found above:

```bash
uv run whetstone check-leakage \
  --run $REPO/runs/nights/night-002 \
  --heldout $REPO/tasks/heldout/source-b.json \
  --checkpoint $REPO/checkpoints/night-002
```

**Halt on any non-zero exit.** A non-zero exit halts the operator before the gate, which is not
run until this exits 0. `--checkpoint` can add a refusal (a tampered, untrained or foreign
checkpoint is exit 2) or a line saying the link is sealed or recorded, not sealed; it can never
change the leakage verdict.

- **Exit 0** — source B training examples were compared with the held-out membership by task
  identity (the trailing 12-hex of each id), and none shared one. A clean check means
  "no shared task identity", never "no contamination": a near-duplicate task — the same
  function, an adjacent commit — under a different identity is not detected. A run without a
  `ledger.json` is still checked and carries a notice saying so; read it into the log.
- **Exit 1** — a leak, named by task. It means one of two things, and you must find out which:
  (a) the night's partition seam failed to exclude held-out ids, or (b) the held-out document
  was derived or re-derived after the night ran (e.g. a corpus re-mint), so the night could not have excluded them. Do
  not assume either. Dropping the leaked examples after the fact would leave the defect in place
  and print a clean result. The candidate is not gated; never loop on this check hoping it comes back clean.
- **Exit 2** — a refusal: a run with no `dataset.json`, an id with no recognisable sha12 (a
  re-mint changed the id scheme, and an amendment is needed before the gate may run), a document
  that cannot be trusted — and a run that compared nothing (no source B training example) is
  exit 2 as well, because no identity was ever checked. Exit 2 is a halt. Fix the named cause
  and re-run the check; never proceed to the gate on it.

A refusal is never a pass. A check that did not run, or ran and compared nothing, is "not
checked", and a promotion whose leakage was not checked is a promotion nobody may quote.

## Step 4 — the gated evaluation

**Run with CWD at the primary checkout (`$REPO`):**

```bash
uv run whetstone gate \
  --candidate $REPO/checkpoints/night-002 \
  --incumbent $REPO/checkpoints/incumbent-base-001 \
  --heldout $REPO/tasks/heldout/source-b.json \
  --tasks $REPO/tasks/local/donor-b \
  --tasks $REPO/tasks/local/donor-a \
  --public $REPO/tasks/public/instances \
  --pool $REPO/tasks/public/pool.json \
  --weights $REPO/weights \
  --runs $REPO/runs \
  --workspace $REPO/runs/gate-001-workspace \
  --timeout 900 \
  --recorded-on 2026-08-25 \
  --run-id promote-001
```

The promotion record lands at `runs/promotions/promote-001.json` — gitignored local evidence,
never published. Its schema is `whetstone-promotion/3`. It carries both re-hashed digests, each
side's `training` block, the held-out document's digest, both sides'
counts over both denominators, the decision with every count it was read from, the retry
discipline's three facts, the tool versions, and `recorded_on`.

## Halt conditions

1. **Exit 2 — a refusal.** The message names the cause: a checkpoint whose bytes do not match
   its provenance, a held-out document whose digest does not match its contents, a membership id
   that matches no loaded task, weights whose provenance the disk does not support, or a trained
   candidate or incumbent whose recorded dataset digest cannot be read — in which case no
   record is written. Fix the
   named thing and re-run with a **new** `--run-id`. Do not edit a document to make a refusal go
   away; a digest mismatch means the document was changed after it was sealed, and the response
   is to find out by whom.
2. **Exit 3 — `UNVERIFIED`.** The evaluation did not compare: at least one held-out task reached
   no verdict on one side, and it survived the retry budget of R = 3. This is a **published
   outcome, not a rerun**. Record it, read the liveness line, and treat the unverified set as the
   finding: `docs/ROADMAP.md:451-453` fixes the response — *if the gate proves unable to fire,
   the fix is a more reliable sandbox, never a looser gate.* Re-running until an evaluation
   happens to verify is selecting on the outcome, and it would turn the honest third exit into a
   slower way of promoting.
3. **Exit 1 — `rejected`.** The candidate did not beat the incumbent, or it regressed a task the
   incumbent solved. Nothing ships. This is the gate working, not a problem to route around: the
   response is another night, never a second opinion from a looser comparison.
4. **A killed run.** The gate resumes nothing — it re-runs from the start. The promotion record
   writer **overwrites** the file at `runs/promotions/<run-id>.json`, so a re-run with the same
   `--run-id` destroys the killed run's partial evidence. Use a fresh `--run-id`
   (`promote-002`, …) and keep both records.

## The liveness measurement (read from the first evaluation onward)

The gate's output carries a `retries:` line on **every** run, spend or none:

```
retries: R=3, <spent> spent over <n> (side, task) pair(s); <u> of <d> held-out tasks still
without a verdict
```

`docs/ROADMAP.md:451-452` makes liveness itself a measurement, so this line is read and written
into the operator's log every time — the unverified count over its denominator, never as a
proportion. A budget spent in full with tasks still unverified is a fact about the machine; a
budget never spent is a fact about the run. The two look identical in an exit code and different
in this line.

`R = 3` is the declared constant (`gate.RETRY_COUNT`), pinned by `PREREGISTRATION.md` § 10.8
(Type 1, 2026-08-25, closing § 7.2). It is not a flag: revising it needs a further dated
amendment grounded in a measured unverified rate, never a command-line choice.

## Step 5 — read the record back

```bash
cat $REPO/runs/promotions/promote-001.json
```

Into the operator's log, from the record itself and never from memory:

- the decision and its three terms (`solved_new`, `solved_old`, `regressed`, `unverified`), each
  over the shared denominator;
- the schema — it must be `whetstone-promotion/3`; a `/1` or `/2` record is refused by every
  reader, never upgraded;
- each side's `training` block — `dataset_digest`, `base_repo_id`, `base_revision`, and
  `sealed` (whether that side's checkpoint seals the link; recorded information, never part of
  the decision). The
  candidate's `dataset_digest` must equal the night's `dataset.json` `digest` that Step 3
  checked; the untrained incumbent's is an explicit `null`, because nothing trained it. This
  block is copied from `provenance.json`: **sealed** for a v2 checkpoint (tamper-evidence, not
  authentication) and **recorded, not sealed** for a v1 one — the `sealed` field says which;
- both checkpoint digests, as re-hashed — the incumbent's is the untrained digest: for the
  `whetstone-checkpoint/2` checkpoint Step 2 writes it folds in `base`, so it differs per base;
  only a legacy `whetstone-checkpoint/1` untrained checkpoint carries the constant digest
  (sha256 over the empty file set, the same for every v1 untrained base). Either way the record
  is read by role and by base identity, never by digest equality;
- the held-out document digest — it must equal the digest of the committed
  `tasks/heldout/source-b.json`, whose split is fixed by `PREREGISTRATION.md` § 10.16 (Type 1,
  2026-09-27), re-derived under the scorable rule — a member is held out only if its oracle
  can be built under the declared budget, the exclusion sealed in the document's rule digest;
- `retry_count`, `retries_used`, and `unverified_after_retries`;
- source A's counts beside source B's, both denominators disclosed.

## Who writes the finding

The finding is written by the operator, from the promotion record and the `check-leakage`
output only — both quoted verbatim, each with its exit code, and nothing remembered or
re-derived beside them. It lives under `docs/planning/`, never `reports/`: a gated evaluation
publishes no figure, and the counts stay in the gitignored record. A finding that halted at
Step 3 says so and says that no gate was run.

## What this sheet does not authorise

- **No published figure.** `reports/` gains nothing from a gated evaluation. The promotion
  record is local evidence in its gitignored home, and `runs/promotions/` is the only home of
  these counts.
- **No threshold.** `PREREGISTRATION.md` pre-registers no numeric success bar, and an amendment
  may never introduce one. The gate rule is the whole of the decision.
- **No second comparison after a rejection.** One evaluation per candidate per incumbent. A
  candidate scored twice and reported once is the selection this project exists to refuse.
