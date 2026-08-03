# Aspect spec — `source-b-miner`

**Feature:** `p1-task-ingestion` · **PRD:** `../prd.md` · **Sequence:** after `task-format`.

## Problem slice and user outcome

Source B is the **pre-registered headline** (`docs/ROADMAP.md:36`, § 6): tasks mined from the
user's own repos, uncontaminated and never leaving the box. Nothing mines them today.

**Outcome:** point `whetstone` at a local repo and get verified-live tasks out, with the
evidence committed and the code not.

## In scope

1. **Candidate selection** — `--no-merges` commits touching ≥1 test `.py` that is **MODIFIED**
   (never merely added — PRD D2) and ≥1 non-test `.py`. `base_commit` is the candidate's
   **parent**.
2. **Node-id derivation** — run the suite twice under junit XML (at parent+held-tests, then
   after the gold patch), diff outcomes. `fail_to_pass` = ids that flip `failed`→`passed`;
   `pass_to_pass` = ids `passed` in both. Ids are minted through `strict.py`'s own
   `_read_report`/`_node_id` (PRD M4), never hand-constructed and never via `--collect-only`.
3. **Flake rejection** — a third run; non-deterministic ids are discarded, not recorded.
4. **The cheat-10 structural floor (PRD D4/M5)** — `test_blobs` holds the held test files plus
   **every `conftest.py` from repo root down to each held test's directory**.
5. **The over-declaration guard** — no held path may be one the gold patch touches. (If it is,
   `strict.py:162-163`'s restore silently overwrites the fix and the task becomes permanently
   unpassable, reported as an ordinary FAIL.)
6. **Liveness + the committed ledger (PRD § 3.1, M8)** — every minted task proved FAIL with an
   empty patch and PASS with the gold patch, `executed == declared`, zero skips. Recorded in
   `tasks/local-ledger.json`: task id, **manifest hash**, both verdicts, tool/interpreter
   versions, date. Hashes and verdicts only — never contents.
7. **Committed recipes** — `tasks/recipes/<donor>.json`: donor path, filters, tool versions,
   mining date. The recipe is committed; the mined manifests go to gitignored `/tasks/local/`.
8. **Donors and target (PRD D3/D5)** — donor A, the sibling project, donor C, whetstone; **60–80 tasks
   stratified across all four**. `donor C` is per-service and is done LAST (PRD N2).

## Out of scope

Source A entirely. Any model invocation. Commits that only ADD a test file (PRD D2 — that
needs a reward-path change, deliberately deferred).

## Acceptance criteria (test-first)

1. **No network on this path** — a test asserts the source-B miner makes zero network calls
   (AST guard on the module plus a runtime seam), lifting the sibling project's
   `tests/test_eval_pool_fetch.py:323-400` technique.
2. Mining a **synthetic donor repo** (built with the existing `tests/fixtures/repos/`
   machinery, extended to a two-commit history) yields a manifest that `load_task` accepts and
   STRICT verifies.
3. **Liveness, per minted task:** empty patch → STRICT FAIL; gold patch → STRICT PASS with
   `executed == declared` and **zero skips**.
4. **Adversarial — the vacuous-task control:** a deliberately vacuous task (one that passes
   with no patch) **fails the build**. Watched failing first — this is the control that stops
   ingestion paying reward for nothing.
5. **Adversarial — cheat 10 differential:** a task whose `test_blobs` omit a `conftest.py` on
   the path to a held test is **rejected at ingestion by M5's rule**, and the assertion names
   *that* rule as the rejecter. The same task hand-authored without M5 is accepted by both
   verifiers — proving the differential is real rather than an incidental failure.
6. **Adversarial — over-declaration:** a candidate whose gold patch touches a would-be-held
   path is rejected at mint time rather than minted into a permanently-unpassable task.
7. A **parametrised** test yields a fully-parametrised node id end-to-end (`strict.py:282-309`
   compares by exact set equality plus a count, so a bare id fails).
8. The ledger is committed, contains one entry per minted task, and carries **no file
   contents** — asserted structurally.
9. `uv run ruff check .`, `uv run mypy src/`, `uv run pytest` exit 0.

## Dependencies and sequencing

Blocked by `task-format` (needs `environment` and the exposed node-id reader). Independent of
`source-a-filter`.

## Risks specific to this aspect

- **Cost:** ~2–3 full suite runs per candidate; 60–80 tasks ≈ 120–240 runs. One-time, offline,
  parallelisable — hours of wall-clock, not minutes. Budget it, don't discover it.
- **Real-donor mining is excluded from CI** (PRD § 8.2): reprovisioning donors per run makes a
  red build ambiguous between "the task regressed" and "the environment flaked". CI covers the
  synthetic donor; real mining is local, with the ledger as its committed evidence.
- **`donor C` has no root `pyproject.toml`** — per-service targets, unbounded by the estimate.
  Ship the three lockfile donors first.
