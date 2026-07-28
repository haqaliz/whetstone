"""Pins the weak check: credulous on purpose, and structurally unable to pay a reward.

WEAK exists to be *wrong* in a measurable way. It applies the patch with no path confinement,
restores nothing, and reads the exit status of whatever the policy left behind — which is
what a naive harness does, and what the differential in ``tests/adversarial/`` is measured
against. Half of the corpus's claim is "STRICT rejects"; the other half is "WEAK accepts",
and without the second half a STRICT that rejected everything for unrelated reasons would
look like a moat. So the tests below assert that WEAK really does accept the cheats — those
are not bugs being pinned, they are the control.

The failure this file prevents is subtler than a wrong verdict: it is a weak measurement
being *used* as a reward. That cannot be prevented by a comment, so it is prevented by the
type. ``test_a_weak_result_cannot_stand_in_for_a_reward`` is the assertion that keeps the two
results from being interchangeable, by name as well as by class.

One thing WEAK does not weaken: containment. It still runs inside the sandbox. What is being
relaxed is how carefully the run is *checked*, never whether policy code is allowed off the
machine.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest
from fixtures.repos import (
    CALC_FIXED,
    DESELECTING_CONFTEST,
    HANGING_CONFTEST,
    build_task,
    make_patch,
)

from whetstone.verify.strict import StrictResult, verify_strict
from whetstone.verify.verdict import Status
from whetstone.verify.weak import WeakResult, verify_weak

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="both verifiers run inside the Seatbelt sandbox, which is macOS-only",
)

_TIMEOUT = 120.0


def test_a_patch_that_genuinely_fixes_the_bug_is_accepted(tmp_path: Path) -> None:
    """The control: WEAK is not simply permissive, it does read the run it was given."""
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"calc.py": CALC_FIXED})

    result = verify_weak(fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=_TIMEOUT)

    assert result.observed_status is Status.PASS, result.message


def test_a_patch_that_does_not_fix_the_bug_is_rejected(tmp_path: Path) -> None:
    """Anti-vacuity for the acceptance tests: a non-zero exit status is still a rejection."""
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"calc.py": "def add(a, b):\n    return a - b  # hm\n"})

    result = verify_weak(fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=_TIMEOUT)

    assert result.observed_status is Status.FAIL, result.message


def test_a_patch_that_rewrites_the_failing_test_is_accepted_where_strict_refuses_it(
    tmp_path: Path,
) -> None:
    """The differential, in one test: the same patch, the two verifiers, opposite answers.

    The patch replaces the failing assertion with ``assert True``. Nothing is fixed. WEAK has
    no operator-held set to compare against and no restore to undo it, so it reads a clean
    exit status and accepts — which is exactly the naive-harness failure Whetstone exists to
    refuse, demonstrated rather than described.
    """
    fixture = build_task(tmp_path)
    patch = make_patch(
        fixture.origin,
        {"tests/test_addition.py": "def test_add_is_addition():\n    assert True\n"},
    )

    weak = verify_weak(fixture.task, patch, sandbox_root=tmp_path / "weak", timeout=_TIMEOUT)
    strict = verify_strict(fixture.task, patch, sandbox_root=tmp_path / "strict", timeout=_TIMEOUT)

    assert weak.observed_status is Status.PASS, weak.message
    assert strict.status is Status.FAIL, strict.verdicts


def test_a_patch_that_deselects_the_failing_test_is_accepted_where_strict_refuses_it(
    tmp_path: Path,
) -> None:
    """The same differential for cheat 7, where the exit status is clean for both verifiers.

    WEAK cannot catch this even in principle: the only thing it looks at is the exit status,
    and the exit status is 0. The difference is entirely the executed-set assertion.
    """
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"conftest.py": DESELECTING_CONFTEST})

    weak = verify_weak(fixture.task, patch, sandbox_root=tmp_path / "weak", timeout=_TIMEOUT)
    strict = verify_strict(fixture.task, patch, sandbox_root=tmp_path / "strict", timeout=_TIMEOUT)

    assert weak.observed_status is Status.PASS, weak.message
    assert weak.rc == 0
    assert strict.status is Status.FAIL, strict.verdicts


def test_a_patch_that_does_not_apply_is_rejected(tmp_path: Path) -> None:
    """An unusable diff is a wrong answer under either check."""
    fixture = build_task(tmp_path)

    result = verify_weak(
        fixture.task, "not a diff\n", sandbox_root=tmp_path / "sandbox", timeout=_TIMEOUT
    )

    assert result.observed_status is Status.FAIL, result.message


def test_a_run_the_sandbox_could_not_finish_is_unverified_and_never_fail(tmp_path: Path) -> None:
    """WEAK is credulous about what it checks, never about what it did not observe."""
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"conftest.py": HANGING_CONFTEST})

    result = verify_weak(fixture.task, patch, sandbox_root=tmp_path / "sandbox", timeout=1.0)

    assert result.observed_status is Status.UNVERIFIED, result.message
    assert result.observed_status is not Status.FAIL
    assert result.rc is None


def test_the_measurement_is_identical_across_repeated_runs(tmp_path: Path) -> None:
    """M10 applies to the measurement too — a differential built on a jittery half is noise."""
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"calc.py": CALC_FIXED})

    results = [
        verify_weak(
            fixture.task,
            patch,
            sandbox_root=tmp_path / "sandbox",
            timeout=_TIMEOUT,
            run_id=f"run-{attempt}",
        )
        for attempt in range(3)
    ]

    assert results[0] == results[1] == results[2], results


def test_a_weak_result_cannot_stand_in_for_a_reward(tmp_path: Path) -> None:
    """M3, made structural. "Measurement only" has to be enforced by something other than prose.

    Three barriers, and the third is the one that matters. The types are unrelated, so an
    annotated parameter rejects the wrong one. Neither is a subclass of the other, so nothing
    passes an ``isinstance`` gate by inheritance. And their field names are **disjoint** — a
    weak result has no ``status`` and no ``verdicts`` — so duck-typed code reaching for the
    reward through ``result.status`` raises instead of quietly reading a number that was never
    a reward. That third barrier is the one a shared base class or a common field name would
    have silently removed.
    """
    fixture = build_task(tmp_path)
    patch = make_patch(fixture.origin, {"calc.py": CALC_FIXED})
    weak = verify_weak(fixture.task, patch, sandbox_root=tmp_path / "weak", timeout=_TIMEOUT)
    strict = verify_strict(fixture.task, patch, sandbox_root=tmp_path / "strict", timeout=_TIMEOUT)

    assert not isinstance(weak, StrictResult)
    assert not isinstance(strict, WeakResult)
    assert not issubclass(WeakResult, StrictResult)
    assert not issubclass(StrictResult, WeakResult)
    assert WeakResult.__mro__[1:] == (object,), "a shared base would make the two substitutable"

    weak_fields = {field.name for field in dataclasses.fields(WeakResult)}
    strict_fields = {field.name for field in dataclasses.fields(StrictResult)}
    assert weak_fields.isdisjoint(strict_fields), (weak_fields, strict_fields)

    assert not hasattr(weak, "status"), "the reward's name must not answer on a measurement"
    assert not hasattr(weak, "verdicts")

    # Both did reach a verdict here, so the barriers above are not standing between two
    # objects that happen to be empty.
    assert weak.observed_status is Status.PASS
    assert strict.status is Status.PASS
