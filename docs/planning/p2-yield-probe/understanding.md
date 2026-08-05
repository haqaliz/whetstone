# Understanding — `p2-yield-probe`

**Dug 2026-08-05**, in `.claude/worktrees/feat-p2-yield-probe` at `a14817e`. Baseline green:
`ruff`, `mypy`, and 580 passed / 2 skipped before anything was touched.

Every claim below carries a `file:line`. Where a figure appears it is derived from
`reports/baseline/report.json`, which is its only home; nothing here is restated into a document
that would then be able to disagree with it.

---

## 1. What the work is really asking

The card says "fix the generation contract so patches apply." The dig says the honest framing is
one level up, and it changes what has to be amended.

`docs/ROADMAP.md:387-389` fires the pivot signal on a premise:

> **Pivot signal — fired.** If no candidate base solves *any* task in the declared source-B set,
> expert iteration has nothing to bootstrap from.

The premise is *expert iteration has nothing to bootstrap from* — a claim about **ability**. But
of the 152 verdict-reaching source-B rollouts, **142 never got a patch onto disk** (`no_diff` 43,
`not_applied` 99), leaving **10** where held tests actually judged a fix. The 3B candidate applied
**zero** patches across all 50 of its covered rollouts.

So the measurement never reached the question the signal is read against. **This slice is not a
third pivot response; it is a measurement-validity fix** — establishing whether the pivot signal
can be read at all. That framing matters practically, because it means § 4's list of responses
("an easier task stratum or a larger base") is not being extended, and the roadmap's § 4 prose
does not need a line-shifting insertion. See § 5.

**What this slice may not claim.** A non-zero yield afterwards would *not* retroactively make the
bases capable — it would mean the first measurement was bounded by its harness. And a zero
afterwards is a much stronger result than the first zero, because the patches would then have
actually been graded. Both outcomes are publishable; neither licenses a comparison with
`reports/baseline/` (§ 4).

## 2. Where it sits on the core loop

`CLAUDE.md` § *The core loop*: this is element **①**'s measurement apparatus, not the reward
itself. Precisely:

- **The reward is untouched.** Nothing under `src/whetstone/verify/` changes. STRICT still decides
  PASS/FAIL by re-execution, still restores held tests from golden after the patch, still asserts
  the executed node-id set. The AST guard's `GUARDED_ROOTS`
  (`tests/test_no_inference_on_reward_path.py:104-109`) is not widened.
- **All new code lands in `src/whetstone/bakeoff/`**, which is `EXEMPT` from the reward-path guard
  by a written reason (`tests/test_reward_path_scope_is_partitioned.py:100-104`) — it is the
  harness that imports `mlx_lm` legitimately, one-directionally.
- **`UNVERIFIED` semantics are untouched.** It is still not a win and still not a loss.

This is emphatically **not** a looser verifier, and the PRD must say so in those words. What
changes is *what the policy is asked to emit* and *how that becomes a diff* — upstream of the
reward, never inside it.

## 3. The seam, precisely

Three files, all in `bakeoff/`:

| Step | Where | What it does today |
|---|---|---|
| Prompt | `rendering.py:131-144` `_RESPONSE_FORMAT` | Demands "a single unified diff … inside one fenced block tagged `diff`" |
| Generate | `scoring.py:432` | `completion = generator.generate(prompt)` — `Generator` is a one-method Protocol (`generator.py:59`) |
| Extract | `scoring.py:435` | `extraction = extract_patch(completion)` → `Extracted` or `NoDiff` |

**The change is: `_RESPONSE_FORMAT` asks for an edit format the model can actually produce, and a
new converter turns that into a unified diff before `_verify` is called.** Nothing else moves.

**One signature consequence, and it is the design's real cost.** A unified diff is self-contained;
a search/replace edit is not — converting it needs the *file contents* to locate the anchor and
compute hunk headers. Those contents already exist at prompt-render time (the oracle sources), so
the converter needs them threaded to it. `extract_patch(completion)` becomes something like
`convert(completion, sources)`. That is a real change to a tested contract, not a drop-in.

### The adversarial property that governs the whole design

`docs/planning/p1-baseline-bakeoff/generation/spec.md` AC5:

> Model output containing a diff that touches a path in `task.test_blobs` is extracted
> **unmodified** and handed on. The extractor must not sanitise, rewrite, or drop such a hunk:
> STRICT's `patch-scope` refusal (`strict.py:524-533`) is the defence, and an extractor that
> quietly repaired the patch would convert a caught cheat into an uncaught one.

**This is strictly harder for a converter than for the current extractor**, and the difference is
the single largest risk in the slice. The current extractor satisfies AC5 by *not modifying* — a
passthrough cannot sanitise. A converter **constructs** the diff, so it must actively choose to
construct one that STRICT will refuse.

Worse: the oracle sources deliberately **exclude every held path** — `rendering.py:151-161`
raises `HeldTestInSources` if one is offered. So when a model emits an edit against a held test,
the converter has *no content to anchor against* and the natural implementation — skip what you
cannot resolve — is exactly the silent repair AC5 forbids. **A cheat that P1 caught would become
a cheat P2 never sees, while every existing test stayed green.** The failing test for this must be
written first and watched failing (`CONTRIBUTING.md:56-60`).

## 4. What publishing costs — two hard guards

**4a. `reports/` has a one-home invariant.** `tests/bakeoff/test_report.py:961-994` pins the exact
file list and says why: "a file extra means there is a second place a figure can live, and the
next reader has no way to tell which of two disagreeing numbers is the real one."

The precedent for moving it is in that same docstring — the guard *already moved once*, from
"`reports/` is absent" to "`reports/` holds three artifacts", when slice 5 ran. The invariant
underneath survived and the literal moved. The same argument is available here **only because the
two runs measure different generation contracts and are explicitly non-comparable**, so neither is
a competing home for the same figure. This must be argued in the guard's own docstring, not
quietly extended.

**4b. The provenance obligation is already binding.** `PREREGISTRATION.md:356-361` (amendment
§ 10.1) requires every report publishing a governed figure to state its generation contract
"identifiably enough that two contracts can be told apart — at minimum a hash of the prompt
template, the retrieval setting, the sampler and its token budget, and a version for the
extractor", and to report two figures under different contracts as **not comparable**.

Note the gap: **the retrieval setting is not a `GenerationContract` field.** It is a hard-coded
module constant `_ORACLE_DISCLOSURE` (`report.py:66-74`). If retrieval stays oracle it can remain
prose, but the contract dataclass (`report.py:175-199`: `prompt_sha256`, `sampler`, `max_tokens`,
`extractor_version`, `dev_subset`) is the natural home and § 10.1 names retrieval explicitly.

Two smaller teeth: `_require_provenance` (`report.py:460-482`) refuses a blank field rather than
rendering one, and `ScoredDevSubset` (`report.py:139-145`) refuses the build if a task the
contract was developed against reaches the scored set — so a **new dev subset must be declared and
excluded**, and it may not be the same three tasks, since those were spent on the old contract.

## 5. The citation fragility (a finding, not a blocker)

`PREREGISTRATION.md` cites `docs/ROADMAP.md` by **line range**, and `tests/test_docs.py:809-851`
asserts every range still contains its anchor text. The roadmap is 618 lines; the highest cited
range ends at **596**. So **any insertion above line 596 breaks an append-only document's
citations**, and the repair cannot simply be made inside that document.

This slice avoids it by construction (§ 1: no § 4 insertion is needed). But it is worth recording
as a structural fragility in its own right: the coupling makes the roadmap's first ~96% effectively
append-only too, which nothing states.

## 6. Contradictions and open questions

1. **The card says "raise the token budget"; the dig says that is one of several causes and the
   evidence cannot separate them.** `NOT_APPLIED` is *"git refused it", full stop* — it conflates a
   malformed diff, a mis-anchored one, a correct diff with the wrong path prefix, CRLF endings, a
   budget-truncated diff (`patch.py:52-53`, live at `max_tokens: 1024`), and rarely an
   infrastructure failure at apply time (`repo.py:100,108,118`). **Since raw generations were never
   persisted, today nothing on disk can attribute the 142 among these causes.** So the slice cannot
   begin by diagnosing the old run — it can only instrument the new one. This reorders the card's
   acceptance criteria: criterion 3 (persist raw output) is a *precondition*, not a nice-to-have.
2. **Does the diagnosis run before the fix?** A cheap first step is to re-run the *existing*
   contract with raw-output persistence on and read what the bases actually wrote. That is ~1.4h of
   generation (`reports/baseline/report.md:82`) and would turn "142 unattributed" into a real
   breakdown, making the format choice evidence-led rather than guessed. **Open: is that worth the
   run, or do we go straight to a new format?** This is the biggest open question in the slice.
3. **Which edit format?** Search/replace blocks, whole-file rewrite, or line-anchored edits. Each
   trades differently against the AC5 risk and against truncation. Undecided.
4. **`--probe N` already exists** (`run.py:580-586`) for a timing sample that publishes cost only
   and no counts — a natural vehicle for a diagnostic run that must not publish a figure.
5. **Where do raw generations live?** `.gitignore:20-24` reserves `/runs/`, `/checkpoints/`,
   `/reports/local/`. They must **not** go under `--out` (that is `reports/baseline/`, committed,
   and for source B would publish the user's private donor code).
6. **`whetstone bakeoff` must not exist.** `run.py:7-13`: `cli.py` is a guarded root, and a
   subcommand would put `mlx_lm` one transitive import from the reward path with every guard green.
   The entry point stays `python -m whetstone.bakeoff.run`.

## 7. Guardrail check

| Guardrail (`CLAUDE.md`) | Status |
|---|---|
| Reward verifiable, never a judge | **Held.** No model on the reward path; `verify/` untouched; guard roots unchanged |
| `UNVERIFIED` ≠ win | **Held.** Untouched |
| Local / BYOK / private | **Held.** Weights (13 GB) and all 66 manifests are already local; the run is offline (`HF_HUB_OFFLINE`, `run.py:382`) |
| No frontier base-model training | **Held.** Nothing trains |
| No invented numbers | **At risk, and the slice's main discipline.** Every figure must come from the new run, and the old report may not be quoted beside it |
| Ship the honest number | **Held, and load-bearing.** A second zero is the publishable outcome (§ 1) |
