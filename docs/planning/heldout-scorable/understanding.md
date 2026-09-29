# Understanding — heldout-scorable

**Written:** 2026-09-27, from the Phase 1 dump (`docs/planning/_card/issue.md`) and the dig.
**Core loop element:** ③ never-regress promotion gate. **Roadmap:** P3 + § 12 launch path.
**Source of truth:** issue #60 (open) + the handoff brief; `docs/ROADMAP.md:451-453` and
`docs/STATUS.md` (2026-09-26) record the fired signal.

## What the work is really asking

The promotion gate cannot fire: 2 of the 12 members of `tasks/heldout/source-b.json`
(`contig-10476d50e5e8`, `contig-16213e62eae1`) are **permanently `NO_ORACLE`** — their file
sets exceed `ORACLE_BUDGET_CHARS = 80_000` (`src/whetstone/bakeoff/sources.py:150`), refused
whole at `:465-497`, deterministic, retry-unaffected. Promotion requires `unverified == 0`
(`src/whetstone/loop/gate.py:207-208`), so `gate-001` reduced to `UNVERIFIED` and **no
candidate can ever be promoted against this document** — the P4 honest-number report then
reduces to "no headline". The roadmap's pre-committed response to a gate that cannot fire
("a more reliable sandbox, never a looser gate") assumes transient unverified; this is
structural (`docs/STATUS.md`, 2026-09-26: "A perfect sandbox changes nothing").

The fix is a **property of the selection, not of the check** (issue #60's own words): a
held-out set is a *chosen* set, and choosing members that can build an oracle is a rule about
the selection — exactly the shape § 10.7 already uses (a pre-committed rule in code, a sealed
document, committed before it scores anything). **What must not happen** (issue #60): the gate
loosened, `NO_ORACLE` excluded from the gate's denominator, or the budget raised to make a
specific document pass.

## The mechanism, mapped

- **The split's machinery** (`src/whetstone/loop/heldout.py`, 786 lines): `SPLIT_SEED`,
  `HELDOUT_BANDS=3`, `MIN_HELDOUT=10`, `MIN_PER_BAND=2`, `_PER_BAND_TAKE=4`; derivation in
  `compose_document` (:310-390); per-band draw `select_band` by `sha256(split_seed, task_id)`
  (:147-162); floors enforced by `_refuse_unmet_floors` (:283-307, shared writer/loader) →
  `EmptyHeldout`. **Rule digest** (:171-186) covers the *source* of `_RULE_FUNCTIONS =
  (difficulty_key, band_of, select_band)` + canonical `_RULE_PARAMETERS` — a rule edit
  invalidates every committed document by design. Loader `read_document` (:407-594): 22 named
  refusals including digest mismatch and hand-edit. Writer CLI:
  `python -m whetstone.loop.heldout --corpus A --corpus B --out tasks/heldout/source-b.json`.
- **The oracle budget** (`src/whetstone/bakeoff/sources.py`): `changed_paths` (:231-257) →
  donor route `_from_donor` (:260-288, `Path(task.repo_url)`, `git show --name-status` at the
  mined commit) → `_read` (:443-491) refusals: per-file byte pre-check, cumulative char total
  over the sorted non-test path set, nothing-readable. **Fittability is a pure function of
  immutable git objects** (commit path set + `base_commit` tree) — deterministic and permanent
  for a fixed corpus; "raising the budget cannot alter an already-posable task" is asserted
  (`tests/bakeoff/test_oracle_sources.py`). **No fittability-only predicate exists** — `_read`
  is reachable only after a full `materialise` checkout (:422-440).
- **The gate** (`src/whetstone/loop/gate.py`): `decide` (:162-221) — either side in
  `_UNCOVERED` (report.py:60, imported by identity) → `unverified += 1` → `Exit.UNVERIFIED`;
  `RETRY_COUNT = 3` (:114); NO_ORACLE members are `_is_retryable` but never actually retried
  (`_CompletionRecorder.completion()` returns `None` when no prompt was rendered, :1318-1327).
  Gate consumes the held-out document via `--heldout` (cli.py:480-490), `read_document` by
  identity, digest recomputed (:696-697). Decision reads only the held-out members; source A is
  reported beside B, never counted (:745, :786-789).
- **check-leakage** (`src/whetstone/loop/check_leakage.py`): reads the dataset document +
  `read_heldout(heldout).membership` — semantics unchanged by re-derivation.
- **The document** (`tasks/heldout/source-b.json`): schema `whetstone-heldout/1`, 66 in
  corpus, 12 members (4 per band), `refusals: {}`, rule digest `862568462b84…`, document
  digest `fc84acab0aed…`. `difficulty` (stratum measurement) is per-id; `refusals` means
  "no stratum difficulty measured" — a distinct meaning from oracle-unfittable.
- **The stratum document** (`tasks/stratum/easier.json`): per-task difficulty
  (files/hunks/added+deleted), consumed by `band_of` through the stratum's own fail-closed
  loader. Its ids are the same 66 — a re-mint relabels the ids there too.
- **The re-mint staging** (issue #62): complete and faithful at
  `_sandbox/remint/` in the primary checkout — 66 manifests re-labeled `donor-a-*` /
  `donor-b-*` (same sha12s, e.g. `donor-a-10476d50e5e8`), re-minted `local-ledger.json`,
  recipes. No re-derived heldout/stratum documents were staged; the "10 of 12 change"
  measurement was transient. Applied to the *machine corpus* (gitignored `tasks/local/`) the
  re-mint changes the draw in 10 of 12 members by construction; the two NO_ORACLE members
  survive as `donor-a-10476d50e5e8`, `donor-a-16213e62eae1` — still permanently NO_ORACLE.
  `tasks/local-ledger.json` **is committed** (`git ls-files`) and binds id →
  `manifest_sha256` over a manifest whose content *is* the id — so applying the re-mint is a
  committed change, not a local swap alone.
- **Amendment discipline** (`PREREGISTRATION.md` § 8.1, :261-276): append-only; Type 1 =
  committed **before the measurement it governs runs**; may never introduce a success
  threshold or reword § 1/§ 4/§ 6; log row in the § 9 table (Date | Amendment | Type | Closes).
  § 3 (:131-138): a changed pinned input (task set = held-out membership) **invalidates the
  series** — "a figure measured on one side of a changed pinned input may not be compared with
  one measured on the other". The baseline-measurement runbook already names the re-derived
  split as § 3's legitimate new series.
- **Runbook pattern**: gate runbook (`docs/planning/p3-promotion-gate/gate-runbook/runbook.md`)
  — steps 2-5, guards in `tests/test_gate_runbook_guards.py` (REPO export, STALE_WORKTREES,
  absolute paths, R-by-identity, § 10.7 digest paragraph at :209-211). Established precedent
  (gate-untrained-incumbent, probe-decision-gate): **runbook rewritten code-first** — guard pin
  RED against a stub sheet first, sheet edited GREEN, same unit.
- **Recomputation pin**: `tests/loop/test_heldout_document.py::test_the_recomputed_document_equals_the_committed_one_field_by_field`
  (:129-167) loads the *machine* corpus (primary checkout, resolved via
  `git worktree list --porcelain`; CI skips) and recomputes the committed document field by
  field — a re-derived document must be committed together with the rule change that produced
  it, or this fails by name. `test_the_module_runs_as_python_m_for_the_runbook` pins the schema
  string `whetstone-heldout/1`.

## Affected areas

`src/whetstone/loop/heldout.py` (rule + derivation + loader), `src/whetstone/bakeoff/sources.py`
(read-only: a new predicate reusing `changed_paths` + a size-only pass — or a new pure
function), `tasks/heldout/source-b.json` + `tasks/stratum/easier.json` +
`tasks/local-ledger.json` (re-derived / re-labeled, committed), `PREREGISTRATION.md` (new §
10.x amendment + log row + status paragraph), `docs/ROADMAP.md` (dated correction blockquote,
§ 12/§ 13 where they name the gate's liveness), gate runbook + its guards,
`tests/loop/test_heldout_document.py` (schema/digest pins), `tests/test_docs.py` (amendment
shape guard), `docs/STATUS.md` + `CHANGELOG.md` (appended records).

## Ambiguities and open questions for the PRD

1. **Scope of the pairing (#62).** The brief pairs the re-derivation with the staged re-mint
   ("so the document is re-derived exactly once"). This grows the tree footprint: the re-mint
   relabels `tasks/local-ledger.json` (committed), the stratum document, and 66 manifests
   (machine-local). The unit must script the manifest swap (operator step on the primary
   checkout, since `tasks/local/` is machine-level) so the recomputation test runs over the
   re-minted corpus. **Lean: yes, one re-derivation** — two re-derivations would re-roll the
   pre-registered input twice.
2. **Where the fittability predicate lives and how the rule digest covers it.** Options: (a)
   a rule function (in `heldout.py`, added to `_RULE_FUNCTIONS`) delegating to `sources.py`
   semantics by identity, with the budget **value** added to `_RULE_PARAMETERS` so the digest
   covers it, derivation refusing if it disagrees with `sources.ORACLE_BUDGET_CHARS`; (b)
   inside `compose_document` only — digest not covering the filter. **Lean: (a)** — § 10.7's
   discipline is "the rule lives in code and its digest is sealed into the document"; an
   un-digested filter is an unsealed rule.
3. **Fittability needs donors at derivation time.** The predicate reads git objects at
   `base_commit` via `Path(task.repo_url)` — the derivation machine needs the donor repos
   (it already has them: the recomputation test runs over the machine corpus). Under the
   re-mint's label-form `repo_url` values the resolution must follow whatever the bakeoff
   does today; a task whose donor cannot be resolved is refused by name at derivation time
   (skip-with-reason, the bakeoff's own posture). Needs a test with a synthetic donor.
4. **Document shape.** The excluded class must be recorded (a new digested field, e.g.
   `excluded` with per-id reasons) while `refusals` keeps its stratum meaning ("not measured").
   The loader must refuse a *superseded* document (missing the new field) by name — a gate
   pointed at an old document must not silently evaluate. Schema string: keep `whetstone-heldout/1`
   (additive field, loader refuses staleness) vs bump to `/2`. **Lean: keep `/1`** — the loader's
   required-field refusal already fails closed; the digest is the seal. Decide in the PRD.
5. **Floors over the filtered population.** `_refuse_unmet_floors` must run over the
   post-exclusion draw (per-band ≥ 2, total ≥ 10, non-degenerate); unmet → `EmptyHeldout` =
   the published finding, never a loosened floor. With 64/66 scorable this is not threatened,
   but the refusal must exist.
6. **Gate-side guard.** None — gate semantics stay byte-identical (acceptance criterion); an
   old-format document refuses at the loader. The gate's honest outcome for a NO_ORACLE member
   remains `UNVERIFIED` — that is unchanged and desired.
7. **Amendment text.** Dated Type 1, closing/replacing the § 10.7 split under the new rule,
   pre-committed before any candidate scores against the new document; "does not change" clause
   (§ 10.10's base, the verifier, the gate's terms untouched); the § 3 series consequence stated
   (prior figures keyed to the old document are non-comparable); § 9 log row; status-paragraph
   edit only per the § 10.7/§ 10.10 precedent. Shape guard in `tests/test_docs.py` first (RED).

## What is deliberately NOT in scope

The budget value (80,000 stays), the gate's decision table / `unverified == 0` / `R = 3`, the
verifier, the corpus's NO_ORACLE handling at generation time, `check-leakage` semantics, issue
#64/#66 (the line-range lead and the publish-readiness section). The two NO_ORACLE tasks stay
in the corpus — excluded only from the held-out *selection*.

## Guardrail check

Reward stays execution-grounded (no verifier change). The gate still refuses to promote on an
unproven gain (`unverified == 0` untouched). Nothing leaves the box (derivation runs on the
machine with the donors). Not redundant with a better base (a better base does not make an
unscorable task scorable). No invented numbers — every claim above cites a file.