# Spec — the run-side stratum filter (aspect 2 of `p2-easier-stratum`)

**Boundary:** the run-side inclusion filter that consumes the committed stratum document
(schema `whetstone-stratum/1`, aspect 1's deliverable). Nothing here computes difficulty,
writes a stratum document, moves a report home, or runs a probe.

## Problem slice

The probe must score **exactly the stratum's tasks** from the loaded source-B corpora — the
task-side fork test of the P2 premise (`prd.md` § 1). The run has no inclusion filter today:
it restricts by whole-directory `--tasks`, positional `--probe N`, and exclusion-only
`--dev-subset` (`run.py:691-839`). A stratum input is new, and the seam it plugs into is the
partition (`run.py:540-543`) — **before** the contract is frozen, so the two audit trails
cover the subset automatically: `freeze` digests the posed prompts of the tasks it is handed
(`run.py:410-465`, "the set of digests the declared template produces over the **scored**
set", `run.py:195-199`), and `Conducted.scored` is derived from the sweeps over the filtered
sets (`run.py:614-618`).

The document is a **pinned input** (`PREREGISTRATION.md:131-138`): the run consumes it,
never a live recomputation of difficulty values — a task set changed by the stratum is a new
series, which is aspect 3's non-comparability ground. Drift is a named error, never silently
repaired, in the exact posture `UnknownDevSubset` holds for the dev subset (`run.py:166-172`,
`run.py:963-982`).

## Decisions (code-grounded)

- **D1 — `--stratum PATH` is an optional flag; absent means today's run, byte for byte.**
  Added to `build_parser` beside `--dev-subset` (`run.py:773-781`), threaded through `main`
  (`run.py:858-875`) into `conduct` (`run.py:488-507`), default `None`. The no-retries
  precedent fixes the byte-identity requirement: a run without the flag must reproduce the
  baseline contract exactly (`freeze` docstring, `run.py:437-440`).
- **D2 — the filter narrows source B only; source A is always scored in full.** Both sources
  always publish together (`PREREGISTRATION.md:142-143`), and `MissingSource` refuses a
  one-source report (`report.py:488-500`). The stratum membership is defined over the
  source-B corpus (aspect 1, M2); the public source is untouched by it.
- **D3 — the dev-subset overlay is unchanged and applies on top.** `_partition` keeps its
  shape (`run.py:963-982`): declared ids excluded from **both** sources, unknown id refused.
  The filter runs before it: load → stratum inclusion (private only) → `_partition`
  (dev overlay) → refuse an empty scored private set **before freeze** (the `MissingSource`
  backstop at `report.py:488-493` would fire only after the night is spent). The
  `ScoredDevSubset` backstop (`report.py:139-145, 502-514`) stays byte-identical and still
  fires for any dev id that reaches the scored set by any path.
- **D4 — the loader is aspect 1's deliverable, consumed here by identity.** The document
  machinery (schema, writer, loader, digests, refusal classes) lives in aspect 1's module
  `src/whetstone/bakeoff/stratum.py` (its own no-inference AST walk, the
  `preanalysis.py`/`diffcheck.py` pattern, `tests/bakeoff/test_autopsy_guards.py:225-256`; the
  strict field-by-field decode with no defaults, the transcript codec discipline, PRD N1). This
  aspect imports it by identity — `stratum.load_stratum is stratum.load_stratum`, asserted `is`
  in a test (the diffcheck identity rule: imported, never copied) — and adds only the run-side
  `include_stratum(membership, tasks)` plus the `run.py` wiring. The four named checks are the
  loader's, each refusal by name:
  1. **Schema** — `schema == "whetstone-stratum/1"`; an old schema fails decode by name,
     never defaults (PRD N1).
  2. **Rule digest** — the document's `rule_digest` must equal the current rule module's
     digest, imported **by identity** from aspect 1's module (the diffcheck identity rule:
     imported, never copied, asserted `is` in a test). Drift between the committed rule and
     the committed document is a refusal, never a repair.
  3. **Document digest** — the document carries a digest over the canonical payload of its
     other fields (schema, rule digest, band, values, membership). Hand-editing any field
     breaks it, and the loader refuses rather than trusts. `document_digest_of` is the one
     canonicalization aspect 1's generator must call (see Open questions 1).
  4. **Membership** — empty membership refused (the empty-directory discipline,
     `manifest.py:71-75`); every id must match a **loaded private** task, refused by name
     with the loaded ids (mirroring `run.py:968-976`); duplicate ids refused; the `values`
     key set must equal the membership set.
- **D5 — inclusion preserves load order.** The filter returns the included tasks in the
  corpus's sorted load order (`manifest.py:58-85`), never in membership order, so a run's
  sequence is a property of the corpus as today. `--probe N` slices the filtered set
  (`run.py:551-552`) and is unchanged.
- **D6 — the provenance names the stratum.** `conduct`'s `task_set` sentence
  (`run.py:641-645`) names the stratum document and its membership count when `--stratum`
  is given; the count itself already follows `len(private_tasks)` (`run.py:641`). `run.py`
  is not pinned and may be edited. Aspect 3 renders the home.
- **D7 — dev ∩ stratum is exclusion, not refusal.** PRD M3 fixes "applies on top": a
  declared dev id inside the membership is excluded from scoring and denominators (the
  real probe expects this — the 5 declared dev ids may fall inside the band). The doctored
  document that smuggles a dev id in is refused by D4's checks, not by the overlap.

## In-scope requirements

- `src/whetstone/bakeoff/stratum.py` — `STRATUM_SCHEMA`, `Stratum` (frozen), the four
  checks of D4, `UnknownStratumId` / `EmptyStratum` / `StratumSchemaError` /
  `StratumDigestMismatch`, `document_digest_of`, `include_stratum(membership, tasks)`.
- `src/whetstone/bakeoff/run.py` — the `--stratum` flag (`run.py:691-839`), `conduct`
  parameter (`run.py:488-507`), the filter at the partition seam (`run.py:540-543`), the
  empty-after-overlay refusal before `freeze`, the refusal catch in `main`
  (`run.py:876-877`), the task_set sentence (`run.py:641-645`). Nothing else.
- Tests: new `tests/bakeoff/test_stratum_loader.py` and
  `tests/bakeoff/test_stratum_filter.py`, reusing `_run`/`_corpus` from
  `tests/bakeoff/test_run.py:168-221` (the `test_dev_subset_mechanism.py:26-28` pattern);
  parser tests in the filter file (the `test_run_contract_flags.py` shape).
- The no-inference walk over `stratum.py`; the AC2 pins untouched and re-proven
  (`tests/bakeoff/test_format_hardening_frozen.py`): `src/whetstone/verify/`,
  `src/whetstone/bakeoff/patch.py`, `src/whetstone/bakeoff/attribution.py` byte-identical
  to `origin/master` — no edit is planned to any of them.

## Acceptance criteria (tests written first)

1. **Inclusion semantics** — a stratum selecting `{alpha, gamma}` from a three-task corpus:
   `Conducted.scored == {alpha, gamma, pallets__flask-4045}`; the private denominator is 2
   and the public denominator 1; `set(contract.posed.values())` is exactly the stratum's
   tasks plus the public instance (no prompt digest exists for the excluded task).
2. **Unknown-id refusal** — a membership id matching no loaded private task is refused by
   name, and the refusal lists the loaded ids.
3. **Empty-stratum refusal** — an empty membership is refused by name.
4. **Schema refusal** — a `whetstone-stratum/0` (or absent) schema fails decode by name;
   an unknown field or wrong type fails the same way.
5. **Digest-mismatch refusal** — a document whose `rule_digest` does not equal
   `difficulty_axis.rule_digest()` is refused, and a document whose membership was
   hand-edited (stale `document_digest`) is refused rather than trusted; each refusal names
   which digest and the expected prefix.
6. **Dev-subset interplay** — a declared dev id inside the membership is excluded from
   scoring and from both denominators; a stratum whose membership is wholly dev-excluded is
   refused **before freeze** (no cost sidecar, no report); the `ScoredDevSubset` backstop
   still fires when a dev id reaches the scored set through the stratum path.
7. **Both sources** — source A's denominator is unchanged by `--stratum`, and both sources
   are published together.
8. **Contract covers the subset** — the stratum run's contract SHA differs from the
   no-stratum run's, and the sealed prompts are exactly the subset's (AC 1's posed check).
9. **Adversarial** — a doctored document (valid-looking, membership edited to add a declared
   dev id, digest not regenerated) is refused; a hand-edited membership is refused rather
   than trusted (both watched failing against a loader without the checks first).
10. **Byte-identity** — a run without `--stratum` reproduces today's contract SHA; the full
    suite, `uv run mypy src/`, `uv run ruff check .`, and the AC2 pins all stay green.

## Out of scope

- The difficulty rule and the stratum document itself — aspect `difficulty-axis`.
- The report home, the one-home guard move, the § 10.5 amendment — aspect 3 (the
  `task_set` sentence edit is here because it is run-side; the home renders it).
- The runbook and the operator's run — aspect 4.
- Any edit to `src/whetstone/verify/`, `src/whetstone/bakeoff/patch.py`,
  `src/whetstone/bakeoff/attribution.py` (AC2 pins). Any figure about a model.

## Open questions / risks

1. **`document_digest` is in the schema (aspect 1, reconciled).** The hand-edit refusal
   (AC 9) is mechanically impossible without a digest that covers the membership; aspect 1's
   spec D5 now carries the field and `document_digest_of`, and this aspect's checks 3 and 4
   consume them by identity. Closed at integration time — see
   `difficulty-axis/spec.md` D5.
2. **Aspect 1's module is `whetstone.bakeoff.stratum`** — not `difficulty_axis`. The plan
   adapts at that seam only; the identity assertion is what matters, not the name.
   Closed at integration time — see `difficulty-axis/spec.md` D1.
3. **Unknown-id scope is the loaded private corpus only** — a public id in a stratum is
   refused (it matches no private task). A union scope would let a stratum "know" a public
   id it cannot filter, which is meaningless.
4. **The identical-to-the-whole-declared-set degeneracy is aspect 1's** (document time,
   PRD M2). The run-side refuses only an empty membership and an empty scored set after the
   overlay; whether the loaded corpora happen to equal the membership is the operator's
   loading choice, not a document defect.
5. **A fully regenerated doctored document** (digests recomputed) passes the run-side
   checks. The defence is layered: git history + ordering (document committed before the
   run) and aspect 1's "provably computable" recomputation test. Stated, never reconciled.
6. **The dev ∩ stratum overlap is expected in the real probe** (M4's 5 declared dev ids may
   sit inside the band), so D7's exclusion must be asserted explicitly and not "fixed" into
   a refusal by a later editor.
