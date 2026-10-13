# Spec — guards

**Aspect 3 of 4** for `night-corpus-remine` (`../prd.md`). Owns **AC3 (M8)**, **AC4 (M5)** and the
**reward half of AC5 (M6)** — the cross-cutting invariants, never the mechanism. **Unit:**
`feat/night-remine-before-draw/aliz` (`../understanding.md`). **Written:** 2026-10-11.

**Depends on:** the `remine` aspect's `run_night` re-mine block and root union
(`../remine/spec.md:115-135`), the `record` aspect's `TaskSet.remined` field
(`../record/spec.md:31-53`), and the `whetstone.loop.remine` module (`../remine/spec.md:57-91`).
**Provides:** the tripwires that prove the re-mine cannot move the held-out split, cannot reach the
reward, and cannot vary a training set over a fixed donor state. **Depended on by:** nothing; this
is the last code aspect before `docs`. **Lands last of the three code aspects** — it is red on the
current tree by construction (it calls `run_night(remine_*=...)` and `whetstone.loop.remine`, both
of which do not exist yet), and green only once `remine` and `record` have landed.

## Outcome

A reader of the night-corpus-remine unit can state, from tests that would fail if the property
broke:

1. two nights over the **same donor state and the same seed** produce byte-identical
   `dataset.json` and `train.jsonl` (M8);
2. a re-mine leaves the committed held-out document's `membership` and `document_digest`
   byte-identical, `whetstone check-leakage` behaves as before on the night's `dataset.json`, the
   recomputation test stays green, and the re-mine writes nothing under the donors' roots (M5);
3. the diff touches nothing under `src/whetstone/verify/` and
   `tests/test_no_inference_on_reward_path.py` stays green (M6);
4. a re-mine that would mint a task whose trailing-12-hex identity collides with a held-out member
   cannot leak it into training — the collision is excluded, never drawn (the adversarial proof).

**Not** in this aspect: the CLI, the miner, the ledger field, the docs. Those are `remine`,
`record`, `docs`.

## In scope

### R1 (M8) — determinism scoped to donor state

Two nights over the same donor state and the same `run_seed` produce byte-identical
`runs/<id>/dataset.json` and `runs/<id>/data/train.jsonl`. This is the existing criterion
(`tests/loop/test_night.py:190-215`, `test_the_same_seed_produces_a_byte_identical_training_set`)
extended to a night that **re-mined**: the pool grew by the same tasks, the draw order is the same,
and the written bytes are the same.

The claim is scoped exactly as the PRD scopes it (`../prd.md:103-105`): same donor state + same
seed. A donor that advanced changes the set **by construction** and that is the point — no test
here asserts determinism across a changed donor. The repo's own determinism basis is
`sha256(run_seed, task_id, attempt)` (`src/whetstone/loop/sampling.py:103-122`) and the dataset's
`(task_id, attempt)` sort (`src/whetstone/loop/dataset.py:311-325`), both already pinned; this
aspect pins that the re-mine does not perturb them.

The test uses the **injected miner** (`monkeypatch` on `whetstone.loop.night.remine`) so the
determinism asserted is the **night's**, not the miner's, and the test costs no provisioning: the
fake is a pure function of the donor state it is handed (it writes the same manifest and returns the
same pairs every call), which is exactly "same donor state". The real miner's determinism is
`remine`'s AC-R1 (`../remine/spec.md:192-194`) and `test_mine_cli.py`'s, not this aspect's.

### R2 (M5) — the held-out invariant

Before and after a re-mine:

- the **committed** held-out document `tasks/heldout/source-b.json` is byte-identical (its
  `membership` and `document_digest` included) — the re-mine writes only under the operator-named
  training-only root, never under `tasks/` (`../prd.md:82-84,140-142`);
- `whetstone check-leakage` on the night's `dataset.json` exits as before — a clean night stays
  clean, because a re-mined task id matches no held-out member (`src/whetstone/loop/check_leakage.py:494-507`
  matches by trailing-12-hex identity);
- `tests/loop/test_heldout_document.py` stays green, **unedited** — its recomputation
  (`:129-164`) re-derives the document from the **primary checkout's** `tasks/local/donor-a` and
  `donor-b` (`:47,91-110`), so a test that mines into a **separate** training-only root must not
  disturb those roots;
- the donors' roots are **never written**: the re-mine root is asserted distinct from, and not
  nested under, `tasks/local/donor-a` / `tasks/local/donor-b`, and a before/after walk of the
  primary's donor roots (when present) is unchanged.

### R3 (M6) — the reward is untouched

The diff touches nothing under `src/whetstone/verify/`, and
`tests/test_no_inference_on_reward_path.py` stays green. The miner already lives under
`src/whetstone/tasks/`, inside the AST guard's `GUARDED_ROOTS`
(`tests/test_no_inference_on_reward_path.py:104-109`), so the guard covers the re-mine path by
construction. `whetstone.loop.remine` is a **new module under the already-exempt `loop` package**
(`tests/test_reward_path_scope_is_partitioned.py:103-155`), so the partition guard needs no change
— but `remine` must not import an inference library, or the `loop` exemption's reason ("imports
`mlx_lm` legitimately") would be false for a module that needs none. This aspect adds a
source/diff-reading tripwire in the repo's style to make that executable.

### R4 — the adversarial proof (collision)

A re-mine that would mint a task whose trailing-12-hex identity collides with a held-out member
**cannot** leak it into training: the colliding task is excluded (or the night refuses), never
drawn. This is the repo's adversarial discipline — *"a verifier is only worth what it rejects"*
(`tests/adversarial/test_cheats.py:1-28`) — turned on the re-mine seam. The two identities that
must agree are the run-side exclusion, which matches membership **by exact task id**
(`src/whetstone/loop/heldout.py:726-749`), and `check-leakage`, which matches **by trailing-12-hex
identity** (`check_leakage.py:494-507`). A minted task that shares a held-out member's sha12 under a
   **different** label prefix is the shape that separates them; the test pins that it never reaches a
   rollout or the trainable partition. **Mechanism (resolved 2026-10-11, integrator):** the re-mine's
   skip-set is the loaded corpus's trailing-12-hex id set (`../remine/spec.md` R1/R5), and
   `exclude_heldout` (`heldout.py:726-749`) requires every held-out membership id to resolve in that
   same corpus — so every held-out member's sha12 is in `skip` before any candidate is considered,
   and a colliding commit is never minted. AC-G7 therefore asserts the skip-set the miner receives
   contains the held-out identity, and that the samely-identified task is absent from the rollout set
   and the trainable partition (the detector half proving the identity match is live).

## Out of scope

- **The mechanism.** `mine(skip=...)`, `whetstone.loop.remine`, the `run_night` re-mine block, the
  root union, the `--remine*` flags and their validation (`../remine/spec.md`). This aspect only
  asserts invariants over them.
- **The ledger field.** `TaskSet.remined`, its serialization and the no-`--remine` byte-identity
  (`../record/spec.md:31-118`). This aspect asserts the round-trip only where a guard needs it, not
  the field's bytes.
- **The docs.** The night sheet, STATUS, CHANGELOG, the ROADMAP § 13 note, the
  `PREREGISTRATION` boundary cross-reference (`../prd.md:212-215`).
- **Re-deriving the held-out split or editing the held-out document** — § 10.16 spent that
  (`../prd.md:169-174`).
- **A yield claim, a larger base, the gate, publishing** (`../prd.md:175-178`).
- **The no-`--remine` byte-identity of the ledger and dataset** — `record` owns the ledger half
  (`../record/spec.md:160-164`) and AC5's dataset half is covered here only as the unflagged
  control in R1.

## Acceptance criteria (tests first)

Strict TDD. Every criterion is a test that **fails on the current tree** (the `remine` parameters
and module do not exist) and **passes after `remine` + `record` land**; `uv run pytest` green on the
branch. All new tests live in the files named below and nothing else is edited.

1. **AC-G1 (M8) — two re-mine nights, one donor state, one seed, the same bytes.** Two nights
   through the `_night` helper (`tests/loop/test_night.py:85-121`, imported as
   `from loop.test_night import _night`) with the injected miner (`monkeypatch` on
   `whetstone.loop.night.remine`), the same `remine_out`, `remine_limit`, and `run_seed`, in two
   run roots, write byte-identical `dataset.json` and `data/train.jsonl`; and the injected miner
   receives the **same `existing` sha set and the same `seed`** in both runs (the "same donor
   state" half). The test also asserts the re-mined task is present (anti-vacuity: a byte-identity
   over an unchanged corpus proves nothing about the re-mine).

2. **AC-G2 (M5) — the committed held-out document is byte-identical across a re-mine.** Read
   `tasks/heldout/source-b.json` bytes (via `REPO_ROOT`, the `tests/loop/test_heldout_document.py:37`
   shape) before and after a re-mine night; assert equal. The document's `membership` and
   `document_digest` are the fields the assertion names in its failure message.

3. **AC-G3 (M5) — the re-mine writes nothing under the donors' roots.** Assert
   `remine_out.resolve()` is not `tasks/local/donor-a` / `donor-b` and is not nested under either;
   and, when the primary checkout's donor roots exist (`_primary_root`/`_machine_corpus` shape,
   `test_heldout_document.py:68-111`), a sorted recursive listing of each root before and after the
   re-mine night is unchanged. Skip with a reason when the machine-level corpus is absent (CI), the
   `test_heldout_document.py:100-109` precedent.

4. **AC-G4 (M5) — `check-leakage` behaves as before on a re-mine night's dataset.** Build a night
   that re-mined one task, run `check_leakage.run_check(night.directory, heldout_doc)` against a
   synthetic held-out document over the night's corpus, and assert the report is `clean` and that
   `check_overlap` did not raise (`NothingCompared`) — the re-mined id matched no member. The
   source-B example count is asserted non-zero (anti-vacuity), the
   `check_leakage.py:242-279` contract.

5. **AC-G5 (M5) — the recomputation test is green unedited.**
   `tests/loop/test_heldout_document.py` passes with **no edit to the file**; the guard test asserts
   the file's own recomputation still runs on a machine with the corpus, or skips with its own
   reason in CI (`:100-109`).

6. **AC-G6 (M6) — the reward path is untouched.** `tests/test_no_inference_on_reward_path.py` stays
   green unedited, and a new source-reading tripwire asserts: (a) no module under
   `src/whetstone/verify/` imports `whetstone.loop` (the reverse of the documented one-way edge,
   the `test_reward_path_scope_is_partitioned.py:409-443` shape); (b) the new
   `src/whetstone/loop/remine.py`, once present, imports no name in the AST guard's inference set
   (`tests/test_no_inference_on_reward_path.py:115-161`), reusing the guard's own
   `_is_inference_import`/`_imported_names` by import (the `test_reward_path_scope_is_partitioned.py:59`
   precedent). **If `src/whetstone/verify/` gained a change, or `remine.py` imports an inference
   client, stop and report** — the tripwire is the stop.

7. **AC-G7 (adversarial) — a colliding re-mine cannot leak a held-out task.** A new test under
   `tests/adversarial/` builds a held-out document whose membership contains a task id
   `donor-a-<sha12>` and a re-mine (injected) that mints a task `donor-x-<sha12>` sharing the
   trailing-12-hex identity under a different label. Assert the colliding id is **not** in
   `_rollout_ids(night)` and **not** in the trainable partition (`{example.task_id for example in
   night.dataset.examples}`); and, as the second half, a direct `check_leakage.run_check` over a
   dataset document carrying the colliding id **reports it as a leak** (proving the identity match
   is live, so the exclusion above is not a vacuous "it was never there"). The test's docstring
   states which half is the exclusion and which is the detector.

## Dependencies and sequencing

- **`record` and `remine` first.** This aspect is red until both land: AC-G1/AC-G2/AC-G3 call
  `run_night(remine_*=...)` (`../remine/spec.md:115-135`) and AC-G4/AC-G7 call
  `whetstone.loop.remine` and `whetstone.loop.check_leakage`. Land order: `record` (independently
  green, `../record/spec.md:200-206`) → `remine` → `guards` → `docs`.
- **No production change is expected.** The guards are tests plus one new test module; if a guard
  fires, the fix belongs to the aspect that owns the code (`remine` or `record`), and this spec must
  be amended to say which — never a silent edit to the guarded code.
- **`tests/loop/test_night.py`, `tests/loop/test_night_integration.py`,
  `tests/loop/test_heldout_document.py` and `tests/test_no_inference_on_reward_path.py` are
  tripwires and must stay green unedited.** A guard that edits its own subject proves nothing.

## Open questions and risks

- **🟢 The collision's mechanism — resolved (2026-10-11, integrator).** Option (a) of the earlier
  draft is chosen: the re-mine's `existing`/`skip` set is the **loaded corpus's** trailing-12-hex id
  set, and `exclude_heldout` (`heldout.py:726-749`) requires every held-out membership id to resolve
  in that same corpus, so every held-out member's sha12 is already in `skip` and a colliding
  candidate is never minted. No post-mine identity filter and no `run_night` change beyond passing
  `existing` are needed; the `remine` spec now states the argument (its R1). AC-G7 asserts the
  property through this mechanism (the injected miner receives a skip-set containing the held-out
  identity and mints nothing for it) plus the `check_leakage` detector half. No reduction is
  required.
- **🟡 Determinism vs. the real miner.** AC-G1 injects the miner, so it pins the **night's**
  determinism over a fixed donor state, not the real miner's. The real miner's determinism is
  `mine()`'s `select()` sort (`src/whetstone/tasks/mine.py:134-151`) and is covered by
  `test_mine_cli.py`. A macOS-only real-donor determinism test (one mint, `limit=1`, two nights) is
  a should-have; if added it belongs in `tests/loop/test_night_remine_integration.py`
  (`../remine/plan_20261011.md:354-397`), not here.
- **🟡 `remine` seed.** The determinism claim depends on `run_night` passing a declared seed to
  `remine` (`../remine/spec.md:237-240`). With `seed=None` the miner is oldest-first by sha and
  still deterministic; AC-G1 asserts only that the two runs' seeds **agree**, not their value, so
  it holds either way. Confirm the intended statement for M8.
- **🟢 Machine-level state.** AC-G2/AC-G3/AC-G5 need the primary checkout's `tasks/local/donor-a|b`;
  on CI they skip with a named reason (`test_heldout_document.py:100-109`). The invariant is still
  asserted structurally on the machine that generated the document, which is the runbook's own
  posture.
- **🟢 No fetch, no network.** Every guard runs offline against synthetic fixtures and `tmp_path`;
  nothing here warms a cache or reaches the network (`../prd.md:146-147,178`).
