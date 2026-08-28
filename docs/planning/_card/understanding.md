# Understanding — morning-report

## What this work is really asking

The launch path's next unit (`docs/ROADMAP.md:663-666`, § 12, decided 2026-08-26): the
**signed morning report**, `whetstone report --last-night` — pulled out of post-horizon
(`docs/ROADMAP.md:592-593`) and placed ahead of the dashboard because it is the demoable
surface, *"wake up and read the proof"*. It is core-loop element ④ and nothing else: it reads
sealed evidence a night (and, if one ran, a gate) already wrote, and renders it. It scores
nothing, decides nothing, and publishes nothing. The previous unit named it explicitly as its
own successor and put it out of scope
(`docs/planning/honest-number-report/prd.md:80`, `:222`).

## What the dig established (read directly — the four dispatched agents went idle without returning reports, so this was read first-hand)

### The evidence exists and is rich enough

- **`Ledger`** (`src/whetstone/loop/ledger.py:146-197`) carries everything a morning note
  needs: `run_id`, `recorded_on`, `run_seed`, `draws`, `model` (repo_id + revision),
  `contract` (the full frozen `GenerationContract`), `task_set` (private/public counts, roots
  count, dev subset, probe, held-out record), `tool_versions`, `seeds`, `draws_recorded`
  (per-draw harness status + `(denominator, unverified, solved)` per source), `dataset`,
  `valid_split`, `checkpoint_digest | None`, `checkpoint_absent`, `capacity`.
- **`ledger.read`** (`ledger.py:211-224`) is fail-closed on the schema string and returns the
  raw `Mapping`, not a `Ledger` — **there is no typed reader today.** A morning report that
  wants fields needs one, and building it fail-closed is this unit's work.
- **`Dataset`** (`dataset.py:167-192`) carries `examples`, `digest`, `denominator`,
  `unverified`, and `coverage` as the honest complement — the training-set size never travels
  alone.
- **`PromotionRecord`** + **`read_promotion_record`** (`gate.py:852-917`) are already
  fail-closed and complete: both digests, the held-out digest, both `Side`s over both sources
  with six counts each (including `weaker_wins` = `N`), the `decision` block verbatim, and all
  three retry facts. Its home is `runs/promotions/<run-id>.json`.
- **`night.disclosure`** (`night.py:349-382`) and **`gate.disclosure`** (`gate.py:679-703`)
  are the prose-from-data prior art. The morning report is, in substance, a **durable, written,
  re-derivable** version of those two disclosures joined — which is the honest way to describe
  it and keeps it from inventing a vocabulary.

### The one genuinely undecided mechanism: how "last night" resolves

**The run id is operator-declared** (`cli.py:328`, `--run-id`), not generated, and
`recorded_on` is *"an input, never the clock"* (`ledger.py:151`). So there is **no timestamp
in the tree** and no ordering signal except the operator's own declared date. mtime is a
filesystem property, not evidence, and a copied directory re-dates it.

The rule that fits this repository: scan the runs root, read each ledger through the
fail-closed reader, and take the greatest `recorded_on` — **refusing a tie by name** and
telling the operator to say which with an explicit `--run`. That satisfies the acceptance
criterion ("resolves last night by a **stated rule**, refusing ambiguity rather than
guessing") without ever consulting the clock or the filesystem.

### The home is already decided, and the one-home guard already carved it out

- `.gitignore:16-23` pre-declares `/reports/local/` with the comment naming **"the morning
  reports"** as the user's own data.
- The one-home guard **already excludes it by name**: `tests/bakeoff/test_report.py:2087` and
  its twin at `:2174`, `:2251` filter `reports/local/`, with the argument at `:2076-2077` —
  *"`.gitignore` reserves it for the user's own nightly output, which is their data and never
  ours to assert on."* **So the one-home guard does NOT move a sixth time.** That is a real
  finding: the brief assumed it stayed put; the guard proves it.
- `reports/local/` already holds `arm-a/` and `budget-2048/`, each a three-artifact
  report.md/report.json/cost.json from the yield probe. A morning report needs its own
  namespace under it (e.g. `reports/local/nightly/<run-id>/`) — the collision is real.

### The locality guard cannot be reused as-is, and that is the sharp edge

`night._refuse_published_root` (`night.py:617-635`) refuses **any** path with a `reports`
component (`PUBLISHED = "reports"`, `night.py:96-98`). `reports/local/` is inside `reports/`,
so importing that predicate by identity would **refuse this unit's own documented home.**

The coherent rule is its narrower sibling: refuse a published root *except* the
`reports/local/` carve-out that `.gitignore:23` and the one-home guard already recognise by
name — reusing `PUBLISHED` by identity and raising `TranscriptNotPrivate` by identity, so this
repository keeps one name for "private evidence was pointed at a published path". It must be
watched failing: `reports/nightly/` refused, `reports/local/night-001/` accepted,
`reports/local/../baseline/` refused **on the resolved path** (the `night.py:620-622`
argument).

### "Signed" is narrative, and the repo settles it

The word appears exactly twice about this feature — `VISION.md:12` (*"a signed proof that the
gains are real and the model didn't cheat"*) and `docs/ROADMAP.md:592`, `:663`. There is **no
crypto anywhere**: `pyproject.toml:21` is `dependencies = []`, *"Zero runtime dependencies"*,
and no signing library exists in any group. A cryptographic signature would also prove the
wrong thing — authorship, not honesty.

The grounded reading, and the one this project's idiom already supports: **sealed to its
evidence.** Every figure carries the digest of the document it came from, and the report is a
pure function of those documents, re-derivable byte-for-byte. That is the same
"harness-reproduces-the-number" property P4 exit criterion 3 demanded of the honest-number
report, at the local surface. The PRD must state this in words and the report must never use
wording implying a signature the code does not produce.

### The CLI edge, and the template for it

`whetstone report` becomes the **fourth** documented function-local edge. The constant is
`_DOCUMENTED_EDGES` (`tests/test_reward_path_scope_is_partitioned.py:152-158`), asserted in
two halves — *"exactly the documented edges"* (`:450-498`) and *"…are function-local"*
(`:501-545`) — and the `loop` exemption's prose says **"exactly THREE documented edges"**
(`:128`), so the reason text moves with the constant. `run_check_leakage_cli`
(`cli.py:815-844`) is the exact template: a function-local import of `REFUSALS`, `disclosure`
and a `run_*` entry point, refusals to `USAGE_ERROR`, no fifth exit code.

### Two stale claims the dig turned up (in files this unit edits anyway)

1. **`cli.py:1-13`** says *"four now do"* and *"All four subcommands"*, enumerating verify /
   mine / run --night / gate — **`check-leakage` is missing**, and the docstring ends *"There
   is still no report, so there is still no stub for it"*, which this unit falsifies.
2. **`README.md:229`** lists as ❌ Not built: *"The never-regress promotion gate, the held-out
   split, the signed morning report, and the dashboard"* — the gate and the split **shipped in
   P3**. The next row is worse: *"🚫 Not released: No tags, no PyPI package, no version"*, with
   **v0.3.0–v0.10.0 tagged and published**. This is exactly the failure `CLAUDE.md` records
   about itself ("This line read 'nothing has been published to PyPI' until 2026-08-20; it had
   been false since v0.3.0"), live again in the repository's front door.

## Placement on the core loop, and the guardrails

Element ④, the signed morning report. The reward path is untouched: the report reads JSON and
renders text. `UNVERIFIED` is never a win — a gate that returned `UNVERIFIED` renders as *no
comparison was made*, and a zero-strict-PASS night renders as the published outcome it already
is (`night.py` writes a ledger, no checkpoint, and exits non-zero). Nothing leaves the box:
the home is gitignored and the note carries hashes and verdicts, never task contents.

## Open questions for the PRD

1. **"Signed" = sealed-to-evidence** (digests + a re-derivation check), never cryptographic.
   Recommend adopting and saying so in the report's own text.
2. **The "last night" rule** — greatest declared `recorded_on`, ties refused by name, explicit
   `--run` as the escape. Recommend adopting; never mtime, never the clock.
3. **Layout under `reports/local/`** — a `nightly/<run-id>/` namespace, and whether the shape
   is report.md + report.json (there is no cost document a night produces).
4. **The gate side is optional evidence.** A night is not always followed by a gated
   evaluation. Recommend an optional `--record` pointer whose absence renders as *"no gated
   evaluation is recorded for this night"* — a fact, never a blank.
5. **Are the two stale claims in scope?** Recommend yes for both: `cli.py`'s docstring is in a
   file this unit edits, and `README.md:229` must change for the morning-report row regardless
   — leaving the neighbouring falsehoods in place while editing the same table would be the
   one thing this project does not do.
