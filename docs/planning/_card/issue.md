# feat night-remine-before-draw

**Source:** inline brief — the `whetstone-next` handoff (2026-10-11), invoked as
`wbf feat night-remine-before-draw`. `gh issue view night-remine-before-draw` probes `FALLBACK`
(slug, no issue); the only open issues are #62 (held-out split keyed on task id) and #64 (patch
representation) — neither is this work. Branch `feat/night-remine-before-draw/aliz`.

**Core loop element:** ② the nightly improvement loop (the night grows the corpus it draws
against). ③ the never-regress promotion gate is *constrained* — the held-out membership must stay
fixed and sealed. The reward (①) does not change: nothing under `verify/` or `tasks/`' reward
boundary is touched.

**Roadmap:** `docs/ROADMAP.md` § 13 (`:794-800`) — the corpus does not grow, and that is a gap in
the thesis rather than a missing feature; `whetstone mine` mints tasks from real donor commits, but
a night reads a frozen directory and never re-mines. Moving *"the night re-mines before it draws"*
out of post-horizon is what makes the thesis mechanical instead of aspirational.

## Brief

Make the night grow its own corpus: before it draws, `whetstone run --night` re-mines the declared
donor repo(s) with the existing `mine()` path (`src/whetstone/tasks/mine.py:154`) and draws against
the freshly-minted verified tasks, per `docs/ROADMAP.md:794-800` (§ 13). The reward path, the gate's
rule/exits and the held-out split must stay byte-identical: re-mine into the training pool only,
leave the sealed held-out membership fixed, and record the mint delta (new ids, head, provenance) in
the run ledger.

**Acceptance criteria, written first (repo is test-first):**

1. A night with a donor that mints new tasks records those tasks in the ledger and draws against them.
2. A night whose donor mints nothing proceeds with the existing corpus and says so, never erroring.
3. A determinism test — same donor state and seed → byte-identical training set.
4. A test asserts the held-out membership and its document digest are unchanged by a re-mine, and
   that `whetstone check-leakage` still holds.
5. Nothing under `src/whetstone/verify/` changes; `tests/test_no_inference_on_reward_path.py` stays green.

**Caveat to resolve in the dig:** source B is pre-registered, so any growth of the declared headline
denominator (as opposed to the training pool) is a Type 1 `PREREGISTRATION.md` amendment committed
before the night that uses it — and `mine()` provisions each donor's environment, so bound the
re-mine cost so a night stays a night.
