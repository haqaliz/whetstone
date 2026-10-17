# Spec — `prose` (raise-k)

**Aspect:** correct every live sentence that names the old budget; record the change.
**Source:** `docs/planning/raise-k/prd.md` (M7, S1, S2; AC6, AC9).

## Problem slice

`docs/ROADMAP.md:775` states in live prose *"Raising k remains untried: `K = 8` is a declared
constant and never a flag"* — false once § 10.19 lands. Three inert test docstrings and the
unit card quote the old value. The changelog and status log must record the change in the same
commit that lands it (the repo's write-up rule).

## In scope

- Add a dated `> **Corrected 2026-10-17 …**` blockquote to `docs/ROADMAP.md` § 13 preserving
  the old sentence (`"Raising k remains untried … `K = 8`"`) and naming § 10.19 — never an
  in-place edit (the § 10.18 precedent, `docs/ROADMAP.md:794-802`).
- Update the inert test docstrings that name `sampling.K = 8`:
  `tests/test_docs.py:735`, `tests/bakeoff/test_report.py:2065,2159`,
  `tests/bakeoff/test_transcript_locality.py:126`.
- `CHANGELOG.md` under `Unreleased`; a `docs/STATUS.md` entry at the top.

## Out of scope

- `docs/ROADMAP.md:419` (a dated blockquote), `CHANGELOG.md:1019` and `docs/STATUS.md` old
  entries (append-only), every merged `docs/planning/**` dir, `reports/portability-arm/`
  (measured under `K=8`). § 14's dated M1 blockquotes — left as historical records
  (user-confirmed, matching the § 10.18 precedent).
- Any `reports/` movement.

## Acceptance criteria (testable, watched failing first)

- **AC3.1** A `tests/test_docs.py` guard asserts `docs/ROADMAP.md` § 13's blockquote slice
  carries `"Corrected 2026-10-17"`, names `10.19`, and preserves the quoted old sentence; and
  that no live (unquoted) ROADMAP sentence still says `"Raising k remains untried"` or
  `"`K = 8`"`.
- **AC3.2** The three inert test docstrings name the new value (or drop the value); no
  assertion depends on them (they are prose).
- **AC3.3** `tests/bakeoff/test_report.py`'s 21-file `reports/` list is unchanged; no new home,
  no new `N of M` figure.

## Dependencies / sequencing

Lands last; the docs/CHANGELOG/STATUS write-up must be the same commit as the change it
describes.

## Open questions / risks

- AC3.1's "no live sentence still says `K = 8`" must use the ROADMAP prose-vs-quoted split
  (`line.lstrip().startswith(">")`) so the preserved quotation inside the blockquote is not
  flagged — the existing § 10.18 guard (`tests/test_docs.py:1198-1236`) is the template.
- Whether § 14 needs its own 2026-10-17 note: user-confirmed no (§ 13 only).
