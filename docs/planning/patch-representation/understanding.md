# Understanding — patch representation

**Written:** 2026-09-27, Phase 2 of `wbf feat patch-representation`. Source: `docs/planning/_card/issue.md`
(the inline brief, plus GitHub #64 dumped verbatim). Numbers about a model are not restated here;
each is pointed at its one home.

## 1. What the work is really asking

Every night so far has selected zero or near-zero strict-`PASS` rollouts, and the tail of that
failure is at patch application: the base writes a unified diff and git refuses it. The
generation contract has been varied along three axes — the retry augmentation
(`reports/format-hardening/`), the base (`reports/larger-base/`), the task set
(`reports/easier-stratum/`) — and **never along the one that produces the refusal: the edit
representation itself.** The work asks two questions in order:

1. **Would a different representation convert those refusals, or only move them?** A format
   without hunk headers and line prefixes removes *count arithmetic* and *line grammar*. It does
   not remove the need to quote existing code exactly. If the model's context lines are invented
   rather than misplaced, search/replace fails the same way under a different name.
2. **If yes, ship the representation** as a pinned, amendment-governed generation contract, with
   the verifier untouched.

## 2. The evidence, and where each figure lives

- **Night-006 (3B, torch/CPU, x131)** — GitHub #64. Its transcripts are on x131 only; this machine
  cannot reach x131 (`ssh` refused, no key). Not usable for slice 1 from here.
- **The larger-base arm (the pinned 32B MLX base, § 10.10)** — its transcripts are local
  (`runs/larger-base-arm-evidence/transcript.jsonl`, gitignored), its report is
  `reports/larger-base/report.md`, and its fine-cause partition already exists at
  `runs/diff-autopsy/larger-base-arm-evidence.json`. Every refusal there falls into one of three
  shapes: well-formed-but-refused, hunk-count-mismatch, hunk-dies-early. **This is the better
  evidence for slice 1**: it is the base the headline series fine-tunes, on the runtime the
  headline night uses.
- **The format-hardening arm (3B/7B/14B MLX)** — local, partitioned at
  `runs/diff-autopsy/format-hardening-arm-evidence.json`. The 7B's failures are a chat-template
  loop no representation addresses; the 14B's are dominated by hunk-count-mismatch.

## 3. Contradictions to surface, not paper over

**C1 — Search/replace was withdrawn once, and the withdrawal's reasoning is partly wrong.**
`p2-yield-probe/prd.md` (the 2026-08-05 correction) withdrew D3 because failures were
"overwhelmingly *git would not read this diff*", "only the second of which search/replace
addresses". But the diff-autopsy (`p2-diff-autopsy/finding.md` § 2), which ran *after* that
withdrawal, names one of the unreadable shapes as **hunk headers declaring counts the bodies do
not satisfy** — which is exactly what a headerless format removes. The withdrawal was right that
loops and stacked fences are untouched by a format change; it was wrong to put every
`WOULD_NOT_PARSE` in that category. `p2-format-hardening/prd.md:324` then refused search/replace
*by name*, citing the withdrawal. The PRD must re-open D3 by stating which part of its premise the
autopsy falsified — not quietly bring it back.

**C2 — `patch.py`'s rule is "locate a diff; never author one."** A search/replace block converted
to a unified diff *is* the harness authoring a diff. The rule exists so the harness can never
strip or redirect a hunk aimed at an operator-held test (converting a caught cheat into an
uncaught one). The rule's *purpose* survives if the conversion is **path-preserving and
total-or-nothing**: every block becomes a hunk on exactly the path it named, a block on a held
path reaches STRICT as a diff on that held path (so `patch-scope` still refuses it and `N` still
counts it), and a block that cannot be located fails the whole rollout rather than being dropped.
The PRD must state this as an amendment of `patch.py`'s doctrine, not a violation of it.

**C3 — `NOT_APPLIED` records no reason.** `scoring.Rollout.detail` is documented as *"empty when
the verifier ran and its own verdicts are the explanation"* (`scoring.py:186-188`), and
`scoring._verify` copies only each verdict's `kind` — the `patch-apply` verdict's `message`
(`PatchError` wrapping git's own report, `verify/repo.py:100,118` via `strict.py:171-183`) never
reaches the record. The journal would persist it (`journal.py` encodes `detail`); nothing puts it
there. So the reason exists at runtime and is thrown away. Fixing it is
small, independent of any representation, and is what makes slice 1 repeatable for future nights.

**C4 — The brief names night-006; local evidence is the 32B arm.** Stated in § 2. Night-006 can
be added once x131 is reachable; it is corroboration, not the primary evidence.

## 4. Affected code

| Step | Where | Today |
|---|---|---|
| Prompt contract | `bakeoff/rendering.py` `_RESPONSE_FORMAT` | demands one fenced unified diff |
| Extract | `bakeoff/patch.py` `extract_patch` | locates a diff, never authors one |
| Score | `bakeoff/scoring.py` `score` → `_verify` | extract → STRICT → WEAK |
| Night | `loop/draws.py` (calls `score`), `loop/night.py:665` (`extractor_version`) | |
| Bake-off | `bakeoff/run.py:1133` `_extractor_version` — digest of the extraction module's source | |
| Retry | `bakeoff/retry.py` + `diffcheck.py` — triggers are *diff-grammar* diagnoses | |
| Attribution | `bakeoff/attribution.py`, `autopsy.py` — offline, transcript-in | |
| Reward | `verify/strict.py` — **not touched** | |

## 5. Guardrails, stated for this unit

- **The reward stays execution-grounded, unchanged.** STRICT still receives a unified diff and
  re-executes the operator's tests; no module under `verify/` or `tasks/` changes. What changes is
  how the model *expresses* an edit, upstream of the reward.
- **The conversion is a new cheat surface and must be tested as one.** Adversarial cases: a block
  on a held test path (must reach STRICT and be refused as `patch-scope`, never dropped); a block
  on a path outside the repository or absolute; an anchor matching zero or several times; an
  empty anchor (an append-anywhere hole); overlapping blocks on one file.
- **`UNVERIFIED` is untouched.** A block that cannot be converted is the model's failure
  (a wrong answer, like an unappliable diff), never `UNVERIFIED`; nothing here can make a
  rollout count as a win that STRICT did not pass.
- **Comparability.** A new representation changes `prompt_sha256` and the extractor version, so
  it is a Type 1 amendment (§ 8.1) committed before any night uses it, and its figures get their
  own non-comparable home.

## 6. Open questions for the interview

1. **Which representation** — search/replace blocks, or whole-function replacement? (Whole-*file*
   rewrite is out: `sources.py`'s 80,000-char budget.)
2. **Where does a failed conversion land** — `NOT_APPLIED` with a named `detail`, or a new
   `Outcome` member? A new member ripples through `report.py`, `gate.py`, `honest_report.py`.
3. **Retry under the new format** — budget 0 (one input moved at a time), or a new diagnosis
   vocabulary? The existing triggers are diff-grammar diagnoses and do not apply.
4. **Which night tests it**, and on which runtime — the pinned 32B MLX base on this Mac, or the
   portability arm on x131? Is the night itself in this unit's scope, or only the amendment?
5. **Slice 1's go/no-go rule** — what share of refusals must have locatable context for slice 2
   to proceed? It must be fixed *before* slice 1 runs, or it is a threshold chosen after seeing
   the number.
