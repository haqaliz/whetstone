# Spec — `night-evidence`

**Unit:** `morning-report` · **Aspect 1 of 4** · PRD: `docs/planning/morning-report/prd.md`

## Problem slice

The morning report renders a night's ledger, but **there is no typed reader for one.**
`ledger.read` (`src/whetstone/loop/ledger.py:211-224`) checks the schema string and returns the
raw `Mapping`. Every field the report needs is one an optimistic parse would default, and a
defaulted count records nothing while succeeding — the failure `LEDGER_SCHEMA`'s own docstring
names (`ledger.py:44-47`) and the one `read_promotion_record` (`gate.py:902-917`) already
refuses on the gate side.

And **which night is "last night" has no answer on disk.** The run id is operator-declared
(`cli.py:328`) and `recorded_on` is *"an input, never the clock"* (`ledger.py:151`), so there is
no timestamp anywhere in the tree. This aspect fixes the rule and makes every way of getting it
wrong a named refusal.

**User outcome:** the operator names no run and gets last night's — or gets told, precisely, why
the question has no single answer today.

## In scope

1. **`read_ledger(path) -> LedgerDocument`** — a fail-closed typed reader beside `ledger.read`
   (reused by identity for the schema check, never re-implemented). Field by field, in the
   `read_promotion_record` shape: every field the report renders is present, of the declared
   type, and never defaulted. Ints are ints and never `bool` (a subclass). Unknown top-level
   fields are refused. Each refusal names the file and the offending field.
2. **`LedgerDocument`** — a frozen dataclass carrying only what the report renders: `run_id`,
   `recorded_on`, `run_seed`, `draws`, `model` (repo_id, revision), the generation contract's
   published fields, `task_set` counts, `tool_versions`, the dataset block
   (`digest`/`denominator`/`unverified`/`examples` count), `valid_split`, `checkpoint_digest`,
   `checkpoint_absent`, and the held-out record when present.
3. **`resolve_last_night(runs_root) -> LedgerDocument`** — the stated rule: read every run
   directory's ledger through the reader above, take the **greatest declared `recorded_on`**.
4. **The refusals, each by name:**
   - `NoRuns` — the runs root holds no run directory. Never an empty morning.
   - `AmbiguousNight` — two or more nights declare the same greatest `recorded_on`. Names the
     tied run ids and points at `--run`. **The refusal is the feature**, not a fallback.
   - `LedgerUnreadable` (reused **by identity** from `ledger.py:59`) — a run directory with no
     ledger, or one the reader rejects, is refused **during the scan and never skipped**.
     Skipping makes a corrupt or killed night invisible to the one command whose job is to say
     what happened last night.
   - `RunIdentityMismatch`-shaped refusal for an explicitly named `--run` whose ledger declares a
     different `run_id` than its directory name.

## Out of scope

- Reading the dataset document's examples, the per-draw journals, or any transcript — the ledger
  carries the dataset's counts and digest, which is everything the report renders.
- The promotion record (aspect 2 composes `read_promotion_record` by identity).
- Any rendering (aspect 2), any path guarding (aspect 3), any CLI (aspect 4).
- Modifying `ledger.py`'s writer or its schema. **The ledger is not made self-sealing here** —
  the PRD states the sealing boundary in the report's own text instead (PRD risk 6).

## Acceptance criteria

Each is a failing test first.

1. A well-formed ledger reads into a `LedgerDocument` with every field carried verbatim.
2. **Every** field's absence is refused by name — asserted by a loop over the document's own
   field list, so a field added later without a refusal fails the suite rather than defaulting.
3. A `weaker_wins`-style integer field given `true` is refused (bool is an int subclass).
4. An unknown top-level field is refused, naming it.
5. A ledger declaring a foreign schema is refused through `ledger.read`'s own check, reused by
   identity (asserted `is`).
6. `resolve_last_night` over three nights returns the greatest `recorded_on` — **and the fixture
   is written so that directory order, alphabetical run-id order, and mtime order each disagree
   with the answer.** Without that, the test passes under an mtime implementation and proves
   nothing.
7. Two nights tied on the greatest `recorded_on` raise `AmbiguousNight`, naming both run ids and
   `--run`. **Watched failing against a credulous resolver that breaks the tie** (by sort order),
   which is the implementation this would decay into.
8. An empty runs root raises `NoRuns`.
9. A run directory whose ledger is missing, truncated, or schema-foreign raises during the scan —
   proven by planting one *beside* two healthy nights and asserting the scan refuses rather than
   returning the healthy pair.
10. A `--run`-named directory whose ledger's `run_id` disagrees with the directory name is
    refused, naming both.
11. The reader and resolver import no inference library; the aspect's path walks clean under the
    existing AST guard.

## Dependencies & sequencing

First aspect; depends only on what exists. Blocks aspects 2 and 4.

## Open questions / risks

- **The tie is not theoretical.** Two nights declared on one date is an ordinary operator
  action, so `AmbiguousNight` will fire in real use. The refusal must name `--run` in the message
  or the operator is stuck holding a correct refusal with no next step.
- `recorded_on` is a free string, not a validated date. Comparing two of them lexicographically
  is correct **only** for ISO-8601. The reader validates the shape and refuses anything else,
  rather than comparing strings of unknown format and calling the greater one "last night".
