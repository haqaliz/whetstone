# Contributing to Whetstone

Thanks for your interest. Whetstone is the **verified self-improvement loop** — a model trains
itself overnight against an execution-grounded verifier, and the run proves it didn't cheat.
This guide is short; the few rules it does state are load-bearing.

> **Where the project is.** `docs/ROADMAP.md` is the authoritative technical plan
> (`docs/technical/ARCHITECTURE.md` is not written yet). Read it before proposing work, so a
> change lands in the phase that needs it rather than three phases early.

## Ground rules (these are the moat, not bureaucracy)

Whetstone's entire value is that **the reward cannot be gamed**. A change that erodes that is a
regression no matter how much it adds. Before you build, read [CLAUDE.md](CLAUDE.md) and
[VISION.md](VISION.md); in particular:

1. **The reward is execution-grounded, never a judge.** Deterministic re-execution decides a
   verdict — a checkable end state, an exit status. A model may help *author* a task or a check;
   only execution may *decide*. An AST guard bans any inference import from the reward path; do
   not work around it, and do not widen the guarded path to make it pass.
2. **`UNVERIFIED` is never a win.** Where the loop cannot ground a claim, it says so by name.
   `UNVERIFIED` never counts toward a gain, is never rendered as `PASS`, and never promotes a
   checkpoint.
3. **Never regress.** A checkpoint is promoted only when it *provably* beats the last on a
   held-out verified set. If the evidence is incomplete, the answer is "not promoted".
4. **Local by default; no data egress.** The loop, the tasks, and the training stay on the
   user's machine. A BYOK cloud teacher is optional and for distillation only — never a step the
   reward depends on.
5. **No invented numbers.** Every figure in a report, a doc, or a commit message must be one the
   verifier produced or a command can reproduce. If you need a statistic you cannot ground, say
   it is unverified. Publishing a modest honest delta is the point; a flattering unsourced one
   is the failure.

## Development setup

Python 3.10+ and [uv](https://github.com/astral-sh/uv). The target platform is
**macOS / Apple Silicon** — the local runtime is MLX (`mlx-lm`), which is Apple-Silicon-only, so
the model-facing parts of the suite only run there. uv is the only supported package manager; do
not use pip or poetry.

```bash
git clone https://github.com/haqaliz/whetstone && cd whetstone
uv sync
uv run pytest             # run the suite
uv run ruff check .       # lint
uv run mypy src/          # type-check
uv run whetstone --help   # the CLI, from source
```

All four commands must exit 0 before you open a PR.

## The workflow

- **Test-first, always.** Whetstone is built strictly RED → GREEN → REFACTOR: no production code
  without a failing test first.
- **Tests with teeth.** Anything asserting an honesty property — the guard, the verdict
  reduction, the promotion gate — must be *watched failing* against a stub or an inverted
  fixture before it is trusted. **A guard nobody has seen fail may be passing vacuously**, and a
  vacuous guard on the reward path is worse than no guard, because it buys false confidence. A
  guard that walks a set of files must also assert that set is non-empty.
- **Branch from `master`** (the base branch — there is no `main`). Name branches
  `<type>/<id>/<owner>`, e.g. `feat/task-verifier/aliz` or `bug/42/aliz`. Worktrees live under
  `.claude/worktrees/<type>-<id>`.
- **Keep the suite green and the tree clean** (`uv run pytest`, `uv run ruff check .`,
  `uv run mypy src/`) on every commit.
- **Open a PR against `master`** with a clear description of what changed and, for anything
  touching a reward or a gate, what its explicit `UNVERIFIED` path is.

## Reporting bugs & ideas

Open a [GitHub issue](https://github.com/haqaliz/whetstone/issues). Describe where the problem
occurs, what you expected, and what actually happened — not a one-liner. For anything
security- or privacy-sensitive, email the maintainer rather than filing a public issue.

## License

By contributing, you agree that your contributions are licensed under the
[Apache-2.0 License](LICENSE).
