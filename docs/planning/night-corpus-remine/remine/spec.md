# Spec — remine

**Aspect 1 of 4** for `night-corpus-remine` (`../prd.md`). Owns M1, M2, M4, M7 and S1 in full;
owns AC1, AC2, AC6 and AC7. **Unit:** `feat/night-remine-before-draw/aliz`
(`../understanding.md`). **Written:** 2026-10-11.

**Depends on:** nothing at the code level except the `record` aspect's `TaskSet.remined` field
(`../record/spec.md:31-53`) for the final ledger write. The skip-set and the `remine` wrapper
are independently landable and green against the current tree. **Provides:** the incremental
miner (`mine(skip=...)`), the `whetstone.loop.remine` module (`remine()` / `RemineReport`), the
`run_night` re-mine block and root union, and the `whetstone run --night` re-mine flags.
**Depended on by:** `record` (it consumes the minted pairs at the `TaskSet` seam), `guards` (it
asserts AC3/AC4/AC5 over the grown corpus), `docs` (S2 names the block).

## Problem slice and user outcome

The nightly loop reads a frozen corpus. `whetstone run --night` loads exactly the task
directories it is handed and never mints new ones — the only private-corpus read is
`load_task_roots(tasks)` at `src/whetstone/loop/night.py:240`. The miner
(`whetstone.tasks.mine.mine`, `src/whetstone/tasks/mine.py:154-165`) exists and is
operator-invoked only; nothing under `src/whetstone/loop/` imports it
(`../understanding.md:59-68`). So a night can only exhaust what the base already knows
(`../prd.md:19-24`).

This aspect makes the night grow the pool it learns from, **before it draws**, from the user's
own new commits, while the pre-registered held-out split stays exactly where it is. The
operator declares one or more donor repositories and labels on the night door; the night mines
only commits whose trailing-12-hex sha is not already in the corpus it will draw from, bounded
by a declared limit, into a separate training-only root, and unions that root into the corpus
`freeze()` computes the contract over (`src/whetstone/loop/night.py:299`).

Outcome: a night that started with N tasks can draw against N+M, where M is the number of new
fixable commits the donor grew since the last night, and the run ledger records which tasks
were added and from which donor (`record` aspect). Nothing new is a no-op, never a failure; a
night without the flags is byte-identical to today.

## In scope

### R1 (M1) — Incremental re-mine

`mine()` (`src/whetstone/tasks/mine.py:154-165`) gains exactly one keyword parameter
`skip: AbstractSet[str] = frozenset()`. When non-empty, a candidate whose
`candidate.sha[:12]` (`_ID_SHA_LENGTH`, `mine.py:73`) is in `skip` is **not attempted**. The
filter lives in `select()` (`mine.py:134-151`) — which already sorts before any shuffle
(`mine.py:148-150`) and ignores `limit` deliberately (its docstring, `mine.py:144-146`) — and
`mine()` forwards `skip=skip` at its `select(...)` call (`mine.py:197`). Default empty ⇒ the
selection and the mint are byte-identical to today, so the existing `whetstone mine` CLI path
(`src/whetstone/cli.py:996-1050`) and its tests (`tests/test_mine_cli.py`) are unaffected.

The sha is the candidate's own commit sha, never the donor's directory name or the label; the
identity a corpus is keyed by is the trailing 12 hex of a task id (`_mint`'s
`f"{label}-{candidate.sha[:_ID_SHA_LENGTH]}"`, `mine.py:295`; `check_leakage._identity`,
`src/whetstone/loop/check_leakage.py:494-507`).

**A held-out member can never be minted, and the skip-set is why.** `existing` (R2/R5) is the
sha12 set of the loaded `--tasks` corpus, and `exclude_heldout` (`night.py:253`) requires every
held-out membership id to resolve in that same corpus — so every held-out member's sha12 is
already in `skip` before the first candidate is considered. A re-mine therefore cannot reintroduce
a held-out task under any label, and `guards` pins this adversarially (its AC-G7): a donor whose
candidate sha collides with a held-out member is skipped, not drawn.

### R2 (M2) — Separate training-only root

A new module `src/whetstone/loop/remine.py` exposes:

```
remine(
    donors: Sequence[tuple[str, Path]],
    *,
    out: Path,
    limit: int,
    scratch: Path,
    timeout: float,
    existing: AbstractSet[str],
    seed: int | None = None,
    clock: Clock = utc_now,
) -> RemineReport
```

`donors` is a sequence of `(label, donor_path)` pairs. It calls `mine(...)` once per donor,
writing manifests into `out` and passing `tasks_root=<evidence>`, where `<evidence>` is a
**sibling** of `out`: `out.parent / (out.name + "-evidence")`, derived in one place. This is a
correction made during implementation (2026-10-11): `mine()` writes its own evidence *into
`tasks_root`* — `local-ledger.json` and `recipes/<label>.json` (`mine.py:397-453`) — while the
night's strict loader refuses **any** non-manifest entry in a root it loads
(`src/whetstone/tasks/manifest.py:69-85`, `load_task_directory`). So the evidence cannot live
inside the loaded root. With the sibling, manifests land in `out` (loaded, pure) and the re-mine's
evidence lands in the sibling (never loaded); neither touches the committed
`tasks/local-ledger.json` / `tasks/recipes/` (the declared-corpus record, `../prd.md:130-133`). It
passes the accumulated `existing` shas (plus every sha minted earlier in this call) as `skip`, so a
second donor in the same night cannot re-mint a commit the first one did.

`RemineReport` carries:

- `minted: tuple[tuple[str, str], ...]` — `(task_id, donor_label)` pairs, **sorted by
  `task_id`** — the seam the `record` aspect serializes;
- `donors: tuple[DonorOutcome, ...]` — a per-donor record: the label, the donor path, the task
  ids minted from it, the rejected `(sha, reason)` pairs, and an `absent` reason string (empty
  when the donor was read).

`out` is operator-named and lives outside `tasks/local/donor-a` / `tasks/local/donor-b`, whose
roots the committed held-out document's `corpus` is bound to by
`tests/loop/test_heldout_document.py:139`. Those roots are never written by a re-mine.

### R3 (M4, M7) — Nothing-new, absent, or unprovisionable is a no-op

A donor that mints nothing — because it has no un-minted candidates, because it is absent or
not a git repository (`MintFailed`, `mine.py:89-94`), or because it is unprovisionable
(`NotProvisionable`, `src/whetstone/tasks/environment.py:557-585`) — is a **no-op for that
donor**: `remine()` records it and continues, never raises. The night proceeds on the existing
corpus. `mine()`'s own per-candidate rejection discipline already absorbs a cold-cache
`NotProvisionable` per candidate (`mine.py:216-220`, returning
`MintReport(minted=(), rejected=..., ledger=None, recipe=None)` at `mine.py:219-220`); this
aspect additionally catches a wholesale `NotProvisionable` and `MintFailed` around each
`mine()` call, so an injected or genuinely unprovisionable donor is a reported no-op rather
than a crashed night (AC7). This deliberately does **not** inherit the CLI's `FAIL_EXIT` on
zero minted (`cli.py:1040-1046`).

### R4 (M7) — Cost-bound and offline

The re-mine is bounded by `limit` and by the night's `timeout` (passed through to `mine`'s
per-candidate `timeout`, `mine.py:207-209`). It runs offline: the miner reads the donor's local
history (`src/whetstone/tasks/donor.py:112-143`), `uv sync --offline` needs a warm cache
(`environment.py:236-254`), and `warm-cache` is the operator's separate network step. No new
network access is introduced anywhere in this aspect.

### R5 (M2) — The night unions the training-only root

`run_night` (`src/whetstone/loop/night.py:179-204`) gains four keyword parameters:
`remine_donors: Sequence[Path] = ()`, `remine_labels: Sequence[str] = ()`,
`remine_out: Path | None = None`, `remine_limit: int | None = None`. When `remine_donors` is
non-empty it runs the re-mine at the **top** of `run_night`, before `load_task_roots(tasks)`
(`night.py:240`), so the grown set is what `freeze()` (`night.py:299`) computes the generation
contract over. Specifically it:

1. loads the existing `--tasks` roots once to obtain the existing corpus's trailing-12-hex id
   set (`load_task_roots`, `src/whetstone/bakeoff/run.py:476-493`);
2. calls `remine(...)` with that set as `existing`, `out=remine_out`, `limit=remine_limit`,
   `scratch=workspace / "remine"`, `timeout=timeout`, `seed=run_seed`;
3. appends `remine_out` to the roots it will load **only if the operator did not already list
   it** (avoid double-loading, `../prd.md` M2), then loads the union fresh so tasks minted this
   night are picked up even when `remine_out` was already among `--tasks`;
4. passes the report's `minted` pairs to the ledger's `task_set` at the `record` seam.

A re-mine that mints nothing (`report.minted == ()`) lets the night proceed on the existing
corpus and records an **empty** delta (`()`, present), distinct from `None` (no re-mine ran) —
`../record/spec.md:39-43`.

### R6 (S1) — CLI shape

`whetstone run --night` gains `--remine <donor>` (repeatable, `Path`), `--remine-label
<label>` (repeatable, paired by position with `--remine`), `--remine-out <dir>` (`Path`) and
`--remine-limit <N>` (`int`), added to the night parser (`src/whetstone/cli.py:262-459`).
Validation happens in the `run_night` handler (`cli.py:1053-1111`) **before** the loop is
called:

- `--remine` and `--remine-label` must be used together and be equal length;
- `--remine-out` and `--remine-limit` are required when any `--remine` is given;
- `--remine-limit >= 1`.

A violation is a usage error (`USAGE_ERROR = 2`, `cli.py:114`) with a message naming the flag,
the `run_mine` limit-below-one precedent (`cli.py:1011-1017`). No re-mine flags ⇒ the call to
`conduct_night` passes the defaults and the night is byte-identical to today.

## Out of scope

- **The ledger field.** `task_set.remined`, its serialization and the no-flag byte-identity are
  the `record` aspect's (`../record/spec.md:29-118`). This aspect only computes the pairs and
  passes them at the seam.
- **Held-out, reward, gate, corpus record.** The held-out document and its split, everything
  under `src/whetstone/verify/`, the gate's rule/exits/retry discipline, and the committed
  66-task record (`tasks/local-ledger.json`, `tasks/recipes/`) are untouched (`../prd.md:169-178`).
- **A standalone `whetstone remine` command.** Deferred (`../prd.md:115-118`); the night-door
  block is the path.
- **Rendering the delta in the morning report.** `whetstone-morning/1` need not show it
  (`../record/spec.md:125-128`).
- **Determinism/invariant guard tests (AC3/AC4/AC5).** Owned by the `guards` aspect; this
  aspect only must not break them.

## Acceptance criteria (tests first)

Strict TDD: every criterion is a test that fails on the current tree and passes after the
change (`uv run pytest` green on the branch).

1. **AC1 (M1, M2)** — over the synthetic locked donor (`tests/fixtures/repos/donor.py` +
   `tests/fixtures/repos/locked.py`, the `tests/test_mine_cli.py:45-50` fixture pattern), a
   night with the re-mine flags mints the donor's un-minted candidates into the training-only
   root, and draws against them: at least one rollout record (`_rollout_ids`, the
   `tests/loop/test_night_integration.py:106-113` shape) carries a newly minted task id. The
   `(task_id, donor)` pair is present in the ledger's `task_set.remined`. (The ledger's own
   record is asserted here end to end; the `record` aspect asserts the serialization in
   isolation.)
2. **AC2 (M4)** — a donor with no un-minted candidates, or an absent donor, lets the night
   proceed on the existing corpus with an empty recorded delta (`task_set.remined == []`); the
   night does not raise and still writes its ledger.
3. **AC6 (S1)** — CLI validation: a `--remine` donor without a paired `--remine-label`, a
   `--remine-label` without a `--remine`, a re-mine without `--remine-out` or `--remine-limit`,
   and `--remine-limit 0` are each `USAGE_ERROR` (exit 2) with the offending flag named, never
   a silent default. The flags reach `run_night` with the names the loop declares.
4. **AC7 (M7)** — a cold-cache / unprovisionable donor is a reported no-op (the night
   proceeds), asserted against an injected miner that raises `NotProvisionable`, and against a
   real donor whose every candidate is refused `NotProvisionable` (no lockfile,
   `tests/test_mine_cli.py:345-372`).
5. **AC-R1 (M1, default empty)** — `select(pool, limit=n)` with no `skip` returns exactly the
   pre-change order (the existing `tests/test_mine_cli.py:244-286` assertions stay green
   unedited); `mine()` with an empty `skip` mints as before.
6. **AC-R2 (M2, seam)** — `remine()` calls `mine()` once per donor with `out=out`,
   `tasks_root=<out>-evidence`, the donor's `label`, and a `skip` set that accumulates every
   previously minted sha. The manifests land in `out` and the miner's `local-ledger.json` /
   `recipes/` land in the sibling evidence dir — never in `out` — so the night's strict loader
   accepts `out` even with the evidence present (the Phase 5 end-to-end assertion).
   `RemineReport.minted` is sorted by `task_id` regardless of minting order; the committed
   `tasks/local-ledger.json` / `tasks/recipes/` are never written (asserted on a synthetic root).
7. **AC-R3 (no double-load)** — when `remine_out` is already among `--tasks`, the night does
   not load it twice: the ledger's `task_set.roots` and `task_set.private` counts reflect the
   deduplicated union, and no task appears twice in the drawn set.

## Dependencies and sequencing

- **`record` first or alongside.** The final ledger write needs `TaskSet.remined`
  (`../record/spec.md:31-43`). This aspect can land the skip-set, the `remine` module and the
  `run_night` block before `record` lands, as long as the `TaskSet(remined=...)` call is added
  in the same commit that `record`'s field exists — or `record` lands first (it is
  independently green). See Open questions for the exact seam.
- **`guards` wraps this and `record`.** AC3 (determinism), AC4 (held-out invariant) and AC5
  (reward untouched, no-flag byte-identity) are `guards`' (`../prd.md:212-213`); this aspect
  must not break `tests/loop/test_heldout_document.py`,
  `tests/test_no_inference_on_reward_path.py` or the no-flag determinism.
- **`docs` last**, in the same commit as the night-sheet write-up (S2,
  `tests/test_night_runbook_guards.py`).

## Open questions and risks

- **🟢 Cross-aspect seam — resolved (2026-10-11, integrator).** The seam is the `TaskSet.remined`
  field, and `run_night` is its **single** writer: it computes `remined: tuple[tuple[str, str],
  ...] | None` (the `RemineReport.minted`, or `None` when no donors were given) and passes
  `remined=remined` into the `TaskSet(...)` at `night.py:374-382`. The `record` side's earlier
  `run_night(remined=...)` **input parameter is dropped** (its spec now says so), so there is one
  writer and one answer. The `TaskSet.remined` field itself is unchanged.
- **🟡 `task_set.roots` count.** Today `roots=len(tasks)` (`night.py:377`), the raw `--tasks`
  count. With a re-mine the honest count is the deduplicated union (`len(loaded_roots)`), which
  is identical for an unflagged night (`../record/spec.md` does not forbid the value moving for
  a flagged night). This spec plans `roots=len(loaded_roots)`; if the `record` aspect's
  byte-identity fixture asserts a fixed `roots`, confirm the value for the re-mine case.
- **🟡 `remine` seed.** This spec plans `run_night` passes `seed=run_seed` to `remine`, so the
  re-mine is a declared input and M8's determinism holds (same donor state + same seed). With
  `seed=None` the miner is also deterministic (oldest-first by sha, `mine.py:148`); the choice
  is a spec decision, not a correctness one.
- **🟡 The synthetic-harness id tolerance.** The `loop.harness` corpus ids (`"alpha"`, `"t-01"`,
  `tests/loop/harness.py:106-122`) do **not** end in 12 hex, so the `existing` sha extraction
  must be tolerant (`task_id[-12:]` / a regex-with-fallback, mirroring
  `check_leakage._identity` at `check_leakage.py:494-507` but never raising). A raising helper
  would make every `_night`-based test refuse.
- **🟡 `MintFailed` vs. `NotProvisionable` at the `remine` boundary.** `mine()` already absorbs
  per-candidate `NotProvisionable` (`mine.py:216-220`), so a cold cache normally surfaces as an
  empty `MintReport`, not an exception. This spec catches both at the `remine` boundary to
  satisfy AC7's injected-miner shape; the reviewer should confirm the extra `NotProvisionable`
  catch is wanted rather than folded into `MintFailed`.
- **🟢 No fetch.** The miner reads the donor's local history (`donor.py:1-6`); a donor not
  already up to date on disk mints nothing new — stated, not hidden (`../prd.md:146-147`).
- **🟢 Privacy.** The re-mine writes under gitignored `tasks/local/`, and the training-only root
  is operator-named outside the committed corpus; nothing new is committed
  (`../prd.md:143-145`).
