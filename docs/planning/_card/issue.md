# Card: feat/patch-representation

## Brief

83% of night-006's rollouts died at patch application, most of them well-formed diffs whose context lines didn't match the file (GitHub #64, ROADMAP § 14 M1 in PR #66). Search/replace was withdrawn as D3 in `p2-yield-probe` because at the time it addressed only a minority failure. The PRD must show, with evidence, that the failure pattern has since changed — not just revive D3. **Slice 1 (read-only, no compute):** over night-006's stored transcripts, classify each well-formed-but-refused diff's context as found-verbatim-elsewhere (offset error) or not-found (invented), and record `NOT_APPLIED` `detail` the way `NO_ORACLE` does. If most are invented, the pick changes. **Slice 2:** a new edit format (search/replace blocks, or whole-function replacement) that the harness turns into a unified diff against the task's source files. A missing or non-unique anchor is refused, never guessed. The verifier and reward path are unchanged. **Acceptance criteria, as tests first:** each format → diff conversion is deterministic and byte-identical across processes; a missing or non-unique anchor is refused with a named reason; `NOT_APPLIED` carries a non-empty `detail`; the new `prompt_sha256` and `extractor_version` are pinned by a `PREREGISTRATION.md` § 10.16 Type 1 amendment committed before any night uses the new format, and that arm's report is declared non-comparable; the reward-path AST guard and control-arm `INTACT` tests still pass.

## Source issue #64

### 83% of night-006's rollouts died on patch application, and over half were well-formed diffs whose context did not match

Labels: 

The 3B night (`night-006`, 336 rollouts) ended with **279 `NOT_APPLIED` — 83% of every rollout generated.** Only 13 were `NO_DIFF`. The base writes a diff 96% of the time; almost none of them land.

`NOT_APPLIED` carries an empty `detail` in the journal, so the reason is not in the run record. It is recoverable, because the night stored transcripts — exactly what `transcript.py` exists for: *"re-running the night to get them costs another night of compute per question asked. So the completion is kept."* No new compute was needed.

## Classifying the 279 final (graded) completions

`autopsy.classify_completion` over the final completion of each `NOT_APPLIED` rollout:

| cause | count | share |
|---|---|---|
| **WELL_FORMED** | **154** | **55%** |
| HUNK_DIES_EARLY | 76 | 27% |
| HUNK_COUNT_MISMATCH | 44 | 16% |
| UNRECOGNISED_SHAPE | 5 | 2% |

Markers across the same set: STACKED_FENCE 278, REPEATED_DIFFS 129, NOOP_HUNKS 93, INDEX_GARBAGE 5.

**Over half the failures are structurally valid unified diffs.** The extractor accepted them; git refused them.

## Why git refused them

149 of the 154 yielded an extractable diff. Sampling 60 and running `git apply --check` against a real checkout at the task's `base_commit`:

- **58 of 60: `error: patch failed: <file>:<line>`** — git's message for *the context at that line does not match*
- 2 of 60: `corrupt patch at line N`
- **0 of 60 would have applied cleanly** — so none are false negatives

The paths are real, the files exist, the diff parses. **The model's context lines and line numbers do not match the file it is patching.**

## Why this matters

Unified diff requires the model to reproduce exact surrounding lines and correct line offsets from memory. That is a transcription task, not a reasoning task, and it is where 55% of this night's work was lost — after the model had already decided what to change.

**This has never been tested.** The arms tried so far moved other inputs: `reports/format-hardening/` is a **retry-augmented** contract, not a different patch representation; `reports/larger-base/` moved base size; `reports/easier-stratum/` moved the task set. The patch *representation* has been unified diff throughout, and the same wall is visible in the format-hardening figures (patch apply 43/64, 50/64, 8/64).

Raising *k* or the base size does not touch this class: a bigger model writes a better-reasoned diff whose context still has to match exactly.

## Proposed direction

A representation that does not require reproducing context or computing offsets — search/replace blocks keyed on a unique anchor, or whole-function replacement. The verifier is unaffected: it still re-executes and the reward stays execution-grounded. What changes is only how an edit is expressed.

This is a **Type 1 amendment** — `prompt_sha256` and `extractor_version` are pinned parts of the generation contract — and it must be declared before the night that tests it, with the arm's figures non-comparable to the existing series.

## Secondary

`NOT_APPLIED` should carry a `detail` the way `NO_ORACLE` does. The outcome accounting for 83% of a nine-day run recorded no reason, and recovering it required joining transcripts to journals by hand.

### Comments



## Related

- #60 The promotion gate cannot fire while the held-out set holds a permanently NO_ORACLE task
- #62 The held-out split is keyed on the task id, so an arbitrary donor label decides what is held out
- PR #66 Record what has to be true before a model of ours is published (ROADMAP § 14) (open; adds ROADMAP § 14, names this M1)
