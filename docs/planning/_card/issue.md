# feat edit-contract-finding — measure a numbered-listing / line-range edit contract before building it

**Core loop element:** ② the nightly improvement loop — the generation contract that produces
rollouts. It touches ① only at the seam where an edit becomes the patch STRICT grades, and ①
itself does not change.
**Roadmap:** M1 of `docs/ROADMAP.md` § 14 (issue #64), follow-on of
`docs/planning/patch-representation/`.
**Source:** inline brief — the `whetstone-next` handoff (2026-09-30) — plus GitHub issue #64
(open) and `docs/planning/patch-representation/finding.md`.

## Brief

The handoff brief from `whetstone-next` (2026-09-30), verbatim:

> The named lead from docs/planning/patch-representation/finding.md § 6: measure, before
> building, whether a numbered-listing / line-range edit contract (the model addresses a
> numbered source listing and writes replacement text; the harness renders the diff) converts
> the pinned base's refusals — the majority are near-misses of contiguity and of the model's
> own edits, so a format that never asks it to quote existing code is the one direction the
> evidence does not already rule out. Mirror the patch-representation unit's shape: a
> pre-committed GO/NO-GO rule (GO iff > half the sampled rollouts address real lines and
> produce grammatical replacements, e.g.) written before the run and exposed as a command
> exit (0 GO / 1 NO-GO / 2 refusal); an offline, deterministic, stdlib-only instrument off
> the reward path, same boundary as bakeoff/locatability.py; a committed finding whose counts
> live only in gitignored runs/. Acceptance criteria, written first: the rule and its
> population are fixed and committed before any rollout runs; a NO-GO ships only the
> instrument, the finding and the reason-field polish — nothing built, no amendment; a GO
> additionally requires the parser/converter with exact location (never repair,
> all-or-nothing, scope-before-location, an NOT_LOCATED-equivalent covered outcome),
> adversarial tests asserting the STRICT/WEAK differential stays intact, and
> PREREGISTRATION.md § 10.x (Type 1) committed before any night records edit_format =
> line-range. Caveat the dig will not be surprised by: there is no stored evidence under the
> new prompt — this unit must spend a small real bake-off (hours on the pinned base), and
> addressability is a necessary condition, never a yield prediction; the finding must say so.
> No changes under verify/ or tasks/; the reward path and the gate's rule are byte-identical
> when this unit lands.

## Originating issue #64 (open) — context, not this unit's source

Title: "83% of night-006's rollouts died on patch application, and over half were well-formed
diffs whose context did not match". The primary direction (search/replace) was measured
**NO-GO** by the `patch-representation` unit (2026-09-27) and deliberately not built; the
secondary item (`NOT_APPLIED` carries a `detail`) shipped. This unit is the finding's § 6
lead, which the finding states "would need its own finding before any amendment".