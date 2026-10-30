"""Guards over the Torch/MPS night sheet, so its commands cannot drift from the door they invoke.

`docs/planning/torch-mps-series/night-door/runbook.md` is the operator's sheet for the Torch/PEFT
series on the Mac's MPS. It is a second series, not an edit of the MLX sheet: the MLX guard
(`tests/test_night_runbook_guards.py`) is hardcoded to that sheet and pins a 32B candidate with the
7B **excluded** by name. This series returns to the 8B under a bounded repair contract
(§ 10.23). One guard module per sheet is the precedent (`test_probe_runbook_guards.py`,
`test_larger_base_runbook_guards.py`,
`test_gate_runbook_guards.py`): the command-independent parse helpers are imported **by identity**,
asserted `is`, and only the door-keyed ones are re-implemented against this sheet's command.

Properties this sheet owns, in addition to the shape the MLX guard pins:

1. the parse really reads the sheet: exactly two door blocks (probe + night), `--probe 2` on the
   probe and no `--probe` on the night;
2. every flag the door, `check-probe` and `check-leakage` blocks pass exists in the shipped parser;
3. `--runs`/`--checkpoints`/`--workspace` are absolute or `$REPO`-anchored, `$REPO` is exported,
   and no worktree is named anywhere;
4. both doors name `--runtime torch` and run under the torch extra (`uv run --extra torch`);
5. the retained candidate is the 8B repair base, passed exactly once in `--only`, and no
   `mlx-community` value appears in any `--only`;
6. the MPS read-back is commanded in the sheet's own words (`backend.name == "torch"`,
   `backend.device == "mps"`, `backend.precision == "float16"`), because `check-probe` does not pin
   the backend;
7. the fit caveat: the probe writes no checkpoint and does not validate training; the `train-arm`
   pre-flight is the 8B fit measurement;
8. the 52-task denominator (51 private + 1 public), the five declared dev ids, the committed
   held-out document on both doors and on `check-probe`, and the resume rule;
9. the night re-mines from the operator-declared donor; the probe does not;
10. operator-declared run ids (never `probe-001`/`night-001`), the finding home under
    `docs/planning/`, no `/reports/` value, and the § 10.23 citation;
11. the public task is provisioned offline: a flask mirror export, `UV_OFFLINE=1`, the probe's
    digest dir pre-warmed into the night workspace, and `caffeinate -dimsu` on both doors.
"""

from __future__ import annotations

import argparse
import re
import shlex
from pathlib import Path

from test_runbook_guards import (
    _bash_blocks,
    _exports_repo,
    _is_anchored,
    _named_paths,
    _worktree_name,
)

from whetstone.cli import build_parser

#: The sheet under guard.
RUNBOOK = (
    Path(__file__).parent.parent / "docs/planning/torch-mps-series/night-door/runbook.md"
)

#: The command every block that invokes the door begins with. It is this sheet's own constant
#: rather than the MLX guard's, because a guard that reaches into another guard's globals can
#: silently repoint the sheet it was watching.
DOOR = "whetstone run --night"

#: The go/no-go command between the probe and the night, and the post-night leakage check. Both
#: are `whetstone` subcommands of their own, so they are keyed here rather than by the DOOR.
PROBE_CHECK = "whetstone check-probe"
LEAKAGE_CHECK = "whetstone check-leakage"

#: The torch-only environment the whole sheet runs under: the primary venv is mixed and carries
#: the arm's ad-hoc installs, so the extra is named on every command.
ENVIRONMENT = "uv run --extra torch"

#: Both doors are wrapped in `caffeinate`: two nights drew every rollout and then found the
#: network gone at the one public task, because the Mac slept. `-s` holds only on AC power.
CAFFEINATE = "caffeinate -dimsu"

#: The one public task's canonical URL and the operator's local bare mirror of it. The mirror is
#: an explicit input the run inherits, never ambient git config (`_git`'s isolation stays).
FLASK_URL = "https://github.com/pallets/flask.git"
MIRROR = "$REPO/runs/flask-mirror.git"

#: The digest dir `provision` keys the committed public manifest's pins to. A literal, because
#: the digest excludes the repo and commit: a pin change must re-clone, and fail offline.
PUBLIC_DIGEST = "b885fb84763091db"

#: The candidate this series retains. The base must be the plain HF repo — the on-disk MLX 4-bit
#: directories are not Torch-loadable — and the full id is the value that cannot also match an
#: MLX directory in the substring matcher.
CANDIDATE = "Qwen/Qwen3-8B"

#: The immutable base revision `PREREGISTRATION.md` § 10.23 pins. The sheet must carry the same
#: string, so a fetched `main` that moved is refused by the door's re-hash rather than by memory.
REVISION = "b968826d9c46dd6066d109eabc6255188de91218"

#: The five dev ids the hardened contract declared (`PREREGISTRATION.md` § 10.4), in the
#: post-§ 10.16 corpus form. Two of them are also held-out members; the sheet states both roles.
DECLARED_DEV = (
    "donor-b-2e149603209a",
    "donor-b-353359e9ac6e",
    "donor-b-3e3051c4192a",
    "donor-b-844db07ed482",
    "donor-b-9dba3ea557f5",
)

#: The committed held-out document the doors and the go/no-go command pass; its membership and
#: digest do not move with the base or the runtime.
HELDOUT_DOC = "$REPO/tasks/heldout/source-b.json"

#: The operator-declared donor the night re-mines, exported exactly as `$REPO` is.
DONOR = "$DONOR"

#: The four flags the night block adds for the re-mine, which the probe must not carry.
REMINE_FLAGS = ("--remine", "--remine-label", "--remine-out", "--remine-limit")

#: The two run-id tokens the operator declares at run time — one per run, never a historical id.
PROBE_RUN_ID = "<torch-probe-run-id>"
NIGHT_RUN_ID = "<torch-night-run-id>"
HISTORICAL_IDS = ("probe-001", "night-001")

#: The finding's home. The gate record stays gitignored; the finding is a planning document.
FINDING = "docs/planning/torch-mps-series/finding.md"

#: Which of the door's flags name something the run writes to.
WRITABLE = ("--runs", "--checkpoints", "--workspace")

FLAG = re.compile(r"--[a-z][a-z0-9-]*")


def _exports_donor(text: str) -> bool:
    """The sheet must define `$DONOR` as an absolute path, or the donor anchor anchors nothing."""
    return "export DONOR=/" in text


def _flat(text: str) -> str:
    """The sheet's words with runs of whitespace collapsed, so a wrapped sentence pin holds."""
    return re.sub(r"\s+", " ", text)


def _runbook() -> str:
    assert RUNBOOK.is_file(), (
        f"{RUNBOOK} is absent, so every guard in this module would fail on a read rather than "
        "pin a sheet. The Torch/MPS series has no command surface until it exists."
    )
    text = RUNBOOK.read_text(encoding="utf-8")
    assert text.strip(), (
        f"{RUNBOOK} is empty, so every guard in this module would pass vacuously. A command "
        "sheet that parses into nothing proves nothing."
    )
    return text


def _door_blocks(blocks: list[str]) -> list[str]:
    """Every block that invokes the night door. There are two: the probe pass and the night."""
    return [block for block in blocks if DOOR in block]


def _probe_block(blocks: list[str]) -> str:
    """The probe pass: the door block that carries `--probe`."""
    return next((block for block in _door_blocks(blocks) if "--probe" in block), "")


def _night_block(blocks: list[str]) -> str:
    """The night itself: the door block that does not carry `--probe`."""
    return next((block for block in _door_blocks(blocks) if "--probe" not in block), "")


def _flags(block: str) -> set[str]:
    """The `--flag` tokens handed to the door, ignoring `uv`'s own `--extra`."""
    return set(FLAG.findall(block.partition(DOOR)[2]))


def _values(block: str, command: str = DOOR) -> dict[str, list[str]]:
    """Flag → every value it was given, from the tokens after the invocation.

    Values are lists because `--tasks`, `--dev-subset` and `--only` are repeatable: a
    last-one-wins parse would silently drop four of the five declared dev ids.
    """
    tokens = shlex.split(block.partition(command)[2], posix=True)
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
    """Every option string the shipped `subcommand` accepts."""
    parser = build_parser()
    subparsers = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    assert subparsers, "the CLI defines no subcommands, so this guard would compare against nothing"
    return {
        option
        for action in subparsers[0].choices[subcommand]._actions
        for option in action.option_strings
    }


def _probe_check_block(blocks: list[str]) -> str:
    return next((block for block in blocks if PROBE_CHECK in block), "")


def _check_leakage_block(blocks: list[str]) -> str:
    return next((block for block in blocks if LEAKAGE_CHECK in block), "")


def test_the_guard_shares_the_parse_helpers_it_can() -> None:
    """One parse implementation for the command-independent parts, imported by identity."""
    from test_runbook_guards import _bash_blocks as shared_blocks
    from test_runbook_guards import _exports_repo as shared_exports
    from test_runbook_guards import _is_anchored as shared_anchor
    from test_runbook_guards import _named_paths as shared_paths
    from test_runbook_guards import _worktree_name as shared_worktree

    assert _bash_blocks is shared_blocks
    assert _named_paths is shared_paths
    assert _worktree_name is shared_worktree
    assert _is_anchored is shared_anchor
    assert _exports_repo is shared_exports


def test_the_parse_really_reads_the_runbooks_command() -> None:
    """Anti-vacuity: an emptied or renamed sheet must fail loudly rather than pass.

    Every assertion below is a statement about the members of a parsed set, so an empty parse
    satisfies all of them at once.
    """
    blocks = _bash_blocks(_runbook())
    assert len(_door_blocks(blocks)) == 2, (
        "WHY THIS IS A FAILURE: the sheet does not carry exactly two door invocations (the probe "
        f"pass and the night). Found {len(_door_blocks(blocks))}"
    )
    probe = _probe_block(blocks)
    night = _night_block(blocks)
    assert probe and DOOR in probe, "no bash block invokes the probe pass"
    assert night and DOOR in night, "no bash block invokes the night without --probe"
    assert _values(probe).get("--probe") == ["2"], (
        "the probe pass does not pass `--probe 2`; a probe that draws elsewhere is a different run"
    )
    assert "--probe" not in _values(night), "the night block still carries `--probe`"
    assert _flags(night), "the night command parsed into no flags at all"


def test_every_flag_the_commands_pass_exists_in_the_parser() -> None:
    """A flag the door does not define is a usage error at 2 a.m., after the setup is done."""
    blocks = _bash_blocks(_runbook())
    for block in _door_blocks(blocks):
        unknown = sorted(_flags(block) - _parser_flags("run"))
        assert not unknown, (
            f"WHY THIS IS A FAILURE: the sheet passes {unknown} and `whetstone run` defines none "
            f"of them. Parser accepts: {sorted(_parser_flags('run'))}"
        )
    for label, block, command, subcommand in (
        ("check-probe", _probe_check_block(blocks), PROBE_CHECK, "check-probe"),
        ("check-leakage", _check_leakage_block(blocks), LEAKAGE_CHECK, "check-leakage"),
    ):
        assert block, f"the sheet runs no `{label}` block"
        unknown = sorted(set(_values(block, command)) - _parser_flags(subcommand))
        assert not unknown, (
            f"WHY THIS IS A FAILURE: the {label} block passes {unknown} and the shipped "
            f"`{subcommand}` defines none of them. Parser accepts: "
            f"{sorted(_parser_flags(subcommand))}"
        )


def test_the_door_commands_writable_paths_are_anchored() -> None:
    """A relative `--workspace` does not resolve in the provisioning subprocesses."""
    for block in _door_blocks(_bash_blocks(_runbook())):
        values = _values(block)
        for flag in WRITABLE:
            named = values.get(flag, [])
            assert named, (
                f"WHY THIS IS A FAILURE: the door command passes no {flag}. It is required, "
                "and a command that omits it does not run at all"
            )
            for value in named:
                assert _is_anchored(value), (
                    f"WHY THIS IS A FAILURE: {flag} is relative ({value!r}). The measured arm "
                    "died exactly this way — every rollout came back UNPROVISIONED"
                )


def test_the_sheet_names_no_worktree_anywhere() -> None:
    """The sheet runs from the primary checkout, because every worktree is eventually deleted."""
    text = _runbook()
    assert ".claude/worktrees/" not in text, (
        "WHY THIS IS A FAILURE: the sheet names a worktree path. Worktrees are removed when "
        "their unit merges, so an operator running this sheet verbatim hits a missing directory"
    )
    named = {
        name
        for line in text.splitlines()
        for path in _named_paths(line)
        if (name := _worktree_name(path)) is not None
    }
    assert named == set(), f"WHY THIS IS A FAILURE: the sheet names worktree(s) {sorted(named)}"
    assert _exports_repo(text), (
        "WHY THIS IS A FAILURE: the sheet anchors its paths to `$REPO` and never exports it. An "
        "unset variable expands to nothing and every path silently becomes relative"
    )


def test_both_doors_name_the_torch_runtime_in_the_torch_environment() -> None:
    """The runtime is named, not detected: the primary venv may carry both engines."""
    blocks = _bash_blocks(_runbook())
    for block in _door_blocks(blocks):
        assert f"{ENVIRONMENT} {DOOR}" in block, (
            f"WHY THIS IS A FAILURE: a door block does not run under `{ENVIRONMENT} {DOOR}`. "
            "The mixed venv refuses an unnamed runtime, and a Torch night under the MLX "
            "environment is not the run the amendment pinned"
        )
        assert _values(block).get("--runtime") == ["torch"], (
            f"WHY THIS IS A FAILURE: the door command's --runtime is "
            f"{_values(block).get('--runtime')!r}; the Torch/MPS series names torch"
        )
    for label, block in (
        ("check-probe", _probe_check_block(blocks)),
        ("check-leakage", _check_leakage_block(blocks)),
    ):
        assert block and ENVIRONMENT in block, (
            f"WHY THIS IS A FAILURE: the {label} block does not run under `{ENVIRONMENT}`"
        )


def test_both_doors_hold_the_machine_awake() -> None:
    """A night is 5-6 hours; the Mac slept and the public task's clone lost its network.

    The prefix is on the door blocks only: `check-probe` and `check-leakage` read local files and
    finish in seconds. `-s` holds only while the machine is on power; `-d/-i/-m/-u` still apply.
    """
    for block in _door_blocks(_bash_blocks(_runbook())):
        assert block.startswith(f"{CAFFEINATE} {ENVIRONMENT} {DOOR}"), (
            f"WHY THIS IS A FAILURE: a door block does not begin with `{CAFFEINATE} "
            f"{ENVIRONMENT} {DOOR}`. The public task is processed last; a sleeping Mac dropped "
            "the network after 832 rollouts and the whole night was UNVERIFIED"
        )


def test_the_sheet_can_provision_the_public_task_offline() -> None:
    """The mirror is an export, not git config, and the printf form lets `$REPO` expand."""
    text = _runbook()
    flat = _flat(text)
    assert f'git clone --mirror {FLASK_URL} "{MIRROR}"' in flat, (
        "WHY THIS IS A FAILURE: the sheet does not name the one human-run network step — "
        f"`git clone --mirror {FLASK_URL} \"{MIRROR}\"` — so the mirror the run reads is "
        "never refreshed from the canonical URL"
    )
    assert (
        "export WHETSTONE_REPO_MIRRORS=$(printf "
        f"'{{\"{FLASK_URL}\":\"%s/runs/flask-mirror.git\"}}' \"$REPO\")"
    ) in flat, (
        "WHY THIS IS A FAILURE: the sheet does not export WHETSTONE_REPO_MIRRORS as a JSON "
        "mapping of the canonical flask URL to the mirror, built with printf so `$REPO` expands. "
        "Without the mapping the control arm and oracle clone the unreachable URL"
    )
    assert "export UV_OFFLINE=1" in text, (
        "WHY THIS IS A FAILURE: the sheet does not set UV_OFFLINE=1. A cold uv cache would reach "
        "an index mid-night instead of failing loudly before the run"
    )


def test_the_sheet_pre_warms_the_public_digest_dir() -> None:
    """The digest dir is the `provision` half; the mirror covers every `materialise` clone."""
    flat = _flat(_runbook())
    assert (
        f'cp -a "$REPO/runs/{PROBE_RUN_ID}-workspace/environments/{PUBLIC_DIGEST}" '
        f'"$REPO/runs/{NIGHT_RUN_ID}-workspace/environments/"'
    ) in flat, (
        "WHY THIS IS A FAILURE: the sheet does not copy the probe's public digest dir "
        f"`{PUBLIC_DIGEST}` into the night workspace. The literal is the committed manifest's "
        "`Interpreters` key; a copied-at-run-time path is a digest that can change silently"
    )


def test_the_workspace_may_hold_only_the_pre_warmed_digest_dir() -> None:
    """The old 'must be empty' sentence contradicts the pre-warm; say the exception."""
    text = _runbook()
    flat = _flat(text)
    assert "empty except the pre-warmed public digest dir" in flat, (
        "WHY THIS IS A FAILURE: the sheet still says the night workspace must be empty, which "
        "the pre-warm makes false. The exception must be stated, or an operator deletes the "
        "paid-for digest dir before the night"
    )
    assert "need no pre-warm" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not say the private tasks need no pre-warm. They "
        "clone local donors, and an operator copying digest dirs for them has wasted the step"
    )
    for token in HISTORICAL_IDS:
        assert token not in text, (
            f"WHY THIS IS A FAILURE: the sheet names the historical run id {token!r}. The pre-warm "
            "addresses the operator's own `<torch-probe-run-id>`; a past run's workspace is not "
            "this run's evidence"
        )


def test_both_doors_retain_the_8b_repair_base() -> None:
    """The 8B repair arm is the retained candidate here, unlike the MLX sheet's named exclusion.

    The MLX exclusion is a measured statement about the MLX 4-bit directory's zero ceiling, not
    about Torch/MPS; copying it would exclude the only class that fits the MPS headroom.
    """
    text = _flat(_runbook())
    assert CANDIDATE in text, "the sheet never names the retained 8B repair base"
    assert REVISION in text, (
        "WHY THIS IS A FAILURE: the sheet never names the immutable base revision § 10.23 pins. "
        "A fetch of `main` that moved is exactly what the revision and the per-file hashes exist "
        "to refuse"
    )
    assert "retained" in text.lower(), (
        "WHY THIS IS A FAILURE: the sheet never says the 8B is retained. A resolution decided in "
        "someone's head is one that can be re-decided after a result"
    )
    assert "25.6 GB" in text and "headroom" in text, (
        "WHY THIS IS A FAILURE: the sheet does not state the MPS headroom the base was chosen "
        "against, so the 14B/32B exclusion is an opinion rather than arithmetic"
    )
    for block in _door_blocks(_bash_blocks(_runbook())):
        assert _values(block).get("--repair") == ["2"], (
            "WHY THIS IS A FAILURE: a door does not pass `--repair 2`. The repair contract's "
            "budget is a frozen input; a command without it draws under a contract the "
            "amendment did not pin"
        )
    for block in _door_blocks(_bash_blocks(_runbook())):
        only = _values(block).get("--only", [])
        assert only == [CANDIDATE], (
            f"WHY THIS IS A FAILURE: --only is {only!r} and the sheet retains exactly "
            f"[{CANDIDATE!r}]. A night trains one candidate"
        )
        assert all("mlx-community" not in value for value in only), (
            f"WHY THIS IS A FAILURE: --only names {only!r}, an MLX 4-bit directory. The MLX "
            "weights are not Torch-loadable, and the substring matcher refuses two candidates"
        )


def test_the_sheet_pins_the_torch_floor() -> None:
    """#86: torch 2.14.0 lost the Metal command buffer; 2.14.1 ran the pre-flight clean."""
    flat = _flat(_runbook())
    assert "torch floor is **2.14.1**" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not pin the torch floor. The 8B night ran 2.14.0 "
        "and lost its Metal command buffer after ~35 h, then failed on a corrupted attention mask"
    )
    assert "2.14.0" in flat and "#86" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not name the version that crashed and the defect "
        "record. A pin without the reason is one that gets lowered after the next result"
    )


def test_the_sheet_reads_the_mps_backend_back() -> None:
    """`check-probe` pins the backend now, and the sheet still reads it back.

    The command pin and the operator's read-back are independent checks: the pin makes a
    mis-provisioned probe exit 1, and the read-back lets the operator see the recorded values
    before the night commits. Both the flags and the values the amendment pinned must be in
    the sheet.
    """
    text = _runbook()
    flat = _flat(text)
    block = _probe_check_block(_bash_blocks(text))
    for phrase in ("--runtime torch", "--device mps", "--precision float16"):
        assert phrase in block, (
            f"WHY THIS IS A FAILURE: the sheet's check-probe block does not pass {phrase!r}. "
            "The § 10.25 probe is a Torch/MPS/float16 run, and the door can only refuse a "
            "mismatch if the sheet names the pins"
        )
    for phrase in (
        'backend.name == "torch"',
        'backend.device == "mps"',
        'backend.precision == "float16"',
    ):
        assert phrase in flat, (
            f"WHY THIS IS A FAILURE: the sheet never demands {phrase} from the run's ledger. "
            "The pin and the read-back are independent checks"
        )
    assert "pins it too" in flat, (
        "WHY THIS IS A FAILURE: the sheet still says `check-probe` does not pin the backend. "
        "It now does, and the read-back is the cross-check"
    )


def test_both_doors_are_supervised() -> None:
    """Every `run --night` block is wrapped by the stall supervisor.

    A hang is the one failure an in-process timeout cannot break; the parent is the breaker.
    The sheet's two doors must use it, with the declared interval.
    """
    blocks = _door_blocks(_bash_blocks(_runbook()))

    assert blocks, "the sheet has no `run --night` block"
    for block in blocks:
        assert "--supervise" in block, (
            "WHY THIS IS A FAILURE: a door runs without the supervisor; an MPS hang would "
            "again take the whole run and its final ledger with it"
        )
        assert _values(block).get("--stall-seconds") == ["3600"], (
            "WHY THIS IS A FAILURE: the door does not declare the supervisor's interval"
        )


def test_the_sheet_states_the_fit_caveat() -> None:
    """A green probe is not an 8B fit check; the `train-arm` pre-flight is the measurement."""
    flat = _flat(_runbook())
    for phrase in (
        "writes no checkpoint",
        "does not validate training",
        "`train-arm` pre-flight",
        "CapacityExceeded",
    ):
        assert phrase in flat, (
            f"WHY THIS IS A FAILURE: the sheet never states {phrase!r}. The probe returns before "
            "the capacity probe, and an operator reading a green probe as proof of fit discovers "
            "the transient after a 40-hour night"
        )


def test_the_denominator_is_the_fifty_two_task_draw() -> None:
    """The post-§ 10.16 arithmetic: 51 private + 1 public = 52 tasks, each drawn `K` times."""
    flat = _flat(_runbook())
    assert "51 private" in flat and "52 tasks" in flat and "1 public" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not state the re-derived draw — 51 private "
        "(66 - 5 dev - 10 held-out not already dev-excluded) + 1 public = 52 tasks. The "
        "denominator is what the night's coverage claim is read against"
    )
    assert "= 62 tasks" not in flat and "61 private" not in flat, (
        "WHY THIS IS A FAILURE: the sheet carries the pre-§ 10.16 denominator, which counts the "
        "held-out members as drawable"
    )


def test_every_declared_dev_id_is_passed() -> None:
    """The same five ids the hardened contract declared, in the post-§ 10.16 corpus form."""
    for block in _door_blocks(_bash_blocks(_runbook())):
        passed = tuple(_values(block).get("--dev-subset", []))
        assert passed == DECLARED_DEV, (
            f"WHY THIS IS A FAILURE: the command excludes {passed!r} and the declared dev set is "
            f"{DECLARED_DEV!r}. The door refuses an id that matches no task, but it cannot "
            "notice one that was never passed"
        )


def test_the_heldout_document_is_passed_by_both_doors_and_the_go_no_go() -> None:
    """The committed document is passed, not only described: without it the split never runs."""
    blocks = _bash_blocks(_runbook())
    for label, block, command in (
        ("probe", _probe_block(blocks), DOOR),
        ("night", _night_block(blocks), DOOR),
        ("check-probe", _probe_check_block(blocks), PROBE_CHECK),
        ("check-leakage", _check_leakage_block(blocks), LEAKAGE_CHECK),
    ):
        assert block, f"no bash block invokes the {label} command"
        heldout = _values(block, command).get("--heldout", [])
        assert heldout == [HELDOUT_DOC], (
            f"WHY THIS IS A FAILURE: the {label} command passes --heldout {heldout!r} and the "
            f"committed document is {[HELDOUT_DOC]!r}. A run without it draws the held-out "
            "members into the training set"
        )


def test_the_probe_decision_is_commanded_before_the_night() -> None:
    """The go/no-go is a command, before the night, bound to the run the probe wrote."""
    blocks = _bash_blocks(_runbook())
    check = _probe_check_block(blocks)
    assert check and PROBE_CHECK in check, (
        "WHY THIS IS A FAILURE: the sheet does not run `whetstone check-probe` as a command"
    )
    night = _night_block(blocks)
    assert night, "no bash block invokes the night without --probe"
    assert blocks.index(check) < blocks.index(night), (
        "WHY THIS IS A FAILURE: the probe decision is commanded after the night"
    )
    probe = _probe_block(blocks)
    probe_values = _values(probe)
    run_dir = f"{probe_values['--runs'][0]}/{probe_values['--run-id'][0]}"
    assert _values(check, PROBE_CHECK).get("--run") == [run_dir], (
        f"WHY THIS IS A FAILURE: check-probe's --run is "
        f"{_values(check, PROBE_CHECK).get('--run')!r} and the probe wrote {run_dir!r}. The "
        "decision must point at the run the probe actually produced"
    )


def test_the_night_resumes_unchanged_and_the_probe_restarts_fresh() -> None:
    """A killed night resumes the same command; a killed probe is never resumed."""
    text = _runbook()
    flat = _flat(text)
    assert "Restart the **same command, unchanged**" in text, (
        "WHY THIS IS A FAILURE: the killed-night restart sentence is gone. A night resumes "
        "unchanged with the same --run-id and --run-seed"
    )
    assert "`--run-id` and `--run-seed`" in flat, (
        "WHY THIS IS A FAILURE: the resume rule does not name the two inputs it preserves"
    )
    assert "Do **not** delete the run directory" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not forbid deleting the run directory, which "
        "discards the paid-for draws and changes the experiment"
    )
    assert "never resumed" in flat and "restart it fresh" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not say a killed probe is never resumed — the "
        "cheap probe is the one place a fresh restart is affordable"
    )


def test_the_night_block_documents_the_remine_and_the_probe_does_not() -> None:
    """The night re-mines from the operator's donor; the probe validates the chain cheaply."""
    blocks = _bash_blocks(_runbook())
    night = _night_block(blocks)
    probe = _probe_block(blocks)
    night_values = _values(night)
    missing = sorted(set(REMINE_FLAGS) - set(night_values))
    assert not missing, (
        f"WHY THIS IS A FAILURE: the night command passes none of {missing} and the night must "
        "re-mine before it draws"
    )
    assert night_values["--remine"] == [DONOR], (
        f"WHY THIS IS A FAILURE: the night command's --remine is {night_values['--remine']!r} "
        f"and it must be {[DONOR]!r}. A literal donor path publishes a home directory"
    )
    for value in night_values["--remine-out"]:
        assert _is_anchored(value), (
            f"WHY THIS IS A FAILURE: --remine-out is relative ({value!r}); the strict loader "
            "reads it from subprocesses whose CWD is not the night's"
        )
    assert not set(REMINE_FLAGS) & set(_values(probe)), (
        "WHY THIS IS A FAILURE: the probe command re-mines. Mining is hours, and the probe "
        "exists to validate the chain before a night is committed to"
    )
    flat = _flat(_runbook())
    for phrase in ("training-only root", "--remine-limit"):
        assert phrase in flat, f"the sheet never states {phrase!r} for the re-mine block"
    assert _exports_donor(_runbook()), (
        "WHY THIS IS A FAILURE: the sheet passes `--remine $DONOR` and never exports it"
    )


def test_run_ids_are_operator_declared_and_never_historical() -> None:
    """The two run ids are the operator's tokens, distinct, and never a past run's."""
    blocks = _bash_blocks(_runbook())
    probe = _probe_block(blocks)
    night = _night_block(blocks)
    assert probe and night, "no bash block invokes the probe pass and the night"
    assert PROBE_RUN_ID != NIGHT_RUN_ID, "the two runs need two distinct run-id tokens"
    for label, block, token in (
        ("probe", probe, PROBE_RUN_ID),
        ("night", night, NIGHT_RUN_ID),
    ):
        values = _values(block)
        assert values.get("--run-id") == [token], (
            f"WHY THIS IS A FAILURE: the {label} command declares --run-id "
            f"{values.get('--run-id')!r} and the sheet must declare the operator's token "
            f"{token!r}. A historical id points the run at an artifact that already exists"
        )
        workspace = values.get("--workspace", [])
        assert workspace and token in workspace[0], (
            f"WHY THIS IS A FAILURE: the {label} command's --workspace is {workspace!r} and does "
            f"not resolve from its declared run id {token!r}"
        )
    historical = sorted(
        token
        for block in blocks
        for token in shlex.split(block, posix=True)
        if any(old in token for old in HISTORICAL_IDS)
    )
    assert not historical, (
        f"WHY THIS IS A FAILURE: the sheet's command blocks still name a historical run id "
        f"({historical!r}). Run ids are declared, never reused"
    )


def test_the_finding_lives_under_planning_and_nothing_is_published() -> None:
    """The finding is a planning document; the night's raw counts stay in gitignored `runs/`."""
    text = _runbook()
    flat = _flat(text)
    assert FINDING in flat, (
        f"WHY THIS IS A FAILURE: the sheet never names {FINDING!r} as the finding's home"
    )
    assert "docs/planning/" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not state that the finding lives under "
        "`docs/planning/`; the gate record stays gitignored"
    )
    assert "Nothing here is published" in text, (
        "WHY THIS IS A FAILURE: the sheet does not state that the night publishes nothing"
    )
    for block in _bash_blocks(text):
        for token in shlex.split(block, posix=True):
            assert "/reports/" not in token, (
                f"WHY THIS IS A FAILURE: the command names {token!r}, inside the published "
                "reports directory, which the door refuses for private donor code"
            )


def test_the_sheet_cites_the_amendment_that_pins_the_series() -> None:
    """The sheet commits a night under § 10.23; it must name the amendment that pinned it."""
    flat = _flat(_runbook())
    assert "`PREREGISTRATION.md` § 10.23" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not cite `PREREGISTRATION.md` § 10.23, the "
        "amendment that pins the runtime, the base and the precision this sheet runs"
    )
    assert "§ 10.7" not in flat, (
        "WHY THIS IS A FAILURE: the sheet still carries a live § 10.7 citation, superseded by "
        "§ 10.16's re-derived held-out split"
    )
