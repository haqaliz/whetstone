# feat whole-function-edit-finding — measure a whole-function replacement edit contract before building it

**Core loop element:** ② the nightly improvement loop — the generation contract that produces
rollouts. It touches ① only at the seam where an edit becomes the patch STRICT grades, and ①
itself does not change.
**Roadmap:** M1 of `docs/ROADMAP.md` § 14 (issue #64, open), follow-on of
`docs/planning/edit-contract-finding/` and `docs/planning/patch-representation/`.
**Source:** inline brief — the `whetstone-next` handoff (2026-10-01) — plus GitHub issue #64
(open) and its comment (2026-10-01, haqaliz).

## Brief

The handoff brief from `whetstone-next` (2026-10-01), verbatim:

> Measure, before building, the whole-function-replacement edit contract — the named lead of
> `docs/planning/edit-contract-finding/measurement-run/finding.md` § 6 (issue #64's
> continuation): the model states a function name, the harness locates the function's extent
> in the file and renders the diff, so the replacement text's surface shrinks to what the
> evidence says the base can write. Mirror the two prior finding units exactly: a
> pre-committed GO/NO-GO rule (e.g. GO iff more than half of sampled rollouts resolve to a
> single in-bounds whole-function replacement that parses) written before any rollout runs
> and exposed as a command exit (0 GO / 1 NO-GO / 2 refusal); an offline, deterministic,
> stdlib-only instrument off the reward path on the same boundary as `bakeoff/addressability.py`;
> a committed finding whose counts live only in gitignored `runs/`. Acceptance criteria,
> written first: a NO-GO ships only the instrument, the finding and any reason-field polish —
> nothing built, no amendment; a GO additionally requires the parser/converter with exact
> location (never repair, all-or-nothing), adversarial tests asserting the STRICT/WEAK
> differential stays intact, and `PREREGISTRATION.md` § 10.x (Type 1) committed before any
> night records `edit_format = whole-function`. Caveat the dig must not be surprised by:
> there is no stored evidence under the new prompt — the unit must spend a small real
> bake-off (hours on the pinned `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`), and
> addressability is a necessary condition, never a yield prediction; the finding must say so.
> No changes under `verify/` or `tasks/`; the reward path and the gate's rule are
> byte-identical when this unit lands.

## Originating issue #64 (open) — context, not this unit's source

Title: "83% of night-006's rollouts died on patch application, and over half were well-formed
diffs whose context did not match".

Body, verbatim:

> The 3B night (`night-006`, 336 rollouts) ended with **279 `NOT_APPLIED` — 83% of every
> rollout generated.** Only 13 were `NO_DIFF`. The base writes a diff 96% of the time;
> almost none of them land.
>
> `NOT_APPLIED` carries an empty `detail` in the journal, so the reason is not in the run
> record. It is recoverable, because the night stored transcripts — exactly what
> `transcript.py` exists for. No new compute was needed.
>
> ## Classifying the 279 final (graded) completions
>
> `autopsy.classify_completion` over the final completion of each `NOT_APPLIED` rollout:
>
> | cause | count | share |
> |---|---|---|
> | **WELL_FORMED** | **154** | **55%** |
> | HUNK_DIES_EARLY | 76 | 27% |
> | HUNK_COUNT_MISMATCH | 44 | 16% |
> | UNRECOGNISED_SHAPE | 5 | 2% |
>
> Markers across the same set: STACKED_FENCE 278, REPEATED_DIFFS 129, NOOP_HUNKS 93,
> INDEX_GARBAGE 5.
>
> **Over half the failures are structurally valid unified diffs.** The extractor accepted
> them; git refused them.
>
> ## Why git refused them
>
> 149 of the 154 yielded an extractable diff. Sampling 60 and running `git apply --check`
> against a real checkout at the task's `base_commit`:
>
> - **58 of 60: `error: patch failed: <file>:<line>`** — the context at that line does not match
> - 2 of 60: `corrupt patch at line N`
> - **0 of 60 would have applied cleanly** — so none are false negatives
>
> The paths are real, the files exist, the diff parses. **The model's context lines and line
> numbers do not match the file it is patching.**
>
> ## Why this matters
>
> Unified diff requires the model to reproduce exact surrounding lines and correct line
> offsets from memory. That is a transcription task, not a reasoning task, and it is where
> 55% of this night's work was lost — after the model had already decided what to change.
>
> **This has never been tested.** The arms tried so far moved other inputs:
> `reports/format-hardening/` is a **retry-augmented** contract, not a different patch
> representation; `reports/larger-base/` moved base size; `reports/easier-stratum/` moved
> the task set. The patch *representation* has been unified diff throughout, and the same
> wall is visible in the format-hardening figures (patch apply 43/64, 50/64, 8/64).
>
> Raising *k* or the base size does not touch this class: a bigger model writes a
> better-reasoned diff whose context still has to match exactly.
>
> ## Proposed direction
>
> A representation that does not require reproducing context or computing offsets —
> search/replace blocks keyed on a unique anchor, or whole-function replacement. The
> verifier is unaffected: it still re-executes and the reward stays execution-grounded.
> What changes is only how an edit is expressed.
>
> This is a **Type 1 amendment** — `prompt_sha256` and `extractor_version` are pinned parts
> of the generation contract — and it must be declared before the night that tests it, with
> the arm's figures non-comparable to the existing series.
>
> ## Secondary
>
> `NOT_APPLIED` should carry a `detail` the way `NO_ORACLE` does. **[SHIPPED 2026-09-27,
> v0.15.0 — not part of this unit.]**

## Comment (2026-10-01, haqaliz) — the numbered-listing measurement shipped NO-GO

> Shipped the numbered-listing edit contract measurement. We asked the pinned base to edit
> code by line ranges against a numbered listing instead of writing unified diffs, ran it
> once over 16 pre-committed tasks, and measured what came back: the model adopted the
> format but didn't reliably close its own edit blocks or write replacement text that
> parses, so the decision was NO-GO and the contract was deliberately not built. This closes
> the second of the two representation directions the earlier patch-representation finding
> left open — both measured, neither built.

## Where the lead comes from

`docs/planning/edit-contract-finding/measurement-run/finding.md` § 6, verbatim:

> One observation is recorded for whoever designs the next contract change, and it is the
> reverse of the diff-contract's: the model's *failure* here is not transcription of
> existing text — it is **closing its own replacement blocks and writing replacement text
> that parses**. A format that reduces the replacement text's surface (e.g. whole-function
> replacement keyed by a name the model can state, where the harness finds the function's
> extent) is the kind of change this evidence does not already rule out — a lead, not a
> proposal, needing its own finding before any amendment.