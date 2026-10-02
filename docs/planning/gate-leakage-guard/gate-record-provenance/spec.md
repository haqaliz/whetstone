# Spec — gate-record-provenance

**Core loop element:** ③. **Slice:** the promotion record names what trained the candidate.

## In scope
- Record fields: training-dataset digest, base repo_id, base revision, for the candidate.
- Refusal when the digest cannot be recovered from the checkpoint/run.

## Out of scope
- The decision rule, retries, counts, or the incumbent's untrained dispatch.

## Acceptance criteria (tests first)
1. A fixture gate run's record carries the three fields, equal to the candidate's recorded values.
2. **Adversarial:** a candidate whose training digest is unrecoverable is refused (exit 2), never
   written with a blank or placeholder.
3. The untrained incumbent records no training digest, explicitly, not a fabricated one.
4. Existing record readers (report/card) still pass their tests, or the schema version is bumped
   and the readers refuse the old version loudly.
5. Decision outcomes (promoted/rejected/UNVERIFIED) on existing fixtures are unchanged.

## Open questions
- Where the digest lives for a checkpoint (checkpoint metadata vs run dataset); resolve in plan.

## Amendments after the review gate
- Task 0 of the plan settles where the three values live before any test is written.
- Schema version is bumped; old-version records are refused by readers, never upgraded.
