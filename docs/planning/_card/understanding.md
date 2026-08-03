# Understanding — feat p1-verifier-core

**Written:** 2026-07-28 · **Branch:** `feat/p1-verifier-core/aliz` · cut from `origin/master` @ `b8022d0`
**Upstream spec:** `docs/ROADMAP.md` § 4 "P1 — Task contract + verifier" (merged in PR #2)
**Core-loop element:** ① verifiable task family + verifier — the moat itself.

Every claim below carries a `file:line` or a command output. Where a committed document turned
out to be wrong, that is stated rather than smoothed over.

---

## 1. What the work is really asking

Build the **reward**, and prove it is a reward and not an opinion. Concretely: a task contract,
a STRICT verifier (the reward) and a WEAK verifier (measurement only), the sandbox they run in,
verdict semantics that cannot render an unverified result clean, a corpus of adversarial cheat
fixtures, and an AST guard that fails the build if an inference library reaches the reward path.

The reward is a **pytest process exit status** (`docs/ROADMAP.md:22-26`). No model is consulted
anywhere on this path, and after this slice that is enforced structurally rather than by
convention. `N` — the count of rollouts a weaker check would have scored as wins — is the
differential between the two verifiers (`docs/ROADMAP.md:84-86`).

**Guardrail check.** Reward stays execution-grounded (an exit status). Nothing leaves the box —
the sandbox spike below runs entirely locally and the verifier makes no network call at all; in
fact it *denies* the network to the process under test. No base model is trained, or even run,
in this slice. `UNVERIFIED` is handled by the ported reduction and never collapses into `PASS`.

---

## 2. The sandbox question — ANSWERED: Seatbelt is separable, and it works

This was the open question that could have reshaped the slice (`_card/issue.md` § Open questions
1). It is now closed on evidence.

### 2a. Dependency direction

`<sibling>/src/<pkg>/sandbox/seatbelt.py` (417 lines) imports, in full
(`seatbelt.py:44-56`):

```
os, re, subprocess, sys, tempfile, dataclasses, pathlib, typing   # stdlib
from the sibling project.snapshot.bth1 import UnsupportedPlatform               # an exception class
from the sibling project.trace import TraceWriter                               # OPTIONAL, default None
```

`scope.py:87-95` is **pure stdlib**. `launch.py:43-56` adds only `the sibling project.sandbox.seatbelt`,
`the sibling project.sandbox.scope`, and the same `UnsupportedPlatform`.

Nothing under `sandbox/` imports `the sibling project.replay`. The direction runs the other way:
`proxy.py:595-596` imports `the sibling project.sandbox.gate` and `the sibling project.sandbox.launch`, and
`cli.py:84,141,190,260` imports `seatbelt`. **The replay substrate depends on the sandbox; the
sandbox does not depend on the replay substrate.**

`TraceWriter` is a type annotation on an optional parameter — `run(..., trace: TraceWriter | None = None)`
(`seatbelt.py:346-353`), and the docstring states outright that *"Containment does not depend on
it: the boundary is the kernel's"* (`:357-358`).

**Verdict: `seatbelt.py` is liftable with two trivial edits** — substitute Whetstone's own
`UnsupportedPlatform` exception, and drop the `TraceWriter` import along with `record_denials`
(`:325`) or retype it. `gate.py` — the module carrying the `UNRESTORABLE_CONCURRENT_TURN`
behaviour the roadmap declines (`docs/ROADMAP.md:326-329`) — is **not** in that dependency set
and stays behind.

`run()` (`seatbelt.py:346-417`) is almost exactly the shape this slice needs: it takes a command,
a write `scope`, a `NetworkPolicy`, a `cwd` and a `timeout`, writes the profile to a temp file,
executes `[/usr/bin/sandbox-exec, "-f", profile, *command]` (`:398-404`), and returns
`SandboxResult(rc, stdout, stderr, profile, denials)`. `NetworkPolicy.deny_all()` exists
(`:128-129`). Note the default `timeout=30.0` (`:353`) — fine for a probe, almost certainly too
short for a pytest run, and a value this slice must set deliberately.

### 2b. Corrections to committed documents

- **`docs/ROADMAP.md` § 7's "Taken" table (`:303-311`) has a real gap.** It lists no sandbox
  module while `:54` requires a no-network sandbox. The table should gain a `sandbox/seatbelt.py`
  row. This is a documentation fix, not a design change.
- **`docs/planning/roadmap-and-task-family/prd.md:58` is half right.** *"the sibling project's Seatbelt sandbox
  and APFS `clonefile` snapshot work natively; no porting phase required"* — the Seatbelt half is
  confirmed (a two-line edit, not a porting phase). The `clonefile` snapshot half refers to
  `<sibling>/snapshot/`, which **is** part of the declined replay substrate (`docs/ROADMAP.md:320-322`).
  This slice takes the sandbox and does not take the snapshot machinery.

### 2c. Live spike — run on this machine, 2026-07-28

`/usr/bin/sandbox-exec` exists. A minimal profile (`(allow default)`, `(deny network*)`,
`(deny file-write*)` + one `subpath` allow) applied to a `python3` probe produced:

```
NET: denied (PermissionError)
WRITE in-scope: allowed (good)
WRITE out-of-scope: denied (PermissionError)
READ out-of-scope: allowed
```

Network denial and write confinement both hold. **Reads are not confined** — the probe read a
file outside the sandbox without obstruction. This is not a defect in the spike; the sibling project documents
it as a property of the profile: *"Reads are NOT scoped (`file-read*` is allowed wholesale) …
it contains what the child can change, not what it can see"* (`seatbelt.py:363-366`).

**Why that matters for the PRD, stated plainly:** the sandbox gives write-confinement, not
blindness. The operator-held tests are restored *into* the sandbox before pytest runs
(`docs/ROADMAP.md:60-63`), so code under test can read the assertions it must satisfy. The
verifier's guarantee is *"the unmodified operator tests genuinely passed"*, **not** *"the policy
never saw the tests"*. That is exactly cheat 6 (`docs/ROADMAP.md:109-118`), and this finding
sharpens why it is a residual: the information needed to special-case is available by
construction, not merely hard to withhold. The PRD must not claim read-blindness anywhere.

**Two risks to carry forward:** `sandbox-exec` is deprecated by Apple (it still works, and the sibling project
depends on it), and the CI runner must be confirmed to permit it — the spike proves this machine,
not `macos-latest`.

---

## 3. The AST guard — both documented traps confirmed, plus a third the roadmap misses

Source: `<sibling>/tests/test_verify_zero_llm.py`.

**Trap 1 — confirmed verbatim** (`:114-121`):

```python
def _is_inference_import(dotted: str) -> bool:
    root = dotted.split(".")[0]
    if root in _INFERENCE_CLIENTS:
        return True
    if root == "<the sibling package name>":
        parts = set(dotted.split("."))
        return bool(parts & _INFERENCE_FIRST_PARTY)
    return False
```

The string is hardcoded. Ported as-is, `whetstone.judge` passes straight through.
`_INFERENCE_FIRST_PARTY` (`:84-86`) is `{llm, judge, model, models, inference, completion,
prompt, prompts}`.

**Trap 2 — confirmed.** `_INFERENCE_CLIENTS` (29 entries: `openai`, `anthropic`, `torch`,
`transformers`, `vllm`, `ollama`, `langchain*`, `jax`, `tensorflow`, …) contains **no** `mlx`,
`mlx_lm`, `peft`, or `accelerate`. Whetstone installs exactly those, so the inherited list has a
hole shaped like our own stack.

**Trap 3 — NOT documented anywhere, and it defeats the guard from inside** (`:105-111`):

```python
elif isinstance(node, ast.ImportFrom):
    if node.level == 0 and node.module is not None:
        names.append((node.module, node.lineno))
```

`node.level == 0` means **relative imports are invisible to the walk**. `from .judge import score`
inside the reward-path package records nothing. The sibling project gets away with it because its first-party
detection keys on the dotted `<sibling>.judge` form, but a package whose internal modules import each
other relatively — which Whetstone's verifier package naturally will — has a silent bypass.
The port must resolve relative imports to their absolute dotted path from the file's package
position. This is a third trap for `docs/ROADMAP.md:166-174` to record.

**Anti-vacuity: the roadmap's claim is verified.** `_modules()` (`:89-92`) asserts the file list
is non-empty. `test_the_guard_actually_sees_the_imports_the_layer_makes` (`:156-175`) asserts the
walk observes real imports (`the sibling project.replay`, `the sibling project.corpus`, `the sibling project.interop`) — it asserts the walk
**sees imports**, and never that `_is_inference_import` **fires**. So Whetstone needs the second
control: a synthetic `whetstone.judge` import that the predicate must return `True` for.

Good news for scoping: the walk uses `GUARDED_ROOTS` + `rglob("*.py")` (`:90`), so the
reward-path-scoped guard the roadmap wants is the mechanism the sibling project already uses — no invention
needed. And `ast.walk` (`:105`) does catch function-local imports, so indenting an import is not
a bypass.

---

## 4. Verdict semantics and the provenance boundary

**`verify/verdict.py` — liftable near-verbatim.** Stdlib only (`dataclasses`, `enum`, `typing`).
`Status` has five members; `_RANK = {NOT_COVERED: -1, PASS: 0, WARN: 1, UNVERIFIED: 2, FAIL: 3}`;
`reduce()` filters `NOT_COVERED` *before* ranking and returns `UNVERIFIED` for an empty set —
"including one that is empty only AFTER the filter". The `Verdict` dataclass carries
`axis`/`kind`/`status`/`observed`/`expected`/`message`; `axis` is sibling-specific ("A1"/"A2"/"A3")
and is the one field needing a decision for Whetstone.

**`verify/invariants.py` — the portable asset is the TEST, not the module.** The module implements
a `read-only` path-scope policy over raw bytes; Whetstone's boundary is different in kind (the
operator holds golden *test file contents*, restored post-patch). What ports exactly is
`tests/test_invariants.py:55 test_no_invariant_is_ever_sourced_from_a_trace`, and its mechanism is
better than expected: it takes a census of public callables in the module, selects the ones whose
**return annotation** produces policy, and asserts that set is exactly the known-safe producers
and that each takes only an operator-controlled path. Keying on the return type rather than the
name is what makes it durable — a future trace-to-policy loader still returns the policy type and
so still trips it.

Whetstone's analogue, and it should be written in this slice: **no callable that produces the
operator-held test blobs may accept policy-produced data (a patch, a rollout, a diff).** That is
the provenance boundary as a structural test rather than a convention.

---

## 5. The SWE-bench inheritance is thinner than the documents imply

`<sibling>/eval/instances/pool.json` holds **166 records** — the number in
`docs/planning/roadmap-and-task-family/prd.md:149` is real and reproducible, and
`eval/instances/selection.py:4` states it independently. Each record's fields, in full:

```
instance_id, repo, base_commit, problem_statement, task_string, is_control
```

**There is no `FAIL_TO_PASS`, no `PASS_TO_PASS`, no test patch, and no install or test command.**
Whetstone's task contract requires the first three (`docs/ROADMAP.md:42-48`). And nothing in
`eval/` ever executes an instance's tests: a grep for `pytest`/`pip install`/`conda`/`docker`
across `eval/**/*.py` returns only the string `"pytest-dev/pytest"` as a repo name
(`eval/instances/selection.py:40`). The `minting_driver/` does clone repos
(`batch.py:127,188`, `entrypoint.py:86`) but to run MCP agent sessions against them — it
provisions **no Python environment** for the repo under test.

**Conclusion:** Whetstone inherits an eligibility filter, a seeded offline draw, and a list of 166
task *ids* — not an execution harness, and not the fields the reward needs. `docs/ROADMAP.md:311`
is honest about this (it claims only "the eligibility filter and the … draw"); the risk is a
reader assuming more. Two consequences:

1. **This slice should use synthetic fixture repos** — tiny, hand-authored, zero third-party
   dependencies. Nothing is lost: the adversarial corpus exists to prove cheats 1–5 are killed and
   that the weak/strict differential is real, and a synthetic repo demonstrates that as rigorously
   as django does, while running in milliseconds and staying deterministic.
2. **P1 exit criterion 4 (`tasks/` from both sources) carries hidden work** — re-fetching
   `FAIL_TO_PASS`/`PASS_TO_PASS`/test patches from the SWE-bench dataset, plus per-instance
   environment provisioning on macOS without Docker. That is a real, unestimated cost sitting in a
   later slice, and it should be recorded as an open question rather than discovered in P2.

---

## 6. Whetstone's own surface — what this slice touches

| File | Change |
|---|---|
| `src/whetstone/cli.py` | **Restructure.** `build_parser()` (`:28-37`) has no subparsers, and `main()` (`:51-72`) falls through to `USAGE_ERROR` on any parse that succeeds. Adding `verify` needs `add_subparsers()` plus dispatch. The module docstring's contract — *"Commands appear here only when something stands behind them"* (`:5-6`) — is now satisfiable for the first time. |
| `src/whetstone/` | **New package** for the verifier. Its layout determines the AST guard's `GUARDED_ROOTS`. |
| `tests/` | **New** `tests/adversarial/` — picked up automatically, since `pyproject.toml:53` sets `testpaths = ["tests"]`. Plus `tests/test_no_inference_on_reward_path.py`. |
| `pyproject.toml` | Likely untouched. `dependencies = []` (`:20`) with the comment that *"nothing on the future reward path may pull in an inference library"* (`:17-19`) — the verifier is stdlib-only, so this holds. |
| `.github/workflows/ci.yml` | Likely untouched — it already runs `ruff check .`, `mypy src/`, and `pytest` (`:29-31`). Watch for whether `sandbox-exec` is permitted on `macos-latest`. |
| `.gitignore` | Untouched. `/_sandbox/` is already pre-declared (`:23`). |

**House style the new tests must match** (from `tests/test_cli.py`): a module docstring naming
*the failure this prevents*; test names as full sentences; `capsys`/`tmp_path` fixtures; assertions
on **both** a return code and observable output; and an explicit **anti-vacuity control** carrying
a docstring noting it was *"watched failing … before being trusted"* (`test_cli.py:51-56`). That
last convention is exactly what the adversarial corpus needs, and it is already the house habit.

**Tooling constraints:** ruff selects `E,F,I,UP,B,SIM,RUF` at line-length 100
(`pyproject.toml:38-43`); `RUF100` makes an unused `# noqa` an error. mypy is `strict` with
`warn_unused_ignores` over `files = ["src"]` only (`:45-50`) — tests are not type-checked.

---

## 7. Ambiguities and open questions for the interview

1. **Where does the verifier package live**, and what exactly are the guard's `GUARDED_ROOTS`?
   The scope must be narrow enough to stay true once `mlx-lm` is legitimately installed elsewhere.
2. **The `axis` field** on the ported `Verdict` — keep, rename, or drop for a domain with one axis?
3. **Sandbox timeout and seed.** `docs/ROADMAP.md:54` says "fixed seed" but does not say what is
   seeded. Candidates: `PYTHONHASHSEED`, disabling any test-order randomisation, and pinning
   pytest's own collection order. The sibling project's `seatbelt.run` pins nothing (no env control in
   `:398-404`) — this is Whetstone's to design, and the determinism acceptance criterion depends
   on it.
4. **What is a verdict, concretely, for one task?** STRICT and WEAK each produce an exit status;
   the reduction folds sub-checks. Which sub-checks exist — patch-touches-test-path,
   skipped-count-is-zero, `fail_to_pass`, `pass_to_pass` — and does each get its own `Verdict`?
5. **Cheat 6's fixture.** The roadmap requires asserting it is accepted by both verifiers as the
   documented residual (`docs/ROADMAP.md:156-158`). That is a test asserting a *known weakness*;
   its naming and docstring need care so a future reader cannot mistake it for coverage.
6. **`sandbox-exec` on `macos-latest`** — unverified. If CI forbids it, the adversarial suite needs
   a documented skip path, and a skip that silently green-lights CI would be its own false pass.
7. **Deferred-slice cost** (§ 5.2) — record, don't solve here.

## 8. Unrelated discrepancy noticed

`CHANGELOG.md:16` heads a `[0.1.0] - 2026-07-27` section and links a release tag, but `git tag`
returns nothing and `CLAUDE.md` states there are no tags. Either the release was never cut or the
changelog is ahead of the code. Out of scope for this slice; flagged so it is not lost.
