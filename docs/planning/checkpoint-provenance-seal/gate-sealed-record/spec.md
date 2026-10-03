# Spec — gate-sealed-record

**Unit:** `checkpoint-provenance-seal` · **Aspect 2 of 3** · **Sequencing:** after `checkpoint-seal`.
**PRD:** `docs/planning/checkpoint-provenance-seal/prd.md` § 5 items 7, 8, 11.

## Problem slice and outcome

The gate and the model card re-open `provenance.json` after it was verified, and the promotion
record cannot say whether the dataset link it records was sealed. After this aspect, both consume the
verified `Checkpoint`, and the record carries `sealed` per side under `whetstone-promotion/3`.

## In scope

- `gate._checkpoint_base`, `_checkpoint_dataset_digest` and `_checkpoint_training` take their values
  from the `Checkpoint` returned by `verify_checkpoint`; they no longer open `provenance.json`.
  The malformed-digest refusals (`DatasetDigestUnrecorded`: empty, null, int, list, short, long,
  non-hex, uppercase, whitespace) are kept as they are.
- `TrainingProvenance` gains `sealed: bool`; `_training_payload`, `_PROMOTION_TRAINING_FIELDS` and
  `_record_training` carry it; `PROMOTION_SCHEMA = "whetstone-promotion/3"`.
- `read_promotion_record` refuses `/2` with its own message (as `/1` is today) and any other schema.
- `card.py` builds from the verified `Checkpoint` rather than `json.loads` of the raw file.
- Every sentence reading "recorded, not verified" in `gate.py` (`:328`, `:937`, `:1105`, `:1633`,
  `:1657`) says what is now true: sealed for v2, recorded and not sealed for v1. So do the
  "same constant for every untrained base" docstrings at `gate.py:280`, `baseline.py:38-40` and
  `:169-171`, which hold for v1 only.
- Should-have: the gate's printed output names a side whose link is not sealed.

## Out of scope

- The decision logic, exits, retry discipline, denominators and the morning/honest-number report's
  reading of counts. `morning.py` and `honest_report.py` are not edited beyond the error wording a
  `/2` refusal needs.
- Making `sealed` a condition of promotion. It is recorded, never decisive.

## Acceptance criteria (written first)

1. A v2 candidate and a v2 incumbent produce a `/3` record with `sealed: true` on both sides.
2. A v1 candidate produces `sealed: false` and the gate's decision for the same counts is identical
   to a v2 candidate's (the differential test: same fixtures, two schemas, byte-identical `decision`
   block).
3. An untrained incumbent records `dataset_digest: null` and `sealed` as its checkpoint reports.
4. A `/2` promotion record is refused by `read_promotion_record`, `morning`, and `honest_report`,
   each with a message naming the old schema; none upgrades it.
5. A `training` block with a missing or non-bool `sealed` is refused, never defaulted.
6. **Adversarial:** a v2 checkpoint whose `dataset_digest` was edited after sealing never reaches the
   record — `run_gate` raises `CheckpointUnverified` first. Under the old code the same edit
   produced a record that named the edited digest.
7. **Adversarial:** a source-reading test asserts `gate.py` and `card.py` contain no read of
   `CHECKPOINT_FILE` outside `sft.py`, so the second-read path cannot return.
8. The gate's exit codes and `solved_new > solved_old AND regressed == 0 AND unverified == 0` rule
   are asserted byte-identical by the existing gate tests, unedited.
9. `gate.verify_checkpoint is sft.verify_checkpoint` identity pins stay green.

## Dependencies and sequencing

Needs aspect 1's `Checkpoint` fields. Independent of aspect 3.

## Open questions and risks

- Existing local `/2` records become unreadable. They are gitignored; the CHANGELOG lists the break.
- `tests/loop/test_promotion_record_n.py` uses `/3` as its "wrong future schema" value; it takes a
  new one.
