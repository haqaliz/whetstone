# Spec — sample-amendment (probe-sample-pin)

**PRD:** `../prd.md`. **Branch:** `feat/probe-sample-pin/aliz`. **Date:** 2026-10-31.

## Problem slice

§ 10.25 pins "the first 16 private tasks" without naming them. The sample is deterministic today
only because the sheet fixes the roots order and files sort by id; a corpus change or a reordered
`--tasks` silently measures a different sample. This aspect appends § 10.26, naming the 16 ids
and disclosing the 4 known `NO_ORACLE` tasks, before the probe runs.

## In-scope

1. Append § 10.26 to `PREREGISTRATION.md` with the text drafted below, and its 4-column log row
   above the other rows (newest at the bottom of the table, following the existing order).
2. `tests/test_docs.py`: a `test_the_probe_sample_amendment_names_the_sample` that:
   - asserts the `### 10.26` heading, the Type 1 line, "does not edit § 10.25", "no success
     threshold", "rewords nothing in § 1, § 4 or § 6";
   - derives the expected 16 ids from the committed `tasks/local-ledger.json`, the five dev ids
     and `tasks/heldout/source-b.json`, in the sheet's roots order (donor-b then donor-a),
     applying the dev overlay then the held-out exclusion, and takes the first 16;
   - extracts every `donor-[ab]-[0-9a-f]{12}` token from the § 10.26 section and asserts the set
     equals the expected 16;
   - asserts the section names the four `excluded` ids and says "not dropped", "NO_ORACLE",
     "272", "at least one", "No count has been measured", "§ 3 baseline remains unspent";
   - asserts the log row.
3. `docs/planning/torch-mps-series/night-sheet/spec.md`: a dated one-line supersession note at
   the top, naming the live sheet and § 10.25/§ 10.26. Do not rewrite the historical spec.

## Out-of-scope

Changing § 10.25's base, budget, GO rule, held-out document or sample membership; running the
probe; the code pin or the sheet (separate aspects).

## Acceptance (test-first)

- The new docs test fails before § 10.26 exists and passes after it.
- The extracted id set equals the derived 16 exactly; adding or removing a corpus task without
  updating the amendment fails the test.
- `uv run pytest tests/test_docs.py -q`, `ruff`, `mypy` green.

## Draft § 10.26 text

```markdown
### 10.26 The § 10.25 probe's 16-task sample is named — 2026-10-31

**Type 1 (§ 8.1): pins the inputs of a measurement, committed before the probe it governs runs.**
It introduces no success threshold, rewords nothing in § 1, § 4 or § 6, and **does not edit
§ 10.25**: this document is append-only, and the 272-draw rule keeps its text byte-intact. What
changes is that the sample § 10.25 called "the first 16 private tasks" is named by id, so the
measurement is the same sample on any machine and any later reader can audit it.

**The sample.** Under the Torch/MPS sheet's roots order (`--tasks .../donor-b` then
`--tasks .../donor-a`), the five declared dev ids and the § 10.16 held-out document, the first
16 private tasks are:

- `donor-b-0cfbb1590a70`, `donor-b-0f8651175ef8`, `donor-b-0fe4582aeac1`,
  `donor-b-45740535725b`, `donor-b-624a42175dda`, `donor-b-afd096a4b2ea`,
  `donor-b-bffecd967c60`, `donor-b-c3e132b7469b`, `donor-b-c57246c7841a`,
  `donor-b-cc7d3f520f1c`, `donor-b-ce6425d3101a`, `donor-b-d900ada906a3`,
  `donor-b-dbf19c8009dd`, `donor-b-ee0841a837c9`, `donor-b-f589d0e93cc9`,
  `donor-a-10476d50e5e8`.

Plus the one public task, that is 17 tasks at `K = 16` — the **272 draws** of § 10.25. The five
dev ids are `donor-b-2e149603209a`, `donor-b-353359e9ac6e`, `donor-b-3e3051c4192a`,
`donor-b-844db07ed482`, `donor-b-9dba3ea557f5`; the held-out document is
`tasks/heldout/source-b.json`, its digest unchanged from § 10.16.

**Four of the sixteen are already recorded as unscorable.** `donor-b-45740535725b`,
`donor-b-bffecd967c60`, `donor-b-d900ada906a3` and `donor-a-10476d50e5e8` are in the held-out
document's `excluded` map: their source files exceed the 80,000-character oracle budget. Their
64 draws are expected `NO_ORACLE`. They are **not dropped and not re-drawn**: they remain in the
denominator, `NO_ORACLE` stays unverified and is never a failure, and the probe's GO rule is
unchanged.

**What does not change.** The base and revision, the runtime and precision, `K = 16` (§ 10.19),
`R = 3` (§ 10.8), `R_repair = 2` (§ 10.23), the failure-class repair vocabulary (§ 10.25), the
score-both-ways verifier, the gate rule and its exits, and the held-out document and its digest.
The GO rule is still **GO iff at least one of the 272 draws is strict-`PASS`**.

**Comparability.** Every figure measured under § 10.23, § 10.24, § 10.21, § 10.22, § 10.20,
§ 10.10 or an arm is **non-comparable** to any figure measured under this probe. Naming the
sample does not start a new series; it fixes the one § 10.25 already pinned.

**No report home.** The gate record stays gitignored under `runs/`; the finding lives under
`docs/planning/torch-mps-series/`; no `reports/` directory is created.

**What is not claimed.** No count has been measured under this probe. The sample contains four
tasks that cannot produce an oracle, so 64 of the 272 draws are expected `NO_ORACLE`; the
amendment discloses that rather than filtering it out. The § 3 baseline remains unspent, nothing
here claims the probe selects a strict-`PASS`, and a NO-GO returns the lever to a human, never to
a loosened verifier.
```

Log row:

```markdown
| 2026-10-31 | The § 10.25 probe's 16-task sample is named by id, with four known `NO_ORACLE` tasks disclosed; the measurement's inputs are unchanged (§ 10.26) | 1 — pins the inputs of a measurement | Yes |
```

## Sequencing

First aspect. The probe cannot run until this is committed; the code and sheet aspects follow.
