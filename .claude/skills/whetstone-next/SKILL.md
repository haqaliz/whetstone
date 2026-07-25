---
name: whetstone-next
description: Use when deciding what to build next in Whetstone and you want the single highest-leverage capability picked from the repo's own roadmap and planning files (not invented), grounded in the moat and in what has already shipped or been deferred, ending with a ready-to-run handoff. Triggers on "whetstone-next", "wn", "what's next", "next feature", "pick next".
arguments: ""
---

# Whetstone Next (pick the most important capability)

## Overview

Read the repo's own roadmap and planning files, rank the real candidate capabilities
against the moat and against what has shipped or been deferred, and recommend the
single highest-leverage one to build next. End with a ready-to-paste
`whetstone-begin-fast` invocation so the next session can start that worktree.

This skill RECOMMENDS and hands off. It does NOT create a worktree or start
`whetstone-begin-fast` itself; the user runs the handoff prompt when ready.

## When to use

- "what should I build next", "pick the next capability", at the start of a session.
- After a merged capability or a phase gate, when choosing the next unit of work.
- Not for: executing a chosen capability (use `whetstone-begin-fast`), or planning an
  already-chosen one (use `prd-interview` / `tech-plan`).

## The candidate set is the FILES, never invented

Read these (the source of truth, in this order). Whetstone is **greenfield**, and most of
the planning surface is **not written yet** — say so plainly rather than filling the gap
from memory:

- `docs/ROADMAP.md`: the 2–3 month phased plan + milestones. **This is meant to be the
  primary candidate set, and it does not exist yet** — `CLAUDE.md` names it as the
  immediate next artifact. Until it's written, the honest read is that there is no ranked
  backlog, and *producing the roadmap* is itself a live candidate (usually the strongest
  one — see rule 1 below).
- `docs/technical/ARCHITECTURE.md`: the nightly loop / verifier / distillation design.
  Also **not written yet**; authoritative over `CLAUDE.md` once it exists.
- `docs/product/PRODUCT_SPEC.md`: the product surface, the report, the trend. Not written yet.
- `CLAUDE.md` and `VISION.md`: **written, and the source of truth today.** The wedge, the
  moat, the five core-loop elements (① verifiable task family + verifier, ② nightly
  improvement loop, ③ never-regress promotion gate, ④ signed morning report, ⑤ local +
  private), and the guardrails the pick must obey.
- `docs/planning/*/`: in-flight, completed, and DEFERRED work, once any exists. Read the
  understanding/PRD notes: a capability deferred for a real blocker must not be
  re-recommended as if it were a quick win.
- `git log` / `git tag` / the test suite: what actually shipped. Trust this over prose;
  code runs ahead of the narrative docs. **Today there is one seed commit and no code** —
  say so plainly rather than implying shipped state.
- `~/dev/at/ideas/research/b1-verified-self-improvement.md`: the seed research and
  rationale, cited in `CLAUDE.md`. Background, not a backlog.
- A `CHANGELOG.md` if one ever exists (it does not today).

If a file above is missing, still reference it by path and say it isn't written yet.
Never substitute memory for a file you couldn't read.

## How to rank (grounded in CLAUDE.md)

1. **Before the roadmap exists, the roadmap is the pick.** `CLAUDE.md` states the next
   artifact is `docs/ROADMAP.md` (a 2–3 month phased plan + milestones). Recommending a
   deep implementation slice while there is no phase plan, no chosen task family, and no
   defined verifier is picking a branch before the trunk. Only rank around this once the
   roadmap (or an explicit user decision) supersedes it.
2. **Harness only.** The loop, the verifier, the promotion gate, the report, the eval
   machinery. **Never** a frontier base model. **Never** an LLM-judge reward. Never
   anything requiring data egress or credentials the founder lacks. Drop any candidate
   that violates a guardrail — this is not a tie-breaker, it's a filter.
3. **The verifier comes first, and everything blocks on it.** ② the loop, ③ the gate, and
   ④ the report are all meaningless without ① an airtight, execution-grounded verifier for
   one task family. A distillation or dashboard slice recommended before the verifier is
   not ambition, it's a blocked pick.
4. **One task family, airtight, before breadth.** `CLAUDE.md` #5: scope to ONE task family
   where the verifier can't be gamed. A second task family is a worse pick than hardening
   the first, every time.
5. **Earn the honest number.** The wedge is publishing a real, verified delta plus the
   "reward-hacking attempts caught & rejected: N" count. Weight whatever gets to *a
   measurable number* soonest — a capability that produces no evidence doesn't advance the
   thesis, however interesting it is.
6. **A gain you can't prove is not a gain.** Work that strengthens the never-regress gate
   or the held-out verified set outranks work that merely makes training faster. `UNVERIFIED`
   never counts as a win, so machinery that turns `UNVERIFIED` into a real verdict is worth
   more than its slot suggests.
7. **Reject what a better base makes redundant.** `CLAUDE.md` #4: build the part that gets
   *better* as open bases improve. If a stronger base model next quarter would delete the
   candidate's value, it's the wrong candidate.
8. **Local-first is a constraint on the pick, not a later port.** A design that only works
   by shipping the user's tasks or training off the box is out, not deferred.
9. **Follow-on slices count.** A shipped capability's next slice is a valid candidate.
10. **Demand-pull beats push.** A surface a real user asked for outranks one the roadmap
    merely lists.

## Process

1. Read the files above. Build the candidate list: unshipped capabilities whose
   dependencies are met, follow-on slices of shipped ones, and any demand-pulled work.
   For thoroughness, you may dispatch one read-only agent to summarize the planning docs.
2. For each candidate, record: shipped-state (cite the file), dependency status,
   moat-leverage, which core-loop element it advances, the risk it retires or exposes,
   and any known blocker.
3. Rank by the rules above. Pick ONE, plus one or two alternates.
4. Sanity-check the pick against the guardrails: does the reward stay execution-grounded?
   does the gate still refuse to promote on an unproven gain? does anything leave the box?
5. Produce the handoff (below).

## Output format

- **The pick**: one line naming the capability and a kebab-case slug.
- **Why**: 2 to 3 bullets tying it to the moat, its dependencies, and what shipped — each
  citing a file (and saying when that file doesn't exist yet).
- **Alternates**: one or two lines.
- **Known caveat**: the nearest feasibility risk, stated honestly, so the
  `whetstone-begin-fast` dig is not surprised by it.
- **Handoff prompt** (ready to paste): a `wbf feat <slug>` line plus a 3 to 5 sentence
  inline brief that includes the caveat and the capability's acceptance criteria (they are
  written first — the repo is test-first). Make clear the user runs this to start the
  worktree; this skill does not start it.

## Honesty rules

- Ground every shipped / pending / deferred claim in a named file. Do not assert from
  memory; the code and git history win over the docs.
- **Nothing has shipped yet.** One seed commit, no `src/`, no tests, no roadmap. Say the
  state is "not started" rather than implying progress. The same contract the product
  enforces applies to this skill: unverified is not passed off as done.
- **Do not invent numbers.** No projected gains, no percentages, no "this should get us
  ~X%". `CLAUDE.md` lists the only grounded external facts (RLVR/reward-hacking, the
  35%-false-positive judge result, Karpathy's environments gap); anything beyond those is
  unverified and must be labeled as such.
- If the strongest-looking candidate has a real blocker, say so and rank it accordingly
  rather than papering over it.
- Recommend only capabilities the files support. The files are thin today — if the pick
  comes from `CLAUDE.md`/`VISION.md` and discussion rather than a roadmap, say exactly that.

## Common mistakes

| Mistake | Fix |
|---|---|
| Inventing a capability or a phase plan not in the docs | Today the candidate set is `CLAUDE.md`'s core loop + `VISION.md`'s wedge; cite where each came from |
| Recommending a deep slice while `docs/ROADMAP.md` is unwritten | The roadmap is the named next artifact — it's usually the pick |
| Recommending the loop, the gate, or the dashboard before the verifier | Everything blocks on an airtight verifier for one task family |
| Adding a second task family before the first is airtight | Breadth after depth — `CLAUDE.md` #5 |
| Recommending an LLM-judge reward because it's faster to build | Drop it against the guardrails — that's the failure mode the project exists to design out |
| Recommending base-model training | Out of scope — we sharpen an open base on the user's tasks |
| Recommending work that needs data or training to leave the box | Local by default is a guardrail, not a preference |
| Recommending something a better open base would make redundant | `CLAUDE.md` #4 — build what improves *with* the base |
| Re-recommending shipped work | Check `git log` and the test suite first, not the prose |
| Re-recommending blocker-deferred work | Read the `docs/planning` deferral note; name the blocker |
| Quoting a projected improvement | No invented numbers — the delta comes from the verifier or it doesn't exist |
| Starting the worktree from this skill | Only recommend and hand off; the user runs `wbf` |
| A vague pick with no slice | Prefer a candidate with a clear, testable first slice |
