# Aspect Spec — `scaffold`

**Feature:** `p0-scaffold` · **Aspect:** `scaffold` (the only one)
**PRD:** `docs/planning/p0-scaffold/prd.md` · **Written:** 2026-07-27

P0 is a single coherent unit — packaging, CLI, tooling config, and CI are mutually dependent
and none is independently shippable. Decomposing further would create artificial seams.

---

## Problem slice

`master` @ `347655a` has zero lines of executable code. The repo's workflow is strict TDD,
so nothing downstream can be built until `uv run pytest` works. This aspect delivers the
whole floor.

## User outcome

`git clone && uv sync && uv run pytest` succeeds on a fresh Apple Silicon machine, and CI
reproduces it on every push to `master`.

## In scope

- `pyproject.toml` (hatchling, `whetstonehq`, `>=3.10`, Apache-2.0, console script, strict
  ruff/mypy config, PEP 735 dev group, optional `mlx` group)
- `src/whetstone/{__init__.py,cli.py}` — `__version__` from `importlib.metadata`; argparse CLI
  with `--help` and `--version` and no subcommands
- `tests/` — flat, no `__init__.py`
- `LICENSE` (Apache-2.0), `.python-version` (3.12), `uv.lock` (committed)
- `.github/workflows/ci.yml` — `macos-latest`, with an mlx-resolution tripwire
- `CHANGELOG.md`, `RELEASING.md`, `CONTRIBUTING.md`
- Two documentation corrections: `ROADMAP.md:290` guard filename; three stale `CLAUDE.md` claims

## Out of scope

Verifier, task contract, reward, sandbox, rollouts, gate, report, dashboard, AST import guard,
`release.yml`, any *use* of mlx beyond proving it resolves and imports, publishing to PyPI.

## Acceptance criteria (these are the failing tests, written first)

Lifted verbatim from `prd.md` § Acceptance Criteria — not re-invented:

| # | Criterion | Test location |
|---|---|---|
| AC-1 | `main(["--help"])` returns 0 **and** stdout names the program `whetstone` | `tests/test_cli.py` |
| AC-2 | `uv run whetstone --help` exits 0 from a shell (console script wired, not just importable) | `tests/test_console_script.py` |
| AC-3 | `whetstone.__version__ == importlib.metadata.version("whetstonehq")` | `tests/test_version.py` |
| AC-4 | `main(["--version"])` returns 0 and prints that same resolved version; bare `main([])` returns **non-zero** and prints usage | `tests/test_cli.py` |
| AC-5 | `uv run ruff check .` exits 0 | CI + local |
| AC-6 | `uv run mypy src/` exits 0 under `strict`, `warn_unused_ignores` on | CI + local |
| AC-7 | **Anti-vacuity control** — the parser introspection AC-4 relies on actually observes `--help` and `--version`, so no check passes over an empty set | `tests/test_cli.py` |
| AC-8 | `LICENSE` exists; first line is the Apache License header | `tests/test_packaging.py` |
| AC-9 | CI green on `master`, running all four commands | GitHub Actions |
| AC-10 | A CI step installs the mlx group on `macos-latest` and asserts `import mlx` succeeds — not merely that install exited 0 | GitHub Actions |
| AC-11 | `ROADMAP.md` no longer cites `test_import_guard.py` for the inference guard | `tests/test_docs.py` |
| AC-12 | `CLAUDE.md` contains none of the three stated stale claims | `tests/test_docs.py` |
| AC-13 | `CHANGELOG.md` carries a `0.1.0` entry matching `pyproject.toml` | `tests/test_packaging.py` |

### The adversarial criterion

P0 ships no reward, so there is no cheating *policy* to defend against. The transferred
obligation is **anti-vacuity**, and AC-7 is the criterion that carries it: it must be watched
failing before it is trusted. Per Belay's convention — *"a guard nobody has seen fail may be
passing vacuously"* — the implementing agent must, for AC-7, temporarily point the
introspection at an empty parser, observe the test FAIL, and revert. That observation is
recorded in the commit body.

The same discipline applies to AC-10: its value is entirely in asserting `import mlx`, since
`mlx-lm` declares `mlx; platform_system == "Darwin"` and therefore installs *successfully with
no engine* off Darwin. An install-exit-0 check would pass on a runner where mlx is absent.

## Dependencies and sequencing

No code dependencies — this is the first code. Sequencing is internal and strict:

1. Packaging + version resolution must exist before the CLI can resolve its own version.
2. The CLI must exist before its tests can pass (but **after** they are written and fail).
3. Tooling config must exist before CI can run it.
4. CI comes last; it runs everything prior.
5. Doc corrections are independent of all the above and can run in parallel.

## Open questions / risks specific to this aspect

1. **`uv.lock` cannot be generated until `pyproject.toml` exists** — so the very first RED
   test runs before any venv. It must be runnable via `uv run --with pytest pytest` or after a
   minimal `pyproject.toml` exists. Sequence carefully; this is the one genuinely awkward
   bootstrap moment.
2. **`importlib.metadata.version("whetstonehq")` requires the package to be *installed*,** not
   merely on `sys.path`. `uv sync` installs the project editable by default, so this works —
   but a test run without a sync will fail confusingly. Worth an explicit error message.
3. **AC-10 can only be verified in CI**, not locally on the founder's machine (where mlx
   installs regardless). Its first real signal is the first CI run.
4. **`macos-latest` is deliberately unpinned** (PRD risk 2) — the mlx step is the tripwire.
