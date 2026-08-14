"""The run-side stratum filter: `--stratum` end to end, through the real driver.

The probe must score exactly the stratum's tasks from the loaded source-B corpora, and the
seam it plugs into is the partition (`run.py:540-543`) — before the contract is frozen, so
both audit trails cover the subset automatically: `freeze` digests the posed prompts of the
tasks it is handed, and `Conducted.scored` is derived from the sweeps over the filtered sets.

This file proves the whole mechanism through `_run`/`_corpus` from `test_run.py` (the
`test_dev_subset_mechanism.py:26-28` pattern): the inclusion semantics, the loader's
refusals surfacing through the driver, the dev-overlay interplay, both sources publishing
together, the contract covering exactly the subset, `--probe` slicing the filtered set, and
the byte-identity of the unflagged path (a run without `--stratum` reproduces the unflagged
contract SHA, and the provenance sentence is literally the pre-stratum sentence).

The loader consumed here is aspect 1's, by identity — asserted `is` below (imported, never
copied, the diffcheck rule). The refusal classes are the module's own.

No model, no `mlx`, no network. The base is the refusing stub `_run` injects; the tasks are
two-commit synthetic donors built with real git. Nothing writes outside `tmp_path`.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from bakeoff.test_report import CONTRACT, FUNNEL, PROVENANCE, _entrant, _rollout, _sweep
from bakeoff.test_run import _run
from whetstone.bakeoff import run as run_module
from whetstone.bakeoff import stratum
from whetstone.bakeoff.report import Entrant, ScoredDevSubset, build_report
from whetstone.bakeoff.run import (
    COST_FILE,
    PROBE_FILE,
    REPORT_FILE,
    build_parser,
    main,
)
from whetstone.bakeoff.scoring import Outcome
from whetstone.bakeoff.stratum import (
    EmptyStratum,
    StratumDigestMismatch,
    StratumSchemaError,
    UnknownStratumId,
)

#: The private corpus `_run` builds by default — the loaded-ids the membership resolves against.
_PRIVATE = ("alpha", "beta", "gamma")


def _stratum(
    root: Path,
    members: Sequence[str],
    *,
    corpus: Sequence[str] = _PRIVATE,
    **fields: Any,
) -> Path:
    """A valid `whetstone-stratum/1` document over `corpus` with membership `members`.

    The digest is sealed through aspect 1's own `document_digest_of` **after** `fields` are
    applied, so a doctored field does not hide behind a stale digest — a test that plants an
    edit reaches the check it is about.
    """
    raw: dict[str, Any] = {
        "schema": stratum.STRATUM_SCHEMA,
        "rule_digest": stratum.rule_digest(),
        "band": {"max_non_test_files": 1, "max_hunks": 2, "max_changed_lines": 30},
        "corpus": list(corpus),
        "donor_heads": {},
        "difficulty": {
            task_id: {
                "files": 1,
                "hunks": 1,
                "added": 1,
                "deleted": 1,
                "f2p": 1,
                "pins": 0,
                "blobs": 1,
            }
            for task_id in corpus
        },
        "refusals": {},
        "membership": list(members),
    }
    raw.update(fields)
    raw["document_digest"] = stratum.document_digest_of(raw)
    root.mkdir(parents=True, exist_ok=True)
    out = root / "easier.json"
    out.write_text(json.dumps(raw))
    return out


def _minimum_cli() -> list[str]:
    """The flags the parser requires, so a test about one option is not a test about the others."""
    return [
        "--tasks", "/corpus/donor-a",
        "--public", "/corpus/public",
        "--pool", "/corpus/pool.json",
        "--funnel", "/corpus/funnel.json",
        "--weights", "/weights",
        "--out", "/out",
        "--workspace", "/scratch",
        "--timeout", "900",
        "--recorded-on", "2026-08-14",
    ]


class _FakeConducted:
    """What `main` reads off a run: the cost lines and the written report paths."""

    costs: tuple[object, ...] = ()
    written: tuple[str, str] | None = None


def test_a_stratum_selects_exactly_its_membership_from_the_loaded_private_corpus(
    tmp_path: Path,
) -> None:
    """AC 1: inclusion — `{alpha, gamma}` from a three-task corpus, source A in full.

    The scored set, both denominators, and the sealed prompts are all asserted, so a filter
    that merely skipped scoring (rather than excluding) could not pass: `Conducted.scored`
    and the denominators come from the sweeps, while `contract.posed` comes from `freeze` —
    two derivations of "the subset" that must agree, and an excluded task contributes **no
    prompt digest** to either.
    """
    doc = _stratum(tmp_path / "doc", ("alpha", "gamma"))
    conducted = _run(tmp_path, stratum=doc)

    assert conducted.report is not None
    assert set(conducted.scored) == {"alpha", "gamma", "pallets__flask-4045"}, (
        f"WHY THIS IS A FAILURE: the scored set is {conducted.scored!r} rather than the "
        "stratum's tasks plus the public instance. A task outside the membership reached a "
        "scored rollout, so the probe's denominator would not be the stratum's"
    )
    assert conducted.report.private[0].denominator == 2, (
        f"WHY THIS IS A FAILURE: the published private denominator is "
        f"{conducted.report.private[0].denominator} rather than 2. The stratum's size is "
        "what the probe's counts are published over; a denominator that differs from the "
        "membership is a count over a different set than the report says"
    )
    assert conducted.report.public[0].denominator == 1, (
        f"WHY THIS IS A FAILURE: source A's denominator moved: "
        f"{conducted.report.public[0].denominator}. A stratum defined over source B must "
        "never touch the public source (spec D2)"
    )
    assert set(conducted.contract.posed.values()) == {
        "alpha",
        "gamma",
        "pallets__flask-4045",
    }, (
        f"WHY THIS IS A FAILURE: the frozen contract poses prompts for "
        f"{sorted(set(conducted.contract.posed.values()))!r}. A prompt digest exists for the "
        "excluded task, so its question was sealed into the generation contract — the "
        "subset's audit trail would not match the subset"
    )


def test_a_membership_id_matching_no_loaded_task_is_refused_naming_the_loaded_ids(
    tmp_path: Path,
) -> None:
    """AC 2: a membership id that resolves nowhere in the loaded private corpus is refused.

    The document itself is valid (the id is measured inside its own corpus, digest sealed),
    so the refusal that fires is the run-side half of spec D4-4: the scope is the loaded
    private corpus only (spec Open question 3), and the refusal lists the loaded ids so the
    operator can see the typo.
    """
    doc = _stratum(
        tmp_path / "doc",
        ("alpha", "ghost"),
        corpus=("alpha", "beta", "gamma", "ghost"),
    )

    with pytest.raises(UnknownStratumId) as refusal:
        _run(tmp_path, stratum=doc)
    message = str(refusal.value)
    assert "ghost" in message, (
        f"WHY THIS IS A FAILURE: the refusal does not name the id that matched nothing: "
        f"{message!r}"
    )
    for loaded in _PRIVATE:
        assert loaded in message, (
            f"WHY THIS IS A FAILURE: the refusal does not list the loaded id {loaded!r}, so "
            f"the operator cannot see the typo: {message!r}"
        )


def test_an_empty_membership_is_refused_through_the_run(tmp_path: Path) -> None:
    """AC 3: a stratum of nothing is a usage error even when a run is standing by."""
    doc = _stratum(tmp_path / "doc", ())

    with pytest.raises(EmptyStratum) as refusal:
        _run(tmp_path, stratum=doc)
    assert "empty" in str(refusal.value).lower(), refusal.value


def test_an_unknown_schema_is_refused_through_the_run(tmp_path: Path) -> None:
    """AC 4: an old-schema document fails decode by name, never defaults."""
    doc = _stratum(tmp_path / "doc", ("alpha",), schema="whetstone-stratum/0")

    with pytest.raises(StratumSchemaError) as refusal:
        _run(tmp_path, stratum=doc)
    assert "whetstone-stratum/0" in str(refusal.value), refusal.value


def test_a_rule_digest_drift_is_refused_naming_the_rule_and_the_expected_digest(
    tmp_path: Path,
) -> None:
    """AC 5: the rule half — a document sealed under a different rule is refused by name.

    The edit is applied to the file without re-sealing, and the rule-digest check precedes
    the document-digest check, so the refusal that fires names the rule and shows the
    module's current digest — the expected value the document must be regenerated against.
    """
    doc = _stratum(tmp_path / "doc", ("alpha",))
    raw = json.loads(doc.read_text())
    raw["rule_digest"] = "0" * 64
    doc.write_text(json.dumps(raw))

    with pytest.raises(StratumDigestMismatch) as refusal:
        _run(tmp_path, stratum=doc)
    message = str(refusal.value)
    assert "rule" in message.lower(), (
        f"WHY THIS IS A FAILURE: the refusal does not name the rule digest: {message!r}"
    )
    assert stratum.rule_digest() in message, (
        f"WHY THIS IS A FAILURE: the refusal does not show the expected (current) digest, so "
        f"the operator cannot tell what the document must be regenerated against: {message!r}"
    )


def test_a_hand_edited_membership_is_refused_naming_the_document_digest(tmp_path: Path) -> None:
    """AC 5/9: the document half — a hand-edited membership is refused rather than trusted.

    The membership edit is applied without re-sealing, so the refusal names the document
    digest and shows the expected digest the payload would have to match.
    """
    doc = _stratum(tmp_path / "doc", ("alpha",))
    raw = json.loads(doc.read_text())
    raw["membership"] = ["gamma"]
    doc.write_text(json.dumps(raw))

    with pytest.raises(StratumDigestMismatch) as refusal:
        _run(tmp_path, stratum=doc)
    message = str(refusal.value)
    assert "document" in message.lower(), (
        f"WHY THIS IS A FAILURE: the refusal does not name the document digest: {message!r}"
    )
    assert stratum.document_digest_of(raw) in message, (
        f"WHY THIS IS A FAILURE: the refusal does not show the expected digest, so a reader "
        f"cannot check the tampering against the payload: {message!r}"
    )


def test_a_dev_id_inside_the_membership_is_excluded_from_scoring_and_both_denominators(
    tmp_path: Path,
) -> None:
    """AC 6 / D7: dev ∩ stratum is exclusion, never a refusal.

    The real probe expects this — the declared dev ids may fall inside the band — so the
    overlay applies on top of the stratum and the dev member is excluded from scoring and
    from both denominators. (The doctored document that *smuggles* a dev id in is refused by
    the loader's checks, never by the overlap.)
    """
    root = tmp_path / "arm"
    ids = ("alpha", "beta", "gamma", "dev-b")
    doc = _stratum(root / "doc", ("alpha", "beta", "dev-b"), corpus=ids)
    conducted = _run(tmp_path, private=ids, stratum=doc, dev_subset=["dev-b"])

    assert "dev-b" not in conducted.scored, (
        f"WHY THIS IS A FAILURE: a declared dev-subset task was scored anyway "
        f"({conducted.scored}). Its prompt and extractor were developed against it, so its "
        "outcome is not a measurement of anything"
    )
    assert conducted.report is not None
    assert conducted.report.private[0].denominator == 2, (
        f"WHY THIS IS A FAILURE: the private denominator is "
        f"{conducted.report.private[0].denominator} rather than 2. The stratum selected "
        "alpha, beta and the dev member; the dev member was dev-excluded, and the published "
        "denominator must reflect the exclusion"
    )
    assert conducted.report.public[0].denominator == 1


def test_a_stratum_wholly_dev_excluded_is_refused_before_freeze(tmp_path: Path) -> None:
    """AC 6: an empty scored private set after the overlay is refused before anything runs.

    `MissingSource` would refuse the report only after the night is spent (report.py:488-493);
    this refusal fires before the contract is frozen, before weights are loaded, and before
    any cost sidecar or report exists — a run that could only publish source A alone is
    refused, not spent.
    """
    ids = ("alpha", "beta", "gamma", "dev-b")
    doc = _stratum(tmp_path / "doc", ("dev-b",), corpus=ids)

    with pytest.raises(EmptyStratum) as refusal:
        _run(tmp_path, private=ids, stratum=doc, dev_subset=["dev-b"])
    assert "dev" in str(refusal.value).lower() or "private" in str(refusal.value).lower(), (
        f"WHY THIS IS A FAILURE: the refusal does not name what was excluded: "
        f"{refusal.value!r}"
    )
    out = tmp_path / "out"
    for artifact in (REPORT_FILE, f"{REPORT_FILE}.json", COST_FILE, PROBE_FILE):
        assert not (out / artifact).exists(), (
            f"WHY THIS IS A FAILURE: {artifact!r} exists after a run that was refused before "
            "freeze. A document on disk is a document somebody quotes, and it outlives the "
            "exception that should have stopped it"
        )


def test_source_a_is_always_scored_in_full_and_both_sources_publish_together(
    tmp_path: Path,
) -> None:
    """AC 7: the stratum is defined over source B only; source A is untouched, never alone."""
    doc = _stratum(tmp_path / "doc", ("alpha", "gamma"))
    conducted = _run(tmp_path, stratum=doc)

    assert conducted.report is not None
    assert conducted.report.public[0].denominator == 1, (
        "WHY THIS IS A FAILURE: source A's denominator changed under --stratum. The public "
        "source is not part of the stratum's scope (spec D2)"
    )
    assert conducted.written is not None, (
        "WHY THIS IS A FAILURE: the run published nothing, so source A's instance exists in "
        "no report — a stratum run that quietly dropped the public source"
    )
    assert "pallets__flask-4045" in conducted.report.markdown


def test_the_stratum_runs_contract_covers_exactly_the_subset(tmp_path: Path) -> None:
    """AC 8: the sealed prompts are exactly the subset's, and the SHA says so.

    The no-stratum run's contract and the stratum run's contract are two different frozen
    questions — an outside reader holding the manifests can recompute either — and the
    stratum run poses no digest for the excluded task.
    """
    plain = _run(tmp_path / "plain")
    doc = _stratum(tmp_path / "doc", ("alpha", "gamma"))
    stratified = _run(tmp_path / "arm", stratum=doc)

    assert stratified.contract.sha256 != plain.contract.sha256, (
        "WHY THIS IS A FAILURE: the stratum run's contract SHA equals the no-stratum run's. "
        "The sealed prompt set is the audit trail of what was asked; a stratum that asks the "
        "same set was not a subset"
    )
    assert set(stratified.contract.posed.values()) == {
        "alpha",
        "gamma",
        "pallets__flask-4045",
    }


def test_a_run_without_the_flag_reproduces_the_unflagged_contract_sha(tmp_path: Path) -> None:
    """AC 10: the no-stratum path is literally untouched — two unflagged runs agree, byte for byte.

    The no-retries precedent (`freeze`, run.py:437-440): omitting `--stratum` reproduces the
    unflagged contract exactly, so a reader recomputing the SHA from the committed manifests
    gets the published value. The provenance sentence is also asserted to be the pre-stratum
    sentence — no stratum clause may leak into the unflagged path.
    """
    first = _run(tmp_path / "first")
    second = _run(tmp_path / "second")

    assert first.contract.sha256 == second.contract.sha256, (
        "WHY THIS IS A FAILURE: two unflagged runs over identical fixtures froze different "
        "contracts. The no-stratum path is not deterministic, so no reader can recompute "
        "the published SHA from the committed manifests"
    )
    assert first.contract.posed == second.contract.posed
    assert first.report is not None
    assert "selected by the committed stratum" not in first.report.markdown, (
        "WHY THIS IS A FAILURE: the unflagged run's provenance sentence names a stratum. "
        "The task-set disclosure must be literally the pre-stratum sentence when --stratum "
        "is absent"
    )


def test_the_task_set_sentence_names_the_stratum_document_and_its_membership_count(
    tmp_path: Path,
) -> None:
    """D6: with --stratum, the provenance names the pinned input a reader can check.

    The count itself follows `len(private_tasks)`; the sentence adds the document path and
    the membership count it selected, so an outside reader holding the committed document can
    verify the report's scope against it.
    """
    doc = _stratum(tmp_path / "doc", ("alpha", "gamma"))
    conducted = _run(tmp_path, stratum=doc)

    assert conducted.report is not None
    sentence = conducted.report.markdown
    assert str(doc) in sentence, (
        f"WHY THIS IS A FAILURE: the task-set sentence does not name the stratum document: "
        f"{sentence!r}"
    )
    assert "membership 2" in sentence, (
        f"WHY THIS IS A FAILURE: the task-set sentence does not carry the membership count "
        f"({sentence!r})"
    )


def test_the_scored_dev_subset_backstop_still_fires_for_a_stratum_member(tmp_path: Path) -> None:
    """The backstop layer, exercised through the stratum path (test_dev_subset_mechanism:90-114).

    The partition removes declared ids before anything runs; this is the second layer, for a
    dev id that reaches the scored set anyway — a caller that bypasses the overlay. A stratum
    member leaked into the scored set is refused by `build_report`, never published.
    """
    leaked = _entrant("small", billions=3.0, private=[Outcome.SOLVED])
    contaminated = Entrant(
        contender=leaked.contender,
        private=_sweep("small", [_rollout("small", "alpha", Outcome.SOLVED)]),
        public=leaked.public,
    )
    contract = dataclasses.replace(CONTRACT, dev_subset=("alpha",))

    with pytest.raises(ScoredDevSubset) as refusal:
        build_report(
            entrants=[contaminated],
            provenance=PROVENANCE,
            contract=contract,
            funnel=FUNNEL,
        )
    assert "alpha" in str(refusal.value), (
        f"WHY THIS IS A FAILURE: the refusal does not name the leaked stratum member. Got "
        f"{str(refusal.value)!r}"
    )


def test_probe_slices_the_stratum_filtered_set(tmp_path: Path) -> None:
    """`--probe N` samples the filtered set, not the whole corpus (run.py:551-552).

    A probe is a timing sample over the tasks that would be scored, which is the question it
    exists to answer — under a stratum, that means the stratum's tasks.
    """
    doc = _stratum(tmp_path / "doc", ("alpha", "gamma"))
    conducted = _run(tmp_path, stratum=doc, probe=1)

    assert conducted.report is None, (
        "WHY THIS IS A FAILURE: a probe published counts. D7's sample measures time and "
        "publishes no counts whatsoever"
    )
    assert conducted.costs[0].tasks == 1, (
        f"WHY THIS IS A FAILURE: the probe ran {conducted.costs[0].tasks} tasks rather than "
        "the declared sample of 1 over the stratum-filtered set"
    )
    assert (tmp_path / "out" / PROBE_FILE).exists()


def test_the_flag_parses_an_optional_path_and_defaults_to_none() -> None:
    """D1: absent means today's run; given, it is a path, never a string to guess at."""
    parsed = build_parser().parse_args(_minimum_cli())
    assert parsed.stratum is None, (
        f"WHY THIS IS A FAILURE: --stratum defaulted to {parsed.stratum!r}. A default path "
        "would consume a document nobody chose"
    )
    parsed = build_parser().parse_args([*_minimum_cli(), "--stratum", "/s/easier.json"])
    assert parsed.stratum == Path("/s/easier.json")


def test_main_forwards_the_stratum_flag_to_conduct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--stratum` at the door reaches `conduct(stratum=...)`, not a dead flag.

    A flag the parser accepts but `main` never forwards would parse cleanly and run the
    unscoped composition while the operator believed the run was restricted.
    """
    seen: dict[str, object] = {}

    def _recording_conduct(**kwargs: object) -> _FakeConducted:
        seen.update(kwargs)
        return _FakeConducted()

    monkeypatch.setattr(run_module, "conduct", _recording_conduct)

    code = main([*_minimum_cli(), "--stratum", "/stratum/easier.json"])

    assert code == 0, code
    assert seen["stratum"] == Path("/stratum/easier.json"), (
        f"WHY THIS IS A FAILURE: conduct received stratum={seen.get('stratum')!r}. A flag "
        "the door swallows is a run the operator believes was restricted while it was not"
    )


def test_a_stratum_refusal_is_reported_at_the_cli_as_a_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """At the CLI, a stratum refusal is a usage error: a non-zero exit, a message, no traceback.

    A traceback reads as a harness defect and invites a re-run of the same command; a usage
    error names the input that was wrong, which is the one thing the operator can fix.
    """
    def _refusing_conduct(**kwargs: object) -> _FakeConducted:
        raise UnknownStratumId(
            "the stratum's membership names 'ghost', which matches no loaded private task"
        )

    monkeypatch.setattr(run_module, "conduct", _refusing_conduct)

    with pytest.raises(SystemExit) as exit_code:
        main([*_minimum_cli(), "--stratum", "/stratum/easier.json"])

    assert exit_code.value.code != 0, (
        "WHY THIS IS A FAILURE: an invocation with a refused stratum document exited zero. "
        "The operator would read that as an accepted run"
    )
    assert "ghost" in capsys.readouterr().err, (
        "WHY THIS IS A FAILURE: the usage error does not name the refused input, so it reads "
        "as a harness crash rather than as something the operator can correct"
    )


def test_the_run_uses_aspect_ones_loader_and_filter_by_identity() -> None:
    """The diffcheck identity rule: imported, never copied — and asserted `is`.

    A second loader — or a second filter — is a second answer to "what may be selected",
    with only one of them reviewed. The run's seam is aspect 1's module, no other.
    """
    assert run_module.read_document is stratum.read_document, (
        "WHY THIS IS A FAILURE: the run does not consume aspect 1's loader. A copied loader "
        "is a second definition of the pinned input's checks, and the two would drift with "
        "only one of them reviewed"
    )
    assert run_module.include_stratum is stratum.include_stratum


# --------------------------------------------------------------------------------------------
# The adversarial proof (AC 9): doctored documents refused — watched failing against a
# deliberately credulous loader first, then held shut by the real loader (the diffcheck
# credulity precedent, `CONTRIBUTING.md:56-60`).
# --------------------------------------------------------------------------------------------


def _credulous(path: Path) -> tuple[str, ...]:
    """The loader without the checks: parse the JSON, trust the membership as spelled.

    This is the stand-in the doctored fixtures were **watched failing against** before the
    real checks existed: it reads the membership and nothing else — no schema, no digests,
    no id resolution — so a doctored document sails through it. It stays in the suite
    because the refusal assertions below are only load-bearing if the *checks*, not the
    fixtures' shape, are what refuses.
    """
    raw = json.loads(Path(path).read_text())
    return tuple(raw["membership"])


def test_a_doctored_document_is_refused_where_a_credulous_loader_would_trust_it(
    tmp_path: Path,
) -> None:
    """AC 9: a valid-looking document whose membership gained a declared dev id is refused.

    The doctored shape — membership edited to add `dev-b`, the `document_digest` **not**
    regenerated — is exactly what a smuggler would produce: every field type is right, the
    added id is a plausible member, and nothing about the file's shape is off. The credulous
    stand-in accepts it (proven in-line, so the refusal below is the checks' doing), and the
    real loader refuses rather than trusts, naming the document digest.
    """
    doc = _stratum(
        tmp_path / "doc", ("alpha", "gamma"), corpus=("alpha", "beta", "gamma", "dev-b")
    )
    raw = json.loads(doc.read_text())
    raw["membership"] = ["alpha", "gamma", "dev-b"]
    doc.write_text(json.dumps(raw))

    assert set(_credulous(doc)) == {"alpha", "gamma", "dev-b"}, (
        "the credulous stand-in did not actually accept the doctored membership, so the "
        "refusal assertions below would be proving something about the fixture instead of "
        "about the checks"
    )
    with pytest.raises(StratumDigestMismatch) as refusal:
        stratum.read_document(doc)
    message = str(refusal.value)
    assert "document" in message.lower(), (
        f"WHY THIS IS A FAILURE: the refusal does not name the document digest: {message!r}"
    )
    assert stratum.document_digest_of(raw) in message, (
        f"WHY THIS IS A FAILURE: the refusal does not show the expected digest, so the "
        f"tampering cannot be checked against the payload: {message!r}"
    )


def test_a_hand_edited_membership_is_refused_where_a_credulous_loader_would_trust_it(
    tmp_path: Path,
) -> None:
    """AC 9: a hand-edited membership in an otherwise valid document is refused, not trusted.

    The second doctored shape: the membership replaced with a different legitimate-looking
    selection (not merely extended), the digest left stale. The stand-in trusts it; the real
    loader refuses, naming the document digest and the expected value.
    """
    doc = _stratum(tmp_path / "doc", ("alpha", "gamma"))
    raw = json.loads(doc.read_text())
    raw["membership"] = ["gamma"]
    doc.write_text(json.dumps(raw))

    assert tuple(_credulous(doc)) == ("gamma",), (
        "the credulous stand-in did not accept the hand-edited membership, so the refusal "
        "assertion below proves nothing about the checks"
    )
    with pytest.raises(StratumDigestMismatch) as refusal:
        stratum.read_document(doc)
    message = str(refusal.value)
    assert "document" in message.lower(), (
        f"WHY THIS IS A FAILURE: the refusal does not name the document digest: {message!r}"
    )
    assert stratum.document_digest_of(raw) in message, (
        f"WHY THIS IS A FAILURE: the refusal does not show the expected digest: {message!r}"
    )


def test_the_checks_distinguish_tampering_from_regeneration_and_the_dev_member_is_excluded(
    tmp_path: Path,
) -> None:
    """The negative control + the dev-smuggle end-to-end (AC 9, D7).

    A **fully regenerated** doctored document — the digest recomputed through the module's
    own `document_digest_of`, so none of the loader's checks can fire — passes the run-side
    checks by construction; that is the layered defence's stated residual (spec Open question
    5: git history + ordering + aspect 1's recomputation test, stated, never reconciled).
    What the run itself does is then proven end-to-end: a dev id inside the membership never
    reaches scoring, because the dev overlay applies on top of the stratum (D7) — a dev
    member is excluded from the scored set and from both denominators, never refused (the
    real probe's declared ids may fall inside the band).
    """
    root = tmp_path / "arm"
    ids = ("alpha", "beta", "gamma", "dev-b")
    doc = _stratum(root / "doc", ("alpha", "beta", "dev-b"), corpus=ids)

    loaded = stratum.read_document(doc)
    assert "dev-b" in loaded.membership, (
        "the regenerated doctored document did not survive the loader, so the negative "
        "control did not control for anything"
    )

    conducted = _run(tmp_path, private=ids, stratum=doc, dev_subset=["dev-b"])

    assert "dev-b" not in conducted.scored, (
        f"WHY THIS IS A FAILURE: a dev id smuggled through the stratum reached the scored "
        f"set ({conducted.scored}). The overlay must apply on top of the stratum (D7), so "
        "the dev member is excluded even when the document claims it"
    )
    assert conducted.report is not None
    assert conducted.report.private[0].denominator == 2, (
        f"WHY THIS IS A FAILURE: the private denominator is "
        f"{conducted.report.private[0].denominator} rather than 2. The dev member is "
        "excluded from the denominator the report publishes"
    )
    assert conducted.report.public[0].denominator == 1
