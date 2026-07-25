# feat roadmap-and-task-family — Write docs/ROADMAP.md and choose the first task family

## Source

**FALLBACK path.** No GitHub issue exists. `gh issue list` returns "No Issues" against
`haqaliz/whetstone` (Issues reachable, repo empty of them), and the `id` is a slug, not a
number. Per `references/gather-context.md` §0 this is the expected case for a greenfield
repo, not a failure.

The brief below is the handoff produced by the `whetstone-next` skill in the immediately
preceding session, which the user acted on by invoking `wbf feat roadmap-and-task-family`.
It is reproduced verbatim.

## Brief

> Write docs/ROADMAP.md: a 2–3 month phased plan with milestones for Whetstone. CLAUDE.md
> names this as the immediate next artifact and the repo is greenfield (two commits, no docs/,
> no src/, no tests) — so this is the first real unit of work, and it must produce a ranked
> plan grounded only in CLAUDE.md and VISION.md, never in invented phases or projected numbers.
>
> The load-bearing decision is picking ONE task family whose verifier is execution-grounded and
> deterministic (CLAUDE.md guardrail #5), and specifying how that verifier actually checks
> observed-vs-claimed end state. Caveat for the dig: this is a docs artifact, so acceptance
> criteria are a checklist over content rather than a test suite, and the failure mode to guard
> against is a roadmap of generic phases that never commits to a family or a verifier mechanism
> — that would leave the current blocker intact.
>
> Acceptance criteria (write these first):
> 1. A single named task family, with a stated reason its end state is deterministically
>    checkable and a paragraph on how a policy would try to game it and why it can't.
> 2. Phases ordered per CLAUDE.md's core loop — verifier before loop before promotion gate
>    before report — each with an exit criterion that is observable, not narrative.
> 3. Milestones dated relative to a start date, sized for a solo founder.
> 4. An explicit "first honest number" milestone: what gets measured, on what held-out verified
>    set, and where the "reward-hacking attempts caught & rejected: N" count comes from.
> 5. Every guardrail restated as a rejection test the plan passes: no frontier base training,
>    no LLM-judge reward, no data egress, UNVERIFIED never counts as a win, and nothing a
>    better open base would make redundant.
> 6. Zero fabricated statistics — only the grounded facts CLAUDE.md lists, anything else
>    labelled unverified.

## Selection rationale carried forward (from `whetstone-next`)

The pick was ranked #1 because:

- `CLAUDE.md` names `docs/ROADMAP.md` as the immediate next artifact ("The next step is a
  planning session that produces `docs/ROADMAP.md`") and lists it under "Docs structure (to
  be created)". `find docs -type f` returned nothing — there is no `docs/` directory.
- `git log` shows two commits (`000ccd9` seed context + vision, `392baf6` port the skills).
  No `src/`, no tests, no tags, no `CHANGELOG.md`, no `README.md`. State is **not started**.
- Everything blocks on core-loop element ① (a verifiable task family + verifier). `CLAUDE.md`
  guardrail #5 requires scoping to ONE family where the verifier is airtight before breadth.

Alternates recorded, not chosen: `verifier-spike` (runnable verifier before the plan —
stronger on time-to-evidence, weaker because the family is unchosen), `architecture-doc`
(`docs/technical/ARCHITECTURE.md` — downstream of the family choice).

## Core-loop placement

Primarily **① verifiable task family + verifier** (it selects the family and specifies the
check), and secondarily the *sequencing* of ②–⑤. This work does not itself implement the
reward, the loop, or the gate.

## Related work

None in-repo. `CLAUDE.md` cites the seed research at
`~/dev/at/ideas/research/b1-verified-self-improvement.md` as background (rationale, not a
backlog). Sibling project Belay (`~/dev/at/belay`) is the execution-grounded verification
engine whose verifier/replay may be reusable.

## Attachments

None.
