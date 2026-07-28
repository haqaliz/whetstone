"""The four gates, each proving rather than assuming — and the ledger that records every refusal.

Source A is narrow, and the deliverable is not the instances it yields: it is the **filter**, and
the published account of everything the filter turned away. So every test here is about a
refusal, and the last section is about the property that makes those refusals trustworthy —
**nothing vanishes**: the ledger's count plus the eligible count equals the input count.

**Gate 1 is a format check and deliberately stops short of a string heuristic for the truncated
ids.** SWE-bench's own data carries 12 whitespace-split parametrised node ids, and it is tempting
to catch them here with a bracket-balance rule. That would be a guess dressed as a gate: the only
assumption-free detector is asking pytest to collect them in the real checkout, which is gate 2.
Gate 1 therefore kills exactly what it can prove — django's unittest-runner form and sympy's bare
names, 64% of Lite — and passes the truncated ones through to be caught by execution.

Offline and deterministic: these tests build ids and rejections directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whetstone.tasks.gates import (
    GATE_COLLECTABILITY,
    GATE_ENVIRONMENT,
    GATE_FORMAT,
    GATE_LIVENESS,
    GATES,
    Ineligible,
    Rejection,
    check_format,
    read_ineligible,
    write_ineligible,
)

#: The real shape of a django instance's declared test, from SWE-bench-Lite. It is not a node id
#: at all — it is what django's own unittest runner prints — and no amount of parsing makes it
#: one.
DJANGO_FORM = "test_ticket_11293 (queries.tests.Queries1Tests)"

#: The real shape of a sympy instance's declared test: a bare function name with no file path.
#: pytest cannot address it without knowing which of 900 files it lives in.
SYMPY_FORM = "test_solve_linear_system"

#: The real shape of one of the 12 ids SWE-bench itself has corrupted: a parametrised id split on
#: whitespace by whatever produced the dataset. Gate 1 must NOT reject this — see the module
#: docstring.
TRUNCATED_FORM = 'tests/test_cli.py::test_locate_app[cliapp.factory-create_app2("foo",'


# --------------------------------------------------------------------------------------
# Gate 1 — format
# --------------------------------------------------------------------------------------


def test_the_django_unittest_runner_form_is_rejected_naming_the_gate() -> None:
    """64% of Lite dies here, and the ledger has to say which gate did it.

    A rejection whose gate is not recorded is a number nobody can audit: "192 instances were
    excluded" is a claim, while "192 were excluded at the format gate, here they are" is
    evidence.
    """
    with pytest.raises(Ineligible) as raised:
        check_format([DJANGO_FORM])

    assert raised.value.gate == GATE_FORMAT
    assert DJANGO_FORM in str(raised.value)


def test_the_sympy_bare_name_form_is_rejected_naming_the_gate() -> None:
    """A bare function name has no file path, so pytest has nothing to address."""
    with pytest.raises(Ineligible) as raised:
        check_format([SYMPY_FORM])

    assert raised.value.gate == GATE_FORMAT


def test_a_truncated_parametrised_id_passes_the_format_gate() -> None:
    """The one that must NOT be caught here, and it is the point of the whole gate ordering.

    A bracket-balance rule would reject it and would look like a win. It would also be a string
    heuristic standing in for a proof, and the moment SWE-bench's corruption took a different
    shape the gate would pass it silently. Collection against the real checkout is the only
    assumption-free detector, and that is gate 2's job.
    """
    check_format([TRUNCATED_FORM])


@pytest.mark.parametrize(
    "node_id",
    [
        "tests/test_cli.py::test_simple",
        "tests/test_cli.py::TestGroup::test_method",
        "tests/test_cli.py::test_parametrised[1-2]",
        "src/flask/tests/test_x.py::test_y",
    ],
)
def test_a_well_formed_node_id_passes(node_id: str) -> None:
    """The shapes pytest actually addresses, including class-qualified and parametrised."""
    check_format([node_id])


@pytest.mark.parametrize(
    "node_id",
    [
        "tests/test_cli.py",
        "tests/test_cli.txt::test_x",
        "/abs/tests/test_cli.py::test_x",
        "../outside/test_cli.py::test_x",
        "./tests/test_cli.py::test_x",
        "tests/test_cli.py::",
        "  tests/test_cli.py::test_x",
        "",
    ],
)
def test_an_id_that_is_not_addressable_as_a_node_id_is_rejected(node_id: str) -> None:
    """Each of these fails for its own reason, and each reason is a way the run would break.

    No `::` at all is a path, not a test. A non-`.py` file is not a module pytest imports. An
    absolute or escaping path is not repository-relative, so the checkout it names is not the one
    the patch was applied to. A non-canonical `./` spelling is the trap `_check_blob_path`
    documents: it loads and then matches nothing git ever says. An empty trailing component
    addresses nothing. Leading whitespace is not stripped on the operator's behalf here for the
    same reason it is not stripped there.
    """
    with pytest.raises(Ineligible) as raised:
        check_format([node_id])

    assert raised.value.gate == GATE_FORMAT


def test_the_gate_reports_every_offending_id_not_only_the_first() -> None:
    """A rejection that named one id would make a two-line fix look like a one-line fix."""
    with pytest.raises(Ineligible) as raised:
        check_format([DJANGO_FORM, SYMPY_FORM, "tests/test_cli.py::test_ok"])

    message = str(raised.value)
    assert DJANGO_FORM in message
    assert SYMPY_FORM in message


def test_an_instance_declaring_no_tests_at_all_is_rejected() -> None:
    """An empty declaration would pass every id check vacuously — there are no ids to fail."""
    with pytest.raises(Ineligible) as raised:
        check_format([])

    assert raised.value.gate == GATE_FORMAT


# --------------------------------------------------------------------------------------
# The gate vocabulary itself
# --------------------------------------------------------------------------------------


def test_the_four_gate_names_are_the_four_the_prd_defines() -> None:
    """The ledger's `gate` field is only meaningful against a closed set of values.

    A rejection recorded under a gate name that exists nowhere else is a rejection a reader
    cannot count, and a typo'd one would silently create a fifth category.
    """
    assert GATES == (GATE_FORMAT, GATE_COLLECTABILITY, GATE_ENVIRONMENT, GATE_LIVENESS)


def test_a_rejection_cannot_be_recorded_under_an_unknown_gate() -> None:
    """Fail-closed, like every other constructor in this package."""
    with pytest.raises(ValueError, match="unknown gate"):
        Rejection(instance_id="a__b-1", gate="vibes", reason="it felt wrong")


# --------------------------------------------------------------------------------------
# The rejection ledger — nothing vanishes
# --------------------------------------------------------------------------------------


def test_the_ledger_count_plus_the_eligible_count_equals_the_input_count(
    tmp_path: Path,
) -> None:
    """The conservation property, and it is the whole reason the ledger is publishable.

    Without it, "24 of 300 were eligible" is a claim about a funnel nobody watched. With it, the
    two numbers are forced to add up to the denominator by the code that writes them.
    """
    path = tmp_path / "ineligible.json"
    rejections = [
        Rejection(instance_id="a__b-1", gate=GATE_FORMAT, reason="django form"),
        Rejection(instance_id="c__d-2", gate=GATE_ENVIRONMENT, reason="no era pins"),
    ]

    write_ineligible(path, rejections, eligible=["e__f-3"], input_count=3)

    document = read_ineligible(path)
    assert document.counts["input"] == 3
    assert document.counts["eligible"] == 1
    assert document.counts["ineligible"] == 2
    assert {rejection.instance_id for rejection in document.rejections} == {"a__b-1", "c__d-2"}


def test_a_ledger_that_does_not_account_for_every_input_is_refused(tmp_path: Path) -> None:
    """The arithmetic is enforced at write time, so a hole cannot be committed.

    Checked here rather than by a reviewer, because the failure it prevents is invisible in a
    diff: a run that dropped three instances between the draw and the gates writes a
    perfectly well-formed ledger describing a smaller world.
    """
    with pytest.raises(ValueError, match="does not account"):
        write_ineligible(
            tmp_path / "ineligible.json",
            [Rejection(instance_id="a__b-1", gate=GATE_FORMAT, reason="django form")],
            eligible=["e__f-3"],
            input_count=5,
        )


def test_an_instance_cannot_be_both_eligible_and_rejected(tmp_path: Path) -> None:
    """The arithmetic can be satisfied by an instance counted twice, so identity is checked too.

    This is the shape a conservation check misses if it only adds: three inputs, one eligible,
    two rejected — and one of the rejected is the eligible one, so an input has still vanished
    while the totals balance.
    """
    with pytest.raises(ValueError, match="both eligible and rejected"):
        write_ineligible(
            tmp_path / "ineligible.json",
            [
                Rejection(instance_id="a__b-1", gate=GATE_FORMAT, reason="django form"),
                Rejection(instance_id="e__f-3", gate=GATE_LIVENESS, reason="did not discriminate"),
            ],
            eligible=["e__f-3"],
            input_count=3,
        )


def test_the_ledger_is_sorted_and_newline_terminated_so_it_diffs(tmp_path: Path) -> None:
    """A committed record whose bytes move for no reason is a record nobody reviews."""
    path = tmp_path / "ineligible.json"
    write_ineligible(
        path,
        [
            Rejection(instance_id="z__z-9", gate=GATE_FORMAT, reason="second"),
            Rejection(instance_id="a__a-1", gate=GATE_FORMAT, reason="first"),
        ],
        eligible=[],
        input_count=2,
    )

    text = path.read_text()
    assert text.endswith("\n")
    assert text.index("a__a-1") < text.index("z__z-9")


def test_a_ledger_that_is_not_a_ledger_raises_naming_the_file(tmp_path: Path) -> None:
    path = tmp_path / "ineligible.json"
    path.write_text('{"schema": "something-else"}')

    with pytest.raises(ValueError, match=r"ineligible\.json"):
        read_ineligible(path)


def test_a_rejection_naming_hundreds_of_ids_states_the_count_rather_than_all_of_them() -> None:
    """The ledger is committed and reviewable, so one rejection may not be a wall of text.

    Measured: django instances declare hundreds of ids apiece, and an uncapped enumeration made
    `ineligible.json` 2.4 MB — a file nobody opens, and therefore evidence nobody checks. The
    **count** is never truncated, because how many failed is the fact a reader needs; the
    examples are, because the two-hundredth one of the same shape teaches nothing.
    """
    with pytest.raises(Ineligible) as raised:
        check_format([f"test_x_{index} (mod.Case)" for index in range(200)])

    message = str(raised.value)
    assert "200 of 200" in message
    assert "195 more" in message
    assert len(message) < 1500, "a single rejection is still long enough to bloat the ledger"
