"""The `whetstone` command line entry point.

The failure this module prevents: a ``--help`` that advertises work the code cannot do.
Commands appear here only when something stands behind them, and four now do. ``verify`` runs
the execution-grounded reward in `whetstone.verify.strict`: it applies a patch to a task's
known-broken commit inside a sandbox, restores the operator-held tests from golden, and
compares what pytest actually executed against what the task declared. ``mine`` is the other
end — it turns a local repository into tasks the first command can run, proving each one live
before it enters the corpus. ``run --night`` is the loop between them: it draws K seeded
attempts per task, keeps only the rollouts that reward passed, and trains a candidate on them.
``gate`` is the never-regress promotion gate: it scores a candidate checkpoint against the
incumbent on the held-out source-B membership and returns exactly one of three exits. There
is still no report, so there is still no stub for it.

**``run --night`` and ``gate`` are the two commands here whose bodies are not in this file,
and deliberately.** This module is a guarded root — it calls ``verify_strict``, and nothing it
imports may reach an inference library. The loop and the gate reach ``mlx_lm`` legitimately,
so they live in the EXEMPT ``whetstone.loop`` package, and ``run_night`` below holds a single
**function-local** import into it, as does ``run_gate_cli``: running ``whetstone verify``
never executes those lines and never loads a model.
``tests/test_reward_path_scope_is_partitioned.py`` asserts they are the only such edges and
that they are function-local.

**All four subcommands share the same four exit codes and add no fifth.** A mint that produced
no task exits ``FAIL_EXIT``, never 0: "nothing could be mined here" is a finding about a donor,
and a caller checking ``rc == 0`` must never read it as a corpus. A night that produced no
candidate is the same shape and is floored the same way.

``--task`` takes a manifest or a **directory** of them, and the directory adds no fifth
outcome. The set reduces worst-status-wins through the same `whetstone.verify.verdict.reduce`
a single task's sub-checks do, so one unverified task among ninety-nine passes exits 3. "Most
of them passed" is not a fourth kind of result; it is a pass the caller has not earned.

**The exit codes are this module's other job, and the honest one.** PASS is 0, FAIL is 1,
argparse's usage error stays 2, and UNVERIFIED is **3**. UNVERIFIED deliberately is not 0: a
caller that checks only ``rc == 0`` must never read a run nobody could check as a win. It is
deliberately not 2 either, because "the reward could not reach a conclusion" is a finding
about a task and "you invoked me wrongly" is a typo, and the two have different remedies. The
honesty contract — UNVERIFIED is never rendered as PASS — has to hold at the process
boundary, not only inside `whetstone.verify.verdict.reduce`. The same rule governs what is
printed: for a non-PASS result only the sub-checks that actually fired are shown, so nothing
in the output of an unverified run reads like a success.

``main`` returns an ``int`` instead of calling ``sys.exit`` so tests can assert on the exit
code directly. argparse exits the process for ``--help``, ``--version``, and usage errors;
those exits are caught and translated back into return codes rather than escaping as
exceptions.

Bare ``whetstone`` prints usage and returns non-zero. A no-op that exits 0 is a claim that
something worked, and nothing did.
"""

import argparse
import sys
import tempfile
from pathlib import Path

from whetstone import __version__
from whetstone.tasks.manifest import load_tasks
from whetstone.tasks.mine import MintFailed, mine
from whetstone.verify.sandbox import UnsupportedPlatform
from whetstone.verify.strict import StrictResult, verify_strict
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status, Verdict, reduce

#: The patch is a genuine fix.
PASS_EXIT = 0

#: The patch is a wrong answer — a declared test did not pass, or it reached for the
#: operator's tests, or it was not applicable at all.
FAIL_EXIT = 1

#: argparse's own convention for "you invoked me wrongly".
USAGE_ERROR = 2

#: Nothing could be concluded: the checkout failed, the task is malformed, the run was killed,
#: the report was unreadable. Not 0 and not `USAGE_ERROR` — see the module docstring.
UNVERIFIED_EXIT = 3

#: Only the statuses `reduce` can actually return are mapped. Anything else — a WARN a future
#: sub-check introduces, a leaked NOT_COVERED — falls through to UNVERIFIED_EXIT rather than
#: to a default 0, so an unrecognised status can never be paid as a win.
_VERDICT_EXIT_CODES: dict[Status, int] = {
    Status.PASS: PASS_EXIT,
    Status.FAIL: FAIL_EXIT,
    Status.UNVERIFIED: UNVERIFIED_EXIT,
}

#: A ceiling on one task's reward run. Named rather than defaulted inside the verifier, which
#: takes no default on purpose: a timeout inherited from somewhere else turns every slow task
#: into an UNVERIFIED nobody can explain.
VERIFY_TIMEOUT_SECONDS = 900.0

#: A ceiling on any single run a mint makes — each of the three derivation runs and each of the
#: two liveness runs. Named here rather than defaulted inside the miner, for the same reason
#: `VERIFY_TIMEOUT_SECONDS` is: a limit inherited from somewhere else turns a slow donor into a
#: discard nobody can explain.
MINE_TIMEOUT_SECONDS = 900.0

#: Where the committed evidence goes. `tasks/local-ledger.json` and `tasks/recipes/<donor>.json`,
#: both relative to this root, exactly as `tasks/README.md` documents them. Overridable so a test
#: does not have to write into the repository's own corpus directory to exercise the miner.
DEFAULT_TASKS_ROOT = Path("tasks")

DESCRIPTION = "Whetstone — a model that trains itself overnight, and proves it didn't cheat."

_VERIFY_DESCRIPTION = (
    "Verify a patch against a task — or against every task in a directory — by re-executing "
    "the task's own tests in a sandbox. A directory reduces worst-status-wins: the run is a "
    "PASS only if every task passed. Exits 0 on PASS, 1 on FAIL, 2 on a usage error, and 3 "
    "when nothing could be verified."
)

_RUN_DESCRIPTION = (
    "Run one night of the improvement loop: draw K seeded attempts at every task under the "
    "frozen generation contract, keep only the rollouts the STRICT verifier passed, and LoRA-SFT "
    "the base on those. Produces runs/<id>/ (ledger, dataset, per-draw journals and transcripts) "
    "and, when the night selected anything and the capacity probe fits, a candidate under "
    "checkpoints/<id>/. Every training example carries a recorded strict-PASS verdict by "
    "construction; UNVERIFIED is never training data. Exits 0 only when a candidate was written."
)

_MINE_DESCRIPTION = (
    "Mine task instances out of a local git repository: commits that turned an existing test "
    "green become tasks, each provisioned from the donor's own lockfile and proved live — it "
    "must FAIL with no patch and PASS with its own reference patch — before it enters the "
    "corpus. The manifests are the user's own code and stay local; the liveness ledger and the "
    "recipe under --tasks-root are the committed evidence. Nothing here reaches the network. "
    "Exits 0 when at least one task was minted, 1 when none could be, and 2 on a usage error."
)

_GATE_DESCRIPTION = (
    "Score a candidate checkpoint against the incumbent on the held-out source-B membership "
    "(plus source A in full) through the STRICT verifier, and decide by the roadmap's rule: "
    "promote iff solved_new > solved_old AND regressed == 0 AND unverified == 0. Exits 0 on "
    "promoted, 1 on rejected, 2 on a refusal (a checkpoint that cannot be re-hashed, a "
    "held-out document that cannot be read, a held-out set of zero), and 3 when the eval is "
    "UNVERIFIED — an incomplete eval is never promoted."
)


def build_parser() -> argparse.ArgumentParser:
    """The parser, built in one place so tests can introspect the flags that really exist."""
    parser = argparse.ArgumentParser(prog="whetstone", description=DESCRIPTION)
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="print the installed whetstone version and exit",
    )

    commands = parser.add_subparsers(dest="command", metavar="<command>")
    verify = commands.add_parser(
        "verify",
        help="verify a patch against a task and exit with the verdict's code",
        description=_VERIFY_DESCRIPTION,
    )
    verify.add_argument(
        "--task",
        required=True,
        type=Path,
        metavar="<path>",
        help="the operator-controlled task manifest (JSON), or a directory of them",
    )
    verify.add_argument(
        "--patch",
        required=True,
        type=Path,
        metavar="<path>",
        help="the patch to verify, as a unified diff",
    )

    mine = commands.add_parser(
        "mine",
        help="mine proven-live tasks out of a local repository",
        description=_MINE_DESCRIPTION,
    )
    mine.add_argument(
        "--donor",
        required=True,
        type=Path,
        metavar="<path>",
        help="the local git repository to mine; it is read, never written to",
    )
    mine.add_argument(
        "--label",
        required=True,
        metavar="<name>",
        help=(
            "a non-identifying name for this donor, recorded in the committed recipe; "
            "the donor's own name is private and must not be used"
        ),
    )
    mine.add_argument(
        "--out",
        required=True,
        type=Path,
        metavar="<path>",
        help="where the task manifests are written, e.g. tasks/local/<label>/",
    )
    mine.add_argument(
        "--limit",
        required=True,
        type=int,
        metavar="<n>",
        help="how many proven-live tasks to mint; must be at least 1",
    )
    mine.add_argument(
        "--seed",
        type=int,
        metavar="<n>",
        help="draw candidates in a seeded order; the same seed mints the same tasks",
    )
    mine.add_argument(
        "--tasks-root",
        type=Path,
        default=DEFAULT_TASKS_ROOT,
        metavar="<path>",
        help="where the committed evidence goes: the liveness ledger and the donor's recipe",
    )

    night = commands.add_parser(
        "run",
        help="run one night of the improvement loop and emit a candidate",
        description=_RUN_DESCRIPTION,
    )
    night.add_argument(
        "--night",
        action="store_true",
        required=True,
        help=(
            "run a night. Required rather than implied: `whetstone run` with nothing behind it "
            "would be a command that exits 0 having done nothing, and the roadmap names this "
            "door as `run --night` so a later `run --day` cannot silently inherit its meaning"
        ),
    )
    night.add_argument(
        "--tasks",
        type=Path,
        required=True,
        action="append",
        metavar="<path>",
        help=(
            "source B: a private corpus directory, repeatable. The miner writes one directory per "
            "donor, so the real corpus is one root per donor rather than their parent. Read by "
            "path and never copied: it is the user's own code and lives outside any worktree"
        ),
    )
    night.add_argument(
        "--public",
        type=Path,
        required=True,
        metavar="<path>",
        help="source A: the eligible public instance(s). Drawn against always, beside source B",
    )
    night.add_argument(
        "--pool",
        type=Path,
        required=True,
        metavar="<path>",
        help=(
            "source A's committed pool. A public instance carries no donor commit, so its control "
            "arm reads the gold patch from here rather than re-deriving one — without it every "
            "public probe is a skip and the night proves nothing about its own harness"
        ),
    )
    night.add_argument(
        "--weights",
        type=Path,
        required=True,
        metavar="<path>",
        help=(
            "the weights root holding provenance.json. Every recorded sha256 is re-checked before "
            "a token is generated"
        ),
    )
    night.add_argument(
        "--runs",
        type=Path,
        required=True,
        metavar="<path>",
        help=(
            "the gitignored root the run directory is created under (`runs/`). It holds the "
            "ledger, the dataset, and the per-draw journals and transcripts — the user's own code, "
            "quoted back. A path inside a reports/ directory is refused"
        ),
    )
    night.add_argument(
        "--checkpoints",
        type=Path,
        required=True,
        metavar="<path>",
        help=(
            "the gitignored root the candidate is written under (`checkpoints/`). Refused inside "
            "a reports/ directory, for the same reason --runs is"
        ),
    )
    night.add_argument(
        "--workspace",
        type=Path,
        required=True,
        metavar="<path>",
        help=(
            "where sandboxes and provisioned environments are built. Never inside --runs: that "
            "directory is the night's evidence and this one is gigabytes of scratch"
        ),
    )
    night.add_argument(
        "--timeout",
        type=float,
        required=True,
        metavar="<seconds>",
        help=(
            "seconds allowed per verification. No default, matching the verifiers: a limit "
            "inherited from elsewhere turns every slow task into an UNVERIFIED nobody can explain"
        ),
    )
    night.add_argument(
        "--recorded-on",
        required=True,
        metavar="<date>",
        help=(
            "the date the operator declares for this run. An input, never the clock — a ledger "
            "that dated itself would differ from itself between two renders of the same records"
        ),
    )
    night.add_argument(
        "--run-id",
        required=True,
        metavar="<id>",
        help=(
            "the run's name, and the directory it gets under --runs and --checkpoints. An input "
            "for the reason --recorded-on is: a generated id makes two invocations of the same "
            "documented command produce two run directories nobody chose"
        ),
    )
    night.add_argument(
        "--run-seed",
        type=int,
        required=True,
        metavar="<n>",
        help=(
            "the night's single seed. Every per-attempt seed is sha256(run_seed, task_id, "
            "attempt), recorded in the ledger; the same seed over the same task set and contract "
            "produces a byte-identical training set"
        ),
    )
    night.add_argument(
        "--dev-subset",
        action="append",
        default=[],
        metavar="<task_id>",
        help=(
            "a task id the generation contract was developed against. Repeatable. Excluded from "
            "both sources before anything is drawn; an id matching no task is refused, because it "
            "would exclude nothing while the ledger said it had"
        ),
    )
    night.add_argument(
        "--heldout",
        type=Path,
        metavar="<path>",
        help=(
            "the committed held-out source-B document (schema whetstone-heldout/1, "
            "tasks/heldout/source-b.json) whose membership this night excludes from rollouts "
            "and training, before the contract is frozen. The document is a pinned input — "
            "consumed, never recomputed — and the loader refuses by name: an unknown schema, "
            "an unknown field, a rule or document digest that no longer matches, a membership "
            "id matching no loaded private task, or a degenerate membership (empty, whole "
            "corpus, below the floors, or empty after the dev-subset overlay). Source A is "
            "still drawn in full. Off by default: without the flag the night is today's "
            "night, byte for byte"
        ),
    )
    night.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="<name>",
        help=(
            "draw with the candidate whose repo id contains NAME. A night trains one candidate, "
            "so a weights root offering several needs this; a name matching nothing or several is "
            "refused rather than resolved"
        ),
    )
    night.add_argument(
        "--probe",
        type=int,
        metavar="<n>",
        help=(
            "draw against only the first N source-B tasks and write NO checkpoint. Use it to "
            "validate the whole chain cheaply before committing a night; a probe that trained "
            "would produce a candidate from a self-chosen sample"
        ),
    )
    night.add_argument(
        "--no-retries",
        action="store_true",
        help=(
            "draw under the un-hardened contract: no retry vocabulary frozen in, no retry "
            "wrapper. Retries are ON by default here, because the hardened contract is the one "
            "the evidence for this candidate was produced under; the ledger records which ran"
        ),
    )

    gate = commands.add_parser(
        "gate",
        help="score a candidate against the incumbent on the held-out set and decide",
        description=_GATE_DESCRIPTION,
    )
    gate.add_argument(
        "--candidate",
        type=Path,
        required=True,
        metavar="<path>",
        help="the candidate checkpoint directory, as a night wrote it under checkpoints/<id>/",
    )
    gate.add_argument(
        "--incumbent",
        type=Path,
        required=True,
        metavar="<path>",
        help="the incumbent checkpoint directory — the checkpoint the candidate must provably beat",
    )
    gate.add_argument(
        "--heldout",
        type=Path,
        required=True,
        metavar="<path>",
        help=(
            "the committed held-out source-B document (schema whetstone-heldout/1, "
            "tasks/heldout/source-b.json) whose membership is what the gate decides over. "
            "Consumed through aspect 1's fail-closed loader; a held-out set of zero is refused"
        ),
    )
    gate.add_argument(
        "--tasks",
        type=Path,
        required=True,
        action="append",
        metavar="<path>",
        help=(
            "source B: a private corpus directory, repeatable — the same roots the night drew "
            "against. The gate scores exactly the held-out document's membership of them"
        ),
    )
    gate.add_argument(
        "--public",
        type=Path,
        required=True,
        metavar="<path>",
        help=(
            "source A: the eligible public instance(s), scored in full and reported beside "
            "source B"
        ),
    )
    gate.add_argument(
        "--pool",
        type=Path,
        required=True,
        metavar="<path>",
        help="source A's committed pool, passed through to the oracle derivation",
    )
    gate.add_argument(
        "--weights",
        type=Path,
        required=True,
        metavar="<path>",
        help=(
            "the weights root holding provenance.json. Each checkpoint's own provenance names "
            "the base it was trained on; the gate resolves it here and stacks the checkpoint's "
            "LoRA adapter on it. Every recorded sha256 is re-checked before anything is loaded"
        ),
    )
    gate.add_argument(
        "--runs",
        type=Path,
        required=True,
        metavar="<path>",
        help=(
            "the gitignored root the promotion record is written under (`runs/`), at "
            "runs/promotions/<run-id>.json. A path inside a reports/ directory is refused"
        ),
    )
    gate.add_argument(
        "--workspace",
        type=Path,
        required=True,
        metavar="<path>",
        help=(
            "where sandboxes and provisioned environments are built, exactly as --workspace "
            "does for a night"
        ),
    )
    gate.add_argument(
        "--timeout",
        type=float,
        required=True,
        metavar="<seconds>",
        help=(
            "seconds allowed per verification. No default, matching the verifiers: a limit "
            "inherited from elsewhere turns every slow task into an UNVERIFIED nobody can explain"
        ),
    )
    gate.add_argument(
        "--recorded-on",
        required=True,
        metavar="<date>",
        help=(
            "the date the operator declares for this comparison. An input, never the clock — "
            "a promotion record that dated itself would differ from itself between two renders "
            "of the same command"
        ),
    )
    gate.add_argument(
        "--run-id",
        required=True,
        metavar="<id>",
        help=(
            "the comparison's name, and the file it gets under runs/promotions/. An input for "
            "the reason --recorded-on is: a generated id makes two invocations of the same "
            "documented command produce two records nobody chose"
        ),
    )
    check = commands.add_parser(
        "check-leakage",
        help="prove a night's training set does not touch the held-out set",
        description=(
            "Compare a night's training set with the held-out membership and exit 0 iff they "
            "are disjoint (docs/ROADMAP.md:449-450). The night already excludes the held-out "
            "ids at its partition seam; this proves it, because an exclusion nobody checks is "
            "a claim — and the one claim this project cannot make on trust is that its "
            "headline was not measured on its own training data. A leak exits 1 and names the "
            "task; a run that cannot be identified or a document that cannot be trusted exits "
            "2. There is no flag that narrows either set: a leakage proof that could be turned "
            "green at the command line would prove nothing."
        ),
    )
    check.add_argument(
        "--run",
        required=True,
        type=Path,
        metavar="<runs/id>",
        help=(
            "a night's run directory. Its ledger identifies it as a night's run and its "
            "dataset.json is the training set — what was actually trained on, which is the "
            "only thing that can reach an adapter's weights"
        ),
    )
    check.add_argument(
        "--heldout",
        required=True,
        type=Path,
        metavar="<path>",
        help=(
            "the committed held-out document (tasks/heldout/source-b.json) whose membership "
            "the training set must not touch. Read through its own fail-closed loader: a "
            "hand-edited membership refuses before anything is compared"
        ),
    )
    return parser


def _exit_code(exc: SystemExit) -> int:
    """Translate the ``SystemExit`` argparse raises into a return code."""
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    print(code, file=sys.stderr)
    return USAGE_ERROR


def _verdict_exit_code(status: Status) -> int:
    """The documented code for a reduced status. Never 0 for anything but PASS."""
    return _VERDICT_EXIT_CODES.get(status, UNVERIFIED_EXIT)


def run_verify(task_path: Path, patch_path: Path) -> int:
    """Verify `patch_path` against `task_path`, print each verdict, and return the exit code.

    `task_path` is a manifest or a directory of them. Every task is verified against the same
    patch and the results reduce worst-status-wins, so the exit code answers "did this patch
    clear the whole set", which is the only question a promotion gate can act on.

    The two ways in are kept apart on purpose. An unreadable or malformed manifest, a directory
    holding something that is not a task, an **empty** directory, or a patch file that is not
    there, is a `USAGE_ERROR`: nothing was attempted, and the operator gave a path that does
    not resolve to a corpus. Only a reward run that happened and could not conclude is
    UNVERIFIED. Collapsing the first into the second would put a typo in the same bucket as a
    finding about a task — and in the empty-directory case it would be worse than a typo:
    `reduce` answers UNVERIFIED for an empty sequence, but the refusal happens in
    `load_tasks` before any reduction, because "you pointed me at nothing" is not a finding
    about a corpus that does not exist.
    """
    try:
        tasks = load_tasks(task_path)
    except ValueError as exc:
        print(f"whetstone verify: {exc}", file=sys.stderr)
        return USAGE_ERROR

    try:
        patch = patch_path.read_text()
    except OSError as exc:
        print(
            f"whetstone verify: could not read patch {str(patch_path)!r}: {exc}",
            file=sys.stderr,
        )
        return USAGE_ERROR

    # A fresh directory per invocation, removed on the way out: the run writes a checkout, a
    # pytest config and a report, and none of them are the operator's to clean up.
    #
    # `.resolve()` is load-bearing, not tidiness. On macOS the temporary directory is handed
    # back under `/var`, which is a symlink to `/private/var`; pytest is given the checkout as
    # its rootdir and then reports every path relative to the resolved location, so an
    # unresolved root makes the reported node ids unreconstructable and the run comes back
    # UNVERIFIED with a perfectly healthy suite behind it. Verified by hand: the same task and
    # patch reduce to PASS with a resolved root and UNVERIFIED without one.
    reached: list[Verdict] = []
    with tempfile.TemporaryDirectory(prefix="whetstone-verify-") as sandbox_root:
        root = Path(sandbox_root).resolve()
        for task in tasks:
            # `verify_strict` gives each task its own run directory under this root, so the
            # tasks cannot see each other's checkouts.
            try:
                result = verify_strict(
                    task, patch, sandbox_root=root, timeout=VERIFY_TIMEOUT_SECONDS
                )
            except UnsupportedPlatform as exc:
                # Reported and carried, not raised past the loop. Every remaining task will hit
                # the same wall, and stopping here would leave them with no verdict at all —
                # which is a shorter denominator, not a shorter run.
                _print_unverifiable(task, f"{exc}")
                reached.append(_task_verdict(task, Status.UNVERIFIED))
                continue
            _print_verdict(task, result)
            reached.append(_task_verdict(task, result.status))

    # Through `reduce`, not through a local max: the ordering that puts UNVERIFIED above PASS
    # is the honesty contract, and it is defined in exactly one place.
    return _verdict_exit_code(reduce(reached))


def run_mine(
    donor: Path, out: Path, *, label: str, limit: int, seed: int | None, tasks_root: Path
) -> int:
    """Mine `donor` into `out`, print what was minted and what was refused, and return the code.

    **A limit below one is a usage error rather than an empty run.** Minting nothing and exiting
    0 would claim a corpus that is not there — the same vacuous-green shape `load_task_directory`
    refuses for an empty directory, one step earlier.

    A donor that cannot be read is also a usage error: "you pointed me at the wrong directory" is
    a typo. A donor that was read and yielded no live task is different — it is a finding, so it
    exits FAIL with every rejection printed. The rejections name the donor's own commits and
    paths, which is the user's information: it goes to their terminal and never into the
    committed ledger or recipe.
    """
    if limit < 1:
        print(
            f"whetstone mine: --limit must be at least 1, got {limit}. A mint that produced no "
            f"task and exited 0 would claim a corpus that is not there",
            file=sys.stderr,
        )
        return USAGE_ERROR

    with tempfile.TemporaryDirectory(prefix="whetstone-mine-") as scratch:
        try:
            report = mine(
                donor,
                out,
                label=label,
                limit=limit,
                seed=seed,
                scratch=Path(scratch).resolve(),
                tasks_root=tasks_root,
                timeout=MINE_TIMEOUT_SECONDS,
            )
        except MintFailed as exc:
            print(f"whetstone mine: {exc}", file=sys.stderr)
            return USAGE_ERROR

    for task in report.minted:
        print(f"{task.task_id}: minted from {task.manifest}")
    for rejection in report.rejected:
        print(f"{rejection.sha[:12]}: rejected — {rejection.reason}")

    if not report.minted:
        print(
            f"whetstone mine: no task could be minted from {str(donor)!r}; "
            f"{len(report.rejected)} candidate(s) were rejected, for the reasons above",
            file=sys.stderr,
        )
        return FAIL_EXIT

    print(f"minted {len(report.minted)} task(s); rejected {len(report.rejected)}")
    print(f"evidence: {report.ledger} and {report.recipe}")
    return PASS_EXIT


def run_night(args: argparse.Namespace) -> int:
    """Dispatch one night into `whetstone.loop`, print its disclosure, and return the exit code.

    **The import is function-local, and that is the whole design of this function.** This module
    is a guarded root (`tests/test_no_inference_on_reward_path.py`): it calls `verify_strict`, it
    is the reward's entry point, and nothing it imports may reach an inference library. The loop
    reaches `mlx_lm` legitimately, so its body lives in the EXEMPT `whetstone.loop` package and
    this file holds exactly one edge into it — inside the handler, so `whetstone verify` and
    `whetstone mine` never execute it and never import `mlx_lm` even transitively. That the edge
    is the only one, and that it is function-local, is asserted by
    `tests/test_reward_path_scope_is_partitioned.py`; a second such import, or the same one moved
    to module scope, fails the build.

    **The exit code answers "is there a candidate", and never flatters.** A night that wrote a
    checkpoint is `PASS_EXIT`. A night that did not is floored at `FAIL_EXIT` even when its own
    task verdicts reduced to PASS — "the loop ran and produced nothing to promote" is a finding,
    and a caller checking `rc == 0` must never read it as a candidate. A control arm that proved
    nothing, or a verified rollout whose completion was never recorded, is `UNVERIFIED_EXIT`:
    nothing could be concluded, which is deliberately neither 0 nor a usage error.
    """
    from whetstone.loop.night import REFUSALS, UNPROVEN, disclosure
    from whetstone.loop.night import run_night as conduct_night

    try:
        night = conduct_night(
            tasks=args.tasks,
            public=args.public,
            pool=args.pool,
            weights=args.weights,
            runs=args.runs,
            checkpoints=args.checkpoints,
            workspace=args.workspace,
            timeout=args.timeout,
            recorded_on=args.recorded_on,
            run_id=args.run_id,
            run_seed=args.run_seed,
            dev_subset=args.dev_subset,
            heldout=args.heldout,
            only=args.only,
            probe=args.probe,
            retries=not args.no_retries,
        )
    except REFUSALS as refusal:
        print(f"whetstone run: {refusal}", file=sys.stderr)
        return USAGE_ERROR
    except UNPROVEN as unproven:
        print(f"whetstone run: {unproven}", file=sys.stderr)
        return UNVERIFIED_EXIT

    for line in disclosure(night):
        print(line)

    if night.checkpoint is not None:
        return PASS_EXIT
    # Floored at FAIL: `reduce` can answer PASS over a task set every draw solved, and a night
    # that solved everything and still wrote no candidate (a probe, a capacity finding) has not
    # produced the thing this command exists to produce.
    return max(FAIL_EXIT, _verdict_exit_code(night.status))


def run_gate_cli(args: argparse.Namespace) -> int:
    """Dispatch one gate comparison into `whetstone.loop.gate`, and return one of three codes.

    **The import is function-local, and that is the whole design of this function — the
    second documented edge from a guarded root into an exempt package, in the `run_night`
    shape.** The gate loads a checkpoint (base + LoRA adapter) through `mlx_lm`; this file is
    the reward's entry point; the import sits inside the handler so `whetstone verify` never
    executes it and never imports `mlx_lm` even transitively. That it is one of exactly two
    such edges, and that both are function-local, is asserted by
    `tests/test_reward_path_scope_is_partitioned.py`; a third such import, or either one
    moved to module scope, fails the build.

    **The exit codes are the roadmap's three, mapped onto the existing four-code contract**
    (`cli.py:64-84`, no fifth): `promoted` → 0, `rejected` → 1, `UNVERIFIED` → 3. UNVERIFIED
    is deliberately not 0 — a caller that checks only `rc == 0` must never read an eval that
    verified nothing as a promotion. A refusal an operator can fix by retyping the command —
    a checkpoint that cannot be re-hashed, a held-out document that cannot be read, a
    held-out set of zero, weights whose provenance does not match the disk — is 2, never a
    traceback.
    """
    from whetstone.loop.gate import REFUSALS, Exit, disclosure, gate_engine, run_gate

    exit_codes = {
        Exit.PROMOTED: PASS_EXIT,
        Exit.REJECTED: FAIL_EXIT,
        Exit.UNVERIFIED: UNVERIFIED_EXIT,
    }
    try:
        outcome = run_gate(
            candidate=args.candidate,
            incumbent=args.incumbent,
            heldout=args.heldout,
            tasks=args.tasks,
            public=args.public,
            pool=args.pool,
            weights=args.weights,
            runs=args.runs,
            workspace=args.workspace,
            timeout=args.timeout,
            recorded_on=args.recorded_on,
            run_id=args.run_id,
            engine=gate_engine,
        )
    except REFUSALS as refusal:
        print(f"whetstone gate: {refusal}", file=sys.stderr)
        return USAGE_ERROR

    for line in disclosure(outcome):
        print(line)
    return exit_codes[outcome.decision.exit]


def run_check_leakage_cli(args: argparse.Namespace) -> int:
    """Prove a night's training set disjoint from the held-out membership, and say so.

    **The import is function-local, and it is the third documented edge from a guarded root
    into an exempt package** — the `run_night` / `run_gate_cli` shape. This one does not need
    `mlx_lm` and never will: the check reads two JSON documents and compares two id sets. It
    is still function-local, because the edge's soundness argument is about the module graph
    of `whetstone verify` and not about what any one handler happens to need today —
    `whetstone.loop.check_leakage` imports `whetstone.loop.night` for the two source names,
    and a module-scope import here would put the night, the bake-off and `mlx_lm` on the
    reward's own entry path. `tests/test_reward_path_scope_is_partitioned.py` asserts these
    are the only three edges and that all three are function-local.

    **The exits are the existing contract, no fifth code**: disjoint → 0, a named overlap →
    1 (a leak is a failure, not a mistyped command), and a refusal an operator can fix — a
    directory that is not a night's run, an unreadable dataset, a held-out document whose
    digest does not match its contents — → 2. There is no `UNVERIFIED` exit here: this
    command reads documents rather than running anything, so it either answers or refuses.
    """
    from whetstone.loop.check_leakage import REFUSALS, disclosure, run_check

    try:
        report = run_check(args.run, args.heldout)
    except REFUSALS as refusal:
        print(f"whetstone check-leakage: {refusal}", file=sys.stderr)
        return USAGE_ERROR

    for line in disclosure(report):
        print(line)
    return PASS_EXIT if report.clean else FAIL_EXIT


def _task_verdict(task: Task, status: Status) -> Verdict:
    """One task's reduced status, as a Verdict, so a set of tasks folds the way sub-checks do."""
    return Verdict(
        kind="task",
        status=status,
        observed=task.task_id,
        expected=None,
        message=f"{task.task_id} reduced to {status.value}",
    )


def _print_verdict(task: Task, result: StrictResult) -> None:
    """The status, and for anything but a PASS, which sub-check fired and why.

    Sub-checks that passed are omitted rather than listed. Two reasons, and the second is the
    load-bearing one: what a reader needs from a refusal is the refusal, and printing the
    word PASS beneath an UNVERIFIED heading would put a success in the output of a run that
    verified nothing.
    """
    print(f"{task.task_id}: {result.status.value}")
    if result.status is Status.PASS:
        return
    for verdict in result.verdicts:
        if verdict.status is Status.PASS:
            continue
        print(f"  {verdict.kind}: {verdict.status.value} — {verdict.message}")


def _print_unverifiable(task: Task, message: str) -> None:
    """A run that never happened, rendered in the same shape as one that did."""
    print(f"{task.task_id}: {Status.UNVERIFIED.value}")
    print(f"  sandbox: {Status.UNVERIFIED.value} — {message}")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code; never raises ``SystemExit``."""
    args = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    if not args:
        parser.print_usage(sys.stderr)
        print(
            "whetstone: nothing to do — see `whetstone --help` for what exists today.",
            file=sys.stderr,
        )
        return USAGE_ERROR

    try:
        namespace = parser.parse_args(args)
    except SystemExit as exc:
        return _exit_code(exc)

    if namespace.command == "verify":
        return run_verify(namespace.task, namespace.patch)

    if namespace.command == "mine":
        return run_mine(
            namespace.donor,
            namespace.out,
            label=namespace.label,
            limit=namespace.limit,
            seed=namespace.seed,
            tasks_root=namespace.tasks_root,
        )

    if namespace.command == "run":
        return run_night(namespace)

    if namespace.command == "gate":
        return run_gate_cli(namespace)

    if namespace.command == "check-leakage":
        return run_check_leakage_cli(namespace)

    # Every input the CLI accepts is handled above. Falling through means a flag or a
    # subcommand was added without a behaviour behind it: report usage and fail rather than
    # exit 0 silently.
    parser.print_usage(sys.stderr)
    return USAGE_ERROR
