---
name: whetstone-end
description: Use when finishing local work on a Whetstone unit of work after the PR is merged and you also need a completion report on Desktop. Triggers on "whetstone-end", "we", "we bug 12", "we feat task-verifier", "end full".
arguments: "type id"
---

# Whetstone End (Full Track)

## Overview

Same cleanup as `whetstone-end-fast`, **plus** a completion report at the end via `whetstone-report`.

**Invocation:** `we <type> <id>` — e.g. `we bug 12`, `we feat task-verifier`.
Arguments and conventions are identical to `whetstone-end-fast`.

## Pipeline

**REQUIRED SUB-SKILL:** Use `whetstone-end-fast` for the cleanup pipeline.

Run its **Phase 0 → Phase 3 exactly as written** (safety check → master + pull → remove worktree → delete branch, then the release phase). Whetstone's base branch is **`master`**, never `main`. **Phase 3 is mandatory** — `pyproject.toml`, `RELEASING.md`, `CHANGELOG.md` and `release.yml` all exist, so every finished unit cuts a release by tag push; verify those four files rather than assuming, and report which channels actually published. Proceed to the report once cleanup verification passes.

### Phase 4 — Completion report

**REQUIRED SUB-SKILL:** Use `whetstone-report` with the unit-of-work id and the corresponding type.

The two skills use slightly different type vocabularies — map before invoking:

| `we` arg | `whetstone-report` arg |
|---|---|
| `bug` | `bug` |
| `task` | `task` |
| `chore` | `task` |
| `feat` | `feature` |
| `feature` | `feature` |

Example: `we bug 12` → invoke `whetstone-report` with `bug` + `12` → writes `/Users/aliz/Desktop/bug-12-completion.md`.

`whetstone-report` fetches the issue via `gh` when reachable (otherwise works from the merged PR / what we just did) and produces the standard template. If it asks for a screenshot/video, provide one (or hand it to the user to attach), then confirm the file landed on Desktop.

### Phase 5 — Comment on the issue (optional)

Same approach as `whetstone-end-fast` Phase 4 — ask the user, draft (using the issue + the just-generated report as source material), confirm, then `gh issue comment <id>`. Skip if there's no reachable issue.

The comment can mirror the report's plain-English summary in a sentence or two. Same tone rules: no em dashes, no jargon, no commit hashes, and no gain the verifier hasn't actually measured. Skip entirely if the user declines.

## Common mistakes

| Mistake | Fix |
|---|---|
| Running the report before cleanup | Phases 0–2 first; the report is last |
| Skipping the report on purpose | Use `whetstone-end-fast` / `wef` instead |
| Passing the wrong type to `whetstone-report` | Apply the mapping table (`feat`/`feature` → `feature`, `chore` → `task`) |
| Posting the issue comment before the report | The comment (Phase 5) comes after the report (Phase 4); the report's plain-English summary is good source material |
| Cleaning up against `main` | Whetstone's base branch is `master` |
| Skipping the release because Phase 3 once read as blocked | The machinery exists — Phase 3 is mandatory; verify the four files and cut it |
| Putting a projected improvement in the report | Only a measured delta on the held-out verified set goes in a report |
| Posting the comment without confirmation | Draft first, confirm with the user, then post |
