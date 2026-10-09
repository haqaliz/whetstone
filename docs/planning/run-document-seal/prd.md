# PRD — run-document-seal

**Core-loop element:** ③ the never-regress promotion gate, at the trust its inputs carry; ④ the
morning report's evidence. ① the reward is untouched: nothing under `verify/` or `tasks/` changes,
and the gate's rule (`solved_new > solved_old`, `regressed == 0`, `unverified == 0`), its three
exits and its retry discipline stay byte-identical. `UNVERIFIED` still counts as not a win. The
whole unit is offline file hashing; nothing leaves the machine.

**Roadmap:** M2 of `docs/ROADMAP.md` § 14 — "Make the gate able to answer"; the follow-on named in
`docs/planning/checkpoint-provenance-seal/prd.md` § 7–8 and the first buildable item in
`docs/STATUS.md`'s 0.20.0 open follow-ups.

**Source:** `docs/planning/_card/issue.md` (the 2026-10-07 `whetstone-next` handoff, verbatim) +
`docs/planning/_card/understanding.md` + the interview decisions of 2026-10-07: seal **both**
documents; a v2 dataset's top-level `digest` is the **seal digest over claims** (the
`whetstone-checkpoint/2` pattern), with the examples digest becoming a claim.

---

## 1. Problem Statement

The checkpoint's own claims are sealed under `whetstone-checkpoint/2`
(`sft.py:905-1003`). The **run's** documents are not, and the tool says so out loud:
`check-leakage --checkpoint` compares a sealed (or recorded) checkpoint value against the run's
`dataset.json` and prints *"the run's `dataset.json` is not sealed, so this compares a checkpoint
claim to a document that anyone with write access to the run can edit"*
(`check_leakage.py:406-407`). That check is load-bearing: the gate runbook halts on any non-zero
`check-leakage` exit (`docs/planning/p3-promotion-gate/gate-runbook/runbook.md`), so it is the
leak guard standing between a leaked candidate and the gate — and its verdict currently rests on a
document its subject can edit.

The gap is worse than the sentence: the dataset's `digest` is not even a digest of the document.
`dataset._digest` (`dataset.py:397-406`) hashes only the ordered `examples` list, so `schema`,
`denominator`, `unverified` and `coverage` sit outside it; and no reader recomputes it —
`check_leakage` trusts the stored field (`check_leakage.py:314`). The ledger has **no digest of
itself at all**, and the morning report states the limit rather than fixing it: *"a ledger is not
self-sealing, and only the checkpoint's own digest is re-derivable from bytes"*
(`morning.py:495-500`). Meanwhile `arm.read_selection` calls `dataset.json` "the sealed document"
(`arm.py:84-97`) while performing no schema check and no digest verification (`:99-107`) — and the
arm is the path that consumes the document as training input.

**Evidence it is real:** the disclosure line above; the two `_digest`/no-digest facts, each
located by file and line; `reports/portability-arm/report.md:27` already calls night #1's
training set "sealed", which under a precise vocabulary it is not; the previous unit's PRD named
this as the separate next unit (`checkpoint-provenance-seal/prd.md` § 7 last bullet, § 8); and
`docs/STATUS.md`'s 0.20.0 open follow-ups. There is no GitHub issue and no external demand — the
unit is defined by the repo's own planning files (verified 2026-10-07).

## 2. Goals & Success Metrics

The goals are properties asserted by tests, not figures. No number in this document was produced
by a run.

- **A v2 dataset and a v3 ledger are tamper-evident for every claim in their documents.** Editing
  any claim, adding an unsealed key, deleting a claim, or downgrading the schema string makes the
  verifying reader raise, and the message names the claim that moved.
- **v1 datasets and v2 ledgers still read, and are never reported as sealed.** Every consumer
  carries the distinction; the real artifacts (night-001's dataset, probe-001's ledger) are never
  rewritten or upgraded in place.
- **The link's far end is verified, not trusted.** `check-leakage --checkpoint` compares against a
  document that was verified first, refuses a tampered sealed dataset by name before any overlap
  comparison, and says which side is sealed.
- **Every run-document reader verifies when the document is sealed.** `check_leakage`,
  `arm.read_selection`, `check_probe`, `morning` and `honest_report` refuse a tampered sealed
  document by name; a v1/v2 document is read as unsealed exactly as today.
- **Nothing else moves.** The gate's rule, exits and retry discipline, the reward, and everything
  under `verify/` and `tasks/` are byte-identical; the checkpoint seal's bytes and error messages
  are byte-identical.

## 3. What "sealed" means here, and what it does not

The digest is an unkeyed hash. Anyone able to edit a document can also recompute its claims and
digest, exactly as `verify_checkpoint` has always allowed for file hashes. A seal therefore does
**not** authenticate the writer and does **not** prove the document is the one a trainer read.

What it catches is the accident-shaped and quiet-edit failures: a document truncated, hand-patched,
confused with another run's, or edited after the fact while a digest cited elsewhere (a report, a
promotion record, the gate runbook) no longer agrees. The vocabulary is **sealed**, never
"verified". The docs state this limit where the claim is made, in the same terms the checkpoint
seal uses (`checkpoint-provenance-seal/prd.md` § 3).

## 4. User Personas & Scenarios

- **The operator gating a candidate.** Runs `check-leakage --run <run> --heldout <doc>
  --checkpoint <dir>` before `whetstone gate`. Today the far end of the comparison is an editable
  file; after this unit the output says whether each side was sealed, and a tampered dataset is a
  refusal rather than a clean verdict.
- **The reader of a morning report.** Renders from a ledger. After this unit the report states the
  ledger's seal state precisely: a v2 ledger is not self-sealing; a v3 ledger is tamper-evident
  against an edit that does not recompute claims and digest.
- **The future operator with a v1/v2 document** (night-001's `dataset.json`, probe-001's
  `whetstone-run/2` ledger). Nothing breaks and nothing is upgraded in place; both are reported
  unsealed.
- **The arm operator.** `whetstone train-arm` reads the night's selection; the word "sealed" in
  its messages becomes true for v2 documents and is disclosed for v1.

## 5. Requirements

### Must-have

1. **One home for the seal primitives.** The canonical-bytes, claim-hash, claims-digest and
   claim-verification logic now private to `sft.py` (`_canonical` `:158-166`, `_claim_hashes`
   `:169-186`, `_claims_digest` `:189-202`, `_verify_claims` `:1036-1094`) is extracted into one
   shared module (planned as `src/whetstone/loop/seal.py`), parameterised by the document's schema
   tag and its unsealed keys, and imported by `sft`, `dataset` and `ledger`. The extraction changes
   no checkpoint bytes and no checkpoint error message; the existing byte-pinned tests stay green
   unedited.
2. **Dataset schema `whetstone-training-set/2`.** The body is `denominator`, `unverified`,
   `coverage`, `examples`; `claims` maps each body key to the sha256 of its canonical JSON; the
   top-level `digest` is the claims digest, domain-separated by the schema tag exactly as the
   checkpoint's is (`sft.py:189-202`). `Dataset.digest` becomes this seal digest, so the value a
   checkpoint records as `dataset_digest` (`night.py:632`, `arm.py:142-162`) is the document's
   own seal and the link between the two ends stays mechanically the same comparison
   (`check_leakage.py:306-329`). The examples-only `_digest` is retired.
3. **The dataset writer writes v2; the reader accepts both, fail-closed on tamper.** A v2
   document whose claim moved, whose keys and claims disagree, or whose digest does not reduce
   from its claims raises a named refusal. A v1 document reads exactly as today and is reported
   unsealed. The verifying reader returns the parsed document and a `sealed` flag and raises a
   dataset-specific named refusal on tamper — the `verify_checkpoint` shape (`sft.py:905-1003`);
   only the exact function and exception names are fixed in the plan. Determinism: the same inputs
   produce byte-identical documents (`dataset.document`'s contract).
4. **`check-leakage` reads the verified dataset.** `run_check` verifies the dataset before the
   overlap comparison; a tampered sealed document refuses (exit 2) with nothing reported clean.
   With `--checkpoint`, the link lines say the run's side is sealed (v2) or "recorded, not sealed"
   (v1), replacing the standing "the run's `dataset.json` is not sealed" sentence
   (`check_leakage.py:406-407`). Without `--checkpoint` the verdict is over the verified document
   and the output stays otherwise unchanged. A mixed-generation pair — a v1 checkpoint's recorded
   digest against a v2 document, or the reverse — is refused by the existing comparison, and a
   test asserts it so the guarantee is explicit rather than an accident of two digest computations
   differing.
5. **Ledger schema `whetstone-run/3`.** The body is today's payload minus `schema`; `claims` and
   the seal `digest` are added in the same shape and domain separation as the dataset's.
   `ledger.write` writes v3.
6. **The ledger reader accepts `/2` and `/3`, refusing `/1`.** `/2` reads exactly as today and is
   reported unsealed; `/3` is verified, and a tampered one raises a named refusal. This is the
   checkpoint's dual-read precedent (`sft.py:931-936`) rather than the single-version refusal the
   `/1`→`/2` backend bump used, because a seal's presence is tellable from the schema string and
   every ledger written under the current schema (`/2`, what the shipped writer emits) must keep
   reading. **Corrected 2026-10-08:** the one real probe ledger is `whetstone-run/1` — written
   before the `/2` bump landed (`a500b04`, 2026-09-08) — and the shipped reader already refuses
   it, so keeping `/1` refused is no regression and probe-001 is not a compatibility constraint.
   The existing discipline survives: `LEDGER_SCHEMA` is still not `/1` and a `/1` document is
   still refused.
7. **Every ledger reader verifies a sealed ledger.** `check_probe` (`check_probe.py:119-158`),
   `morning` (`morning.py:284-371`), `honest_report` (`honest_report.py:387-389`) and
   `check-leakage`'s optional ledger validation read through the verifying reader; a tampered v3
   ledger is a named refusal, never rendered evidence. `morning`'s known-field set
   (`morning.py:207-221`) covers the new keys deliberately, and its `SEAL_SENTENCE`
   (`morning.py:495-500`) is amended to say: a v2 ledger is not self-sealing; a v3 ledger is
   tamper-evident against an edit that does not recompute its claims and digest — still not
   authentication.
8. **`arm.read_selection` reads through the verifying reader.** v1 is accepted unsealed; v2 is
   verified; a tampered v2 is refused. Its docstring and refusal messages stop calling an
   unchecked file "sealed" (`arm.py:84-97`).
9. **Every sentence this unit makes false is corrected in the same commit**, by the rule the
   previous unit followed: the portability-arm report's "night #1's sealed training set"
   (`reports/portability-arm/report.md:27`), the CLI help's "the run's `dataset.json` is not
   sealed" (`cli.py:628-633`), and the gate runbook's sentence plus its guard
   (`docs/planning/p3-promotion-gate/gate-runbook/runbook.md:67`,
   `tests/test_gate_runbook_guards.py:574-578`). If `tests/test_gate_leakage_finding.py`'s quoted
   block changes, its finding is regenerated in the same unit.
10. **Breaking changes are listed as breaking.** A v2 dataset and a v3 ledger are refused by any
    older reader (schema equality), as a v2 checkpoint already is; both are local, gitignored
    artifacts, and no existing artifact is rewritten.

### Should-have

11. `night.disclosure` (`night.py:427`) and the `check-leakage` output name the run documents'
    seal state, so the distinction does not live only in the schema string.
12. A source-reading guard, in the spirit of the checkpoint's one-writer test, asserting the
    dataset and ledger each have exactly one writer and that the writer emits the sealed schema.

### Nice-to-have

13. A read-only `whetstone` command to print a run document's seal state. Not required; the
    information is reachable through `check-leakage`.

## 6. Technical Considerations

- **Reward and gate.** The reward is untouched and stays execution-grounded. The gate's rule,
  exits and retry discipline are byte-identical. A seal never enters a decision: an unsealed v1
  dataset is checked exactly as before, and no verdict changes on seal state alone.
- **Option A, restated.** `Dataset.digest` is the v2 seal digest over the document's claims. The
  committed citations of the old value — night #1's `3416702298c3…` in
  `reports/portability-arm/report.md:27`, `docs/planning/gate-leakage-guard/finding.md:86`,
  `docs/STATUS.md:146` — describe the v1 file on disk and do not move. For new nights, the value
  recorded in checkpoints, promotion records and the morning report names the whole document
  rather than the examples alone; that is the intent, and the docs must say it.
- **The real artifacts, corrected 2026-10-08.** `runs/nights/night-001/dataset.json` (`/1`) lives
  in the primary checkout and is read by a live test
  (`tests/test_gate_leakage_finding.py`); it must keep reading, unsealed, and must never be
  rewritten. The real `runs/night-probe/probe-001/ledger.json` is `whetstone-run/1`, not `/2` as
  an earlier draft of this document said: it predates the `/2` bump (`a500b04`, 2026-09-08), the
  shipped reader already refuses it, and `check-probe` has never been pointed at a real probe. It
  is not a compatibility constraint; the `/2` tolerance is proven by a `/2` fixture in the probe's
  shape.
- **Fixtures that hand-roll documents** (`tests/loop/test_check_leakage.py:342-343, 591-598`,
  `tests/loop/test_arm.py:57-65`, `tests/loop/test_honest_report_door.py:226-275`) either move to
  the real writers or become v1/v2 unsealed fixtures deliberately; the plan decides per test so
  the suite does not accidentally stop exercising the sealed path.
- **`fuse` is checkpoint-only.** The handoff's criterion named it among run-document readers; the
  dig found no read of `dataset.json` or `ledger.json` under `fuse.py`. It has no behaviour to
  change here, and the PRD records the correction rather than inventing a change.
- **Determinism.** The seal is a pure function of the payload: field-by-field serialisation,
  canonical JSON after a round trip, sorted claim lines. The byte-for-byte determinism tests
  (`tests/loop/test_dataset.py:179-194`, `tests/loop/test_night.py:189-214`,
  `tests/loop/test_run_ledger.py:187-206`, `tests/loop/test_night_integration.py:326-374`) are the
  pins.
- **Import shape.** `seal.py` is a stdlib-only leaf; `sft`, `dataset` and `ledger` import it with
  no cycle (`sft` already imports `dataset`, `ledger` already imports `dataset`). No `cli.py` →
  `loop` import edge is added; `tests/test_reward_path_scope_is_partitioned.py` is unaffected, as
  is `tests/test_no_inference_on_reward_path.py` (the reward-path scope is `verify/` and
  `tasks/`).
- **One word, three scopes.** The morning report already calls itself "sealed to its evidence"
  (`morning.py:495-500`) and checkpoints are sealed under v2. This unit adds run-document seals.
  Requirement 7 amends the report's sentence so the senses stay distinguishable: the report is
  reproducibility-sealed; a checkpoint's claims are sealed when v2; a run document's claims are
  sealed when the dataset is v2 or the ledger is v3. No surface may collapse the three.
- **Release.** The unit lands the capability and its docs (STATUS entry, CHANGELOG `Unreleased`,
  ROADMAP M2 note). The version bump and tag are a separate release commit, as `d43cd26` was.

## 7. Risks & Open Questions

- **No real v2 dataset or v3 ledger exists.** No new night has run, `runs/` is the operator's, and
  old documents are never rewritten. The v2/v3 behavior is proven against fixtures and the real
  writers only, as the checkpoint seal was; the docs say so and claim no real sealed run.
- **A seal can be mistaken for authentication.** § 3 is the mitigation; the word is `sealed`, and
  the limit is stated at each surface that prints it.
- **Changing `dataset.digest`'s meaning is deliberate and breaking-adjacent.** New nights record a
  seal digest where the examples digest used to be; the comparison code does not move, old
  citations do not move, and a v1 checkpoint can never be paired with a v2 dataset by a single
  writer. The CHANGELOG says all of this under BREAKING where it applies.
- **The morning report's `SEAL_SENTENCE` currently denies exactly this unit.** It is in the
  must-have list because a code seal and a sentence saying no seal exists cannot ship in the same
  tree.
- **Open:** only the exact function and exception names; the reader shape is fixed in requirements
  3 and 6 (a verifying reader returns the parsed document and a `sealed` flag, raising a
  document-specific named refusal on tamper). Fixed in the aspect plans.
- **Open:** whether `coverage` (a derived value) belongs in the claim set or is recomputed on
  read. Recommendation: it is in the document, so it is claimed like every other payload key.

## 8. Out of Scope

- A signed or keyed seal, a trusted timestamp, or any authentication of the writer.
- Re-sealing, rewriting, or upgrading any existing document, including night-001's dataset and
  probe-001's ledger.
- Proving a document is the one a trainer actually read.
- Any change to the reward, the verifier, the gate's rule, exits or retry discipline, or anything
  under `verify/` or `tasks/`.
- Sealing a checkpoint's `provenance.json` (shipped), the promotion record, or the morning report
  (both already render the seal state of their inputs).
- Producing a clean candidate or running a gate; M2's exit criterion stays open.
- The whole-function measurement, the night's next run, and raising *k* — all the operator's, all
  outside this unit.
- The version bump and tag.

---

## Aspects (proposed)

1. **`seal-core`** — the shared seal module extracted from `sft` (checkpoint bytes unmoved) plus
   `dataset /2`: writer, reader/verifier, `Dataset.digest` semantics, and the v1 tolerance. Owns
   requirements 1–3 and the arm's reader (8).
2. **`leakage-link`** — `check-leakage` verification and disclosure, the CLI help, the gate
   runbook sentence and guard, and the finding regeneration if its quoted block moves. Owns
   requirements 4, 9 and 11.
3. **`ledger-seal`** — `ledger /3` plus every ledger reader and the morning sentence and field
   set. Owns requirements 5–7 and 10–12 as they apply to the ledger.

**Sequencing:** `seal-core` first — it defines the shared seal module and the dataset reader that
the later aspects consume; `leakage-link` and `ledger-seal` then land independently, in either
order.
