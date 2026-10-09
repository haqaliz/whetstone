# Understanding — run-document-seal

**Core-loop element:** ③ the never-regress promotion gate, at the trust its inputs carry; ④ the
morning report's evidence. ① the reward does not change: nothing under `verify/` or `tasks/` is
touched, the gate's rule (`solved_new > solved_old`, `regressed == 0`, `unverified == 0`) and its
three exits stay byte-identical, and `UNVERIFIED` still counts as not a win. Everything is offline
file hashing; nothing leaves the machine.

## What the work is really asking

The checkpoint's own claims are sealed under `whetstone-checkpoint/2` (`sft.py:905-1003`), but the
**run's** documents are not. `check-leakage --checkpoint` compares a sealed (or recorded) value
against the run's `dataset.json`, and prints the limit itself: *"the run's `dataset.json` is not
sealed, so this compares a checkpoint claim to a document that anyone with write access to the run
can edit"* (`check_leakage.py:406-407`). The last unit's PRD named sealing the run's documents as
the separate next unit (`checkpoint-provenance-seal/prd.md` § 7 last bullet, § 8 line 215), and
`docs/STATUS.md`'s 0.20.0 open follow-ups list it first among buildable items. This unit gives
`dataset.json` and `ledger.json` the same claims discipline the checkpoint has: a `claims` map, a
digest over the sorted claim lines, domain-separated by the schema tag, with v1 documents still
readable and never reported as sealed.

## Facts the dig established

- **One writer each.** `night.run_night` writes `dataset.json` at `night.py:336` (via
  `dataset.build`/`write_document`) and `ledger.json` at `night.py:392` (via `ledger.write`); the
  ledger is written even when training raises (`night.py:605-626`). Both documents are serialised
  field by field (`dataset._payload` `dataset.py:365-379`; `ledger._payload` `ledger.py:299-364`),
  so a new field must be named in the payload or it never round-trips.
- **The dataset's `digest` is not a document digest.** `dataset._digest` (`dataset.py:397-406`)
  hashes only the ordered `examples` list; `schema`, `denominator`, `unverified` and `coverage`
  sit outside it. An edit to anything but `examples` moves no digest, and an edit to `examples`
  need not move the stored `digest` because no reader recomputes it (`check_leakage` trusts the
  field, `check_leakage.py:314`).
- **The ledger carries no digest of itself at all** (`ledger.py`), and `morning.SEAL_SENTENCE`
  (`morning.py:495-500`) states that a ledger is not self-sealing.
- **The checkpoint v2 pattern to copy:** `_canonical` (JSON round trip, `sft.py:158-166`),
  `_claim_hashes` (one sha256 per claim; `_UNSEALED_KEYS` and newline keys refused, `:169-186`),
  `_claims_digest` (sha256 over the schema tag, NUL, sorted `key:hash` lines — the domain
  separation, `:189-202`), `_verify_claims` (names the first moved claim, an unlisted key, an
  orphaned claim, `:1036-1094`), and dual-schema read with `sealed = schema == V2` (`:931-936`).
- **The link's two ends.** `check_leakage._link_of` (`:306-329`) compares `Checkpoint.dataset_digest`
  to the run's `dataset.json` `digest`; `_link_lines` (`:379-408`) prints seal state per side. The
  checkpoint side is sealed only for v2; no real v2 checkpoint exists yet.
- **Every run-document reader today reads raw.** `check_probe` (`check_probe.py:119-158`),
  `morning` (`morning.py:284-371`, with unknown-top-level-key refusal at `:207-221, 294-300`),
  `honest_report` (`honest_report.py:387-389`), `arm.read_selection` (`arm.py:83-107`, plain
  `json.loads`, no schema check, no digest verification) and `check_leakage` itself. `gate` and
  `fuse` never open run documents.
- **`dataset_digest`'s chain:** `night.py:632` and `arm.py:142-162` pass the dataset's `digest`
  into `sft.write_checkpoint`; `gate.py:1676-1714` reads it off the verified checkpoint; the
  promotion record carries it (`gate.py:1034-1041`); the morning report renders it from the
  ledger's `dataset.digest` (`morning.py:722`). So a change to what `dataset.digest` means moves
  the value the checkpoint records — mechanically fine, but a decision to take deliberately.
- **Real artifacts are v1 and must not move:** `runs/nights/night-001/dataset.json`
  (digest `3416702298c3…`), `runs/night-probe/probe-001/ledger.json` (**`whetstone-run/1`**, not
  `/2` as this note first said — corrected 2026-10-08 against the primary checkout's bytes: it
  predates the `/2` bump, and the shipped reader already refuses it), and the v1
  `checkpoints/portability-arm` — all in the primary checkout, none in this worktree.
  `tests/test_gate_leakage_finding.py:171-201` runs `check-leakage` against the real night-001
  files and reproduces the committed finding block line-for-line.

## Contradictions with the brief

1. **`arm.read_selection` calls the document "sealed" today** (`arm.py:84-97`) while performing no
   schema check and no digest verification (`:99-107`) — and the arm is the path that actually
   consumes the document as training input. The check-leakage reader is stricter than the training
   reader. This unit can make the word true (and must, or correct it).
2. **`reports/portability-arm/report.md:27` already calls night #1's training set "sealed".** Under
   the new vocabulary a v1 document is unsealed — that prose becomes a false claim unless this
   unit corrects it. The same audit applies to any other sentence that calls a v1 run document
   sealed.
3. **"Not sealed" understates the dataset gap.** The disclosure sentence says the document is not
   sealed; in fact its `digest` does not even cover its own `denominator`/`unverified`/`coverage`,
   and is never recomputed. The unit should state the limit precisely, not just flip a flag.
4. **The ledger's schema-bump precedent is refusal, not dual-read.** `test_backend.py:201-218`
   pins that adding a required field moved `whetstone-run/1` → `/2` and an old-schema ledger is
   refused. A seal is different in kind: v2 ledgers are tellable from v3 by the schema string, so
   the checkpoint's dual-read precedent (`sealed = schema == V3`) fits better — but `/1` stays
   refused, and the test's intent must survive in the plan.

## Consequences for the tests

- `tests/loop/test_check_leakage_checkpoint.py:201-305` pins `SEALED_LINE`/`V1_LINE`/`FAR_END_LINE`
  and several line-order properties; `FAR_END_LINE` ("the run's dataset.json is not sealed") is
  the sentence this unit amends, and `tests/loop/test_check_leakage_cli.py:495-502` pins it in
  `--help`. `tests/test_gate_runbook_guards.py:574-578` pins it in the gate runbook
  (`docs/planning/p3-promotion-gate/gate-runbook/runbook.md:67`).
- `tests/loop/test_morning_evidence.py:134-176` pins that the morning's known-field list covers
  every field the ledger carries and that an unknown top-level key is refused; a ledger seal adds
  keys and must update that list deliberately.
- Determinism pins: `tests/loop/test_dataset.py:179-194`, `tests/loop/test_night.py:189-214`,
  `tests/loop/test_night_integration.py:326-374`, `tests/loop/test_run_ledger.py:187-206` — the
  seal must be a deterministic function of the payload (sorted claim lines, JSON round trip).
- `tests/test_gate_leakage_finding.py:171-201` reproduces committed prose; if any line it quotes
  changes (it runs without `--checkpoint`, so `_link_lines` currently returns nothing), the finding
  regeneration must be part of the unit.
- Fixtures that hand-roll documents: `tests/loop/test_check_leakage.py:342-343, 591-598`,
  `tests/loop/test_arm.py:57-65`, `tests/loop/test_honest_report_door.py:226-275` — if readers
  start verifying seals, these either become v2 writers or keep reading as v1 unsealed by design.

## What cannot be proven here

No real v2 run document exists, and none can exist inside this unit: `runs/` is the operator's,
the next night has not run, and night-001/probe-001 are never rewritten. v2 behaviour is proven
against fixtures and the real writers only, as the checkpoint seal was. The end-to-end
both-sides-sealed link (`check-leakage --checkpoint` over a v2 dataset and a v2 checkpoint) is
fixtures-only until a later night or arm writes both. The seal is an unkeyed hash: tamper-evidence
against an edit that does not also recompute claims and digest, never authentication, and it does
not prove a document is the one a trainer actually read.

## Open questions for the interview

1. **Dataset digest semantics.** Option A: v2 `digest` becomes the seal digest over claims (the
   checkpoint pattern exactly; the examples digest becomes the `examples` claim; the checkpoint
   then records the document's seal). Option B: keep `digest` as the examples digest and add a
   separate seal field. Dig recommendation: **A** — one seal concept, precedent-consistent, and the
   link then records the document rather than a fragment of it. (Caveat to state either way: the
   committed `3416702298c3…` citations describe the v1 night-001 file and do not move.)
2. **Scope.** The brief names both documents. Proposed decomposition: aspect 1 dataset seal +
   `check-leakage` link/disclosure + `arm` verification; aspect 2 ledger seal (`whetstone-run/3`)
   + its readers; aspect 3 prose/contract corrections (arm docstring, portability-arm report,
   CLI help, runbook, finding reproduction if touched).
3. **Schema strategy.** Dual-read `/2` + `/3` for the ledger and `/1` + `/2` for the dataset
   (checkpoint precedent), with `/1` ledgers still refused? Or strict refusal of old schemas?
   Dig recommendation: dual-read; old documents are real operator artifacts.
4. **Which readers refuse on a tampered sealed document** (recommend all of them: `check_leakage`,
   `check_probe`, `morning`, `honest_report`, `arm`), and what a v1 reader prints — "recorded, not
   sealed" — in each surface.
5. **The ledger's `dataset.digest` field** under Option A holds the dataset's seal digest; under
   Option B the examples digest. Either way the name stays; the plan should say which value the
   morning report's `evidence.dataset_digest` is.
