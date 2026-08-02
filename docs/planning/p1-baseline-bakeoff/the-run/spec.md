# Aspect spec — `the-run`

**Parent PRD:** `docs/planning/p1-baseline-bakeoff/prd.md` (D1, D5, D7, M7b, S1, § 7).
**Sequence:** fourth. The only aspect that executes a model; the only one whose output is evidence.

## Problem slice

Everything before this is machinery. This aspect is the measurement: provision three candidate
bases, freeze the generation contract, measure the cost before committing to the full matrix, run
it, and commit `reports/baseline/` — closing P1's last exit criterion and
`PREREGISTRATION.md` § 7.3.

It is also the aspect where the project's honesty rules stop being abstract, because this is where a
disappointing number would first tempt someone to change something and re-run.

## In scope

1. **Weight provisioning** (S1) — a human-run, documented step fetching the three candidates to
   local directories, with `revision` pinned (`mlx-community` repos are mutable). MEASURED sizes:
   Qwen2.5-Coder 3B / 7B / 14B at 4-bit = 1.62 / 3.99 / 7.74 GiB, 13.4 GiB total. Provenance
   (repo id, revision, byte size, checksum) is committed; the weights are not.
2. **The declared second network exception** — `docs/ROADMAP.md:574-576` declares exactly one today.
   The weight fetch is a second: human-run, output provenance committed, and the **scored run pinned
   to local directories under `HF_HUB_OFFLINE=1`** (VERIFIED: a local path loads with zero network;
   a repo id raises `LocalEntryNotFoundError` offline).
3. **The dev subset** (M7b) — a small, declared set of task ids, permanently excluded from every
   published count, against which the prompt and extractor are developed.
4. **Freezing the generation contract** — hash recorded before the scored run starts.
5. **The probe** (D7) — time a declared sample end-to-end, publish the measured per-task cost, and
   let that number decide the full scope. Any reduction is a recorded finding with its arithmetic.
6. **The scored run** — 3 candidates × the declared source-B set + `pallets__flask-4045`, one greedy
   attempt each, both verifiers, control arm included.
7. **Committing `reports/baseline/`**, strictly after `PREREGISTRATION.md`'s commit (`f317b89`).

## Out of scope

- Any training, LoRA, checkpoint, or promotion decision — all of P2/P3.
- Defining a held-out split — § 7.1 stays open and unspent.
- The document corrections — aspect 5, though they land in the same commit as the report.

## Acceptance criteria

These are **operational** as well as testable; this aspect's output is evidence, not only code.

**AC1 — the scored run touches no network for generation.**
Executed with `HF_HUB_OFFLINE=1` and local model paths. A test asserts the MLX adapter is
constructed with a filesystem path, never a bare repo id.

**AC2 — the generation contract is frozen before the first scored result.** *(the honesty control)*
The recorded contract hash is identical across every scored result in the run. If the prompt or
extractor changes afterwards, the run is **invalidated and restarted** — the discipline
`PREREGISTRATION.md:133-135` applies to pinned inputs, applied here to the input that is not yet
pinned. The report records the hash and the dev-subset ids.

**AC3 — the dev subset is excluded from every published count**, and its ids are named in the
report so the exclusion is auditable rather than merely asserted.

**AC4 — the control arm passed in the same run.** `FAIL` reachable via the inert patch and `PASS`
reachable via a reference patch, on the same task set with the same provisioning. If not, the run
publishes `UNVERIFIED` and no ranking.

**AC5 — the probe's numbers are published, including if they force a scope change.**
The measured per-task cost appears in the report. If scope is reduced, exactly what was dropped and
why is recorded — never a silent truncation.

**AC6 — the report's commit post-dates `PREREGISTRATION.md`'s.**
Verified with `git log --date=iso --diff-filter=A --name-only -- 'reports/**'`
(`PREREGISTRATION.md:288`).

**AC7 — the result is published whatever it is.** *(the one that matters)*
Including all-zero, in which case no base is selected, § 7.3 stays open, and P1's pivot signal is
reported as fired (`docs/ROADMAP.md:387-389`). `PREREGISTRATION.md:159-161` requires a zero result
to be published as plainly as a positive one, and `:181-184` says publication is not gated on the
result.

**AC8 — capacity is answered.** Peak memory and wall-clock per candidate recorded, closing
`docs/ROADMAP.md:594-596`. If capacity bounds the candidate or task set, that bound is published as
a finding.

## Dependencies & sequencing

- Depends on aspects 1–3, all of which are testable without `mlx` and without weights.
- Runs on macOS / Apple Silicon only (`sandbox.py:66`); MEASURED: M4 Max, 36 GB, 28.08 GiB
  recommended GPU working set, ~328 GiB free disk.
- The corpus is read from the primary checkout by path; nothing is copied into the worktree.
- ESTIMATE, generation only, 66 tasks × 3 candidates at one attempt: ~59 min, from measured per-unit
  timings on random-weight reconstructions — valid for speed, silent about quality. **The verifier
  half is unmeasured**; the probe exists precisely because that estimate does not.

## Open questions / risks

- **The strongest temptation in the whole slice** is to treat a disappointing number as evidence the
  prompt is wrong. AC2 is the rule that makes the two cases distinguishable after the fact; it only
  works if it is written before the number exists, which is why it is here and not in a retrospective.
- **14B-8bit is excluded by measurement**, not by preference: MEASURED 30.56 GiB peak exceeds the
  28.08 GiB recommended working set. Recorded so the exclusion is not mistaken for an oversight.
- **Source-A verification clones from GitHub per run** (`repo.py:66-84`, no cache), so the scored run
  is *not* fully offline. Disclosed in the report rather than glossed.
- An interrupted overnight run must resume rather than restart (aspect 2, S2); without it, a single
  failure costs the whole measurement.
