"""Where the throwaway venvs in this suite get their `pytest` — named once, used everywhere.

The constants live here rather than in `conftest.py` so that a test can import them without
importing the conftest module by name, and so the one directory this suite provisions its runner
from has a single spelling. `conftest.py` owns the fixture that puts it into effect and carries
the reasoning; `tests/fixtures/wheelhouse/README.md` carries the record of what is in it.
"""

from __future__ import annotations

import os
from pathlib import Path

#: The committed runner wheels. Scaffolding, never a subject: no claim in this suite is about
#: which pytest ran, only that the declared tests were executed by one.
WHEELHOUSE = Path(__file__).resolve().parent / "wheelhouse"

#: uv's own spelling of "resolve from this directory as well as from the cache". An explicit
#: `--find-links` on a command line overrides it, which is what keeps the versions under study
#: (`tests/fixtures/pkgindex`) resolvable from their own directory and from nothing else.
FIND_LINKS = "UV_FIND_LINKS"

#: What every throwaway venv here needs before it can run a task's declared tests at all.
RUNNER = "pytest"


def uv_environment(**overrides: str) -> dict[str, str]:
    """This process's environment with `overrides` applied — for a test that runs `uv` itself.

    Exists so a test can vary one uv setting (an empty `UV_CACHE_DIR`, an absent `UV_FIND_LINKS`)
    without hand-assembling an environment and accidentally dropping `PATH` — which would fail
    for a reason with nothing to do with what it claims. An override of `""` removes the
    variable, since that is how "this machine has no such setting" is spelled.
    """
    environment = dict(os.environ)
    for name, value in overrides.items():
        if value:
            environment[name] = value
        else:
            environment.pop(name, None)
    return environment


__all__ = ["FIND_LINKS", "RUNNER", "WHEELHOUSE", "uv_environment"]
