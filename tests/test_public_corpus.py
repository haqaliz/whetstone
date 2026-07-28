"""The committed source-A corpus, checked against itself. This is the published number.

Everything else in this suite tests the machinery. This file tests the **artifact** — the three
committed files a reader outside this repository would look at — and it exists because a funnel
nobody re-checks is a funnel nobody can trust.

**The honest number, stated here so it is not buried.** Of SWE-bench-Lite's 300 instances,
**one** is eligible: `pallets__flask-4045`. 192 die at the format gate (django's unittest-runner
form, sympy's bare names), 106 at the environment gate because no era-pins have been determined
for them by hand, and 1 — `pallets__flask-5063` — at the collectability gate, because two of the
node ids SWE-bench itself declares for it are truncated mid-parameter and pytest cannot address
them. That is the corpus. It is small, and it is proven.

**Nothing vanishes, and this is where a reader checks that.** The ledger's own counts must add up
to the pool's size, and every eligible instance must have a manifest that loads through the
reward's own loader. Both are asserted against the files as committed, not against a fresh run:
the point of committing them is that they can be checked without one.

Offline: three file reads. No network, no model, no filter run.
"""

from __future__ import annotations

import json
from pathlib import Path

from whetstone.tasks.fetch import DATASET, read_pool
from whetstone.tasks.gates import GATES, read_ineligible
from whetstone.tasks.public import PASS_TO_PASS_SCOPE
from whetstone.verify.task import load_task

PUBLIC = Path(__file__).parent.parent / "tasks" / "public"
POOL = PUBLIC / "pool.json"
LEDGER = PUBLIC / "ineligible.json"
INSTANCES = PUBLIC / "instances"

#: The one instance that clears all four gates today. Named rather than discovered, so that a
#: filter run which silently minted something else fails here instead of being reported as a
#: larger corpus.
PROVEN = "pallets__flask-4045"


def test_the_committed_pool_is_the_whole_of_swe_bench_lite() -> None:
    """300 rows, no row filter, and the header says so — see `fetch`'s `_ELIGIBILITY_NOTE`."""
    document = json.loads(POOL.read_text())

    assert document["dataset"] == DATASET
    assert document["counts"]["records"] == len(document["instances"]) == 300
    assert document["filters"]["rows_filtered"] == 0
    assert document["counts"]["truncated"] == 0


def test_the_ledger_accounts_for_every_instance_in_the_pool() -> None:
    """Conservation, checked against the committed files rather than against a fresh run.

    This is the assertion a reader outside the repository would make, and making it here means
    they do not have to: a filter run that lost instances between the pool and the ledger fails
    the build rather than publishing a smaller world.
    """
    ledger = read_ineligible(LEDGER)

    assert ledger.counts["input"] == len(read_pool(POOL)) == 300
    assert ledger.counts["eligible"] + ledger.counts["ineligible"] == 300
    assert len(ledger.rejections) == ledger.counts["ineligible"]


def test_every_refusal_names_one_of_the_four_gates() -> None:
    """A rejection recorded under a fifth gate name is one nobody can count."""
    ledger = read_ineligible(LEDGER)

    assert {rejection.gate for rejection in ledger.rejections} <= set(GATES)


def test_the_funnel_is_the_one_reported() -> None:
    """The published composition, asserted so it cannot drift without saying so.

    If a re-run moves these numbers, that is a finding about the dataset or about a gate and it
    must be re-reported — not absorbed silently by a test that only checked they added up.
    """
    counts = read_ineligible(LEDGER).counts

    assert counts["format"] == 192
    assert counts["environment"] == 106
    assert counts["collectability"] == 1
    assert counts["liveness"] == 0
    assert counts["eligible"] == 1


def test_the_one_eligible_instance_has_a_manifest_the_reward_s_loader_accepts() -> None:
    """`load_task` is the check, because `load_task` is what the reward will use."""
    document = json.loads(LEDGER.read_text())
    assert document["eligible"] == [PROVEN]

    task = load_task(INSTANCES / f"{PROVEN}.json")

    assert task.task_id == PROVEN
    assert task.source == "public"
    assert task.repo_url == "https://github.com/pallets/flask.git"
    assert len(task.fail_to_pass) + len(task.pass_to_pass) == 52


def test_the_minted_task_pins_its_environment_exactly_and_says_where_its_code_lives() -> None:
    """The two fields that stop the verdict being decided by the calendar or by another tree."""
    task = load_task(INSTANCES / f"{PROVEN}.json")

    assert task.environment.import_roots == ("src",)
    assert "click==8.0.1" in task.environment.pins
    assert all("==" in pin for pin in task.environment.pins)


def test_the_minted_task_holds_the_conftest_above_its_own_tests() -> None:
    """The cheat-10 structural floor (PRD D4/M5) applies to source A too, and it fired.

    pytest loads a conftest by position, so a held test can depend on one without naming it — and
    a patch that rewrote an undeclared conftest would pass the declared tests against fixtures it
    wrote itself.
    """
    task = load_task(INSTANCES / f"{PROVEN}.json")

    assert "tests/conftest.py" in task.test_blobs


def test_the_minted_task_records_what_pass_to_pass_is_scoped_to() -> None:
    """A corpus whose `pass_to_pass` is narrower than a reader assumes overstates itself."""
    task = load_task(INSTANCES / f"{PROVEN}.json")

    assert task.provenance["pass_to_pass_scope"] == PASS_TO_PASS_SCOPE
    assert task.provenance["dataset"] == DATASET


def test_no_manifest_exists_for_an_instance_the_ledger_rejected() -> None:
    """The corpus directory holds exactly the proven set and nothing else.

    `load_tasks` refuses to skip anything it finds in a task directory, so a leftover manifest
    from an earlier run would be verified as though somebody had vouched for it.
    """
    rejected = {rejection.instance_id for rejection in read_ineligible(LEDGER).rejections}
    minted = {path.stem for path in INSTANCES.glob("*.json")}

    assert minted == {PROVEN}
    assert not minted & rejected


def test_the_instance_the_dig_nominated_is_recorded_as_ineligible_with_its_reason() -> None:
    """`pallets__flask-5063` cannot be the proven instance, and the ledger says why.

    It was nominated as already proven end to end, and it is not eligible: two of the node ids
    SWE-bench declares for it — `test_locate_app[cliapp.factory-create_app2("foo",` and one more
    — are truncated mid-parameter in the dataset itself, so pytest exits 4 rather than collecting
    them. Any earlier end-to-end run of it must have used a repaired id list. Asserted here so
    the finding is part of the build rather than a note in a report.
    """
    rejections = {r.instance_id: r for r in read_ineligible(LEDGER).rejections}

    assert "pallets__flask-5063" in rejections
    assert rejections["pallets__flask-5063"].gate == "collectability"
    assert "exited 4" in rejections["pallets__flask-5063"].reason
