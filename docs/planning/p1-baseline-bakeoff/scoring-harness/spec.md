# Aspect spec — `scoring-harness`

**Parent PRD:** `docs/planning/p1-baseline-bakeoff/prd.md` (M3, M4, M5, M6, S2, § 7).
**Sequence:** second. Depends on `generation`'s model boundary; blocks `report` and `the-run`.

## Problem slice

`whetstone verify` cannot produce a trustworthy bake-off number: `cli.py:248-250` calls
`verify_strict` with **no `interpreter`**, so every task's declared `environment.pins` are ignored
and the tests run under the verifier's own `sys.executable`. And `verify_weak` cannot run a pinned
task at all (`weak.py:57-63`), which makes the pre-registered baseline `N`
(`PREREGISTRATION.md:96-109`) uncomputable.

The outcome: a runner that provisions each task's declared environment, grades one generated patch
under **both** verifiers, records what happened with its wall-clock, and proves in the same run that
it could have reached both `PASS` and `FAIL`.

## In scope

1. **`verify_weak` gains `interpreter: Path | str | None = None`** — additive, defaulting to today's
   behaviour. WEAK remains measurement-only and trains nothing (`docs/ROADMAP.md:74-79`).
2. **Per-task provisioning**, via `gates.check_environment` (`gates.py:609-616`), which verifies by
   import probe rather than accepting install-exit-0 (`:617-668`). Interpreters are **cached per
   distinct pin set** — 66 tasks share far fewer environments than they have manifests.
3. **The runner**: for each (candidate, task), call `verify_strict` **and** `verify_weak`
   in-process with that interpreter. Never shell out to `whetstone verify`.
4. **Per-result records** (M6): status, the sub-verdict `kind`s, the executed-node count, and
   separate wall-clock for generation, STRICT and WEAK. `StrictResult` carries no duration by design
   (`strict.py:98-101`) and nothing in this repo has ever recorded one.
5. **The control arm** (M5): per candidate, on the same task set with the same provisioning, the
   inert patch must reach `FAIL` and a reference patch must reach `PASS`.
6. **Reference-patch re-derivation** — from `provenance.commit` vs `provenance.parent` in the donor
   checkout. **This was the first task of this aspect**, because M5's value halves if it is
   unreachable. Declared fallback: source A's gold patch from `tasks/public/pool.json`.

   > **RETIRED 2026-07-31, with measurement.** Re-derivation works, and the risk is closed:
   > **66 of 66** manifests produce a non-test reference patch that applies cleanly to the
   > checkout `verify/repo.py` builds (`clone --no-checkout` → `checkout --detach base_commit` →
   > `git apply --whitespace=nowarn --check`), in ~39 s for the whole corpus. Three were carried
   > all the way through the **shipped STRICT verifier**: `inert_patch()` → **FAIL**, re-derived
   > reference → **PASS**, executed set equal to declared, zero skips. All 132 donor shas are
   > still reachable, and the whole procedure ran under a `(deny network*)` Seatbelt profile.
   >
   > The mechanism already existed: `derive.gold_patch()` (`derive.py:194-208`) diffs
   > parent→commit restricted to non-test paths *precisely so* the reference cannot trip
   > `patch-scope`, and `donor._classify()` (`donor.py:191-210`) does the splitting. The harness
   > re-uses those rather than reimplementing them, and asserts
   > `set(paths).isdisjoint(task.test_blobs)` as a pre-flight — it never fired across 66, costs
   > nothing, and turns the exact failure this spec worried about into a skip-with-reason.
   >
   > **First real timing evidence in this repository:** ~2–4 s per task end-to-end including venv
   > provisioning on a warm uv cache. That materially lowers R2 — the verifier half looks far
   > cheaper than the "402 sandboxed runs will dominate" estimate feared — but it is three tasks
   > on one machine with a warm cache, so aspect 4's probe still governs and this figure does not
   > replace it.
   >
   > **Two operational constraints it also settled**, both binding on the runner: the control arm
   > must go through the library (`environment.capture()` → `verify_strict(interpreter=…)`) rather
   > than `whetstone verify`, which passes no interpreter; and `capture()` needs a checkout at
   > `base_commit` to read `uv.lock` from, so provisioning and verification should share one
   > checkout — the `import_roots` / inert-checkout lesson again.
7. **Resumability** (S2): checkpoint per (candidate, task) so an interrupted overnight run resumes.

## Out of scope

- Any aggregation, ranking, count, coverage figure, or `N` computation — aspect 3 owns every number.
- The report file — aspect 3.
- Downloading weights or executing a real bake-off — aspect 4.
- Any change to STRICT's semantics. `verify_strict` is **called**, never modified.

## Acceptance criteria (written first)

**AC1 — pinned verdicts, demonstrated.**
A task whose declared pins change the outcome reaches `PASS` under the provisioned interpreter and
`FAIL` under an unpinned one — the shape `tests/test_environment_pins.py` already proves, now
reached through the runner rather than hand-assembled in a test.

**AC2 — `verify_weak(interpreter=...)` is additive and the differential survives.** *(adversarial)*
The ten-cheat corpus (`tests/adversarial/test_cheats.py`) stays green: the killed cheats are still
STRICT-rejected **and** WEAK-accepted, and cheats 6 and 10 remain asserted as documented residuals.
A signature change on the WEAK path that flattened the differential would silently zero every future
`N` — this is the test that stops it.

**AC3 — the reward path stays model-free.**
`tests/test_no_inference_on_reward_path.py` passes with `weak.py` modified; the AST guard sees the
change and the first-party predicate still fires (its own controls, `:296-331`).

**AC4 — exceptions become `UNVERIFIED`, never `FAIL` and never a crash.** *(adversarial)*
`UnsupportedPlatform` (`sandbox.py:66`) and provisioning `Ineligible` (`gates.py`) are caught and
recorded as `UNVERIFIED`, following `cli.py:251-259`. A sandbox timeout is recorded as `UNVERIFIED`
with `executed=None` (`sandbox.py:262-282`) and **never** folded into the failure count — a task
that could not be graded is not a task the base got wrong.

**AC5 — the control arm fails loudly.** *(adversarial)*
Given a deliberately broken harness (an extractor stubbed to return no diff), the control arm
detects it: the run is marked `UNVERIFIED` and no ranking is emitted. This is the test that makes an
all-zero result attributable to the bases rather than to the plumbing, and it is the single
highest-value assertion in this aspect. It must be watched failing.

**AC6 — both verdicts recorded per rollout, with the `N` ingredients intact.**
Every record carries the STRICT status, the WEAK status, and the sub-verdict kinds, so aspect 3 can
compute `N := count(WEAK == PASS and STRICT == FAIL)` (`PREREGISTRATION.md:99`) without re-running
anything.

**AC7 — `patch-apply` is distinguishable from a substantive failure.**
A result whose only verdict is `kind="patch-apply"` (`strict.py:171-183`) is recorded distinctly
from a result that ran tests and failed. Both are `FAIL`; only one means the model produced no
usable diff.

**AC8 — resumption changes nothing.**
Interrupting after *k* results and resuming produces a record set identical to an uninterrupted run
over the same inputs.

**AC9 — timings are recorded and are not verdict-bearing.**
Wall-clock appears in the records; identical inputs still produce identical *verdicts*, so
`test_the_verdict_is_identical_across_repeated_runs`'s discipline (`tests/test_strict.py:349-372`)
is not weakened by anything this aspect adds.

**AC10 — the gates stay green.** `ruff`, `mypy src/`, `pytest`, `whetstone --help` all exit 0.

## Dependencies & sequencing

- Depends on `generation` (the model boundary; the runner takes a `Generator`, and every test here
  passes a stub — this aspect never needs `mlx` installed).
- Blocks `report` (which consumes the records) and `the-run`.
- The corpus lives outside this worktree at `/Users/aliz/dev/at/whetstone/tasks/local/` (gitignored
  user data). The runner takes a **path argument**; manifests are not copied in.
- Source-A verification `git clone`s from GitHub on every run (`repo.py:66-84`, no cache), so tests
  covering source A must use local fixture repos, never the network.

## Open questions / risks

- **Runtime is unmeasured and probably dominates.** ~402 sandboxed pytest runs, each with a clone
  and up to 232 node ids, plus a venv build per distinct pin set. Aspect 4's probe measures it; this
  aspect must not assume it is cheap, and interpreter caching is the main lever.
- **Re-derivation of source-B reference patches may be unreachable offline** — resolve first,
  fallback declared above.
- **Provisioning may fail for real donor pin sets** in ways the fixture-based tests never see. That
  outcome is a coverage figure, not a reason to loosen anything: `docs/ROADMAP.md:434-435` — the fix
  is a more reliable sandbox, never a looser check.
