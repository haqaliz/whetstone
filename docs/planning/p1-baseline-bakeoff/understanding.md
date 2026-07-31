# Understanding — p1-baseline-bakeoff

**Written:** 2026-07-30, before any PRD work, from five parallel read-only digs plus direct
reading. Every claim carries a `file:line`. Where a dig measured something on this machine it is
labelled **MEASURED**; where it computed a consequence, **ESTIMATE**. Nothing here is quoted from
memory.

---

## 1. What the work is really asking

`docs/ROADMAP.md:354` is the entire committed specification of the deliverable:

> `- A baseline bake-off report exists under `reports/baseline/``

That is one line, and it is the *only* one. There is **no content schema, no field list, and no
format** for this report anywhere in either authoritative document. So the real ask is larger than
the sentence: to close P1's last criterion this slice must build, from nothing,

1. a **generation surface** — a model, a prompt, and a diff extractor — which does not exist in any
   form (`src/` contains no inference code, and `pyproject.toml:20` declares `dependencies = []`);
2. a **provisioning + scoring harness** that turns a corpus into per-(base, task) verdicts, which
   also does not exist (`src/whetstone/cli.py` has exactly two subcommands, `verify` and `mine`);
3. the **report and its schema**, which this slice must define; and
4. a coordinated **documentation correction**, because the project's status blocks currently assert
   in several places that no number about a model exists — and this slice makes that false.

The second-order ask, which is the part that actually needs care: this is the first slice whose
output is a *claim*, and a pre-registration is already committed that binds what may be claimed.

## 2. Where it sits on the core loop

`CLAUDE.md` § *The core loop* names five elements. This slice touches ① and ④ and nothing else:

- **① verifiable task family + verifier** — it becomes the verifier's first programmatic caller,
  and the first caller to exercise the pinned-environment path end-to-end.
- **④ signed morning report** — it is the ancestor of that artifact: the first report this project
  publishes, and the one that fixes the shape later reports inherit.
- **② the nightly loop, ③ the promotion gate** — explicitly *out*. No training, no LoRA, no
  promotion decision. The bake-off samples an **untrained** base and writes a number down.
- **⑤ local + private** — preserved, with one new pressure described in § 6.

**How the reward stays execution-grounded.** It does not change at all. The reward is
`verify_strict` (`src/whetstone/verify/strict.py:112-120`), whose docstring is explicit that it
*"resolves nothing and installs nothing"* (`:136-137`). This slice adds a *caller* and a
*generator*, both strictly upstream of it: the model produces a patch string, and the verifier
grades it by re-execution exactly as it does today. **No model appears anywhere on the reward
path**, and no model's opinion enters any verdict. The one-directional dependency — bake-off →
verify, never the reverse — is what keeps that true, and § 5 records how it is enforced.

**`UNVERIFIED` is still not a win.** `verdict.py:64-70` ranks `UNVERIFIED` (2) above `PASS` (0), and
`PREREGISTRATION.md:86-90` defines `solved` as STRICT `PASS` only. The report must count
`UNVERIFIED` into coverage's denominator and never into either the solved or the failed column
(`PREREGISTRATION.md:111-114`).

## 3. The one distinction this slice lives or dies on

**This bake-off is base *selection*. It is not the pinned baseline.** The two are conflated in the
prose of both documents, and the conflation is load-bearing against us:

| Cite | Says |
|---|---|
| `PREREGISTRATION.md:126-128` | the pinned baseline is *"the untrained open base, scored on the **held-out set**"* |
| `PREREGISTRATION.md:242-247` (§7.1) | **the held-out split does not exist**, is open, and is closed in P3 *"before the split is used to score anything"* |
| `PREREGISTRATION.md:255-259` (§7.3) | the base is decided *by* the bake-off — so the bake-off cannot presuppose a base, which the pinned baseline does |
| `PREREGISTRATION.md:129-132` | *"measured once, re-measured never"*, binding the pinned baseline score, over five named pinned inputs |
| `docs/ROADMAP.md:370-371` | *"The bake-off scores candidate bases **per source**"* — plural, i.e. selection |

So a number computed over all 66 source-B tasks may not be published as the pinned baseline, and
must not be allowed to spend the once-only measurement. **Nothing in either document states this
obligation** — it is forced by the conjunction above, which is exactly why the report has to say
which measurement it is, in text a test can check.

### Contradiction found between the two authoritative documents

`docs/ROADMAP.md:387` states P1's pivot signal as *"if no candidate base solves any **held-out**
task"* — a set which `PREREGISTRATION.md:242-247` says does not exist and may not be used yet.
**These cannot both be honoured.** This is not papered over: the PRD must choose, and record which
task set the pivot signal was actually evaluated against. My reading is that `:387` predates the
pre-registration's § 7.1 and means "not the training set" loosely; the pre-registration is the
committed public document and wins, so the bake-off scores a declared, hash-recorded set that is
**not** called held-out. That resolution needs the user's assent, since it edits how a committed
pivot signal is read.

## 4. What exists to build on — MEASURED

**The reward, and its exact calling contract.**
`verify_strict(task, patch, *, sandbox_root, timeout, run_id=None, interpreter=None) -> StrictResult`
(`strict.py:112-120`). `StrictResult` carries `status`, `verdicts`, `executed` and is *deliberately*
free of paths, durations and output (`strict.py:98-101`) — so **the harness must record its own
timing**; nothing in the repo has ever recorded a duration (grep of `tasks/local-ledger.json`
returns no timing field, and `proven_at` is one shared stamp per donor, span 0.0s).

Four behaviours the plan depends on:

- A **malformed or non-applying patch is `FAIL`**, not `UNVERIFIED`, at `kind="patch-apply"`
  (`strict.py:171-183`) — *"an unusable patch is a wrong answer"*. A model emitting prose or a
  fenced block instead of a diff therefore scores identically to a wrong fix unless the harness
  inspects `verdicts[0].kind` itself. **It must**, or the pivot signal is unusable: "every candidate
  scored zero" and "the extractor never produced a diff" would be indistinguishable.
- A patch touching a held test is refused at `kind="patch-scope"`, status `FAIL`, before anything
  runs (`strict.py:524-533`), matched case-insensitively for macOS (`strict.py:510-521`).
- A **timeout is `UNVERIFIED`**, one `sandbox-run` verdict, `executed=None` (`sandbox.py:262-282`,
  `strict.py:274-279`) — never `FAIL`.
- `UnsupportedPlatform` (`sandbox.py:66`) and `Ineligible` from provisioning (`gates.py:609-616`)
  are **exceptions, not verdicts**; the harness must catch them and classify as `UNVERIFIED`,
  following `cli.py:251-259`.

**Provisioning is the caller's job, and the CLI does not do it.** `cli.py:248-250` calls
`verify_strict` with **no `interpreter`**, so `whetstone verify` today runs every task's tests under
the verifier's own `sys.executable`, silently ignoring `environment.python` and `environment.pins`.
A pinned bake-off therefore **cannot shell out to `whetstone verify`** — it must call `verify_strict`
in-process with a provisioned interpreter, the pattern `liveness.prove_live` (`liveness.py:97`) and
`tests/test_environment_pins.py:257-274` already demonstrate. `gates.check_environment` (`gates.py:609-616`)
is the existing provisioner that takes a pin list and returns `Provisioned.interpreter`; it verifies
by **import probe**, refusing install-exit-0 as evidence (`gates.py:617-668`).

**The corpus.** 66 source-B manifests exist **only in the primary checkout** at
`/Users/aliz/dev/at/whetstone/tasks/local/` (45 `contig`, 21 `belay`) — gitignored at
`.gitignore:22`, so **absent from this worktree**. All 66 declare `python == "3.12.13"` and
`import_roots == ["src"]`, carry 16–40 pins, and total **3003 declared node ids** (209
`fail_to_pass`, 2794 `pass_to_pass`; median 23.5 per task, max 232). Source A is one committed,
fully loadable manifest, `tasks/public/instances/pallets__flask-4045.json`, with 52 declared ids.

Two consequences:

- **No source-B manifest stores a gold patch.** There is no ceiling arm available without
  re-deriving the reference diff from `provenance.commit` vs `provenance.parent` in the donor.
  (Source A *does* carry gold patches, in `tasks/public/pool.json`.)
- **`repo.materialise` git-clones `repo_url` on every single run** (`repo.py:66-84`), with no cache.
  For source B that clone is a local path — offline. For source A it is
  `https://github.com/pallets/flask.git`, so **every public verification touches the network**.

## 5. The guardrails, and exactly how each is honoured

**The reward-path AST guard.** `GUARDED_ROOTS = (SRC/"whetstone"/"verify", SRC/"whetstone"/"tasks")`
(`tests/test_no_inference_on_reward_path.py:77`), walked with `rglob` — recursive. `mlx`, `mlx_lm`,
`peft`, `accelerate`, `trl` and more are banned (`:119-127`).

- Placing the generator at `src/whetstone/<sibling>/` puts it **outside** the guard: it will not be
  seen, which is correct and intended (`:16-19` — *"The ban applies to the reward path and nowhere
  else"*), and `CONTRIBUTING.md:20` forbids widening the guard to make anything pass.
- Placing it under `verify/**` or `tasks/**` fails the build instantly. Naming any module the
  guarded roots import `model`, `models`, `llm`, `judge`, `inference`, `completion`, `prompt` or
  `prompts` trips the first-party half (`:134-136`, exact component match, not substring).
- **The gap worth closing.** No test pins `GUARDED_ROOTS` to an exact set, so adding an
  inference-carrying sibling leaves the guard alive but no longer descriptive of the tree, and
  nothing notices. That is what acceptance criterion 1 should actually assert: a **net-new
  partition guard** — every package under `src/whetstone/` is either guarded or explicitly exempted
  with a recorded reason — not an edit to the existing file. `CONTRIBUTING.md:53-60` additionally
  requires any file-walking guard to assert its set is non-empty and to have been *watched failing*.

**CI runs without mlx.** `.github/workflows/ci.yml:32` runs `uv run pytest` and `:30` runs
`uv run mypy src/` under plain `uv sync`, which installs only `dev`; the `mlx` extra appears solely
in the last step (`:75-81`) to prove `import mlx.core` works. Therefore:

- no test may import `mlx_lm` at module scope — follow the existing `pytestmark = skipif(...)`
  precedent, extended with `importlib.util.find_spec`;
- `import mlx_lm` inside `src/` needs a `[[tool.mypy.overrides]]` block, because `strict = true`
  with `warn_unused_ignores = true` (`pyproject.toml:45-50`) makes a bare `# type: ignore` an error
  on a machine where mlx *is* installed;
- there is **no marker or timeout infrastructure** for slow tests (`pyproject.toml:52-53` is
  `testpaths` and nothing else), so a slow bake-off test needs a different answer than `-m slow`.
- The repo treats a silent skip as a reportability hazard in the same class as rendering
  `UNVERIFIED` as `PASS` (`tests/conftest.py:66-69`), so a conditionally-skipped inference test
  should be as loud as `ci.yml`'s `-rs` sandbox step.

**`reports/` is not blocked.** `_reports_without_preregistration` (`tests/test_docs.py:173-185`)
short-circuits to `[]` the moment `PREREGISTRATION.md` exists — it does. `.gitignore:16-24` ignores
only `/reports/local/`, so `reports/baseline/` is committable with no ignore change. **But**
`.gitignore` has **no model-cache or weights pattern at all** — no `*.safetensors`, no `models/` —
so nothing prevents `git add -A` committing multi-GiB weights. A new ignore entry is needed, proven
the way `tests/test_tasks_layout.py:36-43` proves one (with the trailing-slash trap at `:15-19`).

**The `%` ban applies to `PREREGISTRATION.md` only** (`tests/test_docs.py:528-542`, three plain
substring tests over the whole file including code fences). The report may contain any spelling of a
proportion — but `PREREGISTRATION.md:157` (*"Every rate carries its denominator"*) and
`CONTRIBUTING.md:29-32` (*"No invented numbers"*) still bind as policy.

### Two guards that will fight this slice, and must be handled deliberately

1. **`tests/test_docs.py:680-701`** asserts `docs/ROADMAP.md` § 4 still contains the literal
   `"One criterion remains open"`. Closing the last criterion makes that false, so the guard is
   edited in the same commit — RED first, as a deliberate slice-scoped update (its own docstring
   says the count must move).
2. **`tests/test_docs.py:735-777`** couples `PREREGISTRATION.md`'s ten ROADMAP citations to
   **absolute line numbers**, checked in both directions. One anchor is
   `("364","368","not one number about a model exists anywhere in this repository")` — a sentence
   this slice falsifies — and § 4 spans `:274-485`, so **any line-count change inside § 4 shifts
   five further anchors**. The docstring at `:737-742` records that this exact breakage already
   happened once.
   Two routes: **(a)** keep the sentence inside lines 364–368 as a *quoted, dated correction*,
   which is the precedent the repo already uses (`docs/ROADMAP.md:466-473` preserves a falsified
   claim exactly this way) and keep the § 4 edit line-count-neutral; or **(b)** re-point the
   citation with a dated amendment plus a lockstep edit of `ROADMAP_CITATIONS`. (a) is cheaper and
   more honest; (b) touches an append-only document. The PRD should pick (a) and treat (b) as
   fallback.

## 6. Feasibility — MEASURED on this machine

Hardware: **M4 Max, 14 cores, 36 GB RAM**, GPU recommended working set **28.08 GiB**, ~328 GiB free
disk, macOS 26.5.2. `mlx-lm==0.31.3` / `mlx==0.32.0` install in ~5s and match `uv.lock:440,465,485`
exactly; `import mlx.core` works and a GPU matmul evaluates. **`uv pip install --offline` also
succeeds** from the existing uv cache, so the runtime needs no network after today.

**Nothing is cached.** `~/.cache/huggingface/hub` holds 130 MB of embedding/sentiment models and
nothing generative; no LM Studio; `~/.ollama/models` is empty. So the weight download is a real,
one-time cost: **ESTIMATE 13.4 GiB** for {3B, 7B, 14B} at 4-bit, from MEASURED HF blob metadata.

**Determinism is available and was verified, not assumed.** Greedy is the default sampler
(`generate.py:386`) and needs no seed; `temp=0` reduces to the same (`sample_utils.py:47`); `temp>0`
differs across calls but reproduces exactly under `mx.random.seed(n)`. Seeding is **global process
state** — there is no `seed=` kwarg — which constrains any in-process parallelism.

**Weights can be pinned to a local directory and the run kept offline.** `load()` decides by a plain
`Path.exists()` check (`utils.py:218-256`): a local directory loads with zero network (verified
under `HF_HUB_OFFLINE=1`), while a repo id raises `LocalEntryNotFoundError` offline. `load()` also
takes `revision=`, which matters because `mlx-community` repos are mutable.

**Throughput, measured honestly.** No prior MLX evidence existed on this machine, so rather than
invent figures the dig reconstructed the real Qwen2.5-Coder architectures from their published
`config.json`, quantized them to match the repos' own settings — parameter bytes agree with
published sizes to two decimals — and timed generation with **random weights**. That is valid for
*speed* and says **nothing about quality**. Per 4000-token prompt / 600-token generation: 3B-4bit
**7.8 s**, 7B-4bit **13.8 s**, 14B-4bit **32.0 s**, 14B-8bit **61.8 s** with a 30.56 GiB peak —
above the recommended working set, so 14B-8bit should be excluded or flagged. Run-to-run spread was
~17% on a busy machine; the bake-off must report its own timings, never these.

**ESTIMATE, generation only, excluding all verifier time:** 66 tasks × R=1 is ~8.6 min at 3B-4bit,
~15.1 min at 7B-4bit, ~35.1 min at 14B-4bit. A three-model 4-bit bake-off at R=5 is roughly **5
hours of generation** — overnight-shaped, which is what the project wants.

**The verifier half is unmeasured and is the real unknown.** Each `verify_strict` call is one `git
clone` plus one sandboxed pytest run over up to 232 node ids, plus one venv build per distinct pin
set. With 66 tasks × candidates × R, and both STRICT and WEAK needed (§ 7), the verifier plausibly
dominates. The plan must measure a small slice before committing to a full matrix, and the plan's
first estimate must be labelled as such.

## 7. Blockers and decisions the PRD must close

1. **`weak.py` cannot run a pinned task, so baseline `N` is not currently computable.**
   `PREREGISTRATION.md:96-109` requires `N := count(WEAK == PASS and STRICT == FAIL)` and a
   **baseline `N`** — but `verify_weak` (`weak.py:57-63`) hardcodes `sys.executable` and takes no
   `interpreter`. Either `weak.py` gains an `interpreter` parameter (a small, in-character change to
   a measurement-only module that imports nothing new — the guard stays green) or baseline `N` is
   not reported and that omission contradicts a committed document. **Recommend: add the parameter.**
   Note it also doubles the executions per (base, task).
2. **The bake-off's task set.** Not "held-out" (§ 3). Recommend: all 66 source-B tasks plus the one
   source-A instance, recorded by hash, with the report stating that no split has been defined and
   that § 7.1 remains open.
3. **A second network exception.** `docs/ROADMAP.md:574-576` declares exactly one — the public
   instance fetch. Downloading weights is a second, and source A's per-run `git clone` is arguably a
   third. Recommend: declare weight fetching as a human-run, provenance-committed provisioning step
   with the scored run pinned to local directories under `HF_HUB_OFFLINE=1`, and disclose the
   source-A clone honestly rather than claiming the run is offline.
4. **The generation contract is an unpinned input to the number.** What the model is shown and how
   its output becomes a patch determines the result, and it is **not** among the five pinned inputs
   at `PREREGISTRATION.md:131-132`. This is the strongest candidate for an amendment-type-2
   disclosure (`:269-270`, which explicitly permits *adding* a disclosure), and arguably a sixth
   pinned input for the later baseline.
5. **Does the whole-evaluation `UNVERIFIED` collapse apply here?** `PREREGISTRATION.md:116-119` says
   an evaluation with any residual unverified task reduces to `UNVERIFIED`, but it presupposes `R`
   retries and `R` is undefined until P3 (`:249-253`), and the surrounding text is the *promotion
   gate*'s. Recommend: read the collapse as gate-scoped, report per-candidate coverage and
   unverified counts instead, and state the reading in the report. `docs/ROADMAP.md:433` — *"the
   unverified rate is reported from the first eval onward"* — binds either way, and this is the
   first eval.
6. **Cross-candidate comparison crosses a pinned input.** Model revision is pinned
   (`PREREGISTRATION.md:131`), so ranking candidates is a comparison across a changed pinned input
   and must carry the non-comparability sentence (`:136-138`) or not be presented as comparable.
   Selecting a base by highest STRICT-PASS count is a *ranking*, which is allowed; any sentence of
   the form "viable if it solves ≥ k" would be a **success threshold** and is forbidden outright
   (`:171`).
7. **The corpus is not in this worktree.** Decide whether the runner takes a `--tasks` path pointing
   at the primary checkout or the manifests are copied in. Copying user data between worktrees is
   discouraged by `whetstone-worktrees`; pointing by absolute path is the sanctioned form.
8. **A "harness broken" outcome must be distinguishable from an honest all-zero**, or P1's pivot
   signal cannot be trusted (§ 4, the `patch-apply` point). Recommend a mandatory control arm per
   candidate: the reference/inert patch, proving the harness can still reach `PASS` and `FAIL` on
   the same task set in the same run.

## 8. Guardrail sanity check (the Phase 2 requirement)

- **Reward execution-grounded?** Yes — unchanged; the model is strictly upstream of `verify_strict`,
  and the AST guard keeps it out of `verify/` and `tasks/`. No judge anywhere.
- **Does the gate promote on an unproven gain?** No gate is touched. Nothing is promoted; nothing
  is trained.
- **Does anything leave the box?** Weight *download* comes in; nothing goes out. Source B's
  manifests are never read by anything networked, and the scored run is pinned offline. The
  source-A `git clone` is an existing, disclosed inbound fetch.
- **Would a better base make this redundant?** No — the opposite. The bake-off is the mechanism by
  which a better base gets adopted (`docs/ROADMAP.md:570`), which is exactly `CLAUDE.md` #4.
- **No invented numbers?** Every figure above is MEASURED or labelled ESTIMATE with its arithmetic;
  the throughput figures carry their random-weight caveat, and none may appear in
  `docs/ROADMAP.md` (`:7-9`) or `PREREGISTRATION.md` (`:163`) — the report is the only sanctioned
  home.

## 9. Stale guidance found, recorded but not fixed here

`.claude/skills/whetstone-next/SKILL.md` and `.claude/skills/whetstone-worktrees/SKILL.md` both
still describe the repo as greenfield with no `src/` and a failing `uv sync`. In this worktree
`uv sync` succeeded and `uv run pytest` reports **396 passed**. Correcting the skills is out of
scope for this slice.
