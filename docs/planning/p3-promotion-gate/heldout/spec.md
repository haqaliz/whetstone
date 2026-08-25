# Spec — heldout (aspect 1 of p3-promotion-gate)

**PRD:** `../prd.md`. **Branch:** `feat/p3-promotion-gate/aliz`. This aspect ships the held-out
document and its loader — the artifact `PREREGISTRATION.md` § 7.1 names open until P3 — plus the
§ 7.1 Type 1 amendment that closes the item. It is the foundation every other aspect consumes.

## Problem slice and user outcome

The held-out split does not exist, and § 7.1's closure rule is a dated amendment committed
**before the split is used to score anything** (`PREREGISTRATION.md:242-247`). The user outcome is
a committed, digest-guarded document declaring which source-B tasks are held out, fixed before any
scoring touches it, with a loader that refuses anything but the exact committed bytes.

## In-scope requirements

1. **The non-degeneracy rule is pre-committed in this spec, before the split is computed** (the
   stratum-band discipline): a split that cannot meet it is the § 7.1 published finding — written
   and committed — never a criterion tuned after the fact.
   - `HELDOUT_BANDS = 3` — the 66 source-B tasks ordered into terciles by the stratum document's
     per-task difficulty measurement (`tasks/stratum/easier.json`: files / hunks / added+deleted),
     the measurement reused as the ordering key, never a new difficulty axis.
   - `MIN_HELDOUT = 10`, `MIN_PER_BAND = 2` — a valid split has at least 10 held-out tasks and at
     least 2 from each band.
   - Selection: per band, tasks sorted by `sha256(split_seed, task_id)` (the stratum split's
     determinism precedent), taking the first `max(MIN_PER_BAND, ceil(MIN_HELDOUT / 3))`; the split
     seed is a declared constant. Recomputation is deterministic and reproducible.
2. **The document** at `tasks/heldout/source-b.json`, schema `whetstone-heldout/1` (the
   `tasks/stratum/easier.json` shape): rule digest (rule source + band + floors + seed, so any rule
   edit invalidates the document by design), the declared constants, the 66-task corpus with
   per-task difficulty and per-task band, membership, refusals, and a `document_digest` the loader
   refuses a hand-edit of. Counts and membership ids only — never paths, never task contents (the
   ledger's locality discipline, walked with a canary).
3. **The loader** in `src/whetstone/loop/heldout.py`, fail-closed by name: `HeldoutSchemaError`,
   `EmptyHeldout` (empty or whole-corpus, in the writer as well), `HeldoutDigestMismatch`, an
   unknown field refused, a duplicated membership refused, a member the document refused rather
   than measured refused. The membership recomputation test re-derives the document from the
   machine corpus field by field, skipping in CI with a reason naming exactly what is missing (the
   stratum precedent).
4. **The write door** `python -m whetstone.loop.heldout --corpus <roots> --out <path>` (the stratum
   door's shape). Refuses a degenerate split by name instead of writing one.
5. **The § 7.1 Type 1 amendment** — a dated entry in `PREREGISTRATION.md` § 10 closing § 7.1 under
   § 8.1 (Type 1), committed as its own change, before the split is used to score anything. It
   states the split size, the stratification rule, and the document location. It introduces no
   proportion in any spelling, no success threshold, and edits nothing above § 10 — `tests/test_docs.py`
   is the arbiter and must stay green (run the amendment against it; adjust wording to the guard,
   never the guard to the wording).

## Out-of-scope boundaries

- No scoring uses the split in this aspect — that is `gate-core`'s and P4's.
- No § 7.3 closure, no § 3 baseline measurement.
- No change to `src/whetstone/verify/`, `src/whetstone/tasks/`, `patch.py`, `attribution.py`
  (the AC2 pins stay byte-identical to `origin/master`).

## Acceptance criteria (testable)

- AC1: the writer produces `tasks/heldout/source-b.json` meeting the pre-committed rule (≥
  `MIN_HELDOUT` total, ≥ `MIN_PER_BAND` per band) or refuses by name and the finding is written
  instead; the loader reads back the exact committed bytes.
- AC2: a hand-edited membership (digest not regenerated), an unknown field, a duplicated
  membership, and an empty/whole-corpus document are each refused by name.
- AC3: the membership recomputation test re-derives the document field by field from the machine
  corpus (skips in CI naming what is missing).
- AC4: the § 7.1 Type 1 amendment is in `PREREGISTRATION.md` § 10, dated, recorded in the log with
  type "1 — closes an open item", and `tests/test_docs.py` stays green with the amendment in place.
- AC5: the canary holds — donor source text cannot reach the document.
- AC6: `uv run pytest` green; ruff and mypy over `src/` green.

## Dependencies and sequencing

- Depends on the machine corpus (`tasks/local/`, primary checkout — the document's recomputation
  test skips without it) and on the stratum document's per-task difficulty (the ordering key).
- Sequence: pre-committed rule in code → writer + document → loader + refusals → § 7.1 amendment →
  write-up. Feeds: `night-integration`, `gate-core`, `check-leakage`.

## Open questions / risks

- The amendment wording must pass `tests/test_docs.py`'s no-proportion guard; if the guard refuses
  "N of 66" phrasing, reword as a count statement without a bare proportion — the guard is the
  arbiter, never an edit target.
- Whether the split lands at all (degenerate corpus) is a real possibility: 66 tasks across 3
  bands with `MIN_HELDOUT = 10` is feasible but not certain — the finding path is part of this
  aspect's deliverable, not an error state.