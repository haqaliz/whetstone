# `tasks/` — the corpus, and which half of it is committed

This directory holds the tasks the verifier is pointed at. **Half of it is deliberately absent
from this repository**, and this file exists so that absence reads as a design decision rather
than as a gap or a cherry-pick. If you came here wondering where the other tasks are, this is
the answer.

Nothing here is populated yet: ingestion is the slice being built. The layout and its rules land
first, because a corpus directory whose rules are decided after the data arrives is a corpus
directory whose rules are decided by the data.

---

## The layout

```
tasks/
├── README.md                   # this file
├── public/                     # COMMITTED — source A, public benchmark instances
│   ├── pool.json               # the fetch output, with a provenance header
│   ├── selected.json           # the seeded, offline, reproducible draw
│   ├── ineligible.json         # the rejection ledger: instance -> the gate that rejected it
│   └── instances/<id>.json     # one task manifest per eligible instance
├── recipes/                    # COMMITTED — HOW source B is mined, never WHAT it produced
│   └── <donor>.json            # donor repository, filters, tool versions, mining date
├── local-ledger.json           # COMMITTED — the source-B liveness record (see below)
└── local/                      # GITIGNORED — source B, the user's own code, never committed
    └── <donor>/<id>.json
```

Two sources feed the corpus. **Source A** is public benchmark data: anyone can fetch the same
instances and check our manifests against them. **Source B** is mined from the user's own
repositories — real red→green commits from real projects, which is the whole point of a system
that improves a model on *your* tasks, and is also code that must never leave the machine.

---

## The tension this resolves

Two documents in this repository disagree, and the disagreement is real rather than a wording
slip:

- **`docs/ROADMAP.md:244`** requires that `tasks/` hold instances from **both** sources, with
  **committed provenance** — so that a published number rests on a corpus a reader can audit.
- **`.gitignore:16-24`** pre-declares `/tasks/local/` as *"the user's own data [that] never
  belongs in the repo"*, following CLAUDE.md's **no data egress** guardrail: the loop and the
  user's data stay local.

Both cannot be literally true of source B. Committing the mined instances would ship the user's
source code — their tests, their diffs, their file paths — into a public repository. Committing
nothing would leave the headline source unauditable, which is the same shape of hole this
project exists to refuse: *"trust us, the other half was fine."*

## The resolution

**Source B's committed artifact is the recipe and the liveness ledger, never the mined
instances.**

- **The recipe** (`recipes/<donor>.json`) records how the corpus was derived: which donor
  repository, which filters and eligibility gates, which tool and interpreter versions, and
  when. It is the procedure, not the output.
- **The liveness ledger** (`local-ledger.json`) records, for every mined task, that it was
  *proven live*: its `task_id`, a **hash of its manifest** rather than the manifest itself, the
  two verdicts that prove the task discriminates (empty patch → FAIL, reference patch → PASS),
  that the executed node-id set equalled the declared one, the skip count, and the versions and
  date behind those runs.

What that buys a reader who has none of the data: they can check that **every** claimed
source-B task was proven live rather than assumed, they can count them, and they can **re-derive
the corpus themselves** from the committed recipe against their own copy of the donor and
compare the result. The evidence is committed; the user's code is not.

What it does not buy them: reproducing *our* instances byte-for-byte. That is the honest cost of
locality, and it is why source A — fully committed and externally checkable — is not optional
padding but the half that keeps the whole number auditable.

---

## What may and may not be committed here

| Path | Committed? | Why |
|---|---|---|
| `public/**` | **Yes** | Public benchmark data. A corpus nobody can inspect cannot support a published number |
| `recipes/**` | **Yes** | A procedure, not the user's code. It is what makes source B re-derivable |
| `local-ledger.json` | **Yes** | Hashes and verdicts only — evidence about the data, never the data |
| `local/**` | **Never** | The user's own source, tests and paths. `.gitignore` enforces this; `tests/test_tasks_layout.py` asserts git's own answer, in both directions |

Before adding anything to this directory, ask the question the table encodes: *does this file
contain the user's code, or evidence about it?* Evidence is committed. Code is not. A file that
contains a little of both is not a borderline case — it is the user's code.

**`local/` is not a staging area.** Nothing is moved from it into a committed directory later.
If a source-B task is worth publishing, it is re-derived from the recipe against a donor whose
owner published it.
