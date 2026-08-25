# Runbook — the first gated evaluation (`whetstone gate`)

**Unit:** `p3-promotion-gate` · **Aspect:** `gate-runbook` · **Branch:** `feat/p3-promotion-gate/aliz` ·
**Worktree:** `/Users/aliz/dev/at/whetstone/.claude/worktrees/feat-p3-promotion-gate`

The operator's sheet for the first evaluation that decides whether a night's candidate may
replace the incumbent. Every command here is run verbatim. A sheet that disagrees with the code
it runs fails *after* a night has already been spent producing the candidate, so
`tests/test_gate_runbook_guards.py` refuses the disagreements first: the flags are checked
against the shipped parser, every path must be absolute, the retry budget must be the declared
constant, the promotion record's home must be the documented one, and the sheet must state the
liveness measurement.

## What the gate decides, and what it does not

The rule is fixed by `docs/ROADMAP.md:420-427` and this sheet cannot soften it:

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
  `/Users/aliz/dev/at/whetstone/checkpoints/night-002`.
- **Incumbent:** the checkpoint the candidate must beat —
  `/Users/aliz/dev/at/whetstone/checkpoints/night-001`.

Both are re-hashed by `verify_checkpoint` before anything is compared, so the decision is a
statement about the bytes on disk and not about the directory names above. A checkpoint whose
hash does not match its provenance refuses the run by name (exit 2).

The first gated evaluation therefore needs **two** nights: the shipped night writes one
checkpoint per night that selected something, and the gate compares two. Until a second night
has run, there is nothing to gate.

## Before the gate

1. **Serialize the GPU.** The gate generates one patch per held-out task per side through
   `mlx-lm`, which samples from process-global `mx.random` state. Run nothing else on the device
   beside it. The gate is greedy (`sampler_for(1)`), so this is about throughput and about not
   perturbing a concurrent night, not about the gate's own determinism.
2. **Empty the workspace.** `/Users/aliz/dev/at/whetstone/runs/gate-001-workspace` must not exist
   or must be empty. The gate resumes nothing.
3. **Declare the inputs.** `--recorded-on` and `--run-id` are typed by the operator and written
   down in the operator's own log. Neither is read from a clock or generated: a record that dated
   or named itself would differ between two renders of the same documented command.
4. **Verify the machinery first** (below). A machinery regression must be found before a night's
   candidate is spent on it.

## Step 1 — verify the machinery on the fixture pair

The gate's own suites run a known-better and a known-worse checkpoint pair through the whole
path — `verify_checkpoint`, the held-out loader, the scoring harness, the retry discipline and
the three exits — under the stub engine, on fixture checkpoints built by `write_checkpoint`
itself. This costs no GPU and takes a few minutes.

**Run with CWD at the primary checkout (`/Users/aliz/dev/at/whetstone`):**

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-p3-promotion-gate \
  pytest tests/loop/test_gate.py tests/loop/test_gate_cli.py tests/loop/test_gate_retry.py -q
```

**Halt if this is not green.** A red fixture suite means the gate is not the gate this sheet
describes, and no result it produces on the real pair may be recorded.

## Step 2 — the gated evaluation

**Run with CWD at the primary checkout (`/Users/aliz/dev/at/whetstone`), executing the branch
code via its project:**

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-p3-promotion-gate \
  whetstone gate \
  --candidate /Users/aliz/dev/at/whetstone/checkpoints/night-002 \
  --incumbent /Users/aliz/dev/at/whetstone/checkpoints/night-001 \
  --heldout /Users/aliz/dev/at/whetstone/tasks/heldout/source-b.json \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/belay \
  --tasks /Users/aliz/dev/at/whetstone/tasks/local/contig \
  --public /Users/aliz/dev/at/whetstone/tasks/public/instances \
  --pool /Users/aliz/dev/at/whetstone/tasks/public/pool.json \
  --weights /Users/aliz/dev/at/whetstone/weights \
  --runs /Users/aliz/dev/at/whetstone/runs \
  --workspace /Users/aliz/dev/at/whetstone/runs/gate-001-workspace \
  --timeout 900 \
  --recorded-on 2026-08-25 \
  --run-id promote-001
```

The promotion record lands at `runs/promotions/promote-001.json` — gitignored local evidence,
never published. It carries both re-hashed digests, the held-out document's digest, both sides'
counts over both denominators, the decision with every count it was read from, the retry
discipline's three facts, the tool versions, and `recorded_on`.

## Halt conditions

1. **Exit 2 — a refusal.** The message names the cause: a checkpoint whose bytes do not match
   its provenance, a held-out document whose digest does not match its contents, a membership id
   that matches no loaded task, or weights whose provenance the disk does not support. Fix the
   named thing and re-run with a **new** `--run-id`. Do not edit a document to make a refusal go
   away; a digest mismatch means the document was changed after it was sealed, and the response
   is to find out by whom.
2. **Exit 3 — `UNVERIFIED`.** The evaluation did not compare: at least one held-out task reached
   no verdict on one side, and it survived the retry budget of R = 3. This is a **published
   outcome, not a rerun**. Record it, read the liveness line, and treat the unverified set as the
   finding: `docs/ROADMAP.md:441-443` fixes the response — *if the gate proves unable to fire,
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

`docs/ROADMAP.md:441-442` makes liveness itself a measurement, so this line is read and written
into the operator's log every time — the unverified count over its denominator, never as a
proportion. A budget spent in full with tasks still unverified is a fact about the machine; a
budget never spent is a fact about the run. The two look identical in an exit code and different
in this line.

`R = 3` is the declared constant (`gate.RETRY_COUNT`), pinned by `PREREGISTRATION.md` § 10.8
(Type 1, 2026-08-25, closing § 7.2). It is not a flag: revising it needs a further dated
amendment grounded in a measured unverified rate, never a command-line choice.

## Step 3 — prove the night did not leak

The gate scores the held-out membership; this is what says that membership was never trained on.
Run it over the night that produced the **candidate**:

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-p3-promotion-gate \
  whetstone check-leakage \
  --run /Users/aliz/dev/at/whetstone/runs/night-002 \
  --heldout /Users/aliz/dev/at/whetstone/tasks/heldout/source-b.json
```

Exit 0 is required. Exit 1 names the leaked task and is **evidence of a regression in the
night's partition seam** — the fix is in the night that produced the run, and dropping the
leaked examples after the fact would leave the defect in place and print a clean result. A
promotion whose leakage was never checked is a promotion nobody may quote.

## Step 4 — read the record back

```bash
cat /Users/aliz/dev/at/whetstone/runs/promotions/promote-001.json
```

Into the operator's log, from the record itself and never from memory:

- the decision and its three terms (`solved_new`, `solved_old`, `regressed`, `unverified`), each
  over the shared denominator;
- both checkpoint digests, as re-hashed;
- the held-out document digest — it must equal the digest of the committed
  `tasks/heldout/source-b.json`, whose split is fixed by `PREREGISTRATION.md` § 10.7 (Type 1,
  2026-08-24, closing § 7.1);
- `retry_count`, `retries_used`, and `unverified_after_retries`;
- source A's counts beside source B's, both denominators disclosed.

## What this sheet does not authorise

- **No published figure.** `reports/` gains nothing from a gated evaluation. The promotion
  record is local evidence in its gitignored home, and `runs/promotions/` is the only home of
  these counts.
- **No threshold.** `PREREGISTRATION.md` pre-registers no numeric success bar, and an amendment
  may never introduce one. The gate rule is the whole of the decision.
- **No second comparison after a rejection.** One evaluation per candidate per incumbent. A
  candidate scored twice and reported once is the selection this project exists to refuse.
