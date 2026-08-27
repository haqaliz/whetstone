# Spec — report-writer (aspect 2 of honest-number-report)

## Problem slice

The § 4 shape needs a document nobody can write yet. The writer is the only place the
pre-registered headline may be instantiated — `test_the_p4_headline_skeleton_is_refused`
(tests/bakeoff/test_report.py:323) forbids the bake-off report from doing it, so this must be
a **new** writer on the five-writer precedent in `src/whetstone/bakeoff/report.py`
(`build_<name>_report` / `write_<name>_report` pairs, frozen dataclass with
`markdown`/`payload`/`cost`, three-artifact shape, deterministic and pure).

## In-scope

- `build_honest_number_report` / `write_honest_number_report`, schema
  `whetstone-honest-number/1`, three artifacts (report.md / report.json / cost.json),
  reusing `_row`, `_over`, `_contract_fields`, `_contract_block`, `_counts`, `tally` **by
  identity** (monkeypatch-proven, the `test_the_larger_base_writer_reuses_the_shared_helpers_by_identity`
  pattern).
- **The § 4 shape** (`PREREGISTRATION.md:57-72, 140-167`): headline `+a of b held-out tasks
  (baseline c of b, final d of b) / coverage e of b / N: f at baseline, g at final`; both
  sources always in the same document; source A per-instance, never a rate; every rate
  carries its denominator; zero or negative deltas rendered as plainly as positive ones.
- **Whose counts are "final" is the decision's function** (PRD gate-resolution 4): promoted →
  candidate; rejected → incumbent (candidate disclosed as the rejected attempt); UNVERIFIED →
  **no headline**, decision + both sides' counts, "no comparison was made", never a delta
  that reads as a win. Coverage renders on both sides; the headline's `e` is the final side's.
- **The baseline figures arrive through the loader, never a copy:** the writer takes plain
  values; the door (aspect 3) reads the sealed artifact. The writer's document renders the
  baseline-side counts byte-equal to the artifact's own figures (asserted), the disjointness
  exception the one-home guard admits (aspect 4).
- Declaration-only state: "**No count is measured here: the report has not run.**" — a module
  constant, writer-generated, no `N of M`, no contract fields, no per-side counts; cost.json
  declaration on the baseline precedent.
- Determinism: no clock, fixed serialization order, `json.dumps(indent=2, sort_keys=True) +
  "\n"`; `recorded_on` is an input.
- Locality discipline: counts, verdicts, provenance — never task contents, never patch
  content; a canary test plants donor source text and asserts it cannot reach any artifact.
- The provenance block: pinned seeds (the promotion record's run ledger fields — model
  revision, task set, tool versions arrive from the record; where the record lacks a field,
  the door supplies it — the writer renders what it is given), the § 7.3-open base sentence,
  the retry facts, `N` sentences (`_N_SENTENCE` by identity).

## Out-of-scope

- Reading any evidence document (the door does that; `report.py` never imports
  `whetstone.loop.*` — the `_BASELINE_EVIDENCE_SCHEMA` declared-string precedent,
  report.py:1112-1117).
- The door, the amendment, the runbook (aspects 3-5).
- Any change to the five existing writers or their homes.
- A delta rendered when the series disagrees — that is the door's refusal (PRD decision 3).

## Acceptance criteria

1. The writer is pure: same inputs → byte-identical output in-process and across
   subprocesses under `PYTHONHASHSEED` 0 and 1.
2. The helpers are reused by identity: monkeypatching each helper's binding at
   `whetstone.bakeoff.report` changes the writer's output.
3. The headline instantiates the § 4 shape exactly for a promoted decision; a rejected
   decision renders the incumbent as final with the candidate disclosed; an UNVERIFIED
   decision renders no headline and no delta, with the decision's counts.
4. Source A appears per-instance with its funnel context, never as a rate; both sources in
   the same document; every `N of M` figure is rendered via `_over` by identity.
5. The baseline-side figures equal the sealed artifact's figures byte-for-byte (the
   fixture provides the artifact-derived values).
6. Declaration state holds no `N of M` in any spelling and is writer-generated (a hand-typed
   twin fails the tests).
7. The locality canary holds: planted donor source text reaches no artifact.
8. `test_the_p4_headline_skeleton_is_refused` still passes (the bake-off report remains
   forbidden from the shape — the new writer does not touch `build_report`).
9. The disjointness scan (aspect 4's guard) passes for the writer's output: no figure from
   the four existing homes (`baseline`, `format-hardening`, `easier-stratum`,
   `larger-base`) appears, except the loader-derived baseline figures (the argued
   exception).

## Dependencies & sequencing

- Depends on: the five-writer precedent in `report.py` (all in place); aspect 1's
  promotion-record field shapes (the writer's input dataclass mirrors them; plain values,
  no import).
- Second of the five aspects; aspect 3 (door) and aspect 4 (home/amendment) consume it.

## Open questions

- None — the shape, the decision semantics, and the exception are fixed by the PRD and its
  gate resolutions.