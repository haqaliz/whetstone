# feat p0-scaffold — Make the repo executable and test-first (ROADMAP P0)

## Source

**FALLBACK path.** No GitHub issue exists. `gh issue list --state all` returns "No Issues"
against `haqaliz/whetstone` (Issues reachable, repo empty of them), and the `id` is a slug,
not a number. Per `references/gather-context.md` §0 this is the expected case for a
greenfield repo, not a failure.

Unlike the previous unit of work, this one has a **committed upstream spec**:
`docs/ROADMAP.md` § 4 "P0 — Scaffold", merged to `master` in PR #2 (`347655a`) immediately
before this branch was cut. The roadmap, not this card, is the authority on P0's exit
criteria.

## Brief

Reproduced verbatim from the `whetstone-next` handoff the user acted on by invoking
`wbf feat p0-scaffold`:

> Build P0 — Scaffold from `docs/ROADMAP.md:128-141`: turn a docs-only repo into an
> executable, test-first Python project so P1's verifier can be built under strict TDD.
> Constraints are already locked in `docs/planning/roadmap-and-task-family/prd.md`
> (criterion 10): `src/whetstone/`, uv, ruff, mypy, `master` as base branch. Caveat for the
> dig: the PyPI distribution name is an open question — `ROADMAP.md:337` records bare
> `whetstone` as taken and `whetstonehq`/`whetstone-ai` as free, but labels this
> **unverified**, so re-check PyPI before writing `pyproject.toml` rather than trusting the
> record; and guard against satisfying "non-trivial test" with an import smoke test.
> Acceptance criteria (write these first): (1) `uv run pytest` exits 0 with at least one
> test that exercises real behaviour, not just importability; (2) `uv run whetstone --help`
> exits 0 and the CLI entry point is wired through `pyproject.toml`; (3) `uv run ruff check .`
> and `uv run mypy src/` both exit 0; (4) `LICENSE` exists as Apache-2.0 per `CLAUDE.md:93`;
> (5) a CI workflow runs all four commands and is green on `master`. No verifier, no reward,
> no model code in this slice — P0 is the floor, and P1 is where the moat gets built.

## The upstream spec (authoritative)

`docs/ROADMAP.md:128-141`, verbatim:

> ### P0 — Scaffold · est. 1 week · target 2026-08-02
>
> The repo currently contains zero lines of executable code. Nothing can be test-first until
> a test runner exists.
>
> **Exit criteria**
> - `uv run pytest` exits 0 with at least one non-trivial test
> - `uv run whetstone --help` exits 0
> - `uv run ruff check .` and `uv run mypy src/` exit 0
> - `LICENSE` exists (Apache-2.0 — `CLAUDE.md:93` states it; the file is absent today)
> - CI workflow green on `master`
>
> **Pivot signal:** none credible.

Note the exact command scopes: `ruff check .` is repo-root, `mypy src/` is src-only.

## Resolved before planning (was an open question in the brief)

**PyPI availability, checked against the live index on 2026-07-26** — this closes
`ROADMAP.md:337`'s open question #1, which was explicitly labelled *"unverified as of today"*:

| Name | `GET https://pypi.org/pypi/<name>/json` | Verdict |
|---|---|---|
| `whetstone` | HTTP 200 | **taken** |
| `whetstonehq` | HTTP 404 | available |
| `whetstone-ai` | HTTP 404 | available |
| `whetstone-hq` | HTTP 404 | available |

The seed research's record was correct. This resolves *availability*; the *choice* of name is
a PRD decision. The import package and CLI remain `whetstone` regardless — that is locked
(`prd.md:174`).

## Selection rationale carried forward (from `whetstone-next`)

- The roadmap now exists and names P0 itself, so `whetstone-next`'s rule 1 ("before the
  roadmap exists, the roadmap is the pick") is discharged.
- Nothing has shipped: `master` at `347655a` carries `CLAUDE.md`, `VISION.md`, `README.md`,
  `assets/logo.svg`, `docs/`, and the skills. **Zero lines of executable code**, no `src/`,
  no `tests/`, no tags.
- P0 does not jump the verifier. It builds the floor P1 stands on. `whetstone-next`'s rule 3
  ("everything blocks on the verifier") is satisfied because P1's exit criteria
  (`ROADMAP.md:154-166`) presuppose a working `uv run pytest`.

Alternate recorded, not chosen: **P1 verifier slice** — higher moat-leverage and the faster
route to a real `N`, but blocked on this unit's toolchain.

## Core-loop placement

**None of the five directly.** P0 is infrastructure beneath the loop: it makes ① buildable
under strict TDD without implementing any part of it. This is the honest placement — claiming
P0 advances ① would overstate it.

The relevant guardrail consequence is negative and load-bearing: **P0 must not put an
inference library on the reward path**, because P1 ships an AST guard that fails the build if
one is there (`ROADMAP.md:158`; see the correction recorded in `understanding.md`).

## Related work

- **PR #2** (merged, `347655a`) — `docs/ROADMAP.md` + the roadmap PRD. The direct upstream.
- **PR #1** (merged, `67bc833`) — logo + README.
- **Belay** (`~/dev/at/belay`) — the shipped sibling. Its scaffold is the reference
  implementation for nearly every open question here; see `understanding.md` § Belay
  precedent.

## Note on this file

`docs/planning/_card/issue.md` is id-free by design (`whetstone-begin-fast` § Phase 1: *"the
id lives in the branch/PR"*), and PR #2 committed it to `master`. Each new unit of work
therefore **overwrites** the previous unit's card on its own branch. The roadmap unit's card
is preserved in history at `347655a`. Flagged as a workflow wart, not a blocker.

## Attachments

None.
