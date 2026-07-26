# PRD — P0 Scaffold

**Slug:** `p0-scaffold` · **Branch:** `feat/p0-scaffold/aliz` · cut from `master` @ `347655a`
**Written:** 2026-07-27 · **Upstream spec:** `docs/ROADMAP.md` § 4 "P0 — Scaffold" (PR #2)
**Core-loop element:** none directly — infrastructure beneath ①

**Deliverable:** an executable, test-first Python project. No reward, no loop, no gate, no
model code.

---

## Problem Statement

`master` @ `347655a` contains **zero lines of executable code** — no `src/`, no `tests/`, no
`pyproject.toml`, no `uv.lock`, no `.python-version`, no `.github/`, no `LICENSE`. The repo
is `CLAUDE.md`, `VISION.md`, `README.md`, `assets/logo.svg`, `docs/`, and ten workflow skills.

The repo's workflow is **strict TDD** (`CLAUDE.md:170`), and `whetstone-worktrees:94` states
the consequence plainly: `uv sync` fails and `uv run pytest` has nothing to run until this
unit ships. `ROADMAP.md:130` says the same — *"Nothing can be test-first until a test runner
exists."*

Every P1 exit criterion (`ROADMAP.md:154-166`) is a `uv run pytest ...` invocation. P1 is the
moat. So the moat is blocked on this.

**Who has this problem:** the founder, today, as the single blocking prerequisite. No end user
is served by P0 — and the PRD should not pretend otherwise.

**Evidence:** `git log origin/master` (four commits, all docs/assets); `find . -name '*.py'`
returns nothing outside gitignored worktrees; `ROADMAP.md:140` assigns P0 **no pivot signal**,
i.e. it cannot be abandoned or descoped.

## Goals & Success Metrics

P0's success is **not** a model-improvement number, and no such number exists yet. Its
criteria are the five commands and artifacts in `ROADMAP.md:133-138`, reproduced as
acceptance criteria below.

The one substantive risk P0 retires is **toolchain feasibility on the locked platform** —
see § Technical Considerations A. Everything else it delivers is a prerequisite, not a result.

**No projected numbers appear in this PRD.** Nothing has been measured.

## User Personas & Scenarios

Only one persona applies at P0: **the founder, and any future contributor cloning the repo.**
The scenario is `git clone && uv sync && uv run pytest` succeeding on a fresh machine, and CI
reproducing that on every push.

The ICP — an engineer who wants a model measurably better at their tasks by morning — is not
served by this unit and will not observe it. Stating that plainly is the honest framing.

## The Decisions (locked in interview, 2026-07-27)

| # | Decision | Choice |
|---|---|---|
| 1 | **Distribution name** | **`whetstonehq`**. `whetstone` is taken on PyPI (verified: HTTP 200 on `pypi.org/pypi/whetstone/json`, 2026-07-26). Import package and CLI stay **`whetstone`** — exactly Belay's `belay-harness` pattern, documented in a `pyproject.toml` comment so the next reader doesn't rediscover it. `whetstone-ai` and `whetstone-hq` were also free and were not chosen. |
| 2 | **CI runner + MLX** | **GitHub Actions, `macos-latest` only, no matrix.** `mlx-lm` is declared in an **optional dependency group**, with one CI step that installs that group purely to prove it resolves on the hosted runner. The test suite does **not** depend on it. |
| 3 | **Lint / type strictness** | **Strict from day one.** `mypy strict = true` over `src/`; ruff with an explicit rule set (`E`, `F`, `I`, `UP`, `B`, `SIM`) and `line-length = 100`. Chosen because there is zero existing code to retrofit — this is the cheapest moment it will ever be. |
| 4 | **Python** | `requires-python = ">=3.10"`, `.python-version` pinned to `3.12`. **Grounded, not copied:** `mlx` core declares `requires-python = ">=3.10"` (PyPI, verified 2026-07-27). Belay's independent choice matches. |
| 5 | **CLI surface** | `--help` exposes **only what exists**. No stubs reserved for `verify`, `run`, `gate`, `check-leakage`, or `report`. A `--help` advertising commands that do nothing is a claim the code can't back — the same failure this project exists to refuse. Resolves `understanding.md` § 5F by declining the premise. |
| 8 | **What the CLI actually does in P0** | Exactly two behaviours, no subcommands: **`whetstone --version`** prints the installed distribution version resolved at runtime via `importlib.metadata`, and **bare `whetstone`** prints usage and exits **non-zero**. Added at the review gate to close critique gap 1 — without it, P0 has no behaviour worth a non-trivial test, and `ROADMAP.md:134` would be satisfied only in letter. The version path is the substantive one: it crosses the distribution↔import boundary (`whetstonehq` → `whetstone`) and fails loudly if the two disagree. |
| 6 | **License** | **Apache-2.0**, confirmed. `CLAUDE.md:93` proposed it under a heading saying "nothing here is locked"; this decision locks it. PEP 639 form (`license = "Apache-2.0"` + `license-files`), no per-file headers. Belay matches. |
| 7 | **In-scope beyond the exit criteria** | `CHANGELOG.md`, `RELEASING.md`, `CONTRIBUTING.md`, plus two documentation corrections (§ Requirements, must-have 8–9). |

## Requirements

### Must-have

1. **`pyproject.toml`** — hatchling backend, `[project] name = "whetstonehq"`, version `0.1.0`,
   `requires-python = ">=3.10"`, PEP 639 license fields, `[project.scripts] whetstone =
   "whetstone.cli:main"`, `[tool.hatch.build.targets.wheel] packages = ["src/whetstone"]`,
   PEP 735 `[dependency-groups]` for dev deps, and an optional group carrying `mlx-lm`.
2. **`src/whetstone/`** with `__init__.py` and `cli.py`. `__version__` derived from
   `importlib.metadata` — **not** a hardcoded literal, explicitly avoiding Belay's
   `0.0.0`-vs-`0.7.0` drift.
3. **`whetstone --help` exits 0**, built on stdlib `argparse`, `main(argv=None) -> int` so
   tests can call it directly and assert on the exit code.
4. **`tests/`** — flat, no `__init__.py`, with at least one test that exercises real
   behaviour (see § Anti-vacuity).
5. **`uv run ruff check .` and `uv run mypy src/` exit 0** with the § Decisions-3 config.
6. **`LICENSE`** — unmodified Apache-2.0 text.
7. **`.github/workflows/ci.yml`** — `macos-latest`, on push/PR to `master`, running
   `uv sync` → `ruff check .` → `mypy src/` → `pytest`, plus the mlx-resolution step.
   Concurrency group with `cancel-in-progress`.
8. **Correct `ROADMAP.md:290`** — it cites Belay's `tests/test_import_guard.py` as *"the AST
   guard proving no model sits on the reward path."* That file bans `mcp`, non-stdlib
   imports, and `json` in `proxy.py`. The actual inference guard is
   `tests/test_verify_zero_llm.py`. Uncorrected, **P1 ports the wrong file** — and P1 is the
   moat.
9. **Update `CLAUDE.md`** — three stale claims: the "nothing is built yet / next step is the
   roadmap" status block (`:5-7`); the runtime named as "Ollama / vLLM / transformers"
   (`:88`) when MLX is locked; and the "reuse Belay's verifier/replay" line (`:79`) the
   roadmap explicitly declines (`ROADMAP.md:292-305`). `CLAUDE.md:7` already obliges this.

### Should-have

10. **`CHANGELOG.md`** (Keep a Changelog format) and **`RELEASING.md`**. Creating
    `pyproject.toml` flips `whetstone-end-fast`'s release phase from no-op to live, so these
    stop being optional in practice.
11. **`CONTRIBUTING.md`** — the uv setup and the test-first contract.
12. **`.python-version`** pinned to `3.12`.
13. **`uv.lock`** committed (`whetstone-worktrees:89` builds venvs from it).

### Nice-to-have

14. Module docstrings in Belay's essay style — each stating what failure the module prevents.
15. A `release.yml` mirroring Belay's tag-vs-version check and PyPI trusted publishing.
    **Deferred by default** — nothing ships from P0, and an untested release workflow is a
    liability, not an asset.

### Explicitly NOT in this unit

No verifier. No task contract. No reward. No sandbox. No rollouts. No gate. No report. No
dashboard. No `mlx` *usage* (only a resolution check). No AST import guard — that is P1's
flagship deliverable and belongs with the code it guards.

## Anti-vacuity (the reward-hacking question, applied to P0)

P0 has no reward, so a policy cannot cheat it. The meaningful version of the question is
**how an implementer could satisfy P0's exit criteria while destroying their purpose** — and
each has a cheap structural answer:

| Cheat | Satisfies | Defeated by |
|---|---|---|
| `assert True` / bare import smoke test | `pytest` exits 0 | AC-1: the test must assert on observable CLI behaviour — exit code and stdout content — via `main(argv)`. `ROADMAP.md:134` says "non-trivial" and means it |
| Blanket `# type: ignore` | `mypy src/` exits 0 | AC-5: `warn_unused_ignores = true` under `strict`, so a needless ignore is itself an error |
| File-level `# ruff: noqa` | `ruff check .` exits 0 | AC-6: ruff's own `RUF100` flags unused noqa; blanket suppressions are reviewable in a 1-file diff |
| CI green without running tests | "CI workflow green" | AC-7: CI must fail if the suite is empty — assert a non-zero collected count, not just exit 0 |
| `uv sync` green on a runner where mlx is absent | "CI green" | AC-8: this is real. `mlx-lm` declares `mlx; platform_system == "Darwin"`, so on Linux it installs **without** the engine and reports success. The mlx step must assert `import mlx` works, not that install exited 0 |

Belay's convention is the precedent: *"a guard nobody has seen fail may be passing
vacuously."* Every guard above should be watched failing before it is trusted.

## Acceptance Criteria (test-first — written before the code)

1. `uv run pytest` exits 0, and the suite contains at least one test that invokes
   `whetstone.cli.main(["--help"])` and asserts **both** the return code is 0 and that stdout
   names the program `whetstone`. Import-only tests do not satisfy this.
2. `uv run whetstone --help` exits 0 from a shell, proving the console script is wired
   through `pyproject.toml` and not merely importable.
3. A test asserts `whetstone.__version__` equals `importlib.metadata.version("whetstonehq")`
   — pinning the two together so they cannot drift.
4. **`main(["--version"])` returns 0 and prints exactly that same resolved version**, and
   **bare `main([])` returns non-zero and prints usage.** These are the two behaviours
   Decision 8 commits to, and AC-4 is the load-bearing non-trivial test: it fails if the
   distribution name, the console script, or the package metadata disagree.
5. `uv run ruff check .` exits 0.
6. `uv run mypy src/` exits 0 under `strict = true`, with `warn_unused_ignores` on.
7. **Anti-vacuity control:** a test asserts the parser introspection used by AC-4 actually
   *observes* the flags that exist (`--help`, `--version`), so the checks cannot pass over an
   empty set. Replaces the earlier "no unimplemented subcommand" criterion, which asserted
   over nothing and was itself the vacuous guard this PRD condemns.
8. `LICENSE` exists and its first line is the Apache License header.
9. CI is green on `master` and its config runs all four commands. Note `pytest` already exits
   5 on an empty collection, so no extra empty-suite guard is needed — AC-7 is what guards the
   failure that actually threatens P0 (a suite of one vacuous test).
10. A CI step installs the mlx optional group on `macos-latest` and asserts `import mlx`
    succeeds — not merely that installation exited 0.
11. `ROADMAP.md` no longer cites `test_import_guard.py` for the inference guard.
12. `CLAUDE.md` contains none of the three stale claims listed in must-have 9.
13. `CHANGELOG.md` carries a `0.1.0` entry matching `pyproject.toml`'s version.

## Technical Considerations

### A. The MLX/CI risk — inverted by what was actually verified

The dig recorded this as *"`mlx-lm` is Apple-Silicon-only, so CI on Linux would fail."*
**Checking PyPI showed that is wrong, and the truth is worse.** `mlx-lm` declares
`mlx>=0.31.2; platform_system == "Darwin"`. On Linux `uv sync` **succeeds** and installs
`mlx-lm` with no engine behind it. `mlx` core does now publish `manylinux`/`win` wheels, but
only via explicit `cpu`/`cuda12`/`cuda13` extras that the marker does not select.

So an `ubuntu-latest` CI would have gone green while proving nothing — a passing check that
misrepresents the state of the system. Decision 2 (`macos-latest` + an `import mlx`
assertion, not an install-exit-0 assertion) is what actually retires the risk.

This is the only genuine engineering risk P0 retires, and it is worth the phase on its own:
discovering it in P2 would invalidate a toolchain three phases of work were built on.

### B. Dependency posture

Belay's `dependencies = []` is load-bearing for Belay and **cannot survive Whetstone**, which
needs `mlx-lm` for rollouts and LoRA. The transferable idea is the *scoped* version: keep the
reward path dependency-free and enforce it narrowly in P1. P0's obligation is purely
negative — **put no inference library on the future reward path**, so P1's guard isn't
pre-poisoned.

Runtime `dependencies` should be `[]` at P0 (the CLI is stdlib-only); ML deps live in the
optional group.

### C. Core-loop placement — honest version

P0 advances **none** of the five elements. It makes ① buildable under strict TDD without
implementing any part of it. Claiming otherwise would overstate the work.

### D. Guardrails

- **Reward execution-grounded** — no reward exists in P0; the obligation is negative (§ B).
- **`UNVERIFIED` never a win** — no gate in P0.
- **Local / no egress** — CI runs against the repo's own source on GitHub's runners. No user
  task data exists yet; none is involved.
- **No frontier base-model training** — P0 trains nothing.
- **Gets better as bases improve** — P0 is toolchain; the optional-group posture keeps the
  base swappable per `CLAUDE.md` #4.

## Risks & Open Questions

1. **`macos-latest` runners are billed at a higher multiplier than Linux.** Accepted
   deliberately: a cheaper runner that cannot observe the engine is worse than no check.
   Revisit only if minutes become a real constraint.
2. **`macos-latest` tracks a moving image.** GitHub repoints it across macOS majors; `mlx`
   ships per-major arm64 wheels (`macosx_14_0`, `15_0`, `26_0`). A future repoint could
   outrun the wheels. **Accepted deliberately, not pinned:** tracking `latest` means the mlx
   resolution step tells us the day the toolchain drifts, whereas a pinned image would hide
   that until someone bumped it. The step is the tripwire, and a tripwire that fires is the
   point.
3. **`strict = true` may bite in P1** when the verifier does subprocess and filesystem work
   with loose types. Mitigated by choosing it now, while the retrofit cost is zero, and by
   `warn_unused_ignores` making each escape hatch visible.
4. **`whetstonehq` is unclaimed but unreserved.** Nothing is published in P0, so the name
   could be taken before first release. Accepted; re-check before the first tag push.
5. **Open:** whether `release.yml` lands here or with the first real release (nice-to-have 15).
   Defaulting to defer.
6. **Open:** `whetstone report --last-night` remains listed both as an inherited constraint
   (`prd.md:175` of the roadmap unit) and as post-horizon (`ROADMAP.md:329`). Decision 5
   sidesteps it for P0 but does not resolve the contradiction for the roadmap.

## Out of Scope

The verifier and task contract (P1); the AST inference guard (P1); rollouts and expert
iteration (P2); the promotion gate (P3); the honest number (P4); distillation, the morning
report, the dashboard, GRPO, a second task family, Linux portability (all post-horizon);
publishing to PyPI; and any use of `mlx` beyond proving it resolves and imports.
