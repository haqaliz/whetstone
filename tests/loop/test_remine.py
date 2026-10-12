"""The incremental re-mine wrapper: one `mine()` per donor, into the training-only root.

The night re-mines the user's own donors before it draws (`whetstone.loop.night`), and the unit
that owns that is this module, not the night. The properties asserted here are the ones the night
delegates:

* **one `mine()` call per `(label, donor)` pair**, each writing manifests into `out` (the
  training-only root the night loads) and the miner's own ledger/recipes into a **sibling**
  evidence root `out.parent/(out.name + "-evidence")` — never the committed corpus, and never
  `out` itself, which the night's strict loader would refuse;
* the **skip-set accumulates** across donors and onto `existing`, so a second donor cannot
  re-mint a commit the first did;
* **absent, unprovisionable, or nothing-minted donors are reported no-ops**, never fatal — the
  night must proceed on the corpus it already has;
* `RemineReport.minted` is the `(task_id, donor)` pairs **sorted by task id**, the shape the
  `record` aspect serializes.

`mine` is injected at the module attribute: a real mint is hours per candidate, and none of the
above is about provisioning. `skip`, `existing`, the loaded root and the evidence root are
observed on the call, not inferred.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from fixtures.repos.mined import build_mined_task

import whetstone.loop.remine as remine_module
from whetstone.loop.remine import DonorOutcome, RemineReport, corpus_shas, remine, trailing_sha
from whetstone.tasks.environment import NotProvisionable
from whetstone.tasks.liveness import Liveness
from whetstone.tasks.manifest import load_tasks
from whetstone.tasks.mine import Minted, MintFailed, MintReport, Rejected
from whetstone.verify.verdict import Status


def _minted(task_id: str) -> Minted:
    """One proven-live task, in the shape `mine()` returns. Nothing reads its body here."""
    return Minted(
        task_id=task_id,
        manifest=Path("/nowhere") / f"{task_id}.json",
        liveness=Liveness(
            task_id=task_id,
            without_patch=Status.FAIL,
            with_patch=Status.PASS,
            executed_without_patch=1,
            executed_matches_declared=True,
            skipped=0,
        ),
        python="/nowhere/python",
    )


def _report(*task_ids: str) -> MintReport:
    """A one-donor `MintReport` carrying `task_ids`, in the order given."""
    return MintReport(
        minted=tuple(_minted(task_id) for task_id in task_ids),
        rejected=(),
        ledger=Path("/nowhere/out/local-ledger.json"),
        recipe=Path("/nowhere/out/recipes/x.json"),
    )


def _record_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace the miner with a recorder that mints one task per donor, named after the label."""
    calls: list[dict[str, Any]] = []

    def fake(donor: Path, out: Path, **kwargs: Any) -> MintReport:
        calls.append({"donor": donor, "out": out, **kwargs})
        return _report(f"{kwargs['label']}-" + "a" * 12)

    monkeypatch.setattr(remine_module, "mine", fake)
    return calls


def test_remine_calls_mine_once_per_donor_into_the_training_only_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two donors, two calls; each writes manifests into `out` and evidence into a sibling root."""
    calls = _record_calls(monkeypatch)
    out = tmp_path / "remined"
    scratch = tmp_path / "scratch"
    donors = (("donor-a", tmp_path / "donor-a-src"), ("donor-b", tmp_path / "donor-b-src"))

    report = remine(
        donors,
        out=out,
        limit=3,
        scratch=scratch,
        timeout=12.0,
        existing={"deadbeef0000"},
    )

    assert len(calls) == 2, calls
    evidence = out.parent / f"{out.name}-evidence"
    for call in calls:
        assert call["out"] == out, "the miner wrote outside the training-only root"
        assert call["tasks_root"] == evidence, (
            "the miner's own ledger/recipes were pointed somewhere other than the sibling "
            "evidence root; inside `out` they would make the night's strict loader refuse it"
        )
        assert call["tasks_root"] != out, "the evidence must never land in the loaded root"
        assert call["limit"] == 3 and call["timeout"] == 12.0
        assert call["scratch"] == scratch / call["label"], (
            "the per-donor scratch was not kept under the passed scratch root"
        )
    assert {call["label"] for call in calls} == {"donor-a", "donor-b"}
    assert report.minted == (
        ("donor-a-" + "a" * 12, "donor-a"),
        ("donor-b-" + "a" * 12, "donor-b"),
    ), report.minted
    assert len(report.donors) == 2, report.donors


def test_evidence_lands_in_a_sibling_so_the_loaded_root_stays_manifest_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The miner's ledger/recipes go to `<out>-evidence`; `out` holds only manifests and loads.

    The regression this prevents was found end to end: `mine()` writes its evidence *into*
    `tasks_root`, and the night's strict loader refuses **any** non-manifest entry in a root it
    loads. With `tasks_root` pointed at the sibling, `out` stays pure and the loader accepts it.
    `out.parent` alone is not the answer — for a `tasks/local/<name>` root the parent is the
    directory that holds the committed `tasks/local-ledger.json` / `tasks/recipes/`.
    """
    out = tmp_path / "remined"
    build_mined_task(tmp_path / "fixture", task_id="mined-fixture", subject="Fix addition")
    manifest = tmp_path / "fixture" / "mined-fixture.json"
    seen: dict[str, Path] = {}

    def fake(donor: Path, out: Path, **kwargs: Any) -> MintReport:
        root = Path(out)
        root.mkdir(parents=True, exist_ok=True)
        evidence = Path(kwargs["tasks_root"])
        evidence.mkdir(parents=True, exist_ok=True)
        shutil.copy(manifest, root / manifest.name)
        (evidence / "local-ledger.json").write_text("{}")
        (evidence / "recipes").mkdir(exist_ok=True)
        seen["evidence"] = evidence
        return MintReport(minted=(), rejected=(), ledger=None, recipe=None)

    monkeypatch.setattr(remine_module, "mine", fake)
    remine(
        (("donor-x", tmp_path / "donor"),),
        out=out,
        limit=1,
        scratch=tmp_path / "s",
        timeout=5.0,
        existing=frozenset(),
    )

    assert seen["evidence"] == tmp_path / "remined-evidence", seen["evidence"]
    assert seen["evidence"] != out.parent, (
        "the evidence was placed in the parent, which for a `tasks/local/<name>` root is the "
        "directory holding the committed `tasks/local-ledger.json` / `tasks/recipes/`"
    )
    assert [task.task_id for task in load_tasks(out)] == ["mined-fixture"], (
        "the night's strict loader refused `out`, so a real re-mine would crash after minting"
    )
    assert not (out / "local-ledger.json").exists() and not (out / "recipes").exists(), (
        "the miner's evidence landed in the loaded root"
    )
    assert (seen["evidence"] / "local-ledger.json").is_file()


def test_the_skip_set_accumulates_across_donors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second donor's skip is the first's minted sha12s plus `existing`, always."""
    calls = _record_calls(monkeypatch)

    remine(
        (("donor-a", tmp_path / "a"), ("donor-b", tmp_path / "b")),
        out=tmp_path / "out",
        limit=2,
        scratch=tmp_path / "s",
        timeout=5.0,
        existing={"deadbeef0000"},
    )

    assert calls[0]["skip"] == frozenset({"deadbeef0000"}), calls[0]["skip"]
    assert calls[1]["skip"] == frozenset({"deadbeef0000", "a" * 12}), (
        f"the second donor did not inherit the first's minted sha: {calls[1]['skip']!r}"
    )


def test_an_absent_donor_is_a_reported_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A donor that cannot be read is recorded and skipped; the other donor's pairs survive."""
    calls: list[str] = []

    def fake(donor: Path, out: Path, **kwargs: Any) -> MintReport:
        calls.append(kwargs["label"])
        if kwargs["label"] == "donor-b":
            raise MintFailed("not a repository")
        return _report(f"{kwargs['label']}-" + "a" * 12)

    monkeypatch.setattr(remine_module, "mine", fake)
    report = remine(
        (("donor-a", tmp_path / "a"), ("donor-b", tmp_path / "missing")),
        out=tmp_path / "out",
        limit=1,
        scratch=tmp_path / "s",
        timeout=5.0,
        existing=frozenset(),
    )

    assert calls == ["donor-a", "donor-b"], "the absent donor aborted the run before being reported"
    assert report.minted == (("donor-a-" + "a" * 12, "donor-a"),), report.minted
    absent = report.donors[1]
    assert absent.label == "donor-b" and absent.minted == (), absent
    assert "not a repository" in absent.absent, absent.absent


def test_a_nonexistent_donor_path_is_a_reported_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A typo'd donor path is a recorded no-op, not a crashed night (M4).

    `mine()` reaches `subprocess(cwd=<path>)`, which raises `FileNotFoundError` — an `OSError`,
    not a `MintFailed` — when the path does not exist. Uncought, that escapes `remine()` and
    kills the night on a mistyped flag. It is a donor that could not be read, exactly like a
    directory that is not a repository, so it is recorded as absent and the loop continues.
    """
    def fake(donor: Path, out: Path, **kwargs: Any) -> MintReport:
        raise FileNotFoundError(2, "No such file or directory", str(donor))

    monkeypatch.setattr(remine_module, "mine", fake)
    report = remine(
        (("donor-x", tmp_path / "typo"),),
        out=tmp_path / "out",
        limit=1,
        scratch=tmp_path / "s",
        timeout=5.0,
        existing=frozenset(),
    )

    assert report.minted == (), report.minted
    outcome = report.donors[0]
    assert outcome.minted == () and outcome.rejected == (), outcome
    assert outcome.absent, (
        f"WHY THIS IS A FAILURE: the nonexistent donor was not reported as absent: {outcome!r}"
    )


def test_an_unprovisionable_donor_is_a_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC7: a wholesale `NotProvisionable` is a reported no-op, never a crashed night."""
    def fake(donor: Path, out: Path, **kwargs: Any) -> MintReport:
        raise NotProvisionable("cold cache")

    monkeypatch.setattr(remine_module, "mine", fake)
    report = remine(
        (("donor-a", tmp_path / "a"),),
        out=tmp_path / "out",
        limit=1,
        scratch=tmp_path / "s",
        timeout=5.0,
        existing=frozenset(),
    )

    assert report.minted == ()
    assert report.donors[0].absent and "cold cache" in report.donors[0].absent


def test_a_donor_that_mints_nothing_is_a_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty `MintReport` is distinct from an absent donor and still a recorded outcome."""
    def fake(donor: Path, out: Path, **kwargs: Any) -> MintReport:
        return MintReport(
            minted=(),
            rejected=(Rejected(sha="a" * 40, reason="NotProvisionable: cold"),),
            ledger=None,
            recipe=None,
        )

    monkeypatch.setattr(remine_module, "mine", fake)
    report = remine(
        (("donor-a", tmp_path / "a"),),
        out=tmp_path / "out",
        limit=1,
        scratch=tmp_path / "s",
        timeout=5.0,
        existing=frozenset(),
    )

    assert report.minted == ()
    outcome = report.donors[0]
    assert outcome.minted == () and outcome.absent == "", outcome
    assert outcome.rejected == (("a" * 40, "NotProvisionable: cold"),), outcome.rejected


def test_minted_pairs_are_sorted_by_task_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pairs are sorted at the report boundary, whatever order the miner minted them in."""
    def fake(donor: Path, out: Path, **kwargs: Any) -> MintReport:
        return _report("donor-x-" + "f" * 12, "donor-x-" + "0" * 12)

    monkeypatch.setattr(remine_module, "mine", fake)
    report = remine(
        (("donor-x", tmp_path / "a"),),
        out=tmp_path / "out",
        limit=2,
        scratch=tmp_path / "s",
        timeout=5.0,
        existing=frozenset(),
    )

    assert report.minted == (
        ("donor-x-" + "0" * 12, "donor-x"),
        ("donor-x-" + "f" * 12, "donor-x"),
    ), report.minted


def test_no_donors_returns_an_empty_report(tmp_path: Path) -> None:
    """`remine(())` is the no-op the night guards against calling at all: empty, not an error."""
    assert remine(
        (),
        out=tmp_path / "out",
        limit=1,
        scratch=tmp_path / "s",
        timeout=5.0,
        existing=frozenset(),
    ) == RemineReport(minted=(), donors=())


def test_donor_outcome_defaults_an_absent_reason_to_empty() -> None:
    """The dataclass's `absent` field defaults to `""`, the night's "the donor was read"."""
    outcome = DonorOutcome(
        label="donor-x", donor=Path("/d"), minted=("a",), rejected=(("b", "c"),)
    )
    assert outcome.absent == "", "the absent reason must default to empty, not None"


def test_trailing_sha_falls_back_to_the_whole_id_for_synthetic_ids() -> None:
    """The harness's `t-11`/`alpha` ids do not end in twelve hex; the helper must not raise."""
    assert trailing_sha("donor-x-0123456789ab") == "0123456789ab"
    assert trailing_sha("t-11") == "t-11"
    assert trailing_sha("alpha") == "alpha"


def test_corpus_shas_reads_every_task_id_tolerantly() -> None:
    """`corpus_shas` is the `existing` set the night builds; it must accept the harness ids."""
    class _Task:
        def __init__(self, task_id: str) -> None:
            self.task_id = task_id

    tasks: Any = (_Task("donor-x-0123456789ab"), _Task("alpha"), _Task("t-11"))
    assert corpus_shas(tasks) == frozenset({"0123456789ab", "alpha", "t-11"})

