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

Properties 5 onward are this sheet's own:

1. the parse really reads the sheet (anti-vacuity);
2. every flag the night command passes exists in the shipped parser;
3. every writable path the night command names is absolute;
4. no worktree is named anywhere, and no stale one survives;
5. the candidate resolution names the retained candidate and excludes the other **by name**, and
   the excluded name appears in no `--only` value;
6. the zero-strict-PASS outcome is stated as a published result rather than as a halt, and the
   declared dev ids are the ones the arms declared;
7. the probe decision is commanded, not read: a `check-probe` block runs before the night with
   only `--run` (against the shipped parser's surface), absolute and exactly the probe block's
   `--runs` root joined with its `--run-id`, the decision rule keeps both pre-committed
   conditions and all three exits' meanings, and a killed probe is never resumed — while a
   killed **night** still resumes unchanged; and
8. the post-§ 10.16 seam: no `belay-`/`contig-` id in any command block; the committed held-out
   document on both door blocks and on the post-night `check-leakage` step, which runs after the
   night; the § 10.16 citation and the scorable rule, with no live § 10.7 citation; the ledger
   digest-equality read-back; operator-declared run-id tokens, distinct and never
   `probe-001`/`night-001`; the re-derived 51 + 1 = 52 denominator; and the two dev ids that are
   held-out members, stated as exclusion, never a refusal; and
9. the live re-mint pin: the five declared dev ids exist in the committed corpus record, and the
   two overlap ids are members of the committed held-out document. This test is green on arrival —
   its RED demonstration is the next re-mint, which has not happened — and fails in any checkout.

**Watched failing first** (CONTRIBUTING.md): every assertion below was run against a deliberately
wrong stub sheet — relative writable paths, a `--sample-more` flag the parser does not define, the
excluded candidate in `--only`, a stale worktree name, the zero-yield paragraph deleted, and for
the probe pin: a sheet with no `check-probe` block, a relative `--run`, a `--run` pointing at the
night's own dir, a decision sentence missing an exit, and a sentence claiming a probe resumes — and
each one refused it before the real sheet existed. The § 10.16 pins were watched failing against
the stale sheet itself: the `guards` aspect's RED commit records each refusal. The live corpus pin
is green on arrival by design — its RED demonstration is the next re-mint, which has not happened.
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

#: The go/no-go command the sheet runs between the probe pass and the night. It is a `whetstone`
#: subcommand of its own (`--run <dir>`), so it is keyed here rather than by the night's DOOR.
PROBE_CHECK = "whetstone check-probe"

#: The leakage check the sheet runs after the night, at the seam where a training set that
#: touched the held-out membership would otherwise wait, unchecked, until the gate. Its own
#: `whetstone` subcommand (`--run`, `--heldout`), so it is keyed here rather than by the DOOR.
LEAKAGE_CHECK = "whetstone check-leakage"

#: Every worktree any unit ever used. A worktree is removed the moment its unit merges, so a
#: sheet that names one sends the operator to a directory that no longer exists — including the
#: sheet's *own* unit's worktree, which is why no name here is exempt. The launch-chain sheets
#: run from the primary checkout instead, and name no worktree at all.
STALE_WORKTREES = (
    "feat-p2-rollouts",
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

#: The five dev ids the hardened contract declared (`PREREGISTRATION.md` § 10.4), in the form the
#: § 10.16 corpus re-mint gave them (`--label`, 2026-09-27). The night runs the same contract, so
#: it must exclude the same ids: a night that scored a task the contract was developed against
#: would be optimising on its own outcome, one layer further along. Two of the five —
#: `donor-b-353359e9ac6e` and `donor-b-3e3051c4192a` — are now held-out members under § 10.16:
#: stated, never dropped, because a declared dev id inside the held-out band is exclusion, never
#: a refusal (`night.py:227-230`).
DECLARED_DEV = (
    "donor-b-2e149603209a",
    "donor-b-353359e9ac6e",
    "donor-b-3e3051c4192a",
    "donor-b-844db07ed482",
    "donor-b-9dba3ea557f5",
)

#: The committed held-out document both door blocks must pass, and the two dev ids the sheet must
#: state are members of it — stated, never dropped from `--dev-subset`.
HELDOUT_DOC = "$REPO/tasks/heldout/source-b.json"
HELDOUT_OVERLAP = ("donor-b-353359e9ac6e", "donor-b-3e3051c4192a")

#: The two run-id tokens the sheet declares at run time — one per run, never the historical
#: `probe-001`/`night-001`. Both are real artifacts: probe-001's ledger is refused by every
#: reader, and night-001's documents are never rewritten. The tokens are distinct literals, so a
#: sheet that reuses one for both runs is refused by name.
PROBE_RUN_ID = "<probe-run-id>"
NIGHT_RUN_ID = "<night-run-id>"

#: The committed corpus record and held-out document this checkout carries: both tracked
#: (`git ls-files`), so the live pin travels with the tree — no GPU, no primary resolution.
CORPUS_RECORD = Path(__file__).parent.parent / "tasks/local-ledger.json"
HELDOUT_DOCUMENT = Path(__file__).parent.parent / "tasks/heldout/source-b.json"

#: Which of the door's flags name something the run writes to. A relative one of these is the
#: failure that killed the measured arm on 2026-08-12.
WRITABLE = ("--runs", "--checkpoints", "--workspace")

FLAG = re.compile(r"--[a-z][a-z0-9-]*")

#: The id form the corpus carried before the § 10.16 re-mint (`belay-<sha12>` / `contig-<sha12>`).
#: No command block may pass one: the door refuses an id matching no task (`UnknownDevSubset`),
#: so a pre-mint id is a command that dies on its first line.
PRE_MINT_ID = re.compile(r"^(?:belay|contig)-[0-9a-f]{12}$")


#: A path the sheet can be run verbatim from: either literally absolute, or anchored to `$REPO`,
#: which the sheet exports to an absolute path before the first door runs. The distinction the
#: 2026-08-12 failure turns on is not the leading slash but **what the subprocess receives**: an
#: exported variable is expanded by the shell before the command starts, so the provisioner is
#: handed an absolute path either way. A bare relative path is not, and that is what produced a
#: night of `UNPROVISIONED`. The operator's own absolute path is deliberately not written into a
#: committed sheet — that publishes a home directory, and a reader re-deriving the run has a
#: different one.
_ANCHOR = "$REPO/"


def _is_anchored(value: str) -> bool:
    return value.startswith("/") or value.startswith(_ANCHOR)


def _exports_repo(text: str) -> bool:
    """The sheet must define `$REPO` as an absolute path, or the anchor anchors nothing."""
    return "export REPO=/" in text


def _flat(text: str) -> str:
    """The sheet's words with runs of whitespace collapsed to single spaces.

    A phrase pin asserts a sentence the sheet wraps freely, and the wrap point is not a word:
    "…§ 10.16 (Type 1,\\n  2026-09-27)…" is the same sentence as its flattened form. The
    emphasis-strip precedent in the gate guard (`_assert_untrained_base_incumbent`) pins words
    against markup the same way; this pins words against wrapping.
    """
    return re.sub(r"\s+", " ", text)


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


def _probe_check_block(blocks: list[str]) -> str:
    """The block that invokes `whetstone check-probe`, or empty when the sheet has none."""
    return next((block for block in blocks if PROBE_CHECK in block), "")


def _probe_check_values(block: str) -> dict[str, list[str]]:
    """Flag → every value the `check-probe` block gave, from the tokens after its invocation.

    Mirrors `_values` for the go/no-go command: `uv run`'s own `--project` sits before the
    invocation, so only what follows `whetstone check-probe` is the subcommand's surface.
    """
    tokens = shlex.split(block.partition(PROBE_CHECK)[2], posix=True)
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


def _probe_check_flags() -> set[str]:
    """Every option string the shipped `check-probe` subcommand accepts."""
    import argparse

    parser = build_parser()
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert subparsers, "the CLI defines no subcommands, so this guard would compare against nothing"
    check_probe = subparsers[0].choices["check-probe"]
    return {option for action in check_probe._actions for option in action.option_strings}


def _check_leakage_block(blocks: list[str]) -> str:
    """The block that invokes `whetstone check-leakage`, or empty when the sheet has none."""
    return next((block for block in blocks if LEAKAGE_CHECK in block), "")


def _check_leakage_values(block: str) -> dict[str, list[str]]:
    """Flag → every value the `check-leakage` block gave, from the tokens after its invocation.

    Mirrors `_probe_check_values` for the post-night leakage step: `uv run`'s own `--project`
    sits before the invocation, so only what follows `whetstone check-leakage` is the
    subcommand's surface.
    """
    tokens = shlex.split(block.partition(LEAKAGE_CHECK)[2], posix=True)
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


def _check_leakage_flags() -> set[str]:
    """Every option string the shipped `check-leakage` subcommand accepts."""
    import argparse

    parser = build_parser()
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert subparsers, "the CLI defines no subcommands, so this guard would compare against nothing"
    check_leakage = subparsers[0].choices["check-leakage"]
    return {option for action in check_leakage._actions for option in action.option_strings}


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
                assert _is_anchored(value), (
                    f"WHY THIS IS A FAILURE: {flag} is relative ({value!r}). The measured arm "
                    "died exactly this way on 2026-08-12 — a relative workspace does not resolve "
                    "in the provisioning subprocesses, so every rollout came back UNPROVISIONED "
                    "and the harness proved nothing"
                )


def test_the_runbook_names_no_worktree_anywhere() -> None:
    """The sheet runs from the primary checkout, because every worktree is eventually deleted.

    This guard used to require *exactly one* worktree — this unit's — which encoded an
    assumption that stopped holding the moment the unit merged: cleanup removes the worktree,
    and the sheet then pointed every command at a directory that no longer exists. The sheet is
    read long after its branch is gone, so the only path that survives is the primary checkout.
    """
    text = _runbook()
    named = {
        name
        for line in text.splitlines()
        for path in _named_paths(line)
        if (name := _worktree_name(path)) is not None
    }
    assert named == set(), (
        f"WHY THIS IS A FAILURE: the sheet names worktree(s) {sorted(named)}. Worktrees are "
        "removed when their unit merges, so an operator running this sheet verbatim hits a "
        "directory that does not exist — or, worse, whatever was left behind in it. Run from "
        "the primary checkout: plain `uv run whetstone ...`, no --project"
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
    """The same five ids the hardened contract declared, in the post-§ 10.16 corpus form.

    Not four, and not a different five. The night runs the contract those ids were developed
    against, so scoring one of them would be optimising on the run's own outcome — and the
    `--dev-subset` disclosure would be false in the one direction nobody checks. The § 10.16
    re-mint changed the ids' form (`belay-*` → `donor-b-*`), never the set: two of the five
    are also held-out members now, and dropping them here would silently shrink the exclusion.
    """
    for block in _door_blocks(_bash_blocks(_runbook())):
        passed = tuple(_values(block).get("--dev-subset", []))
        assert passed == DECLARED_DEV, (
            f"WHY THIS IS A FAILURE: the command excludes {passed!r} and the declared dev set "
            f"is {DECLARED_DEV!r} in the post-§ 10.16 corpus form (the `--label` re-mint). "
            "Every id must be passed; the door refuses an id that matches no task, but it "
            "cannot notice one that was never passed"
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


def test_the_probe_decision_is_commanded_before_the_night() -> None:
    """The go/no-go is a command the sheet runs, before the night, with only `--run`.

    A decision the operator reads is one they can misread at 3 a.m.; a decision the sheet runs
    is one the door has already proved against the parser. And the run it decides must be the
    run the probe block wrote — the two commands are bound by the run dir, so a mismatch
    between them is exactly the drift this guard exists to catch.
    """
    blocks = _bash_blocks(_runbook())
    check = _probe_check_block(blocks)
    assert check and PROBE_CHECK in check, (
        "WHY THIS IS A FAILURE: the sheet does not run `whetstone check-probe` as a command. "
        "The decision rule stays a paragraph an operator reads instead of a gate the sheet "
        "actually executes"
    )
    night = _night_block(blocks)
    assert night, "no bash block invokes the night without --probe"
    assert blocks.index(check) < blocks.index(night), (
        "WHY THIS IS A FAILURE: the probe decision is commanded after the night. The go/no-go "
        "must be decided before a night is committed to"
    )
    values = _probe_check_values(check)
    unknown = sorted(set(values) - _probe_check_flags())
    assert not unknown, (
        f"WHY THIS IS A FAILURE: the check-probe block passes {unknown} and the shipped "
        f"`check-probe` defines none of them. Parser accepts: {sorted(_probe_check_flags())}"
    )
    run_values = values.get("--run", [])
    assert run_values, (
        "WHY THIS IS A FAILURE: the check-probe block passes no --run. The command refuses "
        "without the run directory it must decide"
    )
    run_dir = run_values[0]
    assert _is_anchored(run_dir), (
        f"WHY THIS IS A FAILURE: --run is relative ({run_dir!r}). The decision must name the "
        "probe run directory outright, independent of CWD"
    )
    probe = next((block for block in _door_blocks(blocks) if "--probe" in block), "")
    assert probe, "no bash block invokes the probe pass"
    probe_values = _values(probe)
    runs_root = probe_values["--runs"][0]
    run_id = probe_values["--run-id"][0]
    assert run_dir == f"{runs_root}/{run_id}", (
        f"WHY THIS IS A FAILURE: --run is {run_dir!r} but the probe block wrote "
        f"{runs_root}/{run_id}. The decision must point at the run the probe pass actually "
        "produced, or it decides a different run than the one that ran"
    )


def test_the_decision_sentence_keeps_both_conditions_and_the_exits() -> None:
    """The pre-committed rule survives in the pre-committed words, and the exits carry it.

    Both conditions must be stated in the words the rule was pre-committed in — the control arm
    `PASS` on every draw, and a non-empty seed map — and the command's exits must mean what they
    do: 0 proceeds to the night, 1 is a named finding with no night behind it, 2 is a refusal
    an operator fixes by retyping, never a verdict about the probe.
    """
    text = _runbook()
    assert "control arm" in text and "`PASS`" in text and "every draw" in text, (
        "WHY THIS IS A FAILURE: the sheet drops the control arm `PASS` on every draw, the half "
        "of the pre-committed rule that proves the harness discriminates"
    )
    assert "non-empty seed map" in text, (
        "WHY THIS IS A FAILURE: the sheet drops the non-empty seed map condition. A probe whose "
        "map is empty selected nothing and must not stand behind a night"
    )
    assert "no night runs behind it" in text, (
        "WHY THIS IS A FAILURE: the sheet does not say what exit 1 means — a named harness "
        "finding, and no night runs behind it"
    )
    assert "proceed to the night" in text, (
        "WHY THIS IS A FAILURE: the sheet does not say what exit 0 means — the probe satisfies "
        "the rule, proceed to the night"
    )
    assert "never a verdict" in text, (
        "WHY THIS IS A FAILURE: the sheet does not say what exit 2 means — a refusal an operator "
        "can fix by retyping, never a verdict about the probe"
    )


def test_a_probe_is_never_resumed() -> None:
    """A killed probe restarts fresh under a new id; only a killed night resumes unchanged.

    The restart rule is asymmetric by cost: the probe is first-N private tasks, cheap to re-run
    and worthless if half its draws came from a different run's state, so a killed probe is
    never resumed — it restarts fresh. A killed night, by contrast, still resumes unchanged, and
    that sentence must survive untouched.
    """
    text = _runbook()
    assert "never resumed" in text and "restart it fresh" in text, (
        "WHY THIS IS A FAILURE: the sheet does not say a killed probe is never resumed and must "
        "be restarted fresh under a new --run-id. The cheap probe is the one place a restart is "
        "affordable, and the rule must say so before the run"
    )
    assert "Restart the **same command, unchanged**" in text, (
        "WHY THIS IS A FAILURE: the killed-night restart sentence is gone. A night is resumed "
        "unchanged with the same --run-id and --run-seed; the sheet must still say so"
    )


def test_the_sheet_exports_the_anchor_every_path_depends_on() -> None:
    """`$REPO/...` is absolute only because the sheet makes it so.

    Every path-valued flag here is anchored to `$REPO` rather than written as one operator's
    own absolute path, which keeps a home directory out of a committed file. That trade is
    only sound while the sheet still defines the anchor: an unset `REPO` expands to nothing,
    every path silently becomes relative, and this sheet is back to the shape that killed the
    measured arm on 2026-08-12 — with no leading slash left for the other guards to catch.
    """
    assert _exports_repo(_runbook()), (
        "WHY THIS IS A FAILURE: the sheet anchors its paths to `$REPO` and never exports it. "
        "An unset variable expands to the empty string, so every anchored path resolves "
        "against whatever directory the operator happened to be in"
    )


def test_no_pre_mint_task_id_appears_in_any_command_block() -> None:
    """Every id the sheet passes exists in the re-minted corpus, or the door refuses the run.

    The § 10.16 re-mint renamed the corpus under labels: `belay-<sha12>`/`contig-<sha12>` became
    `donor-a-<sha12>`/`donor-b-<sha12>`. The door's `_partition` refuses an id matching no task
    (`UnknownDevSubset`) for the probe and the night alike, so a pre-mint id in any command
    block is a command that dies on its first line — the staleness this sheet carried.
    """
    surviving = sorted(
        {
            token
            for block in _bash_blocks(_runbook())
            for token in shlex.split(block, posix=True)
            if PRE_MINT_ID.match(token)
        }
    )
    assert not surviving, (
        f"WHY THIS IS A FAILURE: the sheet's command blocks still carry pre-mint task ids "
        f"{surviving}. The corpus was re-minted under labels (`PREREGISTRATION.md` § 10.16, "
        "2026-09-27), so every id is `donor-a-*`/`donor-b-*` now, and the door refuses an id "
        "that matches no task (`UnknownDevSubset`) — the sheet fails on its first command"
    )


def test_both_door_blocks_pass_the_committed_heldout_document() -> None:
    """The held-out document is passed by the probe and the night, not only described.

    `--heldout` is optional in the parser by design — off by default, the night is today's
    night, byte for byte. The sheet is the surface that commits the real night to the pinned
    document: without it the 12 held-out members stay in the draw, the training set is
    non-clean by construction, and `check-leakage` refuses the run at the gate.
    """
    blocks = _bash_blocks(_runbook())
    probe = next((block for block in _door_blocks(blocks) if "--probe" in block), "")
    night = _night_block(blocks)
    for label, block in (("probe", probe), ("night", night)):
        assert block, f"no bash block invokes the {label} door"
        heldout = _values(block).get("--heldout", [])
        assert heldout == [HELDOUT_DOC], (
            f"WHY THIS IS A FAILURE: the {label} command passes --heldout {heldout!r} and the "
            f"committed document is {[HELDOUT_DOC]!r}. A run without it draws the held-out "
            "members into the training set, and its training set is non-clean by construction"
        )


def test_the_sheet_cites_the_amendment_that_re_derived_the_split() -> None:
    """The sheet names § 10.16 — the amendment, and the rule, that gave it its held-out band.

    The sheet commits the night to a specific held-out document, so it must say where that
    document's split came from: `PREREGISTRATION.md` § 10.16 (Type 1, 2026-09-27), re-derived
    under the scorable rule. A sheet that pins the document without naming its provenance
    cannot be audited against the amendment that produced it.
    """
    text = _flat(_runbook())
    assert "`PREREGISTRATION.md` § 10.16 (Type 1, 2026-09-27)" in text, (
        "WHY THIS IS A FAILURE: the sheet does not cite § 10.16 (Type 1, 2026-09-27) as fixing "
        "the held-out split. The split is re-derived under the scorable rule by that amendment, "
        "and a sheet that names no provenance sends the operator to no document at all"
    )
    assert "held out only if its oracle can be built under the declared budget" in text, (
        "WHY THIS IS A FAILURE: the sheet never states the scorable rule — a member is held "
        "out only if its oracle can be built under the declared budget. That is the rule § 10.16 "
        "re-derives the split under, and the operator reading the membership needs it stated"
    )


def test_no_live_citation_of_the_superseded_amendment_survives() -> None:
    """A sheet that still names § 10.7 as fixing the split describes a dead document.

    The history stays in git; the sheet's live instructions must not carry the superseded
    citation. § 10.16 re-derives, never edits, § 10.7's record — and the night sheet commits
    the training run to the document, so it may not point at the amendment that produced a
    document no candidate can be promoted against.
    """
    assert "§ 10.7" not in _flat(_runbook()), (
        "WHY THIS IS A FAILURE: the sheet still carries a live § 10.7 citation. The held-out "
        "split is re-derived by § 10.16 (Type 1, 2026-09-27); a sheet that names § 10.7 as "
        "fixing it sends the operator to the superseded document"
    )


def test_the_ledger_read_back_is_a_digest_equality_halt() -> None:
    """The ledger's held-out record is read against the committed document's digest.

    The gate runbook's Step 5 demands the record's held-out digest equal the committed
    document's, and the night sheet carries the same discipline at its own read-back: the
    run's ledger records the held-out document's digest, and the operator compares it to
    `tasks/heldout/source-b.json` before trusting the night.
    """
    assert "must equal the digest of the committed" in _flat(_runbook()), (
        "WHY THIS IS A FAILURE: the sheet's read-back never demands the ledger's held-out "
        "record equal the digest of the committed document. The digest equality is what makes "
        "the night a statement about the sealed document rather than about a path someone "
        "typed; without it a changed document is indistinguishable from a matching one"
    )


def test_run_ids_are_operator_declared_and_never_historical() -> None:
    """`probe-001` and `night-001` are real runs; a new run may not be pointed at them.

    Both are the sheet's own historical ids: probe-001's ledger is refused by every reader,
    and night-001's documents are covered by the never-rewrite rule. The operator declares
    each run's id before it starts — the same command must never produce a second run directory
    nobody chose — and the paths that follow a run resolve from the declared token.
    """
    blocks = _bash_blocks(_runbook())
    probe = next((block for block in _door_blocks(blocks) if "--probe" in block), "")
    night = _night_block(blocks)
    assert probe and night, "no bash block invokes the probe pass and the night"
    assert PROBE_RUN_ID != NIGHT_RUN_ID, "the two runs need two distinct run-id tokens"
    for label, block, token in (
        ("probe", probe, PROBE_RUN_ID),
        ("night", night, NIGHT_RUN_ID),
    ):
        values = _values(block)
        declared = values.get("--run-id", [])
        assert declared == [token], (
            f"WHY THIS IS A FAILURE: the {label} command declares --run-id {declared!r} and "
            f"the sheet must declare the operator's token {token!r}. A historical id points "
            "the run at an artifact that already exists — probe-001's ledger is refused, and "
            "night-001's documents are never rewritten"
        )
        workspace = values.get("--workspace", [])
        assert workspace and token in workspace[0], (
            f"WHY THIS IS A FAILURE: the {label} command's --workspace is {workspace!r} and "
            f"does not resolve from its declared run id {token!r}. The workspace follows the "
            "run; a fixed one belongs to no run and collides with the next"
        )
    historical = sorted(
        token
        for block in blocks
        for token in shlex.split(block, posix=True)
        if "probe-001" in token or "night-001" in token
    )
    assert not historical, (
        f"WHY THIS IS A FAILURE: the sheet's command blocks still name a historical run id "
        f"({historical!r}). probe-001's ledger is refused by every reader, and night-001's "
        "documents are never rewritten. Run ids are declared, never reused"
    )


def test_after_the_night_commands_check_leakage() -> None:
    """The leakage check is a command after the night, at the seam, before a candidate exists.

    The gate checks the same link at its own end, against the checkpoint; this step checks it
    at the source, over the night's dataset — document-only, no GPU — so a leak is named
    before a checkpoint is trained. It must appear after the night block: there is no run to
    check before the night has run.
    """
    blocks = _bash_blocks(_runbook())
    night = _night_block(blocks)
    assert night, "no bash block invokes the night without --probe"
    leak = _check_leakage_block(blocks)
    assert leak and LEAKAGE_CHECK in leak, (
        "WHY THIS IS A FAILURE: the sheet does not run `whetstone check-leakage` as a command. "
        "Without it the first leakage proof over the night's training set is the gate's — after "
        "a candidate exists — instead of a halt at the seam where the leak was written"
    )
    assert blocks.index(leak) > blocks.index(night), (
        "WHY THIS IS A FAILURE: the leakage check appears before the night it checks. There is "
        "no run directory to read until the night block has written one"
    )
    values = _check_leakage_values(leak)
    unknown = sorted(set(values) - _check_leakage_flags())
    assert not unknown, (
        f"WHY THIS IS A FAILURE: the check-leakage block passes {unknown} and the shipped "
        f"`check-leakage` defines none of them. Parser accepts: {sorted(_check_leakage_flags())}"
    )
    run_dir = f"$REPO/runs/nights/{NIGHT_RUN_ID}"
    assert values.get("--run") == [run_dir], (
        f"WHY THIS IS A FAILURE: the check-leakage block's --run is {values.get('--run')!r} "
        f"and the night's run directory is {[run_dir]!r}. The check must read the run the "
        "night block just produced, resolved from the same declared token"
    )
    assert values.get("--heldout") == [HELDOUT_DOC], (
        f"WHY THIS IS A FAILURE: the check-leakage block passes --heldout "
        f"{values.get('--heldout')!r} and the committed document is {[HELDOUT_DOC]!r}. A "
        "check against anything else proves nothing about the held-out membership"
    )


def test_the_denominator_states_the_heldout_exclusion() -> None:
    """The draw is the post-§ 10.16 arithmetic: the held-out band is subtracted too.

    The stale sentence — "61 private (66 \u2212 5 dev) + 1 public = 62" — leaves the held-out
    members in the draw, which is what made the training set non-clean by construction. The
    shipped order is dev overlay first, held-out second (`night.py:249-261`), and the
    arithmetic the operator reads must be its consequence.
    """
    text = _flat(_runbook())
    assert "51 private" in text and "52 tasks" in text, (
        "WHY THIS IS A FAILURE: the sheet does not state the re-derived draw — 51 private "
        "(66 \u2212 5 dev \u2212 10 held-out not already dev-excluded) + 1 public = 52 tasks, "
        "each drawn `K` times. The denominator is what the night's coverage claim is read against"
    )
    assert "61 private" not in text and "= 62 tasks" not in text, (
        "WHY THIS IS A FAILURE: the sheet still carries the pre-§ 10.16 denominator — "
        '"61 private (66 \u2212 5 dev) + 1 public = 62 tasks". That arithmetic counts the held-out '
        "members as drawable; a reader of the run's coverage would be told the wrong denominator"
    )


def test_the_heldout_overlap_ids_are_stated() -> None:
    """Two declared dev ids are held-out members now, and the sheet states the doctrine.

    Under § 10.16 the re-derived split makes `donor-b-353359e9ac6e` and `donor-b-3e3051c4192a`
    both dev ids and held-out members. A declared dev id inside the held-out band is
    exclusion, never a refusal (`night.py:227-230`): the id stays in `--dev-subset` — dropping
    it would silently shrink the exclusion — and the sheet says what the overlap means.
    """
    text = _flat(_runbook())
    for task_id in HELDOUT_OVERLAP:
        assert task_id in text, (
            f"WHY THIS IS A FAILURE: the sheet never states {task_id}, a declared dev id that "
            "is also a held-out member. The overlap is exclusion, never a refusal, and a reader "
            "must be able to see both roles from the sheet"
        )
    assert "exclusion, never" in text, (
        "WHY THIS IS A FAILURE: the sheet does not state the dev ∩ held-out doctrine — a "
        "declared dev id inside the held-out band is exclusion, never a refusal "
        "(`night.py:227-230`). Without it a reader who sees an overlap assumes the run is "
        "contradictory instead of deliberately double-excluding"
    )


def test_the_declared_dev_ids_exist_in_the_committed_corpus_record() -> None:
    """The five dev ids are corpus members of the record this checkout carries.

    The sheet's `--dev-subset` ids are only real while the committed record still holds them.
    A future re-mint renames them exactly as § 10.16's did, and this suite must fail in any
    checkout — before an operator's night does — so this reads the tracked record, not the
    sheet. The committed held-out document is read too: the two overlapping ids must remain
    members of the split the night excludes.

    **GREEN on arrival, by design.** The corpus is already re-minted; this pin's RED
    demonstration is the next re-mint, which has not happened.
    """
    import json

    ledger = json.loads(CORPUS_RECORD.read_text(encoding="utf-8"))
    heldout = json.loads(HELDOUT_DOCUMENT.read_text(encoding="utf-8"))
    ledger_ids = {task["task_id"] for task in ledger["tasks"]}
    missing = [task_id for task_id in DECLARED_DEV if task_id not in ledger_ids]
    assert not missing, (
        f"WHY THIS IS A FAILURE: the committed corpus record {CORPUS_RECORD.name} does not "
        f"carry dev ids {missing}. The corpus has been re-minted and the sheet's --dev-subset "
        "ids no longer exist — every command that passes them is refused by the door"
    )
    membership = set(heldout["membership"])
    not_held_out = [task_id for task_id in HELDOUT_OVERLAP if task_id not in membership]
    assert not not_held_out, (
        f"WHY THIS IS A FAILURE: the committed held-out document {HELDOUT_DOCUMENT.name} no "
        f"longer holds {not_held_out}. The split was re-derived and the ids the sheet states as "
        "held-out members are gone — the sheet's overlap statement is now false"
    )
    pre_mint = sorted(task_id for task_id in ledger_ids if PRE_MINT_ID.match(task_id))
    assert not pre_mint, (
        f"WHY THIS IS A FAILURE: the committed corpus record still carries pre-mint ids "
        f"{pre_mint}. The record has not been re-minted under labels, and every id the sheet "
        "passes comes from a corpus that no longer exists (or vice versa)"
    )
