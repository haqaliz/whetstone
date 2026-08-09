"""The replay, and the two ways an attributed zero could be worse than an unattributed one.

`reports/baseline/` says 142 of 152 verdict-reaching rollouts never got a patch onto disk and
cannot say why. This file guards the module that answers "why", offline, from stored completions.
The answer is read as evidence for the next slice's format choice, so a breakdown that is merely
*plausible* is worse than no breakdown at all: it would point the fix at a cause that was never
measured, and it would do so with the authority of a number.

**Failure one: a taxonomy invented here.** The buckets must be `patch.py`'s own `NoDiff`
construction sites, not a partition someone thought sounded right (the PRD flags the invented one
as its 🔴, `prd.md` § 8). A bucket set that merely *resembles* the extractor's reasons drifts the
moment `patch.py` gains a fifth reason: the new reason falls into whichever bucket happens to
match, or into an "other" bin, and the breakdown keeps reporting confident counts over a cause it
has never seen. So the mapping test below walks `patch.py` with `ast` and requires a **bijection**
— every construction site covered by exactly one bucket, every bucket covering at least one site.
A fifth reason fails this file rather than being silently absorbed; that is demonstrated against a
synthetic fifth site rather than asserted.

**Failure two: a cause folded into its neighbour.** "git would not parse it" and "git parsed it
and would not apply it" are the two the current report cannot separate, and they have opposite
fixes — the first is an output-format problem, the second is a model-was-wrong problem. Attributing
one as the other would send the next slice to rewrite a prompt over a defect the prompt cannot
reach. The same rule covers the case where no checkout is available: that rollout is `UNATTRIBUTED`
**by name**, never quietly counted in whichever bucket is adjacent, because a missing measurement
rendered as a measurement is how a partial run reads as a complete one.

Nothing here loads a model, and the last test proves it by walking this file and the module it
tests with `ast` — the shape `tests/test_no_inference_on_reward_path.py` uses. That matters more
here than elsewhere in `bakeoff/`: the whole value of the replay is that a night of compute buys
unlimited re-analysis, and an analysis that needed the model back would be a re-run wearing a
replay's name.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from whetstone.bakeoff import patch as patch_module
from whetstone.bakeoff.attribution import (
    NO_DIFF_MARKERS,
    Attribution,
    Cause,
    attribute,
    attribute_all,
    breakdown,
    cause_of_reason,
    extract_patch,
)
from whetstone.bakeoff.patch import Extracted, NoDiff
from whetstone.bakeoff.transcript import Transcribed, Transcript

#: The repository root, reached from `tests/bakeoff/`. Used to read source with `ast` rather than
#: by import: the import guard has to report on the source that ships, not on what the venv holds.
ROOT = Path(__file__).resolve().parents[2]

#: The module under test and this file, the two the no-inference walk covers.
MODULE = ROOT / "src" / "whetstone" / "bakeoff" / "attribution.py"
THIS_FILE = Path(__file__).resolve()

#: A complete, well-formed diff against the fixture repository below. Applies cleanly.
GOOD_DIFF = """diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""

#: The same shape, aimed at a path the checkout does not have. git's `--numstat` parses it
#: happily — it reports `1\t1\tmissing.py` — and `git apply` then refuses with "No such file or
#: directory". Verified against the `git apply` this repository calls. This is the *parsed but
#: did not apply* case, and it is what a base that hallucinated a filename produces.
MISSING_PATH_DIFF = GOOD_DIFF.replace("adder.py", "missing.py")

#: A diff that stops inside its hunk: the header declares two lines on each side and the body
#: supplies one addition short. Verified: `git apply --numstat` answers "corrupt patch at line 7"
#: and refuses, so this never reaches the apply step at all. This is what a base that ran out of
#: generation budget mid-patch produces, and `patch.py` deliberately returns it as `Extracted` so
#: that it is distinguishable from a base that wrote no patch (`patch.py:52-53`).
CORRUPT_HUNK_DIFF = """diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
"""

#: One completion per `NoDiff` construction site in `patch.py`, in that file's own order. The
#: bucket each must land in is the assertion; the completions are the shapes a base really emits.
NO_DIFF_COMPLETIONS: tuple[tuple[str, Cause], ...] = (
    ("   \n\t\n", Cause.NO_OUTPUT),
    (
        "```diff\ndiff --git a/adder.py b/adder.py\n--- a/adder.py\n+++ b/adder.py\n```\n",
        Cause.HEADER_WITHOUT_HUNK,
    ),
    ("Try this:\n\n```python\ndef add(a, b):\n    return a + b\n```\n", Cause.FENCED_WITHOUT_DIFF),
    ("The bug is that `add` subtracts instead of adding.\n", Cause.NO_DIFF_HEADER),
)

#: Marks an interpolation when a reason is reconstructed from source. Two of `patch.py`'s four
#: reasons are f-strings, and a bucket's marker must live inside one literal run rather than
#: spanning a `{...}` — otherwise it would match the source and never match a real reason.
PLACEHOLDER = "\x00"

#: Import roots that would mean a model was consulted. Deliberately wider than `mlx`: the claim
#: is that the replay needs no inference at all, and `torch` or `openai` would break it exactly
#: as `mlx_lm` would.
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"mlx", "mlx_lm", "torch", "transformers", "openai", "anthropic", "huggingface_hub"}
)


def git(
    args: list[str], *, cwd: Path, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Real git, with the developer's own configuration switched off.

    The same environment scrubbing `whetstone.verify.repo._git` does, and for the same reason: a
    machine-local `apply.whitespace=fix` or a `hooksPath` would change which of these fixtures
    parses, and the parse/apply split is the entire finding this file pins.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        input=stdin,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "HOME": str(cwd),
        },
        check=False,
    )


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A one-file git repository that `GOOD_DIFF` applies cleanly to.

    Real git rather than a stub, because the question the checkout layer answers — *did git refuse
    to parse this, or refuse to apply it* — has one authority, and it is the `git apply` that
    `whetstone.verify.repo` shells out to.
    """
    tree = tmp_path / "checkout"
    tree.mkdir()
    (tree / "adder.py").write_text("def add(a, b):\n    return a - b\n")
    assert git(["init", "--quiet", "."], cwd=tree).returncode == 0
    assert git(["add", "adder.py"], cwd=tree).returncode == 0
    committed = git(
        ["-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "base"],
        cwd=tree,
    )
    assert committed.returncode == 0, committed.stderr
    return tree


def record(completion: str, *, candidate: str = "base-a", task_id: str = "task-1") -> Transcribed:
    """A stored rollout carrying `completion`. The prompt is incidental to attribution."""
    return Transcribed(
        candidate=candidate,
        task_id=task_id,
        prompt_sha256="0" * 64,
        prompt="fix the bug",
        completion=completion,
        attempt=1,
        decision="graded",
    )


# --------------------------------------------------------------------------------------------
# Layer 1, the pure replay: the stored text must extract exactly as the live run's did.
# --------------------------------------------------------------------------------------------


def test_the_replay_calls_the_extractor_the_scoring_path_calls() -> None:
    """Identity, not equivalence: the replay must be the same function object, not a copy.

    A re-implementation that agreed on today's fixtures would diverge the first time `patch.py`
    changed, and the divergence would be invisible — the replay would keep producing a confident
    breakdown describing an extractor the run never used. Attributing a *past* run with a *present*
    extractor is a separate, known limitation; attributing it with a second extractor nobody knew
    existed is a defect.
    """
    assert extract_patch is patch_module.extract_patch, (
        "attribution re-exports something other than `patch.extract_patch`.\n\n"
        "WHY THIS MATTERS: the replay's only claim is that it re-derives what the live scoring"
        " path derived. A parallel copy of the extractor makes that claim false the moment the"
        " two drift, and nothing in the breakdown would look wrong while it happened."
    )


def test_a_stored_completion_re_extracts_to_what_the_live_path_produced(tmp_path: Path) -> None:
    """The round trip that makes the transcript worth keeping: disk in, same `Extraction` out.

    The live run extracted from the completion in memory and dropped the text
    (`scoring.py:432-435`). If a stored-and-replayed completion extracted to anything else — a
    stripped trailing newline is enough, since the extractor reads fenced blocks — every figure
    the replay produced would describe a run that never happened.
    """
    completion = f"Here is the fix:\n\n```diff\n{GOOD_DIFF}```\n\nHope that helps!\n"
    live = extract_patch(completion)

    transcript = Transcript(tmp_path / "transcript.jsonl")
    transcript.append(record(completion))
    replayed = transcript.replay()[("base-a", "task-1")]

    assert extract_patch(replayed.completion) == live, (
        f"replayed extraction {extract_patch(replayed.completion)!r} differs from the live"
        f" extraction {live!r}.\n\n"
        "WHY THIS MATTERS: the transcript exists so a night of compute can be re-analysed"
        " offline. A record that does not re-derive the run's own extraction is not evidence of"
        " that run — it is a second, unattributed experiment being reported as the first."
    )
    assert isinstance(live, Extracted) and live.diff == GOOD_DIFF


# --------------------------------------------------------------------------------------------
# Layer 1's taxonomy: the buckets are `patch.py`'s reasons, and a fifth one must fail loudly.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("completion", "expected"), NO_DIFF_COMPLETIONS)
def test_each_no_diff_reason_lands_in_its_own_bucket(completion: str, expected: Cause) -> None:
    """Four shapes a base emits, four distinct causes, four different fixes.

    "Wrote prose", "wrote a fenced block that was not a patch", "started a patch and stopped" and
    "said nothing" are a prompt problem, an extractor-or-format problem, a token-budget problem and
    a model problem. Collapsing any pair of them would send the next slice's format choice after
    the wrong one.
    """
    extraction = extract_patch(completion)
    assert isinstance(extraction, NoDiff), extraction

    result = attribute(record(completion))

    assert result.cause is expected, (
        f"{completion!r} was attributed {result.cause} rather than {expected};"
        f" the extractor's reason was {extraction.reason!r}.\n\n"
        "WHY THIS MATTERS: these four causes have four different fixes. A breakdown that merges"
        " any two of them reports a cause nobody measured, and the next slice spends a generation"
        " pass fixing it."
    )
    assert result.detail == extraction.reason, (
        "the attribution dropped or rewrote the extractor's own sentence.\n\n"
        "WHY THIS MATTERS: the bucket is for counting and the reason is for reading. Whoever"
        " opens the breakdown to understand one rollout needs the sentence `patch.py` wrote"
        " about it, not a paraphrase written here."
    )


def _reason_text(node: ast.expr) -> str:
    """The literal text of a `NoDiff` reason as written in source, interpolations blanked.

    An f-string's `{...}` cannot be evaluated statically and must not be guessed at, so each one
    becomes `PLACEHOLDER`. A bucket marker is required to sit inside one literal run, which is
    what makes a marker that matches this reconstruction also match the real runtime string.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            part.value
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
            else PLACEHOLDER
            for part in node.values
        )
    return PLACEHOLDER


def _no_diff_sites(source: str) -> list[str]:
    """Every `NoDiff(...)` construction in `source`, as its reason's literal text.

    Read with `ast` rather than by importing and calling, because the sites are the taxonomy: a
    reason that exists in the file but is only reachable down some branch this test never
    exercises is still a reason a real run can produce.
    """
    sites: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "NoDiff"):
            continue
        argument = node.args[0] if node.args else next(iter(node.keywords)).value
        sites.append(_reason_text(argument))
    return sites


def _covering_buckets(site: str) -> list[Cause]:
    """Which buckets claim `site`. Exactly one is the requirement; the test asserts it."""
    return [cause for cause, marker in NO_DIFF_MARKERS.items() if marker in site]


def test_every_no_diff_site_in_patch_py_is_covered_by_exactly_one_bucket() -> None:
    """The bijection: `patch.py`'s reasons ARE the taxonomy, and nothing here may invent one.

    Both directions matter and each catches a different mistake. *Every site covered exactly
    once* fails when `patch.py` gains a reason — the failure the PRD's 🔴 asks for, instead of the
    new reason drifting into whichever bucket happens to match. *Every bucket covering a site*
    fails when a reason is removed or reworded, so a bucket cannot go quietly dead and keep
    reporting a count of zero that reads as "this never happens".
    """
    sites = _no_diff_sites(patch_module.__file__ and Path(patch_module.__file__).read_text())

    assert sites, (
        "no `NoDiff(...)` construction was found in patch.py, so this test proved nothing.\n\n"
        "WHY THIS MATTERS: the mapping check is only worth anything if it observed the real"
        " construction sites. An empty walk satisfies every assertion below vacuously."
    )

    uncovered = [site for site in sites if len(_covering_buckets(site)) != 1]
    assert not uncovered, (
        "these `NoDiff` reasons in patch.py are not covered by exactly one bucket:\n  "
        + "\n  ".join(repr(site) for site in uncovered)
        + "\n\nWHY THIS MATTERS: the taxonomy is `patch.py`'s own reasons, never a partition"
        " invented in the attribution module. A reason with no bucket would be counted as"
        " unattributed forever; a reason with two would be counted twice. Add the bucket here"
        " and state what the new reason means — do not widen an existing marker to swallow it."
    )

    claimed = {cause for site in sites for cause in _covering_buckets(site)}
    assert claimed == set(NO_DIFF_MARKERS), (
        f"these buckets match no reason in patch.py: {sorted(set(NO_DIFF_MARKERS) - claimed)}.\n\n"
        "WHY THIS MATTERS: a bucket whose marker no longer matches anything reports zero"
        " rollouts, and zero reads as 'this failure never occurred' rather than as 'this bucket"
        " stopped working'."
    )


def test_a_fifth_no_diff_reason_is_reported_rather_than_absorbed() -> None:
    """The mapping check's teeth, demonstrated on a synthetic `patch.py` rather than claimed.

    Written against a copy in memory so proving the guard works never means committing a
    violation to the real extractor and trusting a later revert. If this passes while the test
    above also passes, the bijection is real: a new reason has nowhere to hide.
    """
    planted = 'x = NoDiff("the model emitted a shape nobody has bucketed yet")\n'
    sites = _no_diff_sites(Path(patch_module.__file__ or "").read_text() + planted)

    unmatched = [site for site in sites if not _covering_buckets(site)]

    assert unmatched == ["the model emitted a shape nobody has bucketed yet"], (
        f"a planted fifth reason was not reported as uncovered; unmatched={unmatched}.\n\n"
        "WHY THIS MATTERS: if a new reason can be added to patch.py without failing this file,"
        " the breakdown silently stops describing the extractor it claims to describe."
    )


def test_an_unrecognised_reason_is_unattributed_by_name_rather_than_guessed_at() -> None:
    """At runtime a reason with no bucket is named as unattributed, never assigned a neighbour.

    The mapping test above is the build-time failure. This is the run-time behaviour behind it:
    if the two ever disagree — an extractor upgraded under an older attribution module — the
    breakdown says "we could not attribute this", which is true, rather than adding one to a
    bucket it was never measured into.
    """
    assert cause_of_reason("something patch.py has never said") is None
    for _completion, expected in NO_DIFF_COMPLETIONS:
        assert expected in set(NO_DIFF_MARKERS), expected


# --------------------------------------------------------------------------------------------
# Layer 2, the checkout: the two causes `reports/baseline/` cannot currently separate.
# --------------------------------------------------------------------------------------------


def test_a_well_formed_diff_naming_a_missing_path_is_parsed_but_did_not_apply(
    checkout: Path,
) -> None:
    """git read this patch and refused it. A model-was-wrong failure, not a format failure.

    `git apply --numstat` reports `missing.py` without complaint — parsing a diff says nothing
    about whether the file exists — and the apply then fails. Today both this and the corrupt
    case below arrive at `NOT_APPLIED` with no way to tell them apart, and they have opposite
    fixes: rewriting the response format cannot help a base that named a file that is not there.
    """
    result = attribute(record(f"```diff\n{MISSING_PATH_DIFF}```\n"), checkout=checkout)

    assert result.cause is Cause.PARSED_BUT_DID_NOT_APPLY, (
        f"attributed {result.cause} ({result.detail!r}) rather than PARSED_BUT_DID_NOT_APPLY.\n\n"
        "WHY THIS MATTERS: this diff is well-formed — git parsed it and named the path. Calling"
        " it a parse failure would send the next slice to change the output format over a base"
        " that hallucinated a filename, which no format can fix."
    )
    assert "did not apply" in result.detail, result.detail


def test_a_corrupt_mid_hunk_diff_is_attributed_as_one_git_would_not_parse(checkout: Path) -> None:
    """git could not read this patch at all. A format-or-budget failure, and the fixable one.

    The hunk header promises two lines on each side and the body stops one short, which is what a
    base that hit its token cap mid-patch emits. `patch.py` returns it as `Extracted` on purpose
    (`patch.py:52-53`) so that "attempted a patch and was cut off" stays distinguishable from
    "wrote no patch" — and this bucket is where that distinction is finally cashed in.
    """
    result = attribute(record(f"```diff\n{CORRUPT_HUNK_DIFF}```\n"), checkout=checkout)

    assert result.cause is Cause.WOULD_NOT_PARSE, (
        f"attributed {result.cause} ({result.detail!r}) rather than WOULD_NOT_PARSE.\n\n"
        "WHY THIS MATTERS: this is the cause the next slice's format change exists to remove."
        " Folded into 'did not apply' it would be invisible, and a format change would be judged"
        " against a number that never contained it."
    )
    assert "could not be parsed" in result.detail, result.detail


def test_a_diff_that_applies_is_not_reported_as_a_failure_to_produce_a_patch(
    checkout: Path,
) -> None:
    """The control: with a real checkout, a good diff must reach `APPLIED` and no other bucket.

    Without this, every assertion above is satisfied by an attributor that answers "would not
    apply" to everything, and the breakdown would report the whole run as a patch-format problem.
    """
    result = attribute(record(f"```diff\n{GOOD_DIFF}```\n"), checkout=checkout)

    assert result.cause is Cause.APPLIED, (
        f"a patch git accepts was attributed {result.cause} ({result.detail!r}).\n\n"
        "WHY THIS MATTERS: an attributor that says 'refused' to everything satisfies both"
        " refusal tests above and describes a run in which nothing ever worked."
    )


def test_attribution_never_writes_to_the_checkout_it_was_handed(checkout: Path) -> None:
    """Attributing one rollout must not change what the next rollout is attributed against.

    Deciding whether a patch applies means applying it, and every candidate's rollout on a task
    shares that task's one checkout. An attributor that applied into the caller's tree would leave
    it dirty, so every later patch for that task would be judged against a tree carrying some
    earlier candidate's edits — a breakdown whose answers depend on the order the rollouts were
    read in.
    """
    before = (checkout / "adder.py").read_text()

    assert attribute(record(f"```diff\n{GOOD_DIFF}```\n"), checkout=checkout).cause is Cause.APPLIED

    assert (checkout / "adder.py").read_text() == before, (
        "the checkout's content changed while attributing a rollout.\n\n"
        "WHY THIS MATTERS: the checkout is shared across every candidate's rollout on that task."
        " A dirty tree makes the second attribution depend on the first, so the breakdown would"
        " change with the order of the file it was read from."
    )
    status = git(["status", "--porcelain"], cwd=checkout)
    assert status.stdout == "", f"the checkout was left dirty: {status.stdout!r}"


def test_a_rollout_with_no_checkout_is_unattributed_by_name(tmp_path: Path) -> None:
    """A measurement that could not be taken is named, never folded into a neighbouring bucket.

    Without a checkout the parse/apply question cannot be asked at all. Attributing such a rollout
    to either answer would manufacture evidence; attributing it to `NO_DIFF_HEADER` would be worse
    still, since the base demonstrably produced a diff. The honest bucket is its own, and it must
    be countable, so a reader can see how much of the breakdown is missing rather than being shown
    a total that quietly excludes it.
    """
    result = attribute(record(f"```diff\n{GOOD_DIFF}```\n"), checkout=None)

    assert result.cause is Cause.UNATTRIBUTED, (
        f"a rollout with no checkout was attributed {result.cause}.\n\n"
        "WHY THIS MATTERS: 'we could not measure this' and 'we measured this and it failed' are"
        " different claims. Reporting the first as the second inflates whichever bucket absorbed"
        " it, and the inflation is invisible."
    )
    assert result.detail, "an unattributed rollout must say why it could not be attributed"

    # A path that does not exist is the same finding as no path at all: the machinery could not
    # run, and saying so is the answer. A checkout that vanished between the run and the replay
    # is the ordinary way this happens.
    vanished = attribute(record(f"```diff\n{GOOD_DIFF}```\n"), checkout=tmp_path / "gone")
    assert vanished.cause is Cause.UNATTRIBUTED, vanished


# --------------------------------------------------------------------------------------------
# The breakdown: per candidate, because one base's failures say nothing about another's.
# --------------------------------------------------------------------------------------------


def test_the_breakdown_counts_causes_per_candidate(checkout: Path) -> None:
    """R2's shape: a cause breakdown for each base, never one pooled total across all of them.

    P1's finding was that the failure modes *differ by candidate* — unapplicable patches at the
    small and large ends, empty diffs in the middle. A pooled count would have hidden exactly
    that, and it is the one thing the report already says is a finding rather than a tie.
    """
    records = (
        record("no patch here, sorry\n", candidate="base-a", task_id="t1"),
        record(f"```diff\n{CORRUPT_HUNK_DIFF}```\n", candidate="base-a", task_id="t2"),
        record(f"```diff\n{GOOD_DIFF}```\n", candidate="base-b", task_id="t1"),
    )

    results = attribute_all(records, checkouts={"t1": checkout, "t2": checkout})

    assert all(isinstance(result, Attribution) for result in results)
    assert breakdown(results) == {
        "base-a": {Cause.NO_DIFF_HEADER: 1, Cause.WOULD_NOT_PARSE: 1},
        "base-b": {Cause.APPLIED: 1},
    }, breakdown(results)


def test_a_task_with_no_checkout_does_not_borrow_another_tasks(checkout: Path) -> None:
    """A per-task checkout mapping must miss loudly, never fall back to whatever is available.

    Applying task A's patch to task B's tree answers a question nobody asked and answers it
    confidently. The absent entry is `UNATTRIBUTED`, exactly as no mapping at all would be.
    """
    results = attribute_all(
        (record(f"```diff\n{GOOD_DIFF}```\n", task_id="t2"),), checkouts={"t1": checkout}
    )

    assert [result.cause for result in results] == [Cause.UNATTRIBUTED], results


# --------------------------------------------------------------------------------------------
# The replay is offline: no model, here or in the module it tests.
# --------------------------------------------------------------------------------------------


def _imported_roots(path: Path) -> set[str]:
    """The top-level package of every import in `path`, function-local ones included.

    `ast.walk` rather than a top-of-file read, because an import moved inside a function would
    otherwise be invisible — which is exactly where a "just this once" model call would go.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_bytes(), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", [MODULE, THIS_FILE])
def test_the_replay_imports_no_inference_library(path: Path) -> None:
    """The replay's whole value is that it costs no compute; an import here would spend some.

    `bakeoff/` is exempt from the reward-path guard, and legitimately so — `mlx_runtime.py` must
    import `mlx_lm`. This is a narrower claim about these two files: a night of generation is
    kept on disk so every later question can be answered offline, and a replay that reached for
    the model again would be a re-run charging a replay's price. The test file is covered too,
    because a fixture that generated its own completions would make the module's own guarantee
    untestable.
    """
    roots = _imported_roots(path)

    assert not roots & FORBIDDEN_IMPORT_ROOTS, (
        f"{path.name} imports {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}.\n\n"
        "WHY THIS MATTERS: the transcript exists so one night of compute can be re-analysed"
        " indefinitely without another. An inference import here means the analysis needs the"
        " model back, and every question asked of the data costs a generation pass again."
    )
    # Anti-vacuity: the walk must be reading real imports, or the assertion above holds for a
    # parser that returned nothing at all.
    assert "whetstone" in roots, roots
