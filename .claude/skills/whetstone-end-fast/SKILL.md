---
name: whetstone-end-fast
description: Use when finishing local work on a Whetstone unit of work after the PR is merged and you want to clean up without generating a completion report. Triggers on "whetstone-end-fast", "wef", "wef bug 12", "wef feat task-verifier", "end fast".
arguments: "type id"
---

# Whetstone End (Fast Track)

## Overview

Closes out a unit of work's local state after the PR has merged: **master → pull → remove worktree → delete branch**, with a **release phase that is blocked today** (no release machinery exists yet). No report (use `whetstone-end` / `we` for that).

**Invocation:** `wef <type> <id>` — e.g. `wef bug 12`, `wef feat task-verifier`.

- `type` ∈ `bug | feat | feature | task | chore` (normalize `feature` → `feat`)
- `id` = the GitHub issue number, or the slug used at begin time
- Owner is `aliz`
- Branch: `<type>/<id>/aliz`; worktree dir: `.claude/worktrees/<type>-<id>`

Whetstone is a single repo, so this runs once. The base branch is **`master`**, never `main`.

## Pipeline

### Phase 0 — Safety check

Before removing anything:

- **Worktree clean?** `git -C <worktree> status --porcelain` must be empty. If not, stop — commit or stash first.
- **Run artifacts?** The loop's outputs (`runs/`, `checkpoints/`, `reports/local/`) are gitignored, so a "clean" worktree can still be holding a night of evidence. Check before removing: if a checkpoint or eval result in there backs a claim anyone has made, move it somewhere durable first. `worktree remove` deletes it with no undo.
- **Branch merged?** Confirm the PR is merged (`gh pr view <PR> --json state,mergedAt` if reachable). `git branch -d` will refuse an unmerged branch on purpose; do not bypass with `-D` without explicit user OK.
- **You may be inside the worktree being removed.** Resolve the primary checkout first (Phase 1) and run all commands from there.

### Phase 1 — Master, pulled

Resolve the **primary** checkout (not the worktree). The first line of `git worktree list` is the primary:

```bash
PRIMARY=$(git worktree list | head -1 | awk '{print $1}')
```

Switch and pull, fast-forward only:

```bash
git -C "$PRIMARY" checkout master
git -C "$PRIMARY" pull --ff-only origin master
```

### Phase 2 — Remove worktree, delete branch

```bash
WORKTREE_NAME="<type>-<id>"   # e.g. bug-12, feat-task-verifier
BRANCH="<type>/<id>/aliz"     # e.g. bug/12/aliz, feat/task-verifier/aliz

git -C "$PRIMARY" worktree remove ".claude/worktrees/$WORKTREE_NAME"
git -C "$PRIMARY" branch -d "$BRANCH"
```

If `worktree remove` refuses due to uncommitted/untracked files, go back to Phase 0 — don't pass `--force` silently.

If `branch -d` refuses because the branch isn't merged into master, surface the message — the PR may not be merged, or there are unpushed commits. Don't use `-D` silently.

After both succeed, verify:

```bash
git -C "$PRIMARY" worktree list           # the worktree should be gone
git -C "$PRIMARY" branch --list "$BRANCH" # should print nothing
```

### Phase 3 — Release a new version (BLOCKED today)

**There is no release machinery in Whetstone yet.** No `pyproject.toml`, no `CHANGELOG.md`, no `RELEASING.md`, no `.github/workflows/release.yml`, and no chosen package name. So today this phase is a **no-op**: say plainly that no release was cut and why, then move on. Do not hand-craft a release to fill the gap — an unpublished project with a manually uploaded artifact is worse than no release at all.

Check before assuming (the repo may have moved on since this skill was written):

```bash
ls pyproject.toml RELEASING.md CHANGELOG.md .github/workflows/release.yml 2>&1
```

**Once those exist, this phase becomes mandatory** — every finished unit of work cuts a release. `RELEASING.md` is the source of truth at that point; what follows is the shape it should take, matching the sibling projects:

1. **Version from the work type:** `feat`/`feature` → **minor** (`0.x+1.0`), `bug`/`chore`/`task` → **patch** (`0.x.y+1`). Read the current `version` in `pyproject.toml` and compute the next; confirm the exact `vX.Y.Z` with the user only if it's ambiguous, otherwise state it and proceed.
2. **Bump + changelog:** update `version` in `pyproject.toml` and move the `CHANGELOG.md` `[Unreleased]` notes into a new dated `## [X.Y.Z]` section. Commit to `master` as `aliz@foresightanalytics.ca` (maps to haqaliz).
3. **CI must be green first.** Push the bump commit to `master` and confirm CI passes (`gh run watch`) before tagging. Never tag on red CI — a release is irreversible (a PyPI version can never be reused, even if yanked).
4. **Tag and push** — this triggers the release:
   ```bash
   git tag -a vX.Y.Z -m "whetstone X.Y.Z" && git push origin vX.Y.Z
   ```
   A tag push is the whole mechanism. Do not `gh release create` by hand and do not build/upload artifacts manually — let the workflow do it.
5. **Verify each channel is live before calling it done.** This is the same honesty rule the product enforces: an unchecked channel is `UNVERIFIED`, not shipped. Watch the release run (`gh run watch`), then confirm each published channel directly. Report which ones published and surface any job that failed; never claim a channel shipped without checking it.

**Release identity, do not get this wrong:** the release belongs to the **haqaliz** account (`git@github.com:haqaliz/whetstone.git`), never `playdolphia`/`aliz-manifold`. Any manual step must run with `gh` active as haqaliz (`gh auth switch --user haqaliz`). Commit as `aliz@foresightanalytics.ca`.

### Phase 4 — Comment on the issue (optional)

Optional, and only if there's a reachable GitHub issue. Ask first: *"Want me to post a short comment on the issue explaining what we did?"* If the user declines, there's nothing meaningful to say, or there's no issue (the work came from an inline brief), skip.

Otherwise:

1. **Draft a short note** (2–4 sentences). Sources, in order of preference:
   - What the user tells you to say.
   - The merged PR's title + description (`gh pr view <PR>`), if accessible.
   - A best-effort summary from the issue title and the change verb.

   Keep it friendly, light on jargon, no em dashes, no commit hashes, no file paths. The change verb matches the type: `bug → fixed`, `task → done`, `feat`/`feature → shipped`, `chore → done`. Example: *"Shipped the task checker. A night's work is now scored by actually re-running the task and looking at what really happened, instead of by asking a model whether it looks right. Let me know if anything looks off."*

   **Don't quote a gain the verifier didn't produce.** If the work has no measured delta yet, say what it enables, not what it improved.

2. **Confirm the draft** with the user before posting.

3. **Post it** via `gh`:

   ```bash
   gh issue comment "$ID" --body "<confirmed comment text>"
   ```

   On success `gh` prints the comment URL. Tell the user it landed. If `gh` errors (not authenticated, Issues disabled), surface it and stop — don't retry blindly.

## Common mistakes

| Mistake | Fix |
|---|---|
| Running from inside the worktree being removed | Resolve `PRIMARY` first, run commands from there |
| Checking out / pulling `main` | Whetstone's base branch is `master`; `main` doesn't exist |
| Using `git pull` (allowing merge) | Use `--ff-only` |
| Forcing branch delete with `-D` | Only after explicit user OK — `-d` refuses unmerged for a reason |
| Forcing worktree remove with `--force` | Same — never silently discard uncommitted work |
| Deleting a worktree holding checkpoints/eval results | Gitignored ≠ worthless; move the evidence out first, then remove |
| Worktree dir vs branch confusion | Worktree dir is `<type>-<id>` (e.g. `bug-12`); branch is `<type>/<id>/aliz` |
| Cutting a release today | Phase 3 is blocked — no `pyproject.toml`/`RELEASING.md`/`release.yml` yet; say so instead of improvising one |
| Hand-crafting a release (`gh release create`, manual upload) | When the machinery lands, a tag push is the whole mechanism |
| Tagging on red CI | A release is irreversible (a PyPI version can't be reused); confirm CI green before the tag |
| Cutting a future release as `playdolphia` | The release is haqaliz's; switch with `gh auth switch --user haqaliz` |
| Posting the issue comment without confirmation | Draft first, show the user, only post after explicit OK |
| Trying to comment when the work has no issue | Skip Phase 4 — it came from an inline brief |
