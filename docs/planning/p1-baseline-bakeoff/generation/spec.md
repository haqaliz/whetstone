# Aspect spec — `generation`

**Parent PRD:** `docs/planning/p1-baseline-bakeoff/prd.md` (M1, M2, M7b partially, M9, M11, § 7).
**Sequence:** first. Aspects 2–4 all depend on the boundary this one defines.

## Problem slice

The repository has never invoked a model. To score a base against the verifier, something must turn
a `Task` into a patch string — and that something is the first inference-carrying code in the tree,
which is exactly the code the project's central guardrail exists to keep away from the reward.

The outcome: a package that produces a unified diff from a task, is testable with **no `mlx`
installed**, and is provably outside the reward path — with a guard that stays true as the tree
grows rather than one that silently stops describing it.

## In scope

1. **A new package `src/whetstone/bakeoff/`** — a *sibling* of `verify/` and `tasks/`, never nested
   under either (`GUARDED_ROOTS` is walked with `rglob`,
   `tests/test_no_inference_on_reward_path.py:77`). Nothing under `verify/` or `tasks/` may import
   it; the dependency runs one way only.
2. **An injectable model boundary** — a protocol (`Generator`, or similar) with a single
   generate-from-prompt method. The MLX implementation is one adapter behind it; every test
   substitutes a stub. No module-scope `import mlx_lm` anywhere the suite imports unconditionally.
3. **The prompt contract** — what a base is shown, built from the `Task` alone. Proposed minimum:
   `problem_statement` plus the declared `fail_to_pass` node ids. It is **content-hashed**, and the
   hash is part of what aspect 3 records as provenance.
4. **The diff extractor** — model text → unified diff string, or an explicit "no diff found"
   outcome. This is the part that must never fail silently (see AC4).
5. **The MLX adapter** — `mlx_lm.load()` against a **local directory** plus `revision`, greedy
   sampling (the default, `generate.py:386`), never a bare repo id at generate time.
6. **The partition guard (net-new test)** — every package under `src/whetstone/` is either in
   `GUARDED_ROOTS` or on an explicit exemption list carrying a written reason.
7. **`[[tool.mypy.overrides]]`** for `mlx_lm.*` / `mlx.*`.
8. **A `.gitignore` rule** covering model weights / caches.

## Out of scope

- Provisioning, verification, scoring, timing, retries — aspect 2.
- The report, the selection rule, any number — aspect 3.
- Downloading weights or running any real model — aspect 4.
- Any change to `verify/` or `tasks/`. (`weak.py`'s parameter belongs to aspect 2.)

## Acceptance criteria (written first)

**AC1 — the package is outside the reward path, and stays outside.**
`tests/test_no_inference_on_reward_path.py` passes unchanged, with `GUARDED_ROOTS` **not widened**
(`CONTRIBUTING.md:20`). A test asserts the guarded set was not extended to include `bakeoff`.

**AC2 — the partition guard catches what the existing guard cannot.** *(adversarial)*
Today, adding a sibling package that imports `mlx_lm` leaves the guard green while its coverage
silently stops describing the tree. The new test must:
- enumerate every package under `src/whetstone/` and assert each is guarded **or** explicitly
  exempted with a reason;
- **fail** against a synthetic tree containing an unlisted package — watched failing, per
  `CONTRIBUTING.md:53-60`;
- assert its own enumerated set is **non-empty** (a walk over nothing passes vacuously).

**AC3 — the suite runs green with `mlx` absent.**
`uv run pytest` passes in an environment where `importlib.util.find_spec("mlx_lm") is None` — this is
CI's actual state (`.github/workflows/ci.yml:32` runs under plain `uv sync`). Any mlx-requiring test
skips **loudly**, in the style `tests/conftest.py:66-69` demands and `ci.yml:33-74` models; a silent
skip is treated as the same class of lie as rendering `UNVERIFIED` as `PASS`.

**AC4 — a non-diff response is reported as such, never as an empty patch.** *(adversarial)*
Given model output that is prose, a fenced code block containing no diff, or an empty string, the
extractor returns an explicit no-diff outcome. It must **not** return `""`: `verify_strict(task, "")`
is charged `FAIL` at `patch-apply` (`liveness.py:14-20`), indistinguishable from a wrong fix — the
precise confusion that would make P1's pivot signal unreadable. A test asserts the two paths are
distinguishable at the type level.

**AC5 — extraction is not credulous.** *(adversarial)*
Model output containing a diff that touches a path in `task.test_blobs` is extracted **unmodified**
and handed on. The extractor must not sanitise, rewrite, or drop such a hunk: STRICT's `patch-scope`
refusal (`strict.py:524-533`) is the defence, and an extractor that quietly repaired the patch would
convert a caught cheat into an uncaught one. The test asserts the extracted diff still contains the
held path.

**AC6 — the prompt contract is deterministic and hashed.**
The same `Task` yields a byte-identical prompt across calls and processes, and its hash is stable.

**AC7 — generation is deterministic under the stub, and greedy under MLX.**
Two runs with the same stub produce identical output. The MLX adapter requests greedy decoding and
loads from a local path with `revision` pinned; a test asserts it never passes a bare repo id.

**AC8 — weights cannot be committed.**
`git check-ignore -v` reports the weights/cache path ignored, proven the way
`tests/test_tasks_layout.py:36-43` proves an ignore rule and honouring the trailing-slash trap
(`:15-19`).

**AC9 — the gates stay green.** `uv run ruff check .`, `uv run mypy src/`, `uv run pytest`, and
`uv run whetstone --help` all exit 0 (`CONTRIBUTING.md:36-50`).

## Dependencies & sequencing

- Depends on nothing outside the current tree.
- Blocks aspects 2, 3 and 4.
- Naming trap: no module the guarded roots import may be named exactly `model`, `models`, `llm`,
  `judge`, `inference`, `completion`, `prompt` or `prompts`
  (`tests/test_no_inference_on_reward_path.py:134-136`, exact component match). Nothing guarded
  should import this package at all, but the names are cheap to avoid.

## Open questions / risks

- **The prompt contract has no precedent.** Problem statement + failing node ids is the smallest
  defensible choice. It must be *fixed and disclosed*, not tuned — the anti-tuning discipline is
  M7b and is enforced in aspect 4.
- **`mlx_lm`'s API surface is version-coupled.** Verified against `mlx-lm==0.31.3`
  (`uv.lock:485`): `mlx_lm.utils.load(...)` and `mlx_lm.generate.generate(...)`, sampler injected as
  a callable rather than a `temperature=` argument. Pin the expectation; do not assume across
  versions.
- Whether the exemption list in AC2 lives in the test or in a committed data file is an
  implementation choice; either way the *reason* must be written down, not implied.
