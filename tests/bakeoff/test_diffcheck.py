"""The validator: the autopsy's taxonomy consulted online, and the retry decision it implies.

The autopsy classifies a stored completion into exactly one fine cause and its walk was
corrected until it agreed with git on every stored record (`finding.md:69-71`). The validator
reuses that taxonomy **by identity** — `diffcheck.classify_completion` *is*
`autopsy.classify_completion`, asserted below — so the online trigger decision and the offline
autopsy cannot disagree about the same bytes. This file pins the mapping from fine cause to
retry trigger, the fixed diagnosis vocabulary (PRD D8: finite, constant sentences, no
completion-derived numbers), and the offline claim (no inference import, no `mlx`, no `run.py`).

Everything asserted here follows from that contract:

* **The trigger mapping is the taxonomy, both halves.** One fixture per shape, in the dig's
  three dialects (`dig-transcripts.md` § 2): `hunk-count-mismatch` fires; a first-hunk death
  fires only on the `bare-line` and `fence-cut` deaths — `end-of-output` is truncation
  *inferred from shape*, never claimed measured (`finding.md:81-84`), and never retried.
  `well-formed`, `im-start-loop`, `no-diff` and `unrecognised-shape` never fire.
  `header-without-hunk` is parameterised: it stays a non-trigger until the measured-arm
  pre-analysis has evidence to flip it, and the parameter is the only thing that flips it.
* **The vocabulary is finite and constant.** `diagnosis_of` answers one constant sentence per
  trigger, with no `str.format`-shaped placeholder and no digit in any sentence — a number
  would make the retry prompt set unbounded and the seal unfreezable (`run.py:240-252`).
* **The validator classifies; it never authors.** There is no code path that edits a diff; the
  tests assert the raw completions pass through classification unchanged.
* **The decision is deterministic.** Same completion, same verdict, twice.
* **The validator costs no compute.** Its own AST walk refuses any inference import.

No model, no `mlx`, no network: every fixture is a tiny synthetic string, a replica of the
dig's observed shapes, never donor content (`card.md:68-70`).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from whetstone.bakeoff import autopsy
from whetstone.bakeoff import diffcheck as diffcheck
from whetstone.bakeoff.autopsy import (
    DeathKind,
    FineCause,
    classify_completion,
)
from whetstone.bakeoff.diffcheck import Trigger, diagnosis_of, trigger_of

#: The repository root, reached from `tests/bakeoff/` — the git working tree the no-inference
#: walk measures.
REPO_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------------------------
# Completion fixtures — synthetic replicas of the dig's observed shapes (`dig-transcripts.md`
# § 2 shapes 1, 2, 3, 7, 15), toy paths, tiny. Never donor content. The leading spaces on
# context lines are load-bearing: a pasted source line with no prefix is exactly the death
# being pinned.
# --------------------------------------------------------------------------------------------

#: Shape 15, the control: a plain-unified diff whose every hunk completes — `WELL_FORMED`.
WELL_FORMED = """--- a/adder.py
+++ b/adder.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""

#: Shape 3, bare-line death (dominant in 3B): the hunk declares 3/3, the body supplies two
#: lines, then the model pastes the source line verbatim — no leading space, no `+`, no `-`.
#: The walk stops at that line with counts remaining; the death line is unprefixed.
BARE_LINE_STUB = """diff --git a/adder.py b/adder.py
index 1234567..89abcde 100644
--- a/adder.py
+++ b/adder.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a - b
+    return a + b
def add(a, b):
"""

#: Shape 3, fence-cut death: the hunk declares 3/3, the body supplies two lines, and the
#: closing ``` arrives before the counts are exhausted. The walk stops at the fence.
FENCE_CUT_STUB = """```diff
diff --git a/adder.py b/adder.py
--- a/adder.py
+++ b/adder.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a - b
+    return a + b
```
"""

#: Shape 3, end-of-output death (every 7B stub ends this way): the hunk declares 3/3, the body
#: supplies two lines, and the completion simply ends with counts remaining. The inferred
#: truncation shape (`prd.md` D5) — never a measured token cap, and never a trigger.
END_OF_OUTPUT_STUB = """--- a/adder.py
+++ b/adder.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a - b
+    return a + b
"""

#: Shape 2, the overrun (14B's signature): the hunk declares 6/24 and the body supplies 25
#: added lines — one more than declared — so `new` goes negative while the walk consumes it
#: and git refuses the patch as corrupt — `HUNK_COUNT_MISMATCH`.
_ADDED_OVERFLOW = "".join("+    return a + b\n" for _ in range(25))
COUNT_MISMATCH = f"""--- a/adder.py
+++ b/adder.py
@@ -100,6 +100,24 @@
 def add(a, b):
    return a - b
   return a + b
{_ADDED_OVERFLOW} def add(a, b):
   # placeholder comment
   try:
"""

#: Shape 1: the loop collapse — chat-template tokens only, `IM_START_LOOP`.
LOOP_TEXT = "<|im_start|>\n" * 30

#: Shape 15, header without hunk: a `diff --git` header and an index line, then nothing —
#: `HEADER_WITHOUT_HUNK`.
HEADER_ONLY = """diff --git a/adder.py b/adder.py
index 1234567..89abcde 100644
"""

#: Plain prose — the inherited-not-observed `NO_DIFF` shape.
PROSE = "The bug is that `add` subtracts instead of adding.\n"

#: The planted unrecognisable completion: control bytes — `UNRECOGNISED_SHAPE` by name.
GARBAGE = "\x00\x01\x02\x03\x04\x05\x06\x07\x08" * 16

#: The control in CRLF line endings — the same diff, terminator-only difference. The walk
#: bares lines (`patch.py:303-308`), so the classification must not move.
CRLF_WELL_FORMED = WELL_FORMED.replace("\n", "\r\n")

#: The trigger half: every fixture above that must fire a retry, and which one.
TRIGGER_FIXTURES: tuple[tuple[str, Trigger], ...] = (
    (BARE_LINE_STUB, Trigger.HUNK_DIES_EARLY),
    (FENCE_CUT_STUB, Trigger.HUNK_DIES_EARLY),
    (COUNT_MISMATCH, Trigger.HUNK_COUNT_MISMATCH),
)

#: The non-trigger half: every fixture above that must be graded rather than retried, with the
#: cause the fixture must actually classify to (anti-vacuity: a fixture that claims a cause it
#: does not produce proves nothing about the mapping).
NON_TRIGGER_FIXTURES: tuple[tuple[str, FineCause], ...] = (
    (WELL_FORMED, FineCause.WELL_FORMED),
    (LOOP_TEXT, FineCause.IM_START_LOOP),
    (END_OF_OUTPUT_STUB, FineCause.HUNK_DIES_EARLY),
    (HEADER_ONLY, FineCause.HEADER_WITHOUT_HUNK),
    (PROSE, FineCause.NO_DIFF),
    (GARBAGE, FineCause.UNRECOGNISED_SHAPE),
)


# --------------------------------------------------------------------------------------------
# The trigger mapping, both halves.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("completion,expected", TRIGGER_FIXTURES)
def test_the_convertible_shapes_fire_their_trigger(completion: str, expected: Trigger) -> None:
    """A parse-refusal a fresh draw can fix is a trigger, named by the taxonomy's own cause.

    `hunk-count-mismatch` and the first-hunk deaths on a bare line or the closing fence are
    the retry-eligible shapes (PRD D3): the model wrote a diff-shaped response that git would
    refuse to parse, and the retry's whole prior completion is what can fix it.
    """
    result = classify_completion(completion)

    assert trigger_of(result) is expected, (
        f"WHY THIS IS A FAILURE: {completion!r} classified {result.cause!r} "
        f"(detail {result.detail!r}) but the trigger mapping did not fire {expected!r}. A "
        "retry-eligible parse-refusal that does not fire never gets its retry, and the "
        "format-hardening arm measures nothing"
    )


@pytest.mark.parametrize("completion,cause", NON_TRIGGER_FIXTURES)
def test_the_rest_are_left_to_be_graded(completion: str, cause: FineCause) -> None:
    """Every non-trigger shape produces no trigger — each for the reason its cause names.

    The fixture's cause is asserted first so the mapping is never tested against a fixture
    that claims a shape it does not produce. Then the decision: `well-formed` must reach git
    and be graded, the loop has nothing content-side that converts it, and the named terminal
    (`no-diff`, `unrecognised-shape`) is not a format problem to have another go at.
    """
    result = classify_completion(completion)

    assert result.cause is cause, (
        f"WHY THIS IS A FAILURE: {completion!r} classified {result.cause!r}, not {cause!r} "
        "— the fixture does not produce the shape this row claims, so the non-trigger "
        "assertion below would be testing nothing"
    )
    assert trigger_of(result) is None, (
        f"WHY THIS IS A FAILURE: {completion!r} classified {result.cause!r} and the trigger "
        f"mapping fired {trigger_of(result)!r}. {cause.value} must not retry: a retry here "
        "would either burn budget on missing content, re-ask a question no draw can answer, "
        "or re-grade a diff that was never a format problem"
    )


def test_the_end_of_output_death_is_named_and_never_retried() -> None:
    """The truncation shape is the one first-hunk death that must not fire.

    `end-of-output` is *inferred from shape* (`finding.md:81-84`): the runtime gives no finish
    reason, so the death is named from the completion's shape, never claimed as a measured
    token cap. It is also the one death a retry cannot help — the budget ran out, and a fresh
    draw of the same budget would stop at the same place.
    """
    result = classify_completion(END_OF_OUTPUT_STUB)

    assert result.cause is FineCause.HUNK_DIES_EARLY, result
    assert result.detail == DeathKind.END_OF_OUTPUT.value, result
    assert trigger_of(result) is None, (
        f"WHY THIS IS A FAILURE: an end-of-output death fired a retry ({trigger_of(result)!r}). "
        "The completion ended with counts remaining; that is budget truncation, inferred from "
        "shape, and a retry would spend another draw on content the budget never reached"
    )


def test_header_without_hunk_is_parameterised_for_the_measured_arm() -> None:
    """`header-without-hunk` stays a non-trigger until evidence flips it — and only the flag does.

    The measured-arm pre-analysis (`prd.md` R5) may find that a header-only completion is
    retry-eligible — the budget ran out before the first hunk — and the mapping is
    parameterised so the arm can flip it without code churn. Nothing else may move it: the
    default is asserted, and the flipped call is asserted, so the parameter is the only way
    the decision changes.
    """
    result = classify_completion(HEADER_ONLY)

    assert result.cause is FineCause.HEADER_WITHOUT_HUNK, result
    assert trigger_of(result) is None, (
        "WHY THIS IS A FAILURE: header-without-hunk fired a retry by default. The measured "
        "arm has not run; the pre-analysis is what decides this shape, and until it has "
        "evidence, the default is no retry"
    )
    assert (
        trigger_of(result, header_without_hunk_is_trigger=True)
        is Trigger.HEADER_WITHOUT_HUNK
    ), (
        "WHY THIS IS A FAILURE: the parameter the measured arm flips did not fire the "
        "header-without-hunk trigger, so the arm cannot move the mapping without code churn"
    )


def test_the_decision_is_deterministic() -> None:
    """Same completion, same verdict, twice — the validator never consults anything live.

    Determinism is the property that makes the retry decision replayable (PRD R3): a verdict
    that depended on the moment of the call could not be re-derived from a stored transcript,
    and the decision would stop being a pure function of (attempts, validator verdicts).
    """
    for completion, expected in (*TRIGGER_FIXTURES, (WELL_FORMED, None)):
        first = trigger_of(classify_completion(completion))
        second = trigger_of(classify_completion(completion))

        assert first is second is expected, (
            f"WHY THIS IS A FAILURE: classifying {completion!r} twice gave {first!r} then "
            f"{second!r}. An online verdict that is not a pure function of the text cannot be "
            "replayed offline, and the retry decision would not be re-derivable from the "
            "transcript"
        )


def test_a_crlf_completion_classifies_like_its_lf_twin() -> None:
    """CRLF output is the same language as LF to the walk; only the terminator differs.

    The validator is text-pure (`patch.py:303-308` bares the terminator before any rule runs),
    so a CRLF completion must reach the same verdict as its LF twin — never a second,
    terminator-shaped opinion of the same diff.
    """
    lf = classify_completion(WELL_FORMED)
    crlf = classify_completion(CRLF_WELL_FORMED)

    assert (crlf.cause, crlf.detail) == (lf.cause, lf.detail), (
        f"WHY THIS IS A FAILURE: the CRLF completion classified {(crlf.cause, crlf.detail)!r} "
        f"where its LF twin classified {(lf.cause, lf.detail)!r}. A validator whose verdict "
        "moves with the terminator would retry one spelling of a diff and grade the other"
    )
    assert trigger_of(crlf) is trigger_of(lf) is None


# --------------------------------------------------------------------------------------------
# The identity discipline: the taxonomy is imported, never copied, never reimplemented.
# --------------------------------------------------------------------------------------------


def test_the_classifier_and_the_taxonomy_are_the_autopsy_s_by_identity() -> None:
    """`diffcheck` re-exports the autopsy's own objects; a copy could drift from it.

    The validator's whole claim is that its online decision cannot disagree with the offline
    autopsy. That is only true if `classify_completion` and the cause and death enums are the
    autopsy's own objects — a reimplementation would start as a faithful copy and end as a
    second opinion on the fuzzy margin the autopsy already settled (`finding.md:69-71`).
    """
    assert diffcheck.classify_completion is autopsy.classify_completion, (
        "WHY THIS IS A FAILURE: diffcheck.classify_completion is not autopsy.classify_completion. "
        "The taxonomy was copied or wrapped, so the online verdict and the offline autopsy can "
        "disagree about the same bytes without any test noticing"
    )
    assert diffcheck.FineCause is autopsy.FineCause, (
        "WHY THIS IS A FAILURE: the FineCause enum was redefined. The trigger mapping reads "
        "causes, and a second enum with the same values is a second vocabulary that can drift"
    )
    assert diffcheck.DeathKind is autopsy.DeathKind, (
        "WHY THIS IS A FAILURE: the DeathKind enum was redefined. The retryable-death set "
        "reads deaths, and a copy of the enum would decide by strings that look identical "
        "until the autopsy adds a fourth death"
    )
    assert diffcheck.AutopsyResult is autopsy.AutopsyResult, (
        "WHY THIS IS A FAILURE: the AutopsyResult type was redefined. trigger_of's input type "
        "must be the autopsy's own record, or a caller could hand it a look-alike"
    )


# --------------------------------------------------------------------------------------------
# The finiteness rule (PRD D8): a finite, fixed vocabulary, or the seal cannot be frozen.
# --------------------------------------------------------------------------------------------


def test_the_diagnosis_vocabulary_is_finite_fixed_and_constant() -> None:
    """One constant sentence per trigger; no format args; no completion-derived numbers.

    Every retry prompt must be pre-rendered at freeze time (`run.py:240-252`), so the
    vocabulary is the prompt set's cardinality: a `str.format`-shaped placeholder or a number
    in a sentence would make the prompt set unbounded — a sentence is a template for prompts,
    and a template with a hole is not a sentence at all. Numbers are banned because a number
    would have to come from the completion, and the retry prompt must not quote the diff.
    """
    sentences = [diagnosis_of(trigger) for trigger in Trigger]

    assert len(sentences) == len(set(sentences)) == len(Trigger), (
        f"WHY THIS IS A FAILURE: the vocabulary is not a bijection with the trigger set — "
        f"{len(sentences)} sentences for {len(Trigger)} triggers. A missing sentence is a "
        "retry prompt the seal cannot pre-render; a duplicated one is a vocabulary that "
        "cannot tell two shapes apart"
    )
    for sentence in sentences:
        assert sentence.strip() == sentence and len(sentence) > 20, (
            f"WHY THIS IS A FAILURE: a diagnosis sentence is empty or degenerate: "
            f"{sentence!r}. A retry prompt carrying it would tell the model nothing"
        )
        assert "{" not in sentence and "}" not in sentence, (
            f"WHY THIS IS A FAILURE: the sentence {sentence!r} carries a format placeholder. "
            "A sentence with a hole is a template, the prompt set is unbounded, and the seal "
            "cannot be frozen (PRD D8)"
        )
        assert not any(char.isdigit() for char in sentence), (
            f"WHY THIS IS A FAILURE: the sentence {sentence!r} carries a number. Any number "
            "in a diagnosis would have to be derived from the completion, which makes the "
            "prompt set unbounded and leaks diff-derived content into the retry prompt"
        )


def test_every_trigger_has_a_sentence_and_the_sentences_are_the_only_output() -> None:
    """`diagnosis_of` is total over the trigger set, and its range is exactly the vocabulary.

    Total because the seal pre-renders every retry prompt at freeze time: a trigger without a
    sentence is a retry that cannot be posed. The range assertion pins the vocabulary as the
    finite set — if a sentence ever varies with anything, the range grows and this fails.
    """
    rendered = {diagnosis_of(trigger) for trigger in Trigger}

    assert len(rendered) == len(Trigger), (
        "WHY THIS IS A FAILURE: two triggers share a sentence, so a retry prompt would not "
        "say which shape it is answering — and the retry template hash could not tell two "
        "diagnoses apart"
    )
    assert all(isinstance(sentence, str) for sentence in rendered)


# --------------------------------------------------------------------------------------------
# The offline guard: the validator's path imports no inference library, and no `run.py`.
# --------------------------------------------------------------------------------------------

#: Import roots that would mean a model was consulted on the validator's path. Deliberately
#: wider than `mlx`, and including `run.py` itself — the driver that loads the engine
#: (`test_autopsy_guards.py` forbids the same roots minus `run`; the validator must not even
#: reach for the driver's module graph).
FORBIDDEN_IMPORT_ROOTS = frozenset({"mlx", "mlx_lm", "torch", "transformers", "run"})

#: The paths the no-inference walk covers. The validator module, its own test files, and the
#: tests that prove it honest — the autopsy guard's shape
#: (`test_autopsy_guards.py:225-256`), applied to this module's path.
DIFFCHECK_PATHS = (
    "src/whetstone/bakeoff/diffcheck.py",
    "tests/bakeoff/test_diffcheck.py",
)


def _imported_roots(source: bytes) -> set[str]:
    """The top-level package of every import in `source`, function-local ones included.

    `ast.walk` rather than a top-of-file read: an import moved inside a function would
    otherwise be invisible — which is exactly where a "just this once" model call would go.
    Relative imports (`from .x import y`) are invisible too, by `node.level == 0`: the
    documented porting-trap shape (`docs/ROADMAP.md` § 7), and this path is first-party code
    that imports by absolute name.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source, filename="<source>")):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_walk_reports_an_import_it_is_given() -> None:
    """Anti-vacuity control: the walk must actually observe imports.

    The guard below asserts an absence, which a parser that saw nothing would satisfy. Fed a
    source that imports `json`, the walk must report `json` — only a walk that reads real
    imports can then be trusted when it reports none on the validator's path.
    """
    assert "json" in _imported_roots(b"import json\n"), (
        "the AST walk did not see the stdlib import it was handed, so the no-inference "
        "assertions below would pass by seeing nothing at all."
    )


def test_a_planted_inference_import_is_seen_and_flagged() -> None:
    """The guard's predicate, watched failing: a planted inference import must be flagged.

    `CONTRIBUTING.md:56-60` — an honesty guard must be proven able to fail. None of the
    validator paths may import a forbidden root today, so the parametrized guard below would
    pass without ever having refused anything; this pins the detection half by feeding the
    walk a source that does exactly what the guard forbids and asserting the forbidden
    intersection is reported.
    """
    roots = _imported_roots(b"import json\n\nfrom mlx_lm import load\n")
    assert roots & FORBIDDEN_IMPORT_ROOTS == {"mlx_lm"}, roots


@pytest.mark.parametrize("relative", DIFFCHECK_PATHS)
def test_the_validator_path_imports_no_inference_library(relative: str) -> None:
    """The validator costs no compute; an import here would spend some.

    The validator runs at grading time, before the verifier — the retry decision must be
    offline and instantaneous, or the harness would charge a model call per rollout just to
    decide whether to make another one. The test files are covered too, because a fixture
    that generated its own completions would make the module's own guarantee untestable.

    Files that have not landed yet are skipped, not silently dropped — walked the moment they
    exist.
    """
    path = REPO_ROOT / relative
    if not path.is_file():
        pytest.skip(f"{relative} does not exist yet — walked when it lands")

    roots = _imported_roots(path.read_bytes())

    assert not roots & FORBIDDEN_IMPORT_ROOTS, (
        f"{relative} imports {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}.\n\n"
        "WHY THIS IS A FAILURE: the validator exists to decide retries at grading time, "
        "offline. An inference import here means the decision needs the model back, and "
        "every completion costs a generation pass before it can even be classified."
    )
    assert roots, (
        f"{relative} contains no import at all, so the assertion above holds for a file "
        "nothing was checked against. A guard that walks a set of files must find imports "
        "in them (`CONTRIBUTING.md:60`)."
    )
