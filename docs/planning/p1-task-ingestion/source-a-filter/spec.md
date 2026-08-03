# Aspect spec — `source-a-filter`

**Feature:** `p1-task-ingestion` · **PRD:** `../prd.md` · **Sequence:** after `task-format`.

## Problem slice and user outcome

Source A (SWE-bench-Lite) is the **only externally checkable half** of the eventual number. It
is also far narrower than the roadmap assumed: a **24-instance ceiling out of 300, with 1
proven** (PRD § 2). The durable deliverable is therefore not the instances — it is the
**filter that proves eligibility per instance instead of assuming it**, plus the ledger of what
it rejected and why.

**Outcome:** a committed, reproducible public corpus whose every member is proven runnable, and
a published account of everything that was not.

## In scope

1. **The human-run fetch** — one script, network, output committed to `tasks/public/pool.json`
   with a provenance header (dataset, config, split, revision, fetched_at, row count, filters).
   **Tests never fetch.** The network client is importable only inside `main`
   (the sibling project's discipline, `fetch_swebench_pool.py:325-329`). Must pull the columns the sibling project's pool
   omits: `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `environment_setup_commit`.
2. **The seeded stratified draw** — pure and offline, `random.Random(seed)`, **sorted before
   any shuffle**, raise rather than draw short. Lift `eval/instances/selection.py`, replacing
   its `random.sample` branch with shuffle-and-take to remove a cross-version unknown.
3. **The four gates (PRD § 6.2), each PROVING, never assuming:**
   1. **Format** — every declared id parses as a pytest node id (kills django's unittest form
      and sympy's bare names: 64% of Lite).
   2. **Collectability** — every id is collectable **in the real checkout**. Assumption-free,
      and the only reliable detector for the 12 whitespace-truncated parametrised ids.
   3. **Environment** — the pinned env resolves **AND imports** on the nominated interpreter.
      **Install-exit-0 is not evidence** — the same false-green the CI `mlx` step guards
      against.
   4. **Liveness** — the two-run FAIL-then-PASS check with `executed == declared`.
4. **The rejection ledger** — `tasks/public/ineligible.json`, every rejected instance recorded
   **with the gate that rejected it**. Never a silent drop. Publishable and on-thesis.
5. **Manifest emission** for survivors into `tasks/public/instances/<id>.json`, with
   `environment` pins determined per instance.

## Out of scope

Source B. Any non-pytest execution path for django/sympy — that is a **second reward surface**
with its own adversarial-corpus obligation, and nothing in P1 budgets for it. Repairing
SWE-bench's own truncated node ids (recorded ineligible; fixing upstream data is not this
project's job).

## Acceptance criteria (test-first)

1. **The draw is byte-identical** across repeated runs at the same seed, and insensitive to
   input ordering — asserted as a byte comparison of the written file, not an id-set match, so
   header drift cannot slip past (the sibling project's `tests/test_eval_mint_set.py:323-341`).
2. **Tests never fetch** — an AST guard asserts the network client appears only inside `main`,
   plus stdlib-only imports at module scope. Anti-vacuity: the guard must be shown to actually
   observe imports.
3. **Gate 1** rejects a django-form id (`test_x (module.Class)`) and a sympy-form bare name,
   naming the gate.
4. **Gate 2** rejects a truncated parametrised id (unbalanced `[`) **by collection against a
   real checkout**, not by string heuristic.
5. **Gate 3** rejects a pin that installs but **fails to import** — the false-green case,
   fixtured from the measured `pytest==4.6.9` on 3.12 (`No module named 'imp'`). Asserts that
   install-exit-0 alone does not pass the gate.
6. **Gate 4** rejects an instance that does not go FAIL-then-PASS.
7. **Every rejected instance appears in the ledger with its gate**; a test asserts the
   ledger's instance count plus the eligible count equals the input count — **nothing vanishes**.
8. At least one **real** instance (`pallets__flask-5063`, already proven end-to-end in the dig)
   passes all four gates and verifies STRICT PASS. If it is the only one, that is the reported
   number.
9. `uv run ruff check .`, `uv run mypy src/`, `uv run pytest` exit 0.

## Dependencies and sequencing

Blocked by `task-format`. Independent of `source-b-miner`.

## Risks specific to this aspect

- **Sphinx is 14 of the 24 survivors and has never been run at a base commit — UNVERIFIED.**
  Gates 3 and 4 discover it per instance. If sphinx fails wholesale, source A collapses to ~10
  and **that number is reported, not hidden**.
- **Era-pins are not derivable from repo metadata** — they were determined by hand for flask.
  Deriving them per instance may need `environment_setup_commit` plus manual work; if a pin set
  cannot be found, the instance is rejected at gate 3 and ledgered, not guessed at.
- **Real-instance liveness is excluded from CI** (PRD § 8.2) — an ambiguous red is a verdict
  decided by the harness. Committed as a dated artifact; re-verified locally.
