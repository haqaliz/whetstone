# Spec — `report-writer`

**Unit:** `morning-report` · **Aspect 2 of 4** · PRD: `docs/planning/morning-report/prd.md`

## Problem slice

The evidence is readable (aspect 1); nothing turns it into something a person reads. Today the
only prose this project builds from data is thrown at a terminal and scrolled away
(`night.disclosure`, `night.py:349-382`; `gate.disclosure`, `gate.py:679-703`). This aspect is
the durable, re-derivable version of those two disclosures joined — and it is where every
honesty rule either holds or quietly doesn't.

**User outcome:** one page that says what last night did, where every figure names the document
it came from, and where a bad night reads as a bad night.

## In scope

1. **`build_morning_report(...) -> MorningReport`** — a pure function of
   `(LedgerDocument, PromotionRecord | None)`, returning `markdown` and `payload` (schema
   `whetstone-morning/1`). No clock, no filesystem, no environment.
2. **`write_morning_report(...) -> tuple[Path, Path]`** — writes `report.md` and `report.json`.
   **Two artifacts, not three**: a night produces no cost document, and an empty `cost.json`
   would assert a measurement nobody made.
3. **The lede.** The markdown opens with one sentence naming the night, what the reward kept over
   what was drawn, and whether a candidate exists. Its shape is pinned in a test.
4. **Coverage travels with every count** — the training-set size never appears without its
   denominator and the unverified count beside it (`dataset.py:169-174`,
   `docs/ROADMAP.md:430-435`).
5. **The three unflattering states, each rendered as itself:**
   - **Zero strict-PASS** — the ledger's `checkpoint_absent` reason verbatim; "no candidate was
     produced". Never a blank section.
   - **No gated evaluation** — `record is None` renders *"no gated evaluation is recorded for
     this night"*. A fact, never an omission.
   - **Gate returned `UNVERIFIED`** — "no comparison was made", with both sides' counts over
     both denominators. Never rendered as `PASS`, never as a win.
6. **The record must belong to this night** — refused by name, nothing rendered (PRD
   must-have 7).

   > **Corrected during the build, 2026-08-28.** This requirement said *"a `record` whose
   > `run_id` is not the ledger's"*. That check is meaningless: a promotion record's `run_id` is
   > the **gate evaluation's** operator-declared name (`gate-001`), not the night's, so it would
   > have compared two unrelated strings. The match is on the **checkpoint digest** — a record
   > concerns this night iff the night's checkpoint digest is one of the two the gate compared —
   > which is stronger, because a digest is evidence and a name is a string somebody typed. See
   > `plan_20260828.md`.
7. **Sealed to its evidence.** Every figure names the digest of the document it came from
   (ledger bytes, dataset digest, checkpoint digest, the record's digests). The markdown carries
   a standing sentence stating the boundary: the report is sealed to its evidence, **not
   cryptographically signed**, and re-derivation proves the report matches the evidence — not
   that the evidence matches the run.
8. **`verify_morning_report(dir, ...)`** — re-render from the same evidence and compare bytes;
   any mismatch is refused, naming the artifact.
9. **Reuse by identity** (imported, never copied, asserted `is`): `read_promotion_record` and the
   gate's decision constants (`PROMOTED`/`REJECTED`), the dataset coverage definition,
   `sft.verify_checkpoint` where a checkpoint digest is re-hashed.

## Out of scope

- Any figure from a published home. The report renders **this run's own counts**, whose only home
  is that run's gitignored directory. It must never restate a figure from `reports/baseline/` or
  any other published directory — asserted.
- Path guarding and the output root (aspect 3). The writer takes a directory it is handed.
- The CLI (aspect 4).
- A trend across nights — out of scope for the unit.

## Acceptance criteria

1. A full night + promoted gate renders both artifacts; the payload declares
   `whetstone-morning/1`.
2. The lede's shape is pinned: it names the run id, the kept count **over** the denominator, and
   the candidate's presence or absence.
3. **Watched failing:** a writer that renders the example count without the denominator fails
   the coverage assertion.
4. A zero-strict-PASS night renders `checkpoint_absent` verbatim and states no candidate —
   asserted on the rendered bytes, not on the payload alone.
5. `record is None` renders the named sentence; the section is present and non-empty.
6. A gate that returned `UNVERIFIED` renders "no comparison was made" and **the word `PASS`
   appears nowhere** in the rendered markdown for that night — watched failing against a
   credulous renderer that prints the candidate's solved count as a result.
7. A record whose `run_id` is not the ledger's is refused by name, and **nothing is written** —
   asserted by listing the output directory after the refusal.
8. Byte-identical across two invocations in-process, and across subprocesses under
   `PYTHONHASHSEED` 0 and 1 (`tests/bakeoff/test_prompt_contract.py:159-194` technique).
9. `verify_morning_report` returns clean on an untouched pair and refuses on a one-byte edit to
   either artifact, naming which.
10. The rendered markdown contains the sealing-boundary sentence, and contains the word "signed"
    only in a construction that denies a cryptographic signature — asserted, because this is the
    claim most likely to be quoted out of the artifact.
11. **Locality canary:** donor source text planted in the ledger's reachable fields cannot appear
    in either artifact.
12. No figure from any committed `reports/` artifact appears in the render — asserted against the
    published homes' own bytes.

## Dependencies & sequencing

Depends on aspect 1. Blocks aspect 4.

## Open questions / risks

- The report renders `PromotionRecord.decision` verbatim. If a later gate adds a fourth decision
  string, the renderer must refuse an unknown one rather than printing it beside a headline —
  the enumeration is asserted complete against the gate's own constants.
