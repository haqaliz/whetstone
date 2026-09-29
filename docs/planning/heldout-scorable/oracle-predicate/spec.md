# Spec — oracle-predicate (aspect 1 of heldout-scorable)

**Aspect dir:** `docs/planning/heldout-scorable/oracle-predicate/` · **Written:** 2026-09-27.
**Source:** `docs/planning/heldout-scorable/prd.md` (must-haves 1, 9; technical
considerations). **Core loop element:** ③ gate (selection input), oracle contract.

## Problem slice

The oracle budget rule lives inside `_read` (`src/whetstone/bakeoff/sources.py:443-491`),
reachable only after a full `materialise` checkout inside `oracle_sources`. The held-out
derivation (aspect 2) needs a **named, structural, permanent** predicate: does this task's
oracle fit the declared budget? It must classify on immutable git objects only (path set at
the mined commit + `base_commit` tree) — never on machine state — so that an exclusion from
the held-out draw can never be caused by a transient condition. Today no such predicate
exists; the budget rule has exactly one statement and it is not exposed.

## In scope

- `OracleFit` — a result type in the `Changed`/`Sources` vocabulary (`fits: bool`,
  `reason: str`), frozen dataclass.
- `oracle_fittable(task, *, budget=ORACLE_BUDGET_CHARS) -> OracleFit` in `sources.py`:
  structural classification, no checkout, no network.
- The **budget rule shared by identity**: the per-path byte pre-check and the cumulative
  char-total check become one function used by `_read` and `oracle_fittable` (asserted `is`).
- The **path-set derivation shared by identity**: the donor route's path computation
  (touched paths → non-test filter → vouched check) becomes one structural function used by
  `_from_donor` and `oracle_fittable`; **machine-state failures (git failures, unreadable
  donor) propagate as exceptions** — the caller refuses by name, never classifies.
- Tests: unit tests on synthetic fixture repos (`fixtures.repos`, `fixtures.repos.mined`
  patterns), plus the machine-corpus differential (CI-skip pattern of
  `tests/loop/test_heldout_document.py`).

## Out of scope

`heldout.py` and the held-out document (aspect 2); the gate; the budget value (80,000 stays);
the re-mint swap (aspect 3); the amendment (aspect 4); the runbook (aspect 5). `_read`'s
*behavior* and `_from_donor`'s *behavior* must be byte-identical — only the internals are
shared with the new predicate.

## Acceptance criteria (testable, written first)

- **AC1.** `oracle_fittable(task)` returns `OracleFit(fits=True, reason="")` for a task
  whose oracle `oracle_sources` builds (synthetic fixture).
- **AC2.** The budget rule is one function: `_read` and `oracle_fittable` reach the same
  object (asserted `is`), and a test changes the budget through the predicate's parameter
  and observes the same boundary `_read` enforces (cumulative `> budget` refuses; `==`
  passes).
- **AC3.** The path-set derivation is one function: `_from_donor` and `oracle_fittable`
  reach the same object (asserted `is`).
- **AC4.** Structural classes return `fits=False` with a reason naming the class: no
  non-test paths; vouched/test_blobs collision; per-file byte pre-check
  (`> budget * _MAX_BYTES_PER_CHARACTER`); cumulative total over budget; nothing readable
  (every path missing at `base_commit` or non-UTF-8).
- **AC5.** Machine state never classifies: a task whose donor cannot be read raises (a
  `GitFailed`-family exception), it does not return `fits=False`; the caller-facing contract
  is documented on `oracle_fittable`.
- **AC6.** Determinism and locality: no checkout, no network, no clock; deriving the same
  task twice gives identical results; the predicate is a pure function of the manifest +
  immutable git objects.
- **AC7.** The budget parameter defaults to `ORACLE_BUDGET_CHARS` and the caller may pass a
  different budget; the boundary follows the parameter.
- **AC8.** No existing record changes shape: `Changed` and `Sources` are untouched, every
  existing refusal reason string is unchanged, and the full `tests/bakeoff/` suite stays
  green.
- **AC9.** Machine-corpus differential (CI-skip, like `test_heldout_document`), per
  direction, reason classes never pooled: for every corpus task with a readable donor —
  predicate-false ⟹ `oracle_sources` refuses; predicate-true ⟹ `oracle_sources` builds
  (`files is not None`).

## Dependencies & sequencing

Root aspect — nothing depends on it; aspects 2-5 depend on it. Do not touch `heldout.py`.

## Open questions / risks

- Blob reads via `git cat-file` (`-s` for the byte pre-check, blob read for the char count)
  — identical bytes to a materialised checkout at `base_commit`, no checkout needed. If
  `git cat-file` proves awkward in tests, materialise once per task instead; the differential
  test is the net either way.
- The exception line: `_touched_paths`'s `GitFailed` currently becomes a `Changed` refusal
  inside `_from_donor`; the shared structural function raises, and `_from_donor` keeps its
  catch — so the bakeoff's behavior is unchanged while the predicate sees exceptions. This
  is the one place where "shared by identity" and "different failure semantics" meet; the
  catch belongs in `_from_donor`, never in the shared function.