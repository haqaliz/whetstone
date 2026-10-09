"""The run ledger's seal: `whetstone-run/3`, writer side, then the verifying reader.

The ledger recorded the night and carried no digest of itself: `ledger._payload` wrote fifteen
top-level keys and every consumer read raw through `ledger.read`, which checked the schema
string and nothing else. Under v3 every one of those fifteen keys is a claim — hashed
canonically into `claims`, with `digest` reducing from the sorted `key:hash` lines,
domain-separated by the schema tag exactly as the checkpoint's and the dataset's are. The
reader verifies before any consumer sees the document; a `/2` ledger — what the shipped writer
emitted until this unit — reads unsealed and byte-unchanged; `/1` is refused exactly as it was.

This file starts with the writer's half: the shape, the reduction, and determinism across
processes. The reader's half follows: the dual-read, every adversarial shape refused by name,
the schema strings, and the documented limit (the digest is unkeyed, so a forger who recomputes
it is not caught). The consumers' half — identity imports and refusals through their own doors
— is Phase 2; `morning`'s known-field totality is Phase 3; the one-writer guard is Phase 5.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from loop.test_run_ledger import _ledger
from whetstone.loop import ledger as run_ledger
from whetstone.loop import seal

#: The fifteen body keys the v3 seal covers: today's `_payload` minus `schema`. Written out
#: rather than derived, so a key that silently stops being written is a failure here.
_BODY_KEYS = frozenset(
    {
        "run_id",
        "recorded_on",
        "run_seed",
        "draws",
        "model",
        "backend",
        "generation_contract",
        "task_set",
        "environment_pins",
        "tool_versions",
        "seeds",
        "draws_recorded",
        "dataset",
        "checkpoint",
        "capacity",
    }
)


def _written(tmp_path: Path) -> Path:
    return run_ledger.write(tmp_path / "ledger.json", _ledger())


def _rewrite(path: Path, document: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _v2(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """A `/2` fixture in the probe's shape: a v3 document with the seal keys stripped.

    No real `/2` ledger exists (the one real probe ledger is `/1`), so this helper is the
    tolerance's fixture: the body of a genuine writer-produced document, relabelled to the
    schema the shipped writer emitted until this unit.
    """
    path = _written(tmp_path)
    document = _parse(path)
    del document["claims"]
    del document["digest"]
    document["schema"] = run_ledger.LEDGER_SCHEMA_V2
    _rewrite(path, document)
    return path, document


# ---------------------------------------------------------------------------
# Writer: the shape, the reduction, determinism
# ---------------------------------------------------------------------------


def test_schema_constants() -> None:
    assert run_ledger.LEDGER_SCHEMA_V1 == "whetstone-run/1"
    assert run_ledger.LEDGER_SCHEMA_V2 == "whetstone-run/2"
    assert run_ledger.LEDGER_SCHEMA_V3 == "whetstone-run/3"
    assert run_ledger.LEDGER_SCHEMA == run_ledger.LEDGER_SCHEMA_V3, (
        "WHY THIS IS A FAILURE: the schema written is not the sealed one, so a new ledger's "
        "claims ride outside its digest — the exact hole this unit closes"
    )
    assert {
        "LEDGER_SCHEMA_V1",
        "LEDGER_SCHEMA_V2",
        "LEDGER_SCHEMA_V3",
        "LEDGER_SCHEMA",
    } <= set(run_ledger.__all__)


def test_the_document_seals_every_body_key_under_the_v3_tag() -> None:
    """AC 1: fifteen claims, no more and no fewer, and the seal's own fields are never claimed."""
    document = json.loads(run_ledger.document(_ledger()))
    body = {key: value for key, value in document.items() if key not in seal.UNSEALED_KEYS}

    assert document["schema"] == run_ledger.LEDGER_SCHEMA_V3
    assert set(body) == _BODY_KEYS, (
        f"WHY THIS IS A FAILURE: the sealed body is {sorted(set(body))}, not the fifteen keys "
        "the ledger writes. A body key outside the write function never round-trips"
    )
    assert not _BODY_KEYS & seal.UNSEALED_KEYS
    assert set(document["claims"]) == _BODY_KEYS
    claims = seal.claim_hashes(body, subject="ledger", refuse=run_ledger.LedgerUnverified)
    assert document["claims"] == claims
    assert document["digest"] == seal.claims_digest(claims, schema=run_ledger.LEDGER_SCHEMA_V3), (
        "WHY THIS IS A FAILURE: the emitted document does not reduce to the digest it carries, "
        "so a reader that re-hashes it — the whole point of the seal — refuses an honest write"
    )


def test_the_digest_is_domain_separated_by_the_schema_tag() -> None:
    document = json.loads(run_ledger.document(_ledger()))

    assert document["digest"] != seal.claims_digest(
        document["claims"], schema=run_ledger.LEDGER_SCHEMA_V2
    )
    assert document["digest"] != seal.claims_digest(
        document["claims"], schema="whetstone-training-set/2"
    ), (
        "WHY THIS IS A FAILURE: the same claims digest identically under another document "
        "family's schema tag, so two generations and two families can collide"
    )


def test_the_written_bytes_are_the_documents_bytes(tmp_path: Path) -> None:
    path = _written(tmp_path)
    assert path.read_text(encoding="utf-8") == run_ledger.document(_ledger())


def test_the_document_is_identical_across_processes_and_hash_seeds() -> None:
    """AC 1: a fresh interpreter under either `PYTHONHASHSEED` renders the same bytes.

    Mapping and set iteration order are the two things that vary across processes and not
    within one; a claim map built in iteration order would make the bytes depend on the run
    that produced them, and a reader regenerating them could not tell a re-render from a
    re-measurement.
    """
    in_process = hashlib.sha256(run_ledger.document(_ledger()).encode("utf-8")).hexdigest()
    tests_root = Path(__file__).resolve().parents[1]
    program = (
        f"import sys, hashlib; sys.path.insert(0, {str(tests_root)!r});"
        "from loop.test_run_ledger import _ledger;"
        "from whetstone.loop import ledger;"
        "print(hashlib.sha256(ledger.document(_ledger()).encode('utf-8')).hexdigest())"
    )
    seen = {}
    for seed in ("0", "1"):
        run = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": seed},
        )
        assert run.returncode == 0, run.stderr
        seen[seed] = run.stdout.strip()
    assert seen["0"] == seen["1"] == in_process, (
        "WHY THIS IS A FAILURE: the ledger's bytes depend on the process that produced them "
        f"(hash seeds {seen}); some mapping or set is serialised in iteration order"
    )


# ---------------------------------------------------------------------------
# Reader: the dual-read and the downgrade guard
# ---------------------------------------------------------------------------


def test_a_v3_ledger_verifies_sealed(tmp_path: Path) -> None:
    path = _written(tmp_path)
    parsed = _parse(path)
    verified = run_ledger.verify_document(path)

    assert isinstance(verified, run_ledger.VerifiedLedger)
    assert verified.sealed is True
    assert verified.document == parsed
    assert run_ledger.read(path) == parsed, (
        "WHY THIS IS A FAILURE: the public reader does not go through the verifying one, so a "
        "consumer would read a tampered document that verify_document would refuse"
    )


def test_a_v2_ledger_reads_unsealed_and_byte_unchanged(tmp_path: Path) -> None:
    """AC 3: the shipped generation still reads, exactly as it did, and is never rewritten."""
    path, document = _v2(tmp_path)
    before = path.read_bytes()

    verified = run_ledger.verify_document(path)

    assert verified.sealed is False
    assert verified.document == document
    assert run_ledger.read(path) == document
    assert path.read_bytes() == before, (
        "WHY THIS IS A FAILURE: reading an older ledger rewrote it. A gitignored operator "
        "artifact is never upgraded in place"
    )


def test_a_v2_document_carrying_claims_is_refused_the_downgrade_guard(tmp_path: Path) -> None:
    """A re-labelled v3 document is the one downgrade with no self-digest fallback.

    No `/2` writer ever emitted `claims`, so their presence under the old schema is a
    deliberate refusal: without it a v3 document relabelled `/2` would read as unsealed with
    no refusal anywhere, and its edits would ride along.
    """
    path = _written(tmp_path)
    document = _parse(path)
    document["schema"] = run_ledger.LEDGER_SCHEMA_V2
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match=r"claims.*whetstone-run/2"):
        run_ledger.verify_document(path)


def test_a_v2_document_carrying_a_digest_is_refused_the_downgrade_guard(tmp_path: Path) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    del document["claims"]
    document["schema"] = run_ledger.LEDGER_SCHEMA_V2
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="digest"):
        run_ledger.verify_document(path)


# ---------------------------------------------------------------------------
# Reader: the adversarial set, each shape refused by name
# ---------------------------------------------------------------------------


def test_every_body_claim_moved_is_refused_naming_the_key(tmp_path: Path) -> None:
    """AC 5(a): parameterised over the document's own body keys, so an added key is covered.

    The value is replaced by `[value]` — a type change no writer produces — while `claims` and
    `digest` are left alone, which is what a quiet edit in a text editor looks like.
    """
    path = _written(tmp_path)
    pristine = _parse(path)
    body_keys = sorted(set(pristine) - seal.UNSEALED_KEYS)
    assert body_keys, "the fixture seals nothing, so this test would prove nothing"

    missed = []
    for key in body_keys:
        doctored = copy.deepcopy(pristine)
        doctored[key] = [doctored[key]]
        _rewrite(path, doctored)
        try:
            run_ledger.verify_document(path)
        except run_ledger.LedgerUnverified as refusal:
            assert key in str(refusal), (
                f"the refusal for a moved {key!r} does not name it: {refusal}"
            )
        else:
            missed.append(key)
    assert missed == [], f"moved body keys accepted without a refusal: {missed}"


def test_an_unclaimed_key_is_refused_by_name(tmp_path: Path) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    document["promoted"] = True
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match=r"'promoted', which no claim seals"):
        run_ledger.verify_document(path)


def test_an_orphaned_claim_is_refused_by_name(tmp_path: Path) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    del document["run_seed"]
    _rewrite(path, document)

    with pytest.raises(
        run_ledger.LedgerUnverified, match=r"records claim 'run_seed' and carries no 'run_seed'"
    ):
        run_ledger.verify_document(path)


def test_a_claim_deleted_while_its_body_key_remains_is_refused(tmp_path: Path) -> None:
    """The body key is then unclaimed, so it is refused exactly as a key added later would be."""
    path = _written(tmp_path)
    document = _parse(path)
    del document["claims"]["run_seed"]
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match=r"'run_seed', which no claim seals"):
        run_ledger.verify_document(path)


def test_a_claim_and_its_body_key_deleted_together_are_refused(tmp_path: Path) -> None:
    """The digest is what catches this one: the remaining claims agree with each other."""
    path = _written(tmp_path)
    document = _parse(path)
    del document["run_seed"]
    del document["claims"]["run_seed"]
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="disagrees with itself"):
        run_ledger.verify_document(path)


def test_two_swapped_claim_values_name_the_first_moved_key(tmp_path: Path) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    claims = document["claims"]
    claims["draws"], claims["run_seed"] = claims["run_seed"], claims["draws"]
    _rewrite(path, document)

    with pytest.raises(
        run_ledger.LedgerUnverified,
        match=r"claim 'draws'.*was changed after the ledger was sealed",
    ):
        run_ledger.verify_document(path)


@pytest.mark.parametrize("value", ["g" * 64, "0" * 63, "A" * 64], ids=["non-hex", "short", "upper"])
def test_a_claim_hash_that_is_not_a_sha256_is_refused(tmp_path: Path, value: str) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    document["claims"]["run_seed"] = value
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match=r"claim 'run_seed' .* not a sha256"):
        run_ledger.verify_document(path)


def test_a_newline_bearing_claim_key_is_refused(tmp_path: Path) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    document["claims"]["a\nb"] = "0" * 64
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="holds a newline"):
        run_ledger.verify_document(path)


@pytest.mark.parametrize(
    "claims",
    [None, "x", ["run_seed"], {"run_seed": 1}],
    ids=["missing", "string", "list", "int-hash"],
)
def test_a_v3_document_without_a_claims_mapping_is_refused(tmp_path: Path, claims: Any) -> None:
    path = _written(tmp_path)
    document = _parse(path)
    if claims is None:
        del document["claims"]
    else:
        document["claims"] = claims
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="claims mapping"):
        run_ledger.verify_document(path)


def test_malformed_or_absent_json_is_unreadable_not_unverified(tmp_path: Path) -> None:
    """A parse failure is the base refusal; tamper is the named one. The two never blur."""
    broken = tmp_path / "broken.json"
    broken.write_text("not json at all", encoding="utf-8")
    with pytest.raises(run_ledger.LedgerUnreadable) as unreadable:
        run_ledger.verify_document(broken)
    assert not isinstance(unreadable.value, run_ledger.LedgerUnverified)

    listing = tmp_path / "listing.json"
    listing.write_text(json.dumps([1, 2]), encoding="utf-8")
    with pytest.raises(run_ledger.LedgerUnreadable):
        run_ledger.verify_document(listing)

    with pytest.raises(run_ledger.LedgerUnreadable):
        run_ledger.verify_document(tmp_path / "absent.json")


def test_the_named_refusal_is_a_ledger_unreadable_and_says_ledger(tmp_path: Path) -> None:
    """Every consumer's refusal tuple already holds the base class, so no tuple needs an edit."""
    assert issubclass(run_ledger.LedgerUnverified, run_ledger.LedgerUnreadable)

    path = _written(tmp_path)
    document = _parse(path)
    document["run_seed"] = [document["run_seed"]]
    _rewrite(path, document)
    with pytest.raises(run_ledger.LedgerUnverified) as refusal:
        run_ledger.verify_document(path)
    assert "ledger" in str(refusal.value), refusal.value
    assert "checkpoint" not in str(refusal.value), refusal.value


# ---------------------------------------------------------------------------
# Reader: the schema strings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema", ["whetstone-run/1", "whetstone-run/99", "something-else/1"])
def test_a_ledger_of_any_other_schema_is_refused_naming_both(tmp_path: Path, schema: str) -> None:
    """AC 6: `/1` and anything unknown are refused, and the message names both accepted schemas.

    `test_backend.py:201-218` passes unedited on this: `LEDGER_SCHEMA` is `/3`, so it is not
    `/1`, and a `/1` stub still raises.
    """
    path = _written(tmp_path)
    document = _parse(path)
    document["schema"] = schema
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnreadable) as refusal:
        run_ledger.verify_document(path)
    assert run_ledger.LEDGER_SCHEMA_V2 in str(refusal.value)
    assert run_ledger.LEDGER_SCHEMA_V3 in str(refusal.value)


def test_a_v2_payload_relabelled_v3_without_claims_is_refused(tmp_path: Path) -> None:
    path, document = _v2(tmp_path)
    document["schema"] = run_ledger.LEDGER_SCHEMA_V3
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified, match="claims mapping"):
        run_ledger.verify_document(path)


# ---------------------------------------------------------------------------
# The limit, pinned rather than implied
# ---------------------------------------------------------------------------


def test_a_forger_who_recomputes_the_claims_is_not_caught(tmp_path: Path) -> None:
    """AC 7, the documented limit: the digest is an unkeyed hash, never authentication.

    Editing a value and recomputing `claims` and `digest` consistently (`PRD` § 3) produces a
    document this reader accepts and reports `sealed`. That is the boundary the vocabulary
    states, not a defect: the seal catches accident-shaped edits and disagreement with a digest
    cited elsewhere; anyone who can edit the file can recompute both.
    """
    path = _written(tmp_path)
    document = _parse(path)
    document["run_seed"] = 7
    body = {key: value for key, value in document.items() if key not in seal.UNSEALED_KEYS}
    document["claims"] = seal.claim_hashes(
        body, subject="ledger", refuse=run_ledger.LedgerUnverified
    )
    document["digest"] = seal.claims_digest(document["claims"], schema=run_ledger.LEDGER_SCHEMA_V3)
    _rewrite(path, document)

    forged = run_ledger.verify_document(path)

    assert forged.sealed is True
    assert forged.document["run_seed"] == 7


# ---------------------------------------------------------------------------
# Phase 2: every consumer verifies by identity; probe-001's real record corrected
# ---------------------------------------------------------------------------


def test_every_consumer_reads_the_ledger_through_the_ledgers_reader() -> None:
    """The spec's "by identity not by edit" (In scope 4): one read path, four consumers.

    Each name is asserted `is` rather than called: a consumer that re-spelled the reader — a
    second parse, an optimistic `json.loads` — would read a tampered document while the
    verifying path refused it, and the day the two disagreed neither would say so.
    """
    from whetstone.loop import check_leakage, check_probe, honest_report, morning

    assert check_probe.read_ledger is run_ledger.read
    assert morning._read_ledger_payload is run_ledger.read
    assert honest_report.read_ledger is run_ledger.read
    assert check_leakage.read_ledger is run_ledger.read


def test_every_consumer_refusal_tuple_holds_the_base_refusal() -> None:
    """`LedgerUnverified` subclasses `LedgerUnreadable`, so a tamper is exit 2 by identity."""
    from whetstone.loop import check_leakage, check_probe, honest_report, morning

    for refusals in (
        check_probe.REFUSALS,
        check_leakage.REFUSALS,
        honest_report.REFUSALS,
        morning.REFUSALS,
    ):
        assert run_ledger.LedgerUnreadable in refusals


def _doctored(tmp_path: Path) -> Path:
    """A genuine v3 write with one body key moved: the tamper every consumer must refuse."""
    path = _written(tmp_path)
    document = _parse(path)
    document["run_seed"] = [document["run_seed"]]
    _rewrite(path, document)
    return path


def test_the_probe_check_refuses_a_doctored_v3_ledger_before_any_decision(tmp_path: Path) -> None:
    """Through the consumer's own door: a doctored run refuses before the fold is read."""
    from loop.test_check_probe import _probe_run
    from whetstone.loop import check_probe

    run = _probe_run(tmp_path)
    path = run / run_ledger.LEDGER_FILE
    document = _parse(path)
    document["run_seed"] = [document["run_seed"]]
    _rewrite(path, document)

    with pytest.raises(run_ledger.LedgerUnverified) as refusal:
        check_probe.run_check(run)
    assert "run_seed" in str(refusal.value)


def test_morning_refuses_a_doctored_v3_ledger_by_name(tmp_path: Path) -> None:
    from whetstone.loop import morning

    with pytest.raises(run_ledger.LedgerUnverified) as refusal:
        morning.read_ledger(_doctored(tmp_path))
    assert "run_seed" in str(refusal.value)


def test_the_honest_report_reader_refuses_a_doctored_v3_ledger_by_name(tmp_path: Path) -> None:
    from whetstone.loop import honest_report

    with pytest.raises(run_ledger.LedgerUnverified) as refusal:
        honest_report.read_ledger(_doctored(tmp_path))
    assert "run_seed" in str(refusal.value)


def test_the_leakage_check_refuses_a_doctored_v3_ledger_before_the_comparison(
    tmp_path: Path,
) -> None:
    """The check's own door: dataset valid, comparison would be clean, ledger tampered.

    `check_leakage.run_check`'s body is unchanged — the dataset read and the overlap
    comparison are the same code — and the tamper refuses only because the module reads the
    ledger through `ledger.read` by identity.
    """
    from loop.test_check_leakage import _MEMBERS, _SURVIVOR, _heldout_document, _run
    from whetstone.loop import check_leakage

    run = _run(tmp_path / "runs" / "night-001", private=(_SURVIVOR,), ledger=False)
    path = run_ledger.write(run / run_ledger.LEDGER_FILE, _ledger())
    document = _parse(path)
    document["run_seed"] = [document["run_seed"]]
    _rewrite(path, document)
    heldout = _heldout_document(tmp_path, _MEMBERS)

    with pytest.raises(run_ledger.LedgerUnverified) as refusal:
        check_leakage.run_check(run, heldout)
    assert "run_seed" in str(refusal.value)


def _primary() -> Path:
    """The primary checkout, resolved from git — a worktree holds none of `runs/`.

    The `test_gate_leakage_finding.py:63-74` pattern, so the gitignored artefact is found
    rather than named by a literal path that only holds on this machine.
    """
    root = Path(__file__).resolve().parents[2]
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        pytest.skip(
            "SKIPPED LOUDLY: git could not name the primary checkout, so the real "
            f"probe-001 ledger cannot be re-checked ({error})"
        )
    return Path(common).parent


def test_the_real_probe_ledger_is_v1_and_still_refused() -> None:
    """AC 4, the corrected premise: the one real probe ledger predates `/2`.

    The PRD recorded the probe-001 ledger as `/2`; the primary checkout's bytes say `/1` —
    verified, not assumed — and `/1` is refused by schema equality, exactly as before the
    seal. Skips loudly, naming the artefact, when the primary checkout holds no `runs/`
    (a fresh clone, CI); it never passes silently and never rewrites the byte.
    """
    primary = _primary()
    ledger_path = primary / "runs" / "night-probe" / "probe-001" / "ledger.json"
    if not ledger_path.is_file():
        pytest.skip(
            "SKIPPED LOUDLY: the primary checkout holds no "
            "runs/night-probe/probe-001/ledger.json, so the corrected premise cannot be "
            "re-checked against the real artefact"
        )
    before = ledger_path.read_bytes()
    document = json.loads(before.decode("utf-8"))

    assert document["schema"] == run_ledger.LEDGER_SCHEMA_V1

    with pytest.raises(run_ledger.LedgerUnreadable) as refusal:
        run_ledger.verify_document(ledger_path)
    assert not isinstance(refusal.value, run_ledger.LedgerUnverified)
    assert run_ledger.LEDGER_SCHEMA_V1 in str(refusal.value)
    assert ledger_path.read_bytes() == before, (
        "WHY THIS IS A FAILURE: a read rewrote the primary checkout's live record. No "
        "document under runs/ is ever touched"
    )


# ---------------------------------------------------------------------------
# Phase 3: the report's reader knows every key the writer emits
# ---------------------------------------------------------------------------


def test_the_morning_reader_knows_every_key_the_ledger_writer_emits() -> None:
    """AC 9: the writer's key set and the report reader's known set cannot drift apart.

    A key added later would make every genuine v3 report refuse as an unknown-key change — the
    writer and the report reader would stop describing the same document. Asserted on the
    emitted document, so the writer's actual output bounds the set, with the two seal keys
    named explicitly so the assertion cannot go vacuous on a document that lost them.
    """
    from whetstone.loop import morning

    document = json.loads(run_ledger.document(_ledger()))

    assert {"claims", "digest"} <= set(document), (
        "the emitted document carries no seal keys, so the coverage assertion below would "
        "prove nothing about the generation the writer emits"
    )
    assert {"claims", "digest"} <= morning._KNOWN_FIELDS
    assert set(document) <= morning._KNOWN_FIELDS, (
        f"the writer emits {sorted(set(document) - morning._KNOWN_FIELDS)} and the morning "
        "reader does not know them; every genuine v3 report would refuse as an unknown-key "
        "change"
    )


# ---------------------------------------------------------------------------
# Phase 5: one writer, and the fuser never sees a run document
# ---------------------------------------------------------------------------


_LEDGER_FILE_MARKERS = frozenset({"LEDGER_FILE"})
_WRITE_METHODS = frozenset({"write_text", "write_bytes"})


def _names_the_ledger_file(node: ast.AST, aliases: set[str], *, literal: bool = True) -> bool:
    """Whether an expression names the ledger document: the constant, an alias, or the bytes.

    `literal=False` ignores the bare string, which is how aliases are seeded: a module that
    binds `"ledger.json"` to its own constant (`honest_report.py:52`, read-only) has not
    bound a write. The literal is matched **exactly** — never as a substring — so
    `tasks/mine.py` and `remint_apply.py`'s `local-ledger.json`, a different ledger's staged
    evidence, are not the run ledger.
    """
    for each in ast.walk(node):
        if isinstance(each, ast.Name) and (each.id in _LEDGER_FILE_MARKERS or each.id in aliases):
            return True
        if isinstance(each, ast.Attribute) and each.attr in _LEDGER_FILE_MARKERS:
            return True
        if literal and isinstance(each, ast.Constant) and each.value == "ledger.json":
            return True
    return False


def _opens_for_writing(call: ast.Call, *, mode_at: int) -> bool:
    """Whether an `open` call carries a write, append or exclusive mode (`mode_at` positional)."""
    modes = [
        *call.args[mode_at : mode_at + 1],
        *(one.value for one in call.keywords if one.arg == "mode"),
    ]
    return any(
        isinstance(mode, ast.Constant)
        and isinstance(mode.value, str)
        and set(mode.value) & set("wax+")
        for mode in modes
    )


def _writes_of_the_ledger_file(source: str) -> list[int]:
    """Line numbers where `source` writes the run ledger; reads and prose are not."""
    tree = ast.parse(source)
    aliases: set[str] = set()
    for _ in range(3):  # a name bound from a name bound from the file, a few steps deep
        for each in ast.walk(tree):
            if isinstance(each, ast.Assign) and _names_the_ledger_file(
                each.value, aliases, literal=False
            ):
                aliases.update(t.id for t in each.targets if isinstance(t, ast.Name))
    lines: list[int] = []
    for each in ast.walk(tree):
        if not isinstance(each, ast.Call):
            continue
        func = each.func
        if isinstance(func, ast.Attribute) and func.attr in _WRITE_METHODS:
            written = _names_the_ledger_file(func.value, aliases)
        elif isinstance(func, ast.Attribute) and func.attr == "open":
            written = _names_the_ledger_file(func.value, aliases) and _opens_for_writing(
                each, mode_at=0
            )
        elif isinstance(func, ast.Name) and func.id == "open" and each.args:
            written = _names_the_ledger_file(each.args[0], aliases) and _opens_for_writing(
                each, mode_at=1
            )
        else:
            written = False
        if written:
            lines.append(each.lineno)
    return sorted(lines)


def test_the_scanner_flags_a_writer_and_passes_a_reader() -> None:
    writers = [
        "(directory / LEDGER_FILE).write_text('x')",
        "(d / run_ledger.LEDGER_FILE).write_bytes(b'x')",
        "(d / 'ledger.json').write_text('x')",
        "open(d / LEDGER_FILE, 'w')",
        "open(d / 'ledger.json', mode='a')",
        "(d / LEDGER_FILE).open('w')",
        "target = d / LEDGER_FILE\ntarget.write_text('x')",
    ]
    for source in writers:
        assert _writes_of_the_ledger_file(source), source

    clean = [
        "payload = json.loads((c / LEDGER_FILE).read_text())",
        "open(c / LEDGER_FILE).read()",
        "open(c / LEDGER_FILE, 'r')",
        '"""Writes ledger.json via LEDGER_FILE.write_text."""\nx = 1',
        "# (d / LEDGER_FILE).write_text('x')\nx = 1",
        "(d / 'other.json').write_text('x')",
        "LEDGER_FILE = 'ledger.json'",
        "(d / 'local-ledger.json').write_text('x')",
        "LEDGER_NAME = 'local-ledger.json'",
    ]
    for source in clean:
        assert _writes_of_the_ledger_file(source) == [], source


def test_only_the_ledger_module_writes_the_ledger_document() -> None:
    """In scope 11: one writer. A second one would be a second document shape, sealed or not.

    The `test_only_sft_writes_the_checkpoint_document` shape (`test_checkpoint_seal.py:944`):
    no source under `src/whetstone/` outside `ledger.py` writes `LEDGER_FILE` — by the
    constant, by an alias bound from it, or by the exact literal `"ledger.json"`, never a
    substring, so the miner's and `remint_apply.py`'s `local-ledger.json` (a different
    ledger's staged evidence) are not flagged and `honest_report.py:52`'s read-only spelling
    of the constant is not a write. The writer's own write is parameterized by path, so its
    teeth are asserted separately: the module holds the write primitive the guard is about.
    """
    root = Path(run_ledger.__file__).resolve().parents[1]  # src/whetstone
    writer = Path(run_ledger.__file__).resolve()
    sources = sorted(root.rglob("*.py"))
    assert writer in sources

    offenders = {
        str(path.relative_to(root)): lines
        for path in sources
        if path != writer
        and (lines := _writes_of_the_ledger_file(path.read_text(encoding="utf-8")))
    }
    assert offenders == {}, (
        f"WHY THIS IS A FAILURE: {sorted(offenders)} write the run ledger. A second writer "
        "is a second document shape, and the seal has no way to tell the two apart"
    )
    assert run_ledger.LEDGER_SCHEMA == run_ledger.LEDGER_SCHEMA_V3, (
        "WHY THIS IS A FAILURE: the writer's declared schema is not the sealed one, so a "
        "new ledger is written unsealed under the v3 name"
    )
    tree = ast.parse(writer.read_text(encoding="utf-8"))
    write_primitives = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _WRITE_METHODS
    ]
    assert write_primitives, (
        "WHY THIS IS A FAILURE: the ledger module itself holds no write primitive, so the "
        "one-writer guard is asserting about a writer that does not write"
    )


def test_the_fuser_reads_no_run_document() -> None:
    """AC 11: `fuse` is checkpoint-only — its bytes carry no run-document seam.

    A full read finds no `ledger.json` / `dataset.json` literal, no `LEDGER_FILE` /
    `DATASET_FILE` name, and no import of the run-document modules: the fuser's one
    document read is the checkpoint's own provenance through `sft.verify_checkpoint`, and
    its one write is `fusion.json`. A second read of a run document here would grow a
    second answer to what the night recorded. The `whetstone-run/2` mention at
    `fuse.py:85` is a checkpoint-side naming inaccuracy this aspect records and
    deliberately does not fix.
    """
    from whetstone.loop import fuse

    source = Path(fuse.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    markers = frozenset({"LEDGER_FILE", "DATASET_FILE"})
    used = set()
    for each in ast.walk(tree):
        if isinstance(each, ast.Name) and each.id in markers:
            used.add(each.id)
        if isinstance(each, ast.Attribute) and each.attr in markers:
            used.add(each.attr)
        if isinstance(each, ast.Constant) and each.value in ("ledger.json", "dataset.json"):
            used.add(str(each.value))
    assert not used, (
        f"WHY THIS IS A FAILURE: the fuser names a run document: {sorted(used)}. Fusing "
        "needs the checkpoint's provenance and nothing beside it"
    )
    imported = set()
    for each in ast.walk(tree):
        if isinstance(each, ast.Import):
            imported.update(alias.name for alias in each.names)
        elif isinstance(each, ast.ImportFrom):
            if each.module:
                imported.add(each.module)
            imported.update(alias.name for alias in each.names)
    run_document_modules = {
        name
        for name in imported
        if name.split(".")[-1] in ("ledger", "dataset")
    }
    assert not run_document_modules, (
        f"WHY THIS IS A FAILURE: the fuser imports run-document modules "
        f"{sorted(run_document_modules)}; the checkpoint is its only document"
    )
