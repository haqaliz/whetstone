# Security & Privacy

## The privacy model (read this first)

Whetstone is designed so that **your code and your training never leave your machine**. It runs on
your own hardware, and there is no upload path anywhere in the codebase.

- **Your tasks are your code.** Tasks mined from your own repositories are written to
  `tasks/local/`, which is gitignored, and they are never committed. What this repository publishes
  about them is *evidence*: the mining recipe, and a ledger of per-task hashes and verdicts. A
  reader with none of your data can count the corpus and confirm every task was proven live —
  and cannot reconstruct a single line of it.
- **Donors are named by pseudonym.** The committed recipe records an operator-chosen label, never a
  path and never your repository's name. `whetstone mine --label` has no default for exactly this
  reason: the only default available is your directory name, and a leak into a committed file is
  not undone by deleting the line later.
- **Model transcripts are your code too.** A completion quotes the source it was shown back
  verbatim, so transcripts are written only to gitignored roots and are **refused** if pointed
  inside the published output directory. That refusal is a hard error, not a warning.
- **One declared network exception.** Fetching public benchmark instances touches the network. It
  is human-run, its output is committed, and the draw itself is pure and offline. The private task
  source never touches the network at all. Scored runs set `HF_HUB_OFFLINE`, so a mistyped model
  path raises instead of downloading.
- **No cloud model is called.** Nothing inside the current roadmap horizon sends anything to a
  hosted model. A BYOK teacher model for distillation is optional and post-horizon; when it exists
  it will be opt-in, and it will never sit on the reward path.

## The sandbox, and its stated limit

Verification runs inside a macOS Seatbelt profile that **denies the network** and **confines
writes** to the run's own directory.

**It confines what a run may write, not what it may read.** File reads are permitted, and this is
stated plainly here because a claim of read-blindness would be false. Whetstone runs code from the
repositories you point it at; treat that code as you would treat running its test suite yourself,
because that is what is happening.

## Scope

Whetstone is **pre-release**. There is no published package, no release, and no supported version.
Nothing here should be treated as hardened, and the sandbox should not be relied on as a security
boundary against deliberately hostile code — it is a determinism and containment boundary for a
reward signal.

## Reporting a vulnerability

Please report privately rather than opening a public issue, using GitHub's
[private vulnerability reporting](https://github.com/haqaliz/whetstone/security/advisories/new).

Useful to include: what you did, what happened, what you expected, and the smallest reproduction
you have. If the finding is a way to make the verifier return `PASS` for a patch that did not
genuinely fix the task, say so explicitly — **that is the highest-severity class of bug in this
project**, because the entire premise is that the reward cannot be gamed. Findings of that kind are
written up in `docs/ROADMAP.md` § 3 with their evidence, whether or not they are closed.

There is no bounty. There is a commitment to publish the finding and its bound honestly, including
when the answer is that it remains open.
