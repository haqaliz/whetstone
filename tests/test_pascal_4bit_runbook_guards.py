"""Guards over the Pascal-4bit night sheet, so its commands cannot drift from the door they invoke.

`docs/planning/pascal-4bit/night-door/runbook.md` is the operator's sheet for the main series on
`x202` — 3x GTX 1080 8 GB, loaded across the visible GPUs — under `torch 2.14.1+cu126`, the
pinned 8B base at 4-bit NF4 with bf16 **compute**. It is a precision/runtime move, not an edit of
the Torch/MPS sheet: the two series are non-comparable and the MPS series is not retired. This
module is one guard per sheet, as `test_torch_mps_runbook_guards.py` is for its own: the
command-independent parse helpers are imported **by identity** from `test_runbook_guards.py`,
asserted `is`, and only the door-keyed ones are this file's own.

Properties this sheet owns:

1. the parse really reads the sheet: exactly two door blocks (probe + night), `--probe 18` on the
   probe pass (the § 10.28 near-miss sample) and no `--probe` on the night (the full 52-task
   corpus);
2. every flag the door and `check-probe` pass exists in the shipped parser;
3. `--runs`/`--checkpoints`/`--workspace` are absolute or `$REPO`-anchored, `$REPO` is exported,
   and no worktree is named anywhere;
4. both doors name `--runtime torch` and run the venv's own `whetstone`;
5. the probe is § 10.28's 18 private + 1 public = 19 tasks x `K = 16` = **304 draws**: the 20-task
   § 10.27 sample minus the two macOS-only tasks, symlinked with the 12 held-out manifests into
   one 30-link root, with no `--dev-subset`;
6. the two excluded ids and their Darwin reasons are stated in the sheet's own words;
7. the check-probe block pins `--device cuda --precision bfloat16 --probe 18`, and its `--run`
   names the directory the probe wrote;
8. the 52-task night passes the five declared dev ids, names both donor roots, and carries no
   `--probe`;
9. the setup names the Pascal-capable wheel (`torch==2.14.1` from the `cu126` index), `gcc`/`g++`
   (Triton's helper needs a compiler), the pinned revision and the exact `quantize.json` sidecar;
10. no `caffeinate` (there is no Mac to hold awake), the mirrors export maps the donors and flask,
    the supervisor wraps both doors, the corpus-removal rule is stated, and the finding's home is
    `docs/planning/pascal-4bit/finding.md`;
11. the two decisions are separate: the harness rule (`check-probe` exit 0) is not the § 10.28 GO
    (at least one of the 304 draws strict-`PASS`).

**Watched failing first** (`CONTRIBUTING.md`): the module was run before the sheet existed and
every test failed on the missing file; it was then run against a stub sheet with `--probe 20`, a
`--dev-subset` on the probe, relative writable paths, a worktree name, `caffeinate`, no excluded
ids and no mirrors export, and every one of those was refused before the real sheet existed.
"""

from __future__ import annotations

import argparse
import json
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
RUNBOOK = Path(__file__).parent.parent / "docs/planning/pascal-4bit/night-door/runbook.md"

#: Both doors. This sheet's own constant, never another guard's.
DOOR = "whetstone run --night"
PROBE_CHECK = "whetstone check-probe"

#: The venv is put on `PATH` by the env block, so the door is invoked by its absolute path.
VENV_DOOR = "$REPO/.venv/bin/whetstone"

#: § 10.27's 20-task near-miss sample, minus the two macOS-only tasks. The remaining 18 plus the
#: public task are § 10.28's 304 draws.
NEAR_MISS_20 = (
    "donor-a-2f4e497580ff",
    "donor-a-34daf85182d5",
    "donor-a-4731e32044c5",
    "donor-a-12a1d8e4d766",
    "donor-a-5e25b106874c",
    "donor-a-f100a90e47f2",
    "donor-a-955d9a079c16",
    "donor-a-a93fe36d6e85",
    "donor-a-d601ff2d0ec0",
    "donor-a-99c0e0464c21",
    "donor-a-37a91266029a",
    "donor-a-df207b27e82c",
    "donor-a-c32d7c672465",
    "donor-a-6d35bb3a4d17",
    "donor-a-3326ca8a116d",
    "donor-b-c3e132b7469b",
    "donor-b-0fe4582aeac1",
    "donor-b-c57246c7841a",
    "donor-b-cc7d3f520f1c",
    "donor-b-ce6425d3101a",
)

#: The two § 10.27 tasks that cannot be scored on Linux: one declares `@darwin_only` tests in
#: `tests/test_replay_batch_server_rooting.py`, the other a module-level Darwin skip in
#: `tests/test_verify_cli.py`. They stay in the corpus; this probe's sample excludes them.
EXCLUDED = {
    "donor-b-c57246c7841a": (
        "@darwin_only",
        "tests/test_replay_batch_server_rooting.py",
    ),
    "donor-b-cc7d3f520f1c": (
        'pytestmark = pytest.mark.skipif(sys.platform != "darwin"',
        "tests/test_verify_cli.py",
    ),
}

NEAR_MISS_18 = tuple(one for one in NEAR_MISS_20 if one not in EXCLUDED)

#: The committed held-out document; its 12 members are loaded into the prep root so the document
#: excludes something, and are never drawn.
HELDOUT = Path(__file__).parents[1] / "tasks/heldout/source-b.json"

#: The five dev ids the hardened contract declared (`PREREGISTRATION.md` § 10.4).
DECLARED_DEV = (
    "donor-b-2e149603209a",
    "donor-b-353359e9ac6e",
    "donor-b-3e3051c4192a",
    "donor-b-844db07ed482",
    "donor-b-9dba3ea557f5",
)

#: The immutable base revision `PREREGISTRATION.md` § 10.28 keeps unchanged.
REVISION = "b968826d9c46dd6066d109eabc6255188de91218"

#: The exact sidecar the 4-bit load reads. `--precision bfloat16` is the compute dtype.
QUANTIZE = (
    '{"bnb_4bit_quant_type": "nf4", "bnb_4bit_compute_dtype": "bfloat16", '
    '"bnb_4bit_use_double_quant": true}'
)

HELDOUT_DOC = "$REPO/tasks/heldout/source-b.json"
NEAR_MISS_ROOT = "$REPO/tasks/local/near-miss"
FINDING = "docs/planning/pascal-4bit/finding.md"

#: The flags whose value the run writes to.
WRITABLE = ("--runs", "--checkpoints", "--workspace")

FLAG = re.compile(r"--[a-z][a-z0-9-]*")


def _heldout_membership() -> tuple[str, ...]:
    return tuple(json.loads(HELDOUT.read_text(encoding="utf-8"))["membership"])


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _runbook() -> str:
    assert RUNBOOK.is_file(), (
        f"{RUNBOOK} is absent, so every guard in this module would fail on a read rather than "
        "pin a sheet. The Pascal-4bit series has no command surface until it exists."
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
    return next((block for block in _door_blocks(blocks) if "--probe" in block), "")


def _night_block(blocks: list[str]) -> str:
    return next((block for block in _door_blocks(blocks) if "--probe" not in block), "")


def _probe_check_block(blocks: list[str]) -> str:
    return next((block for block in blocks if PROBE_CHECK in block), "")


def _values(block: str, command: str = DOOR) -> dict[str, list[str]]:
    """Flag → every value it was given, from the tokens after the invocation."""
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


def test_the_parse_really_reads_the_sheets_two_doors() -> None:
    """Anti-vacuity: exactly two door blocks, the probe's `--probe 18`, the night's none."""
    blocks = _bash_blocks(_runbook())
    assert len(_door_blocks(blocks)) == 2, (
        "WHY THIS IS A FAILURE: the sheet does not carry exactly two door invocations (the probe "
        f"pass and the night). Found {len(_door_blocks(blocks))}"
    )
    probe = _probe_block(blocks)
    night = _night_block(blocks)
    assert probe and night, "the sheet has no separate probe pass and night"
    assert _values(probe).get("--probe") == ["18"], (
        "WHY THIS IS A FAILURE: the probe pass does not draw `--probe 18`; § 10.28's sample is "
        "the 18 private tasks that remain after the two Darwin-only ones are excluded"
    )
    assert "--probe" not in _values(night), (
        "WHY THIS IS A FAILURE: the night block carries `--probe`; the night draws the full "
        "52-task corpus"
    )
    for block in (probe, night):
        assert f"{VENV_DOOR} run --night" in block, (
            f"WHY THIS IS A FAILURE: a door block does not run `{VENV_DOOR} run --night`. The "
            "env block puts the venv on PATH, and an unnamed interpreter may carry another torch"
        )


def test_every_flag_the_commands_pass_exists_in_the_parser() -> None:
    """A flag the door does not define is a usage error after the operator has measured."""
    blocks = _bash_blocks(_runbook())
    for block in _door_blocks(blocks):
        unknown = sorted(set(_values(block)) - _parser_flags("run"))
        assert not unknown, (
            f"WHY THIS IS A FAILURE: the sheet passes {unknown} and `whetstone run` defines none "
            f"of them. Parser accepts: {sorted(_parser_flags('run'))}"
        )
    check = _probe_check_block(blocks)
    assert check, "the sheet runs no `whetstone check-probe` block"
    unknown = sorted(set(_values(check, PROBE_CHECK)) - _parser_flags("check-probe"))
    assert not unknown, (
        f"WHY THIS IS A FAILURE: check-probe is given {unknown} and the shipped `check-probe` "
        f"defines none of them. Parser accepts: {sorted(_parser_flags('check-probe'))}"
    )


def test_the_probe_pass_is_the_section_10_28_sample() -> None:
    """18 private + 1 public = 19 tasks x 16 = 304 draws, on the 30-link near-miss root."""
    text = _runbook()
    blocks = _bash_blocks(text)
    probe = _probe_block(blocks)
    check = _probe_check_block(blocks)
    night = _night_block(blocks)

    assert _values(probe).get("--probe") == ["18"], (
        "the probe pass does not draw `--probe 18`; § 10.28's sample is 18 private tasks"
    )
    assert _values(check, PROBE_CHECK).get("--probe") == ["18"], (
        "check-probe does not read the declared sample as 18; the pin compares the ledger's "
        "task_set.probe to this value"
    )
    assert _values(probe).get("--tasks") == [NEAR_MISS_ROOT], (
        "the probe's task root is not the § 10.28 near-miss root; the two donor roots draw the "
        "whole corpus rather than the sample"
    )
    assert "--dev-subset" not in _values(probe), (
        "the probe passes `--dev-subset`; the near-miss root already excludes the dev ids"
    )
    assert _values(night).get("--tasks") == [
        "$REPO/tasks/local/donor-b",
        "$REPO/tasks/local/donor-a",
    ], (
        "the night does not name both donor roots; the full 52-task corpus is what it draws"
    )

    prep = next((block for block in blocks if "ln -sf" in block), "")
    assert prep, (
        "WHY THIS IS A FAILURE: the sheet has no prep block symlinking § 10.28's sample into "
        "`$REPO/tasks/local/near-miss`; the probe would draw a root that does not exist"
    )
    assert NEAR_MISS_ROOT in prep, (
        "the prep block does not build the probe's `$REPO/tasks/local/near-miss` root"
    )
    found = re.findall(r"donor-[ab]-[0-9a-f]{12}", prep)
    expected = set(NEAR_MISS_18) | set(_heldout_membership())
    assert len(found) == len(set(found)) == 30, (
        f"WHY THIS IS A FAILURE: the prep block carries {len(found)} link(s) with "
        f"{len(set(found))} distinct id(s); the root is 18 sample + 12 held-out = 30 links"
    )
    assert set(found) == expected, (
        f"WHY THIS IS A FAILURE: the prep links are not the 18-task sample plus the held-out "
        f"members: missing {sorted(expected - set(found))}, extra "
        f"{sorted(set(found) - expected)}. The held-out members must be loaded or the door "
        "refuses a split that excludes nothing"
    )

    flat = _flat(text)
    for phrase in ("304", "18 private", "1 public", "19 tasks", "§ 10.28", "30 links"):
        assert phrase in flat, (
            f"WHY THIS IS A FAILURE: the sheet never states {phrase!r} for the § 10.28 sample. "
            "A read of the draw count has nothing to count against"
        )


def test_the_sheet_states_the_two_macos_only_exclusions() -> None:
    """§ 10.27's 20 are cut to 18 because two cannot be scored on Linux.

    `donor-b-c57246c7841a` declares three of its five tests `@darwin_only` in
    `tests/test_replay_batch_server_rooting.py`; `donor-b-cc7d3f520f1c` carries a module-level
    `pytestmark = pytest.mark.skipif(sys.platform != "darwin", ...)` in `tests/test_verify_cli.py`.
    Neither is dropped from the corpus; this probe's sample excludes them by id.
    """
    text = _flat(_runbook())

    for task_id, reasons in EXCLUDED.items():
        assert task_id in text, (
            f"WHY THIS IS A FAILURE: the sheet does not name the excluded task {task_id!r}. A "
            "sample silently smaller than § 10.27's cannot be audited against it"
        )
        for phrase in reasons:
            assert phrase in text, (
                f"WHY THIS IS A FAILURE: the sheet does not state {phrase!r} for {task_id}. The "
                "exclusion is a platform fact, and the reason has to travel with the id"
            )
    assert set(EXCLUDED) <= set(NEAR_MISS_20), "the excluded ids are not § 10.27 tasks"
    assert not set(EXCLUDED) & set(NEAR_MISS_18), (
        "an excluded id is still in the 18-task sample; the sample would draw it"
    )

    ledger = json.loads((Path(__file__).parents[1] / "tasks/local-ledger.json").read_text())
    ledger_ids = {task["task_id"] for task in ledger["tasks"]}
    assert set(NEAR_MISS_18) <= ledger_ids, (
        f"§ 10.28 names tasks absent from the committed ledger: "
        f"{sorted(set(NEAR_MISS_18) - ledger_ids)}."
    )
    assert not set(NEAR_MISS_18) & set(_heldout_membership()), (
        "the sample names held-out members; the document would exclude part of it"
    )
    assert "not retired" in text and "non-comparable" in text, (
        "WHY THIS IS A FAILURE: the sheet does not state that the MPS series is not retired and "
        "that the figures are non-comparable. A moved series that reads as the old one is a "
        "restated number in the making"
    )


def test_the_writable_paths_are_anchored_and_no_worktree_is_named() -> None:
    """Every writable path is absolute or `$REPO`-anchored; a worktree is eventually deleted."""
    text = _runbook()
    blocks = _bash_blocks(text)
    for block in _door_blocks(blocks):
        values = _values(block)
        for flag in WRITABLE:
            named = values.get(flag, [])
            assert named, f"the door command passes no required {flag}"
            for value in named:
                assert _is_anchored(value), (
                    f"WHY THIS IS A FAILURE: {flag} is relative ({value!r}). The provisioning "
                    "subprocesses do not share the run's CWD, and a relative workspace is the "
                    "2026-08-12 failure — every rollout comes back UNPROVISIONED"
                )
    assert _exports_repo(text), (
        "WHY THIS IS A FAILURE: the sheet anchors its paths to `$REPO` and never exports it"
    )
    assert "export REPO=/home/foresight/whetstone" in text, (
        "WHY THIS IS A FAILURE: the sheet does not name x202's `$REPO`, so the anchor is not the "
        "tree the operator measured"
    )
    assert ".claude/worktrees/" not in text, (
        "WHY THIS IS A FAILURE: the sheet names a worktree path. Worktrees are removed when "
        "their unit merges, and x202 has no worktree tree to run from"
    )
    named = {
        name
        for line in text.splitlines()
        for path in _named_paths(line)
        if (name := _worktree_name(path)) is not None
    }
    assert named == set(), f"the sheet names worktree(s) {sorted(named)}"
    assert "caffeinate" not in text, (
        "WHY THIS IS A FAILURE: the sheet wraps a door in `caffeinate`. That is the Mac's "
        "sleep guard; x202 has no Mac to hold awake"
    )


def test_both_doors_name_the_torch_runtime_and_the_repair_budget() -> None:
    """A moved series still runs the pinned runtime, the repair budget and the supervisor."""
    blocks = _bash_blocks(_runbook())
    for block in _door_blocks(blocks):
        values = _values(block)
        assert values.get("--runtime") == ["torch"], (
            f"WHY THIS IS A FAILURE: --runtime is {values.get('--runtime')!r}; § 10.28 moves the "
            "series to Torch on CUDA, not to an unnamed or MLX runtime"
        )
        assert values.get("--repair") == ["2"], (
            "WHY THIS IS A FAILURE: a door does not pass `--repair 2`. `R_repair = 2` is a "
            "frozen input (§ 10.23)"
        )
        assert "--supervise" in values and values.get("--stall-seconds") == ["5400"], (
            "WHY THIS IS A FAILURE: a door runs without the stall supervisor or without its "
            "declared interval; a CUDA hang would take the whole run and its ledger"
        )
        assert values.get("--only") == ["Qwen/Qwen3-8B"], (
            "WHY THIS IS A FAILURE: the door trains a candidate other than the pinned 8B base"
        )


def test_the_check_probe_pins_the_cuda_bf16_backend_and_the_probes_run_dir() -> None:
    """`--device cuda --precision bfloat16` is the compute dtype, not full-precision weights."""
    blocks = _bash_blocks(_runbook())
    check = _probe_check_block(blocks)
    probe = _probe_block(blocks)
    values = _values(check, PROBE_CHECK)

    for flag, expected in (
        ("--runtime", "torch"),
        ("--device", "cuda"),
        ("--precision", "bfloat16"),
        ("--probe", "18"),
        ("--heldout", HELDOUT_DOC),
    ):
        assert values.get(flag) == [expected], (
            f"WHY THIS IS A FAILURE: check-probe passes {flag} {values.get(flag)!r}, not "
            f"{[expected]!r}. The pin can only refuse what the sheet names"
        )
    probe_values = _values(probe)
    run_dir = f"{probe_values['--runs'][0]}/{probe_values['--run-id'][0]}"
    assert values.get("--run") == [run_dir], (
        f"WHY THIS IS A FAILURE: check-probe's --run is {values.get('--run')!r} and the probe "
        f"wrote {run_dir!r}. The decision must point at the run the probe produced"
    )

    flat = _flat(_runbook())
    assert "compute dtype" in flat and "4-bit NF4" in flat and "sidecar" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not separate `--precision bfloat16` (the compute "
        "dtype) from the 4-bit NF4 weights declared by the sidecar. A reader can then restate "
        "the run as full-precision bf16"
    )


def test_the_sheet_states_the_two_decisions() -> None:
    """The harness rule and the § 10.28 GO are distinct; a green `check-probe` is not a GO."""
    flat = _flat(_runbook())
    assert "Harness rule" in flat and "§ 10.28 GO" in flat, (
        "WHY THIS IS A FAILURE: the sheet states one decision rule. The harness rule and the "
        "measurement's GO are different questions and only the second needs a solve"
    )
    assert "exit 0" in flat and "not the GO" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not say `check-probe` exit 0 is not the GO, so a "
        "green harness can be read as a solve"
    )
    for phrase in (
        "at least one of the 304 draws",
        "strict-`PASS`",
        "NO-GO",
        "never to a loosened verifier",
    ):
        assert phrase in flat, (
            f"WHY THIS IS A FAILURE: the sheet never states {phrase!r}. § 10.28's GO rule is the "
            "measurement's decision, and a NO-GO returns the lever to a human"
        )


def test_the_night_is_the_full_corpus_with_the_five_dev_ids() -> None:
    """The night follows a GO on the full 52-task corpus; only the probe is narrowed."""
    blocks = _bash_blocks(_runbook())
    night = _night_block(blocks)
    passed = tuple(_values(night).get("--dev-subset", []))
    assert passed == DECLARED_DEV, (
        f"WHY THIS IS A FAILURE: the night excludes {passed!r} and the declared dev set is "
        f"{DECLARED_DEV!r}. The door refuses an id that matches no task, but it cannot notice "
        "one that was never passed"
    )
    assert "--probe" not in _values(night), "the night still carries `--probe`"
    assert "--dev-subset" not in _values(_probe_block(blocks)), (
        "the probe passes `--dev-subset`; the sample root is already the narrowed set"
    )


def test_the_heldout_document_is_passed_by_both_doors_and_the_go_no_go() -> None:
    """The committed document is passed, not only described: without it the split never runs."""
    blocks = _bash_blocks(_runbook())
    for label, block, command in (
        ("probe", _probe_block(blocks), DOOR),
        ("night", _night_block(blocks), DOOR),
        ("check-probe", _probe_check_block(blocks), PROBE_CHECK),
    ):
        assert block, f"no bash block invokes the {label} command"
        heldout = _values(block, command).get("--heldout", [])
        assert heldout == [HELDOUT_DOC], (
            f"WHY THIS IS A FAILURE: the {label} command passes --heldout {heldout!r} and the "
            f"committed document is {[HELDOUT_DOC]!r}. A run without it draws the held-out "
            "members into the training set"
        )


def test_the_setup_names_the_pascal_wheel_the_compiler_and_the_sidecar() -> None:
    """The measured run is `torch 2.14.1+cu126`, NF4 with bf16 compute, on the pinned revision."""
    text = _runbook()
    flat = _flat(text)
    for phrase in (
        "sudo apt-get install -y gcc g++",
        "uv sync --extra torch",
        "uv pip install --reinstall torch==2.14.1 "
        "--index-url https://download.pytorch.org/whl/cu126",
        "snapshot_download",
        REVISION,
        QUANTIZE,
    ):
        assert phrase in flat, (
            f"WHY THIS IS A FAILURE: the setup does not carry {phrase!r}. The Pascal host needs "
            "the cu126 wheel (the pinned cu130 build has no sm_61 kernels), the compiler Triton's "
            "helper invokes, the immutable revision, and the declared 4-bit sidecar"
        )
    assert "gcc/g++" in flat and "Triton" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not state why the compiler is installed"
    )
    assert "git clone" in flat and "contig" in flat and "belay" in flat, (
        "WHY THIS IS A FAILURE: the setup does not clone both donors; the manifests' repo_url "
        "names them"
    )
    for phrase in ("4-bit", "NF4", "quantize.json", "cu126", "GTX 1080", "device_map", "balanced"):
        assert phrase in flat, (
            f"WHY THIS IS A FAILURE: the sheet never names {phrase!r}. The precision, the "
            "placement, the host and the sidecar are the inputs a reader re-derives the run from"
        )


def test_the_sheet_installs_the_chunked_sdpa_shim() -> None:
    """Pascal has only the math SDPA kernel; the committed shim chunks the query axis.

    Without it a 10,001-token prefill tried to allocate 7.38 GiB on a 7.92 GiB card. The shim is
    numerically exact (query-axis chunking), committed in this repository, gated by
    `WHETSTONE_PASCAL_SDPA=1`, and put on `PYTHONPATH` so the interpreter imports it at startup.
    """
    text = _runbook()
    flat = _flat(text)
    for phrase in (
        "sitecustomize",
        "WHETSTONE_PASCAL_SDPA=1",
        "docs/planning/pascal-4bit/night-door",
        "CHUNK = 256",
        "PYTHONPATH",
        "math SDPA",
        "max diff 0.0",
    ):
        assert phrase in flat, (
            f"WHY THIS IS A FAILURE: the sheet never states {phrase!r} for the chunked-SDPA "
            "shim. The shim is an input: without it the measured prefill OOMs, and without the "
            "gate and the chunk size a reader cannot re-derive which arithmetic ran"
        )


def test_the_mirrors_export_maps_the_donors_and_flask() -> None:
    """The mirror is an explicit input, inherited by the verifier's subprocesses."""
    flat = _flat(_runbook())
    assert "export WHETSTONE_REPO_MIRRORS=" in flat, (
        "WHY THIS IS A FAILURE: the sheet does not export WHETSTONE_REPO_MIRRORS. Without the "
        "mapping the verifier clones the unreachable canonical URL"
    )
    for value in (
        "/home/foresight/whetstone-donors/contig",
        "/home/foresight/whetstone-donors/belay",
        "https://github.com/pallets/flask.git",
        "/home/foresight/whetstone-donors/flask.git",
    ):
        assert value in flat, (
            f"WHY THIS IS A FAILURE: the mirrors export does not map {value!r}. A task whose "
            "repo_url has no entry is cloned from its canonical URL"
        )


def test_the_finding_home_and_the_corpus_removal_rule_are_stated() -> None:
    """The private corpus is copied to the founder's own host and removed after the measurement."""
    flat = _flat(_runbook())
    assert FINDING in flat, (
        f"WHY THIS IS A FAILURE: the sheet never names {FINDING!r} as the finding's home"
    )
    for phrase in (
        "removed after the measurement",
        "founder's own",
        "No count has been measured",
        "§ 3 baseline remains unspent",
    ):
        assert phrase in flat, (
            f"WHY THIS IS A FAILURE: the sheet never states {phrase!r}. The private corpus is an "
            "operator input that does not outlive the run, and no count exists yet"
        )
