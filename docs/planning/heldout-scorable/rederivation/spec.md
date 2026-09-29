# Spec — rederivation (aspect 3 of heldout-scorable)

**Aspect dir:** `docs/planning/heldout-scorable/rederivation/` · **Written:** 2026-09-27.
**Source:** `docs/planning/heldout-scorable/prd.md` (must-haves 6, 10; the #62 pairing),
`docs/planning/_card/issue.md`, `docs/STATUS.md` (2026-09-26, the re-mint record).
**Core loop element:** ③ gate (selection input).

## Problem slice

The held-out document was re-derived in aspect 2 over the current corpus (`contig-*` /
`belay-*` ids). The #62 pairing requires the document to be re-derived exactly once over the
**re-minted** corpus — ids `donor-a-*` / `donor-b-*`, a provably identical commit set (same
sha12s, same heads, differing only in `task_id`, `provenance.donor`, `repo_url`) — so the
donor's arbitrary label stops deciding the split, and the final document is the one the
amendment (aspect 4) pre-commits. The staged re-mint (complete and faithful, at
`_sandbox/remint/` in the primary checkout) is the reference; applying it is an operator
step that must be scripted, guarded, snapshot-protected, and reversible — the machine corpus
(`tasks/local/`) is the evidence behind `gate-001` and every portability figure.

**Known shape of the staged re-mint (measured 2026-09-27):** 66 manifests (45 `donor-a-*` +
21 `donor-b-*`), `repo_url: /Users/aliz/dev/at/whetstone/_sandbox/donors/donor-{a,b}`
(absolute staging paths), `provenance.donor` = the label, staged ledger (66 entries,
evidence intact: `without_patch`/`with_patch`/`executed_matches_declared`/`skipped`/`python`/
`tools`/`proven_at`). The pre-swap corpus's sha12s are the same 66 (the #62 claim).

## In scope

- **Apply machinery, as tested code**: a deterministic, fail-closed apply step that (1)
  snapshots the pre-swap machine corpus (manifests + the committed ledger's local twin) to a
  declared location; (2) verifies the staged re-mint against the snapshot (66, label ids,
  sha12s identical); (3) swaps the primary's `tasks/local/donor-{a,b}` manifests, removing
  the old-id files (a corpus root holds exactly the re-minted set — the loader reads a whole
  directory, nothing skipped); (4) rewrites `repo_url` in each applied manifest to the
  declared real donor paths (the pre-swap corpus's convention); (5) regenerates
  `tasks/local-ledger.json` from the staged ledger's evidence with re-hashed applied
  manifests, via `tasks.ledger`'s `read_ledger`/`write_ledger` by identity. Refuses to
  double-apply (a target that already holds `donor-a-*` files is a named refusal).
- **The re-derivations**: `tasks/stratum/easier.json` under the new ids (difficulties are
  per-commit properties — asserted equal per sha12 to the old document), then
  `tasks/heldout/source-b.json` under the aspect-2 rule (the FINAL document; the aspect-2
  document is superseded within this branch). Both through their established doors.
- **The commit**: ledger + stratum + heldout committed together; the recomputation test
  (`test_the_recomputed_document_equals_the_committed_one_field_by_field`) green over the
  re-minted machine corpus is the gate.
- **A runbook sheet** (the launch-chain pattern: `$REPO`-anchored absolute paths, guard
  tests, snapshot-first) the operator — or this unit, after the guards pass — executes.

## Out of scope

Re-mining via `whetstone mine` (the staged re-mint is the faithful re-mint; the apply step
verifies it, it does not re-derive); changing the donors' locations; the amendment (aspect
4); the runbook for the gate (aspect 5); the verifier, the gate, `check-leakage` semantics.

## Acceptance criteria (testable, written first)

- **AC1.** The apply step is scripted code + a runbook sheet with guard tests; no prose-only
  instruction; every path `$REPO`-anchored absolute.
- **AC2.** Snapshot-first: the step writes a verifiable snapshot of the pre-swap corpus
  before touching anything; the snapshot is asserted to contain the old-id manifests and the
  old ledger state.
- **AC3.** Verification before swap: 66 staged manifests, ids `donor-a-*`/`donor-b-*`,
  sha12s identical to the snapshot's, staged ledger count 66 — each an asserted check; any
  mismatch is a named refusal before any file moves.
- **AC4.** The swap leaves each corpus root holding exactly the re-minted set (66 total, no
  old-id file remains, no foreign file added).
- **AC5.** `repo_url` rewritten exactly to the declared donor paths, in every applied
  manifest (asserted); nothing else in the manifest bytes changes (asserted field-by-field
  against the staged manifest).
- **AC6.** The regenerated ledger: entries differ from the staged ledger only in
  `manifest_sha256` (recomputed from the applied manifest bytes by `tasks.ledger`'s own
  functions, asserted `is`); count 66; the loader accepts it.
- **AC7.** Stratum: re-derived under the new ids; per-sha12 difficulty equal to the old
  document's (asserted over all 66); its loader accepts the re-derived document.
- **AC8.** Held-out: re-derived under the aspect-2 rule; the recomputation test green; the
  two old NO_ORACLE members (`donor-a-10476d50e5e8`, `donor-a-16213e62eae1`) are in
  `excluded` and not in `membership`; `membership ∩ excluded = ∅`; 12 members.
- **AC9.** All four committed files (ledger, stratum, heldout — and the aspect-2 heldout
  superseded by this one) land together; the worktree suite is green on the re-minted
  machine corpus.
- **AC10.** Double-apply refused by name; the snapshot restores the pre-swap corpus
  (demonstrated once in a test with synthetic roots).

## Dependencies & sequencing

Depends on aspect 2 (`heldout-rule`). Runs in parallel with aspect 4 (`amendment`) — the
amendment states the rule, never the membership; both must be committed before aspect 5
(`gate-runbook`) which points at the final document and the amendment's number.

## Open questions / risks

- **Who executes the swap.** The swap touches the primary checkout's gitignored `tasks/local/`
  — machine-level state. This unit's guards make it safe; the operator (or the unit, after
  guards pass) executes it on this machine. The snapshot makes it reversible (AC10).
- **The aspect-2 document is superseded within the branch.** The branch history shows the
  intermediate `contig-*`-id document; the final committed state is the re-minted one. The
  amendment states the final document; no number is published from the intermediate one.
- **The ledger's evidence is reused, not re-derived.** The liveness evidence (without_patch /
  with_patch) was derived over the same commit set (the staging donors are copies at the
  same heads — AC3 pins that); only the manifest hash must follow the rewritten bytes. The
  spec's verification (AC3) is what makes the reuse faithful.