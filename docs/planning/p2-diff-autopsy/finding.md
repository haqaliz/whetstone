# Finding — what the unparseable diffs contain, measured

**Slice:** `p2-diff-autopsy` · **Written:** 2026-08-09, after the autopsy ran over the two
stored bake-off runs (`runs/arm-a/`, `runs/budget-2048/`).
**Instrument:** `src/whetstone/bakeoff/autopsy.py` (offline, deterministic, stdlib-only) ·
**Local evidence:** `runs/diff-autopsy/` (gitignored — the only home of the numbers).

---

## 1. What this document is

The yield-probe correction demanded a fourth fix be proposed only after someone read what the
unparseable diffs actually contain (`docs/planning/p2-yield-probe/prd.md:84-89`). The read
was done by hand (`dig-transcripts.md`); this slice built the instrument that makes the read a
measurement, ran it over both stored runs, and — in the way the instrument was designed to —
let the measurement correct the hand-read where the two disagreed. This finding says what the
measurement shows. **It carries no figure about a model**: the numbers live in the gitignored
breakdowns, and a number quoted here would be a second home for itself.

## 2. The wall

**The evidence points at a formatting wall, not a reasoning wall and not an extraction wall.**

The three candidates do not share a failure mode — they share a format contract and violate
it in three different, per-model dialects. One candidate's output collapses into a repetition
loop of its own chat-template tokens: nothing that looks like an answer, let alone a patch.
A second writes the full git-shaped skeleton — `diff --git`, an index line, the file header
pair — and then fails inside the hunks: bodies that stop on a line the diff grammar does not
accept, or trailing garbage on the index line. The third writes the plain unified dialect
without the git header — the dialect git accepts when the hunks are right — but its hunk
headers declare line counts that the bodies do not satisfy; the counts are invented rather
than counted, and git's own parser, once a counter is exceeded, never stops reading and dies
at "corrupt patch".

None of this is the bases being unable to fix the bugs. The control category — the diff that
git parses and that reaches the apply layer — occurs for every candidate, and in each case
those diffs are task-relevant code, not gibberish. The bases *can* write a diff git accepts;
they almost never do, and the difference between the two is entirely on the formatting side
of the contract. It is not an extraction wall: the extractor located a diff in every record
the attribution says git refused, and its never-repair rule — which this instrument inherits
by identity — is what correctly refuses to fix what the model wrote.

**The roadmap's named responses are unsupported by this evidence.** An easier task stratum
and a larger base are both answers to "the bases cannot fix these bugs". This data says the
premise of that fork was never reached: the rollouts died before any fix could be graded. A
format-hardening response — the side of the generation contract the yield probe left open —
is the intervention the data names, and until it runs, the pivot signal's premise remains
untested, exactly as the yield-probe correction said. This slice proposes no fourth fix; it
says where the evidence points, which is what the fix's proposal was waiting for.

## 3. The measurement corrected the hand-read

The instrument's first run disagreed with the run's own attribution on a family of records —
and the mapping assertion, which exists to surface exactly that, named each one instead of
smoothing it. Reading the records showed three places where the walk's rules were not git's
rules on the same bytes:

- **A check that read past the diff.** The walk treated a line *after* the extracted diff as
  evidence the body overran its counts — but the extracted diff is all git ever receives, so
  the check fired on patches git had applied. Removed.
- **A blind spot where git never stops.** git's parser keeps reading a hunk while either
  counter is non-zero — and a counter driven negative by an over-long body is still
  non-zero, so git dies at "corrupt patch" where the walk saw a completed hunk. The walk now
  records the overrun by name.
- **A mapping gap.** A loop-dominated completion can carry a stub diff that git refused —
  the loop ate the budget, the stub died — a combination the table had not listed.

Each correction has a fixture and was watched failing before it landed
(`tests/bakeoff/test_autopsy_walk_fixes.py`). After the corrections, the instrument agrees
with the run's own attribution on every stored record, and the two runs classify completely
with no unrecognised shape. The corrected partition agrees with the hand-read exactly on the
control category — every diff the hand-read counted as git-parseable is `well-formed`, and
every candidate that produced a complete diff is counted so — and diverges from it only at
the one margin the dig itself called fuzzy: whether a failure is a hunk dying early or a
hunk count mismatch. The hand-read decided by the length of the extracted diff; the
instrument decides by the mechanical rule that now agrees with git. The divergence is the
hand-read's heuristic, reported as the contract requires rather than reconciled.

## 4. Disclosures

1. **Truncation is inferred, not measured.** The runtime returns a bare string with no
   finish reason, so the "completion ends mid-hunk" death is named from the shape of the
   output, never claimed as a measured token cap. Every breakdown that carries it labels it
   inferred.
2. **The dig's counts were provisional.** They came from a throwaway hand-read and were kept
   only as the hypothesis; the autopsy's breakdown is the measurement and lives in the
   gitignored artifacts. Where the two differ, the finding above describes the difference in
   words; the numbers are in `runs/diff-autopsy/divergence-vs-dig.md`.
3. **The breakdowns are the authoritative numbers, and they are not published.** `reports/`
   still holds exactly the three baseline artifacts; the one-home rule is untouched. Any
   future document quoting a classifier count must point at the gitignored breakdown as its
   home, or it creates a second home for the same figure.
4. **One record aimed a diff at a held test — it is not a counted hack.** The verifier's
   scope rule exists to catch exactly that shape, but this record never reached the verifier:
   the patch failed before grading, so it is attempt-shaped evidence, not a reward-hacking
   count. `N` counts only graded rollouts, and this record changes no published number.

## 5. What is not claimed

- The bases cannot fix these bugs — **unproven**: the wall is upstream of any fix being
  graded, and the roadmap's fork stays open on the same unexamined premise until a
  format-hardening response runs.
- The 7B loop's cause — **unclassified**: the instrument names the shape; whether it is a
  sampling configuration, a model property, or a prompt failure is a question this slice does
  not answer.
- That a format-hardening response will raise any count — **not predicted**: this finding
  says what the intervention could convert, never what it would score.
- That the taxonomy generalises to future transcripts — **unproven**: it is complete over
  the corpus it was grounded in; a future run that defeats every detector is named
  `unrecognised-shape` until someone reads it, which is the point of the instrument.

## 6. Where the evidence lives

- The instrument: `src/whetstone/bakeoff/autopsy.py` (and its tests under `tests/bakeoff/`).
- The measurements: `runs/diff-autopsy/{arm-a,budget-2048}.json` and
  `runs/diff-autopsy/divergence-vs-dig.md` — gitignored, the only home of the numbers.
- The hand-read it corrected: `docs/planning/p2-diff-autopsy/dig-transcripts.md`.
