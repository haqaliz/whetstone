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

Twenty properties, and the last fifteen are this sheet's own:

1. the parse really reads the sheet (anti-vacuity);
2. every flag either command passes exists in the shipped parser;
3. every path either command names is absolute;
4. no worktree is named anywhere, and no stale one survives;
5. the retry budget the sheet states is `gate.RETRY_COUNT` — the declared constant, by identity,
   so an amendment that moved `R` without updating the sheet fails here;
6. the promotion record's home is `gate.PROMOTIONS_DIR`, by identity;
7. the **machinery is verified before the real pair** — the gate's own fixture suites run
   first, so the first real evaluation is not also the first test of the machinery;
8. the liveness measurement is stated — the unverified count over its denominator, from the
   first evaluation onward (`docs/ROADMAP.md:451-452`);
9. the `UNVERIFIED` exit is stated as a published outcome with the roadmap's own response, and
   the sheet nowhere tells the operator to rerun until it passes;
10. the sheet names the **untrained base as the first incumbent** — a bash block that
    materializes it with `write_baseline_checkpoint` at an absolute checkpoint path, a gate
    command whose `--incumbent` is that same path and never a night checkpoint, the § 3
    boundary wording ("not the § 3 baseline measurement"), and no "two nights" anywhere;
11. the split the sheet pins is § 10.16's — the amendment (Type 1, 2026-09-27) that re-derived
    the held-out split under the scorable rule — and no live § 10.7 citation survives in the
    sheet's live instructions (a sheet that still names § 10.7 as fixing the split sends the
    operator to the document the gate cannot score; the history stays in git);
12. the scorable rule is stated where the split's provenance is — a member is held out only
    if its oracle can be built under the declared budget, the exclusion by class and sealed
    in the document's rule digest;
13. the digest-equality halt stands — step 5's read-back still demands the record's held-out
    digest equal the committed document's, and a changed document is a halt ("find out by
    whom"), never a rerun;
14. **leakage is checked before the gate** — the `check-leakage` block precedes the
    `whetstone gate` block, and the sheet says to halt on any non-zero exit;
15. every `docs/ROADMAP.md:<a>-<b>` cite lands on lines containing the phrase
    `ROADMAP_CITES` anchors it to, and no cite is unanchored;
16. the sheet names how the candidate's night is identified — the checkpoint's
    `provenance.json` `dataset_digest` equals the night's `dataset.json` `digest` — and calls
    that tie recorded, not verified;
17. the residual is stated — a clean check means "no shared task identity", never "no
    contamination" — and exit 2 includes a run that compared nothing;
18. a `check-leakage` refusal is a halt, never a pass;
19. the record read-back names `gate.PROMOTION_SCHEMA`, by identity, and the `training`
    block's fields;
20. the sheet says who writes the finding — the operator, from the record and the
    `check-leakage` output only, under `docs/planning/`, never `reports/`.

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

#: Every worktree any unit ever used. A worktree is removed the moment its unit merges, so a
#: sheet that names one sends the operator to a directory that no longer exists — including the
#: sheet's *own* unit's worktree, which is why no name here is exempt. The launch-chain sheets
#: run from the primary checkout instead, and name no worktree at all. Imported by identity by
#: the baseline and honest-number guards, so a name added here is retired everywhere at once.
STALE_WORKTREES = (
    "feat-gate-untrained-incumbent",
    "feat-baseline-measurement",
    "feat-honest-number-report",
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

    A phrase pin asserts a sentence the sheet wraps freely, and the wrap point is not a
    word: "…§ 10.16 (Type 1,\\n  2026-09-27)…" is the same sentence as its flattened
    form. The emphasis-strip precedent (`_assert_untrained_base_incumbent`) pins words
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
                if not _is_anchored(value)
            )
            assert not relative, (
                f"WHY THIS IS A FAILURE: `{door}` is given relative path(s) {relative}. The "
                "sheet is run verbatim from a stated CWD, and a path that resolves against the "
                "wrong directory fails as a refusal about the checkpoint rather than the command"
            )


def test_no_worktree_is_named_and_no_stale_one_survives() -> None:
    """Every worktree is deleted when its unit merges, so a sheet may name none.

    This guard used to require *exactly one* — this unit's — which stopped holding the
    moment the unit merged and cleanup removed the directory. The sheet is read long
    after its branch is gone; only the primary checkout survives.
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
        "directory that does not exist. Run from the primary checkout, with no --project"
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

    `docs/ROADMAP.md:451-452` makes liveness itself a measurement, and this sheet is where the
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


def test_the_chain_proves_the_night_did_not_leak() -> None:
    """`whetstone check-leakage` over the night that produced the candidate, in the chain.

    The gate scores the held-out membership; the leakage proof is what says that membership was
    never trained on. A promotion whose leakage was never checked is a promotion nobody may
    quote — and where in the chain it runs is the next guard's business.
    """
    blocks = _bash_blocks(_runbook())
    leak = _door_blocks(blocks, "whetstone check-leakage")

    assert leak, "WHY THIS IS A FAILURE: the chain never proves the night's disjointness"
    values = _values(leak[0], "whetstone check-leakage")
    assert values.get("--run"), "the leakage check names no run directory"
    assert values.get("--heldout"), "the leakage check names no held-out document"


def test_leakage_is_checked_before_the_gate_and_any_non_zero_exit_halts() -> None:
    """The leakage proof runs **before** the gate, and its non-zero exit stops the chain.

    The sheet once ran it after the gate, on the argument that the exit an operator acts on is
    the gate's. That ordering scores a candidate that may have trained on the very membership
    it is scored against, and leaves a promotion record on disk for a comparison that should
    never have been made. Checking first means a leaked candidate is never gated at all.
    """
    text = _runbook()
    blocks = _bash_blocks(text)
    leak = _door_blocks(blocks, "whetstone check-leakage")
    real = _door_blocks(blocks, "whetstone gate")
    assert leak and real, "the sheet must invoke both `whetstone check-leakage` and the gate"
    assert text.index(leak[0]) < text.index(real[0]), (
        "WHY THIS IS A FAILURE: the sheet gates the candidate before it proves the candidate's "
        "night did not train on the held-out membership. A leaked candidate scored against its "
        "own training data writes a promotion record for a comparison that was never fair"
    )
    assert "Halt on any non-zero exit" in _flat(text), (
        "WHY THIS IS A FAILURE: the sheet does not say to halt on any non-zero "
        "`check-leakage` exit. Exit 1 is a named leak and exit 2 is a refusal; neither is a "
        "licence to proceed to the gate"
    )


#: Every `docs/ROADMAP.md:<a>-<b>` the sheet cites, keyed by what the cite is *for*, with the
#: phrase those exact lines must contain. Line numbers drift with every roadmap edit; the phrase
#: is what makes the drift fail here instead of misleading the operator silently. A cite the
#: sheet makes that is not in this table fails too, so a new one cannot arrive unanchored.
#: Matched against the lines with whitespace collapsed and emphasis (`*`) removed.
ROADMAP_CITES = (
    ("the gate rule", 431, 433,
     "promote iff solved_new > solved_old AND regressed == 0 AND unverified == 0"),
    ("the gate's incumbent is not the § 3 baseline", 688, 693,
     "a disagreement is published as a finding, never reconciled"),
    ("the response when the gate cannot fire", 451, 453,
     "the fix is a more reliable sandbox, never a looser gate"),
    ("liveness is a measurement", 451, 452,
     "Liveness is itself a measurement. The unverified rate is reported from the first eval"),
    ("the leakage exit criterion", 459, 460,
     "`uv run whetstone check-leakage` exits 0 — zero overlap between the training set and "
     "the held-out set"),
)

ROADMAP = Path(__file__).parent.parent / "docs/ROADMAP.md"
CITE = re.compile(r"docs/ROADMAP\.md:(\d+)-(\d+)")


def test_every_roadmap_cite_points_at_the_rule_it_names() -> None:
    """A `ROADMAP.md:<a>-<b>` cite must land on lines that say what the sheet says they say.

    Four of this sheet's cites had drifted — the gate rule cited at the end of P2's status
    note, the § 3 boundary cited at the gate-untrained-incumbent paragraph — so an operator
    following a cite to check the sheet found a different rule. The table above anchors each
    one to its phrase.
    """
    text = _runbook()
    cited = {(int(a), int(b)) for a, b in CITE.findall(text)}
    assert len(cited) >= 4, (
        f"WHY THIS IS A FAILURE: the sheet parses into only {sorted(cited)} roadmap cites, so "
        "this guard would check almost nothing"
    )
    anchored = {(a, b) for _, a, b, _ in ROADMAP_CITES}
    unanchored = sorted(cited - anchored)
    assert not unanchored, (
        f"WHY THIS IS A FAILURE: the sheet cites docs/ROADMAP.md lines {unanchored} that no "
        "row of ROADMAP_CITES anchors. Either the cite is stale or it needs a row naming the "
        "phrase those lines must contain"
    )
    uncited = sorted(anchored - cited)
    assert not uncited, (
        f"WHY THIS IS A FAILURE: ROADMAP_CITES anchors {uncited} and the sheet cites none of "
        "them; a row with no cite guards nothing"
    )
    lines = ROADMAP.read_text(encoding="utf-8").splitlines()
    for purpose, start, end, phrase in ROADMAP_CITES:
        body = _flat(" ".join(lines[start - 1 : end])).replace("*", "")
        assert phrase in body, (
            f"WHY THIS IS A FAILURE: the sheet cites docs/ROADMAP.md:{start}-{end} for "
            f"{purpose!r}, and those lines do not contain {phrase!r}. They read: {body!r}"
        )


def _leak_and_gate() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    blocks = _bash_blocks(_runbook())
    leak = _values(_door_blocks(blocks, "whetstone check-leakage")[0], "whetstone check-leakage")
    gate = _values(_door_blocks(blocks, "whetstone gate")[0], "whetstone gate")
    return leak, gate


def test_the_leakage_block_names_the_gates_candidate_as_its_checkpoint() -> None:
    """`--checkpoint` is typed in the check-leakage block and names the gate's `--candidate`.

    A leakage proof over the wrong night proves nothing about the candidate; the typed example
    must tie the two doors mechanically, and name the same night on both.
    """
    leak, gate = _leak_and_gate()
    assert "--checkpoint" in leak and len(leak["--checkpoint"]) == 1, (
        "WHY THIS IS A FAILURE: the check-leakage block carries no --checkpoint, so nothing "
        "mechanical ties the checked night to the candidate and the operator compares by eye"
    )
    assert Path(leak["--checkpoint"][0]).name == Path(gate["--candidate"][0]).name, (
        f"WHY THIS IS A FAILURE: leakage names checkpoint {leak['--checkpoint'][0]!r} but the "
        f"gate scores {gate['--candidate'][0]!r}; the typed example must name one candidate"
    )
    assert Path(leak["--run"][0]).name == Path(gate["--candidate"][0]).name, (
        f"WHY THIS IS A FAILURE: leakage runs over {leak['--run'][0]!r} and the gate scores "
        f"{gate['--candidate'][0]!r}; the typed example must name the same night on both doors"
    )


def test_the_sheet_says_a_v2_checkpoints_link_is_sealed() -> None:
    """The v2 statement is its own sentence: a `whetstone-checkpoint/2` link is sealed."""
    flat = _flat(_runbook()).replace("*", "")
    assert (
        "For a v2 checkpoint (`whetstone-checkpoint/2`) the recorded digest is sealed" in flat
    ), "WHY THIS IS A FAILURE: the sheet never says a v2 checkpoint's dataset link is sealed"


def test_the_sheet_says_a_v1_checkpoints_link_is_recorded_not_sealed() -> None:
    """The v1 statement: a v1 checkpoint's link is recorded, not sealed."""
    flat = _flat(_runbook()).replace("*", "")
    assert "For a v1 checkpoint it is recorded, not sealed" in flat, (
        "WHY THIS IS A FAILURE: the sheet never says a v1 checkpoint's dataset link is "
        "recorded, not sealed"
    )


def test_the_sheet_says_sealed_is_tamper_evidence_not_authentication() -> None:
    """What sealed means: tamper-evidence against an edit that does not recompute the digest."""
    flat = _flat(_runbook()).replace("*", "")
    assert "Sealed means tamper-evidence against an edit that does not also recompute" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not say what sealed means"
    )
    assert "it is not authentication" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not say sealed is not authentication"
    )


def test_the_sheet_says_the_runs_dataset_json_is_sealed_when_v2() -> None:
    """The run's side is conditional: sealed for a v2 dataset, recorded for a v1 one.

    The standing "is not sealed" sentence is false for a v2 dataset, so the sheet states both
    generations rather than one — and never calls the link verified (`sealed` is tamper-evidence).
    """
    flat = _flat(_runbook())
    assert (
        "For a v2 dataset (`whetstone-training-set/2`) the run's `dataset.json` is itself "
        "sealed and the command says so; for a v1 dataset it is recorded, not sealed."
    ) in flat, (
        "WHY THIS IS A FAILURE: the sheet does not state the run's dataset.json seal state "
        "conditionally (sealed when v2, recorded when v1)"
    )


def test_the_sheet_says_a_non_zero_leakage_exit_halts_before_the_gate() -> None:
    flat = _flat(_runbook())
    assert (
        "A non-zero exit halts the operator before the gate, which is not run until this exits 0"
        in flat
    ), (
        "WHY THIS IS A FAILURE: the sheet does not say a non-zero check-leakage exit halts "
        "the operator before the gate"
    )


def test_the_sheet_never_calls_the_dataset_link_verified() -> None:
    """The stale "recorded, not verified" is gone, and no tie/link/digest sentence says verified.

    Case-sensitive with word boundaries, so UNVERIFIED and "unverified" (the gate's own terms)
    are not hits.
    """
    flat = _flat(_runbook()).replace("*", "")
    assert "recorded, not verified" not in flat, (
        "WHY THIS IS A FAILURE: the stale phrase 'recorded, not verified' still describes the "
        "dataset link; it is sealed (v2) or recorded, not sealed (v1)"
    )
    hit = re.search(r"\b(?:tie|link|digest)\b[^.]{0,80}\bverified\b", flat)
    assert hit is None, (
        "WHY THIS IS A FAILURE: the sheet calls the dataset link verified "
        f"({hit.group(0)!r}); sealed is tamper-evidence, not authentication"
        if hit
        else ""
    )


def test_the_sheet_states_what_a_clean_leakage_check_does_not_mean() -> None:
    """Identity is all `check-leakage` compares, and exit 2 includes "compared nothing".

    A clean exit means no shared task identity; a near-duplicate task under a different
    identity is not detected. And a run whose training set held no source B example compared
    nothing — that is a refusal, exit 2, never a clean result (Amendment 2 of the
    gate-leakage-guard PRD).
    """
    flat = _flat(_runbook())
    assert '"no shared task identity", never "no contamination"' in flat, (
        "WHY THIS IS A FAILURE: the sheet does not state the residual — a clean check means "
        '"no shared task identity", never "no contamination"'
    )
    assert "near-duplicate" in flat, (
        "WHY THIS IS A FAILURE: the sheet never names what identity matching cannot see — a "
        "near-duplicate task under a different identity"
    )
    assert "a run that compared nothing (no source B training example) is exit 2" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not say that a run which compared nothing is a "
        "refusal (exit 2). An operator who reads exit 2 as only a typo misses the case where "
        "no identity was ever checked"
    )


def test_a_leakage_refusal_is_a_halt_and_never_a_pass() -> None:
    """Exit 2 halts the chain, and a check that did not run is never read as one that passed."""
    flat = _flat(_runbook())
    assert "Exit 2 is a halt" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not say that a `check-leakage` refusal halts "
        "the chain before the gate"
    )
    assert "A refusal is never a pass" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not say that a refusal or a 'not checked' is "
        "never treated as a pass. That reading is the one that would gate a leaked candidate"
    )


def test_the_record_read_back_names_the_shipped_schema_and_its_training_block() -> None:
    """The read-back names `gate.PROMOTION_SCHEMA` by identity and the `training` block's fields.

    The record is now schema `/3`: each side carries what trained it (since `/2`) and whether
    that link was sealed (`/3`). A sheet that reads back an older record shape skips the block
    that says which dataset the candidate trained on, or whether that claim was sealed.
    """
    flat = _flat(_runbook())
    assert gate.PROMOTION_SCHEMA in flat, (
        f"WHY THIS IS A FAILURE: the sheet's read-back does not name {gate.PROMOTION_SCHEMA!r}, "
        "the schema the gate writes and the readers accept"
    )
    missing = sorted(
        field for field in gate._PROMOTION_TRAINING_FIELDS if f"`{field}`" not in flat
    )
    assert "`training`" in flat and not missing, (
        f"WHY THIS IS A FAILURE: the read-back does not name the `training` block and its "
        f"fields (missing {missing}). It is what records which dataset trained each side"
    )


def test_the_sheet_says_who_writes_the_finding_and_where() -> None:
    """The operator writes the finding, from the record and the leakage output only.

    Its home is `docs/planning/`, never `reports/`: a gated evaluation publishes no figure.
    """
    flat = _flat(_runbook())
    for phrase in (
        "The finding is written by the operator",
        "from the promotion record and the `check-leakage` output only",
        "under `docs/planning/`, never `reports/`",
    ):
        assert phrase in flat, (
            f"WHY THIS IS A FAILURE: the sheet does not say {phrase!r}. Without it the first "
            "gate result has no stated author, source or home"
        )


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
        "(`write_baseline_checkpoint`). `docs/ROADMAP.md:673-683` made the untrained base the "
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
    assert _is_anchored(base_path), (
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
    assert _is_anchored(incumbent), (
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
        "(`docs/ROADMAP.md:688-693`). A sheet that blurs the two invites the first "
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
    `docs/ROADMAP.md:673-683` reordered the launch path — the first incumbent is the untrained
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


def test_the_sheet_cites_the_amendment_that_re_derived_the_split() -> None:
    """Step 5's digest read-back pins the split to § 10.16, not to the amendment it supersedes.

    The sheet named `PREREGISTRATION.md` § 10.7 (Type 1, 2026-08-24) as fixing the held-out
    split. § 10.16 (Type 1, 2026-09-27) re-derives that split under the scorable rule — the
    old document carried members whose oracles could not be built under the sealed budget, so
    no candidate could ever be promoted against it — and the read-back is the one sentence
    that says which document the digest must equal. A sheet that still points at § 10.7 sends
    the operator to the superseded document.

    **Watched failing first:** the assertion was run against a stub sheet that kept the § 10.7
    sentence and against the current sheet; both failed with this message before the sheet
    moved.
    """
    assert (
        "whose split is fixed by `PREREGISTRATION.md` § 10.16 (Type 1, 2026-09-27)"
        in _flat(_runbook())
    ), (
        "WHY THIS IS A FAILURE: the sheet does not cite § 10.16 (Type 1, 2026-09-27) as fixing "
        "the held-out split. The split is re-derived under the scorable rule by that amendment, "
        "and a sheet that names any other provenance sends the operator to the document the "
        "gate cannot score"
    )


def test_no_live_citation_of_the_superseded_amendment_survives() -> None:
    """A sheet that still names § 10.7 as fixing the split describes a dead document.

    The history stays in git; the sheet's live instructions must not carry the superseded
    citation. § 10.16 re-derives, never edits, § 10.7's record — and the gate runbook is
    where an operator meets the split, so it is the one sheet that may not point at the
    amendment that produced a document no candidate can be promoted against.

    **Watched failing first:** the assertion was run against a stub sheet that kept the § 10.7
    sentence and against the current sheet; both failed with this message before the sheet
    moved.
    """
    assert "§ 10.7" not in _flat(_runbook()), (
        "WHY THIS IS A FAILURE: the sheet still carries a live § 10.7 citation. The held-out "
        "split is re-derived by § 10.16 (Type 1, 2026-09-27); a sheet that names § 10.7 as "
        "fixing it sends the operator to the superseded document"
    )


def test_the_sheet_states_the_scorable_rule() -> None:
    """Why the split changed, in the operator's own words: the rule, not the membership.

    The re-derivation's whole point is the scorable rule: a member is held out only if its
    oracle can be built under the declared budget. The exclusion is by class — the rule
    lives as a digest-sealed function, so an edit to the rule invalidates the document by
    design — and the sheet must state that where the split's provenance is, or the operator
    cannot tell a rule exclusion from a hand-picked membership.

    **Watched failing first:** both assertions were run against a stub sheet that kept the
    § 10.7 sentence and against the current sheet; both failed with their messages before
    the sheet moved.
    """
    text = _flat(_runbook())
    assert "held out only if its oracle can be built under the declared budget" in text, (
        "WHY THIS IS A FAILURE: the sheet never states the scorable rule — a member is held "
        "out only if its oracle can be built under the declared budget. That is the rule § 10.16 "
        "re-derives the split under, and the operator reading the membership needs it stated"
    )
    assert "sealed in the document's rule digest" in text, (
        "WHY THIS IS A FAILURE: the sheet never states that the exclusion is sealed in the "
        "document's rule digest. The rule lives as a digest-sealed function, so an edit to it "
        "invalidates the document by design — the exclusion is by class and sealed, never a "
        "hand-picked membership"
    )


def test_the_sheet_still_refuses_a_changed_document_as_a_halt() -> None:
    """The digest-equality halt stands: a changed document is a halt, never a rerun.

    Step 5's read-back demands the record's held-out digest equal the committed document's,
    and halt condition 1 names the response when it does not: find out who changed it. The
    re-derived document must not smuggle in a looser reading — an operator who may rerun a
    digest mismatch until it passes has turned the refusal into a rerun loop.

    **Watched failing first:** both assertions were run against a stub sheet whose halt
    condition lost the digest-mismatch response; each failed with its message before the
    sheet moved.
    """
    text = _flat(_runbook())
    assert "it must equal the digest of the committed" in text, (
        "WHY THIS IS A FAILURE: step 5 no longer demands the record's held-out digest equal "
        "the committed document's. The digest-equality read-back is what makes the decision a "
        "statement about the sealed document"
    )
    assert "the response is to find out by whom" in text, (
        "WHY THIS IS A FAILURE: the sheet no longer names the digest-mismatch response — find "
        "out who changed the document. A changed document is a halt, never a rerun"
    )
