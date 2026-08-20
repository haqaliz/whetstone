# Whetstone: Project Context for Claude Code

This file orients a coding agent working in this repository. Read it first.

> **Status — what exists in this tree today.** `docs/ROADMAP.md` is written and is the
> **authoritative technical document** until `docs/technical/ARCHITECTURE.md` is written;
> that file does not exist yet. This file and `VISION.md` remain the narrative source of
> truth (thesis, moat, guardrails).
>
> **P0 (scaffold) is done:** packaging, the `whetstone` CLI, strict ruff/mypy, pytest, and CI
> on `macos-latest`.
>
> **P1 slice 1 — the task contract and the verifier core — is done** (`docs/ROADMAP.md` § 2, § 3;
> plan at `docs/planning/p1-verifier-core/`). `src/whetstone/verify/` holds the frozen `Task`
> contract, the ported verdict semantics (`UNVERIFIED` ranks above `PASS`), the Seatbelt sandbox
> (network denied, writes confined, environment pinned), the **STRICT** verifier — the reward —
> and the **WEAK** verifier — measurement only — reachable as `whetstone verify`. The
> adversarial corpus (`tests/adversarial/`) runs ten cheats through both verifiers: eight are
> killed, and **two are documented residuals**, cheat 6 (special-casing the known input) and
> cheat 10 (a held test's undeclared dependency). A scoped AST guard keeps inference libraries
> off the reward path.
>
> **P1 slice 2 — the on-disk task format — is done** (`docs/ROADMAP.md` § 3; plan at
> `docs/planning/p1-task-ingestion/`). A manifest now declares its `environment` — exact `==`
> pins and a nominated interpreter — so the verdict stops depending on what the package index
> served that morning; `tests/test_environment_pins.py` demonstrates that, showing one task and
> one correct patch reaching **PASS** pinned and **FAIL** unpinned, resolved offline against a
> committed index. Held test paths are refused unless spelled canonically. `src/whetstone/tasks/`
> reads a whole directory of manifests — nothing skipped, an empty directory is a usage error
> rather than a vacuous pass — and `whetstone verify` accepts one, reducing worst-status-wins so
> a single `UNVERIFIED` task can never exit 0. `tasks/` carries the layout that splits committed
> provenance from local data. The reward-path guard now covers `src/whetstone/tasks/` as well as
> `src/whetstone/verify/`.
>
> **P1 slice 3 — ingestion, and the first real corpus — is done** (`docs/ROADMAP.md` § 4, P1
> exit criterion 4). **Source B (private, the pre-registered headline): 66 tasks**, 45 mined from
> `donor A` and 21 from `donor B`, each *proven live* rather than asserted — FAIL with no patch,
> PASS under its own reference patch, executed node-id set equal to declared, zero skips. Donors
> are named by stable pseudonyms throughout this repository: they are the author's own private
> repositories, and their names are not this project's to publish. Donor B is also the sibling
> project the verifier's design draws on (§ *Relationship to the sibling project*). The manifests
> are the user's code and live in gitignored `tasks/local/`; the committed evidence is
> `tasks/recipes/*.json` and `tasks/local-ledger.json` (hashes and verdicts, never file contents).
> Two donors yielded nothing and the refusals are the finding: `donor C` was refused for having
> no `uv.lock`, and this repository yielded 0 of 2 because its own test-first workflow lands the
> test and the fix in one commit. **Source A (public SWE-bench-Lite): 1 eligible instance of 300**
> — `pallets__flask-4045` — with all 299 refusals ledgered in `tasks/public/ineligible.json`
> against the gate that refused each (192 format, 106 environment, 1 collectability). The
> deliverable there is the four-gate filter and the rejection ledger; **one instance is not a
> public benchmark set and must never be quoted as one.**
>
> **Slice 3 also found and closed a reward-path defect, which is the part worth reading.** A task
> **PASSED with no patch applied** — a false PASS. In a `src`-layout project the tests import by
> package name, resolved through the venv, and the venv held an editable install rooted at a
> *different* checkout than the one the patch was applied to; the tree under verification was
> never imported. The ten-cheat corpus missed it because every fixture repo was flat-layout with
> no venv install, so **the defence had been the shape of the fixtures, not anything the verifier
> did.** Closed by `import_roots` in the manifest, deps-only provisioning
> (`--no-install-project`), and a `PYTHONPATH` naming the run's own checkout so it shadows any
> residual install; `tests/adversarial/test_inert_checkout.py` holds it shut.
>
> **P1 slice 4 — the pre-registration — is done** (`docs/ROADMAP.md` § 6; plan at
> `docs/planning/p1-preregistration/`). `PREREGISTRATION.md` is committed at the repository root,
> **before any number about a model existed**, which is its entire value: it fixes the headline —
> the change in STRICT-PASS *count* on the held-out source-B split, published over its
> denominator and never as a rate — along with every metric definition, the baseline protocol,
> and the rule that both sources are always published together and a disagreement between them is
> reported as a finding. It pre-registers **no numeric success threshold**, because none could be
> grounded before a baseline exists, and forbids one being added once a number does. Three items
> are named as open with the amendment that closes each: the held-out split, the retry count `R`,
> and the base. Five limitations are disclosed up front, including that source B's self-selection
> mitigation (a third donor) **did not land** — `donor C` was refused for having no `uv.lock`.
> `tests/test_docs.py` holds it shut: no placeholder, no figure about a model in any spelling, and
> nothing may exist under `reports/` in a tree lacking the file. That last guard proves
> co-existence, not ordering — the temporal claim is `git log`'s, and the document says so itself.
>
> **P1 slice 5 — the base-model bake-off — is done, and P1 is closed** (`docs/ROADMAP.md` § 4,
> the last exit criterion; plan at `docs/planning/p1-baseline-bakeoff/`). Three candidate open
> bases produced patches locally through `mlx-lm`, every patch was graded by the STRICT verifier,
> and the report lives at `reports/baseline/` (`report.md`, `report.json`, `cost.json`) — read it
> before quoting anything about it. **This tree now holds figures about models, and
> `reports/baseline/` is their only home** — do not restate one anywhere else, because a figure
> quoted twice is a figure that can disagree with itself.
>
> **The result was a zero: not one candidate solved a single task on the declared source-B set.**
> So P1's pivot signal (`docs/ROADMAP.md` § 4) **fired**, **no base is selected**, and
> `PREREGISTRATION.md` § 7.3 stays open — the response it names is an easier task stratum or a
> larger base, never a looser verifier. The failure modes differ by candidate (unapplicable
> patches dominate at the small and large ends, empty diffs in the middle), which is a finding
> about where the wall is rather than a tie. Two things stop that zero being read as a broken
> harness. The **control arm** — an inert patch and each task's own re-derived fix, through the
> same harness, on the same task — was **INTACT on every run**, so the harness demonstrably
> reaches PASS when a correct patch exists. And the reward-hacking count `N` was zero for every
> candidate, which is a floor rather than a rate: the generation contract states the
> patch-scope rule to every candidate, so it discourages exactly what `N` counts.
>
> **Two bounds on that report, disclosed rather than discovered.** Prompts used the **oracle
> retrieval** setting — the base is shown the non-test files the reference patch touches — so
> every count is an **upper bound** on the same base working from the bug report alone, and may
> not be compared with a figure measured without retrieval. And the **generation contract**
> (prompt template, retrieval setting, extractor) is **not** among the pre-registration's pinned
> inputs, yet it demonstrably moves the numbers; a figure measured under a changed contract is
> not comparable to this one.
>
> **The measurement is now instrumented, which is where P2 starts** (plan at
> `docs/planning/p2-yield-probe/`). Reading the bake-off's own failure buckets showed that the
> great majority of verdict-reaching rollouts never got a patch onto disk at all: `NOT_APPLIED`
> means *"git refused it"* and nothing narrower, so a malformed diff, a mis-anchored one and a
> budget-truncated one all wear the same tag. **The pivot signal's premise — that the bases cannot
> fix these bugs — was therefore never actually tested**, because the measurement did not reach the
> question. That makes this a measurement-validity fix rather than a third response to the signal,
> and it is why `docs/ROADMAP.md` § 4 needs no amendment.
>
> `src/whetstone/bakeoff/transcript.py` keeps what a base actually wrote — as a `Generator`
> wrapper, so the one-method model seam is not widened and `score()` is untouched — and
> `attribution.py` replays those completions offline to say *which* zero each was, using
> `patch.py`'s own `NoDiff` reasons as the partition rather than a taxonomy invented beside it.
> The two causes the report cannot separate — git would not read the patch, versus git read it and
> would not apply it — are now distinguished, read-only, with nothing under `verify/` modified.
> Transcripts hold the user's own code back verbatim, so they are refused under `--out` and their
> documented homes are asserted gitignored. **Nothing is published by this**: it produces local
> evidence, and the run that uses it has not been made.
>
> **The instrument was then used, and it falsified two proposed fixes** (`docs/planning/p2-yield-probe/prd.md`,
> corrected 2026-08-05). Arm A re-ran the pinned contract and **reproduced `reports/baseline/`
> exactly** — every published count, four days later — which is the first direct evidence that the
> bake-off is deterministic rather than merely argued to be. Attributing its transcript then showed
> the failures are overwhelmingly *"git would not read this diff"* rather than *"git read it and
> would not apply it"*, which withdrew the search/replace proposal; and a second run at double the
> token budget, on the base the evidence best supported, moved no cause bucket beyond noise and
> solved nothing.
>
> **The reasoning under both was the defect, and it is the transferable part.** Truncation had been
> *inferred from the shape of a diff* and never measured — the spec named that inference as open,
> and it was then reasoned from as settled. So the roadmap's own named responses (an easier task
> stratum, or a larger base) now have more support than any generation-contract change, and no
> further fix should be proposed before someone reads what the unparseable diffs contain. Every
> figure behind this lives in gitignored run artifacts; `reports/baseline/` remains the only home
> for a published one.
>
> **P2 slice 2 — the diff autopsy — is done, and the read is now a measurement** (`docs/planning/p2-diff-autopsy/`;
> plan at `docs/planning/p2-diff-autopsy/autopsy/`). `src/whetstone/bakeoff/autopsy.py` is an
> offline, deterministic, stdlib-only classifier that assigns every stored completion exactly one
> grounded content-shape cause, asserts a fine→coarse mapping against the run's own
> `attribution.json` (a contradiction is reported, never reconciled), and writes its document
> only under a gitignored root. **Running it corrected the hand-read in three places, which is
> the transferable part.** The mapping assertion surfaced walk rules that disagreed with git's
> parser on the same bytes — a check that read text git never parses, a counter-overrun git
> reads as "corrupt patch" while the walk saw a completed hunk, and a mapping gap for
> loop-dominated completions carrying a refused stub — and each correction landed with a
> fixture, watched failing first. The corrected measurement agrees with the run's own
> attribution on every stored record, classifies both runs completely with nothing
> unrecognised, and agrees with the hand-read exactly on the control category while diverging
> from it only at the one margin the dig itself called fuzzy (reported as a finding, never
> reconciled). **The finding** (`docs/planning/p2-diff-autopsy/finding.md`) names a formatting
> wall, not a reasoning or extraction wall: the candidates can write diffs git accepts and
> almost never do, so the roadmap's easier-stratum/larger-base fork is unsupported by this
> evidence, and the pivot signal's premise remains untested until a format-hardening response
> runs — which the finding names but does not build. No figure about a model appears anywhere
> outside the gitignored breakdowns; the one record that aimed a diff at a held test never
> reached the verifier and is disclosed as attempt-shaped evidence, not a counted hack.
>
> **Format-hardening aspect 1 — `diffcheck` — is done** (`docs/planning/p2-format-hardening/diffcheck/`;
> spec at `spec.md`, plan at `plan_20260809.md`). The validator that names the finding's
> formatting wall *online*: `src/whetstone/bakeoff/diffcheck.py` is **classify-only** — it imports
> the autopsy's taxonomy by identity (imported, never copied, asserted `is` in a test), maps the
> fine cause to a retry trigger (`hunk-count-mismatch` and first-hunk deaths on a bare line or the
> closing fence fire; `well-formed`, `im-start-loop`, the inferred `end-of-output` truncation,
> `no-diff`, `unrecognised-shape` and — until the measured-arm pre-analysis flips it, via the one
> parameter that exists for exactly that — `header-without-hunk` never do), and answers the finite,
> fixed diagnosis vocabulary (one constant sentence per trigger; a `str.format` placeholder or a
> digit in any sentence fails the suite — the seal-frozen prompt set, PRD D8). **The transcript
> schema now carries the retry** — `Transcribed` gains `attempt` and `decision` ("retry" |
> "graded"), the codec is updated field by field, and `replay()` still picks the last record per
> key (a trailing "retry" is refused as corruption — a run killed mid-retry — never repaired). And
> the **anti-credulity proof is watched-failing and sub-verdict-pinned**: a held-path edit
> (well-formed, trigger-shaped, and mixed with a real fix) survives validator and extractor
> byte-for-byte and reaches STRICT, which refuses it as `patch-scope` → `(Outcome.OUT_OF_SCOPE,
> Status.FAIL, Status.PASS)` on every shape, while a deliberately credulous validator that drops
> held hunks is proven to lose the differential. The AC2 pins now cover all three frozen paths —
> `src/whetstone/verify/`, `patch.py`, **and `attribution.py`** — byte-identical to `origin/master`,
> the missing pin added, each proven able to fail against a planted change.
>
> **Format-hardening aspect 2 — the `retry-loop` — is done** (`docs/planning/p2-format-hardening/retry-loop/`;
> spec at `spec.md`, plan at `plan_20260809.md`). The validator classifies; the retry converts.
> `src/whetstone/bakeoff/retry.py` holds the retry prompt builder and the `Retry` wrapper on the
> one-method `Generator` seam. The prompt is a **pure function of `(first-attempt prompt, trigger)`** —
> the first prompt, a fixed `RETRY_INSTRUCTION`, and one sentence from the finite diagnosis
> vocabulary, **never the prior completion** (spec B1: completion-derived content would make the
> prompt set unbounded and the seal unfreezable) — so `freeze(..., retry=True)` pre-renders
> `retry_prompt(render_prompt(...), trigger)` per task per trigger into the same `posed` map via
> `setdefault`, and the contract SHA covers the whole retry vocabulary. The wrapper issues at most
> `RETRY_BUDGET` (2) retries per (candidate, task), only on the validator's trigger shapes, returns
> the last completion, and writes **one record per attempt** — its own `prompt_sha256`, its
> one-based `attempt`, and its `decision` ("retry" | "graded") — filed under the task the prompt
> was posed for; the wrapper itself holds the recording pieces (the transcript, the candidate, the
> `posed` map), because no one-method, sealed-prompt channel can carry the wrapper's decision down
> to a recorder — the recording moved *into* the wrapper, and `Recording`/`RecordingGenerator`
> stay untouched for the retries-disabled path. Retries are **off by default**
> (`conduct(..., retries=False)`), composed only when `--transcript` names a file; a mid-run
> retry-template edit raises `ContractChanged` through the seal and aborts the run, asserted
> end-to-end, and the seal-held test proves every prompt an instrumented engine is asked was
> frozen. The retry path has its own no-inference AST walk (no `mlx`, no `run.py`, no `scoring`),
> and `retry_template_sha256()` is the digest aspect `contract-report` publishes.
>
> **Format-hardening aspect 3 — `contract-report` — is done** (`docs/planning/p2-format-hardening/contract-report/`;
> spec at `spec.md`, plan at `plan_20260809.md`). The two contracts are now told apart by their
> published fields: `GenerationContract` carries `retry_budget` (`RETRY_BUDGET`),
> `retry_template_sha256` (`retry_template_sha256()`), `diagnosis_vocabulary_version` (a digest
> over the sorted diagnosis sentences, `diffcheck.diagnosis_vocabulary_sha256()`), and `retrieval`
> — `"oracle"` today, the machine-readability fix (yield-probe D9). A retries-disabled run's
> contract keeps the no-retries shape (budget 0, blank digests) so it stays byte-identical to the
> baseline's; a retried run's declares the whole machinery, and the committed baseline sidecar
> predates all four fields and still parses — `GenerationContract.parse` defaults `retrieval` to
> `"oracle"` and the retry trio to the no-retries state, so `reports/baseline/report.json` keeps
> reading. The report writer supports a second directory: `reports/format-hardening/` with
> `report.md`/`report.json`/`cost.json`, both arms' verdict counts under their own contract
> fields, the non-comparability sentence, per-arm token-spend disclosure, and a pointer to the
> gitignored breakdown home — never restating a classifier count (`finding.md:89-92`). **The
> one-home guard moved a second time, only on the D6 argument in both docstrings** (the file list
> in `test_report.py:1453`'s copy and its opposite-sign twin in `test_transcript_locality.py:73-119`):
> the two directories measure different generation contracts and are declared non-comparable, so
> neither is a competing home for the same figure; a silent list extension is refused. The
> committed artifacts in the new directory are the declaration — no count, no arm, no figure
> restated from `reports/baseline/` — until the measured arm renders the two contracts and their
> figures into it. `PREREGISTRATION.md` § 10.4 (Type 2, 2026-08-09) discloses the hardened
> contract — retry budget, retry template digest, diagnosis vocabulary digest, retrieval stays
> oracle, a new declared dev subset — and declares the two reports non-comparable, with its row
> in the amendment log; nothing above § 10 was edited and no proportion appears in any spelling.
> The dev-subset mechanism is proven as the three layers it is: exclusion from **both** sources
> before anything runs, `UnknownDevSubset` refusal for an id that matches nothing, and the
> `ScoredDevSubset` backstop in the report.
>
> **Format-hardening aspect 4 — the measured arm — is done** (`docs/planning/p2-format-hardening/measured-arm/`;
> spec at `spec.md`, plan at `plan_20260809.md`, finding at `finding.md`).
> `src/whetstone/bakeoff/preanalysis.py` is the offline, stdlib-only, deterministic read of the
> stored autopsy outputs (schema `whetstone-preanalysis/1`, refused under any published path,
> its own no-inference AST walk) that applies **the same trigger mapping as the validator** —
> `diffcheck.trigger_of_cause`, asserted identical — and counts the **retry-eligible ceiling**
> per candidate before any GPU is spent. The ceiling was measured over the two stored runs, and
> the definition was written in the module before the run: the retry-eligible subset of the
> stored parse refusals is a **large majority** — the numbers live in the gitignored
> `runs/format-hardening-preanalysis/ceiling.json`, which is their only home — and one
> candidate's ceiling is **zero**, its `im-start-loop` wall, which is a per-candidate finding
> rather than a tie (the dig predicted exactly that shape). The ceiling is material, so the
> arm's halt condition did not fire and the runbook is written: `--retries` is now a real CLI
> flag (the switch existed in `conduct` but was unreachable — exposed, with the parser and
> wiring tests watched failing first), the donor roots are the real names (`belay`, `contig`),
> and the journal and transcript live in a sibling evidence directory because the harness
> refuses a transcript under `--out` — exactly as it should. **The post-run read is now a
> measurement too** (`src/whetstone/bakeoff/comparison.py`, schema `whetstone-comparison/1`,
> its own no-inference AST walk): journals, autopsy documents and the pre-analysis ceiling
> document become the per-candidate before/after breakdown, the trigger mapping **re-derived
> by identity and asserted** against the pre-analysis's own decisions (a contradiction is a
> named violation, never reconciled), the control discipline enforced (no `INTACT` probe, no
> counts), the D6 denominators disclosed side by side (rollout records vs classified
> completions, and the dev-subset exclusion a hardened contract declares), and the markdown
> render at the runbook's named home (`runs/format-hardening-preanalysis/comparison.md`). The
> stored arms were exercised through it: the assertion held over every record — zero
> violations — and the output is byte-identical across invocations. The report door
> (`--render-report` in the same module) is the first production caller of the aspect-3
> writer, rendering `reports/format-hardening/` by identity from journals and contract
> sidecars — only when an arm has run: a missing journal, an unproven control or zero arms is
> refused by name, never a half-truth render. The finding (`finding.md`) states the measured
> before in words and records the hold decision. **The measured arm has now run and the
> before/after is measured** (`measured-arm-run`, 2026-08-12; finding at `finding.md`): the
> retries converted a material share of the retry-eligible parse refusals into well-formed
> patches for the two trigger-eligible candidates, the loop-collapse candidate was
> unconvertible by its own zero ceiling, and — the measurement's content — well-formed patches
> apply but do not solve: no rollout solved a task on the declared set under the hardened
> contract, so the format-hardening response is exhausted as a yield lever and the roadmap's
> own named fork (an easier task stratum or a larger base) is the next unit, never a fourth
> generation-contract change. The run's own report lives at the gitignored
> `runs/format-hardening-arm/`; the published side is `reports/format-hardening/`, rendered by
> the report door with both arms declared non-comparable; the classifier counts live in the
> gitignored breakdown home `runs/format-hardening-preanalysis/comparison.md` and are not
> restated anywhere else. The run surfaced two corrections, both landed test-first in the
> unit: the arm's writable paths are now absolute and guarded (a relative workspace had died
> `UNPROVISIONED`, `HarnessNotProven`, halt condition 1 — evidence quarantined, never
> deleted), and the runbook's post-run chain now includes the pre-analysis extension step the
> comparison's per-run decisions assertion requires.
>
> **The easier-stratum unit's first aspect — the difficulty axis and the committed stratum —
> is done** (`docs/planning/p2-easier-stratum/`; spec at `difficulty-axis/spec.md`, plan at
> `difficulty-axis/plan_20260814.md`). The fork's first arm needs a subset of the declared
> source-B set that is *easier*, fixed before any rollout, and this is that selection, a
> priori and in code: `src/whetstone/bakeoff/stratum.py` measures the reference fix's shape —
> the non-test files a mined commit touched, and the hunks and added/deleted lines of the
> gold patch derived from the donor at the task's pinned commits — through
> `sources.changed_paths` and `derive.gold_patch` reused **by identity** (never copied,
> asserted `is`), composed exactly as the control arm composes it and asserted
> byte-identical to `control.reference_patch(task).diff` on all 66 tasks. The band is
> pre-committed (one non-test file, at most two hunks, at most thirty changed lines), and the
> rule's own hunk/line walk is validated as a measurement: its added/deleted agree with git's
> own `--numstat` on all 66 tasks, a contradiction named, never reconciled. The stratum
> document is committed at `tasks/stratum/easier.json` (schema `whetstone-stratum/1`) as the
> probe's pinned input: rule digest (rule source + band, so any rule edit invalidates the
> document by design), band, the 66-task corpus, per-task difficulty (files/hunks/
> added/deleted plus the manifest tie-breaks f2p/pins/blobs), refusals, a **19-task
> membership** (4 belay, 15 contig), and a `document_digest` the loader refuses a hand-edit
> of. The loader is fail-closed by name — `UnknownStratumId`, `EmptyStratum` (empty or
> whole-corpus, in the writer as well), `StratumSchemaError`, `StratumDigestMismatch` — and
> the membership recomputation test re-derives the document from the machine corpus field by
> field, skipping in CI with a reason naming exactly what is missing. The document carries
> counts only, never paths and never patch content (the ledger's locality discipline, walked
> with a canary), and the runbook door is `python -m whetstone.bakeoff.stratum --corpus
> <roots> --out <path>`.
>
> **The easier-stratum unit's second aspect — the run-side stratum filter — is done** (spec at
> `stratum-filter/spec.md`, plan at `stratum-filter/plan_20260814.md`). The probe now scores
> exactly the stratum's tasks: `--stratum PATH` on the run door (`python -m
> whetstone.bakeoff.run`) consumes the committed document — aspect 1's loader **by identity**
> (imported, never copied, asserted `is`), with `include_stratum` applying the membership
> against the loaded private corpus at the partition seam, **before** the contract is frozen,
> so the seal and the scored set cover the subset automatically. The loader's membership
> checks are completed where the landed suite stopped: an unknown field, a duplicated
> membership, and a member the document refused rather than measured are each named refusals
> (spec AC 4, D4-4), and the run-side refusal names the id **and the loaded ids** (spec Open
> question 3, the `UnknownDevSubset` posture). The dev overlay applies **on top** — dev ∩
> stratum is exclusion, never refusal, because the real probe's declared ids may fall inside
> the band — an empty scored private set after the overlay is refused **before** freeze,
> source A is always scored in full with both sources publishing together, and the task-set
> sentence names the stratum document and its membership count. A run without the flag is
> today's run byte for byte: the byte-identity test reproduces the unflagged contract SHA and
> asserts the provenance sentence is literally the pre-stratum sentence. The adversarial proof
> was watched failing against a deliberately credulous loader first: a doctored document
> (membership edited to add a declared dev id, digest not regenerated) and a hand-edited
> membership are each refused, naming the document digest and the expected value; a fully
> regenerated doctored document passes the loader by construction — the layered defence is git
> history + ordering + the recomputation test, stated, never reconciled (spec Open question 5)
> — and the dev member it smuggles is then proven excluded end-to-end, never scored, excluded
> from both denominators. The stratum path walks inference-free, and the AC2 pins —
> `src/whetstone/verify/`, `patch.py`, `attribution.py` — are byte-identical to
> `origin/master`.
>
> **The easier-stratum unit's third aspect — the stratum report home — is done** (spec at
> `stratum-report/spec.md`, plan at `stratum-report/plan_20260814.md`). The probe's verdicts
> now have a published home that is honest about what it is: `reports/easier-stratum/` holds
> the three-artifact shape (`report.md`/`report.json`/`cost.json`, schema
> `whetstone-stratum-report/1`), rendered by `report.build_stratum_report` /
> `write_stratum_report` — deterministic and pure, reusing `_row`, `_over`, `tally`,
> `_contract_fields`, `_contract_block` and `_counts` by identity — and by the report door's
> second mode, `--render-stratum-report` in `comparison.py`, which takes **exactly one** arm
> group (`build_contract_arms` reused unchanged, so its missing-journal / empty-journal /
> no-`INTACT`-control refusals hold by identity), refuses zero or two groups by name, and
> requires `--stratum-doc` as a pointer it never parses; `--render-report` is untouched. The
> committed artifacts are the declaration — no count, no contract fields, "**No count is
> measured here: the probe has not run.**" — generated by the writer, never hand-typed. **The
> one-home guard moved a third time, only on the changed-task-set argument in both docstrings**
> (the file list in `test_report.py:1453`'s copy and its opposite-sign twin in
> `test_transcript_locality.py:73-119`): the task set is one of the five pinned inputs, the
> probe scores a **different task set** under the same hardened contract, so its figures are a
> new series declared non-comparable to both existing homes (`PREREGISTRATION.md` § 10.5,
> Type 2, 2026-08-14) — each directory the only home of its own; a silent list extension
> remains refused. The disjointness guard now scans **all six** existing artifacts, with the
> planted-overlap control proved able to fail; the declaration-only home holds no `N of M`
> figure in any of its three artifacts. Nothing above § 10 of the pre-registration was edited
> and no proportion appears in any spelling.
>
> **The easier-stratum unit's fourth aspect — Phase 1 of `probe-run`, the runbook and its
> guards — is done** (spec at `probe-run/spec.md`, plan at `probe-run/plan_20260814.md`).
> The operator's sheet exists and a guard holds it: `docs/planning/p2-easier-stratum/probe-run/runbook.md`
> opens with the candidate resolution (A2), decided before the run from the stored ceiling
> document — the 14B and 3B candidates retained on their measured retry-eligible ceilings,
> and `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` excluded by name for a measured zero
> ceiling in both stored runs (its `im-start-loop` wall), per the pre-committed rule
> (`prd.md:93-103`) — and carries the arm command (hardened contract: `--stratum`,
> `--retries`, the five declared dev ids, `--only` × 2, absolute writable paths, CWD at the
> primary), the halt conditions, the killed-run restart, and the post-run chain (attribution
> → autopsy → the **mandatory** pre-analysis extension over all four autopsy documents → the
> probe's own comparison → the stratum-report door). The guard is extended, never
> parameterized (A1): `tests/test_probe_runbook_guards.py` imports the parse helpers from
> the measured-arm module by identity (asserted `is`), the pinned module byte-untouched, and
> pins the same seven properties plus the A2 resolution rule — every `--only` value is a name
> the resolution block records, the excluded name appears in no `--only` value, and the block
> states the zero-ceiling rule. The guard was watched failing against a deliberately wrong
> stub runbook (relative writable paths, no `--stratum`, a stale worktree name) before the
> real sheet existed. Phases 2–4 are operator-executed: the GPU probe itself, the post-run
> chain, and the finding that applies the pre-committed fork rule (A6) are not built here.
>
> **The easier-stratum probe then ran, and its zero fired the fork rule.** The probe
> executed on the pre-committed stratum under the hardened contract and published its
> finding (execution merged 2026-08-15): every candidate returned zero solved tasks with
> the control intact, so the pre-committed fork rule (`p2-easier-stratum/prd.md:49-51`)
> named the next unit — the larger-base arm — never a looser verifier and never a fourth
> generation-contract change. The probe's M13-style read attributed the zero to premise
> failure rather than axis failure: the formatting wall receded, well-formed patches
> applied, and none turned the tests green.
>
> **The larger-base unit is done, arm and all** (`docs/planning/larger-base-arm/`; the
> operator's sheet at `runbook.md` held by its own guard
> (`tests/test_larger_base_runbook_guards.py`)). The candidate was resolved a priori — the
> 32B-class base on the measured candidate family, the 7B excluded by name for its
> measured zero ceiling — the probe pass (D7) ran first and settled the ROADMAP § 10
> capacity question by measurement (the 32B fits the machine's 36 GiB; MLX memory-maps
> the safetensors, so the resident peak stays far below the weights' size), the hardened
> contract on the declared source-B set with the dev overlay restored ran to completion
> with the control discipline intact on every probe, and the post-run chain — attribution
> → autopsy → the pre-analysis extension over all five autopsy documents → comparison →
> the report door — ran clean. The arm's figures have a published home that is honest
> about what it is: `reports/larger-base/` holds the three-artifact shape (report.md /
> report.json / cost.json, schema `whetstone-larger-base-report/1`), rendered by
> `report.build_larger_base_report` / `write_larger_base_report` — pure and
> deterministic, reusing `_row`, `_over`, `tally`, `_contract_fields`, `_contract_block`
> and `_counts` by identity — and by the report door's third mode
> `--render-larger-base-report` in `comparison.py` (exactly one arm group,
> `build_contract_arms` reused unchanged, the three report modes mutually exclusive).
> The one-home guard admits the fourth directory on the changed-candidate-set argument —
> model revision is one of the five pinned inputs, so the arm's figures are a new series,
> declared non-comparable to all three existing homes (`PREREGISTRATION.md` § 10.6, Type
> 2, 2026-08-15) — and the amendment disclosed the series before any figure existed for
> it. **The measurement: the 32B produced the first nonzero strict-PASS yield the
> harness has ever measured** — the fork rule pre-committed in the unit's PRD routes to
> P2's first slice (rollouts + expert iteration) next, and the finding names the 32B as
> the first candidate with evidence; § 7.3 closes only by a Type 1 amendment before the
> measurement it governs runs. The finding also discloses the material unverified rate
> (a timing property of the 32B's speed against the verification timeout — the P3 retry
> discipline is the named response) and the one field correction the run surfaced (the
> autopsy-stem alignment the comparison refused, landed test-first). Read
> `docs/planning/larger-base-arm/finding.md` and `reports/larger-base/` before quoting
> anything about it.
>
> **P2's first slice — rollouts and expert iteration — is done** (`docs/ROADMAP.md` § P2; plans at
> `docs/planning/p2-rollouts/{sampling,sft,night-door}/`). The project's namesake finally exists:
> `whetstone run --night` draws `K` seeded attempts per task under the hardened contract, keeps
> **only** the rollouts the STRICT verifier passed, LoRA-SFTs the base on those, and writes
> `runs/<id>/` (ledger, dataset, per-draw journals and transcripts) plus a hashed candidate under
> `checkpoints/<id>/`. All four P2 exit criteria are asserted as tests rather than described: the
> door produces both directories, **every** training example carries a recorded strict-PASS
> verdict, two nights at one seed produce a byte-identical training set, and the ledger records the
> pinned seeds, model revision, task set and tool versions.
>
> **The new package is `src/whetstone/loop/`, partitioned EXEMPT on the `bakeoff` precedent, and it
> composes rather than re-decides.** `freeze`/`Sealed`/`Recording`/`Retry`, `control.probe`,
> `harness_status`, `sweep.rankable`, `Journal`, `Transcript`, `load_weights` and — critically — the
> single definition of *solved* (`report.tally`'s `Outcome.SOLVED`, imported by identity) are all
> the bake-off's own. The one genuinely new seam is the sampled draw: `sampling.K = 8` is a
> **declared constant, never a flag** (raising it is the roadmap's named response to a low yield,
> as a diff before a night), the per-attempt seed is `sha256(run_seed, task_id, attempt)` — never
> the builtin `hash`, which is process-salted and would have made the determinism criterion a
> statement about `PYTHONHASHSEED`, asserted by a cross-process test — and `sampler_for(1)` returns
> `mlx_runtime.greedy_sampler` **by identity**, so a single-draw night and the bake-off are one
> experiment. `Draw` wraps outermost so a retry re-asks *within* a draw and consumes no new seed;
> one journal and one transcript live **per draw index**, because both are keyed `(candidate, task)`
> and `K` draws of one task would otherwise collapse to the last. The control arm runs **once per
> task** and is shared across the draws, and a resumed night reuses the recorded probe rather than
> taking a second one.
>
> **`cli.py` gains the one edge this repository has from a guarded root into an exempt package**, and
> it is argued rather than excused: `run --night` holds a single **function-local** import of
> `whetstone.loop.night` inside its handler, so `whetstone verify` never executes it and never
> imports `mlx_lm` even transitively. `tests/test_reward_path_scope_is_partitioned.py` asserts it is
> the only such edge **and** that it is function-local, both watched failing against planted
> imports; a second one, or the same one at module scope, fails the build.
>
> **The refusals are the part worth reading.** `UNVERIFIED` is not training data and neither is
> anything else: the trainable partition is enumerated against `Outcome` and asserted complete, an
> example must carry `SOLVED` *and* a recorded strict `PASS`, and a win from a run whose control arm
> proved nothing is refused by name. A zero-strict-PASS night is a **published outcome** — it writes
> no checkpoint, states the empty result in its ledger, and exits non-zero — because an adapter
> trained on nothing is indistinguishable, to P3's gate, from one that learned something. The
> LoRA capacity probe is D7-style and declared before it ran (a named step count, a stated headroom
> against 36 GiB, with gradient checkpointing and accumulation **pre-committed on** so a failing
> probe has nothing left to try); exceeding it is a capacity finding, not a constant to edit. The
> valid split below its declared floor is *no valid split*, stated verbatim in the checkpoint's
> provenance. The checkpoint is hashed weights-style with a `verify_checkpoint` re-hash, so P3 can
> re-verify the bytes it compares.
>
> **Nothing is published by this unit and `reports/` gains no directory.** A night's counts live in
> its own gitignored `runs/<id>/`, which is their only home; the ledger and the dataset document
> carry hashes and verdicts and never contents (canaries plant donor source text and assert it
> cannot reach either), and both documented homes are asserted gitignored. **No `PREREGISTRATION.md`
> § 10 amendment was made, deliberately**: § 10 discloses published *series*, and this unit publishes
> none. The loop's generation contract does differ from every published one in its `sampler` field
> (categorical, seeded, versus greedy) — that difference is recorded in every run ledger, and the
> amendment belongs to whichever later unit first publishes a figure measured under it.
>
> **The night itself has not been run.** The machinery is shipped and the operator's sheet is
> written (`docs/planning/p2-rollouts/night-door/runbook.md`, held by
> `tests/test_night_runbook_guards.py`: flags pinned to the shipped parser, writable paths absolute,
> exactly one worktree, the five declared dev ids, the retained/excluded candidate resolution, and
> the zero-yield rule stated as a result rather than a halt — watched failing against a deliberately
> wrong stub sheet). The GPU pass is operator-executed, as every arm in this repository has been.
>
> **What is not built.** The nightly loop has never been *run*, so no training set, checkpoint or
> yield figure exists yet. P3 and P4 are untouched: no promotion gate, no held-out split, no nightly
> report, no dashboard. The bake-off is base *selection*, not the pinned baseline of
> `PREREGISTRATION.md` § 3 — that is scored on the held-out split, which does not exist until P3,
> so "measured once, re-measured never" is unspent. Cheat 6 and cheat 10 remain documented
> residuals; ingestion narrowed cheat 10 with a `conftest.py` floor but did **not** close it. The
> cuts so far are v0.3.0–v0.6.0, the last tagged 2026-08-14; nothing has been published to PyPI.
>
> Keep this file, `VISION.md`, and `docs/ROADMAP.md` in sync as direction firms up. Describe the
> state of the tree this file ships in, and never work in flight on a branch — a status that
> names in-progress work is stale the moment that work merges, which has already happened once
> here. A capability is written up in the same commit that lands it, so the claim and the code
> arrive together and neither can outlive the other.

---

## What this project is

**Whetstone** is a system that lets a model **train itself overnight — and proves it didn't
cheat.** Point it at your tasks; each night a local loop runs self-play / RL against an
**unhackable, execution-grounded verifier** (never an LLM judge it can fool), distills the
wins into a small local model, and produces a signed morning report: *"+X% on your real
tasks, zero reward-hacking, here's the proof."* You wake up to a measurably better
**private** model.

**The name.** A *whetstone* sharpens a blade through patient, repeated honing. Whetstone
sharpens a model the same way — a little better each night, against a hard, honest edge.

---

## The wedge (read this before proposing any feature)

The frontier is **RLVR — reinforcement learning from *verifiable* rewards**. Its open wound
is **reward-hacking**: a policy learns to game a soft/LLM-judge reward instead of getting
genuinely better. Whetstone's entire reason to exist is that **the reward is deterministic
re-execution**, so the policy *cannot* game a judge — the classic RLVR failure mode is
designed out.

- **We do NOT build a frontier base model.** We take an open base and make it better on the
  user's tasks, locally.
- **We do NOT reward with an LLM judge.** The reward is execution-grounded (observed-vs-
  claimed state / checkable end-state). If a task drifts toward "let a model grade the
  model," stop and flag it.
- The company/reputation is the **verified self-improvement loop**: the unhackable reward,
  the never-regress promotion gate, and the honest number.

---

## Key strategic constraints (do not violate)

1. **The reward must be verifiable, never a judge.** Execution-grounded, deterministic. This
   is the moat and the reason reward-hacking can't win here.
2. **Never regress.** A new checkpoint ships only when it *provably* beats the last on a
   held-out **verified** set. `UNVERIFIED` never counts as a win (borrow the sibling
   projects' honesty contract: UNVERIFIED is never rendered as PASS).
3. **Local / BYOK / private.** The user's data and the training stay on their machine. A
   cloud teacher model may be used via BYOK for distillation, but the loop and data are
   local by default.
4. **Build the part that gets BETTER as base models improve.** A stronger open base = a
   better starting policy and cleaner distillation; the durable moat is the verifier + the
   loop + the accumulated verified-improvement data, never the base weights.
5. **Ship the honest number even if gains are modest.** Scope to ONE task family where the
   verifier is airtight first; publish the harness and the real delta (including a
   "reward-hacking attempts caught & rejected: N" count), never a hyped one.
6. **No lab required.** RL loop + verifier + distillation + eval is all engineering — the
   founder's edge. No proprietary datasets or credentials.

---

## The core loop (the product surface)

1. **A verifiable task family + verifier** — the reward signal; deterministic, hard to game.
2. **Nightly improvement loop** — self-play / RL / self-distillation against that verifier.
3. **Never-regress promotion gate** — promote a checkpoint only on a proven, verified gain.
4. **Signed morning report** — the verified delta, what changed, and the hack-attempts caught.
5. **Local + private** — runs on the user's machine; the model never leaves.

---

## Relationship to the sibling project

The sibling project is the execution-grounded **verification engine**. Whetstone is the
**improvement loop that trains against a verifier like its**. They reinforce each other: the
sibling project proves a run is correct; Whetstone uses that kind of proof as an unhackable
reward.
`docs/ROADMAP.md` § 7 records exactly what we take and what we decline. **Taken:** the verdict
semantics (`UNVERIFIED` ranked above `PASS`), the provenance boundary, the corpus metrics, the
AST guard that keeps inference libraries off the reward path, the **Seatbelt sandbox approach**
(the profile shape and its SBPL escaping — we wrote our own minimal deny-all profile rather than
vendoring the 417-line module), and the eval instances/scripts.
**Declined: the replay substrate** — for four stated reasons: it answers a harder question than
our reward needs (trace fidelity vs. does the end state pass an operator-held check), its
throughput is built for auditing rather than generating rollouts, parallel calls deliberately
yield `UNVERIFIED` so batched rollouts produce no signal, and it exposes no API surface. Revisit
only if a later task family needs trace fidelity. Whetstone is an independent project with its
own thesis (improvement), not a feature of the sibling project.

---

## Tech direction

**Locked — decided in the planning artifacts; do not re-litigate.**

- **Core: Python**, package path `src/whetstone/`, tests in `tests/`. RL/self-play loop, the
  verifier harness, distillation, and eval all live here.
- **Toolchain: uv exclusively** (no pip, no poetry) + ruff + mypy + pytest. CLI entrypoint
  `whetstone`.
- **Local runtime: MLX / `mlx-lm`**, end-to-end — both rollouts and LoRA — on macOS / Apple
  Silicon (`docs/planning/roadmap-and-task-family/prd.md:63` for the runtime, `:58` for the
  platform). *Not* Ollama, vLLM, or transformers; an earlier draft of this file said those,
  and that was superseded by the PRD.
- **Reward:** execution-grounded verifier for one task family first (code / tool-use with a
  checkable end-state). No LLM-judge reward, ever.
- **License:** Apache-2.0 (`docs/ROADMAP.md` § 4 makes it a P0 exit criterion).
- **Distribution:** OSS, self-hostable, local-first / BYOK. 0.x versioning, tag `vX.Y.Z`, and
  **tag-push is the entire release mechanism**. PyPI distribution name **`whetstonehq`** (bare
  `whetstone` is taken); the import package and the CLI stay `whetstone`. See `RELEASING.md`.
- **Dashboard:** TypeScript / Next.js (founder's stack), as a subdirectory of this repo — the
  nightly report, the verified-gain trend, the caught-hack log. **Post-horizon**, not near-term.

**Still open — genuinely undecided, decide with evidence.**

- **Which open base** we fine-tune / LoRA — **still open, and now open on evidence.** The P1
  bake-off ran against the *working* verifier rather than on paper, and no candidate gave any
  evidence to choose on, so nothing was selected and `PREREGISTRATION.md` § 7.3 stays open.
  Re-opening it means an easier task stratum or a larger base, never a looser verifier.
- **The BYOK cloud teacher for distillation** — optional, and post-horizon; nothing inside the
  current roadmap horizon calls a cloud model at all.
- Everything `docs/ROADMAP.md` § 10 lists as an open question.

`docs/ROADMAP.md` is authoritative on the technical plan today.
`docs/technical/ARCHITECTURE.md` (to be written) supersedes it once it exists.

---

## Founder profile

Solo / small-team. **Full-stack developer + ML engineer.** The moat is engineering — the RL
loop, the unhackable verifier, distillation, and the evaluation machinery — which is exactly
the founder's edge. No dependency on proprietary data, credentials, or a frontier lab.

---

## Quick facts for grounding (do not fabricate beyond these)

- **RLVR (RL from verifiable rewards)** is the live frontier for making models better at
  tasks with checkable outcomes; **reward-hacking** is its central, documented failure mode
  (e.g. METR observed a model rewriting a timer instead of optimizing the task).
- **LLM-as-judge rewards are foolable:** "One Token to Fool LLM-as-a-Judge" shows up to
  **35% false positives** — a judge reward is gameable; an execution-grounded reward is not.
- **The verifiable-environment substrate is a named gap:** Karpathy (Sequoia Ascent 2026) —
  the valuable RL environments "aren't in the frontier-lab mix."
- Seed research + rationale for this project: `~/dev/at/ideas/research/b1-verified-self-improvement.md`.

If you need a statistic that isn't here, do not invent one; say it's unverified.

---

## Non-goals / guardrails (restated so the project doesn't drift)

- **No frontier base-model training** — we improve an open base on the user's tasks.
- **No LLM-judge reward** — the reward must be execution-grounded/verifiable.
- **No regressions shipped** — promote only on a proven verified gain; UNVERIFIED ≠ win.
- **No data egress** — the loop and the user's data stay local by default.
- **No hype** — publish the honest delta and the caught hack-attempts, even when modest.
- **Gets better as base models improve** — reject designs a better base would make redundant.

---

## Docs structure

```
README.md                       # Repo front door
VISION.md                       # Narrative thesis, moat, non-goals
CLAUDE.md                       # This file
CONTRIBUTING.md                 # Dev setup, test-first contract, ground rules
PREREGISTRATION.md              # What P4 may claim, fixed before any number existed
RELEASING.md                    # Tag-push release mechanism (nothing released yet)
reports/baseline/               # The P1 bake-off — the only home of the baseline's figures
reports/format-hardening/       # The hardened arm's report — non-comparable, by the D6 argument
reports/easier-stratum/         # The probe's home — non-comparable, changed task set (§ 10.5)
reports/larger-base/            # The arm's home — non-comparable, new candidate (§ 10.6)
.claude/skills/                 # The repo's own workflow skills (see below)
docs/
  ROADMAP.md                    # 2–3 month phased plan + milestones — authoritative today
  planning/                     # Per-unit PRDs, specs, implementation plans
  technical/ARCHITECTURE.md     # The nightly loop / verifier / distillation design (to write)
  product/PRODUCT_SPEC.md       # Product surface, the report, the trend (to write)
```

`docs/technical/ARCHITECTURE.md` and `docs/product/PRODUCT_SPEC.md` do **not** exist yet. Until
`ARCHITECTURE.md` does, read `docs/ROADMAP.md` for the technical plan — do not assume the
architecture doc's absence means the design is undecided.

---

## Workflow skills (`.claude/skills/`)

The repo carries its own skills, mirroring the author's sibling projects. Use them rather than
improvising a workflow.

| Skill | Alias | What it does |
|---|---|---|
| `whetstone-next` | `wn` | Picks the next capability from the repo's own files; recommends and hands off, never starts the work |
| `whetstone-begin-fast` | `wbf` | Worktree → context → dig → PRD → plan → implement (TDD, agents team) |
| `whetstone-begin` | `wb` | Same, plus diagrams and technical/non-technical proposal PDFs before planning |
| `whetstone-end-fast` | `wef` | Post-merge cleanup: master → pull → remove worktree → delete branch |
| `whetstone-end` | `we` | Same, plus a completion note on Desktop |
| `whetstone-report` | — | The plain-English completion note |
| `whetstone-worktrees` | — | Branch naming, worktree layout, per-worktree setup, cleanup |
| `prd-interview` / `prd-generator` / `tech-plan` | — | The planning chain the begin skills call into |

Conventions the skills assume: base branch **`master`** (never `main`), branch
`<type>/<id>/aliz`, worktree `.claude/worktrees/<type>-<id>`, planning artifacts under
`docs/planning/{slug}/`, and **strict TDD executed through the agents team**.

Every skill enforces the guardrails above — in particular that the reward stays
execution-grounded, that `UNVERIFIED` is never reported as a win, and that no number
appears anywhere the verifier didn't produce it.
