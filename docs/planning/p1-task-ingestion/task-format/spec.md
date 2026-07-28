# Aspect spec — `task-format`

**Feature:** `p1-task-ingestion` · **PRD:** `../prd.md` · **Sequence:** first; blocks both other aspects.

## Problem slice and user outcome

The shipped `Task` contract cannot express a real task. It carries no environment, so a verdict
depends on whatever the dependency resolver served that morning — demonstrated on
`pallets__flask-5063`, where an unbounded `click>=8.0` resolved to today's `click 8.4.2` and
produced a **false FAIL** on 4 `pass_to_pass` tests. And `strict.py:179` hardcodes
`sys.executable`, so every task must run on the verifier's own 3.12 interpreter.

**Outcome:** a task on disk fully determines its own verdict — same manifest, same verdict,
on any machine, on any day.

## In scope

1. **The `environment` field** on the manifest and the `Task` dataclass:
   `{python: "3.12", pins: ["click==8.1.3", ...]}`. `pins` must be exact `==`.
2. **The loader change** — `_FIELDS`, the dataclass, the constructor call, and the fail-closed
   validation for the new field, as ONE atomic change (it transiently reds ~19 tests in
   `tests/test_task_contract.py` plus every fixture-built test via
   `tests/fixtures/repos/__init__.py:172-184`).
3. **Path normalisation** of `test_blobs` keys to git's canonical spelling (closes C3 —
   `./tests/x.py` currently loads but drops out of the patch-rejection set at
   `strict.py:423-434`).
4. **Per-task interpreter in `strict.py`**, replacing the hardcoded `sys.executable` (`:179`).
   Defaults to current behaviour so no existing test changes meaning.
5. **Expose the node-id reader** — `_read_report` / `_node_id` become importable so ingestion
   mints ids through the same code the verifier compares against (PRD M4).
6. **The `tasks/` directory layout** (PRD § 5.1), including `.gitignore` verification that
   `/tasks/local/` is ignored and `/tasks/` is not.
7. **`whetstone verify` accepts a directory** (PRD S1), reducing worst-status-wins via the
   existing `verdict.reduce`.

## Out of scope

Any mining or fetching (aspects 2 and 3). The liveness harness and the ledger (aspect 2 owns
them). The 4-gate filter (aspect 3). Relaxing `strict.py:131-140`.

## Acceptance criteria (test-first — written and watched failing before the code)

1. A manifest **missing** `environment` is rejected by name; `environment.pins` containing a
   non-`==` specifier (`click>=8.0`, `click~=8.1`) is rejected by name; a non-string entry in
   `pins` is rejected. Fail-closed, matching `task.py:89-101`'s contract.
2. A task round-trips through `load_task` with `test_blobs` **byte-identical**, including a
   deliberately non-UTF-8 blob (extends `tests/test_task_contract.py:84-96`).
3. **Adversarial, HARD (PRD criterion 7, no escape hatch):** a task resolved WITHOUT its pins
   reaches a **different verdict** than the same task WITH them. Determinism comes from a
   **recorded local package index** holding two pinned states of one dependency — never the
   live network — so the test is reproducible in CI and does not itself depend on what PyPI
   serves. This is the one new reward-corrupting hole the dig found; it may not be downgraded.
4. A `test_blobs` key spelled `./tests/x.py` is either normalised at load to `tests/x.py` or
   rejected — and a patch touching that file is **refused by STRICT** either way. Watched
   failing against today's behaviour first, so the hole is demonstrated before it is closed.
5. `strict.py` runs a task under a **nominated interpreter**; with none nominated, behaviour is
   byte-identical to today (assert against an existing fixture task's verdict).
6. The provenance census still admits exactly one `Task` producer
   (`tests/test_task_contract.py:232-236`), and any directory loader is sited **outside**
   `whetstone/verify/task.py`.
7. `whetstone verify --task <dir>` reduces N tasks worst-status-wins and emits **no fifth exit
   code** — `tests/test_verify_cli.py:220-224` stays green.
8. `uv run ruff check .`, `uv run mypy src/`, `uv run pytest` all exit 0.

## Dependencies and sequencing

None inbound. Blocks `source-b-miner` and `source-a-filter`, which are independent of each other.

## Risks specific to this aspect

- **The atomic breaking change.** Splitting it across tasks leaves the suite red between
  commits. Sequence as one task.
- **Naming trap (C7):** a module named `models.py` under a guarded root is flagged by the
  first-party inference-name ban (`tests/test_no_inference_on_reward_path.py:119-121`). Use
  `manifest.py`.
- **Criterion 3 is the hardest test in the aspect.** Building the recorded local index is real
  work; it is also the only way to prove the closure rather than assert it.
