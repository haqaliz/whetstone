# Finding — the pinned base's refused diffs mostly do not quote the file exactly: NO-GO

**Slice:** `patch-representation` / `locatability-finding` · **Written:** 2026-09-27, after the
classifier ran once over stored evidence. **Instrument:** `src/whetstone/bakeoff/locatability.py`
(offline, deterministic, stdlib-only, no model). **Rules:** `locatability-finding/spec.md`, fixed
before the run; its three clarifications are each a separate commit dated before the run, and none
followed it. **Local evidence (the only home of every count):** `runs/patch-representation/`
(gitignored).

## 1. The decision

**NO-GO.** The pre-committed rule — GO iff more than half of the population is `LOCATABLE` — does
not hold for `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` over its **37** refused rollouts in
`runs/larger-base-arm-evidence/`. The command exited 1. The population equals the arm's own
`patch apply` count in `reports/larger-base/report.md`, which is the check that the journal, the
transcript and the corpus were joined correctly; every rollout in it was classified, none left
`UNCLASSIFIED`.

By `prd.md` § 4.2 (M7), the unit therefore ships the reason field (`not-applied-detail`) and this
finding, and **does not build** the search/replace contract (§ 4.3) or its amendment (§ 4.4). The
D3 refusals in `p2-yield-probe/prd.md` and `p2-format-hardening/prd.md` stand — now on a
measurement rather than on the withdrawal's partly wrong premise (`prd.md` § 1).

## 2. What the refusals quote, in words

The partition's counts live in `runs/patch-representation/locatability-32b.json`. In words: a
minority of refused rollouts quote the file exactly; the majority carry at least one hunk whose
quoted text is not a contiguous run of the file's lines.

A hand-check read every `INVENTED` hunk line by line (script and tally beside the partition, in
`runs/patch-representation/handcheck-32b-invented.{py,json}`). It was run **after** the decision
and moves nothing; it exists to confirm the classifier matched the spec and to say what "invented"
consisted of:

- **It is not a reading artefact.** No invented hunk is explained by whitespace on the file's
  blank lines — the one place the lenient walk's empty-line rule could have manufactured a miss.
- **About half of the invented hunks quote only real lines — with lines left out.** Every quoted
  line exists in the file, in order, but the model skipped lines between them. A unified diff
  cannot express that, and **neither can an exact search/replace block**: its anchor must be a
  contiguous run too.
- **The rest contain lines that exist nowhere as written**: indentation shifted by a level (the
  `DRIFT` tag catches the rollouts where that is the only fault), a statement paraphrased, or —
  repeatedly — the model's *own edited version* quoted as the old text (a `.resolve()` already
  added to the line it claims to be replacing).

So the model is mostly quoting code *near* the file rather than inventing code from nothing. That
is a real lead, and it is exactly the case the exact-match contract (M10) was designed to refuse:
every route from "near" to "applied" requires the harness to decide which real lines the model
meant, which is the harness choosing the model's answer for it.

## 3. Corroboration, beside and never pooled (PRD S1)

The same command over `runs/format-hardening-arm-evidence/` for the 14B and 3B MLX bases also
exits NO-GO, each over a population equal to its report's `patch apply` count
(`reports/format-hardening/report.md`). Counts in
`runs/patch-representation/locatability-format-hardening-{14B,3B}.json`. The 3B's largest class
is diffs naming files that do not exist, a different failure from the 32B's. None of
this enters the 32B decision; it says only that the decision is not a quirk of one base.

Night-006 (3B, torch/CPU, x131) is not classified: its transcripts are not on this machine. The
command accepts its evidence unchanged whenever they are.

## 4. Disclosures

1. **The measurement is a proxy** (`prd.md` R6). It classifies text written under the *diff*
   prompt. Under a search/replace prompt the model would write different text. NO-GO says the
   necessary condition — the model quoting the file exactly when it tried — mostly did not hold; it
   does not prove a search/replace night would yield nothing.
2. **One arm, one base, one run.** The population is small, and the rule is a go/no-go for building
   a contract, never a claim about the base's ability.
3. **The public task needed a flag the plan left out.** The first run omitted
   `tasks/public/instances` and left `pallets__flask-4045` `UNCLASSIFIED`; the re-run offered it.
   The decision was NO-GO both times and could not have changed (one rollout of 37).
4. **The hand-check's categories are not the spec's.** They were chosen after the decision to
   describe it, which is why they are reported in words and never as a rule.

## 5. What is not claimed

- That search/replace cannot help — **unproven**; see disclosure 1.
- That the base cannot fix bugs — **unproven**; refusals are upstream of any grade.
- That a looser match would raise yield — **not tested, and not proposed**: forgiving elided lines
  or indentation is the harness guessing, which `prd.md` M10 forbids by name.

## 6. Where this leaves the roadmap

The P2 pivot signal's pre-committed responses that remain untried are **raise *k*** and, on the
portability arm, the CPU dtype (`docs/ROADMAP.md` § 13). This finding adds one named lead for
whoever designs the next contract change: **the model's quotes are near-misses of contiguity and
of its own edits, not fabrications** — a representation that never asks the model to quote
existing code at all (e.g. line-range addressing against a numbered source listing) is the kind of
change this evidence does not already rule out. It is a lead, not a proposal, and it would need its
own finding before any amendment.
