# Spec — `locatability-finding`

**PRD:** `../prd.md` § 4.2 (M4–M7a), R6, OQ1.

## Problem slice

Before building an edit contract that drops line numbers, answer one question over evidence that
already exists: when git refused the pinned base's diff, was the code the model quoted **in the
file** (misplaced — a representation problem) or **not** (invented — no representation fixes it)?

## The rules, fixed here before the classifier runs (OQ1)

**Population.** Every `(candidate, task)` whose journal outcome is `NOT_APPLIED`, for the one
candidate named on the command line. The completion classified is the transcript's **graded**
record for that key (`Transcript.replay()` returns the last record, which is the graded one).

**Lenient hunk walk** over the diff `patch.extract_patch` located in that completion:

- A file section opens at a `--- ` line followed by a `+++ ` line. The path is the `+++` side with
  one leading `b/` stripped; if that side is `/dev/null`, the `---` side with `a/` stripped.
- A hunk opens at any line starting `@@`. Its counts are **ignored**.
- Inside a hunk: a line starting `' '` is context, `'-'` removed, `'+'` added; `\` lines
  (`\ No newline at end of file`) are skipped; **an empty line is read as an empty context line**
  *only when a later line of the same hunk follows it* — a run of empty lines that ends the hunk
  (trailing blank lines before prose, a new header, or the end of the text) is not part of it.
  *(Clarified 2026-09-27 while writing the walk's tests, before any run.)*
  Any other line ends the hunk (and the file section, unless it is a new `@@`/`---`/`diff --git`).
- A hunk's **old side** is its context and removed lines, in order, each without its prefix,
  joined with `"\n"`.

**Per-hunk class**, reading the file's bytes at `base_commit` decoded as UTF-8:

- `NO_FILE` — the path does not exist at `base_commit`, or is absolute, or contains a `..` segment.
- `EMPTY` — the old side is empty (a pure insertion carries no anchor; it cannot be located and it
  cannot be invented). Treated as neutral: it neither makes a rollout `LOCATABLE` nor `INVENTED`.
- `INVENTED` — the old side occurs zero times.
- `AMBIGUOUS` — more than once.
- `LOCATABLE` — exactly once.

**Occurrence is line-aligned and counts overlaps.** The file is split on `"\n"` (nothing else — a
`"\r"` stays part of its line); the old side is split the same way; an occurrence is a start line
from which the old side's lines equal the file's lines exactly and in order. Every start is
counted, so a repeated block that overlaps itself is `AMBIGUOUS`, not `LOCATABLE`. No whitespace
folding, no line-ending normalisation. *(Clarified 2026-09-27, before any run: the earlier wording,
`str.count`, would have matched a quoted line inside a longer one — `a = 1` inside `data = 1` — and
would have missed overlapping repeats.)*

**Per-rollout class** — the worst over its non-`EMPTY` hunks, in the order
`UNCLASSIFIED` > `NO_FILE` > `UNREADABLE` > `INVENTED` > `AMBIGUOUS` > `LOCATABLE`:

- `UNCLASSIFIED` — the task or its checkout was not available, the transcript holds no graded
  record for the key, or a named file is not valid UTF-8 (the question could not be asked, so it
  is not answered as `NO_FILE`). Stays in the denominator.
- `UNREADABLE` — no diff was located, or the walk found no hunk with a non-empty old side.

**`DRIFT` sub-tag** (PRD M5a) — on an `INVENTED` rollout, set when every `INVENTED` hunk's old side
would occur exactly once, by the same line-aligned rule, after normalising every line on both
sides to `" ".join(line.split())` (leading and trailing whitespace dropped, internal runs collapsed
to one space). Reported beside the partition; never moves a
rollout.

**Decision.** `GO` iff `count(LOCATABLE) * 2 > population`; else `NO-GO`. Exit 0 GO, 1 NO-GO,
2 refusal (missing transcript/journal, candidate absent from the journal, empty population).

## In scope

- `src/whetstone/bakeoff/locatability.py` — pure classifier + `main` (`python -m`), modelled on
  `attribution.main`: `--transcript`, `--journal`, `--candidate`, repeatable `--tasks`, `--out`.
  Checkouts are materialised into a temporary directory and read, never written.
- Output JSON, schema `whetstone-locatability/1`: population, per-class counts, `DRIFT` count,
  decision, and one row per rollout (task id, class, drift, per-hunk classes). Sorted keys.
- Run it once over `runs/larger-base-arm-evidence/` for the 32B candidate; breakdown written to
  `runs/patch-representation/locatability-32b.json` (gitignored).
- `docs/planning/patch-representation/finding.md` — the decision and pointers, no model figures
  beyond population size and the decision (one-home rule).

## Out of scope

- Any model call, any network, any write to a checkout or to run evidence.
- Pooling other arms into the population (PRD S1 reports them *beside*, if done).
- Changing these rules after seeing the output. Any change is disclosed in the finding with the
  before/after decision.

## Acceptance criteria

1. Each per-hunk class has a fixture that produces it, including an empty-line-as-context hunk and
   a hunk whose declared counts are wrong but whose body is locatable.
2. Worst-of ordering: a rollout with one `LOCATABLE` and one `INVENTED` hunk is `INVENTED`.
3. `EMPTY` hunks are neutral: an insertion-only rollout is `UNREADABLE`, and an insertion beside a
   located hunk leaves the rollout `LOCATABLE`.
4. A path that is absolute or contains `..` is `NO_FILE` and **no file outside the checkout is
   read** (asserted with a sentinel file outside the checkout).
5. `DRIFT` is set on an indentation-shifted old side, is not set on genuinely absent text, and
   never changes the class.
6. `UNCLASSIFIED` rollouts count in the denominator; the decision over (1 locatable, 1
   unclassified) is `NO-GO`, over (2 locatable, 1 invented) is `GO`, and exactly half is `NO-GO`.
7. Exit codes 0/1/2 per the decision rule; refusals print a reason to stderr and write nothing.
8. Output is byte-identical across two runs and across `PYTHONHASHSEED` values.
9. Only `NOT_APPLIED` journal rows enter the population; a `NOT_SOLVED` row with a diff is ignored.
10. The module imports nothing from `mlx`, `torch`, `run`, `scoring`, and nothing under `verify/`
    or `tasks/` imports it (added to the package's existing import guards).
