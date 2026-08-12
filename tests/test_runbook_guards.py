"""Guards over the measured-arm runbook, so its commands cannot drift from the code they run.

`docs/planning/p2-format-hardening/measured-arm/runbook.md` is the operator's command sheet for
the format-hardening arm: the operator executes its arm command verbatim, and a later agent
executes its post-run commands verbatim (execution spec AC1, plan Phase 2). A command sheet
that disagrees with the code it runs fails at night, in a run nobody can undo, so the
disagreements are refused here first. Three drift shapes are guarded, each of which happened
once:

- **A flag the parser no longer accepts.** The runbook was written against `run.py`'s
  `build_parser` (`run.py:691-839`); a flag renamed or dropped there would abort the run at
  parse time, after the night is committed. Every `--flag` the arm command hands to
  `python -m whetstone.bakeoff.run` must still be accepted by it, so the sheet and the code
  cannot drift apart unnoticed.
- **Two different worktrees named in one file.** The runbook shipped naming
  `feat-p2-format-hardening` where the arm command runs and `feat-format-hardening-measurement`
  in every post-run `uv run --project` target: the arm would write its `--out`, workspace and
  evidence into one checkout while the post-run commands read another. The file must name
  exactly one worktree, everywhere, and the arm command must run from the **primary** checkout
  (CWD at the repo root, branch code via the worktree's project — the 54bea44 pattern), so the
  relative `runs/` paths resolve to the primary's gitignored store on both sides of the run.
- **A stale branch name surviving the refresh.** Either old name anywhere is a command that
  runs the wrong checkout's code, or points a reader at a branch that no longer exists.

The guards parse the runbook's fenced bash blocks with stdlib `re`/`pathlib` and compare
against `build_parser()`; importing `run.py` is safe without the mlx extra (every `mlx` import
there is function-local). Every path is resolved **structurally**, as strings — never asserted
to exist on this machine — so the suite is deterministic, offline and CI-safe.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from whetstone.bakeoff.run import build_parser

RUNBOOK = Path(__file__).parent.parent / "docs/planning/p2-format-hardening/measured-arm/runbook.md"
ARM_MODULE = "python -m whetstone.bakeoff.run"
STALE_WORKTREES = ("feat-p2-format-hardening", "feat-format-hardening-measurement")
BASH_BLOCK = re.compile(r"```bash\n(.*?)\n```", re.DOTALL)
PROJECT_TARGET = re.compile(r"uv run --project (\S+)")
FLAG = re.compile(r"--[a-z][a-z0-9-]*")


def _runbook() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert text.strip(), (
        f"{RUNBOOK} is empty, so every guard in this module would pass vacuously. "
        "A command sheet that parses into nothing proves nothing."
    )
    return text


def _bash_blocks(text: str) -> list[str]:
    return BASH_BLOCK.findall(text)


def _arm_block(blocks: list[str]) -> str:
    """The one block that invokes the arm: `python -m whetstone.bakeoff.run` exactly.

    The post-run blocks invoke `whetstone.bakeoff.attribution` et al. under their own parsers,
    so only the arm block's flags may be checked against `run.py`'s parser.
    """
    return next((block for block in blocks if ARM_MODULE in block), "")


def _arm_flags(block: str) -> set[str]:
    """The `--flag` tokens handed to the arm module, ignoring `uv`'s own `--project`.

    Tokens before the module invocation belong to `uv run` — after the refresh the arm command
    reads `uv run --project <worktree> python -m whetstone.bakeoff.run`, and `--project` is
    uv's surface, not the parser's — so only what follows the module is `run.py`'s.
    """
    return set(FLAG.findall(block.partition(ARM_MODULE)[2]))


def _worktree_name(path: Path) -> str | None:
    """The `<name>` of a `.claude/worktrees/<name>` path, or None for any other shape."""
    parts = path.parts
    if parts[-3:] == (".claude", "worktrees", parts[-1]):
        return parts[-1]
    return None


def _named_paths(line: str) -> list[Path]:
    """The absolute paths named on one line, whatever the surrounding punctuation.

    The runbook writes paths in backticks and bold markers; the surrounding noise — `(`, `):`,
    `**`, trailing commas — is stripped so a path is recognised wherever the prose puts it.
    """
    named: list[Path] = []
    for token in line.replace("`", " ").split():
        token = token.strip("()`*,.:;")
        if token.startswith("/") and "/" in token[1:]:
            named.append(Path(token))
    return named


def _arm_cwd_line(text: str) -> str:
    """The line stating where the arm command runs from: the nearest line above its block
    that names a worktree, scanning up past the blank line before the opening fence.
    """
    arm = next((m for m in BASH_BLOCK.finditer(text) if ARM_MODULE in m.group(1)), None)
    assert arm is not None, "no bash block invokes `python -m whetstone.bakeoff.run`"
    for line in reversed(text[: arm.start()].splitlines()):
        if ".claude/worktrees/" in line:
            return line
    return ""


def test_the_parse_really_reads_the_runbooks_command() -> None:
    """Anti-vacuity: an empty or silently renamed file must fail loudly, not pass.

    A guard that parsed no blocks would assert absence on nothing. The arm command's two
    signature flags — the switch that defines this run, and the named dev subset — must come
    out of the parse, proving the blocks being guarded are the runbook's own.
    """
    blocks = _bash_blocks(_runbook())
    assert blocks, (
        "no bash fenced block parsed out of the runbook, so every guard in this module would "
        "pass vacuously. Either the fence style changed or the command sections are gone."
    )
    arm = _arm_block(blocks)
    assert arm, (
        "no bash block invokes `python -m whetstone.bakeoff.run`, so the flag guard has "
        "nothing to check. A renamed module would pass every absence below."
    )
    assert "--retries" in arm, "the arm command no longer carries the switch that defines this run"
    assert "--dev-subset" in arm, "the arm command no longer names its dev subset"


def _arm_values(block: str) -> dict[str, str]:
    """The flag → value pairs the arm command passes, from the tokens after the module.

    The block is shell-shaped (`\\` continuations, one flag per line); `shlex` in POSIX mode
    removes the backslash-newline continuations and yields the tokens exactly as a shell
    would. The first flag follows the module invocation; values are the tokens after each
    flag that do not themselves start with `--`.
    """
    tokens = shlex.split(block.partition(ARM_MODULE)[2], posix=True)
    values: dict[str, str] = {}
    current: str | None = None
    for token in tokens:
        if token.startswith("--"):
            current = token
        elif current is not None:
            values[current] = token
            current = None
    return values


def test_the_arm_commands_writable_paths_are_absolute() -> None:
    """The arm's `--out`, `--workspace`, `--journal` and `--transcript` are absolute paths.

    The workspace is built as `workspace / digest` and provisioned by subprocesses whose CWD
    is not the run's (`run.py:546`, `scoring.py:351`): a relative workspace does not resolve
    there, every environment build fails, every rollout is `UNPROVISIONED`, and the control
    arm proves nothing — the run died exactly this way on 2026-08-12 (`HarnessNotProven`,
    halt condition 1, the worktrees skill's documented pitfall). The same class covers the
    run's other writable paths: absolute means no part of the run depends on CWD.
    """
    values = _arm_values(_arm_block(_bash_blocks(_runbook())))
    for flag in ("--out", "--workspace", "--journal", "--transcript"):
        value = values.get(flag)
        assert value, f"the arm command does not pass {flag}, so its path is unstated"
        assert value.startswith("/"), (
            f"the arm command passes {flag} a relative path {value!r}: the environment "
            "builder and its subprocesses do not share the run's CWD, so the path does not "
            "resolve there and every task is UNPROVISIONED — a night that proves nothing"
        )


def test_every_flag_the_arm_command_passes_exists_in_the_parser() -> None:
    """The permanent drift guard: the sheet and `build_parser` cannot disagree.

    Every flag the arm command hands to `python -m whetstone.bakeoff.run` must still be
    accepted by it, else the operator's night ends in a usage error. The parser side is pinned
    too: `--retries` must be present, proving this guard really saw the parser and not an
    empty one.
    """
    arm = _arm_block(_bash_blocks(_runbook()))
    assert arm
    parser_flags = {name for name in build_parser()._option_string_actions if name.startswith("--")}
    assert "--retries" in parser_flags, (
        "the parser this guard checks does not accept `--retries`, so either the import did "
        "not see the real `build_parser` or the arm's defining switch was removed"
    )
    unknown = _arm_flags(arm) - parser_flags
    assert not unknown, (
        f"the arm command passes flag(s) the parser does not accept: {sorted(unknown)}. "
        "A renamed or dropped flag aborts the run at parse time, after the night is committed."
    )


def test_every_project_target_is_a_worktree_shaped_path() -> None:
    """A `uv run --project` must point at a `.claude/worktrees/<name>` checkout, nothing else.

    The post-run commands execute the worktree's branch code by its project; a target that is
    not a worktree path (a primary checkout, a scratch directory) would run some other tree's
    code and the run's records would not correspond to what it executed.
    """
    targets = [
        match.group(1).rstrip("\\")
        for block in _bash_blocks(_runbook())
        for match in PROJECT_TARGET.finditer(block)
    ]
    assert targets, (
        "no `uv run --project` target parsed out of the runbook, so the worktree-structure "
        "guards have nothing to check"
    )
    for target in targets:
        name = _worktree_name(Path(target))
        assert name, f"{target!r} is not a `.claude/worktrees/<name>` path"


def test_the_runbook_names_exactly_one_worktree_everywhere() -> None:
    """The arm's CWD line and every post-run `--project` target must name the same worktree.

    The stale runbook named `feat-p2-format-hardening` where the arm runs and
    `feat-format-hardening-measurement` in every post-run target: the arm would write its
    `--out`, workspace and evidence into one checkout while the post-run commands read
    another, and the before/after comparison would compare two different trees' records.
    """
    text = _runbook()
    names = {
        name
        for block in _bash_blocks(text)
        for match in PROJECT_TARGET.finditer(block)
        for name in [_worktree_name(Path(match.group(1).rstrip("\\")))]
        if name is not None
    }
    cwd_line = _arm_cwd_line(text)
    assert cwd_line, "no line above the arm command names a worktree, so its CWD is unstated"
    cwd_names = {
        name
        for path in _named_paths(cwd_line)
        for name in [_worktree_name(path)]
        if name is not None
    }
    assert cwd_names, "the arm command's CWD line names no `.claude/worktrees/<name>` path"
    assert len(names | cwd_names) == 1, (
        f"the runbook names {sorted(names | cwd_names)}: the arm would write into one checkout "
        "while the post-run commands read another. Every command must name the same worktree"
    )


def test_the_arm_command_runs_from_the_primary_checkout() -> None:
    """CWD at the primary repo root, never at the worktree (the 54bea44 pattern).

    The run's `--out`, workspace, journal and transcript are relative `runs/` paths: executed
    from the worktree they land in the worktree's store, which the post-run commands (run from
    the primary) do not read. The primary is derived structurally — the checkout a
    `.claude/worktrees/<name>` path lives under is its ancestor three components up — and
    asserted by name only, never as an existing path on this machine.
    """
    cwd_line = _arm_cwd_line(_runbook())
    worktrees = [path for path in _named_paths(cwd_line) if _worktree_name(path) is not None]
    assert worktrees, "the arm command's CWD line names no `.claude/worktrees/<name>` path"
    primary = worktrees[0].parents[2]
    assert primary in set(_named_paths(cwd_line)), (
        f"the arm command's CWD line names the worktree {worktrees[0]} but not the primary "
        f"checkout it lives under ({primary}); run from the worktree, the relative runs/ "
        "paths land in the wrong store while the post-run commands read the primary's"
    )


def test_no_stale_worktree_name_survives_anywhere() -> None:
    """The two stale branch names are gone, everywhere, not just from the commands.

    The refresh moves the runbook onto the unit's worktree; a surviving mention of either old
    name is a command that runs the wrong checkout's code — or a reader pointed at a branch
    that no longer exists. Checked over the whole file, so an edit that fixed the commands but
    left the prose naming the old worktrees still fails.
    """
    text = _runbook()
    found = [name for name in STALE_WORKTREES if name in text]
    assert not found, (
        f"the runbook still names stale worktree(s): {found}. The arm runs the branch code "
        "this repository actually points at; a stale name runs a checkout that is not the one "
        "being measured"
    )
