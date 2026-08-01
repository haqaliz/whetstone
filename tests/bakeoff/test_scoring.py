"""One record per (candidate, task), and the three zeroes it has to keep apart.

The bake-off's plausible outcome is that every candidate base scores zero. That result is only
useful — only a *pivot signal* rather than a shrug — if the zero can be read. Three different
things produce it, they have three different fixes, and a record that collapses them makes an
honest all-zero indistinguishable from a harness that never ran:

1. **the base wrote no diff at all.** A prompt problem, or a base too small to emit a patch.
   Nothing was verified, because there was nothing to verify.
2. **the base wrote a diff that would not apply.** A *format* problem: the base understood the
   task well enough to produce a patch and got the context lines, paths or line numbers wrong.
3. **the base wrote a diff that applied and did not fix the bug.** A genuine capability result,
   and the only one of the three that is actually about the model's ability to fix bugs.

The failure this file exists to prevent is that all three arrive downstream as ``0``. Case 1 is
the sharpest: `verify_strict(task, "")` is charged FAIL at `patch-apply`, so handing the empty
string to the verifier when the extractor found nothing would turn *every* case-1 rollout into a
case-2 rollout — the harness inventing a model failure it never observed. So the assertion here
is not that the two records differ, it is that **the verifier is never called at all** when there
is no diff.

A fourth zero is worse than any of them: **the environment could not be built.** That is not a
result about the base, it is a result about the machine, and it must never be charged against a
candidate. `verify_weak` cannot help — measured, it charges a broken-but-executable interpreter
as FAIL rather than UNVERIFIED — so provisioning failure has to be classified *before* either
verifier is reached. Hence `Outcome.UNPROVISIONED`, and hence a test that asserts neither
verifier was entered.

**No model, no `mlx`, no network.** Every base here is `StubGenerator`, so what is under test is
the harness and nothing else; a real base would make a red result attributable to the model's
mood. Provisioning is exercised against a repository with no lockfile, which fails for the price
of one file read, and the caching claim is asserted by *counting calls* on an injected
provisioner rather than by timing two real `uv sync` runs.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest
from fixtures.repos import build_task, make_patch
from fixtures.repos.mined import MINED_CALC_BUGGY, MINED_CALC_FIXED, build_mined_task

from whetstone.bakeoff.generator import StubGenerator
from whetstone.bakeoff.rendering import render_prompt
from whetstone.bakeoff.scoring import Interpreters, Outcome, Rollout, score
from whetstone.bakeoff.sources import ORACLE_BUDGET_CHARS, oracle_sources
from whetstone.tasks.environment import NotProvisionable
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status

#: Generous enough that a fixture repository of one module and two pytest files can never reach
#: it, so an UNVERIFIED in this file always means something went wrong rather than something went
#: slowly. Named once because a timeout that differs per test is a variable nobody controls.
TIMEOUT = 120.0

#: What a base says when it has nothing to offer. Prose, no fence, no diff header — the shape
#: `extract_patch` reports as no-diff, and the input to case 1.
REFUSAL = "I could not work out what is wrong with this repository, so I have made no change."

#: A well-formed unified diff whose context lines describe a file that does not exist in the
#: checkout. The extractor accepts it — it *is* a diff — and `git apply` refuses it. That split
#: is the whole of case 2: shape without substance.
WRONG_CONTEXT = """\
```diff
--- a/calc.py
+++ b/calc.py
@@ -1,2 +1,2 @@
-def multiply(a, b):
-    return a * b
+def add(a, b):
+    return a + b
```
"""

#: The bug, re-broken a different way. Applies cleanly, and `add(2, 3)` still is not 5. Case 3:
#: a real attempt that a real test refuses.
STILL_BROKEN = "def add(a, b):\n    return a * b\n"

#: The held test file, rewritten so both declared node ids exist and assert nothing. A patch
#: carrying it is refused by the reward before anything runs and waved through by the naive
#: exit-status check — the disagreement `test_the_reward_and_the_control_are_both_recorded` is
#: about. Both node ids have to survive, or WEAK fails on a missing test rather than passing a
#: neutered one and the disagreement disappears for the wrong reason.
NEUTERED_TESTS = """\
def test_adding_zero_is_the_identity():
    assert True


def test_add_is_addition():
    assert True
"""


def posed(task: Task) -> str:
    """The prompt `score` will actually render for `task`, oracle sources and all.

    Every stub in this file is keyed on the exact prompt, so a test that rendered the sourceless
    prompt would hand the harness a table it cannot hit and fail with `UnstubbedPrompt` rather
    than with anything it meant to assert. This is also the assertion that the oracle is
    derivable at all for these fixtures.
    """
    sources = oracle_sources(task)
    assert sources.files is not None, sources.reason
    return render_prompt(task, sources.files)


def test_the_three_zeroes_are_told_apart(tmp_path: Path) -> None:
    """No diff, a diff that will not apply, and a diff that applies and fails: three records.

    All three are "not solved". Reported as one number they are the same number, and a bake-off
    whose every candidate scores zero would say nothing about *why* — which is the one question
    the P1 base decision turns on.
    """
    fixture = build_mined_task(tmp_path / "task")
    prompt = posed(fixture.task)
    applies_and_fails = make_patch(
        fixture.donor, {"calc.py": STILL_BROKEN}, at=fixture.parent
    )

    records = {
        name: score(
            candidate=name,
            task=fixture.task,
            generator=StubGenerator({prompt: answer}),
            sandbox_root=tmp_path / "runs" / name,
            timeout=TIMEOUT,
            interpreters=Interpreters(workspace=tmp_path / "envs"),
        )
        for name, answer in (
            ("wrote-nothing", REFUSAL),
            ("wrote-garbage", WRONG_CONTEXT),
            ("wrote-a-wrong-fix", applies_and_fails),
        )
    }

    outcomes = {name: record.outcome for name, record in records.items()}
    assert outcomes == {
        "wrote-nothing": Outcome.NO_DIFF,
        "wrote-garbage": Outcome.NOT_APPLIED,
        "wrote-a-wrong-fix": Outcome.NOT_SOLVED,
    }, (
        "WHY THIS IS A FAILURE: the three ways a candidate can score zero have collapsed into "
        f"fewer than three tags ({outcomes}). Downstream reads the tag, so a collapse here makes "
        "an honest all-zero bake-off indistinguishable from a harness that never applied a "
        "patch, and the P1 base decision would rest on a number nobody could interpret"
    )

    assert records["wrote-nothing"].strict is None, (
        "WHY THIS IS A FAILURE: no diff was produced, so no verifier ran, and a status here "
        "would be a verdict this harness invented rather than one the verifier returned"
    )
    assert records["wrote-garbage"].verdict_kinds == ("patch-apply",), (
        "WHY THIS IS A FAILURE: a diff that does not apply must be grounded in the verifier's "
        "own patch-apply sub-verdict; without the kinds recorded, NOT_APPLIED is this module's "
        f"assertion rather than the verifier's finding. Got "
        f"{records['wrote-garbage'].verdict_kinds!r}"
    )
    assert records["wrote-a-wrong-fix"].strict is Status.FAIL, (
        "WHY THIS IS A FAILURE: a patch that applied and left the declared test failing is the "
        "one zero of the three that is genuinely about the base's ability, and it has to carry "
        f"the verifier's own FAIL. Got {records['wrote-a-wrong-fix'].strict!r}"
    )


def test_a_solved_task_is_not_confused_with_a_failed_one(tmp_path: Path) -> None:
    """The control for the three zeroes: a correct patch still reaches SOLVED.

    Written because every other assertion in this file is about a record that is *not* a win,
    and a harness that tagged everything as a zero would satisfy all of them.
    """
    fixture = build_mined_task(tmp_path / "task")
    prompt = posed(fixture.task)
    correct = make_patch(fixture.donor, {"calc.py": MINED_CALC_FIXED}, at=fixture.parent)

    record = score(
        candidate="wrote-the-fix",
        task=fixture.task,
        generator=StubGenerator({prompt: correct}),
        sandbox_root=tmp_path / "runs",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert (record.outcome, record.strict) == (Outcome.SOLVED, Status.PASS), (
        "WHY THIS IS A FAILURE: the reference patch for this fixture makes the declared "
        "fail-to-pass test pass, so STRICT returns PASS. A harness that cannot record a win "
        f"would report every base as equally useless. Got {record.outcome!r}, {record.strict!r}"
    )


def test_a_missing_diff_never_reaches_the_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`extract_patch` returning `NoDiff` must not become `verify_strict(task, "")`.

    The empty string is charged FAIL at `patch-apply`, which is byte-for-byte the record case 2
    produces. Passing it would therefore not merely mislabel the rollout — it would erase the
    distinction this whole module exists to preserve, silently, with every guard still green.
    The assertion is on the *call*, not on the record, because a harness could produce the right
    tag while still having run a pointless sandboxed pytest for every no-diff rollout.
    """
    fixture = build_mined_task(tmp_path / "task")
    prompt = posed(fixture.task)

    calls: list[str] = []
    monkeypatch.setattr(
        "whetstone.bakeoff.scoring.verify_strict",
        lambda *args, **kwargs: calls.append("strict"),
    )
    monkeypatch.setattr(
        "whetstone.bakeoff.scoring.verify_weak",
        lambda *args, **kwargs: calls.append("weak"),
    )

    record = score(
        candidate="wrote-nothing",
        task=fixture.task,
        generator=StubGenerator({prompt: REFUSAL}),
        sandbox_root=tmp_path / "runs",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert calls == [], (
        "WHY THIS IS A FAILURE: a verifier was entered for a rollout that produced no diff, so "
        f"something was handed to it in place of the patch that does not exist ({calls}). If "
        "that something is the empty string, every no-diff rollout is recorded as a diff that "
        "would not apply, and the bake-off's most diagnostic distinction is gone"
    )
    assert record.outcome is Outcome.NO_DIFF
    assert record.detail, (
        "WHY THIS IS A FAILURE: `NoDiff` carries a reason naming what was seen instead of a "
        "diff — prose, an unrecognised fence, or nothing at all — which are a prompt problem, "
        "an extractor problem and a model problem with three different fixes. Dropping it "
        "leaves whoever reads a zero with no way to tell which"
    )


def test_an_unbuildable_environment_is_never_charged_to_the_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A donor that cannot be provisioned is a fact about the machine, not about the base.

    `verify_weak` is no help here and would actively mislead: measured, it charges a
    broken-but-executable interpreter as FAIL rather than UNVERIFIED, so a harness that let
    provisioning failures fall through to the verifiers would record them as the candidate
    getting the task wrong. Classification therefore has to happen first, and neither verifier
    may be entered.

    The base is a `StubGenerator` holding **no answers at all**, which is a stronger assertion
    than a spy: if the harness asks it anything, it raises `UnstubbedPrompt` and this test errors
    rather than quietly passing. Generating for a task that can never be verified is wasted model
    time, and on a 66-task overnight bake-off that is measured in hours.
    """
    fixture = build_task(tmp_path / "task", pins=("whetstone-fixture-dep==1.0.0",))
    calls: list[str] = []
    monkeypatch.setattr(
        "whetstone.bakeoff.scoring.verify_strict", lambda *a, **k: calls.append("strict")
    )
    monkeypatch.setattr(
        "whetstone.bakeoff.scoring.verify_weak", lambda *a, **k: calls.append("weak")
    )

    record = score(
        candidate="never-asked",
        task=fixture.task,
        generator=StubGenerator({}),
        sandbox_root=tmp_path / "runs",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert calls == [], (
        "WHY THIS IS A FAILURE: a verifier ran for a task whose environment was never built, so "
        f"whatever it reported was produced under the wrong interpreter ({calls}). WEAK in "
        "particular returns FAIL for an interpreter that starts and cannot import, which would "
        "record a machine problem as the candidate failing the task"
    )
    assert (record.outcome, record.strict, record.weak) == (
        Outcome.UNPROVISIONED,
        Status.UNVERIFIED,
        Status.UNVERIFIED,
    ), (
        "WHY THIS IS A FAILURE: an environment that could not be built has to fall to "
        "UNVERIFIED, which never counts as a win, under a tag that says it was the environment. "
        f"Got {record.outcome!r}, {record.strict!r}, {record.weak!r}"
    )
    assert record.generation_seconds == 0.0, (
        "WHY THIS IS A FAILURE: the base was asked for a patch to a task that could never be "
        "verified. One wasted generation is nothing; 66 tasks times every candidate, overnight, "
        "is the bake-off not finishing"
    )
    assert "uv.lock" in record.detail, (
        "WHY THIS IS A FAILURE: the record does not say why provisioning failed, so whoever "
        f"reads a run of UNPROVISIONED records cannot tell a missing lockfile from a resolver "
        f"error from a wrong interpreter. Got {record.detail!r}"
    )


def test_the_base_is_shown_the_source_it_is_asked_to_patch(tmp_path: Path) -> None:
    """The wiring, asserted on the string the base actually received.

    Everything else in this file could pass with `score` rendering the pre-oracle prompt: the
    stub table would still match, because the table is built from whatever the renderer produces.
    So this test looks at the prompt from the *base's* side and requires the checkout's own broken
    source to be in it. Without that, a unified diff is being asked for against a file the base
    has never seen — measured, that returns NOT_APPLIED on every rollout — and the bake-off would
    rank prompts rather than bases.
    """
    fixture = build_mined_task(tmp_path / "task")
    shown: list[str] = []

    class _Records:
        def generate(self, prompt: str) -> str:
            shown.append(prompt)
            return REFUSAL

    score(
        candidate="shown-the-code",
        task=fixture.task,
        generator=_Records(),
        sandbox_root=tmp_path / "runs",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert len(shown) == 1 and MINED_CALC_BUGGY in shown[0], (
        "WHY THIS IS A FAILURE: the prompt the base was actually handed does not contain the "
        "source of the file it must patch. A unified diff is written from a file's exact context "
        f"lines, so this asks the impossible and charges the answer as the base's error. Got "
        f"{shown!r}"
    )
    for path, contents in fixture.task.test_blobs.items():
        assert contents.decode("utf-8") not in shown[0], (
            f"WHY THIS IS A FAILURE: the operator-held test {path!r} reached the base's context "
            "window along with the source. That is the answer key: STRICT restores exactly those "
            "bytes and grades against them, so a patch special-casing the graded inputs passes "
            "genuinely and no re-execution downstream can tell it from a fix"
        )


def test_a_task_whose_oracle_cannot_be_derived_is_skipped_rather_than_scored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No source to show means no contract to pose, and a rollout that never happened.

    A public instance carries no donor commit, so nothing can say which files its fix touches.
    The tempting behaviour is to render the prompt anyway with no source in it — and that is the
    one thing that must not happen: the task would land in the same denominator as the oracle
    tasks while having been asked a different, impossible question, and nothing in the published
    counts would separate them.

    The base is a `StubGenerator` holding **no answers at all**, which is stronger than a spy: if
    the harness asks it anything it raises `UnstubbedPrompt` and this test errors rather than
    quietly passing.
    """
    fixture = build_task(tmp_path / "task")
    calls: list[str] = []
    monkeypatch.setattr(
        "whetstone.bakeoff.scoring.verify_strict", lambda *a, **k: calls.append("strict")
    )
    monkeypatch.setattr(
        "whetstone.bakeoff.scoring.verify_weak", lambda *a, **k: calls.append("weak")
    )

    record = score(
        candidate="never-asked",
        task=fixture.task,
        generator=StubGenerator({}),
        sandbox_root=tmp_path / "runs",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert (record.outcome, record.strict, record.weak) == (
        Outcome.NO_ORACLE,
        Status.UNVERIFIED,
        Status.UNVERIFIED,
    ), (
        "WHY THIS IS A FAILURE: a task the generation contract could not be built for was scored "
        "as though it had been. It has to fall to UNVERIFIED under a tag that says the contract "
        f"was the problem — UNVERIFIED never counts as a win. Got {record.outcome!r}, "
        f"{record.strict!r}, {record.weak!r}"
    )
    assert calls == [] and record.generation_seconds == 0.0, (
        f"WHY THIS IS A FAILURE: the harness generated or verified for a task it could not pose "
        f"({calls}). Whatever came back is an answer to a question this contract does not define"
    )
    assert record.prompt_sha256 == "", (
        "WHY THIS IS A FAILURE: a prompt digest was recorded for a rollout where no prompt was "
        f"ever rendered, so the provenance names a question nobody was asked. Got "
        f"{record.prompt_sha256!r}"
    )
    assert record.detail, (
        "WHY THIS IS A FAILURE: the skip carries no reason, so an operator reading a corpus of "
        "them cannot tell an absent donor from a held-path collision from an oversized file"
    )


def test_an_over_budget_oracle_is_skipped_rather_than_silently_truncated(tmp_path: Path) -> None:
    """A file too large to show makes the task unposable, not the prompt shorter.

    Truncation is the silent version of the same failure: the base is shown part of a file, writes
    context lines from the part it got, and is charged NOT_APPLIED for it. That rollout ran a
    different experiment from every other one in its denominator, and nothing would record which.
    """
    fixture = build_mined_task(tmp_path / "task", bulk_chars=ORACLE_BUDGET_CHARS + 1_000)

    record = score(
        candidate="never-asked",
        task=fixture.task,
        generator=StubGenerator({}),
        sandbox_root=tmp_path / "runs",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert record.outcome is Outcome.NO_ORACLE, (
        f"WHY THIS IS A FAILURE: an over-budget task was scored. Either its prompt was truncated "
        f"— a different experiment — or it overran the context window, where what the base saw "
        f"was decided by a tokenizer nobody recorded. Got {record.outcome!r}"
    )
    assert str(ORACLE_BUDGET_CHARS) in record.detail, (
        f"WHY THIS IS A FAILURE: the record does not name the budget that refused it, so an "
        f"operator cannot judge whether the limit is wrong for their repository. Got "
        f"{record.detail!r}"
    )


#: A pin set. The versions are never resolved in this file — the provisioner is injected — but
#: they have to be *exact* `==` requirements or the manifest loader refuses them.
PINS = ("whetstone-fixture-dep==1.0.0",)

#: A second, different pin set. Its whole job is to prove the cache is keyed on the pins rather
#: than being a "build one environment ever" bug that the first assertion could not tell apart.
OTHER_PINS = ("whetstone-fixture-dep==2.0.0",)


class CountingProvisioner:
    """A `Provision` that records every call and hands back this process's own interpreter.

    Returning `sys.executable` rather than a fabricated path keeps the substitution honest: a
    fake path would make every rollout scored through it UNVERIFIED for a reason that has
    nothing to do with what is being asserted.
    """

    def __init__(self, *, fails: bool = False) -> None:
        self.calls: list[str] = []
        self.fails = fails

    def __call__(self, task: Task, into: Path) -> Path:
        self.calls.append(task.task_id)
        if self.fails:
            raise NotProvisionable("this donor carries no uv.lock")
        return Path(sys.executable)


def test_tasks_sharing_a_pin_set_are_provisioned_once(tmp_path: Path) -> None:
    """Two tasks, one environment. The cache is keyed on the pins, not on the manifest.

    Source B's 66 tasks were mined from two donors, so the manifests vastly outnumber the
    distinct environments behind them. Provisioning per task would build 66 venvs where a
    handful are needed — per candidate — which is the difference between a bake-off that
    finishes overnight and one that does not.

    The third task exists to keep the assertion from being satisfied by the wrong bug: a cache
    that built exactly one environment and reused it for everything would also report one call
    for the first two tasks, and would be verifying half the corpus against the wrong pins.
    """
    shared_one = build_task(tmp_path / "one", task_id="shared-one", pins=PINS)
    shared_two = build_task(tmp_path / "two", task_id="shared-two", pins=PINS)
    different = build_task(tmp_path / "three", task_id="different", pins=OTHER_PINS)

    provisioner = CountingProvisioner()
    interpreters = Interpreters(workspace=tmp_path / "envs", provision=provisioner)
    acquired = [
        interpreters.acquire(fixture.task)
        for fixture in (shared_one, shared_two, different, shared_one)
    ]

    assert len(provisioner.calls) == 2, (
        "WHY THIS IS A FAILURE: four acquisitions over two distinct pin sets built "
        f"{len(provisioner.calls)} environments ({provisioner.calls}). More than two means the "
        "cache is keyed on something that is not the pin set, and a bake-off would spend its "
        "night running `uv sync` once per manifest per candidate; fewer means two different "
        "pin sets were served one environment, and half the corpus was verified against "
        "dependencies its manifest never declared"
    )
    assert acquired[0].interpreter == acquired[1].interpreter, (
        "WHY THIS IS A FAILURE: two tasks declaring the same pins were handed different "
        "interpreters, so the environment a verdict was produced under depends on which "
        "manifest asked for it rather than on what the manifest declared"
    )
    assert acquired[2].interpreter is not None and acquired[2].failure is None


def test_an_environment_that_cannot_be_built_is_not_rebuilt(tmp_path: Path) -> None:
    """A donor that cannot be provisioned cannot be provisioned 66 times either.

    Caching only the successes would leave the worst case — a whole donor that is unbuildable on
    this machine — retrying the same failure once per task, which is the slowest possible way to
    learn a fact that was available after the first attempt.
    """
    first = build_task(tmp_path / "one", task_id="first", pins=PINS)
    second = build_task(tmp_path / "two", task_id="second", pins=PINS)

    provisioner = CountingProvisioner(fails=True)
    interpreters = Interpreters(workspace=tmp_path / "envs", provision=provisioner)
    failures = [interpreters.acquire(fixture.task).failure for fixture in (first, second)]

    assert len(provisioner.calls) == 1, (
        "WHY THIS IS A FAILURE: a failed provisioning was attempted again for the next task "
        f"declaring the same pins ({provisioner.calls}). Across one unbuildable donor that is "
        "the same failure discovered once per task"
    )
    assert all(failure is not None for failure in failures), (
        "WHY THIS IS A FAILURE: the cached failure was not reported to the second task, so a "
        "rollout would proceed to the verifiers with no environment behind it"
    )


def test_a_task_declaring_no_pins_provisions_nothing(tmp_path: Path) -> None:
    """`pins: []` is a positive claim — nothing is installed — and the honest response is nothing.

    Building a venv anyway would be a `uv` invocation per task for a task family that declared
    it needed none, and it would make the empty pin set indistinguishable from an absent
    `environment`, which is a distinction the manifest loader exists to draw.
    """
    fixture = build_task(tmp_path / "task")
    provisioner = CountingProvisioner()
    interpreters = Interpreters(workspace=tmp_path / "envs", provision=provisioner)

    acquired = interpreters.acquire(fixture.task)

    assert provisioner.calls == [], (
        "WHY THIS IS A FAILURE: an environment was built for a task that declared no "
        f"dependencies ({provisioner.calls})"
    )
    assert (acquired.interpreter, acquired.failure) == (None, None), (
        "WHY THIS IS A FAILURE: declaring no pins is not a provisioning failure. Recording it "
        f"as one would tag every such rollout UNPROVISIONED and verify nothing. Got {acquired!r}"
    )


def test_the_reward_and_the_control_are_both_recorded(tmp_path: Path) -> None:
    """STRICT and WEAK on the same rollout, and the case where they disagree.

    Recording only STRICT would make the caught-hack count underivable, and the gap between the
    two *is* the measurement: this patch neuters the operator-held test, so the naive
    exit-status check calls it a pass and the reward refuses it before anything ran. A harness
    that stored one status per rollout could not tell that story at all.
    """
    fixture = build_mined_task(tmp_path / "task")
    prompt = posed(fixture.task)
    neutered = make_patch(
        fixture.donor, {"tests/test_addition.py": NEUTERED_TESTS}, at=fixture.parent
    )

    record = score(
        candidate="edited-the-test",
        task=fixture.task,
        generator=StubGenerator({prompt: neutered}),
        sandbox_root=tmp_path / "runs",
        timeout=TIMEOUT,
        interpreters=Interpreters(workspace=tmp_path / "envs"),
    )

    assert (record.outcome, record.strict, record.weak) == (
        Outcome.OUT_OF_SCOPE,
        Status.FAIL,
        Status.PASS,
    ), (
        "WHY THIS IS A FAILURE: a patch that rewrote the operator-held test has to be refused "
        "by the reward and accepted by the naive check — that disagreement is what the "
        "execution-grounded reward is for, and both halves of it must survive into the record "
        f"for the caught-hack count to be derivable. Got {record.outcome!r}, {record.strict!r}, "
        f"{record.weak!r}"
    )


def test_timing_is_recorded_and_stays_out_of_the_verdict(tmp_path: Path) -> None:
    """Three separate clocks, and none of them may reach anything the outcome depends on.

    Separate because a base that is slow to generate and a task that is slow to verify are
    different problems, and one total would hide which of them an overnight run was spent on.
    Out of the verdict because the bake-off's comparison between bases has to be reproducible:
    if a duration were part of what a record compares as, two identical runs would differ and
    "the same candidate on the same task gives the same result" could not be asserted at all.
    """
    fixture = build_mined_task(tmp_path / "task")
    prompt = posed(fixture.task)
    correct = make_patch(fixture.donor, {"calc.py": MINED_CALC_FIXED}, at=fixture.parent)

    def run() -> Rollout:
        return score(
            candidate="wrote-the-fix",
            task=fixture.task,
            generator=StubGenerator({prompt: correct}),
            sandbox_root=tmp_path / "runs",
            timeout=TIMEOUT,
            interpreters=Interpreters(workspace=tmp_path / "envs"),
        )

    first, second = run(), run()

    durations = {
        "generation": first.generation_seconds,
        "strict": first.strict_seconds,
        "weak": first.weak_seconds,
    }
    assert all(value >= 0.0 for value in durations.values()), (
        f"WHY THIS IS A FAILURE: a wall-clock duration came back negative ({durations}), which "
        "means it was not measured with a monotonic clock and would go backwards whenever the "
        "system clock was adjusted mid-run"
    )
    assert durations["strict"] > 0.0 and durations["weak"] > 0.0, (
        f"WHY THIS IS A FAILURE: a verifier that provably ran reported no elapsed time "
        f"({durations}), so the field is a constant rather than a measurement and an overnight "
        "run could not be attributed to anything"
    )

    untimed = {"generation_seconds": 0.0, "strict_seconds": 0.0, "weak_seconds": 0.0}
    assert dataclasses.replace(first, **untimed) == dataclasses.replace(second, **untimed), (
        "WHY THIS IS A FAILURE: the same candidate, the same task and the same patch produced "
        "two different records once the clocks are set aside. A bake-off whose result moves "
        f"between runs cannot settle which base to start from.\n{first}\n{second}"
    )
