"""Where the suite's *test runner* comes from — committed, not cached.

Several tests here build a throwaway venv and verify a task inside it, because the reward runs a
task's declared tests as ``<the nominated interpreter>/bin/python -m pytest``. Each of those
venvs therefore needs a ``pytest`` of its own, provisioned **offline**: every install this suite
performs carries ``--offline``, since a suite that fetched from a registry would make its own
results depend on what that registry served that morning — the precise failure the
``environment`` contract exists to close.

``uv pip install --offline pytest`` satisfies "offline" and nothing else. It resolves from uv's
cache alone, and **whether that cache can answer is a property of the machine, not of this
repository.** A developer's cache holds pytest's registry metadata from some earlier resolution,
so it answers; a cold CI runner's does not — ``uv sync`` installs from a lockfile and never
performs the resolution that would cache it — so it fails:

    No solution found when resolving dependencies: because pytest was not
    found in the cache and you require pytest, we can conclude that your
    requirements are unsatisfiable.

That is a suite whose green depends on who ran it, which is not a result. So the runner is
committed at ``tests/fixtures/wheelhouse`` and this file points every ``uv`` invocation in the
session at it.

**The distinction this rests on, and it is the whole design.** ``pytest`` is *scaffolding* — it
is how a declared test gets executed at all, and no claim in this suite is about which pytest
ran. ``whetstone-fixture-dep`` is a *subject*: ``tests/test_environment_pins.py`` shows one task
and one patch reaching PASS under one version of it and FAIL under another, and that resolution
must come from the committed ``tests/fixtures/pkgindex`` and from nowhere else. Provisioning the
first from a wheelhouse weakens nothing; provisioning the second from anywhere but the recorded
index would make the file self-refuting. The two therefore live in different directories and are
resolved by different commands.

**Why an environment variable rather than a flag at each call site.** Some of these installs are
issued by *shipped code* — ``whetstone.tasks.environment.capture`` provisions the runner into a
mined donor's venv — and threading a test-only wheelhouse through the miner's API and its CLI
would put a fixture in the product. ``UV_FIND_LINKS`` is uv's own spelling for "also look here",
it is read by every ``uv`` subprocess this session starts, and an explicit ``--find-links`` on a
command line **overrides** it. That last property is what keeps the subject clean: the fixture
dep is resolved with ``--offline --no-index --no-cache --find-links <pkgindex>``, so the
wheelhouse is not merely outranked there, it is not consulted at all.

Nothing here touches the network. A wheelhouse is a directory of files.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fixtures.runner import FIND_LINKS, RUNNER, WHEELHOUSE


@pytest.fixture(scope="session", autouse=True)
def runner_wheelhouse() -> Iterator[Path]:
    """Point every `uv` subprocess this session starts at the committed runner wheels.

    Autouse and session-scoped because the installs it serves are spread across fixture modules
    and shipped code, and a fixture that had to be requested would be a fixture some future test
    forgets to request — reintroducing exactly the failure this exists to close, and
    reintroducing it *silently on the machine of whoever wrote the test*.

    The variable is **set, not defaulted**. If an operator has their own `UV_FIND_LINKS`, the
    suite's provisioning must still be the suite's, or "which pytest ran" becomes a property of
    the shell it was run from. It is restored when the session ends.

    Raises rather than skips when the wheelhouse is missing or empty: a silently skipped
    provisioning fixture is a green suite in which nothing was ever executed, which is the same
    class of lie as rendering UNVERIFIED as PASS.
    """
    if not any(WHEELHOUSE.glob(f"{RUNNER}-*.whl")):
        raise RuntimeError(
            f"{WHEELHOUSE} holds no {RUNNER} wheel, so every throwaway venv in this suite would "
            f"fall back to resolving {RUNNER} from whatever this machine's uv cache happens to "
            f"hold. That passes on a developer's machine and fails on a cold runner, which is "
            f"the exact defect the wheelhouse exists to close. Restore it (see its README) "
            f"rather than removing the fixture"
        )

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(FIND_LINKS, str(WHEELHOUSE))
        yield WHEELHOUSE
