"""The miner's skip-set: a commit already in the corpus is never attempted again.

The night re-mines the user's own donors before it draws, and the whole reason that is cheap is
incrementality: a candidate whose trailing-12-hex sha is already in the corpus the night will draw
from must not be re-provisioned and re-derived. Without this filter a second night over the same
donor would pay hours of sandboxed pytest for tasks it already has, and — worse — could mint the
same task twice under the same id.

**The default is the contract.** An empty skip-set must leave `select` and `mine` byte-identical
to the tree before this parameter existed, so the operator-invoked `whetstone mine` path and its
tests (`tests/test_mine_cli.py`, unedited) are unaffected. The tests below assert both directions:
non-empty skips a candidate, empty changes nothing.
"""

from __future__ import annotations

from pathlib import Path

from fixtures.repos.donor import build_donor

from whetstone.tasks.donor import Candidate, candidates
from whetstone.tasks.mine import LEDGER_NAME, MintReport, mine, select


def _pool() -> list[Candidate]:
    """The `tests/test_mine_cli.py` pool shape, with distinct leading-12 shas.

    That suite's pool uses ``f"{index:040x}"``, whose leading twelve hex are all zero for every
    small index — fine for the ordering assertions it makes, useless here. The skip key is
    ``sha[:12]`` (`_ID_SHA_LENGTH`), so this pool puts the index in the leading twelve and pads
    the rest, and every candidate then has a sha12 the filter can tell apart.
    """
    return [
        Candidate(
            sha=f"{index:012x}" + "0" * 28,
            parent=f"{index - 1:040x}",
            subject=f"commit {index}",
            held_tests=("tests/test_x.py",),
            source_paths=("x.py",),
            other_paths=(),
        )
        for index in range(1, 12)
    ]


def test_select_skips_a_candidate_by_its_trailing_twelve_hex() -> None:
    """A sha12 in the skip-set is filtered out of the draw; the rest are untouched.

    The identity a corpus is keyed by is the trailing twelve hex of a task id (`label-sha12`,
    `mine._mint`), and this is the same key: the candidate's own commit sha, never the donor's
    directory name or the label.
    """
    pool = _pool()
    skipped = pool[4]
    skipped_sha12 = skipped.sha[:12]

    drawn = select(pool, limit=5, skip={skipped_sha12})

    assert [candidate.sha for candidate in drawn] == [
        candidate.sha for candidate in pool if candidate.sha != skipped.sha
    ], "the skip-set removed a candidate other than the one whose sha12 it named"
    assert select(pool, limit=5, skip=frozenset()) == select(pool, limit=5), (
        "an empty skip-set changed the selection, so the default path is not byte-identical to "
        "the tree before the parameter existed"
    )


def test_select_skip_is_order_and_seed_independent() -> None:
    """The filter applies after the sort-and-shuffle, so a seeded draw excludes the same sha.

    `select` sorts by sha before it shuffles precisely so the draw depends on the seed and nothing
    else. The skip-set is a filter on that deterministic order, so the seeded and unseeded draws
    must omit the same candidate.
    """
    pool = _pool()
    skipped_sha12 = pool[2].sha[:12]

    unseeded = {candidate.sha for candidate in select(pool, limit=5, skip={skipped_sha12})}
    seeded = {
        candidate.sha for candidate in select(pool, limit=5, seed=7, skip={skipped_sha12})
    }
    expected = {candidate.sha for candidate in pool if candidate.sha[:12] != skipped_sha12}

    assert skipped_sha12 not in {sha[:12] for sha in seeded}, (
        "a seeded draw re-admitted a skipped sha"
    )
    assert unseeded == seeded == expected


def test_mine_with_every_candidate_skipped_mints_nothing_and_writes_nothing(tmp_path: Path) -> None:
    """Every candidate already in the corpus: the mint short-circuits, and writes no evidence.

    The skip is checked before `_mint`'s provisioning, so a donor whose whole history is already
    minted costs nothing and — crucially — writes no ledger. A mint that wrote a ledger recording
    no new tasks would make a re-mine that changed nothing look like it changed the corpus.
    """
    donor = build_donor(tmp_path)
    out = tmp_path / "out"
    skip = {candidate.sha[:12] for candidate in candidates(donor)}

    report = mine(
        donor,
        out,
        label="donor-x",
        limit=5,
        scratch=tmp_path / "scratch",
        tasks_root=tmp_path / "tasks",
        timeout=60.0,
        skip=skip,
    )

    assert report == MintReport(minted=(), rejected=(), ledger=None, recipe=None), report
    assert list(out.glob("*.json")) == [], "a fully-skipped mint still wrote manifests"
    assert not (tmp_path / "tasks" / LEDGER_NAME).exists(), "a fully-skipped mint wrote a ledger"


def test_mine_default_skip_is_the_current_behaviour(tmp_path: Path) -> None:
    """No skip-set: the donor's candidates are attempted and rejected, exactly as before.

    Test 3's donor has no lockfile, so every candidate is refused `NotProvisionable` — which is
    what makes this the default-empty contract: the candidates were *attempted*, and the mint
    reported the shortfall rather than silently skipping everything.
    """
    donor = build_donor(tmp_path)

    report = mine(
        donor,
        tmp_path / "out",
        label="donor-x",
        limit=5,
        scratch=tmp_path / "scratch",
        tasks_root=tmp_path / "tasks",
        timeout=60.0,
    )

    assert report.minted == (), (
        "the unprovisionable donor minted a task, so this fixture no longer exercises the "
        "default-empty path"
    )
    assert report.rejected, "no candidate was attempted, so the default is not the old behaviour"
