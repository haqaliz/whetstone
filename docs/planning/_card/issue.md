# chore public-task-offline — a long night must not end on the public task's network

**Source:** inline brief, from the two lost Torch/MPS nights (`torch-mps-night-001`,
`torch-mps-night-002`, both `EXIT 3` `UNVERIFIED`). No GitHub issue exists for this slug. Branch
`chore/public-task-offline/aliz`, worktree `.claude/worktrees/chore-public-task-offline`.

## The evidence, from two runs

Both nights drew all 832 rollouts and then refused:

```
the control arm proved nothing about the harness ... none of its 1 tasks reached INTACT
```

The one public task, `pallets__flask-4045`, was `SKIPPED` in all 16 draws:

```
the environment for task 'pallets__flask-4045' could not be built:
CheckoutError: could not clone 'https://github.com/pallets/flask.git':
fatal: unable to access ... Could not resolve host: github.com
```

The public task is processed **last** (the loop is task-major), so the failure lands at the end of a
5–6 h night and takes the whole run with it. `_select` is right to refuse: a run of zeroes against
an unproven harness is not a result about any base. But the cause is a **network dependency at the
end of a long run**, not a fact about the 7B — and it has now cost two nights.

The short probe cloned the same task successfully; the long nights failed only at the end. The Mac
was not held awake (`caffeinate` was missing), and a global git `insteadOf` mirror was deliberately
ignored: `verify/repo.py:_git` sets `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_SYSTEM=/dev/null`
so no machine config can change what gets verified. That isolation is correct and stays.

## The fix

1. **Reuse a pre-provisioned checkout.** `materialise(task, destination)` currently clones
   unconditionally and raises `CheckoutError: destination path already exists` if the destination is
   populated — the same failure the worktrees skill warns about on a reused workspace. It should
   treat an existing checkout at `task.base_commit` as provisioned and skip the clone, with no
   network. An existing checkout at another commit is moved to the base commit when the object is
   present locally; when it is not, it is a named `CheckoutError`, never a silent wrong commit.
2. **The operator pre-warms the public task.** The probe's workspace already holds the flask
   checkout and venv under its digest directory. The sheet gains a step that copies that digest
   directory into the night workspace before the night, so the one network task is provisioned from
   a proven local copy. The private tasks clone local donor repos and never needed the network.
3. **`caffeinate` the night.** The night command is wrapped in `caffeinate -dimsu` (macOS), so the
   machine cannot sleep through a long run. The sheet and its guard pin it.

Nothing here touches the reward: the strict verifier, the sandbox, the task contract and the
held-out document are unchanged. The `_git` config isolation is not weakened.

## Acceptance criteria (written first)

1. `materialise` on a destination that already holds `base_commit` succeeds **without invoking
   `git clone` or any network operation**; a test with an unreachable `repo_url` proves it.
2. A destination at another commit with the base object present is checked out to the base commit;
   with the object absent, the call raises `CheckoutError` naming the commit (no silent wrong
   commit).
3. A missing destination still clones exactly as today (existing tests unchanged).
4. A `provision`/`Interpreters` test proves a pre-populated digest directory is reused, and the
   public task's control arm can run from it with `repo_url` unreachable.
5. The Torch/MPS night sheet wraps the command in `caffeinate -dimsu`, and
   `tests/test_torch_mps_runbook_guards.py` pins it.
6. `src/whetstone/verify/`'s reward semantics, `tasks/`, the held-out document and the gate rule
   are unchanged apart from `materialise`'s reuse branch; the adversarial and reward-path suites
   stay green.

## Core-loop placement

Element **② the nightly loop**'s operator reliability, and the **verifier's provisioning** boundary
(not its reward path). `UNVERIFIED` remains `UNVERIFIED`; nothing is promoted.

## Roadmap grounding

- `docs/ROADMAP.md` § 8: the public SWE-bench fetch is the declared network exception; the draw is
  meant to be offline. A checkout that needs the network at verification time is the same exception
  leaking into the run.
- `docs/planning/torch-mps-series/`: the series and its sheet; the two lost nights are its first
  operator runs.
- `src/whetstone/verify/repo.py:57-90` (`materialise`), `:155-200` (`_git`'s config isolation);
  `src/whetstone/bakeoff/scoring.py:296-362` (`Interpreters`); the worktrees skill's
  "destination path already exists" warning.
