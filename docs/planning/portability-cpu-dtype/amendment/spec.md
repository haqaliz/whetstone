# Spec — amendment

**Aspect of:** `portability-cpu-dtype` (`docs/planning/portability-cpu-dtype/prd.md`) ·
**Written:** 2026-10-11 · **Order:** last code-aspect dependency is `dtype` (it pins the constant
by name); the docs land in the same commit.

## Problem slice

A dtype change is a pinned input (`PREREGISTRATION.md` § 8.1; `docs/ROADMAP.md:788`), so it needs
a dated Type 1 amendment committed **before** the night that records it, and every sentence the
change makes false being corrected on the record rather than silently rewritten.

## In scope

- **`PREREGISTRATION.md` § 10.17** (append-only, dated 2026-10-11), in the shape of § 10.13
  (`PREREGISTRATION.md:740-791`):
  - the Type 1 line (*"pins the input of an existing arm, committed before the training it governs
    runs"*), no-threshold, no-§ 1/§ 4/§ 6-rewording line, and **does not change § 10.10's base**;
  - **what changes:** the portability arm's CPU precision moves `float32` → `bfloat16`
    (`DEVICE_PRECISION["cpu"]`), for the reason § 13 gives (a larger base cannot load in fp32);
  - **the blast radius:** the one map is read by both the trainer (`torch_runtime.py:138`) and the
    generator/gate loader (`:396`), so **training, rollouts and gate verdicts** all move;
  - **comparability:** every prior arm figure — training, rollouts, gate verdict — is
    **non-comparable**; the old series is not extended;
  - **what is not claimed:** no training has run under this dtype; no count is claimed; the § 3
    baseline is unspent; a zero is entirely possible; *"accept the finding"* remains a legitimate
    outcome.
  - **amendment-log row** (`PREREGISTRATION.md:306-325`): `1 — pins the inputs of a measurement`,
    `Yes`.
- **Dated corrections** for every sentence the change makes false:
  - `docs/ROADMAP.md` § 13's *"The Torch runtime loads `float32` on CPU by declaration"* (`:785`) —
    a dated correction blockquote naming the change and § 10.17;
  - `docs/ROADMAP.md` § 14's dtype mention (`:882-894`, `:991-993`) — a dated note only if it
    reads as present-tense prescription; otherwise left as the historical record.
- **`reports/portability-arm/report.md`** — name `bfloat16` in the existing run-setup prose
  (PRD S1 / AC9). **No new file under `reports/`; no new `N of M` figure.**
- **`docs/STATUS.md`** — a new append-only entry (the repo appends here, never to `CLAUDE.md`).
- **`CHANGELOG.md`** — an `## [Unreleased]` entry (or the next version's section, per the
  release convention).
- **`tests/test_docs.py`** — guards pinning § 10.17's shape and the ROADMAP correction.

## Out of scope

- `CLAUDE.md`'s narrative status block (the repo's rule: append to `docs/STATUS.md`).
- Any number, threshold, or claim about yield/speed/fit.
- Editing `src/whetstone/loop/torch_runtime.py:50-52`'s docstring — that belongs to `dtype`.
- Editing the night-door runbook or any historical arm sheet.

## Acceptance criteria

- **AC6 (PRD M5):** a `tests/test_docs.py` guard pins § 10.17's shape (Type 1 line, the
  no-threshold/no-rewording line, a non-comparability sentence, a "what is not claimed" sentence,
  and its log row), and **cross-pins the literal `bfloat16`** against
  `torch_runtime.DEVICE_PRECISION["cpu"]` so doc and code cannot drift. `PREREGISTRATION.md` keeps
  its 11 `## ` sections and still contains no `%`/`percent`/placeholder token.
- **AC7 (PRD M6):** a guard asserts `docs/ROADMAP.md` § 13 carries a dated correction naming the
  change and § 10.17, and that no live sentence still says the arm "loads `float32` on CPU by
  declaration".
- **AC9 (PRD S1):** `tests/bakeoff/test_report.py`'s exact 21-file `reports/` list is unchanged;
  `report.md` names `bfloat16` and adds no `N of M` figure.

## Dependencies & sequencing

- Depends on `dtype` (cross-pins its constant). `record` should land before the STATUS/CHANGELOG
  prose describes the recorded shape.
- The amendment must be committed **before** any night run under the new dtype — its whole value
  is being prior (PREREGISTRATION § 8.1). This unit runs no night.

## Open questions / risks

- **A new amendment shape:** § 10.11–§ 10.15 each pinned a *base*; § 10.17 pins a *runtime input*.
  The wording makes that explicit ("pins the inputs of a measurement" via the log's Type 1 label).
  Reviewed at the plan's checkpoint.
- **No `%` token** may enter `PREREGISTRATION.md` (`tests/test_docs.py:621-653`).
