# feat heldout-scorable — make the promotion gate able to fire

**Core loop element:** ③ never-regress promotion gate (`CLAUDE.md` § *The core loop*).
**Roadmap:** P3 (`docs/ROADMAP.md:428-465`), § 12 launch path, § 13 where the plan stands.
**Source:** GitHub issue #60 (open, 2026-09-26) + the `whetstone-next` handoff brief.

## Brief

The handoff brief from `whetstone-next` (2026-09-27), verbatim:

> Re-derive the held-out source-B document so the promotion gate can fire (issue #60, open
> since gate-001 returned UNVERIFIED: 2 of 12 held-out tasks are permanently NO_ORACLE over the
> 80,000-char oracle budget, R=3 deterministic, unverified==0 unreachable — no candidate can
> ever be promoted and P4's report reduces to no headline). Scope: a dated Type 1 amendment
> pre-committing a derivation rule that excludes oracle-unfittable members by class (never by
> hand), re-derived and committed before any candidate is scored against it, paired with the
> completed-but-unapplied --label re-mint (issue #62) so the document is re-derived exactly
> once; extend src/whetstone/loop/heldout.py's fail-closed derivation (rule digest covering
> the filter, floors unmet = the published finding, never a loosened floor), re-commit
> tasks/heldout/source-b.json under the new rule, keep check-leakage and the loader's digest
> guards green, and rewrite the gate runbook code-first. Acceptance criteria, written first:
> the derivation refuses by name a population whose scorable members cannot meet the floors;
> the committed document contains zero oracle-unfittable members under the declared budget; a
> hand-edited or stale-rule document is still refused by the loader; the gate's decision
> table, unverified==0 term, R=3 retry and NO_ORACLE-in-denominator semantics are
> byte-identical to master; and the series consequence (prior figures keyed to the old
> document are non-comparable) is stated in the amendment. Caveat the dig will not be
> surprised by: this is a pre-registered-input change — the rule must be fixed and committed
> before the draw, and the two NO_ORACLE tasks are not removed from the corpus, only from the
> held-out selection.

## Issue #60 — The promotion gate cannot fire while the held-out set holds a permanently NO_ORACLE task

**State:** OPEN · **Created:** 2026-09-26 · **Author:** haqaliz
**Link:** https://github.com/haqaliz/whetstone/issues/60 · **Comments:** none.

Body (verbatim):

> The first real gated evaluation (`gate-001`, 2026-09-26) returned `UNVERIFIED`. Its record:
>
> ```
> solved_new 0, solved_old 0, regressed 0, unverified 2 of 12
> retries: R=3, 0 spent over 0 (side, task) pair(s)
> unverified_after_retries: contig-10476d50e5e8 NO_ORACLE (both sides)
>                           contig-16213e62eae1 NO_ORACLE (both sides)
> ```
>
> **Zero retries were spent**, and that is the finding. `NO_ORACLE` means the task's source files exceed `ORACLE_BUDGET_CHARS = 80,000`, so no generation contract can be built — refused whole rather than truncated, by `sources.py`'s design. It is **deterministic**: retrying produces it again, which is why the retry budget went untouched.
>
> Promotion requires `unverified == 0`. Two of the twelve members of `tasks/heldout/source-b.json` are permanently `NO_ORACLE` on this host. **Therefore no candidate, however good, can ever be promoted against this held-out document.** The gate is structurally unable to fire.
>
> `docs/ROADMAP.md` P3 anticipated a gate that cannot fire and pre-committed the response — *"the fix is a more reliable sandbox, never a looser gate"* — but that prescription assumes unverified is **transient**. This is not. A perfect sandbox changes nothing. The retry discipline was built for flaky tests and sandbox timeouts and has no answer for a task whose oracle does not fit the budget.
>
> **What must not happen:** the gate must not be loosened, `NO_ORACLE` must not be excluded from the denominator (`counts_of` keeps unverified outcomes in deliberately — *"coverage is reported, never silently excluded"*), and the budget must not be raised to make a specific document pass.
>
> **Plausible direction:** a held-out set is a *chosen* set. Choosing members that can build an oracle is a property of the selection, not a weakening of the check — the same way the stratum document selects by a rule fixed in advance. That would be a change to how the held-out document is derived, made before any candidate is scored against it, and it pairs naturally with re-deriving the document for other reasons.

## Issue #62 — The held-out split is keyed on the task id, so an arbitrary donor label decides what is held out

**State:** OPEN · **Created:** 2026-09-26 · **Link:** https://github.com/haqaliz/whetstone/issues/62

Body (verbatim):

> `select_band` orders candidates by `sha256(SPLIT_SEED + "\n" + task_id)` and takes the first `_PER_BAND_TAKE`. A task id is `<label>-<sha12>`, and `--label` is documented as *"a non-identifying name for this donor"* — an arbitrary operator choice.
>
> **So an arbitrary naming decision determines which tasks are held out.** Relabelling a donor re-rolls the project's most safety-critical pre-registered input.
>
> **Measured, not argued.** Re-minting the corpus under `--label` (#57/#58) produces a provably identical commit set — all 66 tasks, same donor heads, same seeds, differing only in `task_id`, `provenance.donor` and `repo_url`. Re-deriving the held-out document over it gives 12 members again, but **10 of the 12 change. Only 2 survive.**
>
> **Why this is more than cosmetic.** One of the two tas… (truncated in capture; full body fetched to the worktree dump)

## Related

- **PR #63 (MERGED):** "Record the gate's first real candidate, and its UNVERIFIED verdict" — the commit (`72cd175`) that recorded gate-001, the run this issue describes.
- **Issue #66 (OPEN):** "Record what has to be true before a model of ours is published (ROADMAP § 14)" — proposes a ROADMAP § 14; cross-references #60. Note: `docs/ROADMAP.md` has **no § 14 today** (ends at § 13).

## Evidence trail (from the repo, not the issues)

- `docs/STATUS.md` (2026-09-26): gate-001 record; *"no candidate can ever be promoted against this held-out document on this host."*
- `reports/portability-arm/report.md` appended 2026-09-26: the gate table and the retry-budget finding.
- `src/whetstone/bakeoff/sources.py:150` — `ORACLE_BUDGET_CHARS = 80_000`; `:465-497` — refusal whole, never truncation.
- `src/whetstone/loop/heldout.py` — the split's rule machinery (`SPLIT_SEED`, bands, floors, rule digest).
- `PREREGISTRATION.md` § 10.7 (held-out rule, committed 2026-08-24 before it scored anything), § 10.8 (`R = 3`).
- `docs/ROADMAP.md:451-453` — P3's pre-committed response ("a more reliable sandbox, never a looser gate"); `docs/STATUS.md` 2026-09-26 shows it inapplicable.
- `docs/STATUS.md` (2026-09-26, #62): the `--label` re-mint is complete and faithful in a gitignored staging directory and was **deliberately not applied**.