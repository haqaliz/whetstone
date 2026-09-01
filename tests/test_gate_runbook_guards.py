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

Ten properties, and the last five are this sheet's own:

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
   the sheet nowhere tells the operator to rerun until it passes;
10. the sheet names the **untrained base as the first incumbent** — a bash block that
    materializes it with `write_baseline_checkpoint` at an absolute checkpoint path, a gate
    command whose `--incumbent` is that same path and never a night checkpoint, the § 3
    boundary wording ("not the § 3 baseline measurement"), and no "two nights" anywhere.

**Watched failing first** (`CONTRIBUTING.md`): every assertion was run against a deliberately
wrong stub sheet — relative writable paths, a flag the parser does not define, a renamed
promotion-record home, a stale worktree, a retry budget that disagreed with the constant, no
fixture verification at all, and a "rerun until it promotes" instruction — and each refused it
before the real sheet existed. Ten of the eleven tests here failed against that stub; the
eleventh is about this guard's own shared helpers rather than about the sheet. The tenth
property was watched failing the same way against the current sheet (still "two nights",
still a night-001 incumbent, no materialization step, no § 3 boundary wording) and against a
stub-sheet ladder that repaired one property at a time, each assertion failing with its
intended message before the real sheet was edited.
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
WORKTREE = "feat-gate-untrained-incumbent"
STALE_WORKTREES = (
    "feat-p2-format-hardening",
    "feat-format-hardening-measurement",
    "feat-measured-arm-run",
    "feat-p2-easier-stratum",
    "feat-stratum-probe-execution",
    "feat-larger-base-arm",
    "feat-p2-rollouts",
    "feat-p3-promotion-gate",
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


def _assert_untrained_base_incumbent(text: str) -> None:
    """Every assertion of the untrained-incumbent pin, on the given sheet text.

    The text is a parameter so the stub-sheet drill can run this on a deliberately wrong
    sheet (and on the real one) without touching `RUNBOOK`; the committed test below is the
    one caller.
    """
    plain = text.replace("*", "")
    blocks = _bash_blocks(text)

    materialized = [block for block in blocks if "write_baseline_checkpoint" in block]
    assert materialized, (
        "WHY THIS IS A FAILURE: no bash block materializes the untrained base "
        "(`write_baseline_checkpoint`). `docs/ROADMAP.md:663-671` made the untrained base the "
        "first incumbent — materialized before the gate, never a second night — and a sheet "
        "without the materialization step sends the operator to the gate with nothing to "
        "compare the candidate against"
    )
    match = re.search(r"Path\('([^']+)'\)", materialized[0])
    assert match, (
        "WHY THIS IS A FAILURE: the materialization block names no checkpoint path. The gate "
        "command's `--incumbent` must name the very path the block writes, and a block that "
        "leaves it implicit cannot be the incumbent the sheet resolves"
    )
    base_path = match.group(1)
    assert base_path.startswith("/"), (
        "WHY THIS IS A FAILURE: the materialization block names the relative checkpoint path "
        f"{base_path!r}. The sheet is run from a stated CWD, and a relative path materializes "
        "the incumbent somewhere the gate never reads"
    )

    gate = _door_blocks(blocks, "whetstone gate")
    assert gate, "WHY THIS IS A FAILURE: the sheet invokes `whetstone gate` nowhere"
    incumbents = _values(gate[0], "whetstone gate").get("--incumbent", [])
    assert incumbents, (
        "WHY THIS IS A FAILURE: the gate command passes no `--incumbent`. The candidate must "
        "beat something, and the only thing it may beat is the untrained base"
    )
    incumbent = incumbents[0]
    assert incumbent.startswith("/"), (
        f"WHY THIS IS A FAILURE: the gate command's `--incumbent` is the relative path "
        f"{incumbent!r}. A relative incumbent resolves against the sheet's stated CWD, so the "
        "gate compares the candidate with whatever happens to sit there"
    )
    assert "night-" not in incumbent, (
        f"WHY THIS IS A FAILURE: the gate command's `--incumbent` names a night checkpoint "
        f"({incumbent!r}). The first gated evaluation compares night #1's candidate against "
        "the untrained base the night started from — never against another night's checkpoint, "
        "which is the two-night reading the launch-path reorder removed"
    )
    assert incumbent == base_path, (
        f"WHY THIS IS A FAILURE: the gate command's `--incumbent` ({incumbent!r}) is not the "
        f"path the materialization block writes ({base_path!r}). An operator who gates against "
        "one path while materializing another scores the wrong side of the comparison"
    )

    assert "not the § 3 baseline measurement" in plain, (
        "WHY THIS IS A FAILURE: the sheet never states the § 3 boundary — the gate's "
        "incumbent is **not** the § 3 baseline measurement, different roles, different homes "
        "(`docs/ROADMAP.md:678-683`). A sheet that blurs the two invites the first "
        "disagreement between their figures to be reconciled instead of published as a finding"
    )
    assert "two nights" not in plain, (
        "WHY THIS IS A FAILURE: the sheet still says the first gated evaluation needs **two** "
        "nights. The launch-path reorder made the untrained base the first incumbent, so the "
        "first evaluation needs **one** night; an operator following a two-night sheet waits "
        "for a second night that is not required — and spends it before the gate can fire"
    )


def test_the_sheet_names_the_untrained_base_as_the_first_incumbent() -> None:
    """The first gated evaluation is one night: night #1's candidate vs the untrained base.

    The sheet was written when the first incumbent was a second night.
    `docs/ROADMAP.md:663-671` reordered the launch path — the first incumbent is the untrained
    base the night started from, materialized by `write_baseline_checkpoint` before the gate —
    and this pin refuses the old reading in all four places it could resurface: the
    materialization block itself (a bash block naming the writer, at an absolute checkpoint
    path), the gate command's `--incumbent` (that same path, never a night checkpoint), the
    § 3 boundary sentence, and the "two nights" phrase. Emphasis is stripped before the two
    phrase checks, so `**two**` and `**not**` cannot dodge them.

    **Watched failing first:** every assertion was run against the current sheet and against a
    stub-sheet ladder that repaired one property at a time — no materialization block, a
    night-001 incumbent, a mismatched incumbent, no § 3 boundary, "two nights" — and each
    failed with its intended message before the real sheet was edited.
    """
    _assert_untrained_base_incumbent(_runbook())
