# Spec — leakage-link

**Aspect 2 of 3** for `run-document-seal` (`../prd.md`). Owns PRD requirements 4, 9 and 11.
**Depends on:** `seal-core` (the verifying dataset reader). **Depended on by:** nothing.

## Problem slice and outcome

`check-leakage` is the leak guard the gate runbook halts on, and its far end is today an
editable document: `_read_dataset` (`check_leakage.py:492-499`) reads raw through
`read_document`, `_link_of` trusts the stored `digest` field (`:314`), and the disclosure says
the limit out loud — *"the run's `dataset.json` is not sealed, so this compares a checkpoint
claim to a document that anyone with write access to the run can edit"*
(`:406-407`). After `seal-core` the reader verifies; this aspect wires the verified read into
the check's order of operations, turns a tampered v2 document into a named refusal before any
overlap comparison, makes the run-side link line conditional on the dataset's generation, and
corrects every sentence this unit makes false (requirement 9): the CLI help
(`cli.py:628-633`), the gate runbook sentence plus its guard (`runbook.md:67`,
`tests/test_gate_runbook_guards.py:574-578`), the portability-arm report
(`reports/portability-arm/report.md:27`), and the module docstring's standing claim
(`check_leakage.py:38-40`). It also names the run documents' seal state at the night's own
surface (requirement 11, `night.py:426-427`).

Outcome: the check reads only documents the verifying reader accepted; a tampered v2 dataset
refuses by name with nothing reported clean, with or without `--checkpoint`; the link block
says which side is sealed and which is recorded-not-sealed; the mixed-generation pair is
refused and tested, explicitly rather than by accident. No verdict and no exit code changes
on seal state alone.

## In scope

1. **The verified far end.** `run_check` (`:268-303`) obtains its training document through
   `verify_document` — `read_document` already delegates to it after `seal-core` (seal-core
   spec item 4), so the import at `:56` does not move. `_read_dataset` (`:492-499`) is amended
   so `DatasetUnverified` propagates **unwrapped**: the current `except (OSError, ValueError)`
   at `:496` would swallow it into `DatasetUnreadable` — a refusal that names a moved claim
   inside a message that names a different refusal type. The wrap excludes it (it is already a
   `ValueError` subclass; seal-core's exception note is reviewed when the exclusion is written)
   and keeps `OSError`/other-`ValueError` → `DatasetUnreadable` exactly as today.
   `DatasetUnverified` is added to `REFUSALS` (`:139-152`), so the CLI handler
   (`cli.py:1196-1202`) already turns it into exit 2 with the reason named on stderr. The
   refusal is decided in `_read_dataset`, before `_link_of` and `check_overlap`, so a tampered
   sealed document refuses with or without `--checkpoint` — the verified read is a property of
   the run input, never of the link.
2. **Conditional run-side link lines in `_link_lines` (`:379-408`).** The checkpoint side does
   not move: sealed (`whetstone-checkpoint/2`) or recorded-not-sealed (`whetstone-checkpoint/1`)
   exactly as today (`:392-403`). The second returned line (`:406-407`) becomes conditional on
   the run side's seal state. Mechanism: `run_check` passes the `verify_document` `sealed`
   flag into `_link_of`; `DatasetLink` (`:179-185`) gains `run_sealed: bool`; `_link_lines`
   emits the sealed run line for v2 and the recorded-not-sealed run line for v1. The block
   stays two lines.
   **Proposed wording (the plan may refine):**
   - run side sealed: `the run's dataset.json is sealed (whetstone-training-set/2), so an edit
     to it that did not also recompute its claims and digest would have been refused
     (tamper-evidence, not authentication)`
   - run side recorded: `the run's dataset.json is recorded, not sealed
     (whetstone-training-set/1), so this compares the checkpoint's claim to a document that
     anyone with write access to the run can edit`
   **Honesty rule the lines must obey:** never "verified" — the document and the checkpoint
   files are verified, the *link* is not, and the byte pins (`tests/loop/test_check_leakage_checkpoint.py:255-266`,
   `tests/loop/test_check_leakage_cli.py:354-356`) forbid the word; always "sealed" with the
   generation tag; the tamper-evidence-not-authentication limit stated in the sealed case; and
   the standing sentence's point — anyone with write access can edit — preserved in the v1
   case, where it remains true.
3. **Same-commit prose corrections (requirement 9), this aspect's blast radius:**
   - The module docstring's standing claim (`check_leakage.py:38-40`, "The run's `dataset.json`
     is NOT sealed") restated conditionally (v2 sealed, v1 not), and the `_link_lines`
     docstring's "an unsealed document" (`:384`) likewise.
   - CLI help (`cli.py:628-633`): the sentence "the run's dataset.json is not sealed" is
     replaced by the conditional (proposal: "a v2 dataset's link is reported as sealed, a v1
     dataset's as recorded, not sealed; a tampered v2 dataset exits 2"). The parser
     description's "a document that cannot be trusted" (`:593-594`) already covers the tamper
     exit and does not change.
   - Gate runbook (`runbook.md:67`): "The run's `dataset.json` is not sealed." → conditional
     (proposal: "For a v2 dataset (`whetstone-training-set/2`) the run's `dataset.json` is
     itself sealed and the command says so; for a v1 dataset it is recorded, not sealed."); the
     guard (`test_gate_runbook_guards.py:574-578`) re-pinned to the new sentence.
   - Portability-arm report (`report.md:27`): "night #1's sealed training set" → "night #1's
     training set" named as a v1, unsealed document; the digest citation
     `3416702298c36a9a…` stays, per PRD § 6 (committed citations describe the v1 file on disk
     and do not move).
   - The finding's § 5 prose at `finding.md:100-102` ("trained from the same sealed dataset")
     repeats the same false claim about the same v1 file; corrected in the same commit (see
     Open questions).
   - `tests/loop/test_check_leakage_checkpoint.py`'s module docstring (`:4-5`, "the run's
     document is not sealed at all") rewritten with the tests it describes.
4. **The mixed-generation pair, explicit (requirement 4, last sentence).** Two tests: a v1
   checkpoint's recorded examples digest against a v2 document, and the reverse (a v2
   checkpoint's seal digest against a v1 document) — each refused by the **existing**
   comparison (`_link_of` `:320-328` → `CheckpointNotThisRun`), asserted at `run_check` and
   CLI level, so the guarantee is a tested property and not an accident of two digest
   computations differing.
5. **`night.disclosure` names seal state (requirement 11; `night.py:426-427`).** The "dataset
   digest" line carries the generation: v2 — `dataset digest <d> (sealed,
   whetstone-training-set/2)`; v1 — `dataset digest <d> (recorded, not sealed:
   whetstone-training-set/1)`. No test pins that line's literal (`tests/loop/test_night.py:316`
   asserts the headline only), so this is additive.
6. **The finding does not move; reproduction is pinned instead.** `tests/test_gate_leakage_finding.py`
   runs check-leakage **without** `--checkpoint` (`:119`); `_link_lines` returns nothing for
   `link is None` (`:386-387`); night-001's dataset is v1 and reads unsealed, byte for byte, by
   seal-core's own contract. No-checkpoint output is therefore unchanged and the quoted block
   does **not** move: no regeneration. Instead, a byte-identity pin for the no-checkpoint v1
   disclosure is added in `tests/loop/test_check_leakage.py` — the exact line tuple the
   finding quotes (redaction apart) — so a drift in that path fails in-unit before it can
   reach the finding; the existing live guard (`test_gate_leakage_finding.py:171-201`) keeps
   running unedited.
7. **`run_check_leakage_cli`'s docstring** (`cli.py:1186-1194`) names the refusal cases; "a
   dataset whose claims do not verify" is added to the list (prose, no behavior).

## Out of scope

- The shared seal module, the dataset writer, `verify_document`/`DatasetUnverified` themselves,
  `Dataset.digest` semantics, and `arm.read_selection` (requirement 8) — all `seal-core`
  (requirements 1–3, 8).
- The ledger (`whetstone-run/3`, its readers, the morning sentence), including
  `check-leakage`'s optional ledger validation — all `ledger-seal` (requirements 5–7, 10–12 as
  they apply to the ledger).
- The gate's rule, its three exits and its retry discipline; anything under `verify/` or
  `tasks/`; the reward.
- Rewriting or upgrading any existing document — night-001's dataset and portability-arm's
  checkpoint keep reading as they are.
- Regenerating `docs/planning/gate-leakage-guard/finding.md` (decided above: its quoted block
  does not move).
- The version bump and tag; the morning report unit's sentences (require 5–7, `ledger-seal`).

## Acceptance criteria (tests first)

1. A v2 dataset with one tampered payload field — `denominator`, `unverified`, `coverage`,
   `examples`, one test each — refuses `run_check` with `DatasetUnverified`, its message names
   the field that moved, and the refusal fires with and without `--checkpoint`. The CLI exits
   2, stdout empty, stderr prefixed `whetstone check-leakage: `.
2. A v2 document whose claims and digest were recomputed after the checkpoint recorded the
   old digest (a forger who re-seals the document) is refused as `CheckpointNotThisRun` — the
   checkpoint link moved, not the document — and the reverse (a v2 checkpoint against a v1
   document) equally. Both directions at `run_check` and CLI level (exit 2).
3. `DatasetUnverified` is in `check_leakage.REFUSALS` and subclasses `ValueError` — the
   operator-fixable pin extends `tests/loop/test_check_leakage_checkpoint.py:189-196`.
4. Without `--checkpoint`, a tampered v2 document refuses (exit 2, nothing clean reported) —
   the verified read is a property of the run input, never of the link.
5. Fresh v2 and v1 fixtures: the link block is exactly two lines; the run side reads "sealed
   (whetstone-training-set/2)" for v2 and "recorded, not sealed (whetstone-training-set/1)"
   for v1; neither side's sentence contains the token "verified"; the line-order pins survive
   (link after verdict and residual, notice last).
6. The no-checkpoint disclosure over a v1 document is byte-identical to today (pinned line
   tuple), so `test_the_finding_equals_a_fresh_check_leakage_run`
   (`tests/test_gate_leakage_finding.py:171-201`) passes unedited.
7. Help text: the standing "not sealed" claim is gone, the conditional is present; the runbook
   guard re-pinned to the new sentence; `report.md:27` and `finding.md:101` prose corrected,
   with a grep-level assertion where a guard exists and a review assertion in the same commit
   elsewhere.
8. `night.disclosure`'s digest line names the seal state for v2 and v1 (unit tests over a v2
   and a v1 night fixture).
9. Exit codes untouched: 0/1/2 semantics and stdout/stderr routing unchanged — the existing
   CLI suite passes with only the named literal edits of "Pinned test literals" below.

**Pinned test literals that change (exactly):**

- `tests/loop/test_check_leakage_checkpoint.py`: `FAR_END_LINE` (`:213-216`) is replaced by
  two conditional constants (working names `RUN_SEALED_LINE`/`RUN_V1_LINE`, wording per In
  scope item 2); `SEALED_LINE` (`:202-207`) and `V1_LINE` (`:208-212`) are unchanged, because
  the checkpoint side does not move; the `_link_lines` helper (`:219-221`) selects the new
  constants; the asserting tests at `:238-240`, `:249-251`, `:263-265` (line count stays 2),
  `:278` (leaked run), `:291` (empty branch) and `:304-305` (notice last) extend to cover both
  run generations; the `DatasetLink(...)` equality pins (`:79`, `:90`) gain `run_sealed`.
- `tests/loop/test_check_leakage_cli.py`: the help assertion (`:501`) drops "dataset.json is
  not sealed" and asserts the conditional phrase; the "sealed (whetstone-checkpoint/2)" and
  ordering assertions (`:317`, `:319`) are untouched.
- `tests/test_gate_runbook_guards.py`: `:574-578` re-pinned to the new runbook sentence.
- `tests/loop/test_check_leakage_checkpoint.py:176-186` (a `digest` popped from a v2
  document): expects `DatasetUnverified` instead of `DatasetUnreadable` — a malformed v2 shape
  is a seal refusal by seal-core's contract — exit 2 either way; the plan pins the more
  precise type.
- **Fixture consequence, decided here:** `_run` (`tests/loop/test_check_leakage.py:353-356`)
  writes through the real writer, which seal-core makes v2 with the digest re-derived in
  `build`, so the `RUN_DIGEST = "d" * 64` literal (`test_check_leakage_checkpoint.py:22`)
  stops matching the written document. The checkpoint fixture records the digest read back off
  the written document (`dataset.document()["digest"]`), and the mismatch tests pass a
  deliberately different value. `RUN_DIGEST` becomes derived rather than pinned; the mismatch
  semantics are unaffected.
- **Third-source fixture, decided here:** the hand-rolled payload at
  `tests/loop/test_check_leakage.py:591-598` declares `dataset.DATASET_SCHEMA`, which after
  seal-core is `/2` and would refuse on a missing/incorrect seal before `_training_of` ever
  sees `source-c`. The fixture declares `whetstone-training-set/1` on purpose — v1 reads
  exactly as today, unsealed (seal-core item 4) — preserving the `UnknownSource` semantics
  with the smallest edit. (Forging a valid seal over the payload with seal.py's own primitives
  would be equally honest because the seal is unkeyed, but changes nothing the test is about.)
- The fixture's minimum ledger (`tests/loop/test_check_leakage.py:342-344`) is untouched
  here; if `ledger-seal` lands first, its own fixture modernization owns it (see
  sequencing).

## Dependencies and sequencing

- After `seal-core`: it defines `DatasetUnverified`, `verify_document`, the
  `read_document` delegation and the v2 writer the fixtures now emit.
- Independent of `ledger-seal`, in either order. This aspect's ledger path (`run_check`
  `:294-297`, the minimum-ledger fixture) reads v1/v2 ledgers as today; the `/3` verifying
  read of the optional ledger is `ledger-seal`'s. If `ledger-seal` lands first, its fixture
  modernization covers the minimum-ledger fixture, and the work item lands after it on
  master, keeping this suite green throughout.

## Open questions and risks

- **`finding.md:100-102` "the same sealed dataset".** The words name night-001's v1 dataset,
  so they repeat the false claim `report.md:27` makes and are corrected in this commit (a
  one-word edit, no guard pins the phrase, no regeneration). If the plan reads the sentence
  as describing the sibling checkpoint's sealed claim instead, it stays — but the unit then
  has two different readings of "sealed" in one paragraph, which the PRD's one-word-three-
  scopes rule warns against. Recommendation: correct.
- **`DatasetLink.run_sealed` shape.** The link must carry the run side's seal state; whether
  as a new field or by passing the verified flag through `_link_of`, the block stays two
  lines. The plan pins the field name.
- **The unwrap in `_read_dataset`.** Excluding `DatasetUnverified` from the wrap is the one
  place the refusal naming can regress quietly (a wrapped message that names the right claim
  under the wrong type). The acceptance criteria assert the type at every surface, and the
  seal-core exception note is re-read when the exclusion is written.
- **Fixtures-only run-side seal.** No real v2 dataset exists (PRD § 7); the sealed run line,
  the help sentence and the runbook sentence describe a generation only fixtures exercise.
  None of the surfaces may imply a real sealed run exists.
- **Mixed-generation false positive.** A v1 examples digest could in principle equal a v2
  seal digest; the comparison is exact (`:321`) and the tests use distinct values, so a
  refusal either way is honest — no risk beyond the documented exact comparison.