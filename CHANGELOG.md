# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Whetstone's contract is that a number appears only where something produced it. That applies
here too: this file records what shipped, not what is planned. Nothing is listed under a
released version until it exists in the code.

## [Unreleased]

P1's moat: the reward, the contract it grades against, and the first corpus of real tasks.
Nothing has been tagged since `0.1.0`, so everything below is unreleased. No model has been run
against any of it — the verifier grades patches, and no number about a model exists.

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
