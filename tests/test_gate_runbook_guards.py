"""Guards over the gate runbook, so its commands cannot drift from the doors they invoke.

`docs/planning/p3-promotion-gate/gate-runbook/runbook.md` is the operator's sheet for the
**first real gated evaluation** — the one that decides whether a night's candidate may replace
the incumbent. It is run verbatim, and a sheet that disagrees with the code it runs fails after
a night has already been spent producing the candidate, so the disagreements are refused here.

**Extended, not parameterized, on the night guard's own argument.** The three parse helpers
that are independent of which command a sheet invokes — `_bash_blocks`, `_named_paths`,
`_worktree_name` — are imported **by identity**, asserted `is`, so a fix to the shared parse is
seen by every runbook guard in this tree. The flag and value parses are keyed on this sheet's
own doors and are this file's own, rather than mutating a constant another guard reads: a guard
that reaches into another guard's globals can silently repoint the sheet it was watching.

Nine properties, and the last four are this sheet's own:

1. the parse really reads the sheet (anti-vacuity);
2. every flag either command passes exists in the shipped parser;
3. every path either command names is absolute;
4. exactly one worktree is named anywhere, and no stale one survives;
5. the retry budget the sheet states is `gate.RETRY_COUNT` — the declared constant, by identity,
   so an amendment that moved `R` without updating the sheet fails here;
6. the promotion record's home is `gate.PROMOTIONS_DIR`, by identity;
7. the **machinery is verified before the real pair** — the gate's own fixture suites run
   first, so the first real evaluation is not also the first test of the machinery;
8. the liveness measurement is stated — the unverified count over its denominator, from the
   first evaluation onward (`docs/ROADMAP.md:441-442`);
9. the `UNVERIFIED` exit is stated as a published outcome with the roadmap's own response, and
   the sheet nowhere tells the operator to rerun until it passes.

**Watched failing first** (`CONTRIBUTING.md`): every assertion was run against a deliberately
wrong stub sheet — relative writable paths, a flag the parser does not define, a renamed
promotion-record home, a stale worktree, a retry budget that disagreed with the constant, no
fixture verification at all, and a "rerun until it promotes" instruction — and each refused it
before the real sheet existed. Ten of the eleven tests here failed against that stub; the
eleventh is about this guard's own shared helpers rather than about the sheet.
"""

from __future__ import annotations

import argparse
import re
import shlex
from pathlib import Path

from test_runbook_guards import _bash_blocks, _named_paths, _worktree_name

from whetstone.cli import build_parser
from whetstone.loop import gate

#: The sheet under guard.
RUNBOOK = Path(__file__).parent.parent / "docs/planning/p3-promotion-gate/gate-runbook/runbook.md"

#: The two doors this sheet drives, paired with the subcommand whose parser defines their flags.
DOORS = (("whetstone gate", "gate"), ("whetstone check-leakage", "check-leakage"))

#: This unit's worktree, and every worktree an earlier unit used. A stale name in a sheet sends
#: an operator to a directory that no longer holds the code they think they are running.
WORKTREE = "feat-p3-promotion-gate"
STALE_WORKTREES = (
    "feat-p2-format-hardening",
    "feat-format-hardening-measurement",
    "feat-measured-arm-run",
    "feat-p2-easier-stratum",
    "feat-stratum-probe-execution",
    "feat-larger-base-arm",
    "feat-p2-rollouts",
)

#: Every flag on either door whose value is a path. All of them must be absolute — the failure
#: that killed the measured arm on 2026-08-12 was a relative workspace, and the gate is a longer
#: run than that one: it scores two checkpoints over the whole held-out membership.
PATH_FLAGS = frozenset(
    {
        "--candidate",
        "--incumbent",
        "--heldout",
        "--tasks",
        "--public",
        "--pool",
        "--weights",
        "--runs",
        "--workspace",
        "--run",
    }
)

FLAG = re.compile(r"--[a-z][a-z0-9-]*")

#: How the sheet must spell the retry budget, so the guard can compare it with the constant.
RETRY = re.compile(r"\bR\s*=\s*(\d+)\b")


def _runbook() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert text.strip(), (
        f"{RUNBOOK} is empty, so every guard in this module would pass vacuously. A command "
        "sheet that parses into nothing proves nothing."
    )
    return text


def _door_blocks(blocks: list[str], door: str) -> list[str]:
    """Every bash block that invokes `door`."""
    return [block for block in blocks if door in block]


def _flags(block: str, door: str) -> set[str]:
    """The `--flag` tokens handed to `door`, ignoring `uv`'s own `--project`."""
    return set(FLAG.findall(block.partition(door)[2]))


def _values(block: str, door: str) -> dict[str, list[str]]:
    """Flag → every value it was given, from the tokens after the door invocation.

    Values are a **list** because `--tasks` is repeatable: a last-one-wins parse would silently
    drop a donor root and leave the guard attesting to a command set nobody runs.
    """
    tokens = shlex.split(block.partition(door)[2], posix=True)
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


def _parser_flags(subcommand: str) -> set[str]:
    """Every option string the shipped subcommand accepts."""
    parser = build_parser()
    subparsers = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    assert subparsers, "the CLI defines no subcommands, so this guard would compare with nothing"
    door = subparsers[0].choices[subcommand]
    return {option for action in door._actions for option in action.option_strings}


def test_the_guard_shares_the_parse_helpers_it_can() -> None:
    """One parse implementation for the command-independent parts, imported by identity.

    A second, drifting copy of "which paths does this line name" would let one runbook's guard
    accept a shape another's refuses, and the divergence would look like two correct guards.
    """
    from test_runbook_guards import _bash_blocks as shared_blocks
    from test_runbook_guards import _named_paths as shared_paths
    from test_runbook_guards import _worktree_name as shared_worktree

    assert _bash_blocks is shared_blocks
    assert _named_paths is shared_paths
    assert _worktree_name is shared_worktree


def test_the_parse_really_reads_the_sheets_commands() -> None:
    """Anti-vacuity: a renamed or emptied sheet must fail loudly rather than pass.

    Every assertion below is a statement about the members of a parsed set, so an empty parse
    satisfies all of them at once — the strongest possible result from the weakest possible run.
    """
    blocks = _bash_blocks(_runbook())
    for door, _ in DOORS:
        found = _door_blocks(blocks, door)
        assert found, f"WHY THIS IS A FAILURE: no bash block invokes `{door}`"
        assert any(_flags(block, door) for block in found), (
            f"WHY THIS IS A FAILURE: every `{door}` block parsed into no flags at all"
        )


def test_every_flag_the_commands_pass_exists_in_the_shipped_parser() -> None:
    """A flag the door does not define is a usage error after the night is already spent.

    Checked against `build_parser()` itself rather than against a copied list, so the sheet is
    pinned to the code that ships and not to a memory of it.
    """
    blocks = _bash_blocks(_runbook())
    for door, subcommand in DOORS:
        known = _parser_flags(subcommand)
        for block in _door_blocks(blocks, door):
            unknown = sorted(_flags(block, door) - known)
            assert not unknown, (
                f"WHY THIS IS A FAILURE: the sheet passes {unknown} to `{door}` and the parser "
                f"defines none of them. The operator runs this verbatim. Accepts: {sorted(known)}"
            )


def test_every_path_the_commands_name_is_absolute() -> None:
    """A relative path is the failure that killed the measured arm on 2026-08-12.

    It applies to every path-valued flag here, not only the written ones: the gate reads two
    checkpoints and a committed document, and a relative read resolved against the wrong CWD
    produces a refusal that looks like a missing checkpoint rather than a mistyped command.
    """
    blocks = _bash_blocks(_runbook())
    for door, _ in DOORS:
        for block in _door_blocks(blocks, door):
            values = _values(block, door)
            relative = sorted(
                f"{flag} {value}"
                for flag, given in values.items()
                if flag in PATH_FLAGS
                for value in given
                if not value.startswith("/")
            )
            assert not relative, (
                f"WHY THIS IS A FAILURE: `{door}` is given relative path(s) {relative}. The "
                "sheet is run verbatim from a stated CWD, and a path that resolves against the "
                "wrong directory fails as a refusal about the checkpoint rather than the command"
            )


def test_exactly_one_worktree_is_named_and_no_stale_one_survives() -> None:
    """A stale worktree sends the operator to a directory that no longer holds this code."""
    text = _runbook()
    named = {
        name
        for line in text.splitlines()
        for path in _named_paths(line)
        if (name := _worktree_name(path)) is not None
    }

    assert named == {WORKTREE}, (
        f"WHY THIS IS A FAILURE: the sheet names worktree(s) {sorted(named)} and this unit's is "
        f"{WORKTREE!r}. A sheet naming two sends the operator to whichever they read first"
    )
    stale = sorted(one for one in STALE_WORKTREES if one in text)
    assert not stale, (
        f"WHY THIS IS A FAILURE: the sheet still names {stale}, from an earlier unit. That "
        "directory does not hold the gate"
    )


def test_the_retry_budget_the_sheet_states_is_the_declared_constant() -> None:
    """`R` is pinned by `PREREGISTRATION.md` § 7.2, and the sheet must not state a second value.

    Compared with `gate.RETRY_COUNT` by identity rather than with a number written here, so a
    future amendment that moves `R` fails on the sheet that still quotes the old one — which is
    the only way a document and a constant can be kept from disagreeing quietly.
    """
    stated = {int(one) for one in RETRY.findall(_runbook())}

    assert stated, (
        "WHY THIS IS A FAILURE: the sheet never states the retry budget. The operator reading "
        "an UNVERIFIED exit needs to know what budget was spent before it"
    )
    assert stated == {gate.RETRY_COUNT}, (
        f"WHY THIS IS A FAILURE: the sheet states R = {sorted(stated)} and the shipped constant "
        f"is {gate.RETRY_COUNT}. A sheet that quotes a budget the gate does not use describes a "
        "different experiment"
    )


def test_the_promotion_records_home_is_the_documented_one() -> None:
    """The record's home is `gate.PROMOTIONS_DIR`, by identity — never a second spelling."""
    text = _runbook()
    home = f"runs/{gate.PROMOTIONS_DIR}/"

    assert home in text, (
        f"WHY THIS IS A FAILURE: the sheet does not name {home!r}. The promotion record is the "
        "accumulated verified-improvement trail, and a sheet that sends the operator to the "
        "wrong directory makes it look as though nothing was written"
    )


def test_the_machinery_is_verified_before_the_real_pair() -> None:
    """The first real evaluation must not also be the first test of the machinery.

    The gate's own fixture suites run a known-good and a known-worse checkpoint pair through
    the whole path — `verify_checkpoint`, the held-out loader, the scoring harness, the three
    exits — under the stub engine. Running them first catches a machinery regression before a
    night's candidate is spent on it: the D7 probe-pass discipline every arm in this repository
    has used, applied to a door whose input took a night to produce.
    """
    text = _runbook()
    blocks = _bash_blocks(text)

    fixture = [
        block
        for block in blocks
        if "pytest" in block and "tests/loop/test_gate" in block
    ]
    assert fixture, (
        "WHY THIS IS A FAILURE: the sheet has no fixture verification step. The gate's fixture "
        "suites are what prove the machinery before a night's candidate is spent on it"
    )
    assert "verify_checkpoint" in text, (
        "WHY THIS IS A FAILURE: the sheet never names `verify_checkpoint`. The re-hash on both "
        "sides is what makes the decision a statement about the bytes on disk"
    )
    real = _door_blocks(blocks, "whetstone gate")
    assert real, "the sheet invokes `whetstone gate` nowhere"
    assert text.index(fixture[0]) < text.index(real[0]), (
        "WHY THIS IS A FAILURE: the real pair is scored before the machinery is verified. That "
        "makes the first gated evaluation the machinery's own smoke test, on the one input that "
        "cost a night to produce"
    )


def test_the_sheet_states_the_liveness_measurement() -> None:
    """The unverified count over its denominator, from the first evaluation onward.

    `docs/ROADMAP.md:441-442` makes liveness itself a measurement, and this sheet is where the
    first one gets read. A proportion would breach the denominator rule, so the sheet is checked
    for one as well.
    """
    text = _runbook()
    lowered = text.lower()

    assert "unverified" in lowered and "denominator" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not state the liveness measurement. The "
        "unverified rate is reported from the first eval onward, as a count over its denominator"
    )
    assert "%" not in text and "percent" not in lowered, (
        "WHY THIS IS A FAILURE: the sheet states a proportion. Every rate in this repository "
        "carries its denominator, and this sheet is where the first one is read aloud"
    )


def test_the_unverified_exit_is_a_published_outcome_and_never_a_rerun_loop() -> None:
    """Exit 3 means no comparison was made. The response is the sandbox, never the gate.

    The failure this refuses is the obvious one to write into an operator's sheet: *"if it comes
    back UNVERIFIED, run it again."* Re-running until an eval happens to verify is selecting on
    the outcome, and it would turn the honest third exit into a slower way of promoting.
    """
    text = _runbook()
    lowered = text.lower()

    assert "more reliable sandbox" in lowered, (
        "WHY THIS IS A FAILURE: the sheet does not state the roadmap's own response to an eval "
        "that cannot fire — a more reliable sandbox, never a looser gate"
    )
    for phrase in ("rerun until", "re-run until", "run it again until", "until it promotes"):
        assert phrase not in lowered, (
            f"WHY THIS IS A FAILURE: the sheet says {phrase!r}. Re-running until an eval "
            "verifies is selecting on the outcome, and it turns the third exit into a slower "
            "way of promoting"
        )


def test_the_post_run_chain_proves_the_night_did_not_leak() -> None:
    """`whetstone check-leakage` over the night that produced the candidate, in the chain.

    The gate scores the held-out membership; the leakage proof is what says that membership was
    never trained on. Read after the gate rather than before it only because the exit an
    operator acts on is the gate's — but a promotion whose leakage was never checked is a
    promotion nobody may quote.
    """
    blocks = _bash_blocks(_runbook())
    leak = _door_blocks(blocks, "whetstone check-leakage")

    assert leak, "WHY THIS IS A FAILURE: the post-run chain never proves the night's disjointness"
    values = _values(leak[0], "whetstone check-leakage")
    assert values.get("--run"), "the leakage check names no run directory"
    assert values.get("--heldout"), "the leakage check names no held-out document"
