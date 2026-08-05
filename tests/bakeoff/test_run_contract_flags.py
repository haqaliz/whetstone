"""`--max-tokens` and `--only`: changing the contract deliberately, and disclosing it.

The P1 bake-off ran at a 1024-token budget, and measuring the transcript afterwards showed the
budget was not a background detail: one candidate hit the cap on **every** rollout, so nothing it
produced was a finished answer. Testing that hypothesis needs the budget to be an input rather
than a constant compiled into the runtime.

**Both flags change what a number means, so both are refused rather than defaulted into
silence.** `max_tokens` is already a `GenerationContract` field, which is what makes this safe:
`PREREGISTRATION.md:356-361` requires every report publishing a governed figure to state its
generation contract, so threading the flag through means a run at a different budget *says so in
its own provenance block* instead of looking like the run before it.

`--only` narrows the matrix to named candidates. It exists because the cheapest decisive
experiment is often one base rather than three, and a report over one candidate must not be able
to masquerade as a bake-off — so the names it ran are recorded and an unmatched name is refused.
"""

from __future__ import annotations

import pytest

from whetstone.bakeoff.mlx_runtime import DEFAULT_MAX_TOKENS
from whetstone.bakeoff.run import UnknownCandidate, build_parser, select_candidates


class _Weights:
    """The one field selection reads. A stand-in, so this suite needs no multi-gigabyte fixture."""

    def __init__(self, repo_id: str) -> None:
        self.repo_id = repo_id


_FETCHED = (
    _Weights("mlx-community/Qwen2.5-Coder-3B-Instruct-4bit"),
    _Weights("mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"),
    _Weights("mlx-community/Qwen2.5-Coder-14B-Instruct-4bit"),
)


def test_the_budget_defaults_to_the_pinned_one_so_a_rerun_is_the_same_experiment() -> None:
    """Omitting the flag reproduces the recorded contract rather than inventing a new one."""
    parsed = build_parser().parse_args(_minimum())
    assert parsed.max_tokens == DEFAULT_MAX_TOKENS


def test_the_budget_is_settable_and_is_what_the_contract_will_record() -> None:
    """A run at a different budget is a different experiment, and the report has to say so."""
    parsed = build_parser().parse_args([*_minimum(), "--max-tokens", "2048"])
    assert parsed.max_tokens == 2048


@pytest.mark.parametrize("bad", ["0", "-1"])
def test_a_budget_that_could_not_produce_a_patch_is_refused(bad: str) -> None:
    """Zero tokens is a run in which every candidate fails for a reason about the harness.

    It would publish a clean-looking sweep of zeros that says nothing about any base, which is
    the vacuous shape this project refuses everywhere else.
    """
    with pytest.raises(SystemExit):
        build_parser().parse_args([*_minimum(), "--max-tokens", bad])


def test_without_only_every_fetched_candidate_is_scored() -> None:
    """The default is the whole matrix — narrowing is opt-in and visible in the command line."""
    assert select_candidates(_FETCHED, ()) == _FETCHED


def test_only_narrows_to_the_named_candidates_in_the_fetched_order() -> None:
    """Fetched order, not argument order, so two runs naming the same set agree on sequence."""
    chosen = select_candidates(_FETCHED, ("Qwen2.5-Coder-14B-Instruct-4bit",))
    assert [one.repo_id for one in chosen] == ["mlx-community/Qwen2.5-Coder-14B-Instruct-4bit"]


def test_a_substring_matches_so_the_full_repo_id_need_not_be_retyped() -> None:
    """Operator ergonomics, bounded: it still has to match something that was actually fetched."""
    assert [one.repo_id for one in select_candidates(_FETCHED, ("14B",))] == [
        "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit"
    ]


def test_a_name_matching_nothing_is_refused_rather_than_silently_scoring_nothing() -> None:
    """The failure this prevents is a run that scores an empty matrix and reports success.

    A typo would otherwise select no candidate, produce a report with no entrant, and read as a
    completed sweep — the same shape as `UnknownDevSubset`, which is refused for the same reason.
    """
    with pytest.raises(UnknownCandidate) as refusal:
        select_candidates(_FETCHED, ("Qwen3-Coder",))
    assert "Qwen3-Coder" in str(refusal.value)
    assert "14B" in str(refusal.value), "the refusal should name what WAS available"


def test_a_name_matching_several_is_refused_rather_than_guessing_which(
) -> None:
    """`Qwen2.5` matches all three. Scoring one of them would be a coin toss the report hides."""
    with pytest.raises(UnknownCandidate):
        select_candidates(_FETCHED, ("Qwen2.5-Coder",))


def _minimum() -> list[str]:
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
        "--recorded-on", "2026-08-05",
    ]
