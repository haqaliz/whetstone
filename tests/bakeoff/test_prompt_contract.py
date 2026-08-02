"""Pins what a base model is shown — and, far more importantly, what it is never shown.

The failure this file exists to prevent is **handing the policy the answer key**.

``task.test_blobs`` is the operator's artifact and the whole provenance boundary
(``src/whetstone/verify/task.py``): STRICT restores every one of those files from golden
*after* the patch is applied and grades against them, and refuses outright a patch that touches
one of their paths (``strict.py`` step 2, ``_refused``). A prompt that quoted their contents
would put the exact assertions the reward is computed from into the policy's context — which is
cheat 6, *special-casing the known input* (``docs/ROADMAP.md`` § 3), handed over pre-solved. It
is the one catalogued residual that no execution-grounded check can catch, because a patch that
returns the graded answer for the graded inputs genuinely makes the graded tests pass. The
sandbox is no help: ``file-read*`` is allowed wholesale (``sandbox.py:12-18``) and the verifier's
guarantee is "the unmodified operator tests genuinely passed", never "the policy never saw
them". Precisely because the policy is *not* read-blind, the prompt must not make the cheat
cheaper still — and "the prompt does not leak the held tests" is a claim about a string, which
is a claim a test can hold shut. So it does, here, rather than in a code comment.

**Node ids are a deliberate exception and not a leak.** ``fail_to_pass`` is what the task *asks*
the policy to fix, so it is in the contract by construction, and a node id names a test without
revealing its body: ``tests/test_addition.py::test_add_is_addition`` says which assertion set
must go green and nothing about what those assertions are. That distinction is why the
leak-check below cannot be a naive "no substring of any blob appears in the prompt" — the
function *name* legitimately appears in both. It is asserted on the blob's revealing lines
instead, and on the decoded blob as a whole.

**Second failure: a hash that is not stable, or not a hash.** The rendered contract is hashed
into the bake-off's provenance (PRD M8) and that hash is what makes the anti-tuning rule M7b
enforceable — *any change to the generation contract after the first scored run invalidates that
run and restarts it*. A hash that drifts between processes would invalidate honest runs; a hash
that never changes would let the contract be quietly edited mid-bake-off with the provenance
block still reading identical. Both directions are therefore asserted, and the cross-process arm
runs under **four fixed ``PYTHONHASHSEED`` values plus this process's random one**: set iteration
over strings is seed-dependent, ``sandbox.py`` pins ``PYTHONHASHSEED=0`` for the *reward* — and
this renderer runs outside the sandbox, so it inherits no such pin. Each subprocess proves the
seeds really did differ before the test concludes anything from their hashes agreeing. Why four
and not two is recorded in that test's own docstring, and it was measured rather than guessed.

**Third failure: a renderer that renders nothing.** ``return ""`` satisfies every determinism
and every leak assertion in this file perfectly. The anti-vacuity tests assert the problem
statement and each declared node id are actually *present*, so determinism here is a statement
about a prompt rather than about the empty string.

Everything runs with no ``mlx`` installed and touches no model: this phase is a string and a
digest.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
from fixtures.repos import RepoSpec, build_task

from whetstone.bakeoff.rendering import (
    EmptySources,
    HeldTestInSources,
    prompt_hash,
    render_prompt,
)
from whetstone.verify.task import load_task

#: A held test written so that every line of its *body* is unmistakable if it ever surfaces in a
#: rendered prompt. The sentinel comment and the literal assertions below it are the answer key:
#: a policy shown these does not need to fix ``add`` at all, it needs an ``if`` — which is cheat
#: 6, and no re-execution can tell that patch from a correct one.
HELD_TEST_SOURCE = """\
from calc import add


def test_add_is_addition():
    # ANSWER-KEY-SENTINEL: the exact inputs the operator grades against
    assert add(2, 3) == 5


def test_add_handles_negatives():
    assert add(-7, 11) == 4


def test_add_is_commutative():
    assert add(9, 6) == add(6, 9)


def test_add_of_two_zeroes():
    assert add(0, 0) == 0
"""

#: The lines above that would each, on their own, constitute a leak. Asserted absent from the
#: prompt one by one as well as via the whole decoded blob, because a renderer that emitted a
#: *summary* of the held tests would defeat a whole-blob check while leaking just as much.
REVEALING_LINES = (
    "ANSWER-KEY-SENTINEL",
    "assert add(2, 3) == 5",
    "assert add(-7, 11) == 4",
    "assert add(9, 6) == add(6, 9)",
)

#: A repository whose held test carries the sentinel above. Deliberately a normal task in every
#: other respect — the leak question is about the renderer, not about an exotic manifest.
#:
#: **Four declared node ids, and the count is load-bearing.** With one, a renderer that emitted
#: its sections out of a `set` would be trivially order-stable and the cross-process arm below
#: would report green against the very defect it was written to catch. Four leaves a
#: seed-dependent ordering one chance in 24 of coinciding, which is watched-failing evidence
#: rather than a coin toss.
SENTINEL_REPO = RepoSpec(
    files={
        "calc.py": "def add(a, b):\n    return a - b\n",
        "tests/test_addition.py": HELD_TEST_SOURCE,
    },
    fail_to_pass=(
        "tests/test_addition.py::test_add_is_addition",
        "tests/test_addition.py::test_add_handles_negatives",
        "tests/test_addition.py::test_add_is_commutative",
        "tests/test_addition.py::test_add_of_two_zeroes",
    ),
    pass_to_pass=(),
    held=("tests/test_addition.py",),
    problem_statement="add() subtracts instead of adding.",
)

#: What the oracle setting shows: the **non-test** file the fix touches, as it stands at
#: `base_commit` — i.e. still broken. `calc.py` and never `tests/test_addition.py`, which is the
#: whole distinction this file polices now that file contents are deliberately in the prompt.
ORACLE_SOURCES = {"calc.py": SENTINEL_REPO.files["calc.py"]}

#: A source map that offers an operator-held path. Nothing in the shipped derivation produces one
#: — `sources.oracle_sources` removes test paths and pre-flights against `test_blobs` — so this is
#: the map a *future* caller assembles by hand, or by a derivation that stops classifying
#: correctly. The renderer is the last place that mistake can be refused.
HELD_PATH_SOURCES = {"calc.py": SENTINEL_REPO.files["calc.py"], "tests/test_addition.py": "x = 1\n"}

#: A materially different task: a different problem, a different failing test, a different
#: repository. This is the "and a hash that changes" half of the hash contract — without it,
#: `return "0" * 64` would pass every other assertion in this file.
OTHER_REPO = RepoSpec(
    files={
        "strings.py": "def shout(text):\n    return text\n",
        "tests/test_shout.py": "from strings import shout\n\n\ndef test_shout_upcases():\n"
        '    assert shout("hi") == "HI"\n',
    },
    fail_to_pass=("tests/test_shout.py::test_shout_upcases",),
    pass_to_pass=(),
    held=("tests/test_shout.py",),
    problem_statement="shout() returns its argument unchanged.",
)

#: The other repository's own oracle. Carried so the "a different task hashes differently" arm
#: varies the sources along with everything else — a renderer that ignored its `sources` argument
#: would otherwise still be caught by the problem statement, and this way it is caught twice.
OTHER_SOURCES = {"strings.py": OTHER_REPO.files["strings.py"]}

#: The `PYTHONHASHSEED` values the cross-process arm renders under. `0` disables randomisation
#: outright — it is the value `sandbox.py` pins for the reward, and therefore the one a reader
#: will assume; the rest are ordinary seeds. See that test's docstring for why a fixed pair was
#: measured to be insufficient on its own.
HASH_SEEDS = ("0", "1", "12345", "987654321")

#: Rendered in a **fresh interpreter**, because the question "is this prompt byte-identical
#: across processes" cannot be answered inside one. It reloads the task from the same operator
#: manifest and prints two independent digests plus the seed evidence below.
_RENDER_PROBE = """
import hashlib
import json
import sys

from whetstone.bakeoff.rendering import prompt_hash, render_prompt
from whetstone.verify.task import load_task

prompt = render_prompt(load_task(sys.argv[1]), json.loads(sys.argv[2]))

# The renderer's own hash, and an independent digest of the prompt bytes. If the two ever
# disagree, `prompt_hash` is hashing something other than the string it was handed.
print("PROMPT-HASH:" + prompt_hash(prompt))
print("PROMPT-BYTES:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest())

# Anti-vacuity for the whole subprocess: proof that this interpreter's string hashing really is
# seeded differently from the other run's. Without it, two identical prompt hashes would be
# consistent with PYTHONHASHSEED having been ignored, and the arm would prove nothing.
print("SEED-EVIDENCE:" + str(hash("whetstone")))
"""


def _render_in_subprocess(manifest: Path, *, seed: str) -> dict[str, str]:
    """Render `manifest`'s task in a fresh interpreter under `PYTHONHASHSEED=seed`.

    The seed is **set** rather than defaulted, so an operator who exports their own
    `PYTHONHASHSEED` cannot collapse the arms onto one seed and quietly make this test vacuous.
    """
    probe = subprocess.run(
        [sys.executable, "-c", dedent(_RENDER_PROBE), str(manifest), json.dumps(ORACLE_SOURCES)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONHASHSEED": seed},
        check=False,
    )
    assert probe.returncode == 0, (
        f"rendering the prompt in a subprocess failed (exit {probe.returncode}).\n"
        f"stdout: {probe.stdout}\nstderr: {probe.stderr}\n\n"
        "WHY THIS IS A FAILURE: the cross-process determinism claim is unreachable if the"
        " renderer cannot run in a plain interpreter at all. Note in particular that this probe"
        " imports only `whetstone.bakeoff.rendering` and `whetstone.verify.task` — if it failed"
        " on an ImportError naming `mlx`, the prompt contract has acquired a dependency on the"
        " optional extra and CI (which runs a plain `uv sync`) will not be able to render"
        " anything."
    )
    reported: dict[str, str] = {}
    for line in probe.stdout.splitlines():
        label, _, value = line.partition(":")
        reported[label] = value
    return reported


def test_the_prompt_never_contains_the_held_test_contents(tmp_path: Path) -> None:
    """The assertion this whole file is for: the operator's golden tests stay operator-held.

    Asserted three ways because the leak has three shapes. The whole decoded blob catches a
    renderer that pasted the file; the revealing lines catch one that quoted or summarised part
    of it; and the blobs are read from the loaded `Task` rather than from the source constant, so
    a future manifest that carried a second held file is covered without anyone remembering to
    extend the list.
    """
    task = build_task(tmp_path, SENTINEL_REPO, task_id="sentinel-held-test").task
    prompt = render_prompt(task, ORACLE_SOURCES)

    for path, contents in task.test_blobs.items():
        decoded = contents.decode("utf-8")
        assert decoded not in prompt, (
            f"the rendered prompt contains the whole of held test {path!r}.\n\n"
            "WHY THIS IS A FAILURE: `test_blobs` is what STRICT restores from golden after the"
            " patch and grades against. Putting it in the prompt hands the policy the exam it is"
            " marked with, and makes cheat 6 — special-casing the graded inputs — the cheapest"
            " available strategy rather than a documented residual. No execution-grounded check"
            " can catch that patch afterwards, because it genuinely makes the graded tests pass."
        )

    assert ORACLE_SOURCES["calc.py"] in prompt, (
        "the prompt shows no source at all, so its silence about the held test proves nothing.\n\n"
        "WHY THIS IS A FAILURE: this is the anti-vacuity half of the leak check now that file"
        " contents are deliberately rendered. A renderer that dropped its `sources` argument"
        " would satisfy every assertion above while asking the impossible sourceless question."
    )

    for line in REVEALING_LINES:
        assert line in HELD_TEST_SOURCE, (
            f"the fixture no longer contains {line!r}, so asserting its absence proves nothing.\n"
            "\nWHY THIS IS A FAILURE: this is the anti-vacuity half of the leak check. A"
            " REVEALING_LINES entry that has drifted out of HELD_TEST_SOURCE would keep passing"
            " forever while checking a string no task ever held."
        )
        assert line not in prompt, (
            f"the rendered prompt quotes {line!r} from the operator-held test.\n\n"
            "WHY THIS IS A FAILURE: a partial quote leaks exactly as much as a whole one — the"
            " graded inputs and their expected outputs ARE the answer key. A renderer that"
            " summarised the held tests rather than pasting them would slip past a whole-blob"
            " check and would still make the reward measure the policy's copying rather than its"
            " fixing."
        )


def test_the_oracle_sources_are_shown_with_their_paths(tmp_path: Path) -> None:
    """The change this slice is for: the model is shown the code, not asked to guess it.

    A unified diff needs exact context lines. A prompt carrying no source at all asks for one
    against a file the base has never seen, which is not a hard task but an impossible one — the
    measured probe returned NOT_APPLIED on every rollout — and a bake-off run that way would
    compare prompts rather than bases and report a zero indistinguishable from P1's genuine pivot
    signal.

    The path is asserted as well as the body, because a diff header names the file: source shown
    without its path is source the base cannot address a hunk to.
    """
    task = build_task(tmp_path, SENTINEL_REPO, task_id="sentinel-held-test").task
    prompt = render_prompt(task, ORACLE_SOURCES)

    for path, contents in ORACLE_SOURCES.items():
        assert path in prompt, (
            f"the rendered prompt does not name the source file {path!r}.\n\n"
            "WHY THIS IS A FAILURE: a unified diff addresses its hunks by path. Contents shown"
            " without the path they came from cannot be turned into a diff that applies, and the"
            " rollout would be charged NOT_APPLIED for something the prompt withheld."
        )
        assert contents in prompt, (
            f"the rendered prompt does not contain the body of {path!r}.\n\n"
            "WHY THIS IS A FAILURE: this is the oracle setting's entire content. Without the"
            " file's actual lines the base has no context lines to write, every diff is refused"
            " at `patch-apply`, and the bake-off measures the prompt instead of the bases."
        )

    assert prompt.index(next(iter(ORACLE_SOURCES))) < prompt.index("# Response format"), (
        "the source files are rendered after the response-format section.\n\n"
        "WHY THIS IS A FAILURE: the response format is the instruction the base acts on last and"
        " it is the contract the extractor reads. Burying it above several files of source makes"
        " the shape of the answer the thing most easily forgotten, and a fenced-diff answer that"
        " never arrives is charged as no-diff — a zero about the layout of this string."
    )


def test_a_source_map_naming_an_operator_held_path_is_refused(tmp_path: Path) -> None:
    """The absolute ban, restated for the world where file contents ARE in the prompt.

    Until this slice the renderer read nothing but `problem_statement` and `fail_to_pass`, so
    "the held tests cannot leak" was true by construction. It no longer is: this function now
    renders whatever mapping it is handed. The one thing standing between a mis-derived path set
    and the answer key in the context window is a refusal here — a *raise*, not an omission,
    because a silently-dropped path would let a caller believe it had shown the model a file it
    never did and would make the leak invisible from both sides.
    """
    task = build_task(tmp_path, SENTINEL_REPO, task_id="sentinel-held-test").task

    with pytest.raises(HeldTestInSources) as refusal:
        render_prompt(task, HELD_PATH_SOURCES)

    assert "tests/test_addition.py" in str(refusal.value), (
        f"the refusal does not name the held path it refused. Got {str(refusal.value)!r}\n\n"
        "WHY THIS IS A FAILURE: whoever hits this has a derivation handing over operator-held"
        " files, and a refusal that does not say which one leaves them guessing at the map."
    )


def test_a_prompt_with_no_source_at_all_is_refused(tmp_path: Path) -> None:
    """An empty map is the pre-oracle prompt, and rendering it would score a different experiment.

    `scoring.score` records a task whose oracle could not be derived as skipped-with-reason rather
    than scoring it — because a run mixing sourceless prompts with oracle prompts publishes one
    denominator over two different questions. This refusal is the second lock on that: a caller
    that lost its sources on the way here cannot quietly fall back to the impossible task.
    """
    task = build_task(tmp_path, SENTINEL_REPO, task_id="sentinel-held-test").task

    with pytest.raises(EmptySources):
        render_prompt(task, {})


def test_a_source_file_containing_a_fence_is_still_shown_whole(tmp_path: Path) -> None:
    """A file with ``` in it must not terminate its own block and truncate the rest of itself.

    Markdown fences are the obvious way to delimit a file and the naive spelling is silently
    wrong: a docstring containing a fenced example closes the block early, and everything after it
    reads as prose. The model is then shown a *truncated* file while the harness believes it
    showed a whole one — the same "different experiment" the character budget refuses to run, but
    arriving without even a reason recorded.
    """
    task = build_task(tmp_path, SENTINEL_REPO, task_id="sentinel-held-test").task
    fenced = 'def add(a, b):\n    """Example:\n\n    ```python\n    add(1, 2)\n    ```\n    """\n'

    prompt = render_prompt(task, {"calc.py": fenced})

    assert fenced in prompt, (
        "a source file containing a fence was not rendered whole.\n\n"
        "WHY THIS IS A FAILURE: the file is what the base writes its context lines from. Any"
        " truncation makes a correct diff impossible for a reason nothing records, and the"
        " rollout is charged NOT_APPLIED as though the base had got the format wrong."
    )
    opening, _, tail = prompt.partition(fenced)
    fence = opening.splitlines()[-1]
    assert fence.startswith("````") and tail.lstrip("\n").startswith(fence), (
        f"the block around a fence-carrying file is delimited by {fence!r}, which the file's own"
        " content can close.\n\nWHY THIS IS A FAILURE: the delimiter has to be longer than the"
        " longest run of backticks inside the file, or the file closes its own block."
    )


def test_the_declared_node_ids_are_shown_even_though_their_bodies_are_not(
    tmp_path: Path,
) -> None:
    """The other side of the boundary: naming a test is disclosure, quoting it is the answer key.

    Worth asserting rather than assuming, because the safest-looking way to satisfy the leak
    check above is to stop mentioning the held tests at all — and that would silently redefine
    the task the bake-off measures into "guess which behaviour is wanted".
    """
    task = build_task(tmp_path, SENTINEL_REPO, task_id="sentinel-held-test").task
    prompt = render_prompt(task, ORACLE_SOURCES)

    for node_id in task.fail_to_pass:
        assert node_id in prompt, (
            f"the rendered prompt does not name the declared failing test {node_id!r}.\n\n"
            "WHY THIS IS A FAILURE: `fail_to_pass` is what the task asks the policy to fix. A"
            " prompt that omits it asks a different, harder question than the one the verifier"
            " grades, so a low baseline would be evidence about the prompt rather than about the"
            " base — and P1 exists to choose a base."
        )


def test_the_prompt_contains_the_problem_statement(tmp_path: Path) -> None:
    """Anti-vacuity for every determinism assertion in this file.

    A renderer returning `""` is perfectly deterministic across calls, across processes and
    across seeds, and leaks nothing whatsoever. It is also useless. This is the test that stops
    the rest of the file from being satisfied by nothing.
    """
    task = build_task(tmp_path, SENTINEL_REPO, task_id="sentinel-held-test").task
    prompt = render_prompt(task, ORACLE_SOURCES)

    assert task.problem_statement in prompt, (
        f"the rendered prompt does not contain the problem statement "
        f"{task.problem_statement!r}.\n\n"
        "WHY THIS IS A FAILURE: the problem statement plus the failing node ids IS the prompt"
        " contract (PRD M7b). If the statement is absent, every other assertion here is being"
        " satisfied by a string that tells the model nothing, and the bake-off would be"
        " measuring how well each base guesses."
    )
    assert prompt.strip(), (
        "the rendered prompt is empty or whitespace.\n\n"
        "WHY THIS IS A FAILURE: an empty prompt is stable, hashable and leak-free, so it passes"
        " every other test in this file. It is exactly the vacuous pass this assertion exists to"
        " refuse."
    )


def test_rendering_the_same_task_twice_is_byte_identical(tmp_path: Path) -> None:
    """Determinism within a process, asserted on encoded bytes rather than on string equality.

    Bytes because that is what gets hashed into the provenance block and what gets handed to a
    tokenizer. Ten repeats rather than two so an every-other-call defect — a renderer that
    memoised on the first call and rebuilt on the next — cannot hide in an even count.
    """
    task = build_task(tmp_path, SENTINEL_REPO, task_id="sentinel-held-test").task

    first = render_prompt(task, ORACLE_SOURCES).encode("utf-8")
    repeats = [render_prompt(task, ORACLE_SOURCES).encode("utf-8") for _ in range(10)]

    assert all(rendered == first for rendered in repeats), (
        "rendering the same task twice produced different bytes.\n\n"
        "WHY THIS IS A FAILURE: the rendered contract is hashed into the bake-off's provenance"
        " (PRD M8), and M7b makes any change to it after the first scored run invalidate that"
        " run. A renderer that varies call to call would make every run look invalidated, and"
        " would make two bases incomparable — the difference between them would include the"
        " difference between their prompts."
    )


def test_two_tasks_loaded_from_one_manifest_render_identically(tmp_path: Path) -> None:
    """Determinism across `Task` instances, which is what determinism across processes needs.

    A renderer that seeded anything from `id()`, from the clock, or from the iteration order of
    a set built per instance would pass the repeated-call test on one object and fail this one.
    """
    build_task(tmp_path, SENTINEL_REPO, task_id="sentinel-held-test")
    manifest = tmp_path / "task.json"

    assert render_prompt(load_task(manifest), ORACLE_SOURCES) == render_prompt(
        load_task(manifest), ORACLE_SOURCES
    )


def test_the_hash_is_the_sha256_of_the_prompt_bytes(tmp_path: Path) -> None:
    """The hash is of the prompt, in a spelling anyone auditing the report can reproduce.

    Pinned to `sha256(prompt.encode("utf-8")).hexdigest()` — the same construction
    `whetstone.tasks.ledger` already uses for manifest hashes — so a provenance block published
    in P4 can be checked by a reader with nothing but the prompt and a stdlib.
    """
    task = build_task(tmp_path, SENTINEL_REPO, task_id="sentinel-held-test").task
    prompt = render_prompt(task, ORACLE_SOURCES)

    expected = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    assert prompt_hash(prompt) == expected, (
        f"prompt_hash returned {prompt_hash(prompt)!r}, not {expected!r}.\n\n"
        "WHY THIS IS A FAILURE: this hash is the evidence for M7b — that the generation contract"
        " was not tuned against the scored result. Evidence a reader cannot recompute from the"
        " published prompt is not evidence; it is an assertion with a hex string next to it."
    )


def test_a_materially_different_task_hashes_differently(tmp_path: Path) -> None:
    """The other direction, without which `prompt_hash` need not be a hash at all.

    A constant would satisfy every stability assertion in this file. The whole enforcement value
    of M7b is that editing the contract *changes the recorded hash*, so a scored run cannot be
    quietly continued under a different prompt with the provenance block still reading the same.
    """
    one = build_task(tmp_path / "a", SENTINEL_REPO, task_id="sentinel-held-test").task
    other = build_task(tmp_path / "b", OTHER_REPO, task_id="other-task").task

    assert render_prompt(one, ORACLE_SOURCES) != render_prompt(other, OTHER_SOURCES), (
        "two materially different tasks rendered to the same prompt.\n\n"
        "WHY THIS IS A FAILURE: the tasks differ in their problem statement, their failing node"
        " id and their repository. A renderer that collapses them is discarding the task, and"
        " every base would be asked the same question regardless of what it was pointed at."
    )
    assert prompt_hash(render_prompt(one, ORACLE_SOURCES)) != prompt_hash(
        render_prompt(other, OTHER_SOURCES)
    ), (
        "two different prompts produced the same hash.\n\n"
        "WHY THIS IS A FAILURE: a hash that never changes is not a hash. M7b is enforceable only"
        " because a change to the generation contract shows up as a different recorded digest —"
        " a constant would let the prompt be edited mid-bake-off with the provenance unchanged,"
        " which is the tuning-on-the-outcome the rule exists to forbid."
    )


def test_the_prompt_is_byte_identical_across_processes_and_hash_seeds(tmp_path: Path) -> None:
    """Cross-process determinism, under four fixed hash seeds and this process's random one.

    The realistic defect is a renderer that iterates a `set` or a `frozenset` of strings: its
    sections come out in an order that depends on the interpreter's hash seed, so it is
    byte-identical every time *within* one process and different between two. `sandbox.py` pins
    `PYTHONHASHSEED=0` for the reward — this renderer runs **outside** the sandbox and inherits
    no such pin, so that pinning cannot be borrowed as an argument here.

    **Four seeds, not two, and the in-process comparison as well — because two was measured to
    be too few.** Watched failing against a deliberately set-iterating renderer, seeds `0` and
    `12345` produced the *same* set order for this fixture's four node ids on every run, so that
    pair alone reported green against the very defect it was written to catch. Four node ids give
    24 possible orders and any fixed seed is just one draw from them; what reliably caught the
    defect was the comparison against this process, which pytest runs under a *randomised* seed.
    Both are kept: the fixed seeds make the test reproducible, the random one makes it sensitive.

    Each probe proves its own interpreter was seeded differently from the others before this test
    concludes anything from their agreeing — "PYTHONHASHSEED was ignored" and "the renderer is
    deterministic" produce the same observation otherwise.
    """
    build_task(tmp_path, SENTINEL_REPO, task_id="sentinel-held-test")
    manifest = tmp_path / "task.json"

    rendered = {seed: _render_in_subprocess(manifest, seed=seed) for seed in HASH_SEEDS}
    seed_evidence = {probe["SEED-EVIDENCE"] for probe in rendered.values()}

    assert len(seed_evidence) > 1, (
        f"every subprocess hashed strings identically ({seed_evidence}), so PYTHONHASHSEED did"
        " not take effect.\n\n"
        "WHY THIS IS A FAILURE: this is the anti-vacuity check for the whole test. If the"
        " interpreters share a hash seed then matching prompt hashes are consistent with a"
        " renderer that iterates a set — the exact defect this arm exists to catch — and the"
        " green result would be meaningless."
    )

    digests = {seed: probe["PROMPT-HASH"] for seed, probe in rendered.items()}
    assert len(set(digests.values())) == 1, (
        f"the same task rendered to different prompts under different hash seeds: {digests}.\n\n"
        "WHY THIS IS A FAILURE: the prompt hash is recorded once and compared across the whole"
        " bake-off. If it moves with the interpreter's hash seed, then M7b's invalidation rule"
        " fires on runs where nothing changed, and the one signal that would reveal a genuinely"
        " edited contract is lost in the noise."
    )

    for seed, probe in rendered.items():
        assert probe["PROMPT-HASH"] == probe["PROMPT-BYTES"], (
            f"under PYTHONHASHSEED={seed}, prompt_hash ({probe['PROMPT-HASH']}) is not the"
            f" sha256 of the prompt bytes ({probe['PROMPT-BYTES']}).\n\n"
            "WHY THIS IS A FAILURE: the two digests are computed independently inside the probe."
            " A disagreement means prompt_hash is hashing something other than the string it was"
            " given, so the published digest could not be recomputed from the published prompt."
        )

    # Safe to unpack: the assertion above has already established there is exactly one digest.
    (agreed_digest,) = set(digests.values())
    in_process = prompt_hash(render_prompt(load_task(manifest), ORACLE_SOURCES))
    assert in_process == agreed_digest, (
        f"the prompt hashed differently in this process ({in_process}) than in a fresh one"
        f" ({agreed_digest}).\n\n"
        "WHY THIS IS A FAILURE: the bake-off records the hash in one process and renders prompts"
        " in others. A digest that depends on which interpreter computed it is not provenance."
        " This process runs under pytest's randomised hash seed, which is what makes this the"
        " most sensitive comparison in the test rather than a restatement of the ones above."
    )
