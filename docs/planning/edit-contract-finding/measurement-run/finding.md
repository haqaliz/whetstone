# Finding — the pinned base's numbered-listing completions do not clear the addressability bar: NO-GO

**Slice:** `edit-contract-finding` / `measurement-run` · **Written:** 2026-09-30, after the
measurement ran once over the pre-committed population. **Instruments:**
`src/whetstone/bakeoff/measure.py` (the driver) and `src/whetstone/bakeoff/addressability.py`
(offline, deterministic, stdlib-only, no model). **Rules:** `spec.md`, committed before the run;
the rule sentence is cross-pinned into the instrument's output (`addressability.json`, `rule`).
**Local evidence (the only home of every count):** `runs/edit-contract-finding/` (gitignored).

## 1. The decision

**NO-GO.** The pre-committed rule — GO iff `count(ADDRESSABLE) * 2 > population` — does not
hold for `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` over its **16** pinned tasks. The
command exited 1. The partition, in full:

| class | count |
|---|---|
| ADDRESSABLE | **0** |
| MALFORMED | 8 |
| OUT_OF_RANGE | 5 |
| UNCLASSIFIED | 3 |

The 16 equal the run's own population (`manifest.json`, `tasks`), which is the check that the
journal, the transcript and the manifest were joined correctly; the control arm was `INTACT`
on every one of the 16 draws, so the outcome is about the base and not about a verifier that
graded nothing.

By `spec.md` and the PRD (§ 4.1 M9), the unit therefore ships the measurement and this finding,
and **does not build** the `numbered-listing-contract` aspect (§ 4.2) or the amendment (§ 4.3).
Nothing was built beyond the measurement.

## 2. What the completions looked like, in words

Thirteen of the sixteen tasks received a prompt (three are `NO_ORACLE` — see § 4.2). The base
**adopted the format**: completions open `EDIT <path>:<start>-<end>` blocks with
`<<<<<<< REPLACE` sections, name real repository-relative paths, and address plausible regions
of the shown files. The failures are three shapes:

- **Format discipline (8 of 13, MALFORMED).** Five completions emit a stray marker — a
  `<<<<<<<`/`>>>>>>>` line outside any block, or a block opened inside another block — and two
  open a replacement section the completion never closes. The grammar the prompt pinned was
  written and then violated in the same text.
- **Replacement text that does not parse (4 of 13, OUT_OF_RANGE).** The addressed ranges are
  in-bounds, but the replacement fails the gate. The shape here is mostly **fragment text**:
  indented config entries (e.g. a dict's values) addressed as a standalone edit. A standalone
  `ast.parse` cannot accept a fragment, and this is where the proxy is sharpest — see § 4.1.
- **Overlapping ranges (1 of 13, OUT_OF_RANGE).** One completion addresses two blocks on the
  same file whose ranges overlap.

Zero completions were fully in-shape: no rollout had every block in-range, non-overlapping and
parseable. The decision is therefore not a marginal call — the bar was a strict majority of
fully-addressable rollouts and none existed.

## 3. Corroboration, beside and never pooled

The splice read — the instrument's `syntax_fragile_in_context` sub-count, which splices each
replacement over its range and re-parses the **file** — reports 3 across the whole run. It
corroborates the decision in the direction that matters: even where a replacement could not be
judged by the standalone gate, splicing it into the file it edits rarely left the file
parseable. It is reported beside the partition and was never decisive (the spec's discipline).

The `outside_listing` sub-count is 0: no completion addressed a path outside the oracle
listing's set — including no held-test path. The measurement saw no scope-adjacent behaviour to
report.

## 4. Disclosures

1. **The proxy is sharp at the fragment boundary, and the finding says so rather than hiding
   behind the letter of the rule.** The pre-committed gate is `ast.parse` on the replacement
   alone (`spec.md`, "Decision"). A replacement that is a valid *fragment* of a larger
   structure — exactly what a line-range edit of a config dict legitimately is — cannot pass a
   standalone parse. The sub-count was designed for this and it does not rescue the outcome:
   3 fragile-in-context across the run, and 8 of 13 completions violated the format's own
   grammar, which no proxy sharpness explains.
2. **The population carried three `NO_ORACLE` members.** `donor-a-128bcb99b701`,
   `donor-a-16213e62eae1` and `donor-b-45740535725b` could not build an oracle under the
   sealed budget; no prompt was rendered for them, they are `UNCLASSIFIED` and **stay in the
   denominator** (the spec's rule, executed). They are the same class the held-out scorable
   rule excludes from the held-out set; the easier-stratum band has no such filter, and the
   pre-committed rule did not claim one.
3. **The measurement is a proxy, and it is one exposure.** No run had ever prompted under this
   format; the base met it once. NO-GO says the necessary condition — the base producing
   fully-addressable line-range edits on first exposure — did not hold; it does not prove that
   no prompt shape, no marker grammar and no example would ever clear it, and it says nothing
   about yield under any contract.
4. **The run's `prompt_sha256` is new** (`manifest.json`, `prompt_sha256`): the numbered-listing
   prompt has never been posed before, so every figure in this finding is comparable to nothing
   prior.

## 5. What is not claimed

- That a line-range contract cannot help — **unproven**; see disclosure 3.
- That the base cannot fix bugs — **unproven**; generation is upstream of any grade, and the
  control arm — the only graded part of this run — was `INTACT` on all 16 draws.
- That a looser gate (splice-parse instead of standalone-parse) would change the decision —
  **not tested, and not proposed**: the sub-count suggests it would move the 4
  parse-failing rollouts at most, and 8 MALFORMED rollouts would remain; and loosening a
  pre-committed rule to rescue a NO-GO is the exact move this project's discipline forbids.

## 6. Where this leaves the roadmap

The numbered-listing direction — the `patch-representation` finding's § 6 lead — has now been
**measured and spent**, in both directions the evidence could go: search/replace was NO-GO on
the quoting question, and line-range addressing is NO-GO on the addressing-and-grammar
question. The P2 pivot signal's pre-committed responses that remain untried are **raise *k***
and, on the portability arm, the **CPU dtype** (`docs/ROADMAP.md` § 13; `finding.md:86-92` of
the patch-representation unit). One observation is recorded for whoever designs the next
contract change, and it is the reverse of the diff-contract's: the model's *failure* here is
not transcription of existing text — it is **closing its own replacement blocks and writing
replacement text that parses**. A format that reduces the replacement text's surface (e.g.
whole-function replacement keyed by a name the model can state, where the harness finds the
function's extent) is the kind of change this evidence does not already rule out — a lead, not
a proposal, needing its own finding before any amendment.

**Nothing was built beyond the measurement, and no amendment was made.** The spec, the rule
and this finding stand as committed; the contract aspect and `PREREGISTRATION.md` § 10.17
remain unplanned and unbuilt.