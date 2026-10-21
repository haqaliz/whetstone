# Spec — materialise-mirror

**Aspect:** `materialise-mirror` · **Unit:** `public-task-offline` · **PRD:** `../prd.md` M1–M3,
M5 · **Date:** 2026-10-21

## Purpose

Make every `materialise` caller provision the public task from a local mirror, reuse a
pre-provisioned checkout, and keep the verifier's git isolation intact.

## M1 — the mirror mapping

- `materialise(task, destination)` reads `WHETSTONE_REPO_MIRRORS`: a JSON object mapping a
  canonical URL to a local bare-repo path. Unset or empty ⇒ no mapping.
- If `task.repo_url` has an entry, the clone source is the mapped path; the task manifest keeps the
  canonical URL. A mapped path that is missing or not a git repo is a `CheckoutError` naming the URL
  and the mirror; **the canonical URL is not attempted** (an offline run fails, not silently goes
  online).
- A malformed JSON env is the same named refusal.
- `_git`'s `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM=/dev/null` is unchanged.

## M2 — the reuse branch

Before the clone:
- destination is a git work tree rooted exactly at the destination, the tree is **clean**, and
  `HEAD` is `task.base_commit` → return, no clone;
- clean at another commit and the base commit object exists locally → `git checkout --quiet
  --detach <base_commit>`;
- otherwise (wrong commit with no object, dirty tree, populated non-git, unresolvable commit,
  destination nested in another repo) → `CheckoutError` naming the reason. Never delete, never
  clone over.
- Missing or empty destination → the existing clone path, byte-for-byte.

## M3 — hooks neutralised

`_git` invokes `git -c core.hooksPath=/dev/null …` and sets `GIT_NO_LAZY_FETCH=1`, so a reused or
operator-supplied checkout cannot run a repo-local hook during checkout/apply outside the sandbox,
and a partial clone cannot lazy-fetch. A planted `post-checkout` hook does not run. Global/system
config isolation stays.

## M5 — tests

`tests/test_repo_materialise.py` (or the nearest test home) with real local git fixtures:
the mirror path with an unreachable canonical URL; no mapping still clones; a missing mirror refuses
without network; the reuse cases; the hooks test; `provision` and `verify_strict` with the mapping
and an unreachable `repo_url`; the committed public manifest's pins hash to
`b885fb84763091db`.

## The reward-path declaration

`src/whetstone/verify/repo.py` is inside the frozen reward path. The change is a **declared
amendment** in `reward-path-amendments.json` (`2026-10-22-public-task-offline`), naming the file and
the reason: provisioning (mirror, reuse, hook neutralisation), not verdict semantics. The freeze
guards are not edited; the declaration is the only path through them.

## Non-goals

- No verdict, gate, corpus or held-out change.
- No night run; no base change.
- No machine git config; no weakening of `_git`'s isolation.
