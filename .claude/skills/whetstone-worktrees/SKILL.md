---
name: whetstone-worktrees
description: Isolate parallel work in the Whetstone repo using the Claude Code worktree layout. Use when starting a new bug/feature that should not collide with another running Claude session, or when running the loop and the dashboard from different branches at once. Covers branch naming, worktree placement under .claude/worktrees, per-worktree uv/npm setup, and cleanup.
allowed-tools: Bash, Read, Write, Edit, Glob
---

# Whetstone Worktree Workflow

## When to Use

- You have another Claude session running on a different branch in Whetstone and want to start a new bug/feature without colliding.
- You want to run two things side by side — e.g. the nightly loop on one branch and the dashboard on another.
- A long training/eval run is holding one checkout busy and you want to keep editing elsewhere.
- The primary checkout is dirty and switching branches would mix work.

Don't use this for one-off file edits that finish in a single session — a worktree is overhead for nothing if you commit + push before the next branch switch.

## Layout — the official Claude Code pattern

Whetstone is a **single repo**. Worktrees live **inside it** at `.claude/worktrees/<name>/`. `.claude/worktrees/` must be in `.gitignore` so worktree contents never show up as untracked files in the primary.

```
/Users/aliz/dev/at/whetstone/                                   ← primary (master)
/Users/aliz/dev/at/whetstone/.claude/worktrees/bug-12/          ← bug #12 worktree
/Users/aliz/dev/at/whetstone/.claude/worktrees/feat-task-verifier/
```

This is the layout documented at https://code.claude.com/docs/en/worktrees. Older sibling layouts (`whetstone.12` next to the repo) work but make `cd` paths awkward and don't auto-trigger `.worktreeinclude` for `claude --worktree`.

`.gitignore` carries the `.claude/worktrees/` entry, so this is set up. Verify any time with `git check-ignore -v '.claude/worktrees/'` — keep the **trailing slash**: the pattern is directory-only, so a bare `.claude/worktrees` reports "not ignored" whenever the directory doesn't exist yet, which is a false alarm, not a missing rule.

## Branch naming convention

`<type>/<id>/<owner>` — owner is `aliz`. `id` is a GitHub issue number when there is one, otherwise a short descriptive slug.

- `bug/12/aliz`
- `feat/task-verifier/aliz`
- `feat/promotion-gate/aliz`
- `chore/pin-uv-version/aliz`

Worktree dir name drops the slashes: `<type>-<id>` (e.g. `bug-12`, `feat-task-verifier`).

## The base branch is `master`

Whetstone's base branch is **`master`**, not `main`. Every branch-from, rebase target, and PR base is `master`. Never assume `main` exists.

`origin/master` **exists** (the project context, vision, and skills are pushed), so the normal flow below works. Always branch from `origin/master` rather than local `master` — it's the shared truth, and the local ref may be stale.

## Creating a worktree

### From master (new branch)
```bash
git fetch origin master
git worktree add -b feat/task-verifier/aliz .claude/worktrees/feat-task-verifier origin/master
```

### From an existing branch you already pushed
```bash
git worktree add .claude/worktrees/feat-task-verifier feat/task-verifier/aliz
```

### Via Claude Code's --worktree flag
```bash
claude --worktree feat-task-verifier
```
This creates `.claude/worktrees/feat-task-verifier/` on a new branch `worktree-feat-task-verifier` based on `origin/HEAD`. Your preferred issue/slug branch names don't match that auto-generated name — when you name the work after an issue, create the branch first (as above), then `git worktree add` with the existing branch. Don't rely on `--worktree` to name it.

## Auto-copying gitignored config (`.worktreeinclude`)

A `.worktreeinclude` at the repo root lists gitignored files that should follow into new worktrees, consumed automatically by `claude --worktree`.

**Whetstone currently has no secrets/env files to copy.** Whetstone is **BYOK** for the optional cloud teacher model used in distillation, so once a `.env` or a local model/runtime config exists, create `.worktreeinclude` and list it there, then copy manually when you use bare `git worktree add` (the include is not re-processed after creation):

```bash
# only if such files exist
cp .env .claude/worktrees/feat-task-verifier/
```

`.venv/`, `node_modules/`, and the loop's artifact dirs (`/runs/`, `/checkpoints/`, `/tasks/local/`, `/reports/local/`, `/_sandbox/` — all already in `.gitignore`) are intentionally **not** copied. The first two are large and regenerable; recreate the venv per worktree (below). The rest are the user's own data and never leave the box, per the no-egress guardrail in `CLAUDE.md`.

**Never copy checkpoints, run state, or eval sets between worktrees.** They are the evidence behind a promotion decision, and the never-regress gate depends on that provenance: a checkpoint compared against a held-out set it wasn't actually evaluated on is not a verified gain, it's a fabricated one. Copying an eval set across branches is also how a held-out set silently becomes a training set. If a worktree needs run data, point at it by absolute path rather than duplicating it.

## Per-worktree setup (Python core — uv)

`.venv` is per-worktree and not shared:

```bash
cd .claude/worktrees/feat-task-verifier
uv sync                       # build the venv from uv.lock
uv run pytest                 # run the test suite
uv run whetstone --help       # the CLI entrypoint
```

⚠️ **Weights and corpora are machine-level, not per-worktree.** `weights/` is ~13 GB and `tasks/local/` is the user's own mined corpus; both are gitignored and neither is copied into a worktree. Point at the primary checkout's copies by **absolute** path rather than duplicating them — and note that `weights/provenance.json` records `local_dir` relative to the weights root, so weights fetched *inside* a worktree are stranded when that worktree is removed. Fetch them in the primary checkout.

⚠️ **GPU / local runtime:** the local runtime is **MLX** (`mlx-lm`, an optional extra — `uv sync --extra mlx`), and the GPU is a **machine-level** resource, not a per-worktree one. Two worktrees running training or eval at once will contend for the same GPU and the same runtime port. Serialize the runs, or override the port and be explicit about which worktree owns the device — a run that silently shared a GPU is a run whose timings you can't compare.

## Per-worktree setup (dashboard)

The dashboard (TypeScript — the nightly report, the verified-gain trend, the caught-hack log) **does not exist yet**. Once it does, `node_modules` is per-worktree and not auto-installed:

```bash
cd .claude/worktrees/feat-task-verifier/dashboard
npm install
npm run dev                   # default port 3000
```

If the primary is already serving on 3000, override:
```bash
npm run dev -- -p 3001
```

## Switching between worktrees

```bash
git -C /Users/aliz/dev/at/whetstone worktree list
```

To jump into a worktree's Claude session, `cd` into the worktree dir and run `claude`. Resuming a session started in the primary on the same branch isn't supported — start a fresh session in the worktree.

## Cleaning up

After the PR merges and you no longer need the branch locally (see `whetstone-end-fast`):

```bash
git -C /Users/aliz/dev/at/whetstone worktree remove .claude/worktrees/feat-task-verifier
git -C /Users/aliz/dev/at/whetstone branch -d feat/task-verifier/aliz
```

`worktree remove` refuses if there are uncommitted or untracked changes. Either commit them first, or pass `--force` only if you're sure they should be discarded. Check for run artifacts before forcing — a discarded `runs/` directory is a discarded night of evidence.

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `git worktree add` fails: `invalid reference: origin/master` | Stale local refs | `git fetch origin master` first — `origin/master` exists |
| Branching from `origin/main` | Whetstone's base branch is `master` | `main` does not exist — always use `master` |
| Worktree contents appear as untracked in primary | `.claude/worktrees/` not ignored | Already in `.gitignore`; verify with `git check-ignore -v '.claude/worktrees/'` (trailing slash) |
| `uv run python -m whetstone.bakeoff.run` provisions nothing, every task UNVERIFIED | `--workspace` was a **relative** path | Pass absolute paths: the checkout is created under `--workspace` and a relative one does not resolve from the run's cwd |
| `uv run` reinstalls everything on first call in a worktree | `.venv` not shared between worktrees | Expected — `uv sync` once per worktree |
| `pytest` import errors in worktree | Forgot `uv sync` (no venv yet) | `uv sync` in the worktree root first |
| Two worktrees training at once, numbers don't reproduce | GPU/runtime is machine-level, not per-worktree | Serialize the runs; never compare timings across contended runs |
| `git worktree add` fails: "already checked out" | Branch is checked out in another worktree (often the primary) | `git checkout master` in the conflicting worktree, then retry |
