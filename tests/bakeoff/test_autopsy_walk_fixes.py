"""The walk fixes: three places the walk disagreed with git, now pinned by fixtures.

The operator step ran the autopsy over the stored bake-off runs and the mapping assertion
surfaced three systematic walk-vs-git disagreements — records whose fine verdict and whose
recorded coarse cause contradicted each other for the same shape (`prd.md` R3). Each was
traced to the hunk walk in `autopsy.py` reading the patch differently from the `git apply`
the attribution already answered with. This file pins the fixed rules; every fixture is a
tiny synthetic replica of the observed shape with toy names (`adder.py`, `multiplier.py`),
never donor content (`card.md:68-70`).

**The extracted diff is all git receives.** The walk re-runs the extractor's span logic over
the span it found — the same bytes that reach `git apply`. A line *after* that span is text
git never parses, so it cannot be a hunk-count violation: a hunk that completes exactly at
the diff's end is well-formed whatever the completion continues with. The old walk judged
that trailing text and misnamed an APPLIED patch as `hunk-count-mismatch` — the 3B
`belay-2e149603209a` record git applied while the walk reported "body extends beyond its
declared counts".

**A counter below zero is git's corrupt patch.** git's apply parser loops `while (oldlines
|| newlines)` — in C a negative counter is truthy, so once a hunk body carries more lines of
a kind than its header declared, git keeps reading past the hunk and refuses with "corrupt
patch at line N". The old walk's loop exits at zero-or-negative and reported well-formed —
the 14B `contig-2ef3383b0ce7` record git refused while the walk said "all 1 hunks complete".
The fixed walk records the overrun and names it `hunk-count-mismatch` — the
invented-counts signature — with the existing precedence kept: a death still outranks an
overrun, and an overrun in the first hunk is the mismatch, never `hunk-dies-early`.

**A loop-dominated completion may still carry a diff git refused.** The 7B loop ate the
token budget, and the completions that escape it near the cap write a stub diff the run's
attribution recorded as `WOULD_NOT_PARSE` (`dig-transcripts.md` § 4). The fine pass names
the loop `im-start-loop` (no well-formed diff follows), and the mapping must allow the
coarse `WOULD_NOT_PARSE` beside it — they describe the same record from two sides.

All fixtures are tiny synthetic strings with toy paths — replicas of the dig's observed
shapes, never donor content (`card.md:68-70`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from whetstone.bakeoff.attribution import Cause
from whetstone.bakeoff.autopsy import (
    FINE_TO_COARSE,
    DeathKind,
    FineCause,
    Marker,
    autopsy,
    classify_completion,
)
from whetstone.bakeoff.patch import Extracted, extract_patch
from whetstone.bakeoff.transcript import Transcribed

#: The repository root, reached from `tests/bakeoff/`. Used by the `patch.py`-unmodified guard.
ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------------------------
# The fixtures: synthetic replicas of the three observed walk-vs-git disagreements
# (`dig-transcripts.md` § 2 shapes 2 and 4; § 4), toy paths, tiny. Never donor content.
# --------------------------------------------------------------------------------------------

#: The defect-1 shape: a hunk whose body EXACTLY satisfies its declared counts — six context
#: lines and one added, declared 6/7 — followed by a space-prefixed context line in the
#: completion that the extractor's span correctly stops before. The extracted diff is what
#: git receives and git parses it; the old walk read the trailing context line and flagged
#: "body extends beyond its declared counts" — a false positive on a record git APPLIED
#: (3B, belay-2e149603209a).
SELF_CONSISTENT_HUNK = """--- a/adder.py
+++ b/adder.py
@@ -10,6 +10,7 @@
 from __future__ import annotations

 from dataclasses import dataclass
 from typing import Union

+from adder.verdict import attach
 from adder.connection import derive_connection_context
 from adder.index import derive_correlation
"""

#: The defect-2 shape: a hunk declaring old=6 / new=24 whose body supplies 25 added lines —
#: one more than declared — so `new` goes negative while the walk consumes it. The extra
#: added line keeps git's C loop (`while (oldlines || newlines)`, a negative counter truthy)
#: reading past the hunk, and git refuses the whole patch as corrupt (14B,
#: contig-2ef3383b0ce7, "corrupt patch at line 35"). The old walk exited at zero-or-negative
#: and reported well-formed; the closing fence after the diff kept even the old extends
#: check quiet.
_ADDED_OVERFLOW = "".join("+    return a + b\n" for _ in range(25))
OVERRUN_HUNK = f"""```diff
--- a/adder.py
+++ b/adder.py
@@ -100,6 +100,24 @@
 def add(a, b):
     return a - b
     return a + b
{_ADDED_OVERFLOW} def add(a, b):
     # placeholder comment
     try:
```
"""

#: Precedence: a first-hunk death outranks an overrun in the same hunk. The body drives `new`
#: negative and then dies on an unprefixed line with counts remaining — the death is the
#: stop, never the overrun (`prd.md` D4: first-hunk death is `hunk-dies-early`).
OVERRUN_THEN_DEATH = f"""--- a/adder.py
+++ b/adder.py
@@ -100,6 +100,24 @@
 def add(a, b):
     return a - b
     return a + b
{_ADDED_OVERFLOW}def add(a, b):
"""

#: Precedence: a later-hunk death outranks an overrun. Hunk 1 overruns (25 added against 24
#: declared) and completes its consumption; hunk 2 then dies on an unprefixed line. The walk
#: records the overrun but keeps walking, so the later death — not the earlier overrun — is
#: the verdict's detail.
OVERRUN_THEN_LATER_DEATH = f"""--- a/adder.py
+++ b/adder.py
@@ -100,6 +100,24 @@
 def add(a, b):
     return a - b
     return a + b
{_ADDED_OVERFLOW} def add(a, b):
     # placeholder comment
     try:
--- a/multiplier.py
+++ b/multiplier.py
@@ -1,3 +1,3 @@
 def mul(a, b):
-    return a * b
+    return a ** b
def mul(a, b):
"""

#: The regression shape: a multi-file diff whose two hunks are internally consistent,
#: followed by a dominant `<|im_start|>` token loop (ratio 0.414 > 0.2). A space-prefixed
#: context line sits between the diff and the loop — the line the old extends check judged.
#: The old walk demoted the whole completion to `im-start-loop`; the fix must name the diff
#: well-formed and keep the loop as the `LOOP_PRESENT` marker (`prd.md` D4).
LOOP_AFTER_CONSISTENT_MULTIFILE = """diff --git a/adder.py b/adder.py
index 1234567..89abcdef 100644
--- a/adder.py
+++ b/adder.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
diff --git a/multiplier.py b/multiplier.py
index 1234567..89abcdef 100644
--- a/multiplier.py
+++ b/multiplier.py
@@ -1,2 +1,2 @@
 def mul(a, b):
-    return a * b
+    return a ** b
 from adder import multiply
<|im_start|>
<|im_end|>
system
<|im_start|>
<|im_end|>
system
<|im_start|>
<|im_end|>
system
<|im_start|>
<|im_end|>
system
"""

#: The mapping-shape: a dominant loop followed by a stub diff — the 7B signature
#: (`dig-transcripts.md` § 2 shape 1). The loop ate the budget; the stub that escapes it is
#: what the run's own attribution recorded as `WOULD_NOT_PARSE`.
LOOP_AND_STUB = """<|im_start|>
<|im_end|>
system
<|im_start|>
<|im_end|>
system
--- a/adder.py
+++ b/adder.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a - b
+    return a + b
def add(a, b):
"""


def _transcribed(candidate: str, task_id: str, completion: str) -> Transcribed:
    """One stored generation, synthetic: a toy prompt and one of the completion fixtures above."""
    return Transcribed(
        candidate=candidate,
        task_id=task_id,
        prompt_sha256="0" * 64,
        prompt=f"Fix the bug in {task_id}.",
        completion=completion,
        attempt=1,
        decision="graded",
    )


# --------------------------------------------------------------------------------------------
# Defect 1: the extends check read text git never parses. A hunk that completes exactly at
# the diff's end is well-formed whatever follows in the completion.
# --------------------------------------------------------------------------------------------


def test_a_hunk_completing_exactly_is_well_formed_despite_trailing_context() -> None:
    """A self-consistent hunk followed by a context line is `WELL_FORMED`.

    The body exactly satisfies its declared counts and the extractor's span stops before the
    trailing context line — the extracted diff is all git receives, and git parses it (the
    3B `belay-2e149603209a` record was APPLIED). The old walk read the line after the diff
    and misnamed the record `hunk-count-mismatch`; a completion that continues after a
    complete diff is not a diff that violates its counts.
    """
    result = classify_completion(SELF_CONSISTENT_HUNK)

    assert result.cause is FineCause.WELL_FORMED, (
        f"a self-consistent hunk was classified {result.cause!r} (detail {result.detail!r}).\n\n"
        "WHY THIS MATTERS: the extracted diff is exactly what `git apply` receives; a line "
        "beyond the extractor's span is text git never parses, so it cannot make the hunk "
        "violate its counts. The old verdict — \"body extends beyond its declared counts\" — "
        "flagged a patch git APPLIED."
    )
    assert "complete" in result.detail, result.detail


def test_the_self_consistent_fixture_parses_under_git_apply_numstat(checkout: Path) -> None:
    """The `WELL_FORMED` verdict for the defect-1 shape agrees with the git oracle.

    `git apply --numstat` is the same parse the attribution layer's oracle uses: a record
    the classifier calls well-formed must be one git reads without complaint, or the walk
    and the checkout layer disagree about a real diff — which is precisely the defect this
    fixture exists to close.
    """
    extraction = extract_patch(SELF_CONSISTENT_HUNK)
    assert isinstance(extraction, Extracted)
    result = git(["apply", "--numstat", "-"], cwd=checkout, stdin=extraction.diff)

    assert result.returncode == 0, (
        f"git apply --numstat refused the self-consistent fixture:\n{result.stderr}\n\n"
        "WHY THIS MATTERS: the walk's WELL_FORMED verdict is a claim about git's own "
        "vocabulary, and git is the authority — the defect being fixed is precisely a walk "
        "verdict git contradicts."
    )


# --------------------------------------------------------------------------------------------
# Defect 2: a counter going negative is git's "corrupt patch" — the invented-counts
# signature, named `hunk-count-mismatch`.
# --------------------------------------------------------------------------------------------


def test_a_body_with_more_lines_than_declared_is_hunk_count_mismatch() -> None:
    """A hunk whose body exceeds its declared counts is the mismatch, not well-formed.

    The 14B `contig-2ef3383b0ce7` record: 25 added lines against a declared 24, so `new`
    goes negative during the walk. git's C loop treats a negative counter as truthy and keeps
    reading past the hunk — "corrupt patch at line 35" — while the old walk exited at
    zero-or-negative and reported "all 1 hunks complete". The overrun is the invented-counts
    signature, and it must wear the mismatch's name.
    """
    result = classify_completion(OVERRUN_HUNK)

    assert result.cause is FineCause.HUNK_COUNT_MISMATCH, (
        f"an overrunning hunk was classified {result.cause!r} (detail {result.detail!r}).\n\n"
        "WHY THIS MATTERS: a body with more lines of a kind than its header declared is the "
        "shape git refuses as a corrupt patch; a walk that reports it well-formed reads the "
        "14B signature as healthy. The overrun must be named, and it is never a death — an "
        "overrun in the first hunk is still the mismatch (`prd.md` D4)."
    )
    assert "exceeds" in result.detail, result.detail


def test_the_overrun_fixture_is_refused_under_git_apply_numstat(checkout: Path) -> None:
    """The `HUNK_COUNT_MISMATCH` verdict for the overrun shape agrees with the git oracle.

    The extracted diff is what git receives; git must refuse it as corrupt, exactly as the
    recorded coarse cause `WOULD_NOT_PARSE` said for the real record — the agreement the
    mapping assertion surfaces per record (`prd.md` R3).
    """
    extraction = extract_patch(OVERRUN_HUNK)
    assert isinstance(extraction, Extracted)
    result = git(["apply", "--numstat", "-"], cwd=checkout, stdin=extraction.diff)

    assert result.returncode != 0, (
        "git apply --numstat parsed the overrun fixture.\n\n"
        "WHY THIS MATTERS: the fixture's whole point is the walk/git disagreement — git "
        "refuses the patch the old walk called well-formed. A fixture git parses would pin "
        "nothing."
    )
    assert "corrupt patch" in result.stderr, result.stderr


def test_a_first_hunk_death_outranks_an_overrun_in_the_same_hunk() -> None:
    """A first-hunk death is still `HUNK_DIES_EARLY` even when the body also overran.

    The body drives `new` negative and then dies on an unprefixed line with counts remaining.
    The death is the walk's stop and the precedence table's first-hunk rule names it
    `hunk-dies-early` (`prd.md` D4) — the overrun is only named when no death ended the walk.
    """
    result = classify_completion(OVERRUN_THEN_DEATH)

    assert result.cause is FineCause.HUNK_DIES_EARLY, (
        f"a first-hunk death beside an overrun was classified {result.cause!r} "
        f"(detail {result.detail!r}).\n\n"
        "WHY THIS MATTERS: the precedence table is unchanged in this respect — a death "
        "outranks the overrun, and the death kind still names the fix the record needs."
    )
    assert result.detail == DeathKind.BARE_LINE.value, result.detail


def test_a_later_hunk_death_outranks_an_overrun() -> None:
    """A later-hunk death outranks an overrun in an earlier hunk.

    Hunk 1 overruns its declared counts and hunk 2 then dies on an unprefixed line. The walk
    records the overrun but keeps walking, so the later death — not the earlier overrun — is
    the verdict's detail: `hunk-count-mismatch` either way, but the record must name the
    hunk that actually stopped it.
    """
    result = classify_completion(OVERRUN_THEN_LATER_DEATH)

    assert result.cause is FineCause.HUNK_COUNT_MISMATCH, (
        f"a later-hunk death beside an earlier overrun was classified {result.cause!r} "
        f"(detail {result.detail!r}).\n\n"
        "WHY THIS MATTERS: both are the mismatch, but the detail must name the hunk the walk "
        "stopped at — an earlier overrun that was recorded and passed over is not the stop."
    )
    assert "hunk 2" in result.detail and "dies early" in result.detail, result.detail


# --------------------------------------------------------------------------------------------
# The regression fixture: a consistent multi-file diff demotes the loop to a marker, never
# the cause — the old extends misfire demoted the whole completion to `im-start-loop`.
# --------------------------------------------------------------------------------------------


def test_a_loop_dominated_completion_with_a_consistent_multifile_diff_is_well_formed() -> None:
    """Loop + consistent multi-file diff → `WELL_FORMED` with the `LOOP_PRESENT` marker.

    Both hunks are internally consistent, so the diff's state outranks the loop (`prd.md`
    D4) — the loop is the mode the model was stuck in, and the diff after it is what the
    verifier would have graded. The old walk's extends misfire on the trailing context line
    made the diff read broken and demoted the whole completion to `im-start-loop`, putting a
    record whose diff was fine in the 7B collapse bucket.
    """
    result = classify_completion(LOOP_AFTER_CONSISTENT_MULTIFILE)

    assert result.cause is FineCause.WELL_FORMED, (
        f"a loop beside a consistent multi-file diff was classified {result.cause!r} "
        f"(detail {result.detail!r}).\n\n"
        "WHY THIS MATTERS: `im-start-loop` is primary only when no well-formed diff follows "
        "it. A consistent two-hunk diff is a diff git would grade; the loop demotes to the "
        "`LOOP_PRESENT` marker, never the cause."
    )
    assert Marker.LOOP_PRESENT in result.markers, (
        "the loop that preceded the well-formed diff was not reported as a marker.\n\n"
        "WHY THIS MATTERS: the marker is the observation (`prd.md` D4); a loop that vanishes "
        "from the record is a detector that stopped reporting."
    )
    assert "2 hunks complete" in result.detail, result.detail


# --------------------------------------------------------------------------------------------
# The mapping-table fix: `im-start-loop` may explain a `WOULD_NOT_PARSE` record — the loop
# ate the budget and the stub diff that escaped it was refused by git.
# --------------------------------------------------------------------------------------------


def test_im_start_loop_allows_would_not_parse_in_the_mapping_table() -> None:
    """`WOULD_NOT_PARSE` joins `IM_START_LOOP`'s allowed set.

    A loop-dominated completion can carry a stub diff that git refused — the dig documented
    it: "the remaining nine escape the loop only near the token cap and write a diff: five
    of them a stub" (`dig-transcripts.md` § 4). The run's own attribution recorded
    `WOULD_NOT_PARSE` for exactly those records; the mapping must allow it beside the loop,
    or every one of them reads as a contradiction the operator must hand-resolve.
    """
    assert Cause.WOULD_NOT_PARSE in FINE_TO_COARSE[FineCause.IM_START_LOOP], (
        "WOULD_NOT_PARSE is not in IM_START_LOOP's allowed set.\n\n"
        "WHY THIS MATTERS: the mapping is the assertion between the fine pass and the run's "
        "own attribution (`prd.md` R3). A loop that ate the budget and a stub diff that was "
        "refused describe the same record; a table that cannot say so reports a systematic "
        "contradiction the evidence never claimed."
    )


def test_a_loop_and_stub_recorded_would_not_parse_agrees_end_to_end() -> None:
    """The join: a loop + stub completion recorded as `WOULD_NOT_PARSE` agrees.

    The fixture classifies `IM_START_LOOP` (the loop dominates and no well-formed diff
    follows), and the recorded coarse cause — what the run's own attribution measured — is
    `WOULD_NOT_PARSE`. Both describe the same rollout from two sides; the record must carry
    `coarse_agrees=True`, not a contradiction.
    """
    assert classify_completion(LOOP_AND_STUB).cause is FineCause.IM_START_LOOP, (
        "the loop-and-stub fixture did not classify as IM_START_LOOP — the end-to-end "
        "assertion below would be testing a fixture that claims a cause it does not produce."
    )
    records = autopsy(
        (_transcribed("toy-a", "task-1", LOOP_AND_STUB),),
        {("toy-a", "task-1"): Cause.WOULD_NOT_PARSE},
    )

    assert records[0].coarse_agrees is True, (
        f"a loop + stub record recorded as WOULD_NOT_PARSE was classified "
        f"{records[0].cause!r} with coarse_agrees=False.\n\n"
        "WHY THIS MATTERS: the mapping assertion surfaced this disagreement in both stored "
        "runs; the fix is to the table, not to the records — a loop and a refused stub are "
        "the same failure seen from both layers."
    )


# --------------------------------------------------------------------------------------------
# Determinism (spec AC1): the fixed rules read the same text the same way twice.
# --------------------------------------------------------------------------------------------


def test_classifying_the_fixed_fixtures_twice_yields_identical_records() -> None:
    """Determinism: the fix's own fixtures classify identically on a second pass.

    The autopsy's documents are compared across runs; the walk changes here must not
    introduce a verdict that depends on iteration order or set hashing.
    """
    fixtures = [
        SELF_CONSISTENT_HUNK,
        OVERRUN_HUNK,
        OVERRUN_THEN_DEATH,
        OVERRUN_THEN_LATER_DEATH,
        LOOP_AFTER_CONSISTENT_MULTIFILE,
        LOOP_AND_STUB,
    ]
    for text in fixtures:
        first = classify_completion(text)
        second = classify_completion(text)
        assert first == second, (
            f"classifying the same fixture twice yielded different records:\n"
            f"  first:  {first.cause!r} {first.detail!r} {sorted(first.markers)}\n"
            f"  second: {second.cause!r} {second.detail!r} {sorted(second.markers)}\n\n"
            "WHY THIS MATTERS: determinism is an acceptance criterion (`prd.md` R4); a walk "
            "whose verdict depends on iteration order or set hashing would fail the slice's "
            "byte-identical document promise."
        )


# --------------------------------------------------------------------------------------------
# The real-git oracle, in the `test_attribution.py:144-162` shape with the developer's own
# configuration scrubbed as `:118-141`.
# --------------------------------------------------------------------------------------------


def git(
    args: list[str], *, cwd: Path, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Real git, with the developer's own configuration switched off.

    The same environment scrubbing `whetstone.verify.repo._git` does, and for the same
    reason: a machine-local `apply.whitespace=fix` or a `hooksPath` would change which of
    these fixtures parses, and the parse/refuse split is the entire claim this oracle makes.
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
    """A one-file git repository that `git apply --numstat` can run against.

    Real git rather than a stub, because the question the oracle answers — *does the shape
    the classifier named parse or refuse* — has one authority, and it is the `git apply`
    that `whetstone.verify.repo` shells out to. Parse-only (`--numstat`) needs no matching
    file content.
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
