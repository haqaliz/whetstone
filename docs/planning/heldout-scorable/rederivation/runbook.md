# Runbook — the #62 re-mint applied to the machine corpus (aspect 3, rederivation)

**Unit:** `heldout-scorable` · **Aspect:** `rederivation` · **Branch:** `feat/heldout-scorable/aliz` ·
**Executed once**, after the guard suite passes, on the operator's machine — the machine
that holds the real donors the pre-swap manifests name, the staged re-mint at the
primary's `_sandbox/remint/`, and the pre-swap corpus at the primary's `tasks/local/`.
The apply machinery
(`src/whetstone/loop/remint_apply.py`) exists only on this branch until merge, so every
command below runs with CWD at the **branch's worktree checkout**; `$REPO` always names
the **primary checkout**, whose gitignored `tasks/local/` and `_sandbox/` are the machine
state this sheet touches. The worktree's own path is never spelled — a committed sheet
that names `.claude/worktrees/<name>` sends a later reader to a directory that no longer
exists — it is exported from git's own words instead:

```bash
export REPO=/absolute/path/to/whetstone   # the primary checkout, not a worktree
export WORKTREE="$(git -C "$REPO" worktree list --porcelain | awk '$1 == "worktree" {print $2}' | sed -n '2p')"   # the branch's checkout (the second worktree)
```

The operator's own paths are never written here: a committed sheet that names them
publishes a home directory, and a reader re-deriving this step has different ones. The
real donor paths are recovered from the snapshot — the pre-swap corpus's own `repo_url`
values, paired per sha12 — never typed.

**Why this sheet exists, and what it does not do.** The #62 pairing requires the
held-out document to be re-derived exactly once over the re-minted corpus — ids
`donor-a-*` / `donor-b-*`, a provably identical commit set (same sha12s, same heads,
differing only in `task_id`, `provenance.donor`, `repo_url`) — so the donor's arbitrary
label stops deciding the split. This sheet applies the staged re-mint and re-derives the
three committed documents. It does **not** re-mine anything, does not change the donors'
locations, and does not loosen any rule: the guards and the recomputation test are the
gate, and the snapshot is the reversibility path.

## Step 1 — the guards pass before anything moves

**Run with CWD at the branch's worktree checkout:**

```bash
uv run pytest tests/test_remint_runbook_guards.py tests/loop/test_remint_apply.py -q
```

**Halt if this is not green.** The sheet is guarded exactly so that its commands cannot
drift from the machinery they invoke; a red guard suite means the sheet is not the sheet
the machinery proves, and no machine state may move.

## Step 2 — snapshot the pre-swap corpus (first, always)

The snapshot copies the pre-swap manifests and the committed ledger into
`$REPO/_sandbox/pre-remint` and writes the verification manifest — the old ids, their
sha12s, each manifest's sha256 and the ledger's digest. It is the reversibility
guarantee (spec AC10), and it lands **before** anything moves:

```bash
uv run python -c "from pathlib import Path; from whetstone.loop.remint_apply import snapshot_corpus; print(snapshot_corpus([Path('$REPO/tasks/local/donor-a'), Path('$REPO/tasks/local/donor-b')], Path('$REPO/tasks/local-ledger.json'), Path('$REPO/_sandbox/pre-remint')))"
```

**Halt if the snapshot refuses.** The refusal names the manifest or the ledger that did
not load; nothing has moved, and a pre-swap corpus that cannot be snapshotted must be
understood before it is swapped.

## Step 3 — verify the staged re-mint against the snapshot

Each check is asserted — 66 staged manifests, `donor-a-*` / `donor-b-*` label ids (each
embedding its own manifest's sha12), the commit set identical to the snapshot's, and the
staged ledger's 66 entries — and any mismatch is a named refusal **before any file
moves**:

```bash
uv run python -c "from pathlib import Path; from whetstone.loop.remint_apply import verify_staged; print(verify_staged(Path('$REPO/_sandbox/pre-remint'), Path('$REPO/_sandbox/remint')))"
```

**Halt if the verification refuses.** The staged re-mint is then NOT the provably
identical commit set the #62 pairing requires; report the named mismatch, never proceed.

## Step 4 — swap the manifests

Each corpus root's manifests are replaced with the staged re-mint's and the old-id files
are removed, so each root ends holding exactly the re-minted set:

```bash
uv run python -c "from pathlib import Path; from whetstone.loop.remint_apply import swap_manifests; print(swap_manifests([Path('$REPO/tasks/local/donor-a'), Path('$REPO/tasks/local/donor-b')], Path('$REPO/_sandbox/remint')))"
```

**Halt: double-apply.** If the swap refuses because a corpus root **already holds
donor-a-*** / donor-b-* manifests, the re-mint has been applied here already. Stop, and
do not re-verify the same bytes: the snapshot at `$REPO/_sandbox/pre-remint` is the
reversibility path, and the reason to refuse a second apply by name is that a silent
corpus change would make the amendment's "provably identical commit set" claim false.

## Step 5 — verify the swap

The swap leaves exactly the re-minted set: 66 manifests across the two roots, all
label-form ids, no old-id file remaining:

```bash
uv run python -c "from pathlib import Path; from whetstone.tasks.manifest import load_tasks; roots = [Path('$REPO/tasks/local/donor-a'), Path('$REPO/tasks/local/donor-b')]; tasks = load_tasks(roots[0]) + load_tasks(roots[1]); assert len(tasks) == 66, len(tasks); assert all(t.task_id.startswith(('donor-a-', 'donor-b-')) for t in tasks); print(len(tasks), 'manifests, all label-form')"
```

**Halt if the count or the ids are wrong.** The loader reads a whole directory and
nothing is skipped; a root with a stray or old-id file is a missing denominator, and the
snapshot restores the pre-swap corpus.

## Step 6 — rewrite repo_url to the real donors

The staged manifests' `repo_url` values point at the staging donors (`_sandbox/donors/`).
The real donor paths are the pre-swap corpus's own values, recovered from the snapshot
per sha12 — never typed here — and exactly one field per manifest is rewritten:

```bash
uv run python -c "from pathlib import Path; from whetstone.loop.remint_apply import real_donors, rewrite_repo_url; print(rewrite_repo_url([Path('$REPO/tasks/local/donor-a'), Path('$REPO/tasks/local/donor-b')], real_donors(Path('$REPO/_sandbox/pre-remint'), [Path('$REPO/tasks/local/donor-a'), Path('$REPO/tasks/local/donor-b')])))"
```

**Halt if the rewrite refuses.** An undeclared label, a sha12 the snapshot does not
carry, or a declared donor path that does not exist on this machine are each named
refusals; a rewritten `repo_url` must point at a donor the bakeoff can read.

## Step 7 — regenerate the ledger

The staged ledger's liveness evidence is reused — it was derived over the same commit
set, which Step 3 pinned — and each entry's `manifest_sha256` is recomputed from the
applied manifests, through `tasks.ledger`'s own reader and writer by identity:

```bash
uv run python -c "from pathlib import Path; from whetstone.loop.remint_apply import regenerate_ledger; print(regenerate_ledger([Path('$REPO/tasks/local/donor-a'), Path('$REPO/tasks/local/donor-b')], Path('$REPO/_sandbox/remint'), Path('$WORKTREE/tasks/local-ledger.json')))"
```

**Halt if the regeneration refuses.** A staged entry with no applied manifest, or an
applied manifest the staged ledger never names, is refused by name; never hand-roll a
ledger entry.

## Step 8 — re-derive the stratum document

Through the stratum module's own door, over the re-minted corpus, to the tracked
document:

```bash
uv run python -m whetstone.bakeoff.stratum --corpus "$REPO/tasks/local/donor-a" --corpus "$REPO/tasks/local/donor-b" --out "$WORKTREE/tasks/stratum/easier.json"
```

**Halt if the door refuses.** An unreadable donor is the bakeoff's own skip-with-reason
posture, recorded as a refusal inside the document — never guessed. A stratum document
that cannot be written is a named refusal with the door's words on stderr.

## Step 9 — re-derive the held-out document

Through the heldout module's own door, over the re-minted corpus, to the tracked
document. The door reads the stratum document at `tasks/stratum/easier.json` relative to
its CWD — which is why this sheet runs from the worktree, where Step 8's document now
sits:

```bash
uv run python -m whetstone.loop.heldout --corpus "$REPO/tasks/local/donor-a" --corpus "$REPO/tasks/local/donor-b" --out "$WORKTREE/tasks/heldout/source-b.json"
```

**Halt if the door refuses.** A task whose oracle cannot be decided at derivation time —
an unreadable donor, machine state — is `HeldoutUnscorable`, a refusal naming the task,
never a classification and never an exclusion. Report it by name; never work around a
refused donor.

## Step 10 — the recomputation is the gate

The recomputation test re-derives the held-out document from the committed rule and the
re-minted machine corpus and compares it field by field; the apply suite re-runs the
whole machinery over synthetic roots:

```bash
uv run pytest tests/loop/test_heldout_document.py tests/loop/test_remint_apply.py -q
```

**Halt if this is not green.** The recomputation test is the final document's gate (spec
AC8): a document that disagrees with its own rule on the same corpus is not a document
the gate may score against.

## Step 11 — commit the three tracked documents together

```bash
git add tasks/local-ledger.json tasks/stratum/easier.json tasks/heldout/source-b.json
git commit -m "rederivation: the re-minted corpus is live; ledger, stratum, heldout re-derived (TDD)"
```

Only the three tracked files land in the commit; the machine corpus (`tasks/local/`),
the snapshot (`_sandbox/pre-remint/`) and the staged re-mint (`_sandbox/remint/`) are
gitignored machine state and never committed. The aspect-2 held-out document
(`contig-*` / `belay-*` ids) is superseded by Step 9's document within this branch's
history — both states exist in the history, and no number is published from the
intermediate one.

## Halt conditions, gathered

1. **A guard or apply test is red** — the sheet is not the sheet the machinery proves;
   nothing moves until it is.
2. **The snapshot refuses** — a pre-swap corpus or ledger that cannot be snapshotted must
   be understood before it is swapped; nothing has moved.
3. **The verification refuses** — a count, id, sha12 or ledger-set mismatch names the
   offender; the staged re-mint is not the provably identical set.
4. **The swap refuses — double-apply** — a corpus root already holds donor-a-* / donor-b-*
   manifests; the re-mint has been applied already. Stop; the snapshot restores the
   pre-swap corpus.
5. **The swap verification fails** — not exactly 66 manifests, or an id that is not
   label-form; the loader reads a whole directory and nothing is skipped.
6. **The rewrite refuses** — an undeclared label, a sha12 the snapshot does not carry, or
   a declared donor path that does not exist; the real donors come from the snapshot,
   never a guess.
7. **The ledger regeneration refuses** — a staged entry with no applied manifest, or an
   applied manifest with no staged evidence; never hand-roll the ledger.
8. **A derivation door refuses** — the stratum or heldout door exits nonzero, naming the
   cause (an unreadable donor is recorded or refused by name); report it, never work
   around it.
9. **The recomputation is red** — the re-derived held-out document disagrees with its own
   rule on the re-minted corpus; nothing is committed.

## What this sheet does not authorise

- **No loosening.** The budget, the floors, the rule, the verifier and the gate's terms
  are untouched by this sheet; the re-mint changes ids and `repo_url`, never a rule.
- **No re-mining.** The staged re-mint is the faithful re-mint; the apply step verifies
  it, it does not re-derive it.
- **No intermediate commits.** Only the three tracked documents land in the phase-4
  commit; every other state this sheet touches is gitignored machine state.
- **No rerun after a refusal.** A refusal names the thing to fix; re-running the same
  command is selecting on the outcome. The snapshot is the only response to a botched
  swap.