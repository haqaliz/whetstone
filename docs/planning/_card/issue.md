# feat p1-verifier-core — The task contract and the strict/weak verifier core (ROADMAP P1, slice 1)

## Source

**FALLBACK path.** No GitHub issue exists. `gh issue list --state all` returns "No Issues"
against `haqaliz/whetstone` (Issues reachable, repo empty of them), and the `id` is a slug,
not a number. Per `references/gather-context.md` §0 this is the expected case for this repo —
the same path P0 took (card preserved in history at `3662255`).

The upstream spec is committed: `docs/ROADMAP.md` § 4 "P1 — Task contract + verifier", merged
to `master` in PR #2 (`347655a`). The roadmap, not this card, is the authority on P1's exit
criteria.

## Brief

Reproduced verbatim from the `whetstone-next` handoff the user acted on by invoking
`wbf feat p1-verifier-core`:

> Build the first slice of ROADMAP P1 (docs/ROADMAP.md:144-176): the task contract and the
> strict/weak verifier core, so the reward exists and is provably ungameable for cheats 1-5.
> In scope: the task contract fields (ROADMAP.md:42-48); STRICT and WEAK as specified at
> :56-72; the sandbox at /_sandbox/<run_id>/ with no network and a fixed seed; Belay's verdict
> semantics ported (UNVERIFIED ranked above PASS, empty set reduces to UNVERIFIED — take the
> test at belay tests/test_invariants.py:55, not just the module); the adversarial cheat corpus;
> and the AST inference-guard. Out of scope for this slice: tasks/ ingestion, the base-model
> bake-off, reports/baseline/, and PREREGISTRATION.md — later P1 slices.
>
> Caveat for the dig: ROADMAP § 7's "Taken" table lists no sandbox module even though the
> verifier needs a no-network sandbox, while the older PRD (docs/planning/roadmap-and-task-
> family/prd.md:58) assumed Belay's Seatbelt ports for free — that claim predates the § 7
> decline of the replay substrate and is unverified. Establish whether src/belay/sandbox/
> seatbelt.py is separable from replay/ before designing around it. Also: real SWE-bench
> instances need per-task Python environments and the usual harness answer is Docker, which the
> macOS-only decision rules out — build this slice's corpus from synthetic fixture repos with no
> third-party dependencies, and record the environment-provisioning question as open rather than
> assuming it away. Finally, ROADMAP.md:166-174 documents two verified AST-guard porting traps
> (the hardcoded `root == "belay"` first-party gate, and _INFERENCE_CLIENTS missing mlx/mlx_lm/
> peft/accelerate); honour both.
>
> Acceptance criteria, written first — the repo is test-first:
> 1. `uv run pytest tests/adversarial/` exits 0, asserting per cheat fixture that cheats 1-5 are
>    STRICT-rejected AND WEAK-accepted (proving the differential is real, not vacuously zero),
>    and that cheat 6 is accepted by both as the documented, expected residual.
> 2. `uv run pytest tests/test_no_inference_on_reward_path.py` exits 0 — an AST walk scoped to
>    the reward-path packages, carrying both anti-vacuity controls: one asserting the walk
>    really observes imports, and a second asserting the first-party predicate actually fires on
>    a synthetic `whetstone.judge` import.
> 3. `uv run whetstone verify --task <fixture> --patch <fixture>` emits a verdict, with
>    UNVERIFIED never collapsed into PASS.
> 4. A determinism test: same task + same patch + same seed → identical verdict.
> 5. `uv run ruff check .` and `uv run mypy src/` still exit 0, and CI stays green on master.

## The upstream spec (authoritative)

`docs/ROADMAP.md:144-184`, P1. Its six exit criteria, and which this slice takes:

| # | P1 exit criterion | This slice |
|---|---|---|
| 1 | `uv run pytest tests/adversarial/` exits 0 — cheats 1–5 STRICT-reject AND WEAK-accept; cheat 6 accepted by both as documented residual | **In** |
| 2 | `uv run pytest tests/test_no_inference_on_reward_path.py` exits 0 — reward-path-scoped AST walk + anti-vacuity controls, honouring the two porting traps (`:166-174`) | **In** |
| 3 | `uv run whetstone verify --task <fixture> --patch <fixture>` emits a verdict | **In** |
| 4 | `tasks/` holds instances from both sources with committed provenance | **Deferred** — later P1 slice |
| 5 | A baseline bake-off report exists under `reports/baseline/` | **Deferred** — needs a base model |
| 6 | `PREREGISTRATION.md` is committed | **Deferred** — later P1 slice, before any training run |

The verifier spec itself is `docs/ROADMAP.md:52-93` (STRICT / WEAK / the provenance boundary /
the definition of `N`); the task contract fields are `:42-48`; the cheat enumeration and its
residual are `:98-118`.

**P1's pivot signal** (`:182-184`) belongs to the bake-off, not to this slice: *"if no candidate
base solves any held-out task, expert iteration has nothing to bootstrap from. Pivot to an
easier task stratum or a larger base — not to a looser verifier."* This slice cannot trigger it,
because it runs no model at all.

## Shipped state this builds on

- **P0 merged** (PR #3 `3662255`, plus PR #4 `b8022d0`). `master` @ `b8022d0`.
- `src/whetstone/__init__.py` (20 L) + `src/whetstone/cli.py` (72 L) — the CLI exposes exactly
  `--help` and `--version`; there are no subcommand stubs. `verify` would be the first subcommand.
- `uv run pytest -q` → **19 passed** (verified in this worktree, 2026-07-28). CI green on
  `macos-latest`, last three runs ok.
- Zero runtime dependencies; `mlx-lm` is an **optional** group proven only to resolve and import
  in CI (`docs/planning/p0-scaffold/prd.md` decision 2). Nothing sits on a reward path today
  because no reward path exists yet.

## Open questions carried in from the selection (for the dig to close)

1. **Is Belay's Seatbelt sandbox separable from the declined replay substrate?**
   `docs/ROADMAP.md` § 7's "Taken" table lists **no** sandbox module, yet the verifier requires a
   no-network sandbox (`:54`). `docs/planning/roadmap-and-task-family/prd.md:58` asserted
   *"Belay's Seatbelt sandbox and APFS `clonefile` snapshot work natively; no porting phase
   required"* — but that predates § 7's decline and was never re-verified.
   `~/dev/at/belay/src/belay/sandbox/seatbelt.py` exists (17.9 KB) alongside `gate.py`,
   `launch.py`, `scope.py`. Establish the dependency direction before designing around it.
2. **Per-task environment provisioning.** Real SWE-bench instances need per-instance Python
   environments; the standard harness answer is Docker, which the macOS-only platform decision
   (`docs/planning/roadmap-and-task-family/prd.md:58`) rules out. This slice can sidestep it with
   synthetic fixture repos that have no third-party dependencies — but the question must be
   recorded as open, not assumed away, because P1 exit criterion 4 and all of P2 depend on it.
3. **The two AST-guard porting traps** (`docs/ROADMAP.md:166-174`) are already verified against
   Belay's source. Confirm they still hold, and design the second anti-vacuity control that
   Belay itself lacks.

## Related work

- **PR #3** (`3662255`) — P0 scaffold. The direct upstream; its `docs/planning/p0-scaffold/`
  artifacts are the format precedent.
- **PR #2** (`347655a`) — `docs/ROADMAP.md` and its PRD. The authoritative spec.
- **Belay** (`~/dev/at/belay`) — v0.7.0, shipped. Source of the verdict semantics, the
  provenance boundary, the corpus metrics, the AST guard, and the eval instances
  (`docs/ROADMAP.md:303-311`). Its replay substrate is **declined** (`:313-336`).

## Note on this file

`docs/planning/_card/issue.md` is id-free by design (`whetstone-begin-fast` § Phase 1) and each
unit of work **overwrites** the previous one's card on its own branch. P0's card is preserved in
history at `3662255`. Flagged as a workflow wart, not a blocker.

## Attachments

None.
