# PRD — gate-leakage-guard (2026-10-02)

Sources: `docs/planning/_card/issue.md`, `docs/planning/_card/understanding.md`,
`docs/ROADMAP.md` § 14 (M2), `PREREGISTRATION.md` § 10.16. Decisions taken in the
requirements interview: **option A** (fix the guard, do not run the gate on the contaminated
adapter) and **sha12-only identity matching** with a refusal on an unrecognisable id.

## Problem Statement

M2's exit criterion (`docs/ROADMAP.md` § 14) is a real `promoted`/`rejected` from
`whetstone gate`. The only trained adapter cannot honestly supply one. Four of its six training
examples come from `legacy-a-c6e4d4c4de87`, which the re-mint renamed `donor-a-c6e4d4c4de87`, a
member of the re-derived held-out set. `whetstone check-leakage` compares exact `task_id`
strings, so across the re-mint it reports disjoint (exit 0): a false clean on the case it
exists for. Independently it refuses (exit 2) on night-001 because that run has no
`ledger.json`. The gate record also does not name what trained the candidate, so no verdict
can be tied back to its training data.

## Goals & Success Metrics

- `check-leakage` catches a training/held-out overlap across a task-id rename. Target: the
  renamed-id fixture exits 1 under the new check and exits 0 under the old one.
- A gate record names the candidate's training-dataset digest, base repo_id and revision.
- The gate runbook can be followed for the real pair and refuses a run whose candidate leaks.
- A committed finding records, from the verifier's own outputs, that the night-001 adapter is
  refused for leakage. No gate verdict is produced or implied.

No performance target exists; none is invented.

## Users & scenario

The operator who runs the gate and must trust a `promoted`. A `promoted` on a candidate that
saw a held-out task is a fabricated win.

## Requirements

Must-have
1. **Identity by sha12.** Leakage compares the trailing 12-hex identity of each training task
   id against each held-out member, per source. A training id with no recognisable sha12 is a
   refusal (exit 2), never a pass.
2. **Ledger-free dataset input.** `check-leakage` can be pointed at a run directory that has
   `dataset.json` but no `ledger.json`, stating plainly that it did so.
3. **Provenance in the gate record.** The record gains the candidate's training-dataset
   digest, base repo_id and revision; a candidate whose digest cannot be recovered is a
   refusal, not a blank field.
4. **Runbook generalised.** The sheet names the candidate's night, runs `check-leakage`
   before the gate, halts on non-zero, and its stale roadmap citations are corrected.
5. **Finding.** A committed finding states the leakage result for night-001 against
   `tasks/heldout/source-b.json` using only `check-leakage`'s output, and says no gate was run.
6. **Docs in the same commit as the code that lands them:** `docs/STATUS.md`, `CHANGELOG.md`,
   ROADMAP § 14 M2 (exit criterion stays open, stated plainly).

Should-have
- The finding says who may write up a future gate finding, closing the runbook's gap.

## Technical considerations

- Core-loop element ③ (never-regress gate), at its leakage boundary. The reward (①) and the
  gate's decision rule are untouched; `unverified == 0` is still required, `UNVERIFIED` is
  still never a win, and nothing narrows § 2 / § 8.3.
- The leakage check is offline, deterministic, and off the reward path.
- Exit codes: check-leakage 0/1/2 (see Amendment 2 for the one case that moves to 2); gate 0 promoted, 1 rejected, 3 UNVERIFIED,
  2 refusal.
- Adding fields to the gate record changes its schema; the version and any digest over it
  must be handled deliberately (open question below).
- Reward-hacking surface: a candidate that trained on held-out tasks under a different id.
  The renamed-id adversarial test is the answer; "it can't" is not.

## Risks & Open Questions

- sha12 collisions across sources: matching is per source to bound this; confirm in the spec.
- Does the gate record's schema bump break the morning report or `card` readers?
- Whether the dataset's examples reliably carry a recoverable base repo_id/revision, or only
  the checkpoint does. Resolve in the plan from `sft`/`checkpoint` code.
- A future re-mint could use a scheme with no trailing sha12; the refusal is the safeguard.

## Amendments after the review gate (approved 2026-10-02)

- **Digest recoverability is the plan's first task.** Before any test is written, read `sft` and
  checkpoint metadata to settle where the training-dataset digest, base repo_id and revision
  live. Requirement 3's "refuse if unrecoverable" stands only if real checkpoints carry them;
  if they do not, the requirement is re-scoped by a PRD amendment, never satisfied with a blank.
- **Schema bump is required, not optional.** The record's schema version is bumped; readers
  (`report`, `card`) refuse an old version loudly; old records are never silently upgraded.
- **The refusal is the operator's signal.** An id with no recognisable sha12 is refused with a
  message that says a re-mint changed the id scheme and an amendment is needed before the gate
  may run.
- **Documented residual: near-duplicates.** sha12 identity cannot see a candidate trained on a
  near-identical task (same function, adjacent commit). A clean `check-leakage` means "no
  shared task identity", never "no contamination"; the finding and the runbook say so.
- **M2 stays open.** The only adapter is refused, so M2 needs a clean candidate (option B, an
  operator-run retrain), recorded in the finding as the next unit.
- **The finding is not reproducible without gitignored artefacts** (`runs/nights/night-001/`);
  it says so.

## Amendment 2 — "not checked" exits 2 (2026-10-03, user-approved)

A `check-leakage` run that compared nothing (a training set with no source B examples, so no
identity could be matched against the held-out set) is **a refusal, exit 2**, not exit 0. The
review of the disclosure wording found an exit code that cannot tell "checked" from "nothing
compared" is the wrong signal for a guard the runbook halts on. Exit 0 now means exactly one
thing: examples were compared and none shared a task identity. A training set with no examples
at all stays "disjoint by truth" (exit 0) — nothing trained, nothing to leak. This supersedes the
earlier "exit codes unchanged" line for this one case; the 0/1/2 meanings are otherwise as before.

## Out of Scope

- Running `whetstone gate` on any checkpoint (no GPU, no operator run in this unit).
- Retraining an adapter (option B), and gating the contaminated adapter (option C).
- Repo-and-commit corpus comparison (Decision 2).
- Changing the held-out split, the gate rule, the verifier, or any threshold.
- Any published figure.
