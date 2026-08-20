"""The seeded draw: `k` attempts, each seeded from three declared things and nothing else.

The determinism criterion (`docs/ROADMAP.md:402`) rests entirely on this module, and it has one
failure mode that would satisfy every casual reading of the code: a derivation built on Python's
builtin `hash`, which is **salted per process**. A night built on it would produce a different
dataset on every invocation while every line of it read as deterministic, the ledger would record
seeds that could not be recomputed, and the byte-identity test would fail with nothing in the code
looking wrong. So the first assertion here is a cross-process one.

The other three properties, and why each is worth a test rather than a comment:

* **`K` is a declared constant that the loop actually uses.** A `k` that lived in a flag would be
  a knob an operator turns after seeing a disappointing yield — optimising on the run's own scored
  outcome, which is M7b's discipline applied to the sampling budget.
* **`k = 1` decodes greedily, through the bake-off's own function.** Not "a greedy sampler": *the*
  one, asserted `is`, so a single-draw night and the bake-off are the same experiment rather than
  two that look alike.
* **A prompt the frozen contract does not carry is passed down unseeded and unrecorded.** That is
  what lets `Sealed` raise `ContractChanged` while the seed record stays a record of draws that
  actually happened.

No `mlx`: the seeder is injected, which is the whole reason it is a parameter.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from whetstone.bakeoff.mlx_runtime import greedy_sampler
from whetstone.loop import draws as loop_draws
from whetstone.loop import night as loop_night
from whetstone.loop.sampling import (
    SAMPLER,
    Applied,
    Draw,
    K,
    attempt_seed,
    sampler_for,
)


class _Echo:
    """A base that answers with the prompt it was given. Enough to observe ordering."""

    def generate(self, prompt: str) -> str:
        return prompt


def _contract(prompts: dict[str, str]) -> dict[str, str]:
    """A frozen `posed` map, keyed the way the run's own freeze keys it."""
    from whetstone.bakeoff.rendering import prompt_hash

    return {prompt_hash(prompt): task_id for prompt, task_id in prompts.items()}


def test_the_seed_derivation_is_stable_across_processes() -> None:
    """The one that catches `hash`: the same three inputs give the same seed in a fresh process.

    Run in a subprocess with a **different** `PYTHONHASHSEED`, because that is precisely the
    variable the builtin's salt is read from. A derivation using `hash("task-id")` passes every
    in-process assertion in this file and fails only here — and in production it fails silently,
    as a training set that cannot be reproduced.
    """
    here = attempt_seed(11, "alpha", 3)
    elsewhere = subprocess.run(
        [
            sys.executable,
            "-c",
            "from whetstone.loop.sampling import attempt_seed; print(attempt_seed(11, 'alpha', 3))",
        ],
        capture_output=True,
        text=True,
        check=True,
        env={"PYTHONHASHSEED": "12345", "PATH": "/usr/bin:/bin", "PYTHONPATH": _src()},
    )
    assert int(elsewhere.stdout.strip()) == here, (
        "WHY THIS IS A FAILURE: the same (run_seed, task_id, attempt) produced two different "
        "seeds in two processes, which means the derivation reads process-salted state — the "
        "builtin `hash` is the way this happens. The determinism criterion would then be a "
        "statement about PYTHONHASHSEED, and the seeds recorded in the ledger would be "
        f"unrecomputable. Here {here}, elsewhere {elsewhere.stdout.strip()!r}"
    )


def test_the_seed_depends_on_all_three_declared_inputs() -> None:
    """Change any one of the three and the seed moves — otherwise draws collide silently.

    A derivation that ignored `attempt` would give every draw of a task the same seed, so `k`
    draws would be `k` copies of one answer and rejection sampling would select nothing while
    reporting `k` rollouts.
    """
    base = attempt_seed(1, "alpha", 1)
    assert attempt_seed(2, "alpha", 1) != base, "the run seed does not reach the derivation"
    assert attempt_seed(1, "beta", 1) != base, "the task id does not reach the derivation"
    assert attempt_seed(1, "alpha", 2) != base, (
        "WHY THIS IS A FAILURE: the attempt index does not reach the derivation, so every draw "
        "of a task is seeded identically. k identical draws are one answer repeated"
    )
    assert attempt_seed(1, "a", 11) != attempt_seed(1, "a1", 1), (
        "WHY THIS IS A FAILURE: two different (task, attempt) pairs collide onto one seed, which "
        "means the fields are concatenated without a separator"
    )


def test_a_zeroth_attempt_is_refused() -> None:
    """One-based, because the ledger's attempt field is what a reader recomputes a seed from."""
    with pytest.raises(ValueError, match="one-based"):
        attempt_seed(1, "alpha", 0)


def test_a_draw_seeds_before_it_asks_and_records_what_it_applied() -> None:
    """The order is the guarantee: seed, then generate. Observed, not asserted about.

    A wrapper that seeded *after* delegating would draw from whatever state the previous task
    left behind, which is deterministic in a single serial run and not reproducible from the
    ledger — the worst combination, because it passes a same-process byte-identity test.
    """
    prompt = "fix the adder"
    events: list[str] = []

    class _Watching:
        def generate(self, text: str) -> str:
            events.append("generate")
            return text

    draw = Draw(
        inner=_Watching(),
        contract=_contract({prompt: "alpha"}),
        run_seed=7,
        attempt=2,
        seeder=lambda seed: events.append(f"seed:{seed}"),
    )
    draw.generate(prompt)

    assert events == [f"seed:{attempt_seed(7, 'alpha', 2)}", "generate"], (
        "WHY THIS IS A FAILURE: the seed was not applied immediately before the draw. mlx-lm "
        "samples from process-global mx.random state, so a seed applied late — or not at all — "
        f"means the draw came from whatever the previous one left behind. Got {events!r}"
    )
    assert draw.applied == [Applied(task_id="alpha", attempt=2, seed=attempt_seed(7, "alpha", 2))]


def test_a_prompt_the_contract_does_not_carry_is_passed_down_unseeded(tmp_path: Path) -> None:
    """The composition's point, not a gap: a drifted prompt must reach `Sealed` to be refused.

    `Draw` sits outside the seal. If it seeded and recorded an unfrozen prompt, the run would
    hold an `Applied` record for a generation the seal then aborted — evidence of a draw that
    never happened, in the one file whose purpose is to say what was drawn.
    """
    applied: list[int] = []
    draw = Draw(
        inner=_Echo(),
        contract=_contract({"frozen": "alpha"}),
        run_seed=7,
        attempt=1,
        seeder=applied.append,
    )
    assert draw.generate("a prompt nobody froze") == "a prompt nobody froze"
    assert applied == [] and draw.applied == [], (
        "WHY THIS IS A FAILURE: an unfrozen prompt was seeded and recorded. The seal refuses it "
        f"one layer down, so this record would describe a draw that never happened. Got {applied!r}"
    )


def test_a_single_draw_decodes_with_the_bakeoffs_own_greedy_sampler() -> None:
    """`is`, not "equivalent": a k=1 night and the bake-off must be one experiment.

    A reimplemented argmax would be a second decoding rule that nothing compares against the
    first, and the difference would show up as an unexplained divergence between two runs that
    every document described as the same.
    """
    assert sampler_for(1) is greedy_sampler, (
        "WHY THIS IS A FAILURE: a single-draw night does not decode through "
        "mlx_runtime.greedy_sampler. Then the loop's k=1 and the bake-off's one greedy attempt "
        "are two decoding rules that look alike, and nothing in either report would disclose it"
    )


def test_a_night_of_no_draws_is_refused_rather_than_run() -> None:
    """Zero draws asks nothing and would report an empty dataset as a measured outcome."""
    with pytest.raises(ValueError, match="at least one draw"):
        sampler_for(0)
    with pytest.raises(ValueError, match="at least one draw"):
        loop_draws.sample(
            candidate="x",
            sources={},
            engine=_Echo(),
            contract=loop_draws.Contract(sha256="", posed={}),  # type: ignore[attr-defined]
            run_seed=1,
            draws=0,
            evidence=Path("."),
            sandbox_root=Path("."),
            timeout=1.0,
            interpreters=None,  # type: ignore[arg-type]
        )


def test_k_is_a_declared_constant_and_the_night_uses_it() -> None:
    """`K` is not a flag, and the door must not offer one.

    Two halves. The constant exists and is a small positive integer, and the night's own default
    **is that constant** — asserted through the function's signature, so a later refactor that
    quietly defaulted the door to 1 (or read a `--k` flag) fails here rather than in a night
    whose ledger says one thing and whose draws say another.
    """
    import inspect

    assert isinstance(K, int) and K >= 2, (
        f"WHY THIS IS A FAILURE: K is {K!r}. Rejection sampling needs more than one draw per "
        "task; at k=1 there is nothing to reject and the loop is the bake-off"
    )
    default = inspect.signature(loop_night.run_night).parameters["draws"].default
    assert default is K, (
        "WHY THIS IS A FAILURE: the night's draw count does not default to the declared constant "
        f"K ({K}); it defaults to {default!r}. A per-run k is a knob an operator turns after "
        "seeing a disappointing yield, which is optimising on the run's own scored outcome"
    )
    assert "--k" not in _cli_flags(), (
        "WHY THIS IS A FAILURE: the night door offers a --k flag. Raising k is the roadmap's "
        "named response to a low yield — as an edit to the constant, in a diff, before a night, "
        "never as an argument on a command that has already run once"
    )


def test_the_sampler_is_described_for_a_reader_who_will_not_open_the_file() -> None:
    """The published decoding rule names its parameters, because "sampled" alone is a word."""
    assert "temperature" in SAMPLER and "top-p" in SAMPLER and "seed" in SAMPLER, SAMPLER


def _cli_flags() -> set[str]:
    """Every option string the `run` subcommand accepts, read from the parser that ships."""
    import argparse

    from whetstone.cli import build_parser

    parser = build_parser()
    subparsers = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    night = subparsers[0].choices["run"]
    return {option for action in night._actions for option in action.option_strings}


def _src() -> str:
    """The importable `src/` of this checkout, for the cross-process assertion above."""
    return str(Path(__file__).resolve().parents[2] / "src")
