# Spec — `stratum-report` (aspect 3 of `p2-easier-stratum`)

**Boundary:** the committed report home `reports/easier-stratum/`, the report door's second
mode, the one-home guard move on the changed-task-set argument, and the `PREREGISTRATION.md`
§ 10.5 Type 2 amendment. The run-side filter belongs to aspect `stratum-filter`; the runbook
and the operator's run belong to aspect `probe-run`. Nothing here generates, runs, or scores.

## Problem slice

The probe's verdicts need a published home that is honest about what it is. Two measurements
already have homes — `reports/baseline/` (the P1 bake-off) and `reports/format-hardening/`
(the hardened arm, moved in on the D6 argument). The probe scores a **different task set** —
the pre-committed easier stratum — under the **same** hardened contract, so the D6
different-contract argument does not cover it. The one-home guard (`tests/bakeoff/test_report.py:1353-1399`,
opposite-sign twin `tests/bakeoff/test_transcript_locality.py:73-114`) currently permits
exactly six files under `reports/`, and the only recorded permission is D6
(`docs/planning/p2-yield-probe/prd.md:106-112`). The unit's PRD pre-commits the ground for
this aspect: the task set is a pinned input (`PREREGISTRATION.md:131-132`), a change to a
pinned input invalidates the series and starts a new one (`:133-135`), so a figure over a
different task set is a figure in a **new series**, non-comparable to both existing homes
(PRD M7). The permission must be argued in **both** guard docstrings, the guard moves in the
same commit as the argument, and the amendment (§ 10.5) lands before the run it governs (PRD
M12) — in the same commit as the guard move and the declaration-only home.

## Decisions (PRD M6, M7, M8, M12, code-grounded)

- **R1 — The renderer is a new writer pair in `report.py` plus a second mode on the existing
  door in `comparison.py`; `--render-report` itself is untouched.** The existing writer
  `build_contract_comparison` (`report.py:577-670`) is contract-comparison-specific in every
  required paragraph: its header (`:598-605`), its no-arm declaration (`:610-617`), its
  payload `"measurement": "format-hardening contract comparison; ..."` (`:694-711`) and its
  cost `"kind": "contract-comparison"` (`:717-724`) all restate the D6 ground, which is not
  this home's ground. Reusing it would make the stratum document carry the wrong argument.
  A third module would duplicate the door's refusal logic (`comparison.py:1093-1146`) and the
  writer's identity discipline (`report.py:563-574, 673-687`). So: `report.py` gains
  `build_stratum_report` + `write_stratum_report`, mirroring the comparison pair's shape and
  reusing **by identity**: `_NON_COMPARABILITY` (`report.py:92-95`), `_contract_fields`
  (`report.py:331-358`), `_row` (`report.py:777-785`), `_over` (`report.py:762-764`),
  `tally` (`report.py:425-443`), `_contract_block` (`report.py:1082`), `_counts`
  (`report.py:1103-1109`). `comparison.py`'s door gains `--render-stratum-report`, reusing
  `build_contract_arms` (`comparison.py:824-883`) **unchanged** so its refusals hold by
  identity: a missing journal is refused by name (`:841-845`), an empty journal (`:850-854`),
  an unproven control — no `INTACT` probe — (`:856-862`), an unreadable contract
  (`:886-921`). The existing mode's refusals (zero arms, misaligned groups, missing
  `--breakdown-home` / `--recorded-on` / `--out`, `:1103-1132`) are untouched.
- **R2 — The stratum door takes exactly one arm group, and zero groups is refused.** The
  probe is one run under one contract (PRD M4), so `--render-stratum-report` accepts exactly
  one `--arm NAME --journal PATH --contract PATH` group; zero groups is refused with the
  format-hardening wording's shape — *the committed declaration is not re-rendered by the
  door, and a half-truth render is refused* (`comparison.py:1108-1112`); more than one group
  is refused (a second group would be a second measurement shape, not this report's). The
  door always renders figures: a group that reaches `build_contract_arms` has tallies, so a
  zero-candidate render cannot reach a committed directory.
- **R3 — The door takes `--stratum-doc PATH` as a required input, and the writer never parses
  it.** The changed-task-set claim must be   checkable in the document: the report points at the
  committed stratum document (rule digest + membership, PRD M2, schema owned by
  `difficulty-axis` — aspect 1's module `src/whetstone/bakeoff/stratum.py`) by name, mirroring
  the `--breakdown-home` pointer discipline
  (`report.py:659-662`, `finding.md:89-92`). The writer treats the path as a string — no
  parse — so this aspect never touches the stratum schema, and the render stays a pure
  function of its declared inputs (journal, contract sidecar, two pointer strings,
  `recorded_on`). Missing `--stratum-doc` is refused by name, like `--breakdown-home`.
- **R4 — The stratum report's shape: one contract, per-candidate rows, changed-task-set
  non-comparability, no restated classifier count.** `report.md` states the measurement's
  ground — the declared source-B set scored under the hardened contract, restricted to the
  pre-committed stratum — renders `_contract_fields` for the sidecar's contract (by identity
  via `GenerationContract.parse`, `report.py:219-243`), one per-candidate table with the
  comparison's rows (`solved`, `coverage`, `unverified`, `N`, `no diff`, `patch apply`,
  `patch scope`, `not solved` — via `_row`), the `_NON_COMPARABILITY` sentence beside the
  changed-task-set declaration, token-spend disclosure, the `--stratum-doc` pointer, and the
  `--breakdown-home` pointer. The `N` row is the harness's own WEAK-PASS/STRICT-FAIL
  differential (`PREREGISTRATION.md:96-100`). The sidecars are `report.json` (schema
  `whetstone-stratum-report/1`, with the contract block, per-candidate counts over their
  denominators, `non_comparable: true`, both pointers, `recorded_on`) and `cost.json`
  (`"kind": "stratum-report"`, per-candidate generation seconds). Classifier counts are
  pointed at, never restated (`report.py:659-662`).
- **R5 — The declaration-only state is the writer with zero tallies, generated by the writer,
  never hand-typed.** With `tallies=()`, `build_stratum_report` renders the declaration: the
  home's ground, the three-homes non-comparability, "**No count is measured here: the probe
  has not run.**", both pointers, `recorded_on` — and no `N of M` figure anywhere. This is
  the format-hardening precedent (`git show 487f7f0:reports/format-hardening/report.md`):
  the committed directory held the declaration until the arm rendered figures into it, and
  the door refused to re-render it (`comparison.py:1108-1112`). The declaration is produced
  by a direct writer invocation (Phase 4), not by the door.
- **R6 — The one-home guard moves on the changed-task-set argument, written into both
  docstrings.** Exact argument text, to append in lock-step after the D6 paragraph in
  `tests/bakeoff/test_report.py:1364-1371` and `tests/bakeoff/test_transcript_locality.py:81-87`
  (and the assertion message `test_report.py:1393-1398` updated to name both grounds):

  > **The guard moved a third time when the easier-stratum probe's home landed, and only on
  > the changed-task-set argument.** The task set is one of the five pinned inputs
  > (`PREREGISTRATION.md:131-132`), and a change to any pinned input invalidates the series
  > and starts a new one (`PREREGISTRATION.md:133-135`). The probe scores a **different task
  > set** — a pre-committed difficulty stratum of the declared source-B set — under the same
  > hardened contract, so its figures are a new series, declared non-comparable to both
  > existing homes (`PREREGISTRATION.md` § 10.5): the baseline's figures live in
  > `reports/baseline/`, the hardened arm's in `reports/format-hardening/`, and the probe's
  > in `reports/easier-stratum/` — each the only home of its own. A silent list extension
  > remains refused: the permission is the argument, in this docstring.

  Watched failing first: with the declaration-only directory created and the lists unamended,
  both guards fail; the argument in the docstrings is what permits the move.
- **R7 — The disjointness guard extends to all six existing artifacts.** The adversarial
  guard `test_the_two_contract_report_restates_no_baseline_figure` (`test_report.py:1259-1281`)
  currently reads only `reports/baseline/report.md`. A new test asserts the stratum
  document's `N of M` figures are disjoint from the figures of **all six** existing artifacts
  (`reports/baseline/` and `reports/format-hardening/`, each `report.md`, `report.json`,
  `cost.json`), with the existing non-vacuity assertion (`:1270-1273`) — a figure in both
  homes is exactly how two disagreeing numbers come to exist.
- **R8 — The § 10.5 amendment, Type 2, committed before the run.** `PREREGISTRATION.md` gains
  § 10.5 (draft text in the plan, Phase 4): the new home, its ground (same hardened contract,
  changed task set), the non-comparability declaration covering all three homes, and that the
  probe is a yield test — not the pinned baseline (`PREREGISTRATION.md:126-128`), not the
  held-out split (§ 7.1, open until P3). Append-only: a log-table row at `:306-313`, nothing
  above § 10 edited. No number, no proportion in any spelling, no placeholder — the
  `tests/test_docs.py` guards (`:554-574` placeholders, `:577-609` no proportion, `:676-683`
  amendment exception) stay green. `PREREGISTRATION_SECTIONS` (`test_docs.py:83-95`) stops at
  § 9, so a new § 10 subsection needs no section-list edit.

## In-scope requirements

- `src/whetstone/bakeoff/report.py` — `StratumReport` dataclass; `build_stratum_report` and
  `write_stratum_report` (three-artifact shape, deterministic, pure; declaration-only state
  with zero tallies); reuses the constants/helpers listed in R1 by identity.
- `src/whetstone/bakeoff/comparison.py` — the `--render-stratum-report` mode: exactly one arm
  group, `build_contract_arms` reused unchanged, `--stratum-doc` required, refusals before
  anything is written, `--render-report` untouched.
- `tests/bakeoff/test_report.py` — the one-home guard: list extended to nine files, the R6
  argument in the docstring, assertion message updated; the new disjointness test (R7);
  writer tests (shape, declaration, determinism, contract fields, rows).
- `tests/bakeoff/test_transcript_locality.py` — the opposite-sign twin amended in lock-step
  with the R6 argument (`:81-87`) and the nine-file list (`:100-107`).
- `PREREGISTRATION.md` — § 10.5 + log-table row.
- `reports/easier-stratum/` — the declaration-only three artifacts, committed (generated by
  the writer, never hand-typed).
- `CHANGELOG.md` + `CLAUDE.md` status block — in the shipping commit (repo rule, PRD M13).

## Acceptance criteria (tests written first)

1. The one-home guard's list holds **nine** files — `reports/easier-stratum/`'s three joined
   to the existing six — in **both** `test_report.py:1353-1399` and
   `test_transcript_locality.py:73-114`, each docstring carrying the R6 argument; the move is
   watched failing first (declaration present, lists unamended → red). A silent list
   extension without the docstring argument cannot pass.
2. The new disjointness test: the synthetic stratum document renders figures (non-vacuous)
   and none of its `N of M` figures appears in any of the six existing artifact files.
3. The declaration-only `reports/easier-stratum/` contains no count: no `N of M` figure in
   `report.md`, `report.json`, or `cost.json`, and the declaration states the probe has not
   run (the `test_a_second_contract_report_with_no_measured_arm_states_so` shape,
   `test_report.py:1284-1308`, mirrored for the stratum home).
4. The § 10.5 amendment lands with its log-table row; `tests/test_docs.py` (placeholders,
   no proportion, open-items + amendment exception, section list) is fully green; `git diff`
   of `PREREGISTRATION.md` touches nothing above § 10.
5. The door refuses, each by name and writing nothing: a missing journal, a journal with no
   `INTACT` control probe, zero arm groups, two arm groups, and a missing
   `--stratum-doc` / `--breakdown-home` / `--recorded-on` / `--out`. With valid inputs it
   renders exactly the three artifacts into `--out`, byte-identical across invocations.
6. `write_stratum_report` writes exactly `report.md`, `report.json`, `cost.json` under the
   destination and nothing anywhere else (the `test_the_comparison_writer_writes_the_three_artifacts_and_nothing_else`
   shape, `test_report.py:1311-1331`).
7. `--render-report` (the format-hardening mode) is untouched: its tests pass unchanged.
8. Full suite green after every phase; the AC2 pins hold — `git diff --stat origin/master --
   src/whetstone/verify/ src/whetstone/bakeoff/patch.py src/whetstone/bakeoff/attribution.py`
   is empty (PRD M11).

## Out of scope

- The difficulty rule, the stratum document, and the run-side filter — aspect `stratum-filter`
  (PRD M1–M3); this aspect never parses the stratum document (R3).
- The probe run, its runbook, the post-run chain, and the finding — aspect `probe-run`
  (PRD M4, M5, M9, M10); the door here is the step the runbook calls after the comparison.
- Any edit to `src/whetstone/verify/`, `patch.py`, `attribution.py` (pins hold, PRD M11).
- Any change to `reports/baseline/` or `reports/format-hardening/` artifacts.
- The difficulty distribution, the re-mint stub (PRD S3, N2), and any figure about a model
  outside the report homes and the gitignored breakdown home.

## Open questions / risks

- **The M12 one-commit vs. the precedent's two-commit split.** The format-hardening unit
  landed its § 10.4 amendment (`f460f2d`) and its guard move + declaration (`487f7f0`) in
  separate commits; PRD M12 of this unit forces **one** commit — amendment + guard move +
  declaration-only home. The RED moment is intra-phase (Phase 4) and never committed; the
  format-hardening precedent's split does not bind this unit's ordering, which M12 fixes.
- **"The stratum's denominator" (PRD M6) is read as the harness's own per-candidate
  denominator** — `tally.denominator = len(records)` (`report.py:433`), which for a complete
  probe equals the stratum's declared size less the dev-subset exclusions. The report never
  restates the stratum document's declared membership count (a committed count restated would
  be a two-home figure); the document is pointed at instead (R3). Flagged because a reader
  could read "the stratum's denominator" as the declared membership size.
- **`--stratum-doc` is a new required door input** beyond the PRD's explicit list
  (`--breakdown-home`, `--recorded-on`, `--out`). It exists so the changed-task-set claim is
  checkable in the published document; if review rejects it, the pointer sentence drops and
  the flag with it — the refusal and the writer input change together, test-first.
- **The declaration's breakdown pointer names a home before it exists.** The format-hardening
  declaration pointed at `runs/format-hardening-arm/` pre-run; the rendered report later
  pointed at `runs/format-hardening-preanalysis/comparison.md`. The stratum declaration names
  the probe's evidence home as the runbook declares it; the rendered pointer comes from
  `--breakdown-home` at render time and may differ — both are operator-declared, and the
  writer is a pure function of them.
- **A reviewer may dispute the changed-task-set ground.** The PRD pre-commits it (PRD M7,
  understanding.md:56-60) and the R-f fallback (a labelled section in an existing home) is
  recorded but not preferred; the docstring argument is the permission, and a silent list
  extension remains refused.
