# PRD — public-task-offline

**Unit:** `chore/public-task-offline/aliz` · **Written:** 2026-10-21 · **Type:** chore, off the
reward path. **Source:** the inline brief in `docs/planning/_card/issue.md`. **Understanding:**
`docs/planning/public-task-offline/understanding.md`.

## Problem Statement

Two Torch/MPS nights drew all 832 rollouts and then refused `UNVERIFIED` because the **one public
task** (`pallets__flask-4045`) could not be provisioned at the end of the run:

```
CheckoutError: could not clone 'https://github.com/pallets/flask.git':
Could not resolve host: github.com
```

The public task is processed last; the Mac slept; the network dropped. `_select` is right to
refuse a run whose control arm did not prove the harness. The cost is a 5–6 h night for no result.

The dig shows a digest-dir pre-warm alone cannot fix it: `provision` clones into the digest dir, but
the **control arm** (`verify_strict`/`verify_weak`) and the **oracle** clone into **fresh**
destinations (`strict.py:147-152`, `weak.py:95-100`, `sources.py:465-469`). Every one of them calls
`materialise`. The fix must sit there.

The verifier's `_git` deliberately nulls `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` so no machine
config can change what gets verified (`repo.py:155-185`). That isolation is correct; a mirror must
be an explicit harness input, not ambient git config.

## What this unit is — and is not

It makes the public task provisionable **offline** for every caller, makes a pre-provisioned
checkout reusable, and holds the machine awake through the night. It does not run a night, change
the base, touch the reward, or claim a number. The 7B yield question is a separate unit.

## Goals & Success Metrics

A merged, green tree in which:

- **A local mirror is an explicit input.** `WHETSTONE_REPO_MIRRORS` (JSON: canonical URL → local
  bare repo) is read by `materialise`; a task with an entry clones from the mirror; a missing or
  invalid mirror is a named `CheckoutError`, never a silent network fallback.
- **A pre-populated checkout is reused.** A clean checkout at `task.base_commit` is returned with
  no clone; another commit with the object present is checked out detached; a wrong commit with no
  object, a dirty tree, or a populated non-git directory is refused by name. Nothing is deleted or
  cloned over.
- **The verifier's git isolation is not weakened.** Hooks are neutralised on every `_git`
  invocation (or at least on a reused checkout), and a planted `post-checkout` hook does not run.
- **The sheet can run a night offline.** It pre-warms the public digest dir, exports the mirror
  mapping, and wraps the doors in `caffeinate -dimsu`; the guard pins all three.

## Requirements

### Must-have

**M1 — the mirror mapping.**
`materialise` reads `WHETSTONE_REPO_MIRRORS` (a JSON object; unset/empty means no mapping) and uses
the mapped local path as the clone source when the task's `repo_url` has an entry. The task
manifest keeps the canonical `repo_url`. A mapped path that is missing or not a git repository is a
`CheckoutError` naming both the URL and the mirror, and **no clone of the canonical URL is
attempted** — an offline run must fail rather than quietly reach the network. The mirror is not
git config: `_git`'s `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM=/dev/null` stays.

**M2 — the reuse branch.**
Before cloning, `materialise` handles a populated destination:
- if it is a git work tree rooted exactly at the destination, **clean**, and `HEAD` is
  `task.base_commit` → return, no clone;
- if it is a clean work tree at another commit and the base commit object exists locally →
  `git checkout --quiet --detach <base_commit>`;
- otherwise → `CheckoutError` naming the reason (wrong commit/object absent, dirty tree, not a git
  work tree). Never delete, never clone over.
The empty/missing destination path clones exactly as today.

**M3 — hooks neutralised on the verifier's git.**
`_git` passes `-c core.hooksPath=/dev/null` (and `GIT_NO_LAZY_FETCH=1` for a partial clone), so a
reused or operator-supplied checkout cannot execute a repo-local hook during `checkout`/`apply`
outside the sandbox. A test plants a `post-checkout` hook in a reused checkout and asserts it does
not run. The global/system config isolation is unchanged.

**M4 — the sheet.**
The Torch/MPS sheet gains, before the night: the `WHETSTONE_REPO_MIRRORS` export (with the flask
mirror path), the pre-warm copy of
`$REPO/runs/<torch-probe-run-id>-workspace/environments/b885fb84763091db` into the night workspace,
and `caffeinate -dimsu` on the probe and night blocks. The workspace-emptiness sentence says "empty
except the pre-warmed public digest dir". `tests/test_torch_mps_runbook_guards.py` pins the
`caffeinate` prefix, the pre-warm, the digest literal and the mirror export.

**M5 — tests.**
`materialise` with the mapping and an unreachable canonical URL clones from the mirror; without the
mapping it still clones the URL; a missing mirror refuses without network; the reuse cases above;
`provision` and `verify_strict` with the mapping and an unreachable `repo_url` succeed offline;
the digest of the committed public manifest's pins is `b885fb84763091db`; the hooks test.

**M6 — the write-up.**
`docs/STATUS.md` and `CHANGELOG.md` in the same commit: the provisioning reliability landed; no
night was run; no number; the two lost nights are the motivation, not a base result. The
`src/whetstone/verify/repo.py` move is a **declared reward-path amendment** in
`reward-path-amendments.json` (`2026-10-22-public-task-offline`) — the freeze guards are not edited;
the declaration is the sanctioned path, and it states that the change is provisioning, not verdict
semantics.

### Should-have

**S1 — `UV_OFFLINE=1` in the sheet's environment**, so a cold uv cache fails loudly instead of
reaching an index during the public venv build.

## Acceptance Criteria (testable, written first)

1. With `WHETSTONE_REPO_MIRRORS` mapping the task's URL to a local bare repo and the canonical URL
   unreachable, `materialise` clones from the mirror and checks out `base_commit`; no network.
2. Without the mapping, `materialise` clones the canonical URL (existing behaviour).
3. A mapped mirror that is missing is a `CheckoutError` naming the URL and mirror; the canonical
   URL is not attempted.
4. Reuse: clean at base → no `git clone`/`fetch` (asserted from the recorded git invocations);
   other commit + object present → detached checkout; object absent, dirty tree, populated
   non-git → `CheckoutError`; the directory is not deleted.
5. A planted `post-checkout` hook in a reused checkout does not execute.
6. `provision` and `verify_strict` with the mapping and an unreachable `repo_url` succeed offline.
7. The committed public manifest's pins hash to `b885fb84763091db` (cross-pin).
8. The sheet guard passes with `caffeinate -dimsu`, the pre-warm, the digest and the mirror export;
   the MLX sheet/guard are untouched.
9. `src/whetstone/verify/`'s reward semantics, `tasks/`, the held-out document and the gate rule
   are otherwise unchanged; the adversarial and reward-path suites stay green; `ruff`/`mypy` pass.

## Out of scope / guardrails

- **No night run and no base change.** The 7B/base question is separate.
- **No reward/gate/corpus/held-out change.** The verifier's verdicts are untouched.
- **No machine git config.** The mirror is an explicit env input; `_git`'s isolation stays.
- **No number.** The two lost nights are not a result about the 7B.
- **No `reports/` home.**

## Risks and flagged gaps

🔴 **The mirror is only as good as its content.** A mirror without `base_commit` fails the detached
checkout by name; the operator must refresh it. The sheet pins the digest and the path; a stale
mirror is a named refusal, not a silent wrong tree.

🟡 **The venv build is not forced offline.** The pins route's `uv pip install` has no `--offline`
unless an index is given; a warm cache is assumed, and `UV_OFFLINE=1` (S1) makes a cold cache fail
loudly. The pre-warm copy also removes that build.

🟡 **The digest key excludes the repo and commit.** The pre-warm uses the literal
`b885fb84763091db`; a manifest pin change re-clones (and fails offline). The cross-pin test and the
sheet literal make the drift loud.

🟡 **`caffeinate -s` is AC-only.** On battery, `-d/-i/-m/-u` still apply; the sheet states the
machine must be on power for `-s` to hold.

🟡 **A reused checkout is a trust surface.** M3 neutralises hooks; the pre-warmed checkout comes
from the probe (no hooks). The mirror is operator-supplied, like the donor.

## Aspects

1. `materialise-mirror/` — M1–M3, M5: the mirror mapping, the reuse branch, the hooks hardening,
   and their tests.
2. `sheet-and-writeup/` — M4, M6, S1: the sheet, the guard, the write-up.

## Open questions (for the review gate)

1. **The mirror input.** `WHETSTONE_REPO_MIRRORS` JSON env (recommended: explicit, inherited by the
   verifier subprocesses, no CLI plumbing) vs a `--repo-mirror` flag threaded through the doors.
2. **The reuse branch.** Include it (recommended: it makes the pre-warm and a killed run's
   workspace actually work) vs the mirror alone.
3. **The hooks hardening.** Include `core.hooksPath=/dev/null` (recommended) vs document the reused
   checkout as trusted.
