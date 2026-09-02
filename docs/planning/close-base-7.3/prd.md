# PRD — close-base-7.3

**Unit:** `feat/close-base-7.3/aliz` · **Slug:** `close-base-7.3` · **Written:** 2026-09-02
**Source:** `docs/planning/_card/issue.md` (inline brief from the `whetstone-next` handoff).
**Understanding:** `docs/planning/close-base-7.3/understanding.md` (dig, 2026-09-02).

## Problem Statement

`PREREGISTRATION.md` § 7.3 ("Which open base is fine-tuned") is the last open § 7 item. The
launch path's operator chain (`docs/ROADMAP.md` § 12, corrected 2026-09-01) opens with
"§ 7.3 Type 1 amendment → night #1 → first gated evaluation → baseline spend → P4 report →
finding", and § 8.1 (`PREREGISTRATION.md:266-268`) makes the amendment a hard precondition:
it must be committed **before the measurement it governs runs**, so **night #1 cannot
legally train until the base is pinned here**. A night that trained unpinned would be a
silent breach of § 8.4 — the pre-registration failure this project exists to prevent.

The evidence to close on exists: the larger-base arm measured the first nonzero strict-PASS
yield the harness has ever seen, with the control discipline intact
(`docs/planning/larger-base-arm/finding.md:41-43`), and that finding states § 7.3 closes
only by a Type 1 amendment committed before the measurement it governs runs
(`finding.md:50-53`). This unit performs that closure.

## Goals & Success Metrics

- **Goal 1 — Close § 7.3 by the book.** A dated Type 1 amendment (§ 8.1) naming the base
  being fine-tuned, committed as its own change before night #1, recorded in the amendment
  log. Success: the log's last row reads "closes an open item = Yes" for § 7.3, and
  `git log` proves the amendment precedes any night measurement.
- **Goal 2 — The pin matches the machine.** The named base is byte-identical to what the
  night actually runs: the repo_id matches the night runbook and its guard
  (`test_night_runbook_guards.py:65`), the revision matches `weights/provenance.json:498`.
  Success: a cross-pin test asserts the amendment's repo_id equals the runbook guard's
  constant; the operator verifies revision + per-file hashes against the gitignored
  provenance before committing.
- **Goal 3 — Honesty mechanics hold.** No success threshold introduced, no figure about a
  model in any spelling, nothing above § 10 edited except the status paragraph's open-items
  clause (the § 10.7/§ 10.8 precedent). Success: `tests/test_docs.py` (old and new guards)
  and the full suite are green.

Measured by the suite, not by narrative: this unit reads no number.

## User Personas & Scenarios

- **The operator (aliz)** — runs the launch chain. Scenario: commit this amendment, then
  run night #1; the runbook's first step is satisfied and the night's base is pinned in the
  document that governs it.
- **The future reader of `PREREGISTRATION.md`** — asks "which base did the night fine-tune,
  and was it fixed before the measurement?" Scenario: reads § 10.10, sees the base, the
  revision, the provenance home, the evidence, and the "no count measured here" claim, and
  can verify the timestamp with `git log` (§ 9).

## Requirements

### Must-have

1. **§ 10.10 amendment** appended to `PREREGISTRATION.md`, following the § 10.8 structure:
   a `**Type 1 (§ 8.1): closes § 7.3, committed before the night it governs runs.** It
   introduces no success threshold and rewords nothing in § 1, § 4, or § 6.` opening; a
   `**The base.**` block naming repo_id `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`,
   the immutable revision `d1e3b690c8e225d7795bccddf971ca6be68b2012`, and
   `weights/provenance.json` as the per-file-hash home (re-hashed on every run by
   `src/whetstone/bakeoff/weights.py` — no aggregate digest, none minted); an
   `**The evidence it was chosen on.**` block citing `docs/planning/larger-base-arm/finding.md`
   and `reports/larger-base/` (the figures' only home — cited, never restated); and a
   `**What is not claimed.**` block stating no measurement has been run under the night and
   none is claimed here.
2. **Amendment log row** appended to the table (`:318`): date, "§ 7.3 is closed by the
   amendment below (§ 10.10)", type "1 — closes an open item", "Yes".
3. **Status paragraph edit** (`:321-324`) — the one edit above § 10: the *three*
   § 7.3-specific sentences (the "§ 7.3 is still **open**" clause, the "P1 bake-off selected
   no base, so it does **not** close § 7.3" reasoning, and the "an amendment that tried to
   close it after the fact" warning) are replaced by "§ 7.3 is closed by the dated amendment
   below (§ 10.10)" — the exact § 10.7/§ 10.8 precedent, which replaced each closed item's
   whole sentence group and nothing else (`df7ae15`, `c28bb55`). The § 7.1/§ 7.2 sentence
   stays. Nothing else above § 10 changes; § 7.3's own paragraph, § 10.6, and § 10.9 stay
   as first committed.
4. **Shape guard, watched failing first** — a new test in `tests/test_docs.py` on the § 10.9
   pattern (`d037967`), pinning structure, never the base name's future:
   - § 10.10 exists with "Type 1 (§ 8.1)" and "closes § 7.3";
   - the amendment's no-measurement sentence is present ("At the time of this amendment no
     measurement has been run under the night, and none is claimed here" — exact wording
     pinned like § 10.9's);
   - the log table's last row names § 7.3 and closes an open item;
   - the § 10.10 repo_id equals `tests/test_night_runbook_guards.py`'s `RETAINED` constant
     (single source of truth for the pin: the amendment and the night cannot drift apart
     silently; the base name stays swappable by changing one constant + a new amendment).
     **Mechanism to be verified at plan time**: if `tests/` is importable as a package the
     guard imports the constant; otherwise the guard asserts equality with the constant
     read from the runbook guard module at runtime, with the duplication argued — never a
     second hard-coded copy of the name;
   - no success-threshold phrase in § 10.10.
5. **ROADMAP correction** — a dated "Corrected 2026-09-02" blockquote after
   `docs/ROADMAP.md:370-372` (the "no base is selected … § 7.3 stays open" bake-off record),
   on the `:364-368` precedent: the bake-off's zero stays the dated record; § 7.3 is closed
   by § 10.10; the base was pinned on the larger-base arm's evidence.
6. **State files updated in the same unit** (the repo's own contract, `CLAUDE.md`):
   - `CLAUDE.md` — the "Still open" bullet for the base (`:151-153`) moves to a settled
     line naming the amendment (§ 10.10) and the evidence;
   - `docs/STATUS.md` — a top entry recording the unit;
   - `CHANGELOG.md` — an entry under the next version heading, per the
     gate-untrained-incumbent precedent (`213b6c6`).
7. **Honesty constraints hold.** No success threshold; no `%` / `percent` / `percentage`
   anywhere in PREREGISTRATION.md; no placeholder tokens; no figure about a model in any
   spelling; any new `docs/ROADMAP.md:NN-NN` citation added to `ROADMAP_CITATIONS` in the
   same commit (preference: none — § 10.7/§ 10.8 cite internal refs and file paths only).
8. **Full suite green** in the worktree: `uv run pytest`, `uv run ruff check .`,
   `uv run mypy src/`.

### Should-have

- The amendment names the excluded 7B base's exclusion only if it adds clarity; otherwise
  the runbook already records it (`night-door/runbook.md:20`) and the amendment stays
  minimal. Default: omit.
- `docs/ROADMAP.md:610-611` (capacity question) is left as-is — it stays open.

### Nice-to-have

- None.

## Technical Considerations

- **Append-only mechanics** (dig-verified): the only editable text above § 10 is the
  status paragraph's open-items clause; the log table takes appended rows only; § 10.10 is
  the next free section number.
- **Byte-identity of the pin**: repo_id appears identically in the night runbook (`:14,57,92`),
  `test_night_runbook_guards.py:65`, the larger-base runbook (`:19`), `finding.md:13`, and
  `weights/provenance.json:497`; revision at `provenance.json:498` and `finding.md:22`. The
  amendment matches both exactly. The revision/hash side is operator-verified (provenance is
  gitignored, absent from CI); the repo_id side is machine-verified by the cross-pin guard.
- **Guard design rule**: the new guard pins shape and cross-pin, never a hard-coded base
  name — the swappable-base principle (`PREREGISTRATION.md:257`) is not contradicted by
  naming the pinned base for this series; a future swap needs a new amendment anyway (§ 8.1),
  and the runbook guard's constant is the single place the name lives.
- **Test hazards** (from the dig): `%`-guard (`test_docs.py:637`), placeholder guard
  (`:608`), "no figure about a model" phrase (`:645`), `ROADMAP_CITATIONS` exhaustive
  pairing (`:912-919`), and the § 10.9 shape guard (`:726-761`) — all must stay green.
- **No code under `src/` is touched.** The reward path, the gate, the sandbox, and the
  partition guard are all out of scope by construction.

## Risks & Open Questions

- **Over-pinning the guard** — a guard that hard-codes the base name into test text would
  freeze the swappable base in a second place. Mitigation: the cross-pin imports the
  runbook guard's constant rather than restating it, so there is exactly one test-owned
  copy of the name.
- **Stale-prose creep** — files outside the edit list that carry "§ 7.3 stays open" are
  dated records (STATUS.md entries, CHANGELOG versions, § 10.6/§ 10.9, `reports/baseline/`)
  and must NOT be edited; only the current-state files in Must-have 6 are touched. The plan
  enumerates the inventory so no one reaches for the wrong file.
- **The revision cannot be machine-checked in CI** (provenance.json is gitignored). The
  operator verification step is part of the plan, and the plan's acceptance check records
  it against `finding.md:22`.
- Open: none — the interview closed the three decisions (guard: add; ROADMAP: fold in;
  hash: revision + provenance home).

## Out of Scope

- Running night #1, the gate, the baseline spend, or the P4 report — operator execution of
  shipped machinery, explicitly not this unit.
- Any code change under `src/` — reward path, gate, sandbox, partition guard.
- Minting an aggregate weights digest — the revision sha pins immutability; per-file hashes
  already exist.
- Editing § 7.3's own paragraph, § 10.6, § 10.9, or any existing log row.
- A second task family, distillation, the dashboard, closing cheat 6/10 — all post-horizon
  (`docs/ROADMAP.md` § 9, § 3).

## Non-Functional Requirements

- **Determinism/verifiability**: the amendment is prose + one test change; the guard must
  be watched failing (RED) before the amendment text satisfies it (GREEN), in this unit's
  first commit pair — a separate RED commit (guard alone, failing against today's
  `PREREGISTRATION.md`) lands before the GREEN commit (amendment + log row + status edit),
  on the `f2706ec`-style precedent ("Pin the gate's untrained dispatch … (TDD, RED)").
- **Provenance**: every claim in the amendment is citable — the figures stay in
  `reports/larger-base/`; the amendment points, never restates. The amendment's evidence
  sentence states exactly what the arm measured (first nonzero strict-PASS yield, control
  intact) and bounds it as the best available evidence — § 7.3's "decided by the bake-off
  on evidence against the working verifier" is honored in the wording, never dressed up.
- **No egress**: nothing leaves the box; `weights/provenance.json` stays gitignored.