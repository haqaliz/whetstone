# Spec — sheet-and-writeup

**Aspect:** `sheet-and-writeup` · **Unit:** `public-task-offline` · **PRD:** `../prd.md` M4, M6,
S1 · **Date:** 2026-10-21

## Purpose

Make the Torch/MPS night sheet run the public task offline and keep the machine awake, and write
the unit up.

## The sheet

`docs/planning/torch-mps-series/night-door/runbook.md` gains, before the probe:

1. **A mirror prep step** (the one network use, human-run): `git clone --mirror
   https://github.com/pallets/flask.git "$REPO/runs/flask-mirror.git"`, refreshed if present.
2. **The mirror export**:
   `export WHETSTONE_REPO_MIRRORS=$(printf '{"https://github.com/pallets/flask.git":"%s/runs/flask-mirror.git"}' "$REPO")`.
3. **`export UV_OFFLINE=1`** (a cold cache fails loudly instead of reaching an index).
4. **The pre-warm** into the night workspace:
   `mkdir -p "$REPO/runs/<torch-night-run-id>-workspace/environments"; cp -a
   "$REPO/runs/<torch-probe-run-id>-workspace/environments/b885fb84763091db"
   "$REPO/runs/<torch-night-run-id>-workspace/environments/"`. The literal digest is the
   `Interpreters` key for the committed public manifest; a test cross-pins it.
5. **`caffeinate -dimsu`** as the outer prefix on the probe and night command blocks.
6. The workspace-emptiness sentence becomes "empty except the pre-warmed public digest dir"; the
   private tasks clone local donors and need no pre-warm.

The mirror's content must include the task's `base_commit`; a stale mirror fails the detached
checkout by name.

## The guard

`tests/test_torch_mps_runbook_guards.py` gains, in the existing runtime/environment test's shape:
`CAFFEINATE = "caffeinate -dimsu"`; the probe and night blocks start with
`caffeinate -dimsu uv run --extra torch whetstone run --night`; the sheet exports
`WHETSTONE_REPO_MIRRORS` and `UV_OFFLINE`; the pre-warm copies the literal
`b885fb84763091db` from a `<torch-probe-run-id>` workspace into a `<torch-night-run-id>` workspace;
the workspace-emptiness wording includes the pre-warm exception. No `probe-001`/`night-001` token
appears. The MLX sheet and its guard are untouched.

## The write-up

`docs/STATUS.md` top entry + `CHANGELOG.md` `Unreleased` entry: the mirror/reuse/hooks and the
sheet's pre-warm/caffeinate landed; **no night was run**; the two lost nights are the motivation,
not a base result; **no number** is claimed. A `tests/test_docs.py` write-up guard in the k16 shape.

## Non-goals

- No night run; no base change; no reward/gate/corpus/held-out change.
- No `reports/` home.
