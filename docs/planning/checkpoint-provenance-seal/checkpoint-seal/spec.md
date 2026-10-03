# Spec — checkpoint-seal

**Unit:** `checkpoint-provenance-seal` · **Aspect 1 of 3** · **Sequencing:** first; the other two
consume what it returns.
**PRD:** `docs/planning/checkpoint-provenance-seal/prd.md` § 5 items 1–6.

## Problem slice and outcome

`provenance.json` seals its files and none of its claims. After this aspect, a v2 checkpoint's every
claim is covered by its `digest`, `verify_checkpoint` returns the claims it verified, and a v1
checkpoint verifies exactly as before and says it is not sealed.

## In scope

- `CHECKPOINT_SCHEMA_V2 = "whetstone-checkpoint/2"` beside the v1 constant in `loop/sft.py`.
- `write_checkpoint` writes v2: a `claims` map of `{key: sha256(canonical JSON of the value)}` for
  every top-level key except `schema`, `digest` and `claims`; `digest` reduces from the sorted
  `key:sha256` claim lines.
- `write_baseline_checkpoint` writes v2 for the untrained checkpoint.
- `verify_checkpoint` accepts both schemas. For v2 it re-hashes the files on disk (unchanged),
  recomputes each claim, and refuses by name: a claim whose hash moved, a key with no claim, a claim
  with no key, a digest that does not reduce from the claims.
- `Checkpoint` gains defaulted fields `base_repo_id`, `base_revision`, `dataset_digest` and
  `sealed`, filled from the single parse `verify_checkpoint` already does. `sealed` is `True` only
  for a v2 checkpoint that passed.
- Canonical JSON helper, with a test pinning its bytes.

## Out of scope

- Any consumer: `gate.py`, `card.py`, `check_leakage.py` (aspects 2 and 3).
- Re-sealing, migrating or deleting any v1 checkpoint.
- Validating `dataset_digest`'s shape (the gate keeps that check).

## Acceptance criteria (written first, as failing tests)

1. A v2 checkpoint round-trips: `write_checkpoint` then `verify_checkpoint` returns `sealed = True`
   and the same `digest`.
2. Editing each of `dataset_digest`, `base.repo_id`, `base.revision` and `backend` in a v2
   `provenance.json`, leaving `digest` alone, raises `CheckpointUnverified` whose message contains
   the name of the claim.
3. **Adversarial** — each of these fails under v2 and passes under the file-only seal:
   (a) an added top-level key absent from `claims`; (b) a claim and its key deleted together with
   `digest` unchanged; (c) two claims' hashes swapped; (d) the schema string rewritten to `/1`;
   (e) `untrained` flipped on an untrained v2 checkpoint.
4. A v1 checkpoint built in the `checkpoints/portability-arm` shape verifies and returns
   `sealed = False`, with `dataset_digest` and base populated from the document as recorded.
5. A v1 document is never reported sealed, including one that also carries a `claims` key.
6. Canonical JSON: a fixed document hashes to a fixed hex string pinned in the test.
7. `write_baseline_checkpoint` output verifies, returns `untrained = True`, `sealed = True`,
   `dataset_digest = None`.
8. The MLX-trainer path and the Torch-trainer path (stub trainers, no GPU) both produce a document
   with identical top-level keys and identical `claims` keys; a source-reading test asserts there is
   exactly one writer of `CHECKPOINT_FILE` for trained checkpoints.
9. An old reader refuses v2: the previous equality check on `whetstone-checkpoint/1` is exercised
   against a v2 document.
10. **Round trip:** a checkpoint whose document holds an int, a float, `None`, a nested mapping and a
    list verifies after being written, and the claims are hashed from the JSON round-tripped value.
11. Existing tests updated on purpose: `TRAINED_KEYS` pin, the wrong-schema value in
    `test_baseline_checkpoint.py:147`, and `_record_backend` in `test_gate_cli.py:258` (re-seals or
    states why it edits an unsealed v1 document).

## Dependencies and sequencing

None upstream. Aspects 2 and 3 import `Checkpoint`'s new fields.

## Open questions and risks

- Whether `run_seed`, `training_args`, `capacity_probe` and `validation` belong in `claims`: the PRD
  seals every top-level key, so yes; the plan confirms no key is excluded by accident.
- `bytes` in `files` is checked against disk but today is not part of the digest; as a claim of
  `files` it becomes sealed. Confirm no existing test depends on the old behavior.
