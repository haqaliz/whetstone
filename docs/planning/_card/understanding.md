# Understanding — feat p0-scaffold

**Written:** 2026-07-26 · **Branch:** `feat/p0-scaffold/aliz` · cut from `master` @ `347655a`
**Upstream spec:** `docs/ROADMAP.md` § 4 "P0 — Scaffold" (merged in PR #2)

> Supersedes the `feat/roadmap-and-task-family` note that PR #2 committed at this path;
> that version is preserved in history at `347655a`.

---

## 1. What the work is really asking

Turn a docs-only repository into an executable Python project whose toolchain is good enough
that **P1 can be built test-first**. That is the whole point: P0 produces no product surface,
no reward, no loop. It produces the floor.

The five exit criteria are all commands or file-existence checks, so "done" is not a
judgement call. What is *not* pinned by those criteria — and what this unit must therefore
decide — is everything about *how* the toolchain is configured: Python version, ruff rule
selection, mypy strictness, CI runner OS, and the distribution name.

**The honest framing of P0's value:** it retires no product risk and proves no thesis. It is
a prerequisite. The one substantive risk it *does* retire is toolchain feasibility on the
target platform — specifically whether the MLX-on-Apple-Silicon commitment and a green CI can
coexist (§ 5A).

## 2. Repo state, verified not assumed

`master` @ `347655a` contains: `CLAUDE.md`, `VISION.md`, `README.md`, `.gitignore`,
`assets/logo.svg`, `docs/ROADMAP.md`, `docs/planning/`, and `.claude/skills/` (10 skills).

**Zero lines of executable code.** No `src/`, no `tests/`, no `pyproject.toml`, no `uv.lock`,
no `.python-version`, no `.github/`, no `LICENSE`, no `CHANGELOG.md`, no `CONTRIBUTING.md`.
No git tags. `whetstone-worktrees:94` states the same and warns `uv sync` will fail until
this unit runs.

`docs/technical/ARCHITECTURE.md` and `docs/product/PRODUCT_SPEC.md` are named in `CLAUDE.md`
but **do not exist**. `docs/ROADMAP.md` now does, and is the authoritative technical document
in their absence — a fact no file currently states (§ 5H).

## 3. Already locked — do not re-litigate

From `docs/planning/roadmap-and-task-family/prd.md:171-179` ("Constraints inherited from the
repo — must not be contradicted") and corroborated by `.gitignore`:

- Package path `src/whetstone/`; tests in `tests/`
- **uv exclusively** — no pip, no poetry
- ruff + mypy + pytest
- CLI entrypoint `whetstone`
- Artifact dirs `/runs/`, `/checkpoints/`, `/tasks/local/`, `/reports/local/`, `/_sandbox/`
- Base branch `master`; branches `<type>/<id>/aliz`
- 0.x versioning, tag `vX.Y.Z`, **tag-push is the entire release mechanism**
- `uv.lock` is committed (`whetstone-worktrees:89` — "build the venv from uv.lock")
- Dashboard is a Next.js subdirectory of this repo — **post-horizon**, not P0

`.gitignore` independently corroborates the toolchain: it already pre-declares
`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.venv/`, `*.egg-info/`, `dist/`. Those
entries are the only place ruff and mypy appear outside the PRD.

**Artifact-dir subtlety.** `/tasks/local/` and `/reports/local/` ignore *only* the `local/`
subtree. `ROADMAP.md:163` requires `tasks/` to hold committed provenance, and
`ROADMAP.md:165` requires `reports/baseline/` to be committed. This is consistent by design —
a scaffold that broadened the ignore to `/tasks/` would break P1.

## 4. Belay precedent (the reference implementation)

Belay (`~/dev/at/belay`, v0.7.0, 13,068 LOC across 49 modules, 796 `test_*` functions) is the
shipped sibling. Its scaffold answers most of P0's open questions with working code rather
than speculation.

**Directly transferable:**

| Concern | Belay's answer |
|---|---|
| Build backend | `hatchling`; `[tool.hatch.build.targets.wheel] packages = ["src/belay"]` |
| Name collision | `belay` was taken on PyPI → `name = "belay-harness"`, **import package and CLI stay `belay`**. Documented in a `pyproject.toml` comment |
| Python | `requires-python = ">=3.10"`, `.python-version` = `3.12`, CI installs 3.12 |
| Dep groups | PEP 735 `[dependency-groups]`, not `[project.optional-dependencies]` |
| License | `license = "Apache-2.0"` + `license-files = ["LICENSE"]` (PEP 639), unmodified 202-line text, **no per-file headers** |
| CLI | stdlib `argparse`, single `cli.py`, `main(argv=None) -> int`, `set_defaults(func=...)` dispatch, **lazy imports inside handlers to keep `--help` cheap** |
| CI | GitHub Actions, **`macos-latest` only, no matrix**, `uv sync` → `ruff check .` → `pytest -q`, on push/PR to `master`, with a cancel-in-progress concurrency group |
| Release | tag-push `v*`; validates git tag against `pyproject` version; PyPI **trusted publishing** (OIDC, no stored secret); least-privilege `permissions` |
| Tests | flat `tests/`, **no `__init__.py`** (so `from fixtures.x import y` works), `tmp_path` over fixtures, full-sentence test names, prose assertion messages |

**The distinctive convention worth adopting:** every module opens with a long essay-style
docstring explaining *what failure it prevents*, and every ignore rule that isn't boilerplate
carries a comment citing the guardrail it enforces.

**Where Whetstone must exceed Belay rather than copy it:**

1. **mypy.** Belay declares mypy as a dev dep and **never runs it** — no `[tool.mypy]`, no
   `mypy.ini`, absent from CI. Whetstone's `ROADMAP.md:136` makes `uv run mypy src/` an exit
   criterion, so there is no sibling default to inherit. Strictness must be chosen here.
2. **ruff.** Belay has **no `[tool.ruff]` section** and runs stock defaults. Rule selection
   and line length are undecided for Whetstone.
3. **`dependencies = []`.** Load-bearing for Belay (it proxies MCP and must add nothing to
   the user's process tree) and structurally enforced by an AST guard. **This cannot survive
   Whetstone**, which needs `mlx-lm` for rollouts and LoRA. The transferable idea is the
   *scoped* version: keep the reward package dependency-free and enforce that narrowly.
4. **`__version__`.** Belay's `src/belay/__init__.py` says `"0.0.0"` while `pyproject.toml`
   says `0.7.0`, and nothing reconciles them. Don't inherit the drift.

## 5. Contradictions and blockers found

### A. MLX ↔ "CI green on master" — the sharpest, and it has a resolution

`prd.md:58` locks the platform to macOS/Apple Silicon; `prd.md:63` locks `mlx-lm` end-to-end.
`mlx-lm` is Apple-Silicon-only. `ROADMAP.md:138` makes "CI workflow green on `master`" a P0
exit criterion. If `mlx-lm` is a mandatory dependency and CI runs `ubuntu-latest`, `uv sync`
fails and the criterion is **unreachable by construction**.

Nothing in any repo file specifies the CI runner OS, an optional-dependency group, or a
platform marker.

**Belay solved the identical problem** (Seatbelt + APFS `clonefile` are macOS-only) by running
CI on `macos-latest` only, with a comment saying exactly why. That precedent makes this a
solved design question. What remains is **empirical and must be proven, not assumed**:
whether `mlx-lm` actually installs on GitHub's hosted macOS runner. P0 is the right place to
find out, because discovering it in P2 would invalidate the toolchain after three phases of
work were built on it.

**Mitigation available regardless:** P0 need not depend on `mlx-lm` at all. Nothing in P0's
exit criteria requires it. Deferring the ML dependency to P1/P2 — behind an optional group —
keeps P0 unblocked either way. That is a PRD decision, not an implementation detail.

### B. Distribution name — out of scope, yet structurally required

`prd.md:295` puts "choosing the PyPI package name" **explicitly out of scope**;
`prd.md:178` records "package name unchosen". But `ROADMAP.md:135` requires
`uv run whetstone --help` to exit 0, which requires `[project] name` and a console script.

Availability is now **resolved** (see `issue.md`): `whetstone` taken; `whetstonehq`,
`whetstone-ai`, `whetstone-hq` free. Belay's precedent gives the exact pattern — distribution
name differs, import package and CLI do not. So this reduces to picking one string, and it
must be picked here because `pyproject.toml` cannot be written without it.

### C. Python version — completely unspecified

Grep across every `.md` for `requires-python|python 3|3.1[0-3]` returns **zero hits**. No
minimum, no `.python-version`, nothing. Compounding: `mlx-lm`'s supported range would in
practice constrain this, and nothing writes that down. Belay's `>=3.10` + pinned `3.12` is
available as precedent.

### D. CI provider — implied, never decided

`ROADMAP.md:138` says "CI workflow" with no provider. The PRD's locked-decisions table
doesn't mention CI at all. Evidence is indirect but consistent: `whetstone-end-fast` references
`.github/workflows/release.yml` and uses `gh run watch`. GitHub Actions is the only candidate.

### E. `LICENSE` — required by P0, but formally still "proposed"

`ROADMAP.md:137` makes Apache-2.0 a P0 exit criterion. `CLAUDE.md:93` states Apache-2.0 —
but under a heading reading *"Tech direction (proposed — confirm in the planning session)"*,
and `CLAUDE.md:95` says *"Nothing here is locked."* `prd.md:295` put the LICENSE file out of
scope for the roadmap unit. So P0 is required to ship a license whose choice was never
formally confirmed. Belay is Apache-2.0. **Needs one line of confirmation, not a debate.**

### F. `whetstone report --last-night` — both inherited constraint and post-horizon

`prd.md:175` lists it under constraints that "must not be contradicted"; `ROADMAP.md:329`
places it post-horizon. `prd.md:260-261` already flags this as unresolved. Consequence for
P0: no defensible answer on whether `--help` reserves a `report` subcommand.

### G. The roadmap cites the wrong Belay file for its flagship guard

`ROADMAP.md:290` takes `tests/test_import_guard.py` for *"The AST guard proving no model sits
on the reward path."* **That is not what that file does.** In Belay, `test_import_guard.py`
bans `mcp`, bans all non-stdlib imports, and bans `json` inside `proxy.py`.

The inference-library guard is a **different file: `tests/test_verify_zero_llm.py`**. It bans
~25 inference clients (`openai`, `anthropic`, `torch`, `transformers`, `ollama`, `vllm`,
`langchain`, …) plus first-party module names (`llm`, `judge`, `model`, `inference`, …),
**scoped to specific packages** rather than the whole tree — precisely because Belay
legitimately uses `anthropic`/`openai` in its non-shipped `eval/` tree. It also ships an
anti-vacuity control test asserting the AST walk actually observes real imports.

This is P1's concern, not P0's, but **the roadmap should be corrected or P1 will port the
wrong file**. The scoped shape matters more for Whetstone than for Belay: Whetstone will have
`mlx-lm` genuinely installed, making an accidental judge-import trivially easy and otherwise
invisible.

### H. `CLAUDE.md` is now stale in three places

A P0 implementer is instructed by `CLAUDE.md:3` to read it first, and will be misled:

1. `CLAUDE.md:5-7` — "Status: greenfield. Nothing is built yet. The next step is a planning
   session that produces `docs/ROADMAP.md`." That session happened; the roadmap is merged.
2. `CLAUDE.md:88` — runtime listed as "Ollama / vLLM / transformers". The PRD locked
   **MLX / `mlx-lm`** (`prd.md:63`), which is none of the three.
3. `CLAUDE.md:79` — "Reuse Belay's verifier/replay where it fits." `ROADMAP.md:292-305`
   explicitly **declines** the replay substrate with four stated reasons. The superseded line
   is still there.

`CLAUDE.md:7` instructs "Keep them in sync as direction firms up," so this is a known
obligation, currently unmet. Not P0's deliverable, but cheap to fix on this branch.

## 6. Constraints on the implementation

1. **Test-first, including for the scaffold itself.** `whetstone-worktrees:94` — "the failing
   test comes before the package." The first failing test creates the suite.
2. **"Non-trivial test" is a real bar.** `ROADMAP.md:134`. An `assert True` or a bare import
   smoke test fails the criterion as written. Belay's anti-vacuity convention is the model:
   a guard nobody has watched fail may be passing vacuously.
3. **No inference library on the reward path** — P1's guard will fail the build. P0 must not
   pre-poison it.
4. **Tests deterministic, no network.** Any BYOK teacher call sits behind an injectable seam
   and never runs in CI.
5. **No release may be cut.** But note: creating `pyproject.toml` **flips `whetstone-end-fast`
   Phase 3 from no-op to live**, so `CHANGELOG.md` / `RELEASING.md` become relevant. Whether
   P0 creates them is unspecified.
6. **Never copy artifact dirs between worktrees** — provenance is what makes a promotion
   decision real.
7. **P0 has no pivot signal** (`ROADMAP.md:140`) — it cannot be abandoned.

## 7. Open questions for the PRD interview

1. **Distribution name** — `whetstonehq`, `whetstone-ai`, or `whetstone-hq`? (availability
   resolved; choice outstanding)
2. **Does P0 depend on `mlx-lm` at all**, or defer it behind an optional group? Drives whether
   the CI-runner question is load-bearing now or in P2.
3. **CI runner** — confirm `macos-latest` per Belay precedent; confirm GitHub Actions.
4. **Python** — `requires-python` floor and the pinned `.python-version`.
5. **ruff rule selection and mypy strictness** — no sibling default exists; this is a real
   choice, and `mypy src/` must exit 0 on day one.
6. **Does `--help` reserve later subcommands** (`verify`, `run`, `gate`, `check-leakage`,
   `report`) or expose only what exists? Bears on § 5F.
7. **Confirm Apache-2.0** (§ 5E).
8. **Scope creep check** — are `CHANGELOG.md`, `RELEASING.md`, `CONTRIBUTING.md` in or out?
   None are named in P0's exit criteria.
9. **Does this branch also fix the stale `CLAUDE.md` and the `ROADMAP.md:290` file-name
   error** (§ 5G, § 5H), or are those a separate chore?

## 8. Guardrail check

- **Reward stays execution-grounded** — P0 implements no reward. Its only obligation is
  negative: keep inference libraries off the future reward path (§ 6.3).
- **`UNVERIFIED` never a win** — no gate in P0.
- **Local / no egress** — P0 adds a CI workflow that runs on GitHub's runners against the
  repo's own source. No user task data exists yet and none is involved.
- **No frontier base-model training** — P0 trains nothing.
- **No invented numbers** — the only figures in this note are counted facts (LOC, test counts,
  file sizes, HTTP status codes), each traceable to a command.
