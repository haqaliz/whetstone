# Whetstone: Status Log

The full, append-only engineering status log for this repository —
what landed, when, and what each change did and did not do.
Previously the preamble of `CLAUDE.md`; moved here 2026-08-31 so the
always-loaded project context stays small. Newest entries first.

Read this when you need the history behind a decision. `CLAUDE.md`
carries the current state and the rules that still bind.

---

**The probe decision gate — night #1's go/no-go as a command — is done**
(`docs/planning/probe-decision-gate/`, 2026-09-05). The night-door runbook has pre-committed
the rule since P2 — the night proceeds iff the probe completes with the control arm `PASS` on
every draw and a non-empty seed map — and an operator enforced it by reading the ledger by
eye, which is the narrative judgement `docs/ROADMAP.md:278` forbids as an exit criterion.
`whetstone check-probe --run <runs/id>` is now that sentence as a process exit: read-only over
one probe run directory, running nothing, publishing nothing, reading no number. Exit 0 the
rule holds; exit 1 a named violation (which draw and which source's harness is not `PASS`, or
an empty seed map) and no night runs behind it; exit 2 a refusal an operator can fix by
retyping — `NotARun`, `LedgerUnreadable` (via `ledger.read` by identity), `NotAProbe`,
`IncompleteRun`. There is no `UNVERIFIED` exit: the command reads documents rather than
running anything, so it either answers or refuses. The decision lives in
`whetstone.loop.check_probe` on the `check_leakage` shape — a pure `run_check` plus a
`disclosure()` — and orders itself deliberately: identify the run, pass the ledger through the
schema gate, prove the probe identity, and only then decide, because a check that read a
doctored document and answered "proceed" would be worse than no check. **The two conditions
are exactly the pre-committed ones and nothing more**: the seed map is tested for
non-emptiness literally, never re-derived from `attempt_seed` and never grown into a coverage
bar the rule never set; journals are checked for existence only, because the ledger is the
completeness authority. The sources, the ledger's name and reader, the verdict vocabulary and
the evidence-path derivation are composed by identity from the modules that write them,
asserted `is`. Two notes for whoever reads this next: a genuinely-written probe ledger cannot
carry a non-`PASS` fold, because `rankable` raises `HarnessNotProven` and the night exits
`UNVERIFIED_EXIT` with no ledger at all — so the exit-1 control case exists to catch a doctored
ledger or a future regression in the night's own gate, and its fixtures are adversarial on
purpose; and a fully-replayed **resume** can write a ledger whose recorded seed map is empty
even though every draw ran under a seed, which is why the runbook now says a killed probe is
restarted fresh under a new `--run-id` rather than resumed (a killed **night** still resumes
unchanged). The runbook was rewritten in the same unit, code first — the
`gate-untrained-incumbent` precedent — and its guard grew from two door blocks to three,
watched failing first; the reward path's partition guard grew its fifth edge
(`run_check_probe_cli`, function-local like the other four). **The night has still not been
run**: no training set, checkpoint or yield figure exists, the gate has still not run on real
checkpoints, and this command has never been pointed at a real probe — its exits are proven
against fixtures only. The baseline spend and the P4 report still follow.

**The § 7.3 Type 1 amendment — the launch path's first step — is done**
(`docs/planning/close-base-7.3/`, 2026-09-02). `PREREGISTRATION.md` § 7.3 is closed by the
dated amendment § 10.10, committed before night #1 trains (§ 8.1): the nightly loop
fine-tunes `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, pinned at the immutable
revision `d1e3b690c8e225d7795bccddf971ca6be68b2012` and recorded by per-file hash in the
gitignored `weights/provenance.json`, the evidence being the larger-base arm's first
nonzero strict-PASS yield with the control discipline intact (figures stay in
`reports/larger-base/`, restated nowhere). The amendment landed TDD: a shape guard in
`tests/test_docs.py` was watched failing first (RED), then the amendment satisfied it
(GREEN) — the guard pins § 10.10's shape, the no-measurement sentence, the status-paragraph
closure, the § 10.10 log row, and cross-pins the repo_id against the night runbook guard's
`RETAINED` constant so the pre-registration and the night cannot drift apart silently. The
one edit above § 10 was the status paragraph's § 7.3 sentences, per the § 10.7/§ 10.8
precedent; the roadmap gained the dated correction blockquote next to the bake-off record,
CLAUDE.md's 'Still open' base bullet settled, and the changelog records the unit. **The
night has still not been run**: no training set, checkpoint or yield figure exists, the
gate has still not run on real checkpoints, and the baseline spend and the P4 report
follow.

**The gate-untrained-incumbent unit — the launch path's first incumbent — is done**
(`docs/planning/gate-untrained-incumbent/`, 2026-09-01). The roadmap's named next code unit
(`docs/ROADMAP.md:663-671`) is shipped: `gate_engine` now dispatches on `Checkpoint.untrained`
(gate.py:504-555) — the trained path keeps `adapter_path=str(checkpoint.directory)`
byte-identical, the untrained path delegates to `baseline_engine`, which moved into `gate.py`
(462-501) and is re-imported by `baseline.py` **by identity** (asserted `is`, never copied) —
so `whetstone gate --candidate X --incumbent <untrained base>` reaches the decision table, and
the first gated evaluation compares a night's candidate against the untrained base it started
from: **one night, not two**. An untrained **candidate** is refused by name
(`UntrainedCandidate`, in `REFUSALS`, raised after the per-side re-hash naming the side and
path): its digest is the constant `sha256("")` over the empty file set, which cannot
discriminate bases — the same reason the § 3 series identity keys on base identity, never the
digest (baseline.py:36-39). The gate runbook
(`docs/planning/p3-promotion-gate/gate-runbook/runbook.md`) was rewritten in the same unit,
**code first** (`docs/ROADMAP.md:670-673`): the incumbent is a
`write_baseline_checkpoint`-materialized path (its own step, since the § 3 spend now runs
after the first gated evaluation), the "needs **two** nights" paragraph became the one-night +
untrained-base sentence with the § 3 boundary stated in words (the gate's incumbent is **not**
the § 3 measurement — different roles, different homes, a disagreement published as a finding,
never reconciled), and the guard's `WORKTREE` moved to this unit's with
`feat-p3-promotion-gate` stale; a new pin holds the replacement wording and the
materialization step, watched failing against stub sheets first (each assertion failed for its
intended reason; the pin was proven satisfiable). The dispatch test is the first to invoke
`gate_engine` — fake `mlx_lm` modules injected via `sys.modules` (the extra is absent under
plain `uv sync`), `load`'s kwargs captured: `adapter_path` the checkpoint directory trained,
`None` untrained, `generate` never called (`sampler_for(1)` needs no stub — `greedy_sampler`
imports `mlx.core` only inside its body). Integrity held: `decide()`, the three exits, the
retry discipline and the promotion record schema untouched; the AC2 pins byte-identical to
`origin/master`; the partition guard still holds exactly four function-local edges; 1488
passed, 4 skipped. Two honest disclosures: the untrained-incumbent **decision table** passes
on master — it is a regression pin for the GREEN changes, not a RED — and the baseline
no-inference walk's anti-vacuity control was structurally adjusted to accept the
identity-binding shape (`baseline_engine` is now an `Assign`, not a `FunctionDef`) with the
walk itself unchanged. **The gate still has not run on real checkpoints**: the launch path's
next step is the operator chain — the § 7.3 Type 1 amendment, **night #1**, then the first
gated evaluation against the untrained incumbent — and the baseline spend and the P4 report
follow.

**Status — what exists in this tree today.** `docs/ROADMAP.md` is written and is the
**authoritative technical document** until `docs/technical/ARCHITECTURE.md` is written;
that file does not exist yet. This file and `VISION.md` remain the narrative source of
truth (thesis, moat, guardrails).

**P0 (scaffold) is done:** packaging, the `whetstone` CLI, strict ruff/mypy, pytest, and CI
on `macos-latest`.

**P1 slice 1 — the task contract and the verifier core — is done** (`docs/ROADMAP.md` § 2, § 3;
plan at `docs/planning/p1-verifier-core/`). `src/whetstone/verify/` holds the frozen `Task`
contract, the ported verdict semantics (`UNVERIFIED` ranks above `PASS`), the Seatbelt sandbox
(network denied, writes confined, environment pinned), the **STRICT** verifier — the reward —
and the **WEAK** verifier — measurement only — reachable as `whetstone verify`. The
adversarial corpus (`tests/adversarial/`) runs ten cheats through both verifiers: eight are
killed, and **two are documented residuals**, cheat 6 (special-casing the known input) and
cheat 10 (a held test's undeclared dependency). A scoped AST guard keeps inference libraries
off the reward path.

**P1 slice 2 — the on-disk task format — is done** (`docs/ROADMAP.md` § 3; plan at
`docs/planning/p1-task-ingestion/`). A manifest now declares its `environment` — exact `==`
pins and a nominated interpreter — so the verdict stops depending on what the package index
served that morning; `tests/test_environment_pins.py` demonstrates that, showing one task and
one correct patch reaching **PASS** pinned and **FAIL** unpinned, resolved offline against a
committed index. Held test paths are refused unless spelled canonically. `src/whetstone/tasks/`
reads a whole directory of manifests — nothing skipped, an empty directory is a usage error
rather than a vacuous pass — and `whetstone verify` accepts one, reducing worst-status-wins so
a single `UNVERIFIED` task can never exit 0. `tasks/` carries the layout that splits committed
provenance from local data. The reward-path guard now covers `src/whetstone/tasks/` as well as
`src/whetstone/verify/`.

**P1 slice 3 — ingestion, and the first real corpus — is done** (`docs/ROADMAP.md` § 4, P1
exit criterion 4). **Source B (private, the pre-registered headline): 66 tasks**, 45 mined from
`donor A` and 21 from `donor B`, each *proven live* rather than asserted — FAIL with no patch,
PASS under its own reference patch, executed node-id set equal to declared, zero skips. Donors
are named by stable pseudonyms throughout this repository: they are the author's own private
repositories, and their names are not this project's to publish. Donor B is also the sibling
project the verifier's design draws on (§ *Relationship to the sibling project*). The manifests
are the user's code and live in gitignored `tasks/local/`; the committed evidence is
`tasks/recipes/*.json` and `tasks/local-ledger.json` (hashes and verdicts, never file contents).
Two donors yielded nothing and the refusals are the finding: `donor C` was refused for having
no `uv.lock`, and this repository yielded 0 of 2 because its own test-first workflow lands the
test and the fix in one commit. **Source A (public SWE-bench-Lite): 1 eligible instance of 300**
— `pallets__flask-4045` — with all 299 refusals ledgered in `tasks/public/ineligible.json`
against the gate that refused each (192 format, 106 environment, 1 collectability). The
deliverable there is the four-gate filter and the rejection ledger; **one instance is not a
public benchmark set and must never be quoted as one.**

**Slice 3 also found and closed a reward-path defect, which is the part worth reading.** A task
**PASSED with no patch applied** — a false PASS. In a `src`-layout project the tests import by
package name, resolved through the venv, and the venv held an editable install rooted at a
*different* checkout than the one the patch was applied to; the tree under verification was
never imported. The ten-cheat corpus missed it because every fixture repo was flat-layout with
no venv install, so **the defence had been the shape of the fixtures, not anything the verifier
did.** Closed by `import_roots` in the manifest, deps-only provisioning
(`--no-install-project`), and a `PYTHONPATH` naming the run's own checkout so it shadows any
residual install; `tests/adversarial/test_inert_checkout.py` holds it shut.

**P1 slice 4 — the pre-registration — is done** (`docs/ROADMAP.md` § 6; plan at
`docs/planning/p1-preregistration/`). `PREREGISTRATION.md` is committed at the repository root,
**before any number about a model existed**, which is its entire value: it fixes the headline —
the change in STRICT-PASS *count* on the held-out source-B split, published over its
denominator and never as a rate — along with every metric definition, the baseline protocol,
and the rule that both sources are always published together and a disagreement between them is
reported as a finding. It pre-registers **no numeric success threshold**, because none could be
grounded before a baseline exists, and forbids one being added once a number does. Three items
are named as open with the amendment that closes each: the held-out split, the retry count `R`,
and the base. Five limitations are disclosed up front, including that source B's self-selection
mitigation (a third donor) **did not land** — `donor C` was refused for having no `uv.lock`.
`tests/test_docs.py` holds it shut: no placeholder, no figure about a model in any spelling, and
nothing may exist under `reports/` in a tree lacking the file. That last guard proves
co-existence, not ordering — the temporal claim is `git log`'s, and the document says so itself.

**P1 slice 5 — the base-model bake-off — is done, and P1 is closed** (`docs/ROADMAP.md` § 4,
the last exit criterion; plan at `docs/planning/p1-baseline-bakeoff/`). Three candidate open
bases produced patches locally through `mlx-lm`, every patch was graded by the STRICT verifier,
and the report lives at `reports/baseline/` (`report.md`, `report.json`, `cost.json`) — read it
before quoting anything about it. **This tree now holds figures about models, and
`reports/baseline/` is their only home** — do not restate one anywhere else, because a figure
quoted twice is a figure that can disagree with itself.

**The result was a zero: not one candidate solved a single task on the declared source-B set.**
So P1's pivot signal (`docs/ROADMAP.md` § 4) **fired**, **no base is selected**, and
`PREREGISTRATION.md` § 7.3 stays open — the response it names is an easier task stratum or a
larger base, never a looser verifier. The failure modes differ by candidate (unapplicable
patches dominate at the small and large ends, empty diffs in the middle), which is a finding
about where the wall is rather than a tie. Two things stop that zero being read as a broken
harness. The **control arm** — an inert patch and each task's own re-derived fix, through the
same harness, on the same task — was **INTACT on every run**, so the harness demonstrably
reaches PASS when a correct patch exists. And the reward-hacking count `N` was zero for every
candidate, which is a floor rather than a rate: the generation contract states the
patch-scope rule to every candidate, so it discourages exactly what `N` counts.

**Two bounds on that report, disclosed rather than discovered.** Prompts used the **oracle
retrieval** setting — the base is shown the non-test files the reference patch touches — so
every count is an **upper bound** on the same base working from the bug report alone, and may
not be compared with a figure measured without retrieval. And the **generation contract**
(prompt template, retrieval setting, extractor) is **not** among the pre-registration's pinned
inputs, yet it demonstrably moves the numbers; a figure measured under a changed contract is
not comparable to this one.

**The measurement is now instrumented, which is where P2 starts** (plan at
`docs/planning/p2-yield-probe/`). Reading the bake-off's own failure buckets showed that the
great majority of verdict-reaching rollouts never got a patch onto disk at all: `NOT_APPLIED`
means *"git refused it"* and nothing narrower, so a malformed diff, a mis-anchored one and a
budget-truncated one all wear the same tag. **The pivot signal's premise — that the bases cannot
fix these bugs — was therefore never actually tested**, because the measurement did not reach the
question. That makes this a measurement-validity fix rather than a third response to the signal,
and it is why `docs/ROADMAP.md` § 4 needs no amendment.

`src/whetstone/bakeoff/transcript.py` keeps what a base actually wrote — as a `Generator`
wrapper, so the one-method model seam is not widened and `score()` is untouched — and
`attribution.py` replays those completions offline to say *which* zero each was, using
`patch.py`'s own `NoDiff` reasons as the partition rather than a taxonomy invented beside it.
The two causes the report cannot separate — git would not read the patch, versus git read it and
would not apply it — are now distinguished, read-only, with nothing under `verify/` modified.
Transcripts hold the user's own code back verbatim, so they are refused under `--out` and their
documented homes are asserted gitignored. **Nothing is published by this**: it produces local
evidence, and the run that uses it has not been made.

**The instrument was then used, and it falsified two proposed fixes** (`docs/planning/p2-yield-probe/prd.md`,
corrected 2026-08-05). Arm A re-ran the pinned contract and **reproduced `reports/baseline/`
exactly** — every published count, four days later — which is the first direct evidence that the
bake-off is deterministic rather than merely argued to be. Attributing its transcript then showed
the failures are overwhelmingly *"git would not read this diff"* rather than *"git read it and
would not apply it"*, which withdrew the search/replace proposal; and a second run at double the
token budget, on the base the evidence best supported, moved no cause bucket beyond noise and
solved nothing.

**The reasoning under both was the defect, and it is the transferable part.** Truncation had been
*inferred from the shape of a diff* and never measured — the spec named that inference as open,
and it was then reasoned from as settled. So the roadmap's own named responses (an easier task
stratum, or a larger base) now have more support than any generation-contract change, and no
further fix should be proposed before someone reads what the unparseable diffs contain. Every
figure behind this lives in gitignored run artifacts; `reports/baseline/` remains the only home
for a published one.

**P2 slice 2 — the diff autopsy — is done, and the read is now a measurement** (`docs/planning/p2-diff-autopsy/`;
plan at `docs/planning/p2-diff-autopsy/autopsy/`). `src/whetstone/bakeoff/autopsy.py` is an
offline, deterministic, stdlib-only classifier that assigns every stored completion exactly one
grounded content-shape cause, asserts a fine→coarse mapping against the run's own
`attribution.json` (a contradiction is reported, never reconciled), and writes its document
only under a gitignored root. **Running it corrected the hand-read in three places, which is
the transferable part.** The mapping assertion surfaced walk rules that disagreed with git's
parser on the same bytes — a check that read text git never parses, a counter-overrun git
reads as "corrupt patch" while the walk saw a completed hunk, and a mapping gap for
loop-dominated completions carrying a refused stub — and each correction landed with a
fixture, watched failing first. The corrected measurement agrees with the run's own
attribution on every stored record, classifies both runs completely with nothing
unrecognised, and agrees with the hand-read exactly on the control category while diverging
from it only at the one margin the dig itself called fuzzy (reported as a finding, never
reconciled). **The finding** (`docs/planning/p2-diff-autopsy/finding.md`) names a formatting
wall, not a reasoning or extraction wall: the candidates can write diffs git accepts and
almost never do, so the roadmap's easier-stratum/larger-base fork is unsupported by this
evidence, and the pivot signal's premise remains untested until a format-hardening response
runs — which the finding names but does not build. No figure about a model appears anywhere
outside the gitignored breakdowns; the one record that aimed a diff at a held test never
reached the verifier and is disclosed as attempt-shaped evidence, not a counted hack.

**Format-hardening aspect 1 — `diffcheck` — is done** (`docs/planning/p2-format-hardening/diffcheck/`;
spec at `spec.md`, plan at `plan_20260809.md`). The validator that names the finding's
formatting wall *online*: `src/whetstone/bakeoff/diffcheck.py` is **classify-only** — it imports
the autopsy's taxonomy by identity (imported, never copied, asserted `is` in a test), maps the
fine cause to a retry trigger (`hunk-count-mismatch` and first-hunk deaths on a bare line or the
closing fence fire; `well-formed`, `im-start-loop`, the inferred `end-of-output` truncation,
`no-diff`, `unrecognised-shape` and — until the measured-arm pre-analysis flips it, via the one
parameter that exists for exactly that — `header-without-hunk` never do), and answers the finite,
fixed diagnosis vocabulary (one constant sentence per trigger; a `str.format` placeholder or a
digit in any sentence fails the suite — the seal-frozen prompt set, PRD D8). **The transcript
schema now carries the retry** — `Transcribed` gains `attempt` and `decision` ("retry" |
"graded"), the codec is updated field by field, and `replay()` still picks the last record per
key (a trailing "retry" is refused as corruption — a run killed mid-retry — never repaired). And
the **anti-credulity proof is watched-failing and sub-verdict-pinned**: a held-path edit
(well-formed, trigger-shaped, and mixed with a real fix) survives validator and extractor
byte-for-byte and reaches STRICT, which refuses it as `patch-scope` → `(Outcome.OUT_OF_SCOPE,
Status.FAIL, Status.PASS)` on every shape, while a deliberately credulous validator that drops
held hunks is proven to lose the differential. The AC2 pins now cover all three frozen paths —
`src/whetstone/verify/`, `patch.py`, **and `attribution.py`** — byte-identical to `origin/master`,
the missing pin added, each proven able to fail against a planted change.

**Format-hardening aspect 2 — the `retry-loop` — is done** (`docs/planning/p2-format-hardening/retry-loop/`;
spec at `spec.md`, plan at `plan_20260809.md`). The validator classifies; the retry converts.
`src/whetstone/bakeoff/retry.py` holds the retry prompt builder and the `Retry` wrapper on the
one-method `Generator` seam. The prompt is a **pure function of `(first-attempt prompt, trigger)`** —
the first prompt, a fixed `RETRY_INSTRUCTION`, and one sentence from the finite diagnosis
vocabulary, **never the prior completion** (spec B1: completion-derived content would make the
prompt set unbounded and the seal unfreezable) — so `freeze(..., retry=True)` pre-renders
`retry_prompt(render_prompt(...), trigger)` per task per trigger into the same `posed` map via
`setdefault`, and the contract SHA covers the whole retry vocabulary. The wrapper issues at most
`RETRY_BUDGET` (2) retries per (candidate, task), only on the validator's trigger shapes, returns
the last completion, and writes **one record per attempt** — its own `prompt_sha256`, its
one-based `attempt`, and its `decision` ("retry" | "graded") — filed under the task the prompt
was posed for; the wrapper itself holds the recording pieces (the transcript, the candidate, the
`posed` map), because no one-method, sealed-prompt channel can carry the wrapper's decision down
to a recorder — the recording moved *into* the wrapper, and `Recording`/`RecordingGenerator`
stay untouched for the retries-disabled path. Retries are **off by default**
(`conduct(..., retries=False)`), composed only when `--transcript` names a file; a mid-run
retry-template edit raises `ContractChanged` through the seal and aborts the run, asserted
end-to-end, and the seal-held test proves every prompt an instrumented engine is asked was
frozen. The retry path has its own no-inference AST walk (no `mlx`, no `run.py`, no `scoring`),
and `retry_template_sha256()` is the digest aspect `contract-report` publishes.

**Format-hardening aspect 3 — `contract-report` — is done** (`docs/planning/p2-format-hardening/contract-report/`;
spec at `spec.md`, plan at `plan_20260809.md`). The two contracts are now told apart by their
published fields: `GenerationContract` carries `retry_budget` (`RETRY_BUDGET`),
`retry_template_sha256` (`retry_template_sha256()`), `diagnosis_vocabulary_version` (a digest
over the sorted diagnosis sentences, `diffcheck.diagnosis_vocabulary_sha256()`), and `retrieval`
— `"oracle"` today, the machine-readability fix (yield-probe D9). A retries-disabled run's
contract keeps the no-retries shape (budget 0, blank digests) so it stays byte-identical to the
baseline's; a retried run's declares the whole machinery, and the committed baseline sidecar
predates all four fields and still parses — `GenerationContract.parse` defaults `retrieval` to
`"oracle"` and the retry trio to the no-retries state, so `reports/baseline/report.json` keeps
reading. The report writer supports a second directory: `reports/format-hardening/` with
`report.md`/`report.json`/`cost.json`, both arms' verdict counts under their own contract
fields, the non-comparability sentence, per-arm token-spend disclosure, and a pointer to the
gitignored breakdown home — never restating a classifier count (`finding.md:89-92`). **The
one-home guard moved a second time, only on the D6 argument in both docstrings** (the file list
in `test_report.py:1453`'s copy and its opposite-sign twin in `test_transcript_locality.py:73-119`):
the two directories measure different generation contracts and are declared non-comparable, so
neither is a competing home for the same figure; a silent list extension is refused. The
committed artifacts in the new directory are the declaration — no count, no arm, no figure
restated from `reports/baseline/` — until the measured arm renders the two contracts and their
figures into it. `PREREGISTRATION.md` § 10.4 (Type 2, 2026-08-09) discloses the hardened
contract — retry budget, retry template digest, diagnosis vocabulary digest, retrieval stays
oracle, a new declared dev subset — and declares the two reports non-comparable, with its row
in the amendment log; nothing above § 10 was edited and no proportion appears in any spelling.
The dev-subset mechanism is proven as the three layers it is: exclusion from **both** sources
before anything runs, `UnknownDevSubset` refusal for an id that matches nothing, and the
`ScoredDevSubset` backstop in the report.

**Format-hardening aspect 4 — the measured arm — is done** (`docs/planning/p2-format-hardening/measured-arm/`;
spec at `spec.md`, plan at `plan_20260809.md`, finding at `finding.md`).
`src/whetstone/bakeoff/preanalysis.py` is the offline, stdlib-only, deterministic read of the
stored autopsy outputs (schema `whetstone-preanalysis/1`, refused under any published path,
its own no-inference AST walk) that applies **the same trigger mapping as the validator** —
`diffcheck.trigger_of_cause`, asserted identical — and counts the **retry-eligible ceiling**
per candidate before any GPU is spent. The ceiling was measured over the two stored runs, and
the definition was written in the module before the run: the retry-eligible subset of the
stored parse refusals is a **large majority** — the numbers live in the gitignored
`runs/format-hardening-preanalysis/ceiling.json`, which is their only home — and one
candidate's ceiling is **zero**, its `im-start-loop` wall, which is a per-candidate finding
rather than a tie (the dig predicted exactly that shape). The ceiling is material, so the
arm's halt condition did not fire and the runbook is written: `--retries` is now a real CLI
flag (the switch existed in `conduct` but was unreachable — exposed, with the parser and
wiring tests watched failing first), the donor roots are the real names (`belay`, `contig`),
and the journal and transcript live in a sibling evidence directory because the harness
refuses a transcript under `--out` — exactly as it should. **The post-run read is now a
measurement too** (`src/whetstone/bakeoff/comparison.py`, schema `whetstone-comparison/1`,
its own no-inference AST walk): journals, autopsy documents and the pre-analysis ceiling
document become the per-candidate before/after breakdown, the trigger mapping **re-derived
by identity and asserted** against the pre-analysis's own decisions (a contradiction is a
named violation, never reconciled), the control discipline enforced (no `INTACT` probe, no
counts), the D6 denominators disclosed side by side (rollout records vs classified
completions, and the dev-subset exclusion a hardened contract declares), and the markdown
render at the runbook's named home (`runs/format-hardening-preanalysis/comparison.md`). The
stored arms were exercised through it: the assertion held over every record — zero
violations — and the output is byte-identical across invocations. The report door
(`--render-report` in the same module) is the first production caller of the aspect-3
writer, rendering `reports/format-hardening/` by identity from journals and contract
sidecars — only when an arm has run: a missing journal, an unproven control or zero arms is
refused by name, never a half-truth render. The finding (`finding.md`) states the measured
before in words and records the hold decision. **The measured arm has now run and the
before/after is measured** (`measured-arm-run`, 2026-08-12; finding at `finding.md`): the
retries converted a material share of the retry-eligible parse refusals into well-formed
patches for the two trigger-eligible candidates, the loop-collapse candidate was
unconvertible by its own zero ceiling, and — the measurement's content — well-formed patches
apply but do not solve: no rollout solved a task on the declared set under the hardened
contract, so the format-hardening response is exhausted as a yield lever and the roadmap's
own named fork (an easier task stratum or a larger base) is the next unit, never a fourth
generation-contract change. The run's own report lives at the gitignored
`runs/format-hardening-arm/`; the published side is `reports/format-hardening/`, rendered by
the report door with both arms declared non-comparable; the classifier counts live in the
gitignored breakdown home `runs/format-hardening-preanalysis/comparison.md` and are not
restated anywhere else. The run surfaced two corrections, both landed test-first in the
unit: the arm's writable paths are now absolute and guarded (a relative workspace had died
`UNPROVISIONED`, `HarnessNotProven`, halt condition 1 — evidence quarantined, never
deleted), and the runbook's post-run chain now includes the pre-analysis extension step the
comparison's per-run decisions assertion requires.

**The easier-stratum unit's first aspect — the difficulty axis and the committed stratum —
is done** (`docs/planning/p2-easier-stratum/`; spec at `difficulty-axis/spec.md`, plan at
`difficulty-axis/plan_20260814.md`). The fork's first arm needs a subset of the declared
source-B set that is *easier*, fixed before any rollout, and this is that selection, a
priori and in code: `src/whetstone/bakeoff/stratum.py` measures the reference fix's shape —
the non-test files a mined commit touched, and the hunks and added/deleted lines of the
gold patch derived from the donor at the task's pinned commits — through
`sources.changed_paths` and `derive.gold_patch` reused **by identity** (never copied,
asserted `is`), composed exactly as the control arm composes it and asserted
byte-identical to `control.reference_patch(task).diff` on all 66 tasks. The band is
pre-committed (one non-test file, at most two hunks, at most thirty changed lines), and the
rule's own hunk/line walk is validated as a measurement: its added/deleted agree with git's
own `--numstat` on all 66 tasks, a contradiction named, never reconciled. The stratum
document is committed at `tasks/stratum/easier.json` (schema `whetstone-stratum/1`) as the
probe's pinned input: rule digest (rule source + band, so any rule edit invalidates the
document by design), band, the 66-task corpus, per-task difficulty (files/hunks/
added/deleted plus the manifest tie-breaks f2p/pins/blobs), refusals, a **19-task
membership** (4 belay, 15 contig), and a `document_digest` the loader refuses a hand-edit
of. The loader is fail-closed by name — `UnknownStratumId`, `EmptyStratum` (empty or
whole-corpus, in the writer as well), `StratumSchemaError`, `StratumDigestMismatch` — and
the membership recomputation test re-derives the document from the machine corpus field by
field, skipping in CI with a reason naming exactly what is missing. The document carries
counts only, never paths and never patch content (the ledger's locality discipline, walked
with a canary), and the runbook door is `python -m whetstone.bakeoff.stratum --corpus
<roots> --out <path>`.

**The easier-stratum unit's second aspect — the run-side stratum filter — is done** (spec at
`stratum-filter/spec.md`, plan at `stratum-filter/plan_20260814.md`). The probe now scores
exactly the stratum's tasks: `--stratum PATH` on the run door (`python -m
whetstone.bakeoff.run`) consumes the committed document — aspect 1's loader **by identity**
(imported, never copied, asserted `is`), with `include_stratum` applying the membership
against the loaded private corpus at the partition seam, **before** the contract is frozen,
so the seal and the scored set cover the subset automatically. The loader's membership
checks are completed where the landed suite stopped: an unknown field, a duplicated
membership, and a member the document refused rather than measured are each named refusals
(spec AC 4, D4-4), and the run-side refusal names the id **and the loaded ids** (spec Open
question 3, the `UnknownDevSubset` posture). The dev overlay applies **on top** — dev ∩
stratum is exclusion, never refusal, because the real probe's declared ids may fall inside
the band — an empty scored private set after the overlay is refused **before** freeze,
source A is always scored in full with both sources publishing together, and the task-set
sentence names the stratum document and its membership count. A run without the flag is
today's run byte for byte: the byte-identity test reproduces the unflagged contract SHA and
asserts the provenance sentence is literally the pre-stratum sentence. The adversarial proof
was watched failing against a deliberately credulous loader first: a doctored document
(membership edited to add a declared dev id, digest not regenerated) and a hand-edited
membership are each refused, naming the document digest and the expected value; a fully
regenerated doctored document passes the loader by construction — the layered defence is git
history + ordering + the recomputation test, stated, never reconciled (spec Open question 5)
— and the dev member it smuggles is then proven excluded end-to-end, never scored, excluded
from both denominators. The stratum path walks inference-free, and the AC2 pins —
`src/whetstone/verify/`, `patch.py`, `attribution.py` — are byte-identical to
`origin/master`.

**The easier-stratum unit's third aspect — the stratum report home — is done** (spec at
`stratum-report/spec.md`, plan at `stratum-report/plan_20260814.md`). The probe's verdicts
now have a published home that is honest about what it is: `reports/easier-stratum/` holds
the three-artifact shape (`report.md`/`report.json`/`cost.json`, schema
`whetstone-stratum-report/1`), rendered by `report.build_stratum_report` /
`write_stratum_report` — deterministic and pure, reusing `_row`, `_over`, `tally`,
`_contract_fields`, `_contract_block` and `_counts` by identity — and by the report door's
second mode, `--render-stratum-report` in `comparison.py`, which takes **exactly one** arm
group (`build_contract_arms` reused unchanged, so its missing-journal / empty-journal /
no-`INTACT`-control refusals hold by identity), refuses zero or two groups by name, and
requires `--stratum-doc` as a pointer it never parses; `--render-report` is untouched. The
committed artifacts are the declaration — no count, no contract fields, "**No count is
measured here: the probe has not run.**" — generated by the writer, never hand-typed. **The
one-home guard moved a third time, only on the changed-task-set argument in both docstrings**
(the file list in `test_report.py:1453`'s copy and its opposite-sign twin in
`test_transcript_locality.py:73-119`): the task set is one of the five pinned inputs, the
probe scores a **different task set** under the same hardened contract, so its figures are a
new series declared non-comparable to both existing homes (`PREREGISTRATION.md` § 10.5,
Type 2, 2026-08-14) — each directory the only home of its own; a silent list extension
remains refused. The disjointness guard now scans **all six** existing artifacts, with the
planted-overlap control proved able to fail; the declaration-only home holds no `N of M`
figure in any of its three artifacts. Nothing above § 10 of the pre-registration was edited
and no proportion appears in any spelling.

**The easier-stratum unit's fourth aspect — Phase 1 of `probe-run`, the runbook and its
guards — is done** (spec at `probe-run/spec.md`, plan at `probe-run/plan_20260814.md`).
The operator's sheet exists and a guard holds it: `docs/planning/p2-easier-stratum/probe-run/runbook.md`
opens with the candidate resolution (A2), decided before the run from the stored ceiling
document — the 14B and 3B candidates retained on their measured retry-eligible ceilings,
and `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` excluded by name for a measured zero
ceiling in both stored runs (its `im-start-loop` wall), per the pre-committed rule
(`prd.md:93-103`) — and carries the arm command (hardened contract: `--stratum`,
`--retries`, the five declared dev ids, `--only` × 2, absolute writable paths, CWD at the
primary), the halt conditions, the killed-run restart, and the post-run chain (attribution
→ autopsy → the **mandatory** pre-analysis extension over all four autopsy documents → the
probe's own comparison → the stratum-report door). The guard is extended, never
parameterized (A1): `tests/test_probe_runbook_guards.py` imports the parse helpers from
the measured-arm module by identity (asserted `is`), the pinned module byte-untouched, and
pins the same seven properties plus the A2 resolution rule — every `--only` value is a name
the resolution block records, the excluded name appears in no `--only` value, and the block
states the zero-ceiling rule. The guard was watched failing against a deliberately wrong
stub runbook (relative writable paths, no `--stratum`, a stale worktree name) before the
real sheet existed. Phases 2–4 are operator-executed: the GPU probe itself, the post-run
chain, and the finding that applies the pre-committed fork rule (A6) are not built here.

**The easier-stratum probe then ran, and its zero fired the fork rule.** The probe
executed on the pre-committed stratum under the hardened contract and published its
finding (execution merged 2026-08-15): every candidate returned zero solved tasks with
the control intact, so the pre-committed fork rule (`p2-easier-stratum/prd.md:49-51`)
named the next unit — the larger-base arm — never a looser verifier and never a fourth
generation-contract change. The probe's M13-style read attributed the zero to premise
failure rather than axis failure: the formatting wall receded, well-formed patches
applied, and none turned the tests green.

**The larger-base unit is done, arm and all** (`docs/planning/larger-base-arm/`; the
operator's sheet at `runbook.md` held by its own guard
(`tests/test_larger_base_runbook_guards.py`)). The candidate was resolved a priori — the
32B-class base on the measured candidate family, the 7B excluded by name for its
measured zero ceiling — the probe pass (D7) ran first and settled the ROADMAP § 10
capacity question by measurement (the 32B fits the machine's 36 GiB; MLX memory-maps
the safetensors, so the resident peak stays far below the weights' size), the hardened
contract on the declared source-B set with the dev overlay restored ran to completion
with the control discipline intact on every probe, and the post-run chain — attribution
→ autopsy → the pre-analysis extension over all five autopsy documents → comparison →
the report door — ran clean. The arm's figures have a published home that is honest
about what it is: `reports/larger-base/` holds the three-artifact shape (report.md /
report.json / cost.json, schema `whetstone-larger-base-report/1`), rendered by
`report.build_larger_base_report` / `write_larger_base_report` — pure and
deterministic, reusing `_row`, `_over`, `tally`, `_contract_fields`, `_contract_block`
and `_counts` by identity — and by the report door's third mode
`--render-larger-base-report` in `comparison.py` (exactly one arm group,
`build_contract_arms` reused unchanged, the three report modes mutually exclusive).
The one-home guard admits the fourth directory on the changed-candidate-set argument —
model revision is one of the five pinned inputs, so the arm's figures are a new series,
declared non-comparable to all three existing homes (`PREREGISTRATION.md` § 10.6, Type
2, 2026-08-15) — and the amendment disclosed the series before any figure existed for
it. **The measurement: the 32B produced the first nonzero strict-PASS yield the
harness has ever measured** — the fork rule pre-committed in the unit's PRD routes to
P2's first slice (rollouts + expert iteration) next, and the finding names the 32B as
the first candidate with evidence; § 7.3 closes only by a Type 1 amendment before the
measurement it governs runs. The finding also discloses the material unverified rate
(a timing property of the 32B's speed against the verification timeout — the P3 retry
discipline is the named response) and the one field correction the run surfaced (the
autopsy-stem alignment the comparison refused, landed test-first). Read
`docs/planning/larger-base-arm/finding.md` and `reports/larger-base/` before quoting
anything about it.

**P2's first slice — rollouts and expert iteration — is done** (`docs/ROADMAP.md` § P2; plans at
`docs/planning/p2-rollouts/{sampling,sft,night-door}/`). The project's namesake finally exists:
`whetstone run --night` draws `K` seeded attempts per task under the hardened contract, keeps
**only** the rollouts the STRICT verifier passed, LoRA-SFTs the base on those, and writes
`runs/<id>/` (ledger, dataset, per-draw journals and transcripts) plus a hashed candidate under
`checkpoints/<id>/`. All four P2 exit criteria are asserted as tests rather than described: the
door produces both directories, **every** training example carries a recorded strict-PASS
verdict, two nights at one seed produce a byte-identical training set, and the ledger records the
pinned seeds, model revision, task set and tool versions.

**The new package is `src/whetstone/loop/`, partitioned EXEMPT on the `bakeoff` precedent, and it
composes rather than re-decides.** `freeze`/`Sealed`/`Recording`/`Retry`, `control.probe`,
`harness_status`, `sweep.rankable`, `Journal`, `Transcript`, `load_weights` and — critically — the
single definition of *solved* (`report.tally`'s `Outcome.SOLVED`, imported by identity) are all
the bake-off's own. The one genuinely new seam is the sampled draw: `sampling.K = 8` is a
**declared constant, never a flag** (raising it is the roadmap's named response to a low yield,
as a diff before a night), the per-attempt seed is `sha256(run_seed, task_id, attempt)` — never
the builtin `hash`, which is process-salted and would have made the determinism criterion a
statement about `PYTHONHASHSEED`, asserted by a cross-process test — and `sampler_for(1)` returns
`mlx_runtime.greedy_sampler` **by identity**, so a single-draw night and the bake-off are one
experiment. `Draw` wraps outermost so a retry re-asks *within* a draw and consumes no new seed;
one journal and one transcript live **per draw index**, because both are keyed `(candidate, task)`
and `K` draws of one task would otherwise collapse to the last. The control arm runs **once per
task** and is shared across the draws, and a resumed night reuses the recorded probe rather than
taking a second one.

**`cli.py` gains the one edge this repository has from a guarded root into an exempt package**, and
it is argued rather than excused: `run --night` holds a single **function-local** import of
`whetstone.loop.night` inside its handler, so `whetstone verify` never executes it and never
imports `mlx_lm` even transitively. `tests/test_reward_path_scope_is_partitioned.py` asserts it is
the only such edge **and** that it is function-local, both watched failing against planted
imports; a second one, or the same one at module scope, fails the build.

**The refusals are the part worth reading.** `UNVERIFIED` is not training data and neither is
anything else: the trainable partition is enumerated against `Outcome` and asserted complete, an
example must carry `SOLVED` *and* a recorded strict `PASS`, and a win from a run whose control arm
proved nothing is refused by name. A zero-strict-PASS night is a **published outcome** — it writes
no checkpoint, states the empty result in its ledger, and exits non-zero — because an adapter
trained on nothing is indistinguishable, to P3's gate, from one that learned something. The
LoRA capacity probe is D7-style and declared before it ran (a named step count, a stated headroom
against 36 GiB, with gradient checkpointing and accumulation **pre-committed on** so a failing
probe has nothing left to try); exceeding it is a capacity finding, not a constant to edit. The
valid split below its declared floor is *no valid split*, stated verbatim in the checkpoint's
provenance. The checkpoint is hashed weights-style with a `verify_checkpoint` re-hash, so P3 can
re-verify the bytes it compares.

**Nothing is published by this unit and `reports/` gains no directory.** A night's counts live in
its own gitignored `runs/<id>/`, which is their only home; the ledger and the dataset document
carry hashes and verdicts and never contents (canaries plant donor source text and assert it
cannot reach either), and both documented homes are asserted gitignored. **No `PREREGISTRATION.md`
§ 10 amendment was made, deliberately**: § 10 discloses published *series*, and this unit publishes
none. The loop's generation contract does differ from every published one in its `sampler` field
(categorical, seeded, versus greedy) — that difference is recorded in every run ledger, and the
amendment belongs to whichever later unit first publishes a figure measured under it.

**The night itself has not been run.** The machinery is shipped and the operator's sheet is
written (`docs/planning/p2-rollouts/night-door/runbook.md`, held by
`tests/test_night_runbook_guards.py`: flags pinned to the shipped parser, writable paths absolute,
exactly one worktree, the five declared dev ids, the retained/excluded candidate resolution, and
the zero-yield rule stated as a result rather than a halt — watched failing against a deliberately
wrong stub sheet). The GPU pass is operator-executed, as every arm in this repository has been.

**P3's first aspect — the held-out split — is done** (`docs/planning/p3-promotion-gate/heldout/`;
spec at `spec.md`, plan at `plan_20260824.md`). The artifact `PREREGISTRATION.md` § 7.1 named
open until P3 exists, fixed before it scores anything: `src/whetstone/loop/heldout.py` holds the
pre-committed rule — `HELDOUT_BANDS = 3` terciles over the 66 source-B tasks ordered by the
stratum document's per-task difficulty (files / hunks / added+deleted, reused as the ordering
key by identity, never a new axis), `MIN_HELDOUT = 10`, `MIN_PER_BAND = 2`, and per-band
selection by `sha256(split_seed, task_id)` with the seed a declared constant — and
`tasks/heldout/source-b.json` (schema `whetstone-heldout/1`) declares the membership: 12 of 66,
four from each band, sealed by a rule digest (rule source + declared constants) and a document
digest the loader refuses a hand-edit of. The loader is fail-closed by name
(`HeldoutSchemaError`, `EmptyHeldout`, `HeldoutDigestMismatch`): unknown fields, duplicated
memberships, members the document refused rather than measured, digest mismatches, and
empty/whole-corpus/floor-unmet splits are each refused in the writer and the loader alike — a
corpus that cannot meet the floors is the § 7.1 published finding, never a loosened floor. The
door is `python -m whetstone.loop.heldout --corpus ... --out ...` (refusing a gitignored `--out`
by name, the stratum roots imported by identity), the membership recomputation test re-derives
the document from the machine corpus field by field (skipping in CI with the reason named), and
the locality canary holds: the document carries counts, bands and ids, never task contents.
`PREREGISTRATION.md` § 10.7 (Type 1, § 8.1, 2026-08-24) closes § 7.1 with the split size, the
stratification rule and the document location, committed before the split is used to score
anything; §§ 7.2 and 7.3 remain open.

**P3's third aspect — `gate-core`, the gate itself — is done** (`docs/planning/p3-promotion-gate/gate-core/`;
spec at `spec.md`, plan at `plan_20260824.md`). `whetstone gate --candidate X --incumbent Y
--heldout <doc>` now exists and returns exactly one of the three exits the roadmap fixes
(`docs/ROADMAP.md:420-427`): `promoted` → 0, `rejected` → 1, `UNVERIFIED` → 3, refusals → 2 —
no fifth code. The body lives in `src/whetstone/loop/gate.py` (EXEMPT on the `loop` precedent),
and `tests/test_reward_path_scope_is_partitioned.py` grew from one documented, function-local
edge into the exempt package to **exactly two** — `whetstone.loop.night` and
`whetstone.loop.gate`, each proven able to fail against a planted module-scope import, a third
failing the build. The gate composes, never re-decides: both checkpoints are re-hashed through
`sft.verify_checkpoint` by identity before anything compares (`CheckpointUnverified` refuses
naming the checkpoint); the held-out document is consumed through aspect 1's fail-closed loader
by identity (a held-out set of zero refused by name, a membership id matching no loaded task
refused with the loaded ids); scoring is the bake-off's own `scoring.score` with the greedy
sampler `sampler_for(1)` by identity, so a single-draw gate eval and the bake-off are one
experiment; per-task verdicts fold through `verify.verdict.reduce` by identity (UNVERIFIED
above PASS); and the single definitions of solved and unverified are `Outcome.SOLVED` and
`report._UNCOVERED` by identity. The decision core (`decide`) is a pure function over two
outcome maps — `promote iff solved_new > solved_old AND regressed == 0 AND unverified == 0` —
tested on the full decision table: known-better → promoted, known-worse → rejected, equal
solves → rejected by the `>` term (never a tie-break), candidate == incumbent → rejected
(asserted, not accidental), one still-unverified task → the WHOLE eval is `UNVERIFIED`, and a
regressed task rejects even with a solved gain. Source A is scored in full and reported beside
source B, both denominators disclosed; coverage is the sibling rule (unverified stays in the
denominator); the unverified rate appears in the output as a count over its denominator. The
promotion record is written to the gitignored `runs/promotions/<id>.json` (schema
`whetstone-promotion/1`), whose home is asserted gitignored and which is refused inside a
`reports/` directory by `_refuse_published_root` imported by identity: both digests (re-hashed),
the held-out document digest, per-side verdict counts over both denominators, the decision with
every count it was read from, the retry discipline's own fields (aspect 4), tool versions, and
`recorded_on` — an input, never the clock. The one new machine seam is `gate_engine` (base +
LoRA adapter via `mlx_lm`, smoke-tested only — every test injects the stub engine), and the
per-task scoring seam the retry discipline wraps is exposed: the no-verdict tasks are
carried out of the run with their first-attempt completion hashes, and a FAIL stays FAIL —
the seam is not credulous. **The gate has not been run on real checkpoints** — fixture
checkpoints and the stub engine prove the three-exit differential; the operator's sheet (aspect
6) scripts the first real evaluation.

**P3's fourth aspect — the `retry-discipline`, the gate's liveness — is done**
(`docs/planning/p3-promotion-gate/retry-discipline/`; spec at `spec.md`, plan at
`plan_20260824.md`). `unverified == 0` is the honest term in the gate rule, and a gate
demanding exactly zero of a real machine would never fire (`docs/ROADMAP.md:429-443`), so a
held-out task that reached **no verdict** is scored again up to `R` times and a task that
verifies on retry is verified. `RETRY_COUNT = 3` is a declared module constant, never a flag —
a run that could choose its own budget would make the § 7.2 amendment a formality, and a test
asserts the door offers no retry knob. **What makes the retry safe is what it cannot do.** It
never retries a **verdict**: `_is_retryable` is `report._UNCOVERED` by identity, so `NO_DIFF`,
`NOT_APPLIED`, `NOT_SOLVED` and `OUT_OF_SCOPE` are final — and the differential is proven, not
argued, on a machine whose verifier comes up SOLVED the second time it is asked, where a
deliberately credulous predicate ("anything not SOLVED") promotes a candidate that is **not
better than its incumbent** while the shipped one rejects, watched failing first. It never
re-generates: `_Replay` answers exactly the recorded completion of the first attempt and
raises `RetryInputsChanged` on any other prompt, and the base is *measured* as being asked
each prompt exactly once however many times a task is scored — so "identical inputs" is a
check the code performs rather than a property argued from greedy sampling. A task with no
recorded completion (`UNPROVISIONED`, `NO_ORACLE`, neither of which reaches the generator) is
never retried at all — there is nothing to replay, a "retry" of one would be a fresh
generation wearing the name of a retry, and it keeps the eval `UNVERIFIED`, which is the
honest direction because the gate's default is don't promote. The budget is **per task**, not
per run (a run-wide budget would make liveness a property of how many tasks wobbled), a task
still without a verdict after `R` retries keeps the **whole evaluation** `UNVERIFIED` — not
promoted and not rejected — and the retry sequence is asserted deterministic down to the
recorded evidence on disk. The promotion record carries all three retry facts (the declared
`R`, every task the retry fired on with what it took, and the set that outlasted the budget;
hashes and verdicts only, never contents), and `disclosure` carries an **unconditional**
liveness line — `R`, what was spent, and the unverified count over its denominator, from the
first evaluation onward — because a line that appeared only on trouble would make a clean
machine and an unmeasured one read identically. `PREREGISTRATION.md` § 10.8 (Type 1, § 8.1,
2026-08-25) closes § 7.2 and says plainly that `R = 3` is **declared, not derived**: § 7.2
asks for it to be set from the observed unverified rate, no such rate has been observed
because no gated evaluation has run, and the revision path is a further dated amendment
grounded in a measured rate — never a code edit alone. Flakiness is simulated at exactly one
seam (`gate._score_one`); everything in front of and behind it is the real path — real
prompts, real extraction, real `git apply`, real STRICT. § 7.3 remains open.

**P3's fifth aspect — `check-leakage`, the exclusion proven — is done**
(`docs/planning/p3-promotion-gate/check-leakage/`; spec at `spec.md`, plan at
`plan_20260824.md`). The roadmap makes this its own exit criterion (`docs/ROADMAP.md:449-450`)
separately from the exclusion that prevents the overlap, and the separation is the point: the
night drops the held-out ids at its partition seam, that is a behaviour, and a behaviour nobody
checks is a claim — the one claim this project cannot make on trust being that its headline was
not measured on its own training data. `whetstone check-leakage --run <runs/id> --heldout <doc>`
exits 0 when the two sets are disjoint, **1 with the leaked task named**, and 2 on a refusal
(the existing four-code contract, no fifth; there is no `UNVERIFIED` here, because the command
reads documents rather than running anything). `src/whetstone/loop/check_leakage.py` names an
overlap rather than counting it — the fix for a leak lives in the night that produced it, and
the id is how that night is found — and the disclosure says what a nonzero exit is *evidence
of*: a regression in the partition seam, because the wrong response (dropping the leaked
examples after the fact and re-running) would leave the defect in place and print a clean
result. Ids and examples are counted in their own units (a task drawn `K` times is one id and
several examples), both sources are reported over their own denominators with source A's
overlap **measured** empty rather than assumed, and a night that trained on nothing is
*disjoint by truth* in those words — a zero-strict-PASS night and a night checked and found
clean are different facts. The subject is `runs/<id>/dataset.json` (what was actually trained
on), never the ledger's task set (what was considered); the ledger is read only to identify the
directory as a night's run. The refusals are the rest of it: an unreadable dataset is refused
rather than treated as empty (the two exit identically and are opposite facts), a schema-valid
document with no examples list is refused rather than defaulted, a third source name is refused
rather than filed under one of the two, and the held-out document goes through aspect 1's
fail-closed loader **by identity** before any comparison — the adversarial fixture swaps the
leaked id out of the membership without regenerating the digest, the edit someone would make
to turn a failing check green, and is refused by the digest rather than by the floor. **The
partition guard grew to exactly three documented function-local edges** — `night`, `gate`,
`check_leakage` — watched failing in both halves before the constant was extended and proven
able to fail again afterwards against a planted fourth edge and a planted module-scope import.
The third needs no inference library and never will, and is function-local anyway: the argument
is about the module graph of `whetstone verify`, and `check_leakage` imports the night for the
two source names.

**P3's sixth aspect — the `gate-runbook` — is done, and P3's machinery is complete**
(`docs/planning/p3-promotion-gate/gate-runbook/`; spec at `spec.md`, plan at
`plan_20260824.md`, sheet at `runbook.md`). The operator's sheet for the first evaluation that
decides whether a night's candidate may replace the incumbent, held by
`tests/test_gate_runbook_guards.py` on the night-door precedent: nine pinned properties (flags
against the shipped parser, every path absolute, one worktree and no stale one, the promotion
record's home by identity, the machinery verified before the real pair, the liveness sentence,
and the `UNVERIFIED` exit as a published outcome), watched failing against a deliberately wrong
stub — relative paths, a `--retries` flag the gate does not define, a renamed record home, a
stale worktree, `R = 7`, no fixture verification, and a "rerun until it promotes" instruction —
where ten of the eleven tests refused it. **Two pins are the ones worth reading.** The retry
budget the sheet states is compared with `gate.RETRY_COUNT` **by identity** rather than with a
number written into the guard, so a later amendment that moves `R` fails on the sheet that
still quotes the old one. And the sheet may not tell the operator to rerun until an evaluation
verifies — re-running until it fires is selecting on the outcome, and would turn the honest
third exit into a slower way of promoting; the guard checks for the phrasing and for the
roadmap's own response instead (*a more reliable sandbox, never a looser gate*). The sheet
states three things the machinery does not decide for anyone: the first gated evaluation needs
**two** nights (the night writes one checkpoint per night that selected something, and the gate
compares two); the § 3 baseline measurement is **not** performed here (P4's, spent once, and it
needs a checkpoint the night deliberately does not write); and a killed run resumes nothing —
the record writer overwrites the file at its `--run-id`, so the sheet says to use a fresh one,
which is the writer's actual behaviour stated rather than wished into idempotence.
`docs/ROADMAP.md` § 10 now marks the held-out split and `R` closed, each pointing at the
amendment that closed it.

**P4 slice 1 — the § 3 baseline machinery — is done, and P4 has begun** (`docs/planning/baseline-measurement/`,
merged 2026-08-26 as PR #17, cut as v0.9.0). `write_baseline_checkpoint` materializes the
untrained open base as a `whetstone-checkpoint/1` directory (`untrained: true`, no adapter;
`verify_checkpoint` extended by identity, the trained path byte-identical), and
`python -m whetstone.loop.baseline` scores it on the held-out source-B split plus source A
through `scoring.score` — STRICT and WEAK both, so baseline `N` is measured via
`report.tally`'s `weaker_wins` by identity — with the gate's retry discipline by identity,
the base-only engine seam, and the **measured-once guard keyed on the series identity**: the
base (`repo_id` + `revision`) plus the held-out document digest, because an untrained
checkpoint's digest is the constant `sha256("")` and cannot discriminate bases — the defect
was found at integration and fixed test-first. The committed home
`reports/baseline-measurement/` (schema `whetstone-baseline/1`) holds the three-artifact
shape, declaration-only until the operator spends the measurement; the one-home guard moved
a fifth time on the changed-series argument; the operator's sheet is
`docs/planning/baseline-measurement/measurement-run/runbook.md`, held by
`tests/test_baseline_runbook_guards.py`. **The number is unspent** — the measurement is the
operator's single GPU pass, exactly once — and **§ 7.3 stays open**: the 32B is recorded as
this series' pinned input, never a closure, and no § 10 amendment was made (the baseline is
§ 3 pre-authorized, not a new series requiring a disclosure).

**The launch path is decided, and was reordered 2026-08-28** (`docs/ROADMAP.md` § 12). P4's
first honest number is the launchable milestone. The operator order is now the § 7.3 Type 1
amendment → **night #1** → the first gated evaluation (candidate: night #1's checkpoint;
incumbent: **the untrained base**, not a second night) → spend the baseline → the P4 report
→ the finding. Two changes bought that, and neither loosens anything. The gate's first
incumbent is the untrained base: `verify_checkpoint` already accepts one (`sft.py:526-535`)
and `baseline_engine` is `gate_engine`'s untrained sibling, so the only obstacle is
`gate_engine`'s unconditional `adapter_path=` — the next code unit,
`gate-untrained-incumbent`, which also owns the gate runbook's "needs **two** nights"
paragraph and may not edit that sheet ahead of the code. And the baseline moves **last**,
because nothing before the P4 report reads it and § 3 lets it be spent only once, so a night
that forces a yield lever cannot strand it in an abandoned series. A gate scoring an
untrained incumbent is **not** a § 3 re-measurement — that clause forbids re-running to
confirm or because a result disappointed — and the two figures keep separate homes. One
unit is still buildable while the GPU is busy and reads no number: that dispatch. The other —
the **signed morning report (`whetstone report --last-night`)** — landed 2026-08-28 and is
recorded below. The Next.js dashboard and distillation remain post-horizon.

**P4 slice 2 — the honest-number report — is done** (`docs/planning/honest-number-report/`,
2026-08-27). The pre-registered § 4 shape now has its only legal home:
`reports/honest-number/` (schema `whetstone-honest-number/1`), rendered by
`build_honest_number_report`/`write_honest_number_report` in `report.py` — the sixth writer
on the shared-helper precedent (`_row`/`_over`/`tally` by identity, monkeypatch-proven) —
and by the module door `python -m whetstone.loop.honest_report`, which composes
`read_baseline_document`, `read_promotion_record`, `verify_checkpoint` and the writer **by
identity** and refuses every half-truth render by name, nothing written: an unmeasured
baseline, missing evidence, a failed re-hash, **series disagreement** (the delta is not a
delta across a changed pinned input), candidate/incumbent base disagreement, and a
same-series artifact already at `--out` (measured-once by analogy). **Whose counts are
"final" is the gate decision's function** — promoted → candidate, rejected → incumbent (the
candidate disclosed as the rejected attempt), UNVERIFIED → no headline, "no comparison was
made"; coverage renders on both sides. The dig found one gap the brief lacked: `N_final`
had no on-disk source — the promotion record's `SideCounts` now carries `weaker_wins`
(recorded at scoring time, `report.tally`'s definition by identity) and the record gained
its long-anticipated fail-closed reader. The **harness-reproduces-the-number check** (P4
exit criterion 3) is proven at the count level: the report is a pure function of the two
sealed evidence documents, byte-identical across invocations and subprocesses under
`PYTHONHASHSEED` 0/1, with the baseline-side figures byte-equal to the sealed artifact's
(the loader-by-identity exception) and the funnel figures byte-equal to the corpus ledger's
(the ledger-derived exception — both argued in the guard's sixth move and the § 10.9
disclosure). `PREREGISTRATION.md` § 10.9 (Type 2, 2026-08-27) discloses the final side's
generation contract — the loop's seeded categorical sampler — **before any figure existed**,
the amendment CLAUDE.md's own sampler line owed whichever unit published first under the
loop's contract. The operator's sheet is
`docs/planning/honest-number-report/report-runbook/runbook.md`, held by
`tests/test_honest_number_runbook_guards.py` (ten properties, flags pinned to the shipped
parser by identity, watched failing against a wrong stub where nine of ten refused it).
**The report is unspent**: `reports/honest-number/` holds the declaration-only state —
"**No count is measured here: the report has not run.**" — until the operator chain
completes. The partition guard still holds exactly three edges (module doors only; the
morning report's `whetstone report` subcommand is the next unit's fourth).

**P4 slice 3 — the signed morning report — is done** (`docs/planning/morning-report/`,
2026-08-28). `whetstone report --last-night` exists: core-loop element ④, the first surface
that turns a night's sealed evidence into a page a person reads.
`src/whetstone/loop/morning.py` holds a fail-closed **typed** ledger reader (`ledger.read`
checks the schema and hands back a raw mapping; every field this renders is one an optimistic
parse would default, so each missing, mistyped or unknown field is refused by name in the
`read_promotion_record` shape), the render, and the door.

**Three decisions are the content.** *"Signed" means **sealed to its evidence**, never
cryptographic* — `pyproject.toml` declares zero runtime dependencies and no signing library
exists in any group, and a signature would prove authorship rather than honesty. The page
states its own boundary: re-rendering proves the report matches the evidence, **not** that the
evidence matches the run — a hand-edited ledger re-renders consistently, because a ledger is
not self-sealing and only the checkpoint's digest is re-derivable from bytes. *"Last night"
resolves by the greatest **declared** `recorded_on`*, never mtime and never the clock: the run
id is operator-declared and `recorded_on` is an input, so mtime would be a property of the
filesystem (a restored backup shares one timestamp across every night). A tie is
`AmbiguousNight`, refused by name and pointing at `--run`; a night whose ledger will not parse
refuses the **whole scan** rather than being skipped, because skipping makes a killed night
invisible to the one command whose job is to notice it. And *the promotion record must belong
to this night **by checkpoint digest***, not by run id — the brief said run id and integration
proved that wrong, since a record's `run_id` is the *gate evaluation's* operator-declared name.

**Nothing is published and the one-home guard does not move.** The home is the gitignored
`reports/local/nightly/<run-id>/` — `.gitignore` pre-declared it naming "the morning reports",
and `tests/bakeoff/test_report.py:2076-2087` already excludes that prefix from the
published-artifact list on the argument that it is the user's data and never ours to assert on.
That carve-out is now asserted from this side too, because this unit's home exists only because
of it. `night._refuse_published_root` could **not** be reused by identity — it refuses any path
with a `reports` component and would refuse this unit's own home — so `refuse_published_out` is
its narrower sibling, raising `TranscriptNotPrivate` by identity and checked on the resolved
path. No `PREREGISTRATION.md` § 10 amendment: § 10 discloses published *series*, and this
publishes none.

**Two artifacts, not three** (`report.md`, `report.json`, schema `whetstone-morning/1`): a
night produces no cost document, and an empty `cost.json` would assert a measurement nobody
made. The render is a pure function of two documents — proven by making every file read raise —
so it cannot reach a published home and restate a figure whose only home is elsewhere, and it
is byte-identical across processes under `PYTHONHASHSEED` 0/1. Every unflattering state renders
as itself: a zero-yield night quotes the ledger's own `checkpoint_absent` reason verbatim, a
night with no gate says *"no gated evaluation is recorded for this night"*, and an `UNVERIFIED`
evaluation says **no comparison was made** with `PASS` appearing nowhere in that section —
each watched failing against a renderer that gets it wrong.

**The partition guard grew to exactly four documented function-local edges** — `night`, `gate`,
`check_leakage`, `morning` — watched failing in both halves before the constant moved, and
proven able to fail again afterwards against a planted fifth edge and against the fourth moved
to module scope.

**Two corrections landed with it, and both are the recurring kind.** `cli.py`'s module
docstring counted four commands, omitted `check-leakage`, and said no report command existed —
three false claims in the file's own first paragraph — and it is now asserted against the
parser rather than proof-read. And `README.md`'s status table listed the promotion gate and the
held-out split as ❌ Not built months after P3 merged them, and claimed *"No tags, no PyPI
package, no version"* with v0.3.0–v0.10.0 published: the same failure this file already records
against itself, recurring because nothing was checking. A guard now checks it against `git tag`.

**The report has not been rendered from a real night**, because no night has been run. Its
refusals, its determinism and its three gate renderings are proven against fixture ledgers and
fixture promotion records — the gate's own posture. No operator runbook was written for it: it
is one invocation, no GPU spend and no ordering hazard, so a sheet would restate `--help`.

**What is not built.** The nightly loop has never been *run*, so no training set, checkpoint
or yield figure exists yet — and **the gate has therefore never been run on real
checkpoints**. Its three exits, its retry discipline and its refusals are proven against
fixture checkpoints, the stub engine and a simulated wobble; whether the gate can *fire* on a
real machine is unmeasured, and the roadmap's response if it cannot is a more reliable
sandbox, never a looser gate. `R = 3` is declared a priori for the same reason: there is no
observed unverified rate to set it from. The bake-off is base *selection*, not the pinned
baseline of `PREREGISTRATION.md` § 3 — the split has not scored anything, so "measured once,
re-measured never" is unspent. Cheat 6 and cheat 10 remain documented residuals; ingestion
narrowed cheat 10 with a `conftest.py` floor but did **not** close it. The cuts so far are
v0.3.0–v0.9.0, the last tagged 2026-08-26, and each one published `whetstonehq` to PyPI and a
GitHub Release by tag push. (This line read "nothing has been published to PyPI" until
2026-08-20; it had been false since v0.3.0, and PyPI's own index is what corrected it.)

Keep this file, `VISION.md`, and `docs/ROADMAP.md` in sync as direction firms up. Describe the
state of the tree this file ships in, and never work in flight on a branch — a status that
names in-progress work is stale the moment that work merges, which has already happened once
here. A capability is written up in the same commit that lands it, so the claim and the code
arrive together and neither can outlive the other.

