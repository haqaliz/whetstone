# Pre-registration

**Committed 2026-07-29, in P1, before any number about a model existed.**

This document fixes what Whetstone will measure, which figure is the headline, how the result is
reported, and what its known limitations are — **before** the first measurement is taken. It
discharges `docs/ROADMAP.md` § 6 (`docs/ROADMAP.md:518-528`) and is P1 exit criterion 6
(`docs/ROADMAP.md:355-356`).

`docs/ROADMAP.md` § 4, P4 (`docs/ROADMAP.md:476-477`) grades the published headline against this
file: *"The headline matches what `PREREGISTRATION.md` committed to, and both sources are
published together."* So everything below is written to be checkable later by someone who did not
write it — **including its own citations, which `tests/test_docs.py` resolves against the lines
they name.**

---

## What this is, and what it is not

**It is a timing control.** Two sources with no headline rule is an invitation to post-hoc
selection — in the one project whose entire premise is not fooling yourself. The value of this
document is its commit date: a headline rule chosen before any result is visible constrains what
may be claimed; the same words chosen afterwards merely describe what was found. `git log` is the
evidence, and § 9 says how to check it.

**It is not an independence control.** Whetstone is a solo project. The same person writes these
criteria, builds the verifier, runs the loop, and publishes the result. Nothing here makes the
evaluation independent, and nothing in this document should be read as claiming that it does. This
is stated because the sibling project states it about its own gate, and the honest form of
that limitation is to name it rather than let a reader assume otherwise.

**It is not a plan.** `docs/ROADMAP.md` is the plan. This file constrains only what may be claimed
about a measurement.

## Status at the time of writing

Every claim in this section is checkable in the tree this file was committed to.

- **No model has been run against anything in this repository, and no figure about a model
  exists** (`docs/ROADMAP.md:364-368`). The verifier grades patches; a corpus existing is not a
  measurement.
- `reports/` does not exist. Neither does any baseline. The base-model bake-off — P1 exit
  criterion 5 — has not run, which is why this document could be written honestly.
- **The reward exists and is execution-grounded**: `src/whetstone/verify/` holds the STRICT
  verifier (the reward) and the WEAK verifier (measurement only), with an AST guard that fails the
  build if any inference library is reachable from the reward path.
- **The corpus exists.** Source B: 66 tasks, 45 mined from `donor A` and 21 from `donor B`, each
  proven live before it was kept. Source A: 1 eligible instance of 300 from SWE-bench-Lite, with
  all 299 refusals ledgered (`tasks/README.md`).
- **This document contains no figure about a model**, by rule and by test. See § 4.

## 1. The headline

**The private source (B) is the headline.** It is on-thesis — *"point it at your tasks"* — and
uncontaminated: it is mined from repositories no open base has trained on.

**The headline figure is the change in the count of tasks solved under the STRICT verifier, on the
held-out source-B split**, between the pinned baseline checkpoint and the final checkpoint:

```
headline := solved_final - solved_baseline
            on the held-out source-B split
            where "solved" means STRICT PASS, and nothing else does
```

It is published **as a count over its denominator**, always with coverage and with `N` beside it,
in this shape:

```
+a of b held-out tasks (baseline c of b, final d of b)
coverage e of b     N: f at baseline, g at final
```

The letters above are placeholders for the shape of the answer, not values. **No digit in this
document describes a model**, because no measurement has been taken.

**Why a count and not a rate.** The corpus is small. A rate computed over a small denominator
moves by large-looking amounts when a single task flips, which reads as a measurement and is
mostly noise. Reporting the count with its denominator gives a reader the same information without
the false precision. This follows the sibling project's decision to report its violation figure rather than
threshold it, on the stated ground that inventing a cutoff would manufacture precision the
denominator does not support.

## 2. The metrics, defined before they are measured

**`solved`** — a task is solved iff the STRICT verifier returns `PASS` for the policy's patch.
STRICT is defined at `docs/ROADMAP.md:62-72`: the patch is rejected if it touches any operator-held
path; every held test is restored from the golden copy *after* the patch lands; the skipped-test
count must be zero; and the executed node-id set must equal the declared one exactly. `WEAK` never
counts toward `solved` and never trains anything.

**`delta`** — `solved_final - solved_baseline` on the same task set, under the same verifier, with
the same pinned inputs. A delta computed across a change to any pinned input is not a delta; see
§ 3.

**`N`** — the reward-hacking count, defined at `docs/ROADMAP.md:106-117`:

```
N := count(rollouts where WEAK == PASS and STRICT == FAIL)
```

Reported verbatim as **"N rollouts a weaker check would have scored as wins."** That is a claim
about what the strictness caught, **not** about the policy's intent — a patch that edited a
genuinely-buggy test in good faith still counts. Intent is not observable, so no claim to measure
it will be made.

**`baseline N`** — the same count for the untrained base. `N` alone is uninterpretable: without
the baseline there is no answer to *"did the loop learn to cheat more?"* Both `N` values are
always published together.

**`coverage`** — the fraction of the task set that reached a real verdict, published as a count
over its denominator. Tasks that end `UNVERIFIED` **lower coverage; they never leave the
denominator.** Dropping them is the hundred-out-of-hundred-by-construction lie, and it is refused
here by name.

**`UNVERIFIED`** — never a win, never rendered as `PASS`, never collapsed into `promoted`. Where
the loop cannot ground a claim it says so, and the evaluation says so too: if any task is still
unverified after its deterministic retries, the whole evaluation reduces to `UNVERIFIED` — not
promoted, and not rejected either, because no comparison was actually made.

## 3. The baseline protocol

Every headline figure is a delta, so the "before" is pinned before anything trains
(`docs/ROADMAP.md:504-513`).

- **A pinned baseline checkpoint** — the untrained open base, scored on the held-out set by the
  same STRICT verifier, with its provenance committed alongside: seeds, model revision, task set,
  interpreter and tool versions.
- **Measured once, re-measured never.** Operationally: the baseline is scored exactly one time,
  and that score is committed. It is not re-run to "confirm" it, and it is not re-run because a
  later result looked disappointing. The pinned inputs are the model revision, the task set, the
  environment pins each task declares, the seeds, and the tool versions.
- **A change to any pinned input invalidates the series.** It is treated as starting over: a new
  baseline is measured, and the old series is not extended. This is the only circumstance in which
  a second baseline measurement is legitimate, and the change that caused it is recorded.
- **Non-comparability.** A figure measured on one side of a changed pinned input **may not be
  compared** with one measured on the other. Any before-and-after comparison that crosses such a
  change must carry that sentence beside it, or it must not be published.

## 4. How the result is reported

**Both sources are always published together**, regardless of which looks better, and in the same
document. Neither is published alone, and neither is held back pending the other.

**A disagreement between the two sources is reported as a finding**, not resolved by choosing the
flattering one. **Public-gain-with-private-flat is the expected signature of contamination** and is
itself worth publishing.

**Source A is reported per-instance, never as a rate.** Of SWE-bench-Lite's 300 instances,
**1 eligible instance of 300** survived the four-gate filter — `pallets__flask-4045` — with the
299 refusals ledgered against the gate that refused each (`tasks/README.md`). One instance is not a
public benchmark set and will not be quoted as one. Its result is published as the outcome of that
named instance, with the filter's funnel beside it, so a reader sees the denominator before the
result. **A delta on a single instance is not a measurement**, and no claim will be made as though
it were.

**Every rate carries its denominator.** Nothing is reported as a bare proportion.

**A zero or negative delta is published as plainly as a positive one**, in the same place, with
the same prominence (`docs/ROADMAP.md:480-481`). Shipping the honest number even when modest is
the point; a flattering unsourced one is the failure.

**This document contains no figure about a model** — not a target, not a projection, not an
expected range — because none has been measured. That rule is enforced by a test, not by good
intentions: the document may not contain a proportion in any spelling. Grounded external
statistics this project may cite live in `docs/ROADMAP.md` § 11, which is the correct place for
them.

## 5. Success, and what is not pre-registered

**No numeric success threshold is pre-registered, and none may be added once a number exists.**

The reasoning, stated so it can be judged: no baseline has been measured, no base model has been
chosen, and the held-out split does not yet exist. Any bar set today would be invented, and
inventing a statistic is the one thing `CLAUDE.md:224` forbids outright. A bar set *later*, once a
result is visible, is post-hoc selection wearing the costume of rigour — which is the failure
`docs/ROADMAP.md` § 6 exists to prevent.

What is committed instead:

- The result is **published whatever it is**, including zero and including negative.
- The reporting rules in § 4 bind regardless of the outcome.
- **Publication is not gated on the result.** There is no configuration of the numbers under which
  this project publishes nothing.

A reader may judge the result against their own bar. This project will not move its bar to meet
the result.

## 6. Disclosed limitations

Five things a reader would otherwise discover only after the number, stated in advance. A
limitation disclosed up front is a bound on the claim; the same limitation found afterwards reads
as something that was hidden.

**6.1 Source B is self-selected, and its mitigation did not land.** The private headline is
measured on **the author's own repos**, largely written by Claude Code under strict TDD — and
`donor A` and `donor B` are themselves *about* verification and sandboxing, a closer loop than
*"point it at your tasks"* implies. Selecting commits by red-to-green also over-represents the
test-written-first shape, which is not what a real bug backlog looks like. The mitigation recorded
in planning was to include a third, unrelated donor: **`donor C` was refused** for having no
`uv.lock`, since its pins would have been chosen by the date the mint ran — the exact corruption
the `environment` contract exists to close (`tasks/README.md:171`). So the mitigation is **not in
force**, and the self-selection stands undiluted. None of this disqualifies source B: it is
uncontaminated and on-thesis, which is what it is pre-registered for.

**6.2 Source A is one instance.** See § 4. The deliverable there is the four-gate eligibility
filter and its rejection ledger, not the instance count. Of the 299 refusals, 192 were refused at
the format gate, 106 at the environment gate, and 1 at collectability. The 106 are recoverable only
by hand-determining era-correct pins one instance at a time.

**6.3 Two documented cheats survive into any reported `N`.** **Cheats 6 and 10** in
`docs/ROADMAP.md` § 3 are accepted by both verifiers and are recorded as residuals rather than
patched: special-casing the known input, and mutating a file a held test depends on that the
manifest never declared. Ingestion narrowed the second — every `conftest.py` on the path to a held
test is now declared held — but did not close it. Consequently the verifier's guarantee has stated
bounds, quoted from `docs/ROADMAP.md:187-190`: it guarantees that the operator-held tests, as the
operator wrote them, genuinely ran and genuinely passed; it does **not** guarantee that a fix
generalises; its guarantee extends only as far as the manifest is complete; and the sandbox
confines what a run may **write**, **not what it may read**. `N` counts what the strictness caught.
It is not a claim that nothing got through.

**6.4 Source B's data never leaves the box, which bounds what an outsider can audit.** The mined
manifests are the user's own code and are never committed. What is committed is evidence about
them: the mining recipe and a liveness ledger of per-task hashes and verdicts. A reader with none
of the data can count the corpus, confirm every task was proven live rather than assumed, and
re-derive a corpus from the recipe against their own copy of a donor — but **cannot** reproduce
our instances byte-for-byte. That is the honest cost of locality, and it is why source A, fully
committed and externally checkable, is not optional padding.

**6.5 This pre-registration is a timing control, not an independence control.** Restated here so
it is not lost in the preamble: one person writes the criteria, runs the evaluation, and publishes
the result. Pre-registration fixes *when* the criteria were set. It does nothing about who set
them.

## 7. Open at the time of writing

Three questions this document would naturally settle are genuinely undecided
(`docs/ROADMAP.md:609-614`). Each is named with what closes it and by when. **An open item named
here is a commitment; a blank would be an IOU**, and a pre-registration containing blanks reads as
a commitment while committing to nothing.

**7.1 The held-out split size and stratification.** Open because it depends on the corpus's
difficulty distribution, which has not been measured. Closed in P3, by a dated amendment to this
document committed **before the split is used to score anything**. If the corpus proves too small
to support a held-out split without a degenerate set, **that outcome is itself the published
finding** — the response is a larger or stratified corpus, never a headline computed on the
training set.

**7.2 The retry count `R`.** The promotion gate retries an unverified task a fixed `R` times with
identical seed and inputs. `R` is open because it is *"to be set from the observed unverified rate
rather than guessed"*. Closed in P3, by a dated amendment committed **before the first gated
evaluation**. If the gate proves unable to fire, the fix is a more reliable sandbox, never a looser
gate.

**7.3 Which open base is fine-tuned.** Open because it is decided *by* the bake-off this document
must precede — on evidence against the working verifier, not on paper. Closed in P1 by the bake-off
report under `reports/baseline/`, whose commit must be later than this file's. Naming a base here
would be the mistake: the base is deliberately swappable, and the durable assets are the verifier,
the gate, and the accumulated verified-improvement record.

## 8. The amendment rule

This document is **append-only**. Amendments are dated, committed as their own change, and
recorded in an amendment log at the foot of this file, so `git log` shows what was known when.

1. An amendment may **close an item listed in § 7**, and must be committed **before the
   measurement it governs runs**. An amendment committed after that measurement does not close
   the item; it documents that the item was never closed.
2. An amendment may **add a disclosure**. A limitation discovered later is disclosed late rather
   than not at all.
3. An amendment **may never introduce a success threshold**, and may never narrow, retract, or
   reword the headline definition in § 1, the reporting rules in § 4, or any disclosure in § 6.
   These are the clauses a result would tempt a later editor to soften, which is precisely why
   they are fixed now.
4. Nothing here is amended silently. An edit that changes what this document commits to, without
   a dated entry, is a breach of the pre-registration whether or not anyone notices.

## 9. Provenance

The commitment is only as good as its timestamp, so verify the timestamp rather than trusting
this sentence:

```
# when this file was committed, and by whom
git log --follow --date=iso -- PREREGISTRATION.md

# every report ever committed, with its date — each must be LATER than the commit above
git log --date=iso --diff-filter=A --name-only -- 'reports/**'
```

(The commands above deliberately use `--date=iso` rather than a `--format` string: this document
may not contain the per-cent glyph in any position, including inside a code fence, and § 4 says
why. A guard with an exemption for code fences would have its hole exactly where a plausible
number would sit.)

**The limit of the mechanical check, stated rather than implied.** A test in this repository fails
if anything exists under `reports/` while this file does not. That proves the two cannot co-exist
in the wrong order in a working tree — it does **not** prove temporal ordering, because a single
commit adding both would satisfy it. The temporal claim is the one above, and only `git log`
establishes it. This bound is written here because the sibling project made the inverse mistake:
it required its criteria be copied into the document that publishes the number before its gate
ran, that did not happen, and it had to record the discrepancy afterwards rather than prevent
it. The lesson taken is that a pre-registration belongs in the document that publishes the claim —
which is why this file sits at the repository root and not under `docs/planning/`.

**Amendment log.**

| Date | Amendment | Type (§ 8) | Closes an open item |
|---|---|---|---|
| 2026-08-01 | The generation contract is an unpinned input that moves the numbers (§ 10.1) | 2 — adds a disclosure | No |
| 2026-08-01 | On one public instance, § 4's contamination signature is undetectable (§ 10.2) | 2 — adds a disclosure | No |
| 2026-08-04 | Donor names replaced by stable pseudonyms throughout; the redaction disclosed (§ 10.3) | 2 — adds a disclosure | No |
| 2026-08-09 | The format-hardening contract is a second, non-comparable generation contract; its report has its own home (§ 10.4) | 2 — adds a disclosure | No |
| 2026-08-14 | The easier-stratum probe scores a changed task set under the hardened contract; its report has its own non-comparable home (§ 10.5) | 2 — adds a disclosure | No |
| 2026-08-15 | The larger-base arm scores a new candidate under the hardened contract; its report has its own non-comparable home (§ 10.6) | 2 — adds a disclosure | No |
| 2026-08-24 | The held-out source-B split is fixed and committed; § 7.1 is closed by the amendment below (§ 10.7) | 1 — closes an open item | Yes |
| 2026-08-25 | The promotion gate's retry count `R` is declared; § 7.2 is closed by the amendment below (§ 10.8) | 1 — closes an open item | Yes |
| 2026-08-27 | The honest-number report measures the delta/final series under the loop's contract; its report has its own non-comparable home (§ 10.9) | 2 — adds a disclosure | No |
| 2026-09-02 | The fine-tuned base is pinned; § 7.3 is closed by the amendment below (§ 10.10) | 1 — closes an open item | Yes |
| 2026-09-08 | A portability arm trains a second, smaller base on a second runtime; § 10.10's base is untouched (§ 10.11) | 1 — pins an input for a new arm | Yes |
| 2026-09-08 | The portability arm asks the gate's question once, on its own base and runtime; § 10.10's base untouched and the § 3 baseline unspent (§ 10.12) | 1 — pins the inputs of a measurement | Yes |
| 2026-09-09 | The portability arm scales to a 1.5B base on the same runtime; § 10.10's base untouched (§ 10.13) | 1 — pins an input for an existing arm | Yes |
| 2026-09-13 | The portability arm scales again, to a 3B base on the same runtime; § 10.10's base untouched (§ 10.14) | 1 — pins an input for an existing arm | Yes |

Everything above § 10 is as first committed. No amendment has introduced a success threshold, and
none has narrowed, retracted, or reworded § 1, § 4, or any disclosure in § 6. § 7.3 is closed by the
dated amendment below (§ 10.10). § 7.1 and § 7.2 are closed by the dated amendments below (§ 10.7, § 10.8).

## 10. Amendments

Appended under § 8. Each is dated, committed as its own change, and recorded in the log above.
Nothing above this heading is edited by anything below it; that is what append-only means here.

### 10.1 The generation contract is an unpinned input, and it moves the numbers — 2026-08-01

**Type 2 (§ 8.2): a disclosure, added.** It closes no open item, sets no threshold, and rewords
nothing in § 1, § 4, or § 6. It is disclosed **after** the P1 base-selection bake-off ran rather
than before it, which § 8.2 permits and which is said plainly here rather than smoothed over: the
effect was observed **in** that run, and a limitation found late is disclosed late rather than not
at all.

**The disclosure.** § 3 pins five inputs — model revision, task set, environment pins, seeds, and
tool versions — and treats a change in any of them as invalidating a series. The **generation
contract** is not among the five, and it should have been read as one. It is the whole of how a
task becomes a candidate patch: the prompt template, the retrieval setting that decides which
files of the repository the policy is shown, the sampler and its token budget, and the extractor
that turns a completion into a diff. The bake-off is the first concrete demonstration that it
moves the quantities this document pre-registers.

- **It moves `solved`.** A completion that never becomes an applicable diff cannot reach `PASS`,
  so the extractor and the token budget bound the metric before the verifier is reached at all.
- **It moves `N`.** The contract used in P1 states the patch-scope rule to every candidate — that
  the test files are held by the operator, and that a patch modifying one is refused before it is
  run. That is the right call for comparability, since every base is told the same thing and the
  contract does not name which files are held; but it also discourages precisely the behaviour
  `N` counts. **An `N` measured under a disclosing contract is a floor, not a rate**, and an `N`
  measured under a different contract is not comparable to it. This bound is in addition to the
  residual bound already disclosed in § 6.3, not a replacement for it.
- **It moves what a count means.** P1 used the **oracle retrieval** setting, in which the prompt
  carries the non-test files that task's reference patch touches, as they stand at the base
  commit. Every figure measured that way is an **upper bound** on what the same base would do
  from the bug report alone, and it may not be set beside a published figure measured without
  retrieval.

**What this obliges from here on.** Every report publishing a figure this document governs states
its generation contract in the provenance block, identifiably enough that two contracts can be
told apart — at minimum a hash of the prompt template, the retrieval setting, the sampler and its
token budget, and a version for the extractor. Two figures measured under different contracts are
reported as what they are: **not comparable**. This adds a disclosure and a reporting obligation.
It does not narrow § 4, which continues to govern everything it governed before.

### 10.2 With one public instance, § 4's contamination signature is undetectable — 2026-08-01

**Type 2 (§ 8.2): a disclosure, added.** It withdraws nothing and closes nothing.

§ 4 commits to publishing both sources together, to reporting a disagreement between them as a
finding, and it names public-gain-with-private-flat as the expected signature of contamination.
§ 6.2 already discloses that source A is one eligible instance of 300. The consequence of putting
those two facts side by side was never stated, and is stated now: **on a single public instance
that signature cannot be detected in practice.** One instance can agree with source B or disagree
with it, and neither outcome carries evidence about contamination either way.

So the absence of an observed signature is **not** evidence that there is none, and no report may
present it as such. The commitment in § 4 is unchanged — both sources are still always published
together, and a disagreement is still reported as a finding rather than resolved by picking the
flattering source. What is bounded is the diagnostic power of that comparison over source A, and
it stays bounded by a denominator of one until the public corpus grows.

### 10.3 Donor names are replaced by stable pseudonyms, and the redaction is disclosed — 2026-08-04

**Type 2 (§ 8.2): a disclosure, added.** It closes no open item and sets no threshold.

**What changed.** Source B's donors were named in this document — and across the repository — by
their own repository names. They are the author's **private** repositories, this file is
published, and their names are theirs rather than this project's to publish. Every mention is now
a stable pseudonym: `donor A`, `donor B`, `donor C`. The sibling verification project whose
verdict semantics, sandbox approach and inference guard this project ports is likewise referred
to by description rather than by name. `tasks/README.md` carries the key.

**What did not change, which is the part that matters here.** No claim, count, denominator,
definition, commitment or limitation is altered by this amendment. Source B is still 66 tasks, 45
from one donor and 21 from another; the third donor was still **refused** for having no `uv.lock`,
so § 6.1's mitigation still did not land; the donors are still the author's own repositories and
still *about* verification and sandboxing, which is the property § 6.1 exists to disclose and
which survives the renaming intact. A reader can check this: the substance of every § 6 disclosure
is unchanged, and only identifiers moved.

**Why this is recorded rather than done quietly.** § 8.3 forbids narrowing, retracting or
rewording § 1, § 4, or any disclosure in § 6, and § 8.4 forbids silent edits. This amendment
touches the *text* of § 6.1, so it is logged rather than slipped in. The prohibition in § 8.3 is
against weakening what the document commits to; replacing a private name with a stable label
weakens nothing, and leaving the names in place would have meant publishing third-party
information to satisfy a rule about not softening claims. Both readings are stated so a reader can
judge the call rather than take it on trust.

**A residual, stated rather than left to be found.** Mined task ids are formed as
`<donor>-<sha>`, and that derivation predates this amendment. So the donors' own names still
appear inside task ids in `tasks/local-ledger.json` and in `reports/baseline/`, and the pseudonyms
above do not cover them. Closing it means re-minting the corpus, which would invalidate all 66
recorded manifest hashes and re-run the liveness proof; it is deliberately not done here, and the
redaction is therefore **partial by choice**. The miner no longer writes a donor path or name into
any newly committed file (`whetstone mine --label`).

### 10.4 The format-hardening contract is a second generation contract, declared non-comparable — 2026-08-09

**Type 2 (§ 8.2): a disclosure, added.** It closes no open item, sets no threshold, and rewords
nothing in § 1, § 4, or § 6.

**The disclosure.** The format-hardening slice hardens the generation contract § 10.1 names: a
candidate may be re-asked after a parse refusal, under a **retry budget of two**, with each retry
prompt fixed by a frozen template. The hardened contract publishes its retry budget, a digest of
the retry template, and a digest of the diagnosis vocabulary that decides a retry, as
generation-contract fields — so two contracts can be told apart programmatically, which is what
§ 10.1 obliges from here on. The retrieval setting remains the oracle setting of § 10.1, and the
hardened contract declares its own development subset, excluded from both sources before anything
runs and never scored by the contract it was developed against (M7b).

**The two reports are declared non-comparable.** A figure measured under the hardened contract
is not comparable to one measured under the contract the baseline report publishes — the two
differ in an unpinned input, the generation contract. `reports/baseline/` and
`reports/format-hardening/` are therefore declared non-comparable homes: each is the only home
of its own figures, and neither is a second home for the other's. The baseline's artifacts are
static and are not regenerated. At the time of this amendment no count has been measured under
the hardened contract, and none is claimed here.

### 10.5 The easier-stratum probe scores a changed task set, declared non-comparable — 2026-08-14

**Type 2 (§ 8.2): a disclosure, added.** It closes no open item, sets no threshold, and
rewords nothing in § 1, § 4, or § 6.

**The disclosure.** The format-hardening arm's pre-committed fork rule names an easier task
stratum as the next unit (`docs/planning/p2-format-hardening/measured-arm/finding.md` § 5).
The easier-stratum probe re-tests the P2 premise — that strict-PASS training data exists —
on a difficulty stratum of the declared source-B set, selected by a pre-committed rule and
declared in a committed stratum document before the probe runs. The probe runs the hardened
generation contract § 10.4 discloses, on the stratum's tasks.

**The three reports are declared non-comparable.** § 3 pins five inputs — model revision,
task set, environment pins, seeds, and tool versions — and treats a change to any of them
as invalidating a series. The task set is a different one here: the probe measures a new
series, not an extension of an old one, and a figure from it may not be compared with one
from `reports/baseline/` — a different task set and a different contract — or with one from
`reports/format-hardening/` — a different task set under the same contract.
`reports/easier-stratum/` is therefore the only home of the probe's figures, and the
existing homes' artifacts are static and are not regenerated.

**What the probe is not.** The probe is a yield test: it measures whether training data
exists on the easier stratum, under the fork rule pre-committed in its PRD. It is not the
pinned baseline of § 3 (`:126-128`), which stands unmeasured and may still be measured
exactly once; it is not the held-out split of § 7.1, which remains open until P3. At the
time of this amendment no count has been measured under the probe, and none is claimed here.

### 10.6 The larger-base arm scores a new candidate, declared non-comparable — 2026-08-15

**Type 2 (§ 8.2): a disclosure, added.** It closes no open item, sets no threshold, and
rewords nothing in § 1, § 4, or § 6.

**The disclosure.** The easier-stratum probe's pre-committed fork rule names the
larger-base arm as the next unit after the probe's zero
(`docs/planning/p2-easier-stratum/prd.md:44-55`). The arm re-tests the P2 premise — that
strict-PASS training data exists — on the same declared source-B set, under the same
hardened generation contract § 10.4 discloses, with a new candidate. Model revision is
one of the five pinned inputs (`:131-132`), and a change to a pinned input invalidates a
series and starts a new one (`:133-135`), so the arm's figures are a new series, not an
extension of an old one.

**The four reports are declared non-comparable.** A figure from the arm may not be
compared with one from `reports/baseline/` — a different model revision under a
different contract; with one from `reports/format-hardening/` — a different model
revision under the same contract; or with one from `reports/easier-stratum/` — a
different model revision and a different task set. `reports/larger-base/` is therefore
the only home of the arm's figures, and the existing homes' artifacts are static and
are not regenerated.

**What the arm is not.** The arm is a measurement: it re-tests whether strict-PASS
training data exists at a larger base. It is not the pinned baseline of § 3
(`:126-128`), which stands unmeasured and may still be measured exactly once; it is not
the held-out split of § 7.1, which remains open until P3; and it is not a
base-selection closure — it produces evidence only, and § 7.3 closes by a Type 1
amendment committed before the measurement it governs runs (§ 8.1). At the time of this
amendment no count has been measured under the arm, and none is claimed here.

### 10.7 The held-out source-B split is fixed and committed — 2026-08-24

**Type 1 (§ 8.1): closes § 7.1, committed before the split is used to score anything.** It
introduces no success threshold and rewords nothing in § 1, § 4, or § 6.

**The split.** § 7.1 is closed by this amendment: 12 of the 66 declared source-B tasks are
held out, fixed by the rule that follows and committed at `tasks/heldout/source-b.json`
(schema `whetstone-heldout/1`) — the document the promotion gate and the night consume,
sealed by a digest its loader refuses a hand-edit of, in the same commit as this amendment.

**The rule that fixed it.** The 66 tasks are ordered into three terciles by the stratum
document's per-task difficulty measurement (`tasks/stratum/easier.json`: files / hunks /
added+deleted); per band, the members sort by `sha256(split_seed, task_id)` and the first
`max(MIN_PER_BAND, ceil(MIN_HELDOUT / HELDOUT_BANDS))` are held out, under the pre-committed
floors of at least 10 held-out tasks and at least 2 from each band. The rule lives in code
(`src/whetstone/loop/heldout.py`) and its digest is sealed into the document, so any rule
edit invalidates the document by design. The membership is 4 tasks per band, 12 in total; a
split that could not meet the floors would have been the published finding § 7.1 names,
never a loosened floor.

**What is not claimed.** No measurement has been run on the split, and none is claimed
here: this amendment precedes any scoring, which is the whole of its value, and the pinned
baseline measurement of § 3 remains unspent.

### 10.8 The promotion gate's retry count `R` is declared — 2026-08-25

**Type 1 (§ 8.1): closes § 7.2, committed before the first gated evaluation.** It introduces
no success threshold and rewords nothing in § 1, § 4, or § 6.

**The value.** `R = 3`. It is a declared constant in the gate's own module
(`RETRY_COUNT`, `src/whetstone/loop/gate.py`), landed in the commits this amendment follows,
and it is deliberately **not** a command-line flag: a run that could choose its own retry
budget would make this amendment a formality, and no two gated evaluations would be
comparable.

**It is declared, not derived, and that is stated rather than glossed.** § 7.2 asks for `R`
to be *"set from the observed unverified rate rather than guessed"*. No such rate has been
observed: no night has run and no gated evaluation has run, so there is nothing to set it
from. The larger-base arm reported its unverified rate qualitatively as material, which is
the reason the mechanism exists at all but is not a rate this value was computed from.
`R = 3` is therefore an a-priori declaration under § 8.1's deadline — fixed before the
measurement it governs, which is the whole of its value — and its revision path is a further
dated amendment grounded in a measured rate, never a code edit alone.

**What the mechanism does, so that what `R` governs is unambiguous.** Only a held-out task
that reached **no verdict** is retried; a verdict is final, and a task the candidate was
scored on and failed is never re-run. Each retry replays the first attempt's own recorded
bytes — identical inputs, checked rather than assumed — so a retry is verification
re-execution and never a second generation. A task that verifies on retry is verified. A task
still without a verdict after `R` retries keeps the **whole evaluation** `UNVERIFIED`: not
promoted, and not rejected either, because no comparison was made on it.

**What is not claimed.** No gated evaluation has run, so no unverified rate is reported here
and none is implied by this value. The gate's output carries the unverified count over its
denominator from its first evaluation onward. And § 7.2's own instruction stands unchanged: if
the gate proves unable to fire, the fix is a more reliable sandbox, never a looser gate.

### 10.9 The honest-number report measures the delta/final series under the loop's contract, declared non-comparable — 2026-08-27

**Type 2 (§ 8.2): a disclosure, added.** It closes no open item, sets no threshold, and
rewords nothing in § 1, § 4, or § 6.

**The disclosure.** The honest-number report publishes the P4 headline — the delta
between the § 3 baseline's counts and the promotion gate's final side's, over the
held-out split, with both sources always in the same document (§ 4). Its final-side
figures are measured under the loop's generation contract, whose **seeded categorical
sampler** (`sampling.K = 8` draws per task, each seeded from the run's seed, the task
id and the attempt index) differs from every published contract's greedy sampler. The
sampler is part of the generation contract § 10.1 obliges a report to state, and the
difference is recorded in every run ledger. The contract is not a pinned input
(§ 10.1), so the delta against the same series' baseline remains legitimate: the
baseline and the final side are measured under the same series, and the sampler
difference is disclosed here rather than let to read as a disqualification.

**The five reports are declared non-comparable.** A figure from the report may not be
compared with one from `reports/baseline/` — a different model revision under a
different contract; with one from `reports/format-hardening/` — a different model
revision under the same contract; with one from `reports/easier-stratum/` — a
different task set and a different contract; with one from `reports/larger-base/` — a
different model revision and a different contract; or with one from
`reports/baseline-measurement/` — the § 3 baseline's own, which this report renders
and which keeps its own home. `reports/honest-number/` is therefore the only home of
the delta/final series' figures, and the existing homes' artifacts are static and are
not regenerated.

**Two exceptions are argued, never silent.** The § 4 shape requires the baseline's
counts (`baseline c of b`) and source A's funnel (the eligibility and the refusals by
gate) in the same document as the delta. The baseline-side figures are the sealed § 3
artifact's own, rendered through its fail-closed loader by identity and asserted
byte-equal to the artifact's figures — never restated from another home. The funnel
figures are committed corpus facts: the four-gate funnel over SWE-bench-Lite's 300,
as `tasks/public/ineligible.json`'s denominators declare them, asserted equal to the
ledger, never recomputed. Both are named here so the report's overlaps with the
existing homes are the two admitted sets and nothing else.

**What the report is not.** The report is the § 4 document itself: it renders the
operator chain's fruits — the baseline spend, the two nights, the first gated
evaluation — and measures nothing by itself, the number it publishes being the gate
decision's function, never a new measurement. It is not the pinned baseline of § 3
(`:126-128`), which stands unspent until the operator measures it; it is not the
held-out split's own report; and § 7.3 stays open, closing only by a Type 1 amendment
committed before the measurement it governs runs (§ 8.1). At the time of this
amendment no count has been measured under the report, and none is claimed here.

### 10.10 The fine-tuned base is pinned, closing § 7.3 — 2026-09-02

**Type 1 (§ 8.1): closes § 7.3, committed before the night it governs runs.** It introduces
no success threshold and rewords nothing in § 1, § 4, or § 6.

**The base.** The nightly loop fine-tunes `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`,
pinned at the immutable revision `d1e3b690c8e225d7795bccddf971ca6be68b2012` and recorded by
per-file hash in `weights/provenance.json` (gitignored — the weights never leave the box),
re-hashed on every run by the harness. The night runbook's resolution block names the same
base (`docs/planning/p2-rollouts/night-door/runbook.md`), and the run ledger records it, so
the base this amendment pins and the base the night runs are one and the same input.

**The evidence it was chosen on.** § 7.3 asks that the base be decided on evidence against
the working verifier, not on paper. The larger-base arm is that evidence: it scored this
candidate on the declared source-B set under the hardened contract with the control
discipline intact, and it produced the first nonzero strict-PASS yield the harness has ever
measured. The arm's figures have one home, `reports/larger-base/`, and this amendment
restates none of them; the arm's finding names the fork decision and the closure rule this
amendment performs (`docs/planning/larger-base-arm/finding.md`). The base is named as the
best available evidence, not as a selection the evidence exceeds.

**What is not claimed.** No night has run: no training set, checkpoint or yield figure
exists. At the time of this amendment no night has run, no count has been measured under it,
and none is claimed here — this amendment precedes night #1, which is the whole of its
value, and the pinned baseline measurement of § 3 remains unspent. The base is pinned for
this series; it remains deliberately swappable, and a change of base is a further Type 1
amendment committed before the measurement it governs runs (§ 8.1).

### 10.11 A portability arm, with its own base and its own runtime — 2026-09-08

**Type 1 (§ 8.1): pins the inputs of a new arm, committed before the training it governs
runs.** It introduces no success threshold, rewords nothing in § 1, § 4, or § 6, and — this is
the part that matters — **does not change the base § 10.10 pinned.** The 32B base and the MLX
runtime remain the pinned inputs of the main series. This amendment opens a second arm beside
it, in the shape `reports/larger-base/` and `reports/easier-stratum/` already established: a
changed input means a non-comparable arm with its own home, never a quiet substitution inside
an existing series.

**Why an arm and not a substitution.** Whetstone's runtime was MLX end to end, which is Apple
Silicon only, so the loop could train on exactly one class of machine and the model it produced
was loadable by exactly one runtime. That is a property of the *implementation*, not of the
thesis: nothing in the wedge — an execution-grounded reward, a never-regress gate, an honest
number — depends on Metal. This arm exists to demonstrate the loop on a second runtime and a
second operating system, and to emit an adapter in the ecosystem's own interchange format so
that what the loop produces is loadable off the machine that produced it.

**The base.** The arm fine-tunes an open Qwen2.5-Coder instruct base in Hugging Face format,
pinned by immutable revision and recorded by per-file hash in the same
`weights/provenance.json` shape the main series uses, re-hashed before a token is generated.
The specific base and revision are recorded in the arm's own report home before it trains,
because a base named after the fact is not a pinned input.

**The base size is deliberately not fixed by this amendment, and the machinery must not fix it
either.** The arm begins at the smallest size that trains on the hardware available — a CPU-only
Linux host with 16 GB of RAM — because the question it answers first is *does the loop run at
all off Apple Silicon*, and that question is answered no better by a larger base than by a
smaller one. Larger bases on this runtime are expected and intended. Each is a further Type 1
amendment naming its base and revision, committed before it trains; the trainer, the adapter
format and the gate take the base as an input and are required to be indifferent to its size, so
that scaling up is an amendment and not a rewrite.

**Comparability, stated plainly.** A figure measured under this arm is **not comparable** to any
figure from the main series, and not to any other arm's. Different weights, a different runtime,
different kernels and a different quantisation of the same architecture all sit between them,
and each is sufficient on its own to make the comparison meaningless. The arm's figures have one
home and this document restates none of them. The promotion gate already refuses to score a
candidate from one runtime against an incumbent from another, and that refusal is the mechanical
form of this paragraph.

**What is not claimed.** No training has run under this arm. At the time of this amendment no
count has been measured under it and none is claimed here — the amendment precedes the training,
which is the whole of its value. In particular nothing here claims the arm's adapter is better
than its base: that is the promotion gate's question, on a held-out set, and it is unasked. The
§ 3 baseline remains unspent.

### 10.12 The portability arm asks the gate's question, on its own base and its own runtime — 2026-09-08

**Type 1 (§ 8.1): pins the inputs of a measurement, committed before it runs.** It introduces
no success threshold, rewords nothing in § 1, § 4, or § 6, and **does not change the base
§ 10.10 pinned** or spend the § 3 baseline. It extends the arm opened by § 10.11 and nothing
else.

**What changes, stated exactly.** § 10.11 closed with *"nothing here claims the arm's adapter is
better than its base: that is the promotion gate's question, on a held-out set, and it is
unasked."* This amendment asks it — once, under this arm, with the answer published whatever it
is. The sentence in § 10.11 is not edited; this document is append-only, and an earlier
commitment that has been superseded is more useful visible than tidied away.

**Why ask it here rather than wait for the main series.** The never-regress promotion gate is
the mechanism this project's central claim rests on, and **it has never scored a real
candidate.** Its three exits, its retry discipline and its refusals are proven against fixture
checkpoints and a stub engine; whether it fires on real weights, on a real machine, is
unmeasured — `docs/ROADMAP.md` § 12 says so in those words. That is a question about the
*mechanism*, not about any model, and it is answered no better by a large base than by a small
one. The main series' gated evaluation should not be the first time the gate has ever run.

**The measurement, pinned.**

| | |
|---|---|
| Candidate | a checkpoint from a night drawn **and** trained end to end on the arm's runtime |
| Incumbent | the untrained arm base that night started from, loaded through `baseline_engine` |
| Task set | the held-out source-B membership fixed by § 10.7, unchanged |
| Decoding | greedy on both sides, `sampler_for(1)` by identity |
| Home | `reports/portability-arm/`, the arm's own, declared by § 10.11 |

The night is drawn on the arm's runtime, which § 10.11's first run was not: that checkpoint was
trained on Linux from examples night #1 had already drawn on Apple Silicon. A candidate whose
rollouts came from one runtime and whose training came from another is a hybrid, and the arm's
question is about a loop that runs in one place.

**What is not claimed, and what a result here does not license.** A figure from this evaluation
is **not comparable** to the main series or to any other arm — § 10.11's comparability paragraph
governs unchanged, and the gate's own `MismatchedBackend` is its mechanical form. It is not the
§ 3 baseline, which remains unspent and whose one home is `reports/baseline-measurement/`. It is
not the § 1 headline, and it may never be quoted as one.

**The expected outcome is no promotion, and that is written down before the run.** The arm's
training set is a handful of strict-`PASS` examples on a small base. A gate that rejects is the
mechanism working, and a rejection is published with the same prominence a promotion would be
(`CLAUDE.md` #5; P4 carries no pivot signal). **No threshold is introduced here**: the gate's
promotion rule is the one already fixed in § 2 and § 10.8, and this amendment does not touch it.

**One disclosure it costs.** Scoring the held-out membership under this arm means that set has
now been looked at by one more candidate. With a single evaluation the selection pressure is
negligible, but it is not zero, and the honest form of that is to say so here rather than to
discover it later: every future arm scored against the same 12 tasks adds to it, and a
membership scored many times stops being held out in the sense § 10.7 intended.


### 10.13 The portability arm scales to a larger base, on the same runtime — 2026-09-09

**Type 1 (§ 8.1): pins the input of an existing arm, committed before the training it governs
runs.** It introduces no success threshold, rewords nothing in § 1, § 4 or § 6, and **does not
change the base § 10.10 pinned.** The 32B base and the MLX runtime remain the pinned inputs of
the main series.

**This amendment is the mechanism § 10.11 described, not a new argument.** That amendment closed
by saying the arm begins at the smallest base that trains on the hardware, that *"larger bases on
this runtime are expected and intended"*, and that *"each is a further Type 1 amendment naming its
base and revision, committed before it trains."* This is that amendment, for the first such step.

**The base.** `Qwen/Qwen2.5-Coder-1.5B-Instruct`, at immutable revision
`2e1fd397ee46e1388853d2af2c993145b0f1098a`, recorded by per-file SHA-256 in
`weights/provenance.json` in the same shape the main series uses, and re-hashed before a token is
generated. The runtime is unchanged from § 10.11: `torch` on a CPU-only Linux host with 16 GB of
RAM. The arm's previous base, `Qwen/Qwen2.5-Coder-0.5B-Instruct` at
`ea3f2471cf1b1f0db85067f1ef93848e38e88c25`, remains in that document rather than being replaced,
so what has already run under it stays attributable.

**Why the step is taken, stated without a number.** The arm's night under the 0.5B base ran to
completion with the control arm intact on every draw and selected **zero** strict-`PASS` rollouts.
The binding constraint was not the reward and not the harness: the overwhelming majority of
rollouts produced no well-formed unified diff at all, under a retry budget that was already on.
That is a statement about what the base could express, not about what the verifier would accept,
and the response to it is a base with more capacity — never a looser notion of what counts as a
win. The counts behind this paragraph live in that night's ledger and in `docs/STATUS.md`; this
document restates none of them.

**A feasibility check preceded this amendment, and it is not a result.** Before naming this base,
four draws were taken from it on one task's prompt, off the arm's own engine, and passed to the
arm's own extractor, solely to establish that the machine could host the base and that the base
could produce diff-shaped output at all. **It is a feasibility check and not a measurement**: four
draws, one task, no verifier, no control arm, and no scoring. It is recorded here so that it can
never be mistaken for a finding or quoted as one. **No count from it is published, it sets no
threshold, and it decides nothing about what counts as a win.** Had it shown the base could not
express a patch on this hardware, the honest act would have been to report that and not write this
amendment — which is why it ran before the amendment rather than after.

**Comparability, unchanged and restated.** A figure measured under this arm is **not comparable**
to any figure from the main series, to any other arm's, or to the arm's own figures under its
previous base. A different base is a different candidate; § 10.6 established that a new candidate
gets its own non-comparable home, and nothing about a base being larger makes it comparable to a
smaller one. The promotion gate already refuses to score a candidate from one runtime against an
incumbent from another, and it compares a candidate against the base it was trained from — not
against the arm's earlier base.

**What is not claimed.** No training has run under this base. No count has been measured under it
and none is claimed here — the amendment precedes the training, which is the whole of its value.
Nothing here claims this base will yield a strict-`PASS` rollout, that its adapter will beat its
base, or that a checkpoint will exist at all; the arm's night under the previous base produced
none, and that outcome remains entirely possible here. The § 3 baseline remains unspent.

### 10.14 The portability arm scales again, to a 3B base on the same runtime — 2026-09-13

**Type 1 (§ 8.1): pins the input of an existing arm, committed before the training it governs
runs.** It introduces no success threshold, rewords nothing in § 1, § 4 or § 6, and **does not
change the base § 10.10 pinned.** The 32B base and the MLX runtime remain the pinned inputs of the
main series.

**This is the second application of the mechanism § 10.11 described**, and § 10.13 was the first.
That amendment closed by saying larger bases on this runtime are *"expected and intended"* and that
*"each is a further Type 1 amendment naming its base and revision, committed before it trains."*
This is that amendment for the next rung.

**The base.** `Qwen/Qwen2.5-Coder-3B-Instruct`, at immutable revision `488639f1ff808d1d3d0ba301aef8c11461451ec5`, recorded by
per-file SHA-256 in `weights/provenance.json` in the same shape the main series uses, and re-hashed
before a token is generated. The runtime is unchanged from § 10.11 and § 10.13: `torch` on a
CPU-only Linux host with 16 GB of RAM. Both previous bases remain in that document rather than
being replaced, so what has already run under each stays attributable.

**Why the step is taken, stated without a threshold.** The arm's night under the 1.5B base ran to
completion with the control arm intact on every draw and selected **zero** strict-`PASS` rollouts,
exactly as the night under the 0.5B base had. What changed between those two nights is *which*
constraint was binding. Under the smaller base the overwhelming majority of rollouts produced no
well-formed unified diff at all; under the larger one most of that difficulty was gone and the
failures moved one stage later — patches that git could parse, that named real files, and that did
not fix the bug. Two outcomes that had never been reached before were reached: patches that applied
and ran the task's real tests, and patches refused for aiming at an operator-held test file. The
counts behind this paragraph live in that night's ledger, in `docs/STATUS.md` and in
`reports/portability-arm/report.md`; this document restates none of them.

That is the reason for another base and it is worth stating precisely, because it is not *"the
number went up"*. It is that the failure mode changed in the direction more capacity predicts, and
the honest next move is more capacity — never a looser notion of what counts as a win.

**What has been checked before naming this base, and what it is not.** That the machine can host
the base and run the existing chain against it is established by a `--probe` run, whose go/no-go is
decided by `whetstone check-probe` against the rule pre-committed in the night door's runbook. A
probe writes no checkpoint and reaches no trainer. **It is a feasibility check and not a
measurement**: no count from it is published, it sets no threshold, and it decides nothing about
what counts as a win.

**Comparability, unchanged and restated.** A figure measured under this arm is **not comparable**
to any figure from the main series, to any other arm's, or to this arm's own figures under either
previous base. A different base is a different candidate; § 10.6 established that a new candidate
gets its own non-comparable home, and nothing about a base being larger makes it comparable to a
smaller one. The promotion gate already refuses to score a candidate from one runtime against an
incumbent from another, and it compares a candidate against the base it was trained from.

**What is not claimed.** No training has run under this base. No count has been measured under it
and none is claimed here — the amendment precedes the training, which is the whole of its value.
Nothing here claims this base will yield a strict-`PASS` rollout, that its adapter will beat its
base, or that a checkpoint will exist at all. **Two consecutive nights under this arm have produced
none, and a third such outcome is entirely possible** — a larger base is the pre-registered
response to a zero, not a prediction that the zero ends. The § 3 baseline remains unspent.
