# PRD — patch representation

**Slug:** `patch-representation` · **Branch:** `feat/patch-representation/aliz` · **Written:** 2026-09-27
**Sources:** `docs/planning/_card/issue.md` (inline brief + GitHub #64), `understanding.md` (this
directory). **Roadmap position:** M1 of `docs/ROADMAP.md` § 14 as proposed in open PR #66; P2's
pivot signal (`docs/ROADMAP.md` § 13). **Core-loop element:** ② the nightly improvement loop — the
generation contract that produces rollouts. It touches ① only at the seam where an edit becomes
the patch STRICT grades, and ① itself does not change.

No figure about a model is stated in this document. Each is pointed at its one home.

---

## 1. Problem statement

A night trains only on strict-`PASS` rollouts, and five nights across three base sizes selected
none (`docs/STATUS.md`; `docs/ROADMAP.md` § 13). The largest single cause of a rollout never being
graded is that **git refuses the diff the model wrote**. On the pinned base
(`mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`, § 10.10) every refusal in the larger-base arm
falls into one of three shapes — a well-formed diff whose context git would not match, a hunk whose
header declares counts its body does not satisfy, and a hunk body that stops on a line the diff
grammar rejects (`runs/diff-autopsy/larger-base-arm-evidence.json`, gitignored; the arm's report is
`reports/larger-base/report.md`). Night-006 on the portability arm shows the same pattern at larger
scale (GitHub #64).

All three shapes are artefacts of the **unified-diff representation**: its line-number arithmetic,
its hunk counts, its per-line prefix grammar. The contract has been varied three ways — retry
augmentation, base size, task difficulty — and never along this axis.

**What is not yet known, and is the first thing this unit measures:** whether the model's quoted
code is *misplaced* (right text, wrong position or wrong framing — a representation problem) or
*invented* (text that is not in the file — a problem no representation fixes). A representation
without line numbers still requires the model to quote existing code exactly.

**Search/replace was withdrawn once, and this PRD re-opens it on stated grounds.**
`p2-yield-probe/prd.md` (correction of 2026-08-05) withdrew D3 because failures were
"overwhelmingly *git would not read this diff*", which it held search/replace does not address.
The diff-autopsy that ran afterwards (`p2-diff-autopsy/finding.md` § 2) found that one of the
principal unreadable shapes is **hunk counts the body does not satisfy** — removed entirely by a
headerless format. The withdrawal was right about chat-template loops and stacked fences, which no
format fixes; it was wrong to place every `WOULD_NOT_PARSE` among them. `p2-format-hardening/prd.md`
then refused search/replace by name on the strength of that withdrawal. This PRD supersedes both
refusals **only if** § 4.2's pre-committed rule says go.

## 2. Goals and success metrics

| Goal | Measured by | Home of the figure |
|---|---|---|
| G1 — every `NOT_APPLIED` states why | `Rollout.detail` non-empty on every `NOT_APPLIED` record | test suite |
| G2 — answer *misplaced or invented* before building anything | locatability partition over the pinned base's refused rollouts | gitignored `runs/patch-representation/`; a committed finding states the decision, not the count |
| G3 — an alternative edit contract that cannot widen the cheat surface | adversarial tests in § 6 all pass | test suite |
| G4 — the contract is pinned before any night uses it | `PREREGISTRATION.md` § 10.16 merged before any night records `edit_format = search-replace` | git history |

**No yield target is set.** This unit does not claim, predict or target any strict-`PASS` count.
Whether the new contract produces training data is the question the *next* night answers, under
§ 10.16, in its own non-comparable home.

## 3. User and scenario

The founder-operator running nights, and behind them the ICP: an engineer who wants a model
measurably better at their own tasks by morning, privately, and will not trust a gain they cannot
check. Today that engineer's night ends with an empty training set and a report in which most
rollouts say only "git refused it". After this unit: every refusal names its cause, and the
operator can run a night under a representation that is designed to remove the arithmetic the
model keeps getting wrong — with the verifier byte-for-byte unchanged.

## 4. Requirements

### 4.1 Must — `NOT_APPLIED` carries a reason (aspect `not-applied-detail`)

- M1. When STRICT's sole verdict is `patch-apply`, `scoring._verify` records that verdict's
  `message` in `Rollout.detail`. Today it is dropped (`scoring.py:499-509`).
- M2. No other outcome's `detail` changes; no verdict, status or outcome changes.
- M3. The journal already encodes `detail`; a replayed record round-trips it.

### 4.2 Must — the locatability measurement and its pre-committed rule (aspect `locatability-finding`)

- M4. An offline, stdlib-only, deterministic classifier over stored transcripts + journals (no
  model, no network, off the reward path — same boundary as `attribution.py`/`autopsy.py`). For
  each rollout whose outcome is `NOT_APPLIED`, it reads the transcript record with
  `decision == "graded"` — the larger-base arm ran with retry budget 2, so the first attempt is not
  necessarily the one STRICT saw — and walks the extracted diff's hunks **leniently**
  (hunk counts ignored; a bare empty line inside a hunk read as an empty context line; any other
  unprefixed line ends the hunk — rules stated in the module and tested), takes each hunk's
  old-side text (context + removed lines), and reads the named file at the task's `base_commit`.
- M5. Each rollout gets exactly one class, the **worst** across its hunks, in this order:
  `NO_FILE` (a named path does not exist at `base_commit`) → `UNREADABLE` (no hunk could be walked)
  → `INVENTED` (an old side occurs zero times) → `AMBIGUOUS` (occurs more than once) →
  `LOCATABLE` (every old side occurs exactly once). A rollout the classifier cannot reach (task or
  donor missing) is `UNCLASSIFIED` and **stays in the denominator**.
- M5a. **Whitespace drift is reported, never forgiven.** An `INVENTED` rollout whose every old side
  *would* occur exactly once after folding runs of whitespace and ignoring leading indentation is
  additionally tagged `DRIFT`. The tag is a sub-count reported beside the partition; it never moves
  a rollout into `LOCATABLE`, because M10 forbids the converter the same folding. A finding
  dominated by `DRIFT` is a NO-GO for this format and a named lead for the next decision.
  (Decided at the review gate, 2026-09-27.)
- M6. **The decision rule, fixed here, before the measurement runs:** population = every
  `NOT_APPLIED` rollout of `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` in
  `runs/larger-base-arm-evidence/`. **GO iff `LOCATABLE` > half the population; otherwise NO-GO.**
  The rule is exposed as a command exit (0 go, 1 no-go, 2 refusal), mirroring `check-probe`.
- M7. Output: a gitignored breakdown under `runs/patch-representation/` (the figures' only home)
  and a committed `docs/planning/patch-representation/finding.md` stating the decision and pointing
  at the breakdown. On NO-GO the unit ships § 4.1 and § 4.2 only, and § 4.3–4.4 are not built.
- M7a. **The operator sees the finding before § 4.3 starts.** The command exit decides; a human
  reads the finding at a checkpoint before any contract code is written. The checkpoint can stop a
  GO; it cannot turn a NO-GO into a GO.

### 4.3 Must, on GO — the search/replace contract (aspect `search-replace-contract`)

- M8. **Format.** One or more blocks, each: a path line (relative to the repository root), then
  `<<<<<<< SEARCH`, the exact existing text, `=======`, the replacement, `>>>>>>> REPLACE`. Blocks
  may sit inside a fence. The prompt's response-format section states this and nothing else about
  editing; the rest of the prompt is byte-identical to the diff contract's.
- M9. **Parsing never repairs.** A malformed block (missing marker, missing path) makes the rollout
  `NO_DIFF` with a named reason, exactly as an unfound diff does today. No block is ever dropped
  while others proceed.
- M10. **Location is exact.** Each SEARCH text must occur **exactly once** in the file's contents at
  `base_commit`, compared byte-for-byte after nothing but the model's own text — no whitespace
  folding, no fuzzy match, no line-ending normalisation. Located spans on one file must not overlap.
- M11. **Empty SEARCH** is accepted only when the path does not exist at `base_commit` (file
  creation). An empty SEARCH on an existing file is refused — it is an insert-anywhere hole.
- M12. **All or nothing.** If any block on any non-held path fails M10/M11, no diff is produced and
  the rollout is recorded under a new outcome, `NOT_LOCATED`, with a `detail` naming the path, the
  block's index and the reason (`absent`, `ambiguous: N matches`, `overlaps block K`,
  `empty search on existing file`, `no such file`). STRICT is not entered.
- M13. **Scope before location — the rule that keeps `N` honest.** A block naming a path in
  `task.test_blobs` is **never** refused by the converter, whatever its anchor. The rollout is
  converted to a diff that names the held path (a located block rendered normally; an unlocated one
  rendered as a hunk anchored at line 1 whose old side is the SEARCH text) and handed to STRICT, whose
  pre-apply scope check refuses it as `patch-scope`. This works because STRICT's early path read is
  `git apply --numstat`, which parses without checking context (`verify/repo.py:87-110`); the
  rendered hunk must therefore be *grammatical*, and a test asserts `numstat` names the held path
  for the line-1 rendering. A held path absent at `base_commit` is rendered as a new file. The outcome is `OUT_OF_SCOPE` and it is counted
  as a caught attempt, **because STRICT said so** — the converter never labels scope itself. This
  mirrors STRICT's own order (`strict.py`: declared paths → held check → apply).
- M14. **Conversion** produces a unified diff (`--- a/<path>` / `+++ b/<path>`, three lines of
  context, files in first-appearance order, git's `\ No newline at end of file` marker where the old
  or new content lacks a final newline) that `git apply --check` accepts against the base checkout
  whenever every block located. Pure function of (blocks, file contents); byte-identical across
  processes and hash seeds.
- M15. **The reward path is untouched.** Nothing under `verify/` or `tasks/` changes or imports the
  new modules; the existing AST guard and the package's one-way import test cover them.
- M16. **Selector.** An explicit edit-format field, `diff` (default, unchanged behaviour,
  byte-identical prompts) or `search-replace`, on both the night and the bake-off drivers. The
  night's ledger and the bake-off's provenance block record it. `extractor_version` becomes a digest
  over every module the selected contract's extraction path executes, so it moves when the
  converter moves.
- M17. **Retry budget is 0 under `search-replace`.** The existing triggers diagnose diff grammar;
  a driver asked for `search-replace` with a non-zero retry budget refuses to start.
- M18. `NOT_LOCATED` is added to every consumer that partitions outcomes — `report.py`, `gate.py`,
  `honest_report.py`, the morning report — as a not-solved, **covered** outcome (the model answered
  and was wrong; it is not `UNVERIFIED`, and it is never a win). An exhaustiveness test fails if a
  future `Outcome` member is not placed.

### 4.4 Must, on GO — the amendment (aspect `amendment-10-16`)

- M19. `PREREGISTRATION.md` § 10.16, **Type 1 (§ 8.1)**, committed before any night records
  `edit_format = search-replace`: it pins the edit format, the prompt template SHA-256, the extractor
  version, retry budget 0, and names the non-comparable home `reports/search-replace/` (declaration
  only until a night runs). It states that figures under it are comparable to nothing prior, sets no
  threshold, and points at § 4.2's finding for why it exists.
- M20. `docs/ROADMAP.md` records that the D3 refusals in `p2-yield-probe` and `p2-format-hardening`
  are superseded, and on what evidence; `docs/STATUS.md` gets its entry in the same commit as the
  capability (repository rule: claim and code arrive together).

### Should

- S1. The locatability classifier also runs over `runs/format-hardening-arm-evidence/` (14B, 3B)
  as corroboration, reported beside — never pooled into — M6's population.
- S2. The classifier accepts night draw directories (`runs/nights/<id>/draws/`), so night-006 can
  be classified once its transcripts are on this machine.

### Nice

- N1. A search/replace-specific retry vocabulary. Explicitly deferred (§ 7).

## 5. Technical considerations

- **Where it plugs in** — `understanding.md` § 4. The converter sits between extraction and
  `_verify` in `scoring.score`; the prompt change is confined to `rendering._RESPONSE_FORMAT`'s
  counterpart; both drivers (`loop/draws.py`, `bakeoff/run.py`) thread the selector.
- **Reading files at `base_commit`** happens in the harness, off the reward path, read-only, from
  the same repository `sources.oracle_sources` reads. Held test contents may be *read by the
  harness* to render M13's diff; they are never rendered into a prompt (`rendering.HeldTestInSources`
  is unchanged).
- **`patch.py`'s doctrine — "locate a diff; never author one" — is amended, not broken.** The
  doctrine exists so the harness can never strip or redirect a hunk aimed at a held test. Under
  `search-replace` the harness *does* author the diff, and the doctrine's purpose is carried by
  M9 (never repair), M12 (all or nothing), M13 (scope before location) and M14 (path-preserving).
  The new module's docstring says this in those words; `patch.py` is not edited.
- **Determinism** — `difflib` output is deterministic, but its handling of missing final newlines
  is not git's; M14's marker handling is the known sharp edge and gets its own fixtures.
- **Reward-hacking surface (explicit).** The converter is a new door between policy text and the
  reward. What STRICT receives is still a unified diff that STRICT re-executes against the
  operator's restored tests; nothing the converter does can make STRICT return `PASS` for a patch
  it would not pass as a diff. The new risks are all *conversion* risks (§ 6).
- **Promotion-gate impact.** None to the gate's rule. `NOT_LOCATED` is a covered not-solved outcome;
  `UNVERIFIED` semantics, `R`, and the promote condition are unchanged.

## 6. Risks and open questions

- **R1 (reward-hacking) — a held-path attempt escapes `N`.** Closed by M13; test: a garbage anchor
  on a held path records `OUT_OF_SCOPE` with `verdict_kinds == ("patch-scope",)`.
- **R2 (reward-hacking) — insert-anywhere.** Closed by M11; test: empty SEARCH on an existing file
  is `NOT_LOCATED`, never applied.
- **R3 (reward-hacking) — the harness chooses among matches.** Closed by M10; test: a two-match
  anchor is `NOT_LOCATED: ambiguous`, never the first match.
- **R4 (reward-hacking) — path escape.** Absolute paths, `..` segments, and symlinked paths that
  resolve outside the checkout are `NOT_LOCATED: no such file`, never read from the host.
- **R5 — the finding says NO-GO.** Then the representation is not the wall, and that is a result:
  the unit ships the reason field and the finding, and the roadmap's remaining responses (raise *k*;
  CPU dtype) are what's left. Not a failure of this unit.
- **R6 — the population is small, and the measurement is a proxy.** One arm on one base. And it
  classifies text the model wrote *under the diff prompt*; under a search/replace prompt the model
  writes different text. LOCATABLE says the model *could* quote the file when it tried — a
  necessary condition for the new contract to help, not a prediction that it will. The rule is a
  go/no-go for building, never a claim about yield; the finding says both and states the
  population size.
- **R8 — the ripple is the cost.** Adding `NOT_LOCATED` touches every outcome partition (M18);
  that, not the converter, is most of § 4.3's effort. Rough shape: `not-applied-detail` small;
  `locatability-finding` medium; `search-replace-contract` the largest (parser + converter +
  outcome ripple + two drivers); `amendment-10-16` small.
- **R7 — night-006 is unreachable from this machine** (`ssh x131` refused). S2 makes it classifiable
  later; the decision does not wait for it.
- **OQ1** — the lenient walk's exact rules (M4) decide `UNREADABLE` vs `INVENTED` at the margin;
  they are fixed in the spec before the classifier runs, and any change after is disclosed.

## 7. Out of scope

- Running a night under `search-replace` — the next unit, under § 10.16.
- Any change under `verify/` or `tasks/`; any change to STRICT, WEAK, the gate rule or `R`.
- Fuzzy, whitespace-tolerant or "best match" location; whole-function or whole-file formats.
- A search/replace retry vocabulary (N1).
- The held-out set (#60, #62) and publication (M2, M3 of PR #66).
- Raising *k*, CPU dtype, and any base change.

## 8. Aspects

| Aspect | Boundary | Depends on |
|---|---|---|
| `not-applied-detail` | § 4.1 — git's message reaches `Rollout.detail` | — |
| `locatability-finding` | § 4.2 — classifier, command exit, run, finding | `not-applied-detail` not required (reads transcripts) |
| `search-replace-contract` | § 4.3 — format, parser, converter, `NOT_LOCATED`, selector, drivers | GO from `locatability-finding` |
| `amendment-10-16` | § 4.4 — § 10.16, ROADMAP/STATUS | `search-replace-contract` |
