# Spec — `cli-door`

**Unit:** `morning-report` · **Aspect 4 of 4** · PRD: `docs/planning/morning-report/prd.md`

## Problem slice

`docs/ROADMAP.md:663` names the command: `whetstone report --last-night`. Adding it makes this
the **fourth** documented function-local edge from a guarded root into the exempt `loop` package
— the guard that keeps `whetstone verify` from ever importing an inference library, even
transitively. The edge is cheap to add and must be impossible to add silently.

**User outcome:** one command, in the morning, that renders the proof.

## In scope

1. **The `report` subcommand** in `src/whetstone/cli.py`, on the `run_check_leakage_cli`
   template (`cli.py:815-844`): a **function-local** import of the loop module's `REFUSALS`,
   `disclosure` and entry point; refusals to `USAGE_ERROR` on stderr; **no fifth exit code**.
2. **Flags:** `--last-night` (resolve by the stated rule), `--run <dir>` (name one explicitly),
   `--runs <root>` (where to scan, default `runs/`), `--record <path>` (optional gate evidence),
   `--out <dir>`, `--verify <dir>`. `--last-night` and `--run` are mutually exclusive and naming
   neither is a usage error. **No `--recorded-on`**: the report carries the night's own declared
   date and stamps none of its own, which is what makes byte-identity a property of the design.
3. **Exit codes, the existing four-code contract:** rendered → 0; a `--verify` mismatch → 1 (a
   report that does not match its evidence is a failure, not a mistyped command); a named refusal
   → 2. There is no `UNVERIFIED` exit — this command reads documents and renders, so it either
   answers or refuses. (`check-leakage`'s own argument, `cli.py:828-832`.)
4. **The partition guard moves, in both halves:** `_DOCUMENTED_EDGES`
   (`tests/test_reward_path_scope_is_partitioned.py:152-158`) gains the fourth entry, and the
   `loop` exemption's prose — which today reads *"exactly THREE documented edges"* (`:128`) —
   moves with it. The reason and its proof must not drift apart.
5. **The two stale claims corrected** (user-confirmed, PRD must-have 11):
   - `cli.py:1-13` — says "four now do" and "All four subcommands", omits `check-leakage`, and
     ends *"There is still no report, so there is still no stub for it"*, which this unit
     falsifies.
   - `README.md:229-230` — lists the never-regress promotion gate and the held-out split as
     ❌ Not built (both shipped in P3), and says *"No tags, no PyPI package, no version"* when
     v0.3.0–v0.10.0 are tagged and published. This is the failure `CLAUDE.md` records about
     itself ("it had been false since v0.3.0"), live in the repository's front door.
6. **`CLAUDE.md`'s status block and `docs/ROADMAP.md` § 12** record the capability in the same
   commit that lands it — the standing rule that the claim and the code arrive together.

## Out of scope

- An operator runbook and its guard. Decided at the review gate: this is one invocation, no GPU
  spend, no ordering hazard, so a sheet would restate `--help` and a guard would pin a sheet
  nobody needs. Every prior runbook scripted a multi-step chain or a spend; this scripts neither.
- Any `PREREGISTRATION.md` § 10 amendment — § 10 discloses published *series*, and this unit
  publishes none.
- Any move of the one-home guard (aspect 3 asserts it stays put).

## Acceptance criteria

1. `whetstone report --last-night --runs <root> --out <dir>` renders and exits 0, printing the
   artifact paths.
2. `--last-night` with `--run` is a usage error; naming neither is a usage error.
3. Each named refusal from aspects 1–3 surfaces on stderr and exits 2 — asserted per refusal
   class, so a new refusal that escapes as a traceback fails the suite.
4. `--verify` on an untouched pair exits 0; on a one-byte edit exits **1**, not 2.
5. **The partition guard proves exactly four edges** — watched failing in both halves before the
   constant moves, and proven able to fail again afterwards against a planted **fifth** edge and
   against the fourth moved to **module scope**.
6. The `loop` exemption's prose states four edges and names `whetstone.loop.morning`; asserted,
   so the reason cannot outlive its constant.
7. `whetstone verify` still imports no inference library, transitively — the existing AST guard
   and scope guard both green.
8. `whetstone --help` lists `report`, and `cli.py`'s module docstring enumerates every
   subcommand that exists — asserted against the parser's own subcommand names, so the docstring
   cannot go stale again the way it just did.
9. `README.md`'s status table contains no ❌ row for the promotion gate or the held-out split,
   and no claim that nothing is released — asserted against `git tag`, so the row cannot re-stale
   without the suite noticing.

## Dependencies & sequencing

Last. Depends on aspects 1, 2 and 3.

## Open questions / risks

- Criterion 9 pins a document against `git tag`, which is unusual here but is exactly the check
  that would have caught the README's live falsehood. If it proves brittle in CI (a shallow
  clone has no tags), it degrades to skipping with the reason named — never to passing.
