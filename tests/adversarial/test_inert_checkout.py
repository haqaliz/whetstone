"""The code under test must be the checkout the patch was applied to. Nothing else may decide.

**This is not one of the ten cheats and deliberately is not in `CHEATS`.** Nobody authors it:
the submission that collects the reward here is the *empty* one. It is the resolver's-clock
hole's sibling — a reward corrupted with no adversary in the room — and it is filed the same
way `docs/ROADMAP.md` § 3 files that one: as prose and a standalone proof rather than as a
table row, because the table's fourth column reports a **differential** (STRICT refuses while
WEAK accepts) and this has none. Both verifiers were wrong in the same direction, and the fix
is in the task contract and the harness, not in a defence STRICT was missing.

**What went wrong, precisely.** A `src`-layout donor is imported by package name — contig's
tests say `import contig`, not `import src.contig` — so the name resolves through whatever the
interpreter's `sys.path` offers. `uv sync --frozen --project <checkout>` installed the project
**editable**, rooted at the checkout the miner provisioned in, which was a *different directory*
from the checkout the reward applies patches to. The run's own tree was therefore never
imported. Observed with `uv pip freeze` reporting `-e file:///…/donor`, and with
`import contig.self_heal` resolving to the provisioning checkout's `src/`.

**Why the corpus missed it.** Every fixture repository was flat — `calc.py` beside `tests/` —
and none was installed into a venv. Under `python -m pytest` with the checkout as the working
directory, a flat layout puts the code under test at `sys.path[0]`, where nothing can shadow
it. The defence was the fixtures' shape, not the verifier's.

**The proof shape, and why the patch is not the empty string.** `git apply` refuses an empty
diff, so `verify_strict(task, "")` returns FAIL from `patch-apply` before a single test runs —
and every task then looks fine, this one included. `liveness.py` records the same trap. So the
no-patch arm applies `inert_patch()`, a real diff adding one inert non-python file, and the
assertions additionally require that tests **actually ran**. A FAIL nobody ran a test for is
not evidence about anything.

Observed on this machine, 2026-07-28, before the fix: STRICT returned **PASS** for a task
verified with no patch applied. Real `sandbox-exec`, real git, real pytest, real venv.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fixtures.repos import CALC_FIXED, Fixture, build_task, make_patch
from fixtures.repos.packaged import (
    SRC_LAYOUT_CALC,
    SRC_MODULE,
    can_import_calc,
    stale_interpreter,
)

from whetstone.tasks.liveness import inert_patch
from whetstone.verify.strict import verify_strict
from whetstone.verify.verdict import Status

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="the reward runs inside the Seatbelt sandbox, which is macOS-only",
)

_TIMEOUT = 120.0


@pytest.fixture(scope="module")
def shadowed(tmp_path_factory: pytest.TempPathFactory) -> tuple[Fixture, Path]:
    """A `src`-layout task, and an interpreter that already has a FIXED `calc` in it.

    Module-scoped because the venv is the expensive part and both arms below want the same one:
    the mirror is only evidence that the fix did not simply break everything if it runs against
    the identical interpreter, with the identical stale copy still sitting in it.
    """
    root = tmp_path_factory.mktemp("inert-checkout")
    return build_task(root, SRC_LAYOUT_CALC, task_id="src-layout-adder"), stale_interpreter(root)


def test_the_stale_install_really_does_supply_a_passing_calc(
    shadowed: tuple[Fixture, Path], tmp_path: Path
) -> None:
    """Anti-vacuity. Without this, both assertions below could pass for the wrong reason.

    If the venv could not import `calc` at all — a mistyped `.pth`, a site-packages directory
    that moved — then the no-patch arm would FAIL because nothing imported, not because the
    right thing imported, and the mirror would be the only test doing any work. The check is run
    from a directory that is not a checkout, so what it observes is the interpreter's own
    `sys.path` and nothing a working directory contributed.
    """
    _, interpreter = shadowed
    elsewhere = tmp_path / "not-a-checkout"
    elsewhere.mkdir()

    assert can_import_calc(interpreter, cwd=elsewhere), (
        "the stale copy is not importable under this interpreter, so it cannot shadow anything "
        "and the tests below would prove nothing"
    )


def test_a_checkout_outside_the_run_cannot_pay_the_reward_for_an_empty_submission(
    shadowed: tuple[Fixture, Path], tmp_path: Path
) -> None:
    """**The RED.** No patch, a fixed copy installed elsewhere, and the reward must not be paid.

    The task's `fail_to_pass` test asserts `add(2, 3) == 5`. The checkout under verification
    contains the bug and nothing was applied to it, so the only way this test can pass is by
    importing a `calc` from somewhere the run does not control. That is what the interpreter's
    stale install offers, and before the fix the reward took it.

    `executed` is asserted non-empty for the same reason `liveness._require_the_tests_ran`
    exists: a FAIL reached before pytest ran would satisfy the status assertion while proving
    the opposite of what this test claims.

    Observed before the fix: `Status.PASS`, every sub-verdict passing. Observed after:
    `Status.FAIL` at `fail-to-pass`, with the declared set executed exactly.
    """
    fixture, interpreter = shadowed

    result = verify_strict(
        fixture.task,
        inert_patch(),
        sandbox_root=tmp_path / "no-patch",
        timeout=_TIMEOUT,
        interpreter=interpreter,
    )

    assert result.status is not Status.PASS, (
        "the reward was paid for a run with no patch applied. The declared test can only pass "
        "against code that is not in this checkout, so the verdict was decided by a directory "
        "outside the run — and a policy that submitted nothing would be paid for it"
    )
    assert result.status is Status.FAIL, result.verdicts
    assert result.executed, (
        "no test ran, so the FAIL is not evidence about which checkout was imported"
    )
    assert set(result.executed) == set(fixture.task.fail_to_pass) | set(
        fixture.task.pass_to_pass
    ), result.executed


def test_the_same_task_still_passes_under_its_reference_patch(
    shadowed: tuple[Fixture, Path], tmp_path: Path
) -> None:
    """The mirror, and it is what stops the fix from being "make everything FAIL".

    Same task, same interpreter, same stale copy still installed — only the patch differs. It
    fixes the module inside the checkout, which is the tree the reward is now guaranteed to be
    importing, so the reward is paid. A defence that shadowed the install by breaking imports
    outright would fail here.
    """
    fixture, interpreter = shadowed
    patch = make_patch(fixture.origin, {SRC_MODULE: CALC_FIXED})

    result = verify_strict(
        fixture.task,
        patch,
        sandbox_root=tmp_path / "reference",
        timeout=_TIMEOUT,
        interpreter=interpreter,
    )

    assert result.status is Status.PASS, result.verdicts
    assert [verdict.status for verdict in result.verdicts] == [Status.PASS] * 4
