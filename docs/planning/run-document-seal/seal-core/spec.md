# Spec — seal-core

**Aspect 1 of 3** for `run-document-seal` (`../prd.md`). Owns PRD requirements 1–3 and 8.
**Depends on:** nothing. **Depended on by:** `leakage-link`, `ledger-seal` (both consume the
shared seal module and the dataset's verifying reader).

## Problem slice and outcome

The checkpoint's seal primitives live private to `sft.py` (`_canonical` `:158-166`,
`_claim_hashes` `:169-186`, `_claims_digest` `:189-202`, `_verify_claims` `:1036-1094`) and the
dataset has none. Outcome: one stdlib-only seal module with a single implementation of the hash
logic, used by `sft` with **byte-identical** checkpoint behaviour; a `whetstone-training-set/2`
dataset that is tamper-evident for every claim; `Dataset.digest` becomes the document's seal, which
a new checkpoint records unchanged in kind (the value a checkpoint's `dataset_digest` names for a
v2 dataset is the document's own seal); and the arm's reader verifies instead of trusting. v1
documents (night-001) still read, unsealed, and are never rewritten.

## In scope

1. **`src/whetstone/loop/seal.py`** — stdlib-only (`hashlib`, `json`, `re`) and typed for
   `mypy --strict`:
   - `UNSEALED_KEYS: frozenset[str] = frozenset({"schema", "digest", "claims"})`
   - `CLAIM_HASH: re.Pattern[str]` — 64 lowercase hex, the injectivity pin.
   - `canonical(value: Any) -> bytes` — the JSON round trip, `sort_keys=True`,
     `separators=(",", ":")`, `ensure_ascii=True`, `.encode("ascii")`.
   - `claim_hashes(body: Mapping[str, Any], *, subject: str, refuse: type[Exception]) -> dict[str, str]`
     — refuses `UNSEALED_KEYS` and newline-bearing keys by name.
   - `claims_digest(claims: Mapping[str, str], *, schema: str) -> str` — sha256 over
     `schema + "\0" + sorted key:hash lines` (the domain separation).
   - `sealed_document(body: Mapping[str, Any], *, schema: str, subject: str, refuse: type[Exception]) -> dict[str, Any]`
     — `{"schema": schema, "digest": ..., "claims": ..., **body}`.
   - `verify_claims(document: Path, raw: Mapping[str, Any], *, schema: str, subject: str, refuse: type[Exception]) -> None`
     — the `_verify_claims` logic moved verbatim, with every message parameterised only by
     `subject`; passing `subject="checkpoint"` reproduces the current checkpoint messages
     byte-for-byte.
2. **`sft.py` delegates.** `_canonical`, `_claim_hashes`, `_claims_digest`, `_CLAIM_HASH`,
   `_UNSEALED_KEYS` and the body of `_verify_claims` move to `seal.py`; `sft` imports them under
   its existing private names or calls them directly. No checkpoint byte and no checkpoint error
   message changes; the checkpoint seal tests (`tests/loop/test_checkpoint_seal.py`, pinned
   canonical bytes and cheats A–D) run unedited.
3. **Dataset schema `whetstone-training-set/2`.**
   - Constants: `DATASET_SCHEMA_V1`, `DATASET_SCHEMA_V2`, `DATASET_SCHEMA = DATASET_SCHEMA_V2`.
   - Body: `denominator`, `unverified`, `coverage`, `examples` (the derived `coverage` is in the
     document, so it is claimed like every other payload key).
   - `Dataset.digest` is the seal digest over that body, computed in `build`; `write_document`
     writes `sealed_document(...)` through `document()` with the same deterministic
     `json.dumps(indent=2, sort_keys=True) + "\n"` framing. The examples-only `_digest` is retired.
   - `night.run_night` (`night.py:336`) and any arm writer emit v2 through the existing writer.
4. **Verifying dataset reader.**
   - `DatasetUnverified(ValueError)` — the named refusal; malformed shape, moved claim, unclaimed
     key, orphaned claim, and digest mismatch are all this type, never a stray `KeyError`/`TypeError`.
   - `verify_document(path: Path) -> VerifiedDataset` — a frozen dataclass carrying the parsed
     `document: Mapping[str, Any]` and `sealed: bool`; accepts `whetstone-training-set/1`
     (`sealed=False`, no claims check, exactly today's parse) and `/2` (claims verified first);
     any other schema refused.
   - `read_document(path) -> Mapping[str, Any]` stays public as `verify_document(path).document`,
     so `check_leakage`'s import keeps working and the verifying path is the only path.
5. **`arm.read_selection` verifies.** It reads through `verify_document`; v1 is accepted as today;
   v2 is verified; a tampered v2 raises the named refusal rather than proceeding to train. Its
   docstring and messages stop calling an unchecked file "sealed" (`arm.py:84-97`), and the
   refusal is a named one the CLI turns into exit 2, not a traceback.
6. **Stale prose in this aspect's blast radius is corrected in the same commit:** the `Dataset`
   docstring's "sha256 over the canonical document" (`dataset.py:180-182`) becomes true and is
   stated precisely; `example_of`/`build` docstrings that describe the digest's material follow the
   new computation.

## Out of scope

- Any change to the checkpoint's schema, digest computation, error messages or tests.
- The ledger (`ledger-seal`) and `check_leakage`'s disclosure lines / CLI help / runbook
  (`leakage-link`).
- Rewriting or upgrading any existing document.
- Any change under `verify/` or `tasks/`, the reward, the gate's rule or exits.
- The portability-arm report prose (owned by `leakage-link`).

## Acceptance criteria (tests first)

1. `seal.py` has no non-stdlib imports; `tests/test_no_inference_on_reward_path.py` and
   `tests/test_reward_path_scope_is_partitioned.py` stay green.
2. Checkpoint bytes unmoved: the existing `test_checkpoint_seal.py` suite passes **unedited**,
   including the pinned canonical bytes, the claim-edit cheats, the merged-key forgery and the
   v1/v2 domain-separation tests; a new test asserts `write_checkpoint` output for a fixture is
   byte-identical to the value captured before the extraction.
3. A v2 dataset document built from a fixture:
   - verifies through `verify_document` (`sealed is True`) and its `digest` equals
     `Dataset.digest` and `document()["digest"]`;
   - edited in `examples`, `denominator`, `unverified` or `coverage` (one test each) is refused by
     name, and the message names the key that moved;
   - with an unclaimed key added, a claim deleted, two claim values swapped, a claim hash that is
     not 64-hex, a newline in a claim key, or the schema string rewritten to `/1` (with the v1
     digest not recomputing), is refused by name — one adversarial test per shape, in the spirit of
     the checkpoint's cheat list;
   - a forger who rewrites a claim *and* the claims *and* the digest together is not caught, and a
     test documents that limit rather than implying otherwise.
4. Determinism: `tests/loop/test_dataset.py`'s byte/digest equality and
   `tests/loop/test_night.py`'s byte-identical-training-set tests pass with the v2 document; the
   same inputs produce the same seal on repeated builds and across processes.
5. v1 tolerance: a fixture in night-001's shape (`/1`, examples-only digest) reads through
   `verify_document` with `sealed is False`, byte-unchanged, and `read_document` returns the same
   mapping as before.
6. The link's far end: a checkpoint written by the night/arm flow over a v2 dataset records
   `dataset_digest == dataset.document()["digest"]`, asserted end to end with a fake trainer
   (the same pattern as the checkpoint tests' fake adapter files).
7. `arm.read_selection`: v1 fixture → same `(digest, count)` as before; v2 fixture → the verified
   digest; tampered v2 → the named refusal; no schema-check-free `json.loads` path remains
   (source-reading guard).
8. Nothing under `verify/` or `tasks/` is modified (`git diff --name-only` in review; the suite's
   scope guards stay green).

## Dependencies and sequencing

- First aspect; no dependency. `leakage-link` and `ledger-seal` consume `seal.py` and
  `verify_document`.
- `night.run_night`'s dataset write and `arm.read_selection` change here; the ledger they also
  write is untouched until `ledger-seal`.

## Open questions and risks

- **Exception naming.** `DatasetUnverified` is the working name; the plan pins it and the CLI
  refusal mapping. It should subclass `ValueError` so existing `(OSError, ValueError)` wrapping
  sites can be audited deliberately rather than swallowing it.
- **Refactor risk on shipped seal code.** The extraction touches a freshly sealed checkpoint path.
  Mitigation: byte-pinned tests run unedited plus the new byte-identity test; the extraction is the
  first task and must leave the suite green before any dataset change.
- **`coverage` claiming.** The recommendation is stated: claim it because it is in the document.
  If the plan finds a reason it must be derived on read, that is a PRD-level change.
- **Fixture modernization.** Tests with hand-rolled dataset documents
  (`tests/loop/test_arm.py:57-65`, `tests/loop/test_check_leakage.py:342-343, 591-598`) are decided
  per test: either write through the real writer or declare the fixture v1-unsealed on purpose.
