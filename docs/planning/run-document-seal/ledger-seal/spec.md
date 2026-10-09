# Spec — ledger-seal

**Aspect 3 of 3** for `run-document-seal` (`../prd.md`). Owns PRD requirements 5–7 and the ledger parts of 10–12.
**Depends on:** `seal-core` (the shared seal module). **Depended on by:** nothing.

## Problem slice and outcome

The ledger carries no digest of itself. `ledger._payload` (`ledger.py:299-364`) serialises fifteen
top-level keys field by field — `schema` (`:49`) plus `run_id`, `recorded_on`, `run_seed`, `draws`,
`model`, `backend`, `generation_contract`, `task_set`, `environment_pins`, `tool_versions`, `seeds`,
`draws_recorded`, `dataset`, `checkpoint`, `capacity` — and nothing in the module computes a digest
over any of them. Every consumer reads raw through `ledger.read` (`:256-269`), which checks
`raw.get("schema") == LEDGER_SCHEMA` and nothing else: `check_probe.run_check`
(`check_probe.py:135`), `morning.read_ledger` (`morning.py:292`, through the import at `:53-54`),
`honest_report` (`honest_report.py:387-389`) and `check_leakage`'s optional validation
(`check_leakage.py:294-297`). `morning.SEAL_SENTENCE` (`morning.py:495-500`) states the limit and is
the one existing sentence this unit makes false.

Outcome: `whetstone-run/3` seals every claim in the document the way `whetstone-checkpoint/2` seals
a checkpoint's (`sft.py:905-1003`); `ledger.write` writes v3; `ledger.read` verifies a v3 document
before any consumer sees it, accepts a `/2` document as today (unsealed — the verifying reader
returns `sealed=False`), and refuses `/1` exactly as today; every malformed or tampered sealed shape
is a named `LedgerUnverified`; `morning`'s known-field set covers the seal keys and its sentence is
true for both generations. No existing artifact is rewritten.

## In scope

1. **`whetstone-run/3`.** Constants beside the current one, mirroring `sft.py:92-96` and seal-core's
   dataset constants: `LEDGER_SCHEMA_V1 = "whetstone-run/1"` (declared only, still refused),
   `LEDGER_SCHEMA_V2 = "whetstone-run/2"`, `LEDGER_SCHEMA_V3 = "whetstone-run/3"`,
   `LEDGER_SCHEMA = LEDGER_SCHEMA_V3`.
   The body is today's `_payload` minus `schema` (the fifteen keys above, unchanged in name, and
   the `journal.py` codec rule kept: a `Ledger` field not named in `_payload` never round-trips).
   `claims` is `seal.claim_hashes(body, subject="ledger", refuse=LedgerUnverified)`; `digest` is
   `seal.claims_digest(claims, schema=LEDGER_SCHEMA_V3)` (the schema tag is the domain separation);
   `document(ledger)` keeps the `json.dumps(..., indent=2, sort_keys=True) + "\n"` framing
   (`ledger.py:244-246`). `write` (`:249-253`) is unchanged and writes v3; `night.run_night`
   (`night.py:392`) and its write-even-when-training-raises path need no edit.
2. **Verifying reader.** `class LedgerUnverified(LedgerUnreadable)` — the named refusal for every
   malformed/tampered sealed shape. Subclassing the existing `LedgerUnreadable` (`ledger.py:65-66`)
   is deliberate: every consumer's refusal tuple already holds the base class (`check_probe.py:84-90`,
   `check_leakage.py:145`, `morning.py:787-796`, `honest_report.py:118`), so the named refusal maps
   through the same exit-2 refusals with no per-consumer tuple edit. A frozen `VerifiedLedger`
   carrying `document: Mapping[str, Any]` and `sealed: bool`, and `verify_document(path)` in the
   shape seal-core fixes for the dataset: parse; refuse any schema other than `/2` or `/3` as
   `LedgerUnreadable`, naming both accepted schemas while keeping the `LEDGER_SCHEMA` string in the
   message (`test_run_ledger.py:157` matches on it); `/3` calls
   `seal.verify_claims(path, raw, schema=LEDGER_SCHEMA_V3, subject="ledger", refuse=LedgerUnverified)`
   and returns `sealed=True`; `/2` returns `sealed=False` after the downgrade guard below.
   `read(path) -> Mapping[str, Any]` stays public as `verify_document(path).document`, so the
   verifying path is the only path and no consumer's call site changes; `read`'s docstring (`:257`)
   and the `LEDGER_SCHEMA` comment (`:50-53`) move with the behaviour.
3. **The `/2` downgrade guard.** A `/2` document carrying `claims` or a top-level `digest` is
   refused as `LedgerUnverified`, because no `/2` writer ever emitted either. The checkpoint reader
   tolerates a `/1` document that carries a `claims` key (`sft.py:915-916`) and catches its
   downgrade at the file-digest self-consistency comparison (`sft.py:983-989`); a `/2` ledger has
   no self-digest to fall back on, so the guard has to be explicit or a re-labelled v3 document
   reads as unsealed with no refusal anywhere.
4. **Every ledger reader verifies, by identity not by edit.** `check_probe.py:43-44`,
   `morning.py:53-54`, `honest_report.py:42-43` and `check_leakage.py:65-66` all import `read` (or
   the module) by identity; after this aspect a tampered v3 ledger raises `LedgerUnverified` before
   any decision, count, link or render. `check_leakage`'s optional validation (`:294-297`) reads
   exactly what it read before, now verified.
5. **`morning`'s known-field set and its field tests.** `_KNOWN_FIELDS` (`morning.py:207-221`)
   gains `claims` and `digest`, declared-not-rendered like `schema` and `backend`; without them
   every v3 ledger refuses as an unknown-key schema change. Writer-coverage totality is asserted
   (every top-level key `ledger.document` emits is in `_KNOWN_FIELDS`), so a body key added later
   cannot silently break every v3 report. The field-level mutation tests
   (`test_morning_evidence.py:115-131, :151-164, :167-176, :198-212`) are re-based on a deliberate
   unsealed `/2` helper (the v3 document with `claims`/`digest` stripped and the schema rewritten),
   because a v3 document cannot lose or mistype a field without the seal refusing first; a new test
   proves that ordering on the v3 document itself. Happy-path and resolver tests keep reading
   through the real writer (`test_morning_evidence.py:47-57`), so the sealed path stays exercised.
6. **`SEAL_SENTENCE` amended** (`morning.py:495-500`), one markdown line retaining the three pinned
   phrases ("sealed to its evidence", "not cryptographically signed", "does not prove the evidence
   matches the run" — `test_morning_render.py:336-338` and the per-line "sign" rule at `:341-353`)
   and adding: a `whetstone-run/2` ledger is not self-sealing; a `whetstone-run/3` ledger is
   tamper-evident against an edit that does not recompute its claims and digest; that is not
   authentication, because anyone who can edit the file can recompute both. The old clause "only
   the checkpoint's own digest is re-derivable from bytes" is false after this unit — a v3 ledger's
   digest is re-derived from its claims — and is removed.
7. **`dataset.digest` under Option A, stated.** `ledger._payload`'s dataset block (`:351-358`)
   carries `"digest": ledger.dataset.digest`. Under the PRD's Option A, `Dataset.digest` is the
   dataset's own seal digest (seal-core), so a ledger's `dataset.digest` field holds the **dataset's
   seal digest**, and `morning`'s `DatasetCounts.digest` (`morning.py:360-367`) and its
   `evidence.dataset_digest` (`:720-723`) follow it unchanged. The ledger seals the *citation*
   (the `dataset` claim covers that string); it does not open or verify the dataset file — that
   stays `check-leakage`'s and the arm's, through seal-core's reader. The committed citations of
   the old value — night #1's `3416702298c3…` in `reports/portability-arm/report.md:27`,
   `docs/planning/gate-leakage-guard/finding.md:86`, `docs/STATUS.md:146` — describe the v1 file on
   disk and do not move; no committed artifact cites a v3 value because no v3 ledger exists and
   none is written in this unit.
8. **Real artifacts, corrected.** `runs/nights/night-001/dataset.json` is `whetstone-training-set/1`
   (seal-core's tolerance; not this aspect). **The real `runs/night-probe/probe-001/ledger.json` is
   `whetstone-run/1`, not `/2`** as `prd.md:186` and `_card/understanding.md:55` state — verified
   2026-10-08 against the primary checkout's bytes, and consistent with `whetstone-run/2` landing
   2026-09-08 (`a500b04`) after the probe's ledger was written 2026-09-05. The shipped reader
   already refuses it (schema equality with `/2`; `docs/STATUS.md:754` records that `check-probe`
   has never been pointed at a real probe), so this aspect neither breaks nor restores it; keeping
   `/1` refused is PRD requirement 6 and is what `test_backend.py:201-218` pins. There is no real
   `/2` ledger: the tolerance is proven by a `/2` fixture in the probe's shape, and a
   loudly-skipped live-primary test records the real file's `/1` schema and its by-name refusal
   (the `test_gate_leakage_finding.py:63-74` pattern).
9. **Hand-rolled minimal ledgers, decided per test.** `test_honest_report_door.py:226-275`,
   `test_check_leakage.py:340-357`, `test_night_integration.py:274-294` and the
   `test_check_probe.py:45-94` probe fixture: see the acceptance criteria for each decision.
10. **Requirement 10, the ledger half.** The breaking change is listed as breaking in the unit's
    `CHANGELOG` `Unreleased` and `docs/STATUS.md` entry: a v3 ledger is refused by any older reader
    by schema equality, exactly as a v2 checkpoint already is; it is a local, gitignored artifact;
    no existing document is rewritten.
11. **Requirement 12, the ledger half.** A source-reading guard in the spirit of
    `test_only_sft_writes_the_checkpoint_document` (`test_checkpoint_seal.py:944-959`): no source
    under `src/whetstone/` outside `ledger.py` writes `LEDGER_FILE`, and the writer declares
    `LEDGER_SCHEMA == LEDGER_SCHEMA_V3`.

Requirement 11 (should-have) is deferred: see Open questions.

## Out of scope

- The dataset: `whetstone-training-set/2`, its reader, `Dataset.digest` semantics and
  `arm.read_selection` — seal-core's.
- `check-leakage`'s disclosure lines, its CLI help, the gate runbook sentence and guard, and any
  finding regeneration — `leakage-link`'s. This aspect touches `check_leakage.py` only at
  `:294-297`'s reader call (no edit) and one fixture schema string.
- The checkpoint: schema, digest computation, bytes, messages, tests; nothing added here changes
  `sft.py`.
- The promotion record, the gate's rule, its exits and retry discipline, the reward, and
  everything under `verify/` and `tasks/`.
- Rewriting or upgrading probe-001, night-001 or any existing document; re-sealing any `/2`
  ledger.
- The morning report's schema, payload shape or a per-document seal flag: the sentence names both
  generations and no field is added (see Open questions).
- `fuse.py`: the correction is recorded in the criteria; it has no run-document read to change.
- The version bump and tag.

## Acceptance criteria (tests first)

Every criterion is a test written before its implementation. Cites are the files that change, not
new test names.

1. **Seal shape and determinism.** For the shipped `_ledger()` fixture: `ledger.document` emits
   `schema == "whetstone-run/3"`; the body keys are exactly the fifteen keys of the old payload
   minus `schema`, none in `seal.UNSEALED_KEYS`; `claims` covers exactly them;
   `digest == seal.claims_digest(document["claims"], schema="whetstone-run/3")` and differs from
   the same claims digested under another document's schema tag (domain separation);
   `ledger.write(path, l).read_text() == ledger.document(l)`. The `test_run_ledger.py:187-206`
   pins stay green, including `document(_ledger()) == path.read_text()` at `:204`. Cross-process:
   fresh interpreters under two `PYTHONHASHSEED` values produce the same sha256 of
   `ledger.document(_ledger())` (the seeding pattern of `test_honest_report_door.py:982-1029`).
2. **v3 happy path and consumers.** `verify_document(path).sealed is True`; `read` returns the
   parsed document. The existing writer-based consumer suites pass unedited — `test_check_probe.py`'s
   `_probe_run` (`:45-94`), `test_morning_evidence.py`'s happy paths and resolvers,
   `test_run_ledger.py`, and the honest-report door's rendering tests once its fixture is `/2`
   (criterion 8).
3. **v2 tolerance and the `/1` refusal.** A `/2` fixture in the probe's shape (`schema` pinned to
   `ledger.LEDGER_SCHEMA_V2`, no `claims`/`digest`) reads with `sealed is False`, byte-unchanged,
   and `read` returns the same fields as before. `verify_document` refuses a `/2` document that
   carries `claims` or a top-level `digest` (the downgrade guard). `test_run_ledger.py:153-162`
   and `test_backend.py:201-218` pass **unedited**, and the discipline they pin survives dual-read
   exactly: `LEDGER_SCHEMA != "whetstone-run/1"` holds with `LEDGER_SCHEMA = LEDGER_SCHEMA_V3`, and
   a `/1` stub is still refused. Dual-read does not weaken the bump's invariant — a required
   field's absence must be impossible under the declared schema — because a `/2` document can
   never carry `/3`'s additions: the downgrade guard refuses seal keys under `/2`, and relabelling
   `/2`→`/3` without a complete claims map refuses as `LedgerUnverified` (criterion 6).
4. **The real-record correction.** A loudly-skipped test resolves the primary checkout (the
   `test_gate_leakage_finding.py:63-74` pattern), asserts `runs/night-probe/probe-001/ledger.json`
   declares `whetstone-run/1`, and asserts `verify_document` refuses it by name — recording the
   corrected premise, not the PRD's. The `/2` tolerance itself is criterion 3's fixture.
5. **Adversarial — every shape, refused by name as `LedgerUnverified`.** On a written v3 document:
   (a) each body key moved, parameterised over `sorted(set(document) - seal.UNSEALED_KEYS)` so a
   body key added later is covered automatically — the value replaced by `[value]`, claims and
   digest untouched, the message naming the key; (b) an unclaimed key added; (c) an orphaned claim
   (claim with no body key); (d) a claim deleted while its body key remains (refused as unclaimed);
   (e) a claim and its body key deleted together with the digest left alone (refused at digest
   reduction); (f) two claims' hash values swapped (the first moved key is named); (g) a claim hash
   that is not 64 lowercase hex; (h) a newline in a claim key. Malformed or unreadable JSON stays
   `LedgerUnreadable`. `issubclass(LedgerUnverified, LedgerUnreadable)` is asserted, each consumer's
   `REFUSALS` holds the base class, and a sample refusal message says "ledger", not "checkpoint"
   (the `subject` parameterisation).
6. **Adversarial — schema strings.** `/3` rewritten to `/2` with the seal keys retained → the
   downgrade guard refuses; `/3` or `/2` rewritten to `/1`, or to anything else → `LedgerUnreadable`
   naming `/2` and `/3`; a `/2` payload relabelled `/3` without claims → `LedgerUnverified` (no
   claims mapping).
7. **The documented limit.** A forger edits a value and recomputes `claims` (through
   `seal.claim_hashes`) and `digest` (through `seal.claims_digest`) consistently:
   `verify_document` accepts and `sealed is True`. The test's docstring states this is the
   unkeyed-hash boundary (`prd.md` § 3), not a defect, as the checkpoint's cheat list does.
8. **The hand-built fixtures, decided.** `test_honest_report_door.py:226-275`: the fixture declares
   `ledger.LEDGER_SCHEMA` (`:238`), which after the bump is `/3`, and it carries none of the fields
   the door reads in a sealed document — the verifying reader refuses it (no claims map), so it
   **must change**. Pinned to `ledger.LEDGER_SCHEMA_V2` it is accepted **unsealed** and every door
   read is unchanged; building a whole `Ledger` through `write` is rejected because the fixture
   exists to feed the door's four reads (`honest_report.py:387-389`), not to exercise the seal. The
   identity test `honest_report.read_ledger is ledger.read` (`:613`) now means the door verifies
   any v3 ledger it is handed; a new test points it at a doctored v3 ledger and expects the named
   refusal with nothing rendered (mirroring `:1077`). `test_check_leakage.py:342-343` — the "minimum
   `ledger.read` accepts" run identifier — pins `LEDGER_SCHEMA_V2` for the same reason.
   `test_night_integration.py:274-294` becomes a deliberate `/2` fixture and its
   `recorded["schema"] == run_ledger.LEDGER_SCHEMA` assertion (`:293`) becomes the v2 constant: its
   point is tolerance of an absent optional record in an older ledger, which is the `/2` path now;
   a companion test asserts that deleting the same key from a v3 document is `LedgerUnverified`,
   not tolerated. `test_check_probe.py`'s `_probe_run` already writes through the real writer, so it
   exercises the sealed path unchanged; a new `/2` probe fixture pins the probe tolerance.
9. **`morning`.** `claims` and `digest` are in `_KNOWN_FIELDS`; a writer-coverage test asserts
   `set(json.loads(ledger.document(_ledger()))) <= morning._KNOWN_FIELDS` (anti-vacuity: both seal
   keys are in the emitted document). A v3 ledger reads through `morning.read_ledger`; a v3
   document with a required field deleted refuses at the seal by name, not at `LedgerFieldMissing`;
   the re-based `/2` fixtures still exercise every `REQUIRED_FIELDS` refusal. The
   `FIELD_SOURCES`/`LedgerDocument` totality test (`test_morning_evidence.py:134-148`) is unchanged
   because no rendered field is added.
10. **`SEAL_SENTENCE`.** The rendered report and `payload["seal"]` carry the amended sentence; it
    contains all three pinned phrases, both generation clauses and "not authentication"; the
    per-line "sign" rule stays green; the rest of the payload and the `whetstone-morning/1` schema
    are byte-identical to before apart from the sentence.
11. **`fuse` correction.** A full read of `fuse.py` (244 lines) finds no read of `dataset.json`,
    `ledger.json`, `LEDGER_FILE` or `DATASET_FILE`: its only document read is the checkpoint's
    provenance through `sft.verify_checkpoint` (`fuse.py:175-182`) and its only write is
    `fusion.json` (`:135-157, :192-194`). The handoff's naming of `fuse` among run-document readers
    is wrong; it has no behaviour to change. (Adjacent, not fixed here: `fuse.py:85` names schema
    `whetstone-run/2` where the checkpoint's own schema is `whetstone-checkpoint/2` (`sft.py:94`) —
    a pre-existing checkpoint-side inaccuracy outside this aspect.)
12. **Guards and scope.** The one-writer guard (In scope 11) passes; no change under `verify/` or
    `tasks/`; `tests/test_reward_path_scope_is_partitioned.py` and
    `tests/test_no_inference_on_reward_path.py` stay green (the seal module is the stdlib-only
    leaf); checkpoint bytes and messages untouched.

## Dependencies and sequencing

- **Depends on `seal-core`:** `whetstone.loop.seal` with `UNSEALED_KEYS`, `claim_hashes`,
  `claims_digest`, `sealed_document` and `verify_claims`, plus the dataset's `sealed`-flag reader
  shape. Nothing here compiles before the module exists; the first task is the adversarial tests
  against `seal.py` as shipped.
- **Independent of `leakage-link`** except for shared files: this aspect edits `check_leakage.py`
  not at all (the verifying read rides the identity import) and one fixture schema string; conflicts
  are one line.
- The writer bump, the reader, `_KNOWN_FIELDS`, the sentence and the fixture updates land in one
  series: a tree where `write` emits v3 while `morning` lacks `claims`/`digest`, or where the
  sentence still denies the seal, fails its own suite. The unit's `CHANGELOG`/`STATUS`/`ROADMAP`
  notes and the breaking-change sentence land with it (PRD § 6).

## Open questions and risks

- **The probe-001 premise is wrong (the one real contradiction found).** `prd.md:186` and
  `_card/understanding.md:55` say `runs/night-probe/probe-001/ledger.json` is `/2`; the bytes are
  `/1` and the shipped reader already refuses them. Two consequences the plan must accept: no real
  `/2` ledger exists to keep reading, and the "real artifacts keep reading" constraint for this
  unit is carried by the dataset half (seal-core) alone. Making `/1` ledgers readable again is a
  PRD-level change (requirement 6 names `/2`+`/3` and requires `/1` refused) and would defeat
  `test_backend.py:201-218`'s invariant that `backend`'s presence is guaranteed — not an aspect
  decision.
- **Per-document seal state is not rendered by the morning report.** The sentence names both
  generations; it does not say which one this report's ledger is. Rendering the state would need a
  `LedgerDocument` field with no payload source, changing the `FIELD_SOURCES`/`LedgerDocument`
  totality test and the morning payload. Requirement 11 is should-have and is deferred to
  `leakage-link`/`night.disclosure` if the plan decides the distinction must appear outside the
  schema string; `verify_document(...).sealed` is the programmatic surface today.
- **`LedgerUnverified` subclasses `LedgerUnreadable`** rather than seal-core's sibling
  `DatasetUnverified(ValueError)`, because the ledger has an existing base every consumer already
  catches. A reviewer should confirm no consumer wants to distinguish "unreadable" from "tampered"
  at the exit level; today none does.
- **The downgrade guard is stronger than the checkpoint reader's tolerance** (`sft.py:915-916`).
  That is deliberate and tested; no legitimate `/2` ledger carries `claims`, and the fail-closed
  direction is the one to be wrong in.
- **Mutation tests and the v2 helper.** If the morning mutation tests were re-sealed instead of
  re-based on `/2`, the suite would keep passing while exercising a forger's power rather than the
  reader's field checks. The spec picks the `/2` helper plus one explicit v3-refusal test to keep
  both surfaces honest.
- **No real v3 ledger exists** and none can be written inside this unit (`runs/` is the operator's;
  night-001 has no ledger at all). v3 behaviour is proven against fixtures and the real writer
  only, as the checkpoint seal was; the first real v3 ledger is the next night's.
- **`honest_report.py:52` spells `LEDGER_FILE = "ledger.json"` a second time** beside
  `ledger.LEDGER_FILE` (`ledger.py:56`). Not this aspect's to change; recorded so the plan does not
  read the one-writer guard as claiming otherwise.
