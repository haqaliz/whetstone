"""Gate 2: the declared ids are found by pytest in the real checkout, or the instance is refused.

**This is the gate that catches what no string rule can.** SWE-bench itself carries 12 node ids
split on whitespace by whatever produced the dataset —
`tests/test_cli.py::test_locate_app[cliapp.factory-create_app2("foo",` — and gate 1 deliberately
lets them through, because a bracket-balance rule would be a guess wearing a gate's clothes. Here
pytest is simply asked to find them, in the checkout the reward will run in.

**Why an unfindable id is worse than a failing one.** pytest exits 4 when it cannot address what
it was given, and `strict.py` maps that to UNVERIFIED — which aborts the run rather than grading
it. One such instance in a corpus does not cost one task; it costs the verdict of everything the
run was reducing. That is the cost gate 2 buys out.

**And the reverse failure, which is quieter.** A parametrised id declared *bare* — `test_p`
rather than `test_p[1]` — collects perfectly happily and expands into several. The executed set
then never equals the declared set, so STRICT answers FAIL for every patch forever, with nothing
in the verdict pointing at the manifest. The gate compares the collected set against the declared
set for exactly that reason.

Offline: a directory of test files, collected inside the Seatbelt sandbox, which denies the
network outright. No git and no clone — gate 2 asks a question about a directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from whetstone.tasks.gates import GATE_COLLECTABILITY, Ineligible, check_collectable

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="collection runs inside the Seatbelt sandbox, which is macOS-only",
)

#: As in `tests/test_strict.py`: long enough that a slow machine is not misreported as an
#: uncollectable instance, short enough that a hung run does not hold the suite.
_TIMEOUT = 120.0

#: A test file with one plain test and one parametrised test, which is the minimum that can
#: distinguish "not found" from "found, but it expanded".
_SUITE = """\
import pytest


def test_plain():
    assert True


@pytest.mark.parametrize("value", [1, 2])
def test_parametrised(value):
    assert value
"""


@pytest.fixture(scope="module")
def checkout(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A directory holding one collectable test file. Not a git repository — none is needed."""
    root = tmp_path_factory.mktemp("gate2").resolve()
    (root / "tests").mkdir()
    (root / "tests" / "test_suite.py").write_text(_SUITE)
    return root


def _collect(checkout: Path, node_ids: list[str], workspace: Path) -> tuple[str, ...]:
    return check_collectable(
        node_ids, checkout=checkout, workspace=workspace, timeout=_TIMEOUT
    )


# --------------------------------------------------------------------------------------
# The positive case, and the control that keeps it honest
# --------------------------------------------------------------------------------------


def test_ids_that_exist_in_the_checkout_are_collected(checkout: Path, tmp_path: Path) -> None:
    """The gate returns what pytest found, so the caller can see it rather than assume it."""
    collected = _collect(
        checkout,
        ["tests/test_suite.py::test_plain", "tests/test_suite.py::test_parametrised[1]"],
        tmp_path,
    )

    assert set(collected) == {
        "tests/test_suite.py::test_plain",
        "tests/test_suite.py::test_parametrised[1]",
    }


def test_the_gate_actually_collected_something(checkout: Path, tmp_path: Path) -> None:
    """Anti-vacuity: a gate that collected nothing and compared two empty sets would pass.

    Returning the collected ids rather than `None` is what makes this assertable at all, and it
    is the reason the signature is what it is.
    """
    collected = _collect(checkout, ["tests/test_suite.py::test_plain"], tmp_path)

    assert collected


# --------------------------------------------------------------------------------------
# The 12 corrupted ids, killed by execution rather than by pattern
# --------------------------------------------------------------------------------------


def test_a_truncated_parametrised_id_is_rejected_by_collection(
    checkout: Path, tmp_path: Path
) -> None:
    """The shape SWE-bench's own data carries, refused because pytest cannot find it.

    Note what is *not* happening: nothing here counts brackets. The id is handed to pytest, which
    reports it as not found and exits 4, and that exit is the evidence. If the dataset's
    corruption ever takes another shape, this gate still catches it and a string rule would not.
    """
    with pytest.raises(Ineligible) as raised:
        _collect(checkout, ['tests/test_suite.py::test_parametrised[1,'], tmp_path)

    assert raised.value.gate == GATE_COLLECTABILITY
    assert "test_parametrised[1," in str(raised.value)


def test_an_id_naming_a_file_that_is_not_there_is_rejected(
    checkout: Path, tmp_path: Path
) -> None:
    """An instance whose declared file the base commit does not carry is not verifiable."""
    with pytest.raises(Ineligible) as raised:
        _collect(checkout, ["tests/test_absent.py::test_x"], tmp_path)

    assert raised.value.gate == GATE_COLLECTABILITY


def test_the_rejection_says_pytest_could_not_address_the_id(
    checkout: Path, tmp_path: Path
) -> None:
    """A refusal has to name the consequence, not just the symptom.

    An unfindable id makes pytest exit 4, `strict.py` maps 4 to UNVERIFIED, and an UNVERIFIED
    aborts the run rather than grading it. A reader who only saw "collection failed" would think
    they had lost one task.
    """
    with pytest.raises(Ineligible) as raised:
        _collect(checkout, ["tests/test_absent.py::test_x"], tmp_path)

    assert "UNVERIFIED" in str(raised.value)


# --------------------------------------------------------------------------------------
# The quieter failure: an id that collects into more than one
# --------------------------------------------------------------------------------------


def test_a_bare_parametrised_id_is_rejected_because_it_expands(
    checkout: Path, tmp_path: Path
) -> None:
    """It collects fine and is still unusable, which is why exit code 0 is not the whole gate.

    `test_parametrised` expands into `[1]` and `[2]`. The executed set would then never equal the
    declared set, and STRICT would answer FAIL for every patch forever with nothing in the
    verdict pointing at the manifest.
    """
    with pytest.raises(Ineligible) as raised:
        _collect(checkout, ["tests/test_suite.py::test_parametrised"], tmp_path)

    assert raised.value.gate == GATE_COLLECTABILITY
    assert "test_parametrised[1]" in str(raised.value)


def test_an_empty_declaration_is_refused_rather_than_collected(
    checkout: Path, tmp_path: Path
) -> None:
    """Handing pytest no ids collects the whole suite, which answers a different question."""
    with pytest.raises(Ineligible):
        _collect(checkout, [], tmp_path)
