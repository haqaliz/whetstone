# Understanding — public-task-offline

**Unit:** `chore/public-task-offline/aliz` · **Written:** 2026-10-21 · **Source:** the inline brief
in `docs/planning/_card/issue.md`.

## What the two lost nights actually show

`torch-mps-night-001` and `torch-mps-night-002` each drew all 832 rollouts and then refused:

```
the control arm proved nothing about the harness ... none of its 1 tasks reached INTACT
```

`pallets__flask-4045` was `SKIPPED` in all 16 draws:

```
CheckoutError: could not clone 'https://github.com/pallets/flask.git':
fatal: unable to access ... Could not resolve host: github.com
```

The public task is processed **last** (sources outer, tasks inner: `draws.py:159-161`), so the
failure lands at the end of a 5–6 h night. The Mac was not held awake; the short probe cloned the
same task fine. `_select` is right to refuse; the cause is a network dependency at the end of a
long run, not a fact about the 7B.

## The isolation that must stay

`verify/repo.py:_git` (`:155-185`) sets `GIT_CONFIG_GLOBAL=/dev/null` and
`GIT_CONFIG_SYSTEM=/dev/null` so no machine config can change what gets verified — signing, hooks
paths, filters. A global git `insteadOf` was deliberately ignored by it. **That isolation is
correct and is not weakened.** Any mirror must be an **explicit harness input**, not ambient git
config.

## The correction the dig forced

A **digest-dir pre-warm alone is insufficient.** The public task's checkout appears in four
different places:

| Consumer | Destination | Clone? |
|---|---|---|
| `provision` | `<workspace>/environments/<digest>/checkout` (`scoring.py:237-238`) | yes, but this is the digest dir an operator can pre-populate |
| `verify_strict` (the control arm) | `<sandbox_root>/<run_id>/repo` (`strict.py:147-152`) | **fresh every call** |
| `verify_weak` | `<sandbox_root>/<run_id>/repo` (`weak.py:95-100`) | fresh |
| `oracle_sources` | `tempfile.mkdtemp()/checkout` (`sources.py:465-469`) | fresh |

So copying the probe's `environments/b885fb84763091db` into the night workspace fixes only the
**provisioning** step. The control arm and the oracle still clone into fresh directories, and an
unreachable `repo_url` still makes them `UNVERIFIED`/`NO_ORACLE`. **The fix has to sit at the
`materialise` boundary, where every one of those callers meets it.**

## The fix

1. **An explicit local mirror mapping, read by `materialise`.**
   `WHETSTONE_REPO_MIRRORS` is a JSON object mapping the canonical URL to a local bare repo
   (`{"https://github.com/pallets/flask.git": "/…/runs/flask-mirror.git"}`), exported by the
   operator for the run. `materialise` clones from the mirror path when the task's `repo_url` has
   an entry; the canonical `repo_url` stays in the task manifest. A missing or invalid mirror is a
   named `CheckoutError`, **never** a silent network fallback, so a run that claims to be offline
   cannot quietly reach GitHub.
   - The mapping is an operator input to the harness, not `~/.gitconfig`: the `_git` config
     isolation is untouched. The checkout is still detached at `task.base_commit`, and a mirror
     that lacks that commit fails by name.
2. **`materialise` reuses a pre-provisioned checkout.** It currently clones unconditionally, so a
   populated workspace (the digest pre-warm, or a killed run's workspace) fails with
   `destination path already exists`. It should reuse a **clean** checkout at `base_commit` with no
   clone; move a clean checkout at another commit when the object is present locally; and refuse by
   name otherwise (wrong commit and object absent, dirty tree, populated non-git directory).
   Never delete, never clone over.
3. **The sheet pre-warms and `caffeinate`s.** The probe's flask digest dir is copied into the night
   workspace (the `provision` half is then offline); the night/probe commands are wrapped in
   `caffeinate -dimsu`, so the machine cannot sleep and drop the network. The guard pins both.
   The venv build still uses the `uv` cache; `UV_OFFLINE=1` can make a cold cache fail loudly
   instead of reaching an index.

## Contradictions surfaced — flag, do not paper over

**1. "The workspace must be empty" vs the pre-warm.** The Torch/MPS sheet says the night workspace
must not exist or must be empty (`runbook.md:89-91`). The pre-warm makes it non-empty (only the
digest dir). The sheet must say the workspace is empty **except** the pre-warmed public digest dir;
the guard pins that. The private tasks clone local donors and need no pre-warm.

**2. The digest key does not include the repo or commit** (`scoring.py:340,357`: python + pins
only). The pre-warm is addressed by the literal digest `b885fb84763091db` for the committed
manifest; a manifest pin change would change the digest and silently re-clone. A test cross-pins
the manifest's pins to the digest, and the sheet uses the literal under `$REPO/runs/<torch-probe-run-id>-workspace`
so it cannot drift silently.

**3. A reused checkout is a new trust surface.** `_git` nulls global/system config but not
repo-local hooks; a reused or pre-warmed checkout could carry a `post-checkout` hook. The dig
flags it. The unit adds `-c core.hooksPath=/dev/null` to `_git`'s invocations (or to the reuse
checkout) and a test that a planted hook does not run. This keeps the reuse from weakening the
isolation the verifier exists to hold.

**4. The network exception.** `ROADMAP.md` § 8 says the public fetch is the one declared network
exception and the draw is offline. A verifier-time clone is that exception leaking into the run.
The mirror makes the run genuinely offline for source A.

## Core-loop placement

Element **② the nightly loop**'s operator reliability and the **verifier's provisioning** boundary,
not its reward path. `UNVERIFIED` stays `UNVERIFIED`; nothing is promoted or loosened.

## Open questions for the PRD / review gate

1. **The mirror format.** A JSON object in `WHETSTONE_REPO_MIRRORS` (recommended: explicit,
   testable, no new CLI) vs a `--repo-mirror` flag on `run`/`gate` (more plumbing). The env is
   inherited by the verifier subprocesses; the flag would need threading.
2. **The reuse branch.** Include it (recommended: it makes the pre-warm and a killed run's
   workspace actually work, and fixes the `destination path already exists` failure) or use the
   mirror mapping alone (which covers every clone site but not the venv/digest pre-warm).
3. **The hooks hardening.** Include `core.hooksPath=/dev/null` in `_git` (recommended) or document
   the reused-checkout trust boundary and leave `_git` untouched.
