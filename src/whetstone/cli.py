"""The `whetstone` command line entry point.

The failure this module prevents: a ``--help`` that advertises work the code cannot do.
P0 has no verifier, no loop, and no gate, so the CLI exposes exactly two behaviours —
``--help`` and ``--version`` — and no subcommand stubs. Commands appear here only when
something stands behind them.

``main`` returns an ``int`` instead of calling ``sys.exit`` so tests can assert on the exit
code directly. argparse exits the process for ``--help``, ``--version``, and usage errors;
those exits are caught and translated back into return codes rather than escaping as
exceptions.

Bare ``whetstone`` prints usage and returns non-zero. A no-op that exits 0 is a claim that
something worked, and nothing did.
"""

import argparse
import sys

from whetstone import __version__

#: argparse's own convention for "you invoked me wrongly".
USAGE_ERROR = 2

DESCRIPTION = "Whetstone — a model that trains itself overnight, and proves it didn't cheat."


def build_parser() -> argparse.ArgumentParser:
    """The parser, built in one place so tests can introspect the flags that really exist."""
    parser = argparse.ArgumentParser(prog="whetstone", description=DESCRIPTION)
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="print the installed whetstone version and exit",
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
        parser.parse_args(args)
    except SystemExit as exc:
        return _exit_code(exc)

    # Every input P0 accepts leaves through argparse above. Falling through means a flag was
    # added without a behaviour behind it: report usage and fail rather than exit 0 silently.
    parser.print_usage(sys.stderr)
    return USAGE_ERROR
