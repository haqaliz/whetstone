"""The re-mint apply step as tested machinery: snapshot, verify, swap, rewrite, regenerate.

The #62 pairing requires the held-out document to be re-derived exactly once over the
re-minted corpus — ids `donor-a-*` / `donor-b-*`, a provably identical commit set (same
sha12s, same heads, differing only in `task_id`, `provenance.donor`, `repo_url`). The staged
re-mint is the reference; applying it is an operator step that must be scripted, guarded,
snapshot-protected and reversible (`docs/planning/heldout-scorable/rederivation/spec.md` AC1-AC6,
AC10). This file is the step as code, over synthetic roots: every test below builds its own
fake staging, fake old-id corpus and fake ledger, so the machinery is proven on the shapes it
will meet on the machine before it is pointed at the real one (the phase-4 runbook step).

The ledger regeneration must reuse `tasks.ledger`'s own `read_ledger`/`write_ledger` by
identity — a hand-rolled JSON emit would be a second ledger contract — so the identity pin
below is part of the contract, not an implementation detail.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from fixtures.repos import _git
from fixtures.repos.mined import (
    MINED_BULK_LINE,
    MINED_CALC_BUGGY,
    MINED_CALC_FIXED,
    MINED_TESTS_AFTER,
    MINED_TESTS_BEFORE,
)

from whetstone.bakeoff import stratum
from whetstone.loop import heldout
from whetstone.tasks import ledger, remint_apply

#: The two donor labels the staged re-mint carries, and the old-id labels it replaces.
DONOR_A = "donor-a"
DONOR_B = "donor-b"
OLD_A = "contig"
OLD_B = "belay"


def _manifest(
    task_id: str,
    *,
    sha12: str,
    donor: str,
    repo_url: str,
) -> dict[str, object]:
    """One valid synthetic manifest, shaped like the machine corpus's (full commit 40-hex)."""
    commit = sha12 + "c" * 28
    parent = sha12 + "p" * 28
    return {
        "task_id": task_id,
        "source": "private",
        "repo_url": repo_url,
        "base_commit": commit,
        "environment": {"python": "3.12", "pins": [], "import_roots": ["."]},
        "problem_statement": f"Fix {task_id}",
        "fail_to_pass": ["tests/test_x.py::test_fail"],
        "pass_to_pass": ["tests/test_x.py::test_pass"],
        "test_blobs": {
            "tests/test_x.py": base64.b64encode(b"def test_fail():\n    assert False\n").decode()
        },
        "provenance": {"donor": donor, "commit": commit, "parent": parent},
    }


def _write(root: Path, name: str, raw: dict[str, object]) -> Path:
    """One manifest on disk under `root`, deterministically serialised."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n")
    return path


def _corpus(
    root: Path, label: str, donor: str, repo_url: str, sha12s: list[str]
) -> dict[str, Path]:
    """A synthetic corpus root: `len(sha12s)` manifests named `<label>-<sha12>.json`."""
    written: dict[str, Path] = {}
    for sha12 in sha12s:
        task_id = f"{label}-{sha12}"
        written[task_id] = _write(
            root,
            f"{task_id}.json",
            _manifest(task_id, sha12=sha12, donor=donor, repo_url=repo_url),
        )
    return written


def _entry(task_id: str, manifest_sha256: str) -> dict[str, object]:
    """One synthetic ledger entry, the committed shape (`tasks/ledger.py:74-97`)."""
    return {
        "task_id": task_id,
        "manifest_sha256": manifest_sha256,
        "without_patch": "FAIL",
        "with_patch": "PASS",
        "executed_matches_declared": True,
        "skipped": 0,
        "python": "3.12.13",
        "tools": {
            "git": "git version 2.50.1",
            "uv": "uv 0.12.17",
            "whetstone": "0.14.1",
        },
        "proven_at": "2026-09-26T01:26:21Z",
    }


def _ledger(root: Path, entries: list[dict[str, object]]) -> Path:
    """A synthetic staged ledger on disk, and its path (the `_sandbox/remint` shape)."""
    path = root / "local-ledger.json"
    path.write_text(
        json.dumps({"schema": ledger.LEDGER_SCHEMA, "tasks": entries}, indent=2) + "\n"
    )
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _old_layout(tmp_path: Path) -> dict[str, Path]:
    """The pre-swap machine-corpus shape: two old-id roots under `tasks/local/`."""
    corpus = tmp_path / "tasks" / "local"
    donor_a = corpus / DONOR_A
    donor_b = corpus / DONOR_B
    contig = _corpus(donor_a, OLD_A, OLD_A, "/real/donor/contig", ["a1" * 6, "a2" * 6])
    belay = _corpus(donor_b, OLD_B, OLD_B, "/real/donor/belay", ["b1" * 6])
    return {"donor-a": donor_a, "donor-b": donor_b, "manifests": {**contig, **belay}}


def _staged_layout(tmp_path: Path) -> dict[str, Path]:
    """The staged re-mint shape: `staged/local/{donor-a,donor-b}` + `staged/local-ledger.json`."""
    staged = tmp_path / "staged"
    local = staged / "local"
    _corpus(local / DONOR_A, DONOR_A, DONOR_A, "/sandbox/donors/donor-a", ["a1" * 6, "a2" * 6])
    _corpus(local / DONOR_B, DONOR_B, DONOR_B, "/sandbox/donors/donor-b", ["b1" * 6])
    entries = [
        _entry("donor-a-a1a1a1a1a1a1", "1" * 64),
        _entry("donor-a-a2a2a2a2a2a2", "2" * 64),
        _entry("donor-b-b1b1b1b1b1b1", "3" * 64),
    ]
    _ledger(staged, entries)
    return {
        "staged": staged,
        "local": local,
        "donor-a": local / DONOR_A,
        "donor-b": local / DONOR_B,
    }


def _old_ledger(tmp_path: Path) -> Path:
    """The pre-swap committed ledger: the old ids, hashes of the old manifests."""
    return _ledger(
        tmp_path,
        [
            _entry("contig-a1a1a1a1a1a1", "a" * 64),
            _entry("contig-a2a2a2a2a2a2", "b" * 64),
            _entry("belay-b1b1b1b1b1b1", "c" * 64),
        ],
    )


# --------------------------------------------------------------------------------------------
# AC2 — the snapshot, written before anything moves, and asserted to carry the old state.
# --------------------------------------------------------------------------------------------


def test_snapshot_corpus_records_the_pre_swap_state(tmp_path: Path) -> None:
    """AC2: the snapshot carries the old-id manifests, their sha12s, and the old ledger."""
    layout = _old_layout(tmp_path)
    ledger_path = _old_ledger(tmp_path)
    out = tmp_path / "snapshot"

    location = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], ledger_path, out
    )

    assert location == out
    for task_id, path in layout["manifests"].items():
        root = "donor-a" if task_id.startswith("contig") else "donor-b"
        copied = out / "manifests" / root / path.name
        assert copied.read_bytes() == path.read_bytes(), (
            f"the snapshot did not copy {path.name} byte-identically"
        )
    assert (out / "local-ledger.json").read_bytes() == ledger_path.read_bytes(), (
        "the snapshot did not copy the pre-swap ledger byte-identically"
    )

    raw = json.loads((out / "snapshot.json").read_text())
    assert raw["schema"] == remint_apply.SNAPSHOT_SCHEMA
    ids = {task["id"] for task in raw["tasks"]}
    assert ids == {"contig-a1a1a1a1a1a1", "contig-a2a2a2a2a2a2", "belay-b1b1b1b1b1b1"}, ids
    sha12s = {task["sha12"] for task in raw["tasks"]}
    assert sha12s == {"a1a1a1a1a1a1", "a2a2a2a2a2a2", "b1b1b1b1b1b1"}, sha12s
    for task in raw["tasks"]:
        assert task["sha12"] == task["commit"][:12]
    assert raw["ledger"]["sha256"] == _sha256(ledger_path), (
        "the snapshot's ledger digest does not match the ledger it copied"
    )
    assert raw["ledger"]["tasks"] == 3


def test_snapshot_refuses_a_corpus_that_does_not_load(tmp_path: Path) -> None:
    """The snapshot is fail-closed: a corpus the loader would refuse is refused by name."""
    layout = _old_layout(tmp_path)
    (layout["donor-a"] / "stray.txt").write_text("not a manifest")
    ledger_path = _old_ledger(tmp_path)

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.snapshot_corpus(
            [layout["donor-a"], layout["donor-b"]], ledger_path, tmp_path / "snapshot"
        )
    assert "stray.txt" in str(caught.value), caught.value


def test_snapshot_refuses_a_snapshot_destination_that_already_holds_state(tmp_path: Path) -> None:
    """A second snapshot would overwrite the first: refused, never silently replaced."""
    layout = _old_layout(tmp_path)
    ledger_path = _old_ledger(tmp_path)
    out = tmp_path / "snapshot"
    out.mkdir()
    (out / "previous.json").write_text("{}")

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.snapshot_corpus([layout["donor-a"], layout["donor-b"]], ledger_path, out)
    assert "previous.json" in str(caught.value), caught.value


# --------------------------------------------------------------------------------------------
# AC3 — verification before swap: 66 label-form ids, identical sha12s, staged ledger count.
# --------------------------------------------------------------------------------------------


def test_verify_staged_accepts_the_faithful_re_mint(tmp_path: Path) -> None:
    """AC3 happy path: label ids, identical commit set, staged ledger count — all asserted."""
    layout = _old_layout(tmp_path)
    snapshot = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], _old_ledger(tmp_path), tmp_path / "snapshot"
    )
    staged = _staged_layout(tmp_path)

    record = remint_apply.verify_staged(snapshot, staged["staged"])

    assert record.total == 3
    assert record.by_label == {"donor-a": 2, "donor-b": 1}


def test_verify_refuses_a_staged_re_mint_of_the_wrong_count(tmp_path: Path) -> None:
    layout = _old_layout(tmp_path)
    snapshot = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], _old_ledger(tmp_path), tmp_path / "snapshot"
    )
    staged = _staged_layout(tmp_path)
    (staged["donor-b"] / "donor-b-b1b1b1b1b1b1.json").unlink()

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.verify_staged(snapshot, staged["staged"])
    assert "2" in str(caught.value) and "3" in str(caught.value), caught.value


def test_verify_refuses_a_staged_manifest_that_is_not_label_form(tmp_path: Path) -> None:
    """An old-id file surviving in the staged re-mint is a foreign body, refused by name."""
    layout = _old_layout(tmp_path)
    snapshot = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], _old_ledger(tmp_path), tmp_path / "snapshot"
    )
    staged = _staged_layout(tmp_path)
    (staged["donor-a"] / "donor-a-a1a1a1a1a1a1.json").unlink()
    _write(
        staged["donor-a"],
        "contig-a1a1a1a1a1a1.json",
        _manifest(
            "contig-a1a1a1a1a1a1", sha12="a1a1a1a1a1a1", donor=OLD_A, repo_url="/real/donor/contig"
        ),
    )

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.verify_staged(snapshot, staged["staged"])
    assert "contig-a1a1a1a1a1a1" in str(caught.value), caught.value


def test_verify_refuses_a_staged_commit_set_that_is_not_identical(tmp_path: Path) -> None:
    """A single changed commit breaks the provably-identical claim, refused before any move."""
    layout = _old_layout(tmp_path)
    snapshot = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], _old_ledger(tmp_path), tmp_path / "snapshot"
    )
    staged = _staged_layout(tmp_path)
    changed = staged["donor-b"] / "donor-b-b1b1b1b1b1b1.json"
    raw = json.loads(changed.read_text())
    raw["base_commit"] = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    changed.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n")

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.verify_staged(snapshot, staged["staged"])
    assert "deadbeef" in str(caught.value), caught.value


def test_verify_refuses_a_staged_ledger_of_the_wrong_count(tmp_path: Path) -> None:
    layout = _old_layout(tmp_path)
    snapshot = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], _old_ledger(tmp_path), tmp_path / "snapshot"
    )
    staged = _staged_layout(tmp_path)
    _ledger(staged["staged"], [_entry("donor-a-a1a1a1a1a1a1", "1" * 64)])

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.verify_staged(snapshot, staged["staged"])
    assert "1" in str(caught.value) and "3" in str(caught.value), caught.value


def test_verify_refuses_a_staged_ledger_that_names_no_staged_manifest(tmp_path: Path) -> None:
    """The staged ledger's ids must resolve against the staged manifests, or it is refused."""
    layout = _old_layout(tmp_path)
    snapshot = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], _old_ledger(tmp_path), tmp_path / "snapshot"
    )
    staged = _staged_layout(tmp_path)
    _ledger(
        staged["staged"],
        [
            _entry("donor-a-a1a1a1a1a1a1", "1" * 64),
            _entry("donor-a-a2a2a2a2a2a2", "2" * 64),
            _entry("donor-b-b9b9b9b9b9b9", "3" * 64),
        ],
    )

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.verify_staged(snapshot, staged["staged"])
    assert "donor-b-b9b9b9b9b9b9" in str(caught.value), caught.value


# --------------------------------------------------------------------------------------------
# AC4 + AC10 — the swap: exactly the re-minted set per root, old ids gone, double-apply refused.
# --------------------------------------------------------------------------------------------


def test_swap_leaves_each_root_holding_exactly_the_re_minted_set(tmp_path: Path) -> None:
    """AC4: 66 total in the real case; here the synthetic 3 — old ids gone, nothing foreign."""
    layout = _old_layout(tmp_path)
    staged = _staged_layout(tmp_path)

    record = remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])

    assert {path.name for path in layout["donor-a"].iterdir()} == {
        "donor-a-a1a1a1a1a1a1.json",
        "donor-a-a2a2a2a2a2a2.json",
    }, "donor-a did not end with exactly the staged set"
    assert {path.name for path in layout["donor-b"].iterdir()} == {
        "donor-b-b1b1b1b1b1b1.json"
    }, "donor-b did not end with exactly the staged set"
    removed = {path.name for path in record.removed}
    assert removed == {
        "contig-a1a1a1a1a1a1.json",
        "contig-a2a2a2a2a2a2.json",
        "belay-b1b1b1b1b1b1.json",
    }, removed
    assert len(record.added) == 3


def test_swap_refuses_to_double_apply_and_moves_nothing(tmp_path: Path) -> None:
    """AC10: a target that already holds donor-a-* files is a named refusal, before any move."""
    layout = _old_layout(tmp_path)
    staged = _staged_layout(tmp_path)
    remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])
    before = {
        path.name: path.read_bytes() for path in layout["donor-a"].iterdir()
    }

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])
    assert "donor-a" in str(caught.value) and "double-apply" in str(caught.value), caught.value
    after = {path.name: path.read_bytes() for path in layout["donor-a"].iterdir()}
    assert after == before, "the refused second swap moved files"


def test_the_snapshot_restores_the_pre_swap_corpus(tmp_path: Path) -> None:
    """AC10: the snapshot is the reversibility guarantee — restore reproduces the old corpus."""
    layout = _old_layout(tmp_path)
    ledger_path = _old_ledger(tmp_path)
    snapshot = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], ledger_path, tmp_path / "snapshot"
    )
    staged = _staged_layout(tmp_path)
    remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])

    for root in (layout["donor-a"], layout["donor-b"]):
        for path in root.iterdir():
            path.unlink()

    for root in (layout["donor-a"], layout["donor-b"]):
        source = snapshot / "manifests" / root.name
        for path in source.iterdir():
            path.replace(root / path.name)

    restored = {
        p.name: p for root in (layout["donor-a"], layout["donor-b"]) for p in root.iterdir()
    }
    for task_id, path in layout["manifests"].items():
        assert restored[path.name].read_bytes() == path.read_bytes(), (
            f"the snapshot did not restore {task_id} byte-identically"
        )


# --------------------------------------------------------------------------------------------
# AC5 — the repo_url rewrite: exactly one field, to the declared real donor paths.
# --------------------------------------------------------------------------------------------


def test_rewrite_repo_url_changes_only_the_repo_url_field(tmp_path: Path) -> None:
    """AC5: every applied manifest differs from its staged twin in repo_url and nothing else."""
    staged = _staged_layout(tmp_path)
    layout = _old_layout(tmp_path)
    remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])
    donors = {"donor-a": tmp_path / "real" / "contig", "donor-b": tmp_path / "real" / "belay"}
    donors["donor-a"].mkdir(parents=True)
    donors["donor-b"].mkdir(parents=True)

    count = remint_apply.rewrite_repo_url([layout["donor-a"], layout["donor-b"]], donors)

    assert count == 3
    for root in (layout["donor-a"], layout["donor-b"]):
        for path in sorted(root.iterdir()):
            applied = json.loads(path.read_text())
            staged_raw = json.loads((staged["local"] / root.name / path.name).read_text())
            for key, value in staged_raw.items():
                if key == "repo_url":
                    continue
                assert applied[key] == value, (
                    f"the rewrite changed {key} in {path.name}, not only repo_url"
                )
            assert applied["repo_url"] == str(donors[applied["provenance"]["donor"]]), (
                f"{path.name} was not pointed at its declared real donor"
            )


def test_rewrite_refuses_an_undeclared_donor_label(tmp_path: Path) -> None:
    layout = _old_layout(tmp_path)
    staged = _staged_layout(tmp_path)
    remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])
    donors = {"donor-a": tmp_path / "real" / "contig"}
    donors["donor-a"].mkdir(parents=True)

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.rewrite_repo_url([layout["donor-a"], layout["donor-b"]], donors)
    assert "donor-b" in str(caught.value), caught.value


def test_rewrite_refuses_a_declared_donor_path_that_does_not_exist(tmp_path: Path) -> None:
    """A rewrite target that is not on the machine is a named refusal, never a written pointer."""
    layout = _old_layout(tmp_path)
    staged = _staged_layout(tmp_path)
    remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])
    donors = {
        "donor-a": tmp_path / "real" / "contig",
        "donor-b": tmp_path / "real" / "belay",
    }

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.rewrite_repo_url([layout["donor-a"], layout["donor-b"]], donors)
    assert "does not exist" in str(caught.value), caught.value


def test_real_donors_recovers_the_pre_swap_donor_paths_per_label(tmp_path: Path) -> None:
    """The real donor paths are the pre-swap corpus's own, recovered from the snapshot.

    The runbook never types an operator's absolute path; the rewrite step recovers the real
    donor paths from the snapshot (the pre-swap manifests' `repo_url` values, paired per
    sha12) instead. Each staged label must resolve to exactly one path.
    """
    layout = _old_layout(tmp_path)
    snapshot = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], _old_ledger(tmp_path), tmp_path / "snapshot"
    )
    staged = _staged_layout(tmp_path)
    remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])

    donors = remint_apply.real_donors(
        snapshot, [layout["donor-a"], layout["donor-b"]]
    )

    assert donors == {
        "donor-a": Path("/real/donor/contig"),
        "donor-b": Path("/real/donor/belay"),
    }, donors


def test_real_donors_refuses_a_sha12_the_snapshot_does_not_carry(tmp_path: Path) -> None:
    """A commit the pre-swap corpus never held has no recoverable donor path: refused."""
    layout = _old_layout(tmp_path)
    snapshot = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], _old_ledger(tmp_path), tmp_path / "snapshot"
    )
    staged = _staged_layout(tmp_path)
    remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])
    stranger = layout["donor-b"] / "donor-b-b1b1b1b1b1b1.json"
    raw = json.loads(stranger.read_text())
    raw["base_commit"] = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    stranger.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n")

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.real_donors(snapshot, [layout["donor-a"], layout["donor-b"]])
    assert "deadbeef" in str(caught.value), caught.value


def test_real_donors_refuses_a_label_that_resolves_to_mixed_donor_paths(tmp_path: Path) -> None:
    """One label must name one donor; a mixed label would send the bakeoff to two repos."""
    layout = _old_layout(tmp_path)
    snapshot = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], _old_ledger(tmp_path), tmp_path / "snapshot"
    )
    staged = _staged_layout(tmp_path)
    remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])
    doctored = snapshot / "manifests" / "donor-a" / "contig-a2a2a2a2a2a2.json"
    raw = json.loads(doctored.read_text())
    raw["repo_url"] = "/real/donor/elsewhere"
    doctored.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n")

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.real_donors(snapshot, [layout["donor-a"], layout["donor-b"]])
    assert "donor-a" in str(caught.value) and "more than one" in str(caught.value), caught.value


# --------------------------------------------------------------------------------------------
# AC6 — the regenerated ledger: staged evidence, re-hashed manifests, tasks.ledger by identity.
# --------------------------------------------------------------------------------------------


def test_regenerate_ledger_keeps_the_staged_evidence_and_re_hashes_the_applied_manifests(
    tmp_path: Path,
) -> None:
    """AC6: entries differ from the staged ledger only in manifest_sha256; the loader accepts."""
    layout = _old_layout(tmp_path)
    staged = _staged_layout(tmp_path)
    remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])
    donors = {"donor-a": tmp_path / "real" / "contig", "donor-b": tmp_path / "real" / "belay"}
    donors["donor-a"].mkdir(parents=True)
    donors["donor-b"].mkdir(parents=True)
    remint_apply.rewrite_repo_url([layout["donor-a"], layout["donor-b"]], donors)
    out = tmp_path / "tasks" / "local-ledger.json"

    remint_apply.regenerate_ledger([layout["donor-a"], layout["donor-b"]], staged["staged"], out)

    staged_entries = {
        e.task_id: e for e in ledger.read_ledger(staged["staged"] / "local-ledger.json")
    }
    regenerated = ledger.read_ledger(out)
    assert len(regenerated) == 3
    applied: dict[str, Path] = {}
    for root in (layout["donor-a"], layout["donor-b"]):
        for path in sorted(root.iterdir()):
            applied[json.loads(path.read_text())["task_id"]] = path
    for entry in regenerated:
        staged_entry = staged_entries[entry.task_id]
        assert entry.manifest_sha256 == _sha256(applied[entry.task_id]), (
            f"{entry.task_id}: the regenerated hash is not the applied manifest's"
        )
        assert entry.manifest_sha256 != staged_entry.manifest_sha256, (
            f"{entry.task_id}: the rewritten manifest hashes identically to the staged one"
        )
        for field in (
            "without_patch",
            "with_patch",
            "executed_matches_declared",
            "skipped",
            "python",
            "tools",
            "proven_at",
        ):
            assert getattr(entry, field) == getattr(staged_entry, field), (
                f"{entry.task_id}: the regenerated ledger changed {field}, which must be the "
                "staged evidence unchanged"
            )


def test_regenerate_uses_the_ledger_io_by_identity() -> None:
    """A hand-rolled JSON emit would be a second ledger contract — the IO is tasks.ledger's own."""
    assert remint_apply.read_ledger is ledger.read_ledger
    assert remint_apply.write_ledger is ledger.write_ledger


def test_regenerate_refuses_a_staged_ledger_entry_with_no_applied_manifest(tmp_path: Path) -> None:
    layout = _old_layout(tmp_path)
    staged = _staged_layout(tmp_path)
    remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])
    _ledger(
        staged["staged"],
        [
            _entry("donor-a-a1a1a1a1a1a1", "1" * 64),
            _entry("donor-a-a2a2a2a2a2a2", "2" * 64),
            _entry("donor-a-a9a9a9a9a9a9", "9" * 64),
        ],
    )

    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.regenerate_ledger(
            [layout["donor-a"], layout["donor-b"]], staged["staged"], tmp_path / "ledger.json"
        )
    assert "donor-a-a9a9a9a9a9a9" in str(caught.value), caught.value


# --------------------------------------------------------------------------------------------
# The chain end to end — the phase-4 runbook's shape, over synthetic roots.
# --------------------------------------------------------------------------------------------


def test_the_apply_chain_runs_end_to_end_over_synthetic_roots(tmp_path: Path) -> None:
    """AC1-AC6 together: snapshot → verify → swap → rewrite → regenerate, in that order."""
    layout = _old_layout(tmp_path)
    ledger_path = _old_ledger(tmp_path)
    staged = _staged_layout(tmp_path)
    snapshot = remint_apply.snapshot_corpus(
        [layout["donor-a"], layout["donor-b"]], ledger_path, tmp_path / "snapshot"
    )
    remint_apply.verify_staged(snapshot, staged["staged"])
    remint_apply.swap_manifests([layout["donor-a"], layout["donor-b"]], staged["staged"])
    donors = {"donor-a": tmp_path / "real" / "contig", "donor-b": tmp_path / "real" / "belay"}
    donors["donor-a"].mkdir(parents=True)
    donors["donor-b"].mkdir(parents=True)
    remint_apply.rewrite_repo_url([layout["donor-a"], layout["donor-b"]], donors)
    out = tmp_path / "tasks" / "local-ledger.json"
    remint_apply.regenerate_ledger([layout["donor-a"], layout["donor-b"]], staged["staged"], out)

    total = 0
    for root in (layout["donor-a"], layout["donor-b"]):
        names = sorted(path.name for path in root.iterdir())
        assert all(name.startswith(("donor-a-", "donor-b-")) for name in names), names
        total += len(names)
    assert total == 3
    entries = ledger.read_ledger(out)
    assert len(entries) == 3
    applied: dict[str, Path] = {}
    for root in (layout["donor-a"], layout["donor-b"]):
        for path in sorted(root.iterdir()):
            applied[json.loads(path.read_text())["task_id"]] = path
    for entry in entries:
        assert entry.manifest_sha256 == _sha256(applied[entry.task_id]), (
            f"{entry.task_id}: the chain's final hash is not the applied manifest's"
        )

# --------------------------------------------------------------------------------------------
# Phase 2 — the re-derivations through their established doors: the stratum door over a
# synthetic re-minted corpus (per-sha12 difficulty equality), the heldout door over the
# synthetic corpus (the class excluded, never drawn).
# --------------------------------------------------------------------------------------------


def _commit(donor: Path, files: dict[str, str], subject: str) -> str:
    """Write `files` into `donor`, commit them, and return the resulting SHA."""
    for relative, contents in files.items():
        target = donor / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents)
    _git(["add", "--all"], cwd=donor)
    _git(["commit", "--quiet", "--message", subject], cwd=donor)
    return _git(["rev-parse", "HEAD"], cwd=donor).strip()


def _mined_corpus(
    tmp_path: Path,
    *,
    staged: bool,
    count: int,
    bulk: int = 0,
) -> tuple[Path, dict[str, str], str | None]:
    """A synthetic corpus of `count` real-git mined tasks; returns (root, id by sha12, bulk id).

    Each task is built in its own scratch directory (its donor lives beside the manifest,
    and a corpus root may hold only manifests), then the manifest alone is copied into the
    returned corpus root. Every third task's fixing commit also touches `notes.md`, so its
    shape sits outside the stratum band (two non-test files) while still being measured —
    a corpus where every task is in band would be a degenerate whole-corpus stratum, and a
    derivation that never faced the refusal would prove nothing about the door. `bulk`
    names the number of characters the first task's `base_commit` source file carries, so
    its oracle exceeds any budget smaller than it (its id is the third return). The ids are
    sha12-form: `<label>-<base_commit's first 12 hex>`.
    """
    root = tmp_path / ("staged-corpus" if staged else "old-corpus")
    root.mkdir()
    by_sha12: dict[str, str] = {}
    bulk_id: str | None = None
    for i in range(count):
        scratch = tmp_path / ("staged-scratch" if staged else "old-scratch") / str(i)
        donor = scratch / "donor"
        donor.mkdir(parents=True)
        _git(["init", "--quiet", "--initial-branch=main"], cwd=donor)
        # The fixture pins commit dates, so two identical seed trees would be one commit;
        # the per-task marker keeps every seed tree distinct and every sha12 unique.
        marker = f"# task {i}\n"
        before: dict[str, str] = {
            "calc.py": MINED_CALC_BUGGY + marker,
            "tests/test_addition.py": MINED_TESTS_BEFORE,
        }
        after: dict[str, str] = {
            "calc.py": MINED_CALC_FIXED + marker,
            "tests/test_addition.py": MINED_TESTS_AFTER,
        }
        if i % 3 == 2:
            before["notes.md"] = "# notes\n"
            after["notes.md"] = "# notes\n\n- fixed\n"
        if bulk and i == 0:
            padded = MINED_BULK_LINE * (bulk // len(MINED_BULK_LINE) + 1)
            before["bulk.py"] = padded
            after["bulk.py"] = padded + "FILLER += 'y'\n"
        parent = _commit(donor, before, "Seed the calculator")
        commit = _commit(donor, after, f"Fix task {i}")
        sha12 = parent[:12]
        label = (
            ("donor-a" if i % 2 == 0 else "donor-b")
            if staged
            else ("contig" if i % 2 == 0 else "belay")
        )
        task_id = f"{label}-{sha12}"
        manifest = {
            "task_id": task_id,
            "source": "private",
            "repo_url": str(donor),
            "base_commit": parent,
            "environment": {"python": "3.12", "pins": [], "import_roots": ["."]},
            "problem_statement": f"Fix task {i}",
            "fail_to_pass": ["tests/test_addition.py::test_add_is_addition"],
            "pass_to_pass": ["tests/test_addition.py::test_adding_zero_is_the_identity"],
            "test_blobs": {
                "tests/test_addition.py": base64.b64encode(MINED_TESTS_AFTER.encode()).decode()
            },
            "provenance": {"donor": label, "commit": commit, "parent": parent},
        }
        _write(root, f"{task_id}.json", manifest)
        by_sha12[sha12] = task_id
        if bulk and i == 0:
            bulk_id = task_id
    return root, by_sha12, bulk_id


def test_the_stratum_difficulty_is_equal_per_sha12_between_old_and_re_minted(
    tmp_path: Path,
) -> None:
    """AC7's core: the difficulty axis is a per-commit property, asserted equal per sha12.

    The old document is derived over the old-id corpus through the apply's own door, the
    re-minted twin over the label-form corpus (same commits, new ids), and the two documents'
    difficulties must agree for every sha12 — a changed difficulty under the same commit
    would mean the re-mint moved the axis, not just the labels.
    """
    old_root, old_ids, _ = _mined_corpus(tmp_path, staged=False, count=3)
    staged_root, staged_ids, _ = _mined_corpus(tmp_path, staged=True, count=3)

    old_out = tmp_path / "old-stratum.json"
    staged_out = tmp_path / "staged-stratum.json"
    remint_apply.re_derive_stratum([old_root], old_out)
    remint_apply.re_derive_stratum([staged_root], staged_out)

    old_doc = json.loads(old_out.read_text())
    new_doc = json.loads(staged_out.read_text())
    assert set(new_doc["difficulty"]) == set(staged_ids.values())
    for sha12, old_id in old_ids.items():
        assert new_doc["difficulty"][staged_ids[sha12]] == old_doc["difficulty"][old_id], (
            f"task at commit {sha12}: the re-minted difficulty differs from the old "
            "document's, but the commit is the same — the axis moved, not the labels"
        )


def test_the_heldout_rederivation_excludes_the_class_and_never_draws_an_excluded_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The heldout re-derivation over the re-minted corpus: the class excluded, never drawn.

    Fifteen measured tasks, one of whose oracles exceeds the sealed budget at `base_commit`
    (a permanent property of the commit, not machine state). The re-derivation must record
    exactly that task in `excluded` — with the predicate's own reason — and the membership
    must never draw it: `membership ∩ excluded = ∅`, 12 members (AC8's shape over a
    synthetic corpus).
    """
    staged_root, _, bulk_id = _mined_corpus(
        tmp_path, staged=True, count=15, bulk=200_000
    )
    assert bulk_id is not None

    stratum_doc = tmp_path / "tasks" / "stratum" / "easier.json"
    assert stratum.main(["--corpus", str(staged_root), "--out", str(stratum_doc)]) == 0

    monkeypatch.chdir(tmp_path)
    out = tmp_path / "heldout" / "source-b.json"
    remint_apply.re_derive_heldout([staged_root], out)

    doc = json.loads(out.read_text())
    assert set(doc["excluded"]) == {bulk_id}, doc["excluded"]
    reason = doc["excluded"][bulk_id]
    assert "bulk.py" in reason, reason
    assert not (set(doc["membership"]) & set(doc["excluded"])), (
        "the membership draws an id the scorable filter excluded; the draw never holds out "
        "a task the rule refused"
    )
    assert len(doc["membership"]) == 12, doc["membership"]


def test_the_rederivations_use_the_doors_by_identity() -> None:
    """The apply step drives `stratum.main` / `heldout.main` by identity — never a second door."""
    assert remint_apply.stratum is stratum
    assert remint_apply.heldout is heldout


def test_re_derive_stratum_refuses_a_relative_corpus_path(tmp_path: Path) -> None:
    """A relative corpus path is the 2026-08-12 failure class: refused before anything runs."""
    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.re_derive_stratum([Path("tasks/local/donor-a")], tmp_path / "out.json")
    assert "relative" in str(caught.value), caught.value


def test_re_derive_stratum_refuses_a_relative_out(tmp_path: Path) -> None:
    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.re_derive_stratum([tmp_path / "corpus"], Path("tasks/stratum/easier.json"))
    assert "relative" in str(caught.value), caught.value


def test_re_derive_stratum_refuses_when_the_door_refuses(tmp_path: Path) -> None:
    """A door that exits 2 is a named refusal carrying the door's own words, never a bare exit."""
    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.re_derive_stratum([tmp_path / "missing"], tmp_path / "out.json")
    message = str(caught.value)
    assert "stratum" in message and "could not read task manifest" in message, message


def test_re_derive_heldout_refuses_when_the_door_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable stratum document halts the heldout re-derivation by name."""
    corpus, _, _ = _mined_corpus(tmp_path, staged=True, count=1)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(remint_apply.RemintRefusal) as caught:
        remint_apply.re_derive_heldout([corpus], tmp_path / "out.json")
    message = str(caught.value)
    assert "heldout" in message and "stratum document" in message, message
