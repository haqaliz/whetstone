# `tasks/` — the corpus, and which half of it is committed

This directory holds the tasks the verifier is pointed at. **Half of it is deliberately absent
from this repository**, and this file exists so that absence reads as a design decision rather
than as a gap or a cherry-pick. If you came here wondering where the other tasks are, this is
the answer.

**Both sources are populated.** Source B carries **66 tasks** — 45 mined from `contig`, 21 from
`belay` — every one of them *proven live* before it was kept. None of those 66 files is in this
repository and none ever will be; what is committed is the evidence about them, which is the
subject of most of this document.

Source A carries one. **Of SWE-bench-Lite's 300 instances, exactly one is eligible** —
`pallets__flask-4045` — and `ineligible.json` records all 299 refusals with the gate that made
each one. That is not a placeholder: it is the honest yield of a filter that proves eligibility
per instance instead of assuming it, and the funnel below is the deliverable. **One instance is
not a public benchmark set**, and nothing downstream may quote it as one.

| Stage | Refused | Why |
|---|---:|---|
| format | 192 | django declares its tests in its own unittest runner's form, sympy declares bare names with no file path. Neither is addressable by pytest |
| environment | 106 | no era-pins have been determined by hand for them. A repository declares ranges, so nothing in the dataset answers which versions its era used, and resolving at filter time would decide the verdict by the calendar |
| collectability | 1 | `pallets__flask-5063`: two of the node ids SWE-bench itself declares for it are truncated mid-parameter, so pytest exits 4 |
| liveness | 0 | nothing reached this gate and failed it |
| **eligible** | **1** | `pallets__flask-4045` — STRICT PASS, 52 declared node ids, executed == declared, zero skips |

**106 of those refusals are ours to reduce, and the way to reduce them is by hand.** Each needs
an era-correct install set determined one incident at a time and added to `era-pins.json` with
how it was determined. That is the honest cost of a pinned corpus, and it is why the number is
one rather than an estimate.

---

## The layout

```
tasks/
├── README.md                   # this file
├── public/                     # COMMITTED — source A, public benchmark instances
│   ├── pool.json               # the fetch output, with a provenance header
│   ├── era-pins.json           # HAND-DETERMINED install sets, one per instance (an INPUT)
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

- **`docs/ROADMAP.md` § 4, P1 exit criterion 4** requires that `tasks/` hold instances from
  **both** sources, with **committed provenance** — so that a published number rests on a corpus
  a reader can audit.
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
| `public/era-pins.json` | **Yes** | An *input*, not an output: versions found by hand, with how each set was determined. Without it every instance is refused at gate 3, which is the correct behaviour and not a useful corpus |
| `recipes/**` | **Yes** | A procedure, not the user's code. It is what makes source B re-derivable |
| `local-ledger.json` | **Yes** | Hashes and verdicts only — evidence about the data, never the data |
| `local/**` | **Never** | The user's own source, tests and paths. `.gitignore` enforces this; `tests/test_tasks_layout.py` asserts git's own answer, in both directions |

Before adding anything to this directory, ask the question the table encodes: *does this file
contain the user's code, or evidence about it?* Evidence is committed. Code is not. A file that
contains a little of both is not a borderline case — it is the user's code.

**`local/` is not a staging area.** Nothing is moved from it into a committed directory later.
If a source-B task is worth publishing, it is re-derived from the recipe against a donor whose
owner published it.


---

## How source A is produced

Two **human-run** steps, in order. Both touch the network, and that is why neither is a
`whetstone` subcommand — every subcommand the CLI advertises claims to be offline, and a
networked one would make that claim conditional on which flag was passed. Their **output** is
committed, and everything else — the whole test suite included — reads only the output.

```
python -m whetstone.tasks.fetch     # SWE-bench-Lite -> public/pool.json  (no row filter)
python -m whetstone.tasks.public    # pool -> four gates -> instances/ + ineligible.json
```

The four gates are numbered as the PRD defines them and **execute** in the order
`format, environment, collectability, liveness`, which the ledger records. Proving an id
collectable in the real checkout requires the checkout to be importable, and that is the
environment gate's answer; run before it, the collectability gate would refuse every instance for
a reason that has nothing to do with its ids.

To re-prove a single instance without spending the whole funnel again:

```
python -m whetstone.tasks.public --only pallets__flask-4045
```

Note that `--only` narrows the ledger's denominator to exactly what was run, which is why the
ledger records that denominator rather than assuming 300.

---

## How source B is produced

One command per donor, offline, reading the donor and never writing to it:

```
uv run whetstone mine --donor <path> --out tasks/local/<donor>/ --limit <n> --seed 1
```

It enumerates commits that take an **existing** test from red to green, mints a manifest for
each, and — the part that matters — **proves every one live before keeping it**: the task must
report FAIL with no patch applied and PASS under its own reference patch, with the executed
node-id set equal to the declared one and zero skips. A candidate that cannot be shown to
discriminate is not written out, so no unproven task can enter the corpus by being merely
plausible. Each mint appends to `local-ledger.json` and writes the donor's `recipes/<donor>.json`.

**What the two mints actually produced, refusals included.**

| Donor | Minted | Note |
|---|---:|---|
| `contig` | 45 | reached its `--limit` with candidates left over |
| `belay` | 21 | exhausted its candidates below a `--limit` of 25 |
| `rereflect` | — | **refused: no `uv.lock`.** Its pins would have been chosen by the date the mint ran, which is the exact corruption `environment` exists to close |
| `whetstone` | 0 of 2 | this repository's own test-first workflow lands the test and the fix in **one** commit, so the held test does not collect at the parent |

The two refusals are recorded here rather than dropped, because they are the more transferable
result: a donor without a lockfile cannot yield a pinned task at all, and a repository that
commits its tests alongside its fixes cannot yield a red→green task by this rule no matter how
healthy it is. Neither is a bug in the miner.

**The held set is wider than the test files.** Every `conftest.py` from the repository root down
to each held test's directory is declared held too, read at the parent commit. That narrows cheat
10 (`docs/ROADMAP.md` § 3) and does not close it — a commit may also touch a data file no
conftest rule would ever see — so the cheat stays a documented residual. Read the roadmap for the
bound; do not infer a stronger one from this directory being well organised.
