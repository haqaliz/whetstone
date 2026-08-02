# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Whetstone's contract is that a number appears only where something produced it. That applies
here too: this file records what shipped, not what is planned. Nothing is listed under a
released version until it exists in the code.

## [Unreleased]

P1 complete: the reward, the contract it grades against, the first corpus of real tasks, and the
bake-off that closes the phase. Nothing has been tagged since `0.1.0`, so everything below is
unreleased. Figures about a model now exist, and `reports/baseline/` is their only home — nothing
in this file restates one, because a figure quoted twice is a figure that can disagree with itself.

### Added

- The verifier core (`src/whetstone/verify/`): the frozen `Task` contract, verdict semantics in
  which `UNVERIFIED` ranks above `PASS`, a Seatbelt sandbox that denies the network and confines
  writes, and the STRICT verifier — the reward — alongside the WEAK one, which is measurement
  only. Both reachable as `whetstone verify`.
- An adversarial corpus (`tests/adversarial/`) putting ten cheats through both verifiers: eight
  killed, and two reported rather than patched — special-casing the known input, and mutating a
  file a held test depends on that the manifest never declared.
- An AST guard that fails the build if any inference library is reachable from the reward path,
  scoped to the reward-path packages so it stays true once `mlx-lm` is legitimately installed
  elsewhere. Extended in this cycle to cover `src/whetstone/tasks/`, because ingestion authors
  the very boundary the reward path enforces; each guarded root is now asserted to contribute
  modules, so widening the scope cannot leave a root silently watching nothing.
- `environment` on every task manifest — a nominated interpreter and exact `==` pins, with
  ranges refused at load rather than defaulted. Without it a verdict depends on the resolution
  date: `pallets__flask-5063` declares `click>=8.0`, today's `click 8.4.2` has removed
  `CliRunner(mix_stderr=)`, four `pass_to_pass` tests fail, and a correct patch is scored FAIL.
  `tests/test_environment_pins.py` shows one task and one correct patch reaching PASS pinned and
  FAIL unpinned, resolved offline against a committed two-version index.
- A per-task interpreter, so a task is verified under the Python era it was written for instead
  of whichever one happens to be running the verifier.
- Non-canonical held test paths are refused at load — `./tests/x.py`, `tests//x.py`, a trailing
  slash, a bare `.` component, an empty path. Each is a second spelling of a held file that the
  patch-scope refusal compares against git's canonical output and never matches. Refused, never
  silently rewritten: the error names the canonical spelling and stops.
- `whetstone verify --task` accepts a directory of manifests, reducing worst-status-wins through
  the existing verdict semantics, so one `UNVERIFIED` task among passes can never exit 0. No new
  exit code. Nothing is skipped — a non-manifest entry fails the invocation loudly — and an empty
  directory is a usage error rather than a set of zero tasks that all passed.
- The `tasks/` layout, splitting what may be committed from what may not: public benchmark
  instances and the mining recipe and liveness ledger are committed; the user's own mined tasks
  never are. `tasks/README.md` states the rule and `tests/test_tasks_layout.py` asserts git's own
  answer in both directions.
- A miner for source B — the user's own repositories — turning a commit that takes an existing
  test from red to green into a task. **66 tasks minted, 45 from `contig` and 21 from `belay`,
  each proven live before it was kept**: FAIL with no patch, PASS under its own reference patch,
  the executed node-id set equal to the declared one, zero skips. A task that cannot be shown to
  discriminate is not written out. The manifests are the user's code and stay in gitignored
  `tasks/local/`; what ships is `tasks/recipes/<donor>.json` — the procedure — and
  `tasks/local-ledger.json`, a per-task manifest hash with the two verdicts and the tool versions
  behind them. A reader with none of the data can still count the corpus, check that every task
  was proven rather than assumed, and re-derive it against their own copy of the donor.
- The `conftest.py` floor at mint time: every `conftest.py` from the repository root down to each
  held test's directory is declared held, read at the parent commit, and a held set that omits one
  is refused by name. This **narrows** cheat 10 and does not close it — ~22% of `contig`'s
  mintable commits (49 of 224) also touch a non-`.py` file no conftest rule would ever see — so
  the cheat stays a documented residual in the corpus and in `docs/ROADMAP.md` § 3.
- A four-gate eligibility filter for source A (SWE-bench-Lite) — format, environment,
  collectability, liveness — proving eligibility per instance instead of assuming it. **One of 300
  instances is eligible** (`pallets__flask-4045`), and all 299 refusals are committed in
  `tasks/public/ineligible.json` against the gate that refused each: 192 format, 106 environment,
  1 collectability. The rejection ledger is the deliverable; the count is its honest output, and
  one instance is not a benchmark-sized set.
- `environment.import_roots` on every manifest — the repository-relative directories holding the
  code under test — put on `PYTHONPATH` by STRICT, resolved against the run's own checkout.
- Donors whose layout cannot be read from their build configuration, and donors with no lockfile,
  are refused **by name** rather than guessed at. A wrong import root does not fail loudly; it
  fails by passing, and an unpinned donor would have its versions chosen by the date the mint ran.
- `PREREGISTRATION.md`, committed at the repository root **before any number about a model
  existed** — which is the whole of its value, since a headline rule chosen once results are
  visible describes them rather than constraining them. It fixes the headline as the change in
  STRICT-PASS **count** on the held-out source-B split, published over its denominator with
  coverage and `N` beside it and never as a rate; defines every metric before any is measured;
  carries the baseline protocol, including what it means for a changed pinned input to invalidate
  a series; and commits to publishing both sources together, with a disagreement between them
  reported as a finding rather than resolved by picking the flattering one.
- **No numeric success threshold is pre-registered, and none may be added once a number exists.**
  No baseline has been measured and no base chosen, so any bar set today would be invented — and
  one set later would be post-hoc selection wearing the costume of rigour. Three items are named
  as open instead of guessed, each with the dated amendment that closes it and the measurement it
  must precede: the held-out split, the retry count `R`, and which open base is fine-tuned.
- Five limitations disclosed in advance rather than discovered in the result: source B's
  self-selection — **and that its stated mitigation did not land**, since `rereflect` was refused
  for having no `uv.lock`; source A being 1 eligible instance of 300 and reported per-instance;
  cheats 6 and 10 surviving into any reported `N`, with the verifier's bound that it confines what
  a run may write and not what it may read; source B's data never leaving the box, which limits
  what an outsider can audit; and that pre-registration is a timing control and **not** an
  independence control, this being a solo project.
- Guards in `tests/test_docs.py` holding the document shut: every section present, **no
  placeholder in any spelling** — Belay's `PHASE0_RESULTS.md` carried `TO-BE-FILLED` for ten days
  — **no figure about a model**, banned as glyph and as word so the rule cannot be spelled around,
  and nothing under `reports/` in a tree lacking the file. That last guard is exercised against
  two synthetic trees, because `reports/` does not exist yet and a guard nobody has watched fail
  may be passing vacuously. It proves co-existence, not ordering: a single commit adding both
  would satisfy it, and the document states that limit itself rather than letting the test read
  as stronger than it is.

- **Every `docs/ROADMAP.md` citation the pre-registration makes is resolved against the lines it
  names**, each paired with an anchor that must appear inside that exact range, and the pairing
  asserted exhaustive in both directions so a new citation cannot be added without an anchor. This
  guard exists because the slice broke it: the same commit corrected a paragraph in § 4, which
  pushed every later section down by about twenty lines, and five citations written against the
  pre-edit file pointed into the wrong section by the time it landed. An adversarial review caught
  it and nothing in the suite did, because a substring assertion does not know what line it is on.
  **A document whose stated value is that a stranger can check it cannot ship pointers that
  dissolve when their target moves.**

- **The P1 base-model bake-off** (`python -m whetstone.bakeoff.run`, deliberately not a
  `whetstone` subcommand — it is an operator tool, not part of the product surface), which closes
  the last P1 exit criterion. Three candidate open bases each produce one greedy patch per task
  through `mlx-lm`, every patch is graded by the **STRICT** verifier, and both sources are scored
  and published together. The output is `reports/baseline/report.md` with its machine-readable
  `report.json` and `cost.json`, and it is **the only place in this repository where a figure
  about a model may live**.
- **No base is selected, and the zero is published rather than re-run until it flattered someone.**
  Not one candidate solved a single task on the declared source-B set, so P1's pivot signal fired,
  `PREREGISTRATION.md` § 7.3 stays open, and the response it names is an easier task stratum or a
  larger base — never a looser verifier. The failure modes differ by candidate, which locates the
  wall rather than reporting a tie.
- **A control arm, so that a zero is a statement about a base and not about a harness.** Every
  scored task is also run with an inert patch and with its own re-derived reference fix, through
  the same harness under the same environment pins, and a run whose control arm proved nothing is
  refused before it can reach the report. It was intact on every source-B run. This is the direct
  descendant of the false PASS recorded below: the lesson there was that a verdict can come from
  outside the run, and an uncontrolled zero has exactly the same shape.
- **Two bounds disclosed in the report rather than left to be found in it.** Prompts use the
  **oracle retrieval** setting — each base is shown the non-test files the reference patch
  touches — so every count is an upper bound on what the same base would do from the bug report
  alone, and may not be compared with a figure measured without retrieval. And the **generation
  contract** (prompt template, retrieval setting, sampler, token budget, extractor) is **not**
  among the pre-registration's five pinned inputs while demonstrably moving the numbers, `N`
  included; the contract states the patch-scope rule to every candidate, which makes `N` a floor
  under a disclosing contract rather than a natural rate.

### Fixed (documentation)

- **`docs/ROADMAP.md:387` stated P1's pivot signal over a set that does not exist.** It read *"any
  held-out task"*, while `PREREGISTRATION.md:242-247` leaves the held-out split open until P3 — so
  there was no such set for the signal to be read against. The wording now names the declared
  source-B set, the change is dated in place rather than made silently, and `reports/baseline/`
  publishes the disagreement between the two documents as a finding.
- **`docs/ROADMAP.md` § 4, `CLAUDE.md`, `README.md` and this file each asserted, in the present
  tense, that this repository held no figure about a model.** The bake-off makes that false, and a
  status block
  that denies the measurement it ships beside is the failure `docs/ROADMAP.md` § 4 already records
  this project committing once. All four are corrected in the commit that lands the report. The
  roadmap's copy could not simply be deleted: `PREREGISTRATION.md` is **append-only** and cites
  `docs/ROADMAP.md:364-368` on that exact sentence, so the sentence is kept inside those five
  lines as a **quoted, dated correction** — the precedent § 4 already sets for its claim about
  belay — the § 4 rewrite is line-count-neutral so no later citation shifts, and all ten pinned
  citations still resolve. `tests/test_docs.py` now asserts the claim survives in the roadmap only
  inside a blockquote and nowhere in its running prose, and that P1 records **no** criterion still
  open, both spellings of the older count being forbidden.

- Five stale `docs/ROADMAP.md:NNN-MMM` citations in `PREREGISTRATION.md`, and three
  `CLAUDE.md:NNN` citations — one in `PREREGISTRATION.md`, two in `docs/ROADMAP.md` § 11 — that
  this cycle's own insertion into `CLAUDE.md` pushed further out of place. Two further stale
  citations are **left standing and reported rather than quietly fixed**: `docs/ROADMAP.md:289`
  cites `CLAUDE.md:93` for the licence in a P0 block whose parenthetical *"the file is absent
  today"* is separately stale, and `docs/ROADMAP.md:536` quotes a `CLAUDE.md` sentence that no
  longer exists anywhere in that file — it was removed as a stale claim and `tests/test_docs.py`
  now forbids its return. Both need a decision about historical framing rather than a new line
  number, which is a different change from this one.
- **`docs/ROADMAP.md` § 4, P4 overstated a sibling project's failure.** It asserted that Belay's
  `PHASE0_RESULTS.md` carried 20 `TO-BE-FILLED` markers; that was exact on 2026-07-28 and false
  about ten hours later, when the document was filled and recorded a **PIVOT** — a negative
  result, published. Verified by `grep -c`: 0. A claim about another project's honesty, inside our
  own section about publishing honestly, is the worst sentence in the document to leave stale. The
  transferable lesson replaces it and is sharper: Belay's criteria were fixed in a **planning
  file** and never copied into the document that publishes the number before the gate ran — which
  is why `PREREGISTRATION.md` sits at the repository root and not under `docs/planning/`.

### Fixed

- **A false PASS on the reward path: a task passed with no patch applied at all.** For a
  `src`-layout project the tests import by package name, resolved through the venv — and the venv
  carried an editable install rooted at the *provisioning* checkout, a different directory from
  the one the reward applies patches to. The tree under verification was never imported, so the
  verdict came from outside the run and a policy submitting nothing would have been paid. Closed
  at both ends: `import_roots` on `PYTHONPATH` ahead of `site-packages`, and provisioning with
  `--no-install-project` so no copy of the project exists for a verdict to leak into. The
  ten-cheat corpus had missed it because every fixture repository was flat-layout and none was
  installed into a venv — **the defence was the shape of the fixtures, not anything the verifier
  did.** `tests/adversarial/test_inert_checkout.py` is the regression, and it asserts the mirror
  too: the same task under its real reference patch still passes.

## [0.1.0] - 2026-07-27

The scaffold. No verifier, no reward, no loop, no gate, and no model code — P0 exists so that
everything after it can be built test-first.

### Added

- Python packaging: distribution `whetstonehq`, import package and CLI `whetstone`, built with
  hatchling. Zero runtime dependencies — the CLI is stdlib-only.
- `whetstone` console script exposing exactly two behaviours: `--help` and `--version`. No
  subcommand stubs; a command appears only when something stands behind it.
- `whetstone.__version__`, resolved at runtime from installed package metadata rather than
  written as a literal, so it cannot drift from what was built.
- A test suite (`pytest`) covering the CLI's exit codes and output, the version boundary
  between distribution and import package, the wired console script exercised in a real
  subprocess, and an anti-vacuity control over the parser's flags.
- Strict tooling from day one: `ruff` (line length 100) and `mypy --strict` over `src/`.
- Apache-2.0 `LICENSE`.
- CI on `macos-latest`, running ruff, mypy, and pytest, plus a step that installs the optional
  `mlx` extra and asserts `import mlx` actually succeeds — not merely that installation
  exited 0.

[Unreleased]: https://github.com/haqaliz/whetstone/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/haqaliz/whetstone/releases/tag/v0.1.0
