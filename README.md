<div align="center">

<img src="assets/logo.svg" alt="Whetstone" width="104" />

# Whetstone

**A model that trains itself overnight — and proves it didn't cheat.**

Point Whetstone at your own repositories. Each night a local loop generates candidate fixes, grades every one by **re-executing the tests you hold** in a sandbox — never by asking a model what it thinks — keeps only the wins, and distils them back into a small local model. In the morning you get the verified delta, what changed, and the count of reward-hacking attempts the strictness caught.

[![CI](https://github.com/haqaliz/whetstone/actions/workflows/ci.yml/badge.svg)](https://github.com/haqaliz/whetstone/actions/workflows/ci.yml)
[![Status](https://img.shields.io/badge/status-pre--release%20·%20macOS%20only-e3b341)](docs/ROADMAP.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Built with uv](https://img.shields.io/badge/built%20with-uv-DE5FE9?logo=astral&logoColor=white)](https://github.com/astral-sh/uv)
[![Pre-registered](https://img.shields.io/badge/results-pre--registered-3fb950)](PREREGISTRATION.md)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-3fb950)](CONTRIBUTING.md)

[Quickstart](#quickstart) · [How it works](#how-it-works) · [Coverage & limits](#coverage--limits-stated-exactly) · [Status](#status-what-exists-today) · [Roadmap](docs/ROADMAP.md) · [Vision](VISION.md) · [Contributing](CONTRIBUTING.md)

</div>

---

> **Read this before anything else.** Whetstone is **pre-release**: the reward and task ingestion
> are built and tested; the nightly loop and the promotion gate are **not**. Nothing has been
> tagged and no version has been published. The one measurement taken so far lives in
> [`reports/baseline/`](reports/baseline/), which is the **only** place in this repository a figure
> about a model may appear — and its result was that **no base model was selected**, because no
> candidate produced evidence to choose on. [`PREREGISTRATION.md`](PREREGISTRATION.md) was
> committed *before* that measurement existed, which is the whole of its value.

## Why Whetstone

The live frontier for making models better at checkable work is **RLVR** — reinforcement learning
from *verifiable* rewards. Its central, documented failure mode is **reward-hacking**: the policy
learns to game the reward instead of getting better. METR observed a model rewriting a timer rather
than optimising the task it was given.

The usual patch is to have a model grade the model. That does not work where it matters:
*"One Token to Fool LLM-as-a-Judge"* reports up to **35% false positives** against a judge reward.
A guess about correctness is not a verification of it, and a policy will find the guess.

**Whetstone's reward is a process exit status.** A task is a repository at a known-broken commit
plus tests that currently fail. The policy proposes a patch; the reward is whether those tests pass
and the previously-passing ones still do. There is no reference answer, no similarity score, and no
model opinion anywhere on the reward path — a scoped AST guard fails the build if an inference
library is even *importable* from it. The classic RLVR failure mode is designed out rather than
monitored for.

- 🪨 **The name.** A whetstone sharpens a blade by patient, repeated honing against a hard, honest
  edge. Same idea, applied to a model.
- 🔒 **Local and private.** The loop, your repositories, and the model stay on your machine. The
  one network call in the project fetches public benchmark instances, is human-run, and has its
  output committed.
- ⛔ **Never regress.** A checkpoint is promoted only on a *proven* gain over a held-out verified
  set. `UNVERIFIED` is never a win, and never rendered as `PASS`.
- 📉 **Honest numbers, including the bad ones.** A zero or a negative delta is published as plainly
  as a gain. The first measurement this project took was a zero, and it is in the repository.
- 📈 **Gets better as open models do.** The durable asset is the verifier, the gate, and the
  accumulated record of verified improvement — never the base weights, which are swappable by
  design.

> Karpathy (Sequoia Ascent 2026) named the gap this sits in: the valuable RL environments
> *"aren't in the frontier-lab mix."*

---

## Quickstart

**Requirements:** macOS on Apple Silicon (the sandbox is Seatbelt; the runtime is MLX), Python
3.10+, and [uv](https://github.com/astral-sh/uv).

The published distribution is **`whetstonehq`**; the import package and the CLI are both
`whetstone`. It has zero runtime dependencies — the CLI is stdlib-only:

```bash
uv tool install whetstonehq
whetstone --help
```

The nightly loop needs the MLX runtime, which is an optional extra
(`uv tool install "whetstonehq[mlx]"`); `whetstone verify` needs nothing beyond the standard
library. To work on Whetstone itself, install from source instead:

```bash
git clone https://github.com/haqaliz/whetstone.git
cd whetstone
uv sync
uv run whetstone --help
```

Every command below is written `uv run whetstone …` for the source checkout; drop the `uv run`
if you installed the tool.

### 1 · Grade a patch against a task

The reward, on its own. `STRICT` is what would train a policy; `WEAK` is measurement only and never
trains anything.

```bash
uv run whetstone verify --task path/to/task.json --patch path/to/fix.diff
```

A task manifest declares the repository, the broken commit, the tests that must go green, the tests
that must stay green, the exact dependency pins, and the test files the operator holds. Pass a
directory instead of a file and every manifest in it is graded, reduced worst-status-wins — so a
single `UNVERIFIED` task can never exit 0.

### 2 · Mine tasks out of your own repository

A commit that turns a failing test green *is* a task. The miner finds them, and **proves each one
live before keeping it**: it must FAIL with no patch and PASS under its own reference patch, with
the executed test set equal to the declared one and zero skips.

```bash
uv run whetstone mine \
  --donor /path/to/your/repo \
  --label donor-a \
  --out tasks/local/donor-a \
  --limit 25
```

Your mined manifests are your code and are **gitignored**. What this repository commits is the
*evidence about* them: the mining recipe, and a ledger of per-task hashes and verdicts. `--label`
has no default on purpose — the only available default is your repository's own name, and a leak
into a committed file is not undone by deleting the line later.

### 3 · Score open bases against the verifier

```bash
python -m whetstone.bakeoff.run --help
```

Deliberately **not** a `whetstone` subcommand: the CLI is a guarded reward-path root, and a
subcommand would put an inference library one transitive import away from the reward while every
guard stayed green.

### 4 · Run a night of the improvement loop

```bash
uv run whetstone run --night --help
```

Draws `k` seeded attempts at every task under a frozen generation contract, keeps **only** the
rollouts the STRICT verifier passed, and LoRA-trains the base on those — so every training example
is verified by construction and `UNVERIFIED` can never become one. It writes `runs/<id>/` (a ledger
of the pinned seeds, model revision, task set and tool versions; the selected dataset; the per-draw
journals and transcripts) and, when the night selected anything and the declared capacity probe
fits, a hashed candidate under `checkpoints/<id>/`. A night that selected nothing writes no
candidate, says so, and exits non-zero.

This one **is** a subcommand, because it is the product surface the roadmap names — and it reaches
the loop through a function-local import inside its own handler, so `whetstone verify` never loads
a model. It is one of exactly five such edges (`run --night`, `gate`, `check-leakage`, `report`,
`check-probe`); that there are five and that every one of them is function-local is asserted by the
reward-path partition guard, which fails the build on a sixth or on any one moved to module scope.

Both `runs/` and `checkpoints/` are gitignored, and the run's own documents carry hashes and
verdicts and never file contents: the training set is your code, and it stays on your machine.

---

## How it works

```
STRICT — the reward
  1. check out the broken commit into a sandbox (no network, writes confined, seed fixed)
  2. apply the policy's patch
       └── REJECT the rollout if it touches any operator-held test path
  3. restore every held test from the golden copy — always, after the patch
  4. run the declared tests
       └── skipped count must be zero
       └── the EXECUTED test-id set must equal the declared one, exactly
  5. reward := the exit status, folded with the assertions above

WEAK — measurement only, never trains anything
     apply the patch with no confinement, restore nothing, run pytest, read the exit status
```

**The provenance boundary is the whole design.** The tests are the *operator's* artifact; the patch
is the *policy's*. They never mix. Held tests are restored from golden **after** the patch lands, so
nothing the policy wrote can influence what grades it. Without that, the policy authors its own
reward.

**Step 4's executed-set assertion is not a refinement of the skip check** — it closes a hole that
check never covered. `-k`, `-m` and `--deselect` remove tests from a run without producing a single
skip, and they arrive from configuration rather than from test files. An exit status answers *"did
anything fail?"*; it cannot answer *"were these the tests?"*, and the reward rests on the second
question.

### `N` — reward-hacking attempts caught

```
N := count(rollouts where WEAK == PASS and STRICT == FAIL)
```

Reported verbatim as **"N rollouts a weaker check would have scored as wins."** That is a claim
about what the strictness caught, **not** about the policy's intent — a patch that edited a
genuinely buggy test in good faith still counts. Intent is not observable, so no claim to measure it
is made.

---

## Coverage & limits, stated exactly

A verifier is worth what it rejects, so what it does *not* catch is documented rather than left to
be discovered. [`docs/ROADMAP.md`](docs/ROADMAP.md) § 3 carries the full cheat surface and its
evidence; the short version:

**The guarantee.** Whetstone guarantees that the operator-held tests, **as the operator wrote
them**, genuinely ran and genuinely passed.

**What it does not guarantee, by name:**

- **It does not guarantee the fix generalises.** A patch that special-cases the exact test input
  satisfies every structural check. This is a **documented residual** — mitigated by held-out
  evaluation, not eliminated.
- **The guarantee extends only as far as the task manifest is complete.** If a held test depends on
  a file the manifest never declared, that file is outside the boundary. Ingestion narrowed this and
  did **not** close it — a second documented residual.
- **The sandbox confines what a run may *write*, not what it may *read*.** No claim of
  read-blindness is made anywhere.
- **The cheat list is discovered, never enumerated.** Four of its ten entries arrived *after* the
  table already read as complete. It is append-only and must never be described as exhaustive.

Every killed cheat is backed by a fixture asserting **both** halves of the differential — that
STRICT rejects it *and* that a weaker check accepts it — so a rejection for an unrelated reason
cannot pass for a defence. The two residuals are asserted as *accepted by both*, so silence can
never be mistaken for coverage.

**Two reward corruptions with no adversary in the room**, both found here and both closed, are
written up in the roadmap because they generalise: a dependency resolved *by date* rather than by
pin turned a correct patch into a FAIL, and an editable install rooted outside the checkout under
test produced a **PASS with no patch applied at all**.

---

## Status: what exists today

| | |
|---|---|
| ✅ **Built** | The task contract, the STRICT and WEAK verifiers, the Seatbelt sandbox, the adversarial cheat corpus, the reward-path import guard, task ingestion for a private and a public source, the base-model bake-off, the pre-registration, the measurement instrumentation (a transcript of what a base actually wrote, and an offline attributor and classifier that say *why* a rollout never produced an applicable patch), **the nightly loop** (seeded rejection sampling, strict-PASS-only selection, the run ledger, LoRA-SFT behind a declared capacity probe, and the `whetstone run --night` door), **the never-regress promotion gate** with its held-out split, its declared retry discipline and its leakage check, the § 3 baseline machinery and the honest-number report writer, the signed morning report (`whetstone report --last-night`), which renders one night's sealed evidence into a page a person reads, and — new — **the probe decision gate** (`whetstone check-probe --run <runs/id>`), which turns the night door's pre-committed go/no-go into a command exit rather than an operator reading a ledger by eye |
| 🔬 **Open question** | **What a night actually yields.** The loop's machinery is shipped and tested; it has not been run, so this repository holds no training set, no checkpoint and no yield figure. The response to a low yield is pre-committed — raise the number of draws, never loosen the check — see `docs/planning/p2-rollouts/night-door/runbook.md` |
| ❌ **Not built** | The Next.js dashboard, and distillation into a small local model — both named post-horizon |
| 📦 **Released** | v0.3.0 through v0.13.0, tagged and published to PyPI as `whetstonehq`; the import package and the CLI stay `whetstone`. Tag-push is the whole release mechanism (`RELEASING.md`) |

**Platform:** macOS / Apple Silicon only today. The sandbox is Seatbelt and the runtime is MLX;
Linux portability is named as post-horizon rather than promised.

---

## Documentation

| Document | What it is |
|---|---|
| [`VISION.md`](VISION.md) | The thesis, the moat, and the non-goals |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | The authoritative technical plan: task family, verifier, cheat surface, phases |
| [`PREREGISTRATION.md`](PREREGISTRATION.md) | What any future number may claim — fixed before any number existed |
| [`reports/baseline/`](reports/baseline/) | The one measurement taken so far, and the only home for a figure about a model |
| [`tasks/README.md`](tasks/README.md) | Which half of the corpus is committed, and why the other half never can be |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Dev setup and the few rules that are load-bearing |
| [`SECURITY.md`](SECURITY.md) | The privacy model, and how to report a vulnerability |
| [`CHANGELOG.md`](CHANGELOG.md) | What has actually shipped |

---

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first — it is short, and its rules are the ones that keep
the project honest. In particular: development is **strictly test-first**, any test asserting an
honesty property must be *watched failing* before it is trusted, and the guarded reward path is
never widened to make a check pass.

```bash
uv run pytest          # the suite
uv run ruff check .    # lint
uv run mypy src/       # types
uv run whetstone --help
```

All four must exit 0 before a pull request.

## License

[Apache-2.0](LICENSE). The mark in `assets/logo.svg` is a W drawn as two rounded parallelograms
plus a dot; it inherits `currentColor` and flips to a light fill on dark backgrounds.
