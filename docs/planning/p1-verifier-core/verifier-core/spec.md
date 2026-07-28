# Aspect Spec — verifier-core

**Feature:** `p1-verifier-core` · **Aspect:** `verifier-core` (the only aspect; this unit ships as
one PR, and its phases are strictly sequential)
**PRD:** `docs/planning/p1-verifier-core/prd.md` · **Written:** 2026-07-28
**Core-loop element:** ① verifiable task family + verifier

---

## Problem slice

The repo can run tests but cannot grade a patch. This aspect delivers the reward: a task contract,
a STRICT verifier and a WEAK verifier, the sandbox they execute in, verdict semantics that refuse
to render `UNVERIFIED` as a pass, an adversarial corpus proving the strict/weak differential is
real, and a structural guard keeping inference libraries off the reward path.

**User outcome:** the founder can grade a patch against a task and get a verdict grounded in a
pytest run — and can demonstrate, from the test suite alone, that six named cheats are rejected
and that the seventh is a documented residual.

## In-scope requirements

Lifted from the PRD's must-haves:

| # | Requirement |
|---|---|
| M1 | The task contract (`Task`), frozen, loaded only from an operator-controlled file |
| M2 | STRICT: checkout → apply patch (reject on test-path touch) → restore golden → run pytest → skipped-count zero → reward is exit status |
| M2b | Assert the **executed node-id set** equals `fail_to_pass + pass_to_pass`, each `fail_to_pass` reporting `passed` |
| M3 | WEAK: no confinement, no restore, measurement only — never trains anything |
| M4 | The sandbox: own minimal SBPL profile, network denied, writes confined to `/_sandbox/<run_id>/`, explicit timeout |
| M5 | Verdict semantics ported: `UNVERIFIED` above `PASS`, empty set reduces to `UNVERIFIED`, worst-status-wins |
| M6 | The provenance boundary as a structural test (return-type census of `Task` producers) |
| M7 | Adversarial corpus: cheats 1–5 and 7 assert STRICT-rejects-AND-WEAK-accepts; cheat 6 asserts accepted by both as the documented residual |
| M8 | AST inference guard scoped to the reward path, three porting traps, two anti-vacuity controls |
| M9 | `whetstone verify` emitting a verdict (requires subparser restructuring) |
| M10 | Determinism: same task + patch + seed → identical verdict |

Should-haves: **S1** CI asserts `sandbox-exec` really denies the network; **S2** the four
committed-document corrections (PRD § E); **S3** `UNVERIFIED` reachable and tested.

## Out-of-scope boundaries

`tasks/` ingestion and the on-disk task format; the base-model bake-off and `reports/baseline/`;
`PREREGISTRATION.md`; per-instance environment provisioning for real SWE-bench repos; any model
invocation, rollout, or training; the promotion gate; the honest number; everything post-horizon.
Also out: the `CHANGELOG.md` 0.1.0-without-a-tag discrepancy.

**No real SWE-bench instance is executed in this aspect.** All fixtures are synthetic: tiny
hand-authored repos with zero third-party dependencies.

## Acceptance criteria

Lifted verbatim in substance from the PRD. These are the failing tests, written before the code.

1. `uv run pytest tests/adversarial/` exits 0 — one fixture per cheat: cheats 1–5 and 7 assert
   **STRICT rejects AND WEAK accepts**; cheat 6 asserts both accept, as the documented residual.
2. **Cheat 7 specifically:** a patch touching no test path but adding `-k`/`--deselect` to
   `[tool.pytest.ini_options] addopts` is rejected by STRICT, and the test asserts the rejection
   reason is *the executed set did not match* — not an incidental failure.
3. `uv run pytest tests/test_no_inference_on_reward_path.py` exits 0, with **both** anti-vacuity
   controls: the walk observes real imports, **and** `_is_inference_import("whetstone.judge")` is
   `True`.
4. The guard resolves relative imports — a planted `from .judge import x` inside the reward path
   is caught.
5. `uv run whetstone verify --task <fixture> --patch <fixture>` emits a verdict and returns
   PASS→0, FAIL→1, UNVERIFIED→3, never colliding with the existing `USAGE_ERROR = 2`.
   `UNVERIFIED` never exits 0.
6. **Determinism:** same task + patch + seed → identical verdict over repeated runs.
7. **The reduction:** an empty verdict set reduces to `UNVERIFIED`; `{PASS, UNVERIFIED}` reduces
   to `UNVERIFIED`.
8. **The provenance boundary:** no public callable returning a `Task` accepts policy-produced data.
9. **The sandbox denies the network** — observed, not assumed.
10. **A sandbox failure or timeout reduces to `UNVERIFIED`, not `FAIL`.**
11. **A patch touching a path in `test_blobs` is rejected by STRICT before any test runs** — not
    merely "the tests failed afterwards".
12. `uv run ruff check .` and `uv run mypy src/` exit 0; CI green.

**Adversarial criterion (mandatory for reward work):** criteria 1, 2 and 11 are the adversarial
half. Every cheat fixture must be **watched failing before it is trusted**, per house style
(`tests/test_cli.py:52`), and each asserts *both* halves of the differential — a fixture that only
proves STRICT rejects could be rejecting for an unrelated reason.

## Dependencies and sequencing

- **Depends on:** P0 (merged). `uv sync` works; `uv run pytest` → 19 passed.
- **Blocks:** every later phase — P2 rollouts, P3 gate, P4 number.
- **Internal order:** verdict + task contract → sandbox → STRICT/WEAK → adversarial corpus →
  AST guard → CLI → doc corrections. The guard comes after the package exists so its
  `GUARDED_ROOTS` points at something real; the corpus comes after both verifiers so each fixture
  can assert the differential rather than one half.

## Open questions and risks

- **`sandbox-exec` on `macos-latest` is unverified.** The spike proves this machine only. If CI
  forbids it, the honest response is a loudly-named skip, never a silent green. Decide on
  evidence from the first CI run.
- **`sandbox-exec` is Apple-deprecated** with no Docker-free replacement. Isolate it behind
  `sandbox.py` so the mechanism is swappable; do not spread it across call sites.
- **The cheat enumeration is provisional, not exhaustive.** Cheat 7 was found by critiquing the
  PRD, after the roadmap had called the table complete. Treat the corpus as append-only, and do
  not describe it as covering everything.
- **The open class behind cheat 7:** which other inputs can the patch influence that `test_blobs`
  does not cover — environment variables, a `conftest.py` above the repo root, installed
  entry-point plugins? Phase 3 addresses the instance; the class stays open and is recorded here.
- `Verdict.axis` — provisionally dropped (Whetstone has one axis; a constant field misdescribes
  the structure). Revisit if a second axis appears.
