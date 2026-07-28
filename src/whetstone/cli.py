"""The `whetstone` command line entry point.

The failure this module prevents: a ``--help`` that advertises work the code cannot do.
Commands appear here only when something stands behind them — and for the first time one
does. ``verify`` runs the execution-grounded reward in `whetstone.verify.strict`: it applies
a patch to a task's known-broken commit inside a sandbox, restores the operator-held tests
from golden, and compares what pytest actually executed against what the task declared. There
is still no loop, no gate and no report, so there are still no stubs for those.

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
from whetstone.verify.sandbox import UnsupportedPlatform
from whetstone.verify.strict import StrictResult, verify_strict
from whetstone.verify.task import Task, load_task
from whetstone.verify.verdict import Status

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

DESCRIPTION = "Whetstone — a model that trains itself overnight, and proves it didn't cheat."

_VERIFY_DESCRIPTION = (
    "Verify a patch against a task by re-executing the task's own tests in a sandbox. "
    "Exits 0 on PASS, 1 on FAIL, 2 on a usage error, and 3 when nothing could be verified."
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
        help="the operator-controlled task manifest (JSON)",
    )
    verify.add_argument(
        "--patch",
        required=True,
        type=Path,
        metavar="<path>",
        help="the patch to verify, as a unified diff",
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
    """Verify `patch_path` against `task_path`, print the verdict, and return its exit code.

    The two ways in are kept apart on purpose. An unreadable or malformed manifest, or a patch
    file that is not there, is a `USAGE_ERROR`: nothing was attempted, and the operator gave a
    path that does not resolve. Only a reward run that happened and could not conclude is
    UNVERIFIED. Collapsing the first into the second would put a typo in the same bucket as a
    finding about a task.
    """
    try:
        task = load_task(task_path)
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
    with tempfile.TemporaryDirectory(prefix="whetstone-verify-") as sandbox_root:
        try:
            result = verify_strict(
                task,
                patch,
                sandbox_root=Path(sandbox_root).resolve(),
                timeout=VERIFY_TIMEOUT_SECONDS,
            )
        except UnsupportedPlatform as exc:
            _print_unverifiable(task, f"{exc}")
            return UNVERIFIED_EXIT

    _print_verdict(task, result)
    return _verdict_exit_code(result.status)


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

    # Every input the CLI accepts is handled above. Falling through means a flag or a
    # subcommand was added without a behaviour behind it: report usage and fail rather than
    # exit 0 silently.
    parser.print_usage(sys.stderr)
    return USAGE_ERROR
