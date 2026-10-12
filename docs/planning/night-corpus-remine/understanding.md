# Understanding — night-corpus-remine

**Written:** 2026-10-11, Phase 2 of `wbf feat night-remine-before-draw`. Source: the inline brief
(`docs/planning/_card/issue.md`) and the four-agent dig over the worktree
`feat/night-remine-before-draw/aliz`.

## What the work is really asking

`docs/ROADMAP.md:794-800` (§ 13) states the gap: *"a night reads a frozen directory and never
re-mines. Expert iteration against a fixed task set converges by construction… Moving 'the night
re-mines before it draws' out of post-horizon is what makes the thesis mechanical instead of
aspirational."* The literal ask is to make `whetstone run --night` call the existing miner
(`src/whetstone/tasks/mine.py:154`) over the user's own repos before it loads its corpus, so a
night draws against tasks that did not exist last night.

The real ask underneath it is narrower and harder: **make the loop's training pool grow without
moving the pre-registered held-out split.** The brief already frames that boundary, but the dig
found the boundary is not where the brief assumes — the committed held-out document's `corpus`
field is bound to the *full* machine corpus by a recomputation test, so "grow the training pool"
and "leave the held-out document alone" are in direct tension and one of them must move.

## Core-loop placement, and guardrails

- **Element ② (nightly improvement loop).** The night grows the pool it learns from. The reward
  (①) does not change: nothing under `src/whetstone/verify/` or `tasks/`' reward boundary is
  touched, and the miner already lives under `src/whetstone/tasks/`, which the P1 AST guard
  (`tests/test_no_inference_on_reward_path.py`) already covers — a model still may not author the
  tasks, and re-mining real commits is explicitly *not* the declined proposer/solver generator
  (`docs/ROADMAP.md:797-812`).
- **Element ③ is constrained, not changed.** The held-out split is the never-regress gate's
  scoring input; the re-mine must leave its membership and `document_digest` fixed. A win is
  unchanged: `promoted` only on a proven gain with `unverified == 0`; `UNVERIFIED` is never a win.
- **Element ⑤ (local + private).** The miner is offline (`git` local clone, `uv --offline`) and
  needs the donor present locally; nothing leaves the box. This is the same constraint the miner
  already carries (`docs/planning/p1-task-ingestion/source-b-miner/spec.md:76-78`).

## The affected areas (from the dig)

**The mining path — `src/whetstone/tasks/mine.py`**
- `mine(donor, out, *, label, limit, scratch, tasks_root, timeout, seed=None, clock=utc_now) -> MintReport` (`mine.py:154`). Writes manifests to `out/<task_id>.json`, merges the liveness ledger
  `tasks_root/local-ledger.json` by task id, writes `tasks_root/recipes/<label>.json`.
- Task id = `f"{label}-{candidate.sha[:12]}"` (`mine.py:295`) — derived from label + mined commit
  sha, never the donor's directory name (#57).
- Proven-live = held set → environment capture → derive → liveness, i.e. **one fresh venv build
  and five sandboxed pytest runs per candidate** (`mine.py:265-322`); `uv sync --frozen
  --no-install-project --offline` (`environment.py:236-254`).
- **Cost is hours, not minutes** (`docs/planning/p1-task-ingestion/prd.md:374-376`,
  `source-b-miner/spec.md:74-75`); `--offline` requires a warm uv cache or every candidate is
  refused `NotProvisionable` with a WARM_REMEDY (`environment.py:557-585`); `warm-cache` is the one
  network step (`warm.py:1-35`).
- **No incrementality and no dedup.** `mine()` iterates `select(pool)` and breaks at `limit`
  (`mine.py:197-218`); a re-mine with the same limit and no seed re-attempts the same
  oldest-by-sha candidates, and `minted_at` (`mine.py:307,369`) makes the manifest bytes differ
  across calls. There is no "commits newer than the last mint" filter.
- Donor selection — `donor.candidates` (`donor.py:112-143`): HEAD history, oldest first, exactly
  one parent (no merges/root), ≥1 modified test `.py` and ≥1 non-test `.py`. Local path only; no
  fetch.

**The night door — `src/whetstone/loop/night.py`**
- `run_night(tasks: Sequence[Path], public, pool, weights, runs, checkpoints, workspace, timeout,
  recorded_on, run_id, run_seed, dev_subset=(), heldout=None, stratum=None, draws=K, …)` (`night.py:179-204`).
- The **only** private-corpus read is `load_task_roots(tasks)` at `night.py:240` — the natural
  insertion point for a re-mine is immediately before it, so the grown set is what gets loaded and
  what `freeze()` (`night.py:299`) computes the contract over.
- Overlay order (`night.py:240-297`): load full corpus → held-out resolve against the full corpus
  → `_partition` dev-subset → held-out exclusion → stratum resolve/filter → probe slice →
  `EmptyTaskSet` guard. `--tasks` is a repeatable list (`cli.py:277-288`), so a night can already
  union several corpus roots with no code change.
- Determinism — per-draw seed = `sha256(run_seed, task_id, attempt)` (`sampling.py:103-122`),
  `K = 8` a declared constant (`sampling.py:79`), dataset sorted by `(task_id, attempt)`
  (`dataset.py:311-325`). Byte-identity depends on the same loaded task set (ids and order),
  overlays, contract and engine. The brief correctly rescopes the determinism claim to "same donor
  state and seed"; the repo's own claim is already scoped to "a machine running one night"
  (`docs/planning/p2-rollouts/night-door/runbook.md:64-67`).
- Ledger `whetstone-run/3` (`ledger.py:60-63`) records `task_set{private,public,roots counts,
  dev_subset ids, probe, heldout record, stratum record}`, `seeds[]`, `dataset.digest`, etc.
  (`ledger.py:383-465`) — **no corpus membership list and no corpus digest.** A mint delta would be
  a new field under `task_set`; v3 seals every body key, so a new field is covered by the digest
  (`ledger.py:51-53`).

**The held-out / corpus seal — `src/whetstone/loop/heldout.py`, `PREREGISTRATION.md`**
- Only the **held-out split** is sealed and pre-registered: `document_digest` over
  `_DIGESTED_FIELDS` incl. `corpus` (66) and `membership` (12) (`heldout.py:234-244,321-334`;
  `tasks/heldout/source-b.json`). The training corpus membership is *recorded* (`tasks/local-ledger.json`,
  `tasks/README.md:8-11`, § 10.7/§ 10.16 prose) but not sealed as a whole.
- **The collision:** `tests/loop/test_heldout_document.py:139` asserts
  `len(tasks) == len(committed["corpus"])` where `tasks` is loaded from the primary checkout's
  `tasks/local/donor-b` + `tasks/local/donor-a` (`:47,91-110`). The document's `corpus` field is the
  population the split was drawn from, recomputed from the **full** machine corpus. Adding
  manifests to those two roots breaks this test — i.e. the committed document is bound to the full
  corpus, not only to the held-out membership.
- `check-leakage` matches by trailing-12-hex identity (`check_leakage.py:494-507`); new mined ids
  match nothing, so the overlap stays clean, and growth does not touch the document's bytes.
- `PREREGISTRATION.md` § 3 lists "the task set" among the pinned inputs, and a change "invalidates
  the series" (`:131-135`). Whether *training-pool* growth (as opposed to the **scoring** held-out
  set) is a "task set" change is **not stated anywhere** — the sharpest open question.

## Contradictions to surface (not paper over)

1. **§ 13 elevates a capability § 14 never ranks.** § 13:799 calls re-mining *"what makes the thesis
   mechanical instead of aspirational"*, but § 9's post-horizon list (`:598-603`) never named
   re-mining, and § 14's ranked path (`:836`) calls patch representation *"the only identified lever
   on the zero"* and lists what is *not* on the path (`:989-1000`) without mentioning re-mining.
   `docs/planning/whole-function-edit-finding/prd.md:245-246` classifies re-mining as a roadmap
   "gap … named, not built". So § 13 asserts a promotion out of a post-horizon list that never
   contained it.
2. **Two different mechanisms for "gets better over time".** § 13 says it needs *new verified
   tasks arriving*; `CLAUDE.md`/`VISION.md:41-46` attribute it to *base improvement + accumulated
   verified-improvement data*. These are different claims; § 13 does not reconcile them.
3. **The brief's "training pool ≠ headline denominator, so no amendment" is not settled by the
   docs.** § 3 pins "the task set"; the dig found no statement distinguishing the scoring task set
   from the training pool. This unit must state the boundary and, if it moves a pinned input, call
   for a Type 1 amendment rather than assert exemption.

## The design decisions the PRD must make (and my pre-read)

1. **Where do re-mined tasks live, given the recomputation test?** Preferred: a **separate
   training-only root** (e.g. `tasks/local/remined/…`) that the night unions via an extra
   `--tasks`, leaving `donor-a`/`donor-b` (the document's `corpus`) untouched. Alternative —
   grow `donor-a`/`donor-b` and re-derive the document — is a Type 1 amendment that re-rolls the
   split (§ 10.16's whole point), so it is out of scope unless the user chooses it.
2. **Incrementality.** The re-mine must select only candidates not already in the corpus (by sha12
   vs `local-ledger.json` / the loaded roots); otherwise it re-pays hours for the same tasks. This
   is new miner behaviour (a "new candidates only" filter), not a call to `mine()` as written.
3. **Cost bound.** A re-mine must be bounded (a declared limit and/or a wall-clock budget) so a
   night stays a night; the miner is offline and needs a warm cache. Options: a `--remine` block on
   the night door with `--remine-limit` / donor paths / labels, or a pre-night command whose delta
   the night consumes.
4. **The delta in the ledger.** Record, under `task_set`, the ids (or a digest + count) of tasks
   added this night, so a reader can attribute the training set to a corpus that grew. Task ids in
   the ledger are already acceptable (`seeds[]` carries them); no file contents.
5. **Determinism scoping.** State the claim precisely: same donor state + same seed → byte-identical
   training set; a donor that advanced changes the set by construction, and that is the point.

## Open questions (for the interview / review gate)

- **Q1 — boundary.** Is training-pool growth a § 3 pinned-input change (→ Type 1
  `PREREGISTRATION.md` amendment), or is § 3's "task set" the *scoring* held-out set only? Either
  way the PRD must say so explicitly.
- **Q2 — placement.** Separate training-only root (recommended) vs. growing the document's corpus
  roots and re-deriving the held-out document.
- **Q3 — shape.** A re-mine flag/block on `whetstone run --night` vs. a standalone `whetstone
  remine` the night consumes. Which keeps "one night, one command" true?
- **Q4 — scope of the first slice.** Full auto-mine inside the night, or a bounded first slice that
  proves the increment (new tasks → ledger → drawn) against a synthetic donor, with the real
  donor run left to the operator?
- **Q5 — empty delta.** Is "the donor minted nothing" a reported no-op (brief AC2) and never a
  non-zero exit, and does it still emit the ledger's corpus record?

## What this unit is not

- Not a change to the reward, the gate's rule/exits/retry discipline, the held-out membership, or
  any schema's meaning.
- Not re-deriving the held-out split (that is § 10.16, already spent; re-running it re-rolls the
  membership and drops the series).
- Not a task generator — the declined proposer/solver loop (`docs/ROADMAP.md:809-812`) stays
  declined; only the user's own commits are mined.
- Not a claim about yield: a bigger pool says nothing about whether any candidate improves.
