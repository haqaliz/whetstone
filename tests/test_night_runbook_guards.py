"""Guards over the night runbook, so its commands cannot drift from the door they invoke.

`docs/planning/p2-rollouts/night-door/runbook.md` is the operator's sheet for the first night of
the improvement loop: the operator runs its probe pass and its night command verbatim. A sheet
that disagrees with the code it runs fails at three in the morning, in a run nobody can undo, so
the disagreements are refused here first.

**Extended, not parameterized — where extension is honest.** The arm guards
(`tests/test_runbook_guards.py`, and the two that build on it) parse a sheet whose command is
`python -m whetstone.bakeoff.run`, and their block/flag/value helpers are keyed on that module
string at module scope. Three of their helpers are independent of it — `_bash_blocks`,
`_named_paths`, `_worktree_name` — and those are imported **by identity**, asserted `is`, so a fix
to the shared parse is seen by every runbook guard in this tree. The three that are keyed on the
command are re-implemented here against **this** door's command rather than by mutating a module
constant the other guards read, because a guard that reaches into another guard's globals is a
guard that can silently repoint the sheet it was watching.

Six properties, and the last two are this sheet's own:

1. the parse really reads the sheet (anti-vacuity);
2. every flag the night command passes exists in the shipped parser;
3. every writable path the night command names is absolute;
4. exactly one worktree is named anywhere, and no stale one survives;
5. the candidate resolution names the retained candidate and excludes the other **by name**, and
   the excluded name appears in no `--only` value;
6. the zero-strict-PASS outcome is stated as a published result rather than as a halt, and the
   declared dev ids are the ones the arms declared.

**Watched failing first** (CONTRIBUTING.md): every assertion below was run against a deliberately
wrong stub sheet — relative writable paths, a `--sample-more` flag the parser does not define, the
excluded candidate in `--only`, a stale worktree name, and the zero-yield paragraph deleted — and
each one refused it before the real sheet existed.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from test_runbook_guards import _bash_blocks, _named_paths, _worktree_name

from whetstone.cli import build_parser

#: The sheet under guard.
RUNBOOK = Path(__file__).parent.parent / "docs/planning/p2-rollouts/night-door/runbook.md"

#: The command every block that invokes the door begins with. The night's door is a `whetstone`
#: subcommand rather than a `python -m` module, which is why this constant is this file's own.
DOOR = "whetstone run --night"

#: This unit's worktree, and every worktree an earlier unit used. A stale name in a sheet sends an
#: operator to a directory that no longer holds the code they think they are running.
WORKTREE = "feat-p2-rollouts"
STALE_WORKTREES = (
    "feat-p2-format-hardening",
    "feat-format-hardening-measurement",
    "feat-measured-arm-run",
    "feat-p2-easier-stratum",
    "feat-stratum-probe-execution",
    "feat-larger-base-arm",
)

#: The candidate resolution, decided before the run from measured evidence.
RETAINED = "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit"
EXCLUDED = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"

#: The five dev ids the hardened contract declared (`PREREGISTRATION.md` § 10.4). The night runs
#: the same contract, so it must exclude the same ids: a night that scored a task the contract was
#: developed against would be optimising on its own outcome, one layer further along.
DECLARED_DEV = (
    "belay-2e149603209a",
    "belay-353359e9ac6e",
    "belay-3e3051c4192a",
    "belay-844db07ed482",
    "belay-9dba3ea557f5",
)

#: Which of the door's flags name something the run writes to. A relative one of these is the
#: failure that killed the measured arm on 2026-08-12.
WRITABLE = ("--runs", "--checkpoints", "--workspace")

FLAG = re.compile(r"--[a-z][a-z0-9-]*")


def _runbook() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert text.strip(), (
        f"{RUNBOOK} is empty, so every guard in this module would pass vacuously. A command "
        "sheet that parses into nothing proves nothing."
    )
    return text


def _door_blocks(blocks: list[str]) -> list[str]:
    """Every block that invokes the night door. There are two: the probe pass and the night."""
    return [block for block in blocks if DOOR in block]


def _night_block(blocks: list[str]) -> str:
    """The night itself: the door block that is not the probe pass.

    Told apart by `--probe`, which is exactly what makes them different runs — one draws against a
    declared sample and writes no candidate, the other is the night.
    """
    return next((block for block in _door_blocks(blocks) if "--probe" not in block), "")


def _flags(block: str) -> set[str]:
    """The `--flag` tokens handed to the door, ignoring `uv`'s own `--project`.

    Tokens before the door invocation belong to `uv run`; only what follows it is the CLI's.
    """
    return set(FLAG.findall(block.partition(DOOR)[2]))


def _values(block: str) -> dict[str, list[str]]:
    """Flag → every value it was given, from the tokens after the door invocation.

    Values are collected as a **list** rather than a single string, because `--tasks`,
    `--dev-subset` and `--only` are repeatable and a last-one-wins parse would silently drop four
    of the five declared dev ids — the exact disclosure that must not be false.
    """
    tokens = shlex.split(block.partition(DOOR)[2], posix=True)
    values: dict[str, list[str]] = {}
    current: str | None = None
    for token in tokens:
        if token.startswith("--"):
            current = token
            values.setdefault(current, [])
        elif current is not None:
            values[current].append(token)
            current = None
    return values


def _parser_flags() -> set[str]:
    """Every option string the shipped `run` subcommand accepts."""
    import argparse

    parser = build_parser()
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert subparsers, "the CLI defines no subcommands, so this guard would compare against nothing"
    night = subparsers[0].choices["run"]
    return {option for action in night._actions for option in action.option_strings}


def test_the_guard_shares_the_parse_helpers_it_can() -> None:
    """One parse implementation for the parts that are command-independent, imported by identity.

    A second, drifting copy of "which paths does this line name" would let one runbook's guard
    accept a shape another's refuses, and the divergence would look like two correct guards.
    """
    from test_runbook_guards import _bash_blocks as shared_blocks
    from test_runbook_guards import _named_paths as shared_paths
    from test_runbook_guards import _worktree_name as shared_worktree

    assert _bash_blocks is shared_blocks
    assert _named_paths is shared_paths
    assert _worktree_name is shared_worktree


def test_the_parse_really_reads_the_runbooks_command() -> None:
    """Anti-vacuity: a renamed or emptied sheet must fail loudly rather than pass.

    Every assertion below is a statement about the members of a parsed set, so an empty parse
    satisfies all of them at once — the strongest possible result reported by the weakest
    possible run.
    """
    blocks = _bash_blocks(_runbook())
    assert len(_door_blocks(blocks)) == 2, (
        "WHY THIS IS A FAILURE: the sheet does not carry exactly two door invocations (the probe "
        f"pass and the night). Found {len(_door_blocks(blocks))}"
    )
    night = _night_block(blocks)
    assert night and DOOR in night, "no bash block invokes the night without --probe"
    assert _flags(night), "the night command parsed into no flags at all"


def test_every_flag_the_night_command_passes_exists_in_the_parser() -> None:
    """A flag the door does not define is a usage error at 2 a.m., after the setup is done.

    Checked against `build_parser()` itself rather than against a copied list, so the sheet is
    pinned to the code that ships and not to a memory of it.
    """
    blocks = _bash_blocks(_runbook())
    known = _parser_flags()
    for block in _door_blocks(blocks):
        unknown = sorted(_flags(block) - known)
        assert not unknown, (
            f"WHY THIS IS A FAILURE: the sheet passes {unknown} and `whetstone run` defines "
            f"none of them. The operator runs this verbatim; a flag that does not exist is a "
            f"usage error after the workspace has been prepared. Parser accepts: {sorted(known)}"
        )


def test_the_night_commands_writable_paths_are_absolute() -> None:
    """The correction the measured arm's death bought, applied to this door's three roots.

    A relative `--workspace` does not resolve in the provisioning subprocesses, whose CWD is not
    the run's: every environment build fails, every rollout is `UNPROVISIONED`, and the control
    arm proves nothing. That is a whole night spent discovering a path shape.
    """
    for block in _door_blocks(_bash_blocks(_runbook())):
        values = _values(block)
        for flag in WRITABLE:
            named = values.get(flag, [])
            assert named, (
                f"WHY THIS IS A FAILURE: the sheet's door command passes no {flag}. It is "
                "required, and a command that omits it does not run at all"
            )
            for value in named:
                assert value.startswith("/"), (
                    f"WHY THIS IS A FAILURE: {flag} is relative ({value!r}). The measured arm "
                    "died exactly this way on 2026-08-12 — a relative workspace does not resolve "
                    "in the provisioning subprocesses, so every rollout came back UNPROVISIONED "
                    "and the harness proved nothing"
                )


def test_the_runbook_names_exactly_one_worktree_everywhere() -> None:
    """One worktree, and it is this unit's. Two would mean half the sheet runs other code."""
    text = _runbook()
    named = {
        name
        for line in text.splitlines()
        for path in _named_paths(line)
        if (name := _worktree_name(path)) is not None
    }
    assert named == {WORKTREE}, (
        f"WHY THIS IS A FAILURE: the sheet names {sorted(named)} as worktrees and this unit's is "
        f"{WORKTREE!r}. An operator running half the commands against another branch's checkout "
        "produces a run nothing in the evidence would explain"
    )


def test_no_stale_worktree_name_survives_anywhere() -> None:
    """A copied sheet keeps the branch it was copied from, and the paths still look plausible."""
    text = _runbook()
    surviving = sorted(name for name in STALE_WORKTREES if name in text)
    assert not surviving, (
        f"WHY THIS IS A FAILURE: the sheet still names {surviving}, a worktree from an earlier "
        "unit. Those directories are removed after their unit merges, so the command either "
        "fails or — worse — runs whatever is left in them"
    )


def test_the_resolution_names_the_retained_candidate_and_excludes_the_other() -> None:
    """The a-priori candidate decision, in the sheet, before any night runs.

    Both halves matter. The retained candidate must be the one `--only` narrows to, and the
    excluded one must be named **and** absent from every `--only` value — an exclusion that is
    argued in prose and then contradicted in the command is worse than no exclusion, because the
    prose is what a reader checks.
    """
    text = _runbook()
    assert RETAINED in text and EXCLUDED in text, (
        "WHY THIS IS A FAILURE: the sheet does not record the candidate resolution by name. A "
        "resolution decided in someone's head is one that can be re-decided after a result"
    )
    assert "zero" in text.lower() and "ceiling" in text.lower(), (
        "WHY THIS IS A FAILURE: the sheet excludes a candidate without stating the measured rule "
        "it was excluded under (its zero retry-eligible ceiling)"
    )
    for block in _door_blocks(_bash_blocks(text)):
        only = _values(block).get("--only", [])
        assert only == [RETAINED], (
            f"WHY THIS IS A FAILURE: --only is {only!r} and the resolution retains exactly "
            f"[{RETAINED!r}]. A night trains one candidate; a second would produce a checkpoint "
            "whose base nobody can name"
        )
        assert EXCLUDED not in only


def test_every_declared_dev_id_is_passed_and_matches_the_hardened_contract() -> None:
    """The same five ids the hardened contract declared, excluded from both sources.

    Not four, and not a different five. The night runs the contract those ids were developed
    against, so scoring one of them would be optimising on the run's own outcome — and the
    `--dev-subset` disclosure would be false in the one direction nobody checks.
    """
    for block in _door_blocks(_bash_blocks(_runbook())):
        passed = tuple(_values(block).get("--dev-subset", []))
        assert passed == DECLARED_DEV, (
            f"WHY THIS IS A FAILURE: the command excludes {passed!r} and the hardened contract "
            f"declared {DECLARED_DEV!r}. Every id must be passed; the door refuses an id that "
            "matches no task, but it cannot notice one that was never passed"
        )


def test_the_zero_yield_outcome_is_stated_as_a_result_rather_than_a_halt() -> None:
    """The response to a low yield is `K`, in a diff, before the next night — never the check.

    A sheet that listed "no strict-PASS rollouts" among its halt conditions would train the
    operator to treat a legitimate finding as a failure to be worked around, which is the exact
    pressure the roadmap's pivot rule exists to resist.
    """
    text = _runbook()
    assert "not** a halt" in text or "not a halt" in text, (
        "WHY THIS IS A FAILURE: the sheet does not say that a zero strict-PASS yield is a "
        "published outcome rather than a halt condition"
    )
    assert "raise `K`" in text or "raise K" in text, (
        "WHY THIS IS A FAILURE: the sheet does not name the pre-committed response to a low "
        "yield. The roadmap's rule is to raise the number of draws, never to weaken the check, "
        "and an operator reading this at 3 a.m. must not have to remember that"
    )
    assert "loosen" in text, (
        "WHY THIS IS A FAILURE: the sheet never states what must NOT be done in response to a "
        "low yield, which is the half of the rule that is under pressure at the time"
    )


def test_the_sheet_publishes_nothing() -> None:
    """A night's counts live in its own gitignored run directory, which is their only home.

    The four published report homes each measure a different pinned input and are declared
    non-comparable; a fifth series appearing because a night's number got written down beside
    them would be a figure that can disagree with itself.
    """
    text = _runbook()
    assert "Nothing here is published" in text, (
        "WHY THIS IS A FAILURE: the sheet does not state that the night publishes nothing. An "
        "operator with a number and no instruction writes it down somewhere"
    )
    for block in _door_blocks(_bash_blocks(text)):
        for values in _values(block).values():
            for value in values:
                assert "/reports/" not in value, (
                    f"WHY THIS IS A FAILURE: the command names {value!r}, inside the published "
                    "reports directory. The door refuses it, and the sheet must not ask for it"
                )
