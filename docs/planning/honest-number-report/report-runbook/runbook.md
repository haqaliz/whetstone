# Runbook — the honest-number report render (`python -m whetstone.loop.honest_report`)

**Unit:** `honest-number-report` · **Aspect:** `report-runbook` · **Branch:**
`feat/honest-number-report/aliz` · **Worktree:**
`/Users/aliz/dev/at/whetstone/.claude/worktrees/feat-honest-number-report`

The operator's sheet for the report render — the last step of the operator chain
(`docs/ROADMAP.md:652-656`): § 7.3 amendment → baseline spend → night #1 → night #2 → first
gated evaluation → the P4 report → the finding. **The render waits for the first gated
evaluation — two nights precede it**: it consumes the sealed evidence that chain produced —
the § 3 baseline artifact, the promotion record and both checkpoints — and a report rendered
before the gate ran would state a decision nobody made. The night writes one checkpoint per
night that selected something, and the gate compares two.

Every command here is run verbatim. A sheet that disagrees with the code it runs fails after
a night has been spent producing the candidate, so `tests/test_honest_number_runbook_guards.py`
refuses the disagreements first: the flags are checked against `honest_report.build_parser`,
every writable path must be absolute, exactly one worktree may be named, and the sheet must
state the refusals as the refusals they are.

## What the render is

The door reads the sealed baseline artifact fail-closed (`read_baseline_document`), the
promotion record fail-closed (`read_promotion_record`), and re-hashes both checkpoints
(`verify_checkpoint`), then verifies one series: the record's held-out document digest and
the candidate's base identity must each equal the baseline series', and the incumbent must
declare the same base as the candidate. A delta across a changed pinned input is not a delta
(`PREREGISTRATION.md:92-94`), and a **series disagreement is refused by name, nothing
written**.

The report instantiates the **§ 4 shape** (`PREREGISTRATION.md:140-167`): **both sources**
are always published together in the same document; source A per-instance, never a rate;
every rate carries its denominator; the baseline score, the final score, the **delta**,
**`N_baseline`**, **`N_final`** and **coverage** over the held-out split, with the full
provenance block (pinned seeds, model revision, task set, tool versions). A zero or negative
delta is published as plainly as a positive one.

The **decision semantics** are the gate's and the writer's, passed through verbatim — each
decision renders a **defined document**: `promoted` renders the candidate's counts as final;
`rejected` renders the incumbent's as final, with the candidate disclosed beside them as the
rejected attempt; `UNVERIFIED` renders **no headline and no delta** — the decision and both
sides' counts, "no comparison was made", never a delta that reads as a win. Whose counts are
"final" is the gate decision's function, never the renderer's choice.

## Before you run

1. **The render follows the first gated evaluation** — the baseline spend and the two nights
   precede it; the promotion record and both checkpoints exist on disk.
2. **Verify the machinery first** (Step 1 below). A machinery regression must be found
   before the sealed evidence is spent on it.
3. **Declare the inputs.** `--recorded-on` and `--run-id` are typed by the operator and
   written down in the operator's own log; neither is read from a clock or generated.
   `--recorded-on` is an input, never the clock. `<run-id>` is the promotion record's own
   run id — a record whose run id differs from the one named is refused by name
   (`RunIdentityMismatch`).

## Step 1 — verify the machinery on the fixture suites

The door's own suites run the whole path — the promotion-record reader, the writer's § 4
shape and decision semantics, the door's refusals — on fixtures, without the machine. This
costs no GPU and takes a few minutes. **Halt if this is not green**: a red fixture suite
means the door is not the door this sheet describes, and no render it produces on the real
evidence may be recorded.

**Run with CWD at the primary checkout (`/Users/aliz/dev/at/whetstone`):**

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-honest-number-report \
  pytest tests/loop/test_honest_report_door.py tests/bakeoff/test_honest_number_report.py tests/loop/test_promotion_record_n.py -q
```

## Step 2 — the render

**Run with CWD at the primary checkout (`/Users/aliz/dev/at/whetstone`), executing the
branch code via its project:**

```bash
uv run --project /Users/aliz/dev/at/whetstone/.claude/worktrees/feat-honest-number-report \
  python -m whetstone.loop.honest_report \
  --render \
  --baseline /Users/aliz/dev/at/whetstone/reports/baseline-measurement/report.json \
  --record /Users/aliz/dev/at/whetstone/runs/promotions/<run-id>.json \
  --checkpoint-candidate /Users/aliz/dev/at/whetstone/checkpoints/<candidate> \
  --checkpoint-incumbent /Users/aliz/dev/at/whetstone/checkpoints/<incumbent> \
  --heldout /Users/aliz/dev/at/whetstone/tasks/heldout/source-b.json \
  --out /Users/aliz/dev/at/whetstone/reports/honest-number \
  --recorded-on <declared-at-run-time> \
  --run-id <run-id>
```

Every flag verified against the module's own parser (`honest_report.build_parser`) at write
time. Notes on the choices:

- **The evidence pointers are absolute, and the writable home is absolute too** — no part
  of the render depends on CWD.
- **`--heldout` is a pointer the door never parses** (on the comparison.py `--stratum-doc`
  precedent): the series check runs on the documents' own digests, never on this path.
- **A half-truth render is refused by name, nothing written** (exit 2, no fifth code): an
  **unmeasured baseline** (a declaration carries no counts to delta against), a missing or
  unreadable evidence document, a failed checkpoint re-hash, a **series disagreement**, an
  incumbent on a different base than the candidate, a run id that is not the record's, an
  `--out` git cannot see, and a same-series artifact already at `--out` (the measured-once
  posture — the report is a pure function of its sealed evidence, so a second render of the
  same series would be the first render wearing a second date). A **changed** pinned input
  is a legitimate new series, rendered beside it, never refused; a declaration-only artifact
  at `--out` is overwritten, never refused — it carries no series.
- **The report is never re-rendered to be checked.** Re-rendering until the number flatters
  is selecting on the outcome; the render is a pure function of the sealed evidence, and the
  number is stated once, in the finding.

## A killed render

The render resumes nothing — it is re-run from the start. The `--run-id` names the promotion
record's own identity, never an id the render invents: after a killed run, name the **fresh
`--run-id`** the re-run's record carries (`runs/promotions/<run-id>.json`), and a render that
names an id the record does not declare is refused by name (`RunIdentityMismatch`) — nothing
is resumed, and nothing is hand-repaired. If the killed write left a same-series `report.json`
at `--out`, the re-render is refused by the measured-once posture: the artifacts are what
the render left, and the response is the finding, never an edit of the artifacts.

## After the render — the post-run chain

Read, in this order:

1. **The artifacts** — `reports/honest-number/` (`report.md`, `report.json`, `cost.json`,
   schema `whetstone-honest-number/1`): both sources' baseline/final counts, the delta, both
   N's, coverage, the decision, and the full provenance block. Counts and verdicts only —
   no prompt, completion or patch text.
2. **The finding** — the operator's own commit: the rendered artifacts
   (`reports/honest-number/`) are committed with the finding that records the render. The
   finding **states the number** — the number's narrative home is the finding, on the
   baseline runbook's precedent — and **nothing in this sheet is a figure about a model**.