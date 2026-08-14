# Spec — `difficulty-axis` (aspect 1 of `p2-easier-stratum`)

**Boundary:** the difficulty rule, the band, and the committed stratum document (schema
`whetstone-stratum/1`). Nothing on the run side, nothing published, no report change.

## Problem slice

The probe needs a subset of the declared source-B set that is *easier*, where "easier" is fixed
before any rollout — a pure selection over the corpus the project already holds. No difficulty
concept exists anywhere in the tree (`docs/planning/p2-easier-stratum/understanding.md:26-30`);
this aspect invents it a priori, in code, and pins it in a committed document whose membership a
test can re-derive. The axis is the reference fix's shape: the gold patch deterministically
derived from the donor at `provenance.commit`/`parent` — the same derivation the control arm
performs (`src/whetstone/bakeoff/control.py:195-256`, `src/whetstone/bakeoff/sources.py:260-287`)
— measured as files touched (non-test), hunks, and lines added/deleted. That is the only per-task
signal that is both discriminating and not outcome-derived (`understanding.md:31-39`), and it is
fixed at mint time: the gold patch is a pure function of the manifest's provenance plus the
pinned donor state it names (`docs/planning/p2-easier-stratum/prd.md:211-217`), never a model
verdict (`PREREGISTRATION.md:171-177`).

## Decisions (code-grounded)

- **D1 — The rule module lives in `src/whetstone/bakeoff/stratum.py`, never in `tasks/`.**
  The rule must reuse `sources.changed_paths` by identity, and the import direction is one-way —
  *"`whetstone.bakeoff` imports `whetstone.verify` and `whetstone.tasks`; neither may import
  back"* (`sources.py:84-85`). A `tasks/` placement would close that loop into a cycle
  (`tasks.stratum` → `bakeoff.sources` → `tasks.donor`), or force a copied derivation — the exact
  second-definition the project refuses (`control.py:24-29`). Placement in `bakeoff/` also needs
  **zero guard changes**: `bakeoff` is already exempt from the reward-path inference ban with a
  written reason (`tests/test_reward_path_scope_is_partitioned.py:100-105`), while `tasks/` is a
  guarded root defended as "where `test_blobs` is written"
  (`tests/test_no_inference_on_reward_path.py:76-84, 104-109`) — the difficulty rule is bake-off
  tooling reading donors, not reward-path material. The pattern ancestors (`diffcheck.py`,
  `retry.py`, `preanalysis.py`, `comparison.py`) all live beside it.
- **D2 — The gold patch is reused by identity, composed exactly as the control arm composes it.**
  `difficulty_of(task)` calls `sources.changed_paths` (`sources.py:231`) for the non-test path
  set, builds the `Candidate` exactly as `control._from_donor` does (`control.py:231-241`), and
  calls `tasks.derive.gold_patch` (`derive.py:194-208`). A test asserts identity
  (`stratum.changed_paths is sources.changed_paths`, `stratum.gold_patch is derive.gold_patch` —
  the diffcheck discipline, `docs/planning/p2-format-hardening/diffcheck/plan_20260809.md:57-59`),
  and the corpus test asserts the composed diff is **byte-identical** to
  `control.reference_patch(task).diff` on every corpus task — no second definition of "the
  commit's own fix" can exist and disagree with the one the control arm trusts.
- **D3 — The shape is measured by the rule's own hunk/line walk over the gold patch, validated
  as a measurement against git's parse.** No git command reports hunk counts, and
  `verify.repo.declared_paths` — git's own `--numstat` parse — drops the added/deleted counts and
  reports renames by destination only (`repo.py:87-95, 103-109`), so it cannot carry this measure
  even where it agrees with it. The rule therefore walks the git-produced patch text (always
  well-formed: `gold_patch` emits it, `derive.py:201-208`) for hunks (`@@` headers) and added/
  deleted content lines, and the corpus test **asserts the walk's added/deleted against git's
  `--numstat` per file on all 66 tasks** — a contradiction is a named failure, never reconciled
  (the autopsy finding's discipline, `docs/planning/p2-diff-autopsy/finding.md:69-71`). The
  walk's margin cases (binary hunks, `\ No newline` markers, renames) are enumerated in fixtures;
  the cross-assertion is what proves the walk and git agree on the real corpus. Files touched is
  `len(changed.paths)` — the derivation's own answer, the same set the oracle's scope uses
  (`sources.py:276-287`); the cross-assert is lines-only because numstat's file count disagrees
  on renames by construction (`repo.py:93-95`).
- **D4 — The band is pre-committed here, before any run: one non-test file, at most two hunks,
  at most 30 changed lines.** Membership falls out of `files == 1 and hunks <= 2 and
  added + deleted <= 30`. The numbers are module constants and a test asserts they equal the
  spec's (the diffcheck frozen-vocabulary discipline,
  `docs/planning/p2-format-hardening/diffcheck/spec.md:50-52`); widening after seeing
  the corpus is post-hoc selection (`prd.md:218-221`). If membership is empty or equals the whole
  declared corpus, the **writer refuses by name** — never a vacuous pass, never a silent widening
  (the empty-directory refusal of `src/whetstone/tasks/manifest.py:70-75`).
- **D5 — The stratum document is committed at `tasks/stratum/easier.json`, and it is the
  pinned input.** The run (aspect 2) consumes the document, never a live recomputation; a rule
  whose digest no longer matches the document's is refused by the loader — the document is the
  pre-committed artifact, drift is a named error. It carries: schema, rule digest, band, the
  corpus it was computed over, per-task difficulty values, refusals, membership, and a
  **`document_digest`** — a digest over the canonical payload of the other fields (schema, rule
  digest, band, corpus, values, refusals, membership), computed by this module's
  `document_digest_of`. The field is aspect 2's mechanically-required check
  (`stratum-filter/spec.md` D4.3): a hand-edited membership breaks it, and the loader refuses
  rather than trusts. **No timestamp field**: the recomputation test must compare
  byte-identically, and a write-moment clock would make equality impossible by construction
  (contrast the ledger's injected clock, `ledger.py:29-31, 64-71`, which exists for evidence
  about a mint — this document is the pinned rule output, not evidence about when it ran).
- **D6 — The document is evidence about the data, never the data.** Per `tasks/README.md:126-128`
  the committed artifact carries counts only: files/hunks/added/deleted and the manifest-
  structural tie-break fields (`len(fail_to_pass)`, `len(environment.pins)`, `len(test_blobs)` —
  present in every manifest, `understanding.md:33-38`) — never path names, never patch content,
  never donor code. Task ids are already committed in the ledger (`tasks/README.md:24-27`); file
  paths are not. `tests/test_stratum_document.py` walks the written JSON structurally with a
  canary that proves the walk would see a leak (the ledger-walk pattern, `ledger.py:23-27`).
- **D7 — The rule digest is scoped to the rule, not the module's I/O.** `rule_digest()` hashes
  `inspect.getsource` of the rule functions (difficulty computation + band membership) plus a
  canonical JSON rendering of the band parameters. A loader-only edit (an error-message change)
  must not refuse the committed document; any rule-source or band edit must — that is the
  rule-drift guard (`prd.md:78-85`). `tasks/stratum/` is committable: `.gitignore:16-24` ignores
  only `/tasks/local/`.
- **D8 — Source A has no difficulty, by construction.** Its single instance carries no donor
  commit (`control.py:209-211`) and its gold patch is a dataset artifact, not a shape this axis
  measures. `difficulty_of` refuses such a task by name ("carries no donor commit"), and the
  document records the refusal; the stratum's corpus is exactly the declared source-B set
  (`prd.md:8-9, 33-35`). The run-side filter (aspect 2) still scores source A — both sources
  publish together (`PREREGISTRATION.md:142-143`); the stratum simply does not include it.

## In-scope requirements

- `src/whetstone/bakeoff/stratum.py`: `difficulty_of(task) -> Difficulty | Refusal` (refusals:
  no donor commit, `changed_paths` refusal carried through with its reason, git failure with a
  reason — the `control.py:242-252` shape); band constants + `in_band`; `rule_digest()`;
  `document_digest_of`; the four loader refusals named in aspect 2's spec — `UnknownStratumId`,
  `EmptyStratum`, `StratumSchemaError`, `StratumDigestMismatch` (defined here, imported by
  identity there); the `whetstone-stratum/1` writer and schema-versioned loader; a module
  `main()` for the runbook (`python -m whetstone.bakeoff.stratum --corpus <roots> --out <path>`).
- The committed document `tasks/stratum/easier.json`.
- Tests (written first): `tests/bakeoff/test_stratum_rule.py`, `tests/bakeoff/test_stratum_document.py`,
  `tests/bakeoff/test_stratum_corpus.py` (machine-level; see AC 1).
- The no-inference AST walk over the rule's path with the diffcheck root set
  (`tests/bakeoff/test_diffcheck.py:382-467` pattern, `FORBIDDEN_IMPORT_ROOTS = {mlx, mlx_lm,
  torch, transformers, run}`): no `mlx`, no `run.py`, no `scoring`.

## Acceptance criteria (tests written first)

1. `uv run pytest tests/bakeoff/test_stratum_rule.py tests/bakeoff/test_stratum_document.py
   tests/bakeoff/test_stratum_corpus.py` green; the rule's no-inference walk green.
2. **Membership recomputation == committed document.** The corpus test loads all 66 manifests
   from `tasks/local/{belay,contig}/` (gitignored, machine-level) against the donors at
   `task.repo_url` (read-only), re-runs the rule, and asserts recomputed difficulty, refusals,
   membership, corpus ids and digest equal the committed document field by field. In CI the
   machine-level state is absent (plain `uv sync` and no donors, `.github/workflows/ci.yml`), so
   the test skips with a reason naming exactly what is missing — the `requires_sandbox` posture
   (`tests/test_verify_cli.py:32`) — and the runbook re-runs it on the machine before the probe.
3. **Degenerate refusals.** Empty membership and whole-corpus membership are refused **by name**,
   in both the writer and the loader — each test watched failing before the code exists.
4. **Rule-digest mismatch refusal.** A document carrying a digest that does not match the
   module's current `rule_digest()` (planted edit to rule source or band parameter) is refused by
   the loader, naming the drift.
5. **Determinism.** Two runs of the rule over one corpus produce byte-identical documents; the
   walk's added/deleted agree with git's `--numstat` on all 66 corpus tasks (a contradiction is a
   failure, never reconciled).
6. **Identity with the control arm.** `stratum.changed_paths is sources.changed_paths`,
   `stratum.gold_patch is derive.gold_patch`; the corpus test asserts the rule's composed gold
   diff equals `control.reference_patch(task).diff` byte-for-byte on every corpus task.
7. **AC2 pins hold.** `git diff --stat origin/master -- src/whetstone/verify/
   src/whetstone/bakeoff/patch.py src/whetstone/bakeoff/attribution.py` is empty; the reward-path
   guard and scope-partition tests pass unchanged (`prd.md:151-154`).
8. **Locality.** The committed document carries no path-shaped or content-shaped values; a
   canary proves the walk would flag one (`ledger.py:23-27` pattern).

## Out of scope

- The run-side inclusion filter (`--stratum`), `UnknownStratum` refusal, dev-subset interplay —
  aspect `stratum-filter` (`prd.md` M3).
- The report home `reports/easier-stratum/`, the one-home guard move (M7), the § 10.5 amendment
  (M8), the report door (M6), the finding (M9), the runbook (M10), candidate exclusion (M4) —
  later aspects of this unit, per M12 ordering (`prd.md:130-138`).
- Any change to `verify/`, `patch.py`, `attribution.py`, or the reward-path guards (M11).
- Any `whetstone` CLI change, any `pyproject.toml` change, any new dependency, any network use.

## Open questions / risks

- **Stratum size is unknown until the rule runs** (`prd.md:218-221`). Degenerate → usage error
  (refused by name, so the committed document can never be degenerate); small → a finding naming
  the re-mint step. The spec's band numbers are the pre-committed ones; nothing here widens them.
- **The axis itself is an assumption** — "smaller fix ⇒ easier" is not measured by anything yet
  (`prd.md:222-227`). This aspect guarantees the measure is a priori, deterministic, and
  re-derivable; whether it routes the fork correctly is the probe's question, answered later by
  M13's falsification check.
- **The walk's agreement with git on the margin** (binary hunks, renames, newline markers). The
  corpus cross-assertion is the response; if it contradicts, the finding records it and the
  fallback (a standalone `--numstat` caller in the rule — a second invocation of git's own parse,
  never a second parser) is named but not built.
- **`inspect.getsource`-based digest fragility**: any rule-source edit invalidates the committed
  document by design (the drift guard). A refactor that renames a rule function must regenerate
  the document in the same commit; the corpus test enforces the pairing.
- **CI cannot exercise the recomputation** (no donors, no manifests). The test's teeth are on the
  machine; the runbook makes the re-run a pre-probe step so the guard fires before any rollout
  spend.
