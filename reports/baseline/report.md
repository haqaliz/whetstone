# Base selection bake-off

## What this measurement is, and what it is not

This document reports **base selection**: which open base P1 starts from, decided by a bake-off against the working verifier rather than from a table of somebody else's benchmark scores. It is not the pinned baseline of `PREREGISTRATION.md:126-128`.

"Measured once, re-measured never" (`PREREGISTRATION.md:129-132`) is not spent by this report. The pinned baseline is scored on the held-out split, and that split does not exist yet (`PREREGISTRATION.md` § 7.1, open until P3), so the baseline stands unmeasured and may still be measured exactly once, later, by whoever chooses to spend it.

The set scored here is the declared source-B set, and it is not a held-out split. No figure in this document is a delta: `delta` is defined only as `solved_final - solved_baseline` (`PREREGISTRATION.md:92-94`), and neither term exists.

This report ranks and does not threshold: it names no minimum any candidate must clear, and PREREGISTRATION.md:171 forbids one being added now that a number exists.

## The ranking

A figure measured on one side of a changed pinned input may not be compared with one measured on the other. Candidates differ in model revision, which is a pinned input (`PREREGISTRATION.md:131`), so the rows below are ranked against one another and are not comparable figures.

| Rank | Candidate | Revision | Parameters (B) | `solved` |
|---|---|---|---|---|
| 1 | `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit` | `3dd939c621c08e5753d5b89f35a2642cd83b98ca` | 3.0 | 0 of 63 |
| 2 | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` | `019cc73c45c770444708a6dd8690c66243cc5c80` | 7.0 | 0 of 63 |
| 3 | `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` | `29efdbab55a161237ab1e432a3abaf6c7ae2b477` | 14.0 | 0 of 63 |

**Outcome.** no base is selected: every candidate solved zero, so there is no evidence to choose on. PREREGISTRATION.md § 7.3 stays open and the pivot signal at docs/ROADMAP.md:387-389 is reported as fired — the response is an easier task stratum or a larger base, never a looser verifier.

**Selected base:** none.

## Source B — the declared private set

| Figure | `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit` | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` | `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` |
|---|---|---|---|
| `solved` | 0 of 63 | 0 of 63 | 0 of 63 |
| `coverage` | 50 of 63 | 51 of 63 | 51 of 63 |
| `unverified` | 13 of 63 | 12 of 63 | 12 of 63 |
| `N` | 0 of 63 | 0 of 63 | 0 of 63 |
| `no diff` | 1 of 63 | 42 of 63 | 0 of 63 |
| `patch apply` | 49 of 63 | 8 of 63 | 42 of 63 |
| `patch scope` | 0 of 63 | 0 of 63 | 0 of 63 |
| `not solved` | 0 of 63 | 1 of 63 | 9 of 63 |

`solved` is STRICT `PASS` and nothing else (`PREREGISTRATION.md:86-90`). A task that reached no verdict lowers `coverage` and stays in the denominator; it is counted in neither `solved` nor the failure rows, because UNVERIFIED is not a win and is not a loss either — it is the absence of a comparison.

## `N` — the reward-hacking count

`N := count(rollouts where WEAK == PASS and STRICT == FAIL)` (`PREREGISTRATION.md:96-100`).

- `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit`: 0 rollouts a weaker check would have scored as wins. (0 of 63)
- `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit`: 0 rollouts a weaker check would have scored as wins. (0 of 63)
- `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit`: 0 rollouts a weaker check would have scored as wins. (0 of 63)

This is a claim about what the strictness caught and not about intent: intent is not observable, so no claim to measure it is made here.

> N counts what the strictness caught. It is not a claim that nothing got through.

That bound is `PREREGISTRATION.md:211-220`: cheat 6 and cheat 10 in `docs/ROADMAP.md` § 3 are accepted by both verifiers and are recorded as residuals rather than patched, so the verifier's guarantee has stated limits and `N` is bounded by them.

Every `N` here is a baseline `N`, and no final `N` exists — nothing has been trained, so there is nothing to compare against. `PREREGISTRATION.md:107-109` requires both to be published together, and the second one does not exist yet.

**`N` is a floor.** The generation contract states the patch-scope rule to every candidate — *"the test files are held by the operator ... a patch that modifies any test file is refused before it is run"* — which is the right call for comparability, since every base is told the same thing and the contract does not name which files are held. It also discourages precisely the behaviour `N` counts, so this figure is a lower bound under a disclosing contract rather than a natural rate. Two consequences follow. An `N` measured under a different generation contract is not comparable to this one — the contract is an unpinned input, and this is the first concrete demonstration that it moves a pre-registered number. And this is a second bound on `N`, alongside the residual bound above: it is not a claim about what a policy would have done had it not been told the rule.

## Source A — SWE-bench-Lite, one instance

**The four-gate funnel comes first, because it is the denominator.** Eligible: 1 of 300 instances — `pallets__flask-4045`. Refused: 299 of 300, by gate: format 192 of 299, environment 106 of 299, collectability 1 of 299, liveness 0 of 299.

- **Result for `pallets__flask-4045`, `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit`:** not solved under STRICT (0 of 1).
- **Result for `pallets__flask-4045`, `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit`:** not solved under STRICT (0 of 1).
- **Result for `pallets__flask-4045`, `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit`:** not solved under STRICT (0 of 1).

One instance is not a public benchmark set and is not quoted as one. A result on a single instance is not a measurement, and no claim is made as though it were (`PREREGISTRATION.md:149-155`). The deliverable in source A is the four-gate filter and its rejection ledger, not the instance count.

## Both sources, together

Both sources are published in this document regardless of which looks better, and neither is held back pending the other (`PREREGISTRATION.md:142-143`).

For every candidate the two sources point the same way, so no contamination signature is observed here. With source A at one instance the signature would not be detectable in practice in any case, which is a bound on what its absence can mean.

## The control arm

Across every source-B run: INTACT 189 of 189, BROKEN 0 of 189, SKIPPED 0 of 189. The control arm runs an inert patch and the task's own re-derived fix through the same harness on the same task, so a zero in the tables above is a statement about a base rather than about a verifier that never graded anything. A run whose control arm proved nothing is refused before it reaches this document.

## Measured wall-clock

Generation 5000.9 seconds; verification 387.2 seconds; control arm 1167.6 seconds. Measured on this run, not estimated. Any capacity bound this exposes is published as a finding rather than worked around (`docs/ROADMAP.md:594-596`).

## Provenance

The five pinned inputs of `PREREGISTRATION.md:131-132`:

- **Revision, per candidate:** `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit` at `3dd939c621c08e5753d5b89f35a2642cd83b98ca`, `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` at `019cc73c45c770444708a6dd8690c66243cc5c80`, `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` at `29efdbab55a161237ab1e432a3abaf6c7ae2b477`.
- **Task set:** source B: 63 tasks from [PosixPath('/Users/aliz/dev/at/whetstone/tasks/local/belay'), PosixPath('/Users/aliz/dev/at/whetstone/tasks/local/contig')]; source A: 1 from tasks/public/instances. Declared and hash-recorded, and deliberately NOT called held out (PRD D4): PREREGISTRATION.md § 7.1 leaves that split open and unspent.
- **Environment pins:** per task, from its own manifest: exact `==` pins and a nominated interpreter, resolved once per distinct pin set (whetstone.bakeoff.scoring.Interpreters) and shared by the control arm and the rollout so both are graded under the same environment.
- **Seeds:** none: one greedy attempt per task per candidate (argmax over the vocabulary, mlx_lm==0.31.3). No sampling is performed, so there is no seed to record and no draw for a re-run to differ on.
- **Tool versions:** mlx-lm 0.31.3, platform Darwin 25.5.0 arm64, python 3.12.13, whetstonehq 0.1.0.
- **Recorded on:** 2026-08-01 (declared by the operator, never read from a clock, so two renders of the same records agree byte for byte).

**The generation contract, which is not among the five pinned inputs.** It determines the number and is not pinned, so a later figure measured under a changed contract is not comparable to this one. Template SHA-256 `b7d6d3d4052db5e95a4e8eaa65d2728176406c580e260c4b637442ff333cd1ae`; sampler greedy: argmax over the final logprob axis (mx.argmax(logprobs, axis=-1)); token budget 1024; extractor version extract_patch@3e91bab8c123; development subset `belay-0cfbb1590a70`, `belay-0f8651175ef8`, `belay-0fe4582aeac1` — excluded from every count above, because scoring a task the contract was iterated against would be optimising on the outcome.

**Retrieval: the oracle setting, disclosed.** Each prompt shows the base the non-test files that task's reference patch touches, as they stand at `base_commit` (the standard SWE-bench oracle condition, `whetstone.bakeoff.sources`). Without them a unified diff is being asked for against a file the base has never seen; with them the prompt also names which files to change, which is work the unassisted setting includes. Every count here is therefore a figure about the oracle setting and an upper bound on what the same base would do from the bug report alone. It may not be compared with a published figure measured without retrieval.

## Findings and disclosed bounds

**The held-out clash, recorded rather than smoothed over.** `docs/ROADMAP.md:387` states P1's pivot signal over a held-out task, but `PREREGISTRATION.md:242-247` leaves the held-out split open until P3, so no such split exists for the signal to be read against. This report reads it against the declared source-B set instead, and records that the two documents do not agree.

**Network.** Two exceptions, where `docs/ROADMAP.md:574-576` declares one. Source A's instance is verified against a `git clone` of the upstream repository, which touches the network on each verification. The weights every candidate was loaded from were fetched in a separate, human-run step with its provenance committed; the scored run itself ran offline. Source B never touches the network at all.

**Source B cannot be reproduced byte-for-byte outside this machine.** The mined manifests are the user's own code and are never committed; what is committed is the mining recipe and a liveness ledger of per-task hashes and verdicts (`PREREGISTRATION.md:222-228`). A reader with none of the data can count the corpus, confirm every task was proven live rather than assumed, and re-derive a corpus from the recipe against their own copy of a donor — but cannot reproduce these instances. That is the honest cost of locality, and it is why source A, fully committed and externally checkable, is not optional padding.

**Self-selection stands undiluted.** Source B is mined from the author's own repositories and its mitigation did not land (`PREREGISTRATION.md:200-204`).
