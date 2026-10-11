# Finding — the pinned base's whole-function completions do not clear the resolvability bar: NO-GO

**Slice:** `whole-function-edit-finding` / `measurement-run` · **Written:** 2026-10-11, after
the measurement ran once over the pre-committed population. **Instruments:**
`src/whetstone/bakeoff/measure.py` (the driver, `--renderer whole-function`) and
`src/whetstone/bakeoff/resolvability.py` (offline, deterministic, stdlib-only, no model).
**Rules:** `spec.md`, committed before the run; the rule sentence is cross-pinned into the
instrument's output (`resolvability.json`, `rule`). **Local evidence (the only home of every
count):** `runs/whole-function-edit-finding/` (gitignored).

## 1. The decision

**NO-GO.** The pre-committed rule — GO iff `count(RESOLVABLE) * 2 > population` — does not
hold for `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` (`d1e3b690c8e2`, the pinned § 10.10
base) over its **16** pinned tasks. The command exited 1. The partition, in full:

| class | count |
|---|---|
| RESOLVABLE | **0** |
| MALFORMED | 13 |
| NO_FILE | 0 |
| AMBIGUOUS | 0 |
| UNKNOWN_FUNCTION | 0 |
| NOT_PARSEABLE | 0 |
| UNCLASSIFIED | 3 |

The 16 equal the run's own population (`manifest.json`, `tasks`), which is the check that the
journal, the transcript and the manifest were joined correctly; the control arm was `INTACT`
on every one of the 16 draws, so the outcome is about the base and not about a verifier that
graded nothing.

By `spec.md` and the PRD's pre-committed discipline, the unit therefore ships the measurements
and this finding, and **does not build** the whole-function contract aspect or an amendment.
Nothing was built beyond the measurement.

## 2. What the completions looked like, in words

Thirteen of the sixteen tasks received a prompt (three are `NO_ORACLE` — see § 4.2). The base
**adopted the format**: completions open `EDIT <path>` blocks, name a `FUNCTION` the file does
contain, and write a `<<<<<<< REPLACE` body. The failures are two shapes, both of which are
violations of the format's own grammar:

- **A `def` line inside the body (8 of 13, MALFORMED).** The format's body is the function's
  *body* — the harness finds the function's extent, so the replacement must be body-only. The
  model instead wrote the whole function, opening with the signature and its indentation
  (`def <name>(...)`), inside the body block. The replacement text it produced is a complete
  definition — structurally coherent code — that the format cannot splice.
- **A stray marker (5 of 13, MALFORMED).** A `<<<<<<<`/`>>>>>>>` marker outside any block, or a
  block opened inside another block — the grammar pinned in the prompt written and then
  violated in the same text.

Zero completions were fully in-shape: nothing was a body-only replacement that the wrapped
standalone parse (following the resolved target's kind) could accept. The decision is
therefore not a marginal call — the bar was a strict majority of resolvable rollouts, and
none existed.

## 3. Corroboration, beside and never pooled

The splice read — `splice_in_context`, which splices a body over its resolved function and
re-parses the **file** — reports **0** across the whole run: not one replacement could be
spliced into the file it edits. It is reported beside the partition and was never decisive
(the spec's discipline). The `outside_shown_set` sub-count is 0: no completion addressed a
path outside the oracle listing's set — including no held-test path.

## 4. Disclosures

1. **The proxy is a wrapped standalone parse, and the finding says so rather than hiding
   behind the letter of the rule.** The gate follows the resolved target's kind — a function
   body — and an `IndentationError` is the format's own grammar violation (`MALFORMED`). The
   sharpest class, "def line inside the body", is not a proxy artefact: a body that opens with
   the signature cannot parse as a body under any reading, and the splice sub-count confirms
   the same text damages the file it edits.
2. **The population carried three `NO_ORACLE` members.** `donor-a-128bcb99b701`,
   `donor-a-16213e62eae1` and `donor-b-45740535725b` could not build an oracle under the
   sealed budget; no prompt was rendered for them, they are `UNCLASSIFIED` and **stay in the
   denominator** (the spec's rule, executed). They are the same class the held-out scorable
   rule excludes from the held-out set; the easier-stratum band has no such filter, and the
   pre-committed rule did not claim one.
3. **The measurement is a proxy, and it is one exposure.** No run had ever prompted under this
   format; the base met it once. NO-GO says the necessary condition — the base producing a
   resolvable whole-function edit on first exposure — did not hold; it does not prove that no
   prompt shape, no marker grammar and no example would ever clear it, and it says nothing
   about yield under any contract.
4. **The run's `prompt_sha256` is new** (`manifest.json`, `prompt_sha256`): the whole-function
   prompt has never been posed before, so every figure in this finding is comparable to
   nothing prior.

## 5. What is not claimed

- That a whole-function contract cannot help — **unproven**; see disclosure 3.
- That the base cannot fix bugs — **unproven**; generation is upstream of any grade, and the
  control arm — the only graded part of this run — was `INTACT` on all 16 draws.
- That a looser gate would change the decision — **not tested, and not proposed**: the
  splice read is 0 across the run, the same direction the standalone gate reported, and
  loosening a pre-committed rule to rescue a NO-GO is the exact move this project's
  discipline forbids.

## 6. Where this leaves the roadmap

The patch-representation axis is now **measured and spent in all three directions this
project's evidence could see**: search/replace was NO-GO on the quoting question
(`docs/planning/patch-representation/finding.md`), numbered-listing line-range was NO-GO on
the addressing-and-grammar question (`docs/planning/edit-contract-finding/measurement-run/
finding.md`), and whole-function replacement is NO-GO on the body-grammar question (this
finding). The wall the three measurements describe is the same wall, reported from three
angles: this base does not produce replacement *text* that conforms to a pinned edit grammar —
across the three formats, the malformed share of graded completions was 8/13, 13/13 and now
13/13, and the splice reads were 3, 0 and 0. The observation recorded for the next contract
designer sharpens once more: the failure is neither transcription of existing text
(search/replace), nor line addressing (numbered-listing), nor text-vs-name resolution
(whole-function) — it is writing replacement text that satisfies its own format's grammar at
all. The P2 pivot signal's pre-committed responses that remain untried are **raise *k*** and,
on the portability arm, the **CPU dtype** (`docs/ROADMAP.md` § 13). M1's exit criterion —
a night selects at least one strict-`PASS` and therefore writes both a ledger and a
checkpoint — stands open; § 14's "What is explicitly not on this path" names raising *k* for
the reason this evidence does not soften: it buys more samples from a pipeline where most
patches never apply.

**Nothing was built beyond the measurement, and no amendment was made.** The spec, the rule
and this finding stand as committed; the whole-function contract aspect and any
`PREREGISTRATION.md` § 10.x amendment remain unplanned and unbuilt, exactly as the
pre-committed rule required.