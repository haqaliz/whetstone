# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Whetstone's contract is that a number appears only where something produced it. That applies
here too: this file records what shipped, not what is planned. Nothing is listed under a
released version until it exists in the code.

## [Unreleased]

Nothing yet.

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
