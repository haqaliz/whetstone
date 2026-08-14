# Pre-registration

**Committed 2026-07-29, in P1, before any number about a model existed.**

This document fixes what Whetstone will measure, which figure is the headline, how the result is
reported, and what its known limitations are — **before** the first measurement is taken. It
discharges `docs/ROADMAP.md` § 6 (`docs/ROADMAP.md:500-510`) and is P1 exit criterion 6
(`docs/ROADMAP.md:355-356`).

`docs/ROADMAP.md` § 4, P4 (`docs/ROADMAP.md:458-459`) grades the published headline against this
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
(`docs/ROADMAP.md:486-495`).

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
the same prominence (`docs/ROADMAP.md:462-463`). Shipping the honest number even when modest is
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
(`docs/ROADMAP.md:591-596`). Each is named with what closes it and by when. **An open item named
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

Everything above § 10 is as first committed. No amendment has introduced a success threshold, and
none has narrowed, retracted, or reworded § 1, § 4, or any disclosure in § 6. §§ 7.1, 7.2 and 7.3
are all still **open** — in particular the P1 bake-off selected no base, so it does **not** close
§ 7.3, and an amendment that tried to close it after the fact would document only that the item
was never closed (§ 8.1).

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
