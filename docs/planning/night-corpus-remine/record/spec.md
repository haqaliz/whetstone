# Spec — record

**Aspect 2 of 4** for `night-corpus-remine` (`../prd.md`). Owns M3 in full, the byte-identity
half of M6/AC5, and the record half of AC1. **Unit:** `feat/night-remine-before-draw/aliz`
(`../understanding.md`). **Written:** 2026-10-11.

**Depends on:** nothing at the code level — it is independently landable and green against the
current tree. **Provides:** the ledger `task_set.remined` field, its conditional rendering and
its consumer tolerance. **Depended on by:** `remine` (it writes the field from the re-mine it
runs), `guards` (it asserts the round-trip), `docs` (S2 names the block).

## Problem slice and outcome

The night writes a `whetstone-run/3` ledger whose `task_set` object records *which tasks the
night drew against*, as counts and ids (`src/whetstone/loop/ledger.py:137-171` builds it;
`ledger.py:409-428` serialises it). Nothing in that object records that the corpus **grew** this
night, or from which donor: a reader of the evidence cannot tell a night that re-mined five new
commits from a night that drew against the same frozen pool (`../understanding.md:75-79` — "no
corpus membership list and no corpus digest"). The run ledger has no field for the re-mine delta.

Outcome: the re-mine delta is recorded under the existing `task_set` object as a new key
`remined` — `null`-omitted when no re-mine ran, and otherwise a list of `{"task_id": <str>,
"donor": <str>}` sorted by `task_id`, ids and donor labels only, never file contents. A night
**without** the re-mine flags produces a ledger byte-identical to the pre-change tree. No schema
bump: the field is nested under an existing claim, so v3's seal covers it and no reader that
checks top-level keys learns a new key. The `remine` aspect owns minting and passing the pairs;
this aspect owns where they land, how they serialize, and the byte-identity proof.

## In scope

1. **`TaskSet` gains `remined`.** A new frozen field on the dataclass
   (`ledger.py:137-171`), appended after `stratum` so its default keeps every construction
   written before it compiling (the `heldout`/`stratum` precedent, `ledger.py:163-171`):

   ```
   remined: tuple[tuple[str, str], ...] | None = None
   ```

   A tuple of `(task_id, donor)` pairs. `None` means **no re-mine block ran**; `()`
   (an empty tuple) means **a re-mine ran and minted nothing** (M4). The two are distinct and
   both must be representable — see Acceptance criteria 3 and the Edge cases. The field carries
   ids and labels only; the module's own discipline is "hashes and verdicts, never contents"
   (`ledger.py:9-15`) and the canary at `tests/loop/test_run_ledger.py:116-134` must stay green.

2. **`_body` renders `remined` conditionally — the byte-identity lever.** `_body`
   (`ledger.py:383-449`) writes its keys field by field and every body key is a seal claim
   (`ledger.py:383-390`; the sealing is `ledger.py:266-271`). The `task_set` dict
   (`ledger.py:409-428`) must include a `"remined"` key **only when the field is not `None`**:

   - `ledger.task_set.remined is None` → the key is absent. The `task_set` claim's canonical
     bytes are exactly today's, so the whole document is byte-identical to the pre-change tree.
   - otherwise → `"remined": [{"task_id": task_id, "donor": donor} for ...]`, sorted by
     `(task_id, donor)`.

   This is a **deliberate deviation** from the always-present `heldout`/`stratum` `null` style
   (`ledger.py:415-427`, which emit `null` when absent). The deviation is the safety property
   itself: an always-present `"remined": null` would change the `task_set` claim and every
   ledger's bytes, breaking the invariant that a night without the flags is today's night, byte
   for byte. The reason must be stated in the code comment beside the conditional, as the
   `heldout`/`stratum` conditionals state theirs.

   Sorting is applied at the serialization boundary, not trusted from the caller: `mine.py`'s
   iteration order is the donor's commit order (`../understanding.md:51-57`), so a caller that
   passed pairs in minting order would otherwise produce different bytes for the same delta.
   `task_id` is unique by construction (`label-sha12`, `mine.py` per `../prd.md:42`), so the
   `donor` second key is inert for honest input and only makes the order total for any input.

3. **The `TaskSet.remined` field and its one writer.** `run_night` builds the `TaskSet`
   (`night.py:374-382`). The **only** writer of `remined` is `run_night`, from the re-mine it
   itself runs (`../remine/spec.md` R5): `remined=None` when no re-mine block ran, else the
   `RemineReport.minted` pairs (a non-empty or empty tuple). There is **no** `run_night` input
   parameter for `remined` — see the resolved interface decision in Open questions. The one-line
   edit adding `remined=...` to the `TaskSet(...)` call is owned by the `remine` aspect (it owns
   the value); `record` owns the field, its rendering and its tolerance. Until `remine` lands the
   `TaskSet` construction omits the argument and the field defaults to `None` — the byte-identity
   path — so `record` is independently landable and green.

4. **Reader and consumer tolerance, verified — no change required.** The new key is nested inside
   the `task_set` claim, so:
   - **The seal covers it.** `seal.claim_hashes` hashes each top-level body value, including the
     whole nested `task_set` mapping (`seal.py:50-72`, hashing `body.items()` at `:72`), and
     `verify_claims` re-hashes each claim and refuses a changed one by name
     (`seal.py:164-171`). Editing `task_set.remined` without recomputing the document is a
     `LedgerUnverified` naming `task_set`; the top-level claim set is unchanged, so
     `verify_claims`' unclaimed/orphaned checks (`seal.py:151-163`) do not fire.
   - **The reader is generic.** `verify_document` (`ledger.py:299-342`) checks the schema string
     and, for `/3`, calls `seal.verify_claims` (`ledger.py:324-332`); it enforces no top-level
     key set and inspects no nested shape. The `/2` downgrade guard (`ledger.py:333-342`) is
     untouched.
   - **`morning` checks top-level keys only.** `_KNOWN_FIELDS` (`morning.py:207-228`) is compared
     at `morning.py:301-307` against `set(payload)`; `task_set` is read as a block
     (`morning.py:313`) and only its known subfields are extracted (`morning.py:319-366`). No
     code rejects an unknown **nested** key. So `task_set.remined` needs **no** `_KNOWN_FIELDS`
     change and **no** `/4` bump.
   - **`check_probe` and `honest_report` ignore it.** `check_probe.run_check` reads only
     `task_set.probe` (`check_probe.py:201-210`); `honest_report._input` reads only
     `task_set['private']` and `task_set['public']` (`honest_report.py:249,277-280`). Neither
     rejects extra nested keys, and neither changes.
   - **A pre-change reader reads a new remined ledger.** Because the key is nested, an older v3
     reader's `verify_claims` re-hashes `task_set` as a whole and accepts, and its consumers
     extract the same subfields — so the field is forward-compatible and no generation bump is
     needed in either direction.

   A source-reading guard asserts there is **no** nested-shape validator that would refuse the
   key (Acceptance criteria 7).

5. **The byte-identity proof.** A night without the re-mine flags produces a ledger byte-identical
   to the pre-change tree. Proven two ways (Acceptance criteria 1–2): the `_body` conditional
   leaves the `task_set` claim unchanged, and a pinned sha256 of `ledger.document(_ledger())`
   captured on the pre-change tree (see Open questions / the plan) reproduces exactly.

## Out of scope

- **Minting and the night-door flags.** The skip-set/`remine` wrapper, `--remine*` parsing, the
  training-only root union, and computing the `(task_id, donor)` pairs are the `remine` aspect's
  (`../prd.md:204-211`). This aspect only defines where the pairs land and takes them.
- **Rendering the delta in the morning report.** `whetstone-morning/1` is not required to show
  the re-mine block; the PRD says the *ledger* records it so a reader can attribute the set
  (`../prd.md:43-44`). `morning` already tolerates the nested key (In scope 4). Surfacing it on
  the page is a `docs`/later decision — see Open questions.
- **A top-level ledger field, a `/4` schema bump, and any `_KNOWN_FIELDS` edit.** Rejected: the
  invariant is no-flag byte-identity, and a top-level always-present field would break it; a
  nested field under an existing claim needs neither.
- The reward, the gate's rule/exits/retry discipline, the held-out document and its split, the
  corpus's declared 66-task record (`tasks/local-ledger.json`, `tasks/recipes/`), the dataset
  document and `train.jsonl`, and everything under `src/whetstone/verify/`.

## Acceptance criteria (tests first)

Strict TDD: every criterion is a test that fails on the current tree and passes after the change
(`uv run pytest` green). Cites are the files that change.

1. **The field round-trips, sorted, ids only.** A `Ledger` whose `TaskSet.remined` is a tuple of
   `(task_id, donor)` pairs written through `run_ledger.write` and read back through
   `run_ledger.read` yields `recorded["task_set"]["remined"] == [{"task_id": ..., "donor": ...},
   ...]` sorted by `(task_id, donor)` regardless of input order (feed them reversed). The entry
   dicts have exactly the keys `{"task_id", "donor"}`. Build the fixture with
   `dataclasses.replace` on the shipped `tests/loop/test_run_ledger.py:_ledger()` (frozen — do
   not edit it; `tests/loop/test_night_integration.py:284` imports it).

2. **The no-remine byte-identity pin.** For the unmodified shipped `_ledger()` fixture
   (`remined` defaulted to `None`), `ledger.document(_ledger())` hashes to the value captured on
   the pre-change tree **before any source edit**:
   `sha256 = 4fe1022f659fe0b98123dbbf011ace415fd1b9210a6ebee83f6f49ef9aae392d`. The test also
   asserts structurally that `"remined" not in json.loads(document)["task_set"]`, so the failure
   names `remined` rather than only "the bytes moved". This is the ledger half of AC5/M6.

3. **`None` vs. empty, both representable.** `remined=None` → no `"remined"` key;
   `remined=()` → `"remined": []` present. Two tests, because the distinction is M4's "the
   delta is empty (recorded)" versus "no re-mine block ran" and a single boolean cannot carry it.

4. **A night without the flags reproduces the golden ledger.** A night run through
   `tests/loop/test_night.py`'s `_night` helper (its injected engine/trainer/runtime) with no
   `remined` argument writes a `ledger.json` whose `task_set` has no `"remined"` key and whose
   bytes equal a second identical unflagged night's — the determinism half of M8/AC3 as it
   touches the ledger. (The `dataset.json`/`train.jsonl` half of AC3 is `guards`'.)

5. **The writer is the seam.** Given a `Ledger` whose `TaskSet.remined` is a tuple of pairs,
   `run_ledger.document(ledger)` emits `task_set.remined` as the sorted list — asserted at the
   `document()` boundary (the pure writer), complementing Criterion 1's `write`→`read`
   round-trip. The full end-to-end AC1 (mint → draw → ledger) is the `remine` aspect's; this
   aspect never drifts a second writer into `run_night` (Open questions).

6. **The seal covers the nested field — tamper refused by name.** On a genuine v3 document with a
   `remined` list, deleting or mutating `document["task_set"]["remined"]` and rewriting the file
   (leaving `claims`/`digest`) raises `run_ledger.LedgerUnverified` matching `"task_set"` — the
   `tests/loop/test_night_integration.py:307-322` pattern, one level deeper. A companion test
   asserts that a forger who recomputes `claims` and `digest` through `seal.claim_hashes` /
   `seal.claims_digest` is accepted with `sealed is True` and its docstring states this is the
   unkeyed-hash boundary (`ledger.py:79-88`), not a defect.

7. **No nested-shape validator refuses the key.** A source-reading test asserts no module under
   `src/whetstone/loop/` validates a nested `task_set` key set: `morning._KNOWN_FIELDS`
   (`morning.py:207`) is a flat frozenset compared only against `set(payload)`
   (`morning.py:301`); `ledger.verify_document` (`ledger.py:299-342`) checks only the schema
   string; `check_probe` reads only `task_set.probe` (`check_probe.py:201-210`); `honest_report`
   reads only `task_set['private']`/`task_set['public']` (`honest_report.py:249,277-280`). A
   v3 ledger carrying `task_set.remined` reads through `morning.read_ledger`,
   `check_probe.run_check` and `honest_report`'s read unedited. **If any of these is found to
   reject nested keys, stop and report — the plan must then add the minimal tolerance fix, and
   this criterion is the tripwire.** (As read on 2026-10-11, none does.)

8. **The canary still holds.** `tests/loop/test_run_ledger.py:116-134` stays green **unedited**,
   and a new test writes a ledger whose `remined` donor labels and ids look like a donor's and
   asserts no source text and no prompt reaches the bytes — `remined` carries ids and labels,
   never content.

9. **No schema bump.** `ledger.LEDGER_SCHEMA == ledger.LEDGER_SCHEMA_V3` (`ledger.py:63`) is
   unchanged, and `tests/loop/test_backend.py`'s `LEDGER_SCHEMA != "whetstone-run/1"` pin and
   `tests/loop/test_run_ledger.py:153-162` (unknown schema refused, message names
   `LEDGER_SCHEMA`) stay green unedited.

## Dependencies and sequencing

- **Independent at the code level.** `TaskSet` / `_body` / the `run_night` parameter can land
  with `_ledger()`'s `remined=None`, no `remine` module in the tree: the field default is `None`
  and the seam's default is `None`, so every existing caller compiles and every existing test
  stays green. This is deliberate — the `record` and `remine` aspects are independent code
  (`../prd.md:217-219`) and `record` may land with or just before `remine`.
- **The `remine` aspect** writes the field: its `run_night` change adds `remined=...` to the
  `TaskSet(...)` call (`night.py:374-382`). Until it lands no caller sets the field and the
  byte-identity path is the only one taken.
- **The `guards` aspect** owns the held-out invariant, the dataset/train.jsonl determinism and
  the reward-untouched checks; this aspect owns only the ledger bytes and the field.
- **`docs`** lands last in the same commit as the write-up, per the repo's rule; nothing here
  writes status.

## Open questions and risks

- **Interface shape — resolved (2026-10-11, integrator).** The seam is the `TaskSet.remined`
  field, and its **single** writer is `run_night`, from the re-mine it runs internally
  (`../remine/spec.md` R5). The earlier draft's `run_night(remined=...)` **input parameter is
  dropped**: `run_night` already owns the minted value, so an input parameter would be a second
  writer of the same field — a second answer, which this repo's conventions forbid. `record`
  therefore owns the field, its rendering and its tolerance; `remine` owns the one-line
  `TaskSet(remined=...)` call. `record`'s tests exercise the field through `write`/`read` and the
  pure writer, never through a `run_night` argument.
- **Byte-identity golden is a fixture hash, not a fixture file.** Criterion 2 pins the sha256 of
  `ledger.document(_ledger())`. The fixture is fully hand-built with a fixed `tool_versions` dict
  and a fixed `backend` (`tests/loop/test_run_ledger.py:88-95`), so the document is
  environment-independent and the hash is stable. It is captured before either aspect edits the
  tree (the plan's first task); the agent must not regenerate it after the change.
- **The conditional-key style is a deviation.** A reviewer may prefer the `heldout`/`stratum`
  always-present `null` style for uniformity. It is rejected here on the safety property alone
  (In scope 2): it would move every ledger's bytes. The comment beside the conditional must say
  so, or a later "uniformity" cleanup silently breaks M6/AC5.
- **A `remine` delta larger than the ledger should carry.** The pairs are a list proportional to
  the minted count, bounded by `--remine-limit` (`../prd.md:99-102`); it is ids and labels only,
  not a corpus list, so the ledger stays "hashes and verdicts"-shaped in spirit. If a future
  re-mine could mint thousands, the field would want a digest — not this slice.
- **No real remined ledger exists.** The first is the next night that runs with the flags. The
  behaviour is proven against the real writer and fixtures only, as every earlier schema change
  was.
