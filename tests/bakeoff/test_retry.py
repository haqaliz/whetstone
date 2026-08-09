"""The retry prompt: first-attempt prompt plus one finite diagnosis sentence, never the completion.

The format-hardening wall is that candidates write diffs git refuses to parse. The retry
converts: re-ask the model, bounded and only when the evidence says the attempt was
convertible, with a prompt the run's own seal will accept — which forces the retry prompt
to be a pure function of `(first-attempt prompt, trigger)` (PRD D8, spec B1). The prior
completion is deliberately **absent**: any completion-derived content would make the prompt
set unbounded, and the seal (`run.py:240-252`) refuses prompts whose hash is not in the
frozen `posed` map.

Everything asserted here follows from that contract:

* **`retry_prompt` composes exactly three parts** — the first-attempt prompt, the fixed
  `RETRY_INSTRUCTION`, and exactly one sentence from the diagnosis vocabulary — and nothing
  else: no completion, no attempt number, no verdict detail.
* **The retry vocabulary is finite and fixed.** The instruction and every diagnosis sentence
  carry no format placeholder and no digit — a sentence with a hole is a template for an
  unbounded prompt set, and a number would have to be derived from the completion. The
  diffcheck finiteness rule (`test_diffcheck.py:327-358`) is re-asserted here at the
  composition level, over the exact material a retry prompt appends.
* **`retry_template_sha256` is a digest of the fixed material**, so aspect `contract-report`
  can publish it as a contract field: it moves on any byte change to the instruction or a
  sentence (a template edit voids the run, like any other), and equals the digest of the
  same content twice.

No model, no `mlx`, no network, no `run.py`, no `scoring`: the builder is pure string work,
and the module's own no-inference AST walk refuses the inference and driver roots — the
same walk shape as `test_autopsy_guards.py:225-256` and `test_diffcheck.py:441-469`.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from whetstone.bakeoff import diffcheck
from whetstone.bakeoff.diffcheck import Trigger, diagnosis_of
from whetstone.bakeoff.retry import RETRY_INSTRUCTION, retry_prompt, retry_template_sha256

#: The repository root, reached from `tests/bakeoff/` — the git working tree the no-inference
#: walk measures.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: A stand-in first-attempt prompt. The retry builder appends to whatever it is handed and
#: never reads it, so the identity of this fixture is irrelevant beyond being a non-empty
#: string the composed result can be asserted against.
FIRST = "Fix the bug.\n\nThe failing tests must pass.\n"


# --------------------------------------------------------------------------------------------
# The retry prompt: exactly the three parts, in a fixed order, pure.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("trigger", Trigger)
def test_retry_prompt_composes_the_prompt_the_instruction_and_one_diagnosis(
    trigger: Trigger,
) -> None:
    """A retry prompt is the first prompt plus the fixed instruction plus one sentence.

    The order is load-bearing: the model has seen the first-attempt prompt before, and the
    instruction then the diagnosis reads as "this failed, here is why, do it right this
    time". Nothing else may be appended — in particular no completion-derived content (B1),
    which would make the prompt set unbounded and the seal unfreezable.
    """
    retried = retry_prompt(FIRST, trigger)

    assert retried.startswith(FIRST), (
        f"WHY THIS IS A FAILURE: the retry prompt dropped or rewrote the first-attempt "
        f"prompt ({retried!r}). The retry is a second draw of the same question; a prompt "
        "that does not carry the question is not a retry"
    )
    tail = retried[len(FIRST):]
    assert tail == "\n\n" + RETRY_INSTRUCTION + "\n" + diagnosis_of(trigger), (
        f"WHY THIS IS A FAILURE: the retry prompt appends {tail!r} rather than the fixed "
        "instruction plus exactly one diagnosis sentence. Any other content is either "
        "completion-derived (unbounded, unfreezable) or a vocabulary the freeze cannot "
        "pre-render"
    )


@pytest.mark.parametrize("trigger", Trigger)
def test_retry_prompt_is_a_pure_function_of_prompt_and_trigger(trigger: Trigger) -> None:
    """Same (prompt, trigger), same retry prompt — twice, and across the trigger set.

    Purity is what makes the prompt set pre-renderable at freeze time: `freeze` poses
    `retry_prompt(render_prompt(...), trigger)` per trigger, so a prompt that varied with
    anything else could not be sealed. It is also what makes the retry decision replayable
    (PRD R3) — a stored transcript re-derives exactly what was asked.
    """
    first = retry_prompt(FIRST, trigger)
    second = retry_prompt(FIRST, trigger)

    assert first == second, (
        f"WHY THIS IS A FAILURE: retry_prompt({FIRST!r}, {trigger!r}) answered {first!r} "
        f"then {second!r}. A builder that is not a pure function of its two arguments "
        "cannot be pre-rendered at freeze time, and the seal would abort every run"
    )
    assert retry_prompt(FIRST, trigger) != retry_prompt(FIRST + "\n", trigger), (
        "WHY THIS IS A FAILURE: two different first-attempt prompts produced the same "
        "retry prompt, so the retry would not carry the question it is a second draw of"
    )


def test_two_triggers_never_share_a_retry_prompt() -> None:
    """The diagnosis sentences are distinct, so the retry prompt says which shape it answers.

    A retry prompt that could not tell `hunk-count-mismatch` from `hunk-dies-early` would
    ask the model to fix a shape it was not shown — and the retry template hash could not
    distinguish two diagnoses it must be able to distinguish.
    """
    rendered = {retry_prompt(FIRST, trigger) for trigger in Trigger}

    assert len(rendered) == len(Trigger), (
        f"WHY THIS IS A FAILURE: the trigger set rendered {len(rendered)} distinct retry "
        f"prompts for {len(Trigger)} triggers. A shared prompt is a vocabulary that cannot "
        "tell two shapes apart"
    )


# --------------------------------------------------------------------------------------------
# The finiteness rule (PRD D8), re-asserted at the composition level: no hole, no digit.
# --------------------------------------------------------------------------------------------


def test_the_retry_instruction_and_the_vocabulary_are_finite_fixed_and_constant() -> None:
    """The whole fixed tail — instruction plus every sentence — has no format hole and no digit.

    The diffcheck finiteness assertion (`test_diffcheck.py:327-358`) covers the sentences;
    this re-asserts the same rule over the instruction and over the exact material a retry
    prompt appends. A placeholder is a template for an unbounded prompt set, and the seal
    can only be frozen over a set it can enumerate; a number would have to be derived from
    the completion, which B1 forbids outright.
    """
    material = [RETRY_INSTRUCTION, *(diagnosis_of(trigger) for trigger in Trigger)]

    assert len(material) == 1 + len(Trigger), (
        "WHY THIS IS A FAILURE: the fixed material is not one instruction plus one sentence "
        "per trigger, so the retry prompt set's cardinality is not |first prompts| x "
        "|vocabulary| and the freeze cannot enumerate it"
    )
    for part in material:
        assert part.strip() == part and len(part) > 20, (
            f"WHY THIS IS A FAILURE: a fixed part of the retry prompt is empty or "
            f"degenerate: {part!r}"
        )
        assert "{" not in part and "}" not in part, (
            f"WHY THIS IS A FAILURE: the fixed part {part!r} carries a format placeholder. "
            "A sentence with a hole is a template for an unbounded prompt set, and the seal "
            "cannot be frozen (PRD D8)"
        )
        assert not any(char.isdigit() for char in part), (
            f"WHY THIS IS A FAILURE: the fixed part {part!r} carries a number. Any number "
            "in the retry prompt would have to be derived from the completion, which is "
            "exactly the unboundedness B1 removes"
        )


# --------------------------------------------------------------------------------------------
# The retry template hash: a contract field's value, published by aspect contract-report.
# --------------------------------------------------------------------------------------------


def test_retry_template_sha256_is_the_digest_of_the_fixed_material() -> None:
    """The contract field's value, recomputed here from the same bytes a reader would hold.

    The digest must be reproducible by an outside reader with nothing but the instruction
    and the vocabulary — the same recompute property as `prompt_hash`
    (`rendering.py:267-279`). Spelling the construction again in the test is what pins it:
    a builder that quietly reordered or dropped a sentence would move the hash with no
    test noticing.
    """
    material = "\n".join((RETRY_INSTRUCTION, *(sorted(diagnosis_of(t) for t in Trigger))))
    expected = hashlib.sha256(material.encode("utf-8")).hexdigest()

    assert retry_template_sha256() == expected, (
        "WHY THIS IS A FAILURE: retry_template_sha256 is not the digest of the instruction "
        "plus the sorted vocabulary sentences, so the contract field could disagree with "
        "the material the run actually appends"
    )
    assert retry_template_sha256() == retry_template_sha256(), (
        "WHY THIS IS A FAILURE: the digest is not a pure function of the fixed material, so "
        "a reader recomputing it from the published vocabulary would disagree with the run"
    )


def test_retry_template_sha256_moves_when_a_sentence_moves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sentence edit is a template edit: it moves the digest, which voids the run.

    The digest is what the report publishes, so a template change must move it — otherwise
    two runs under different retry instructions would publish one hash (PRD M7b applied to
    the retry vocabulary). The edit is made through `DIAGNOSES`, the one place a sentence
    lives, and the digest is recomputed at call time so the change is seen.
    """
    before = retry_template_sha256()
    edited = {
        **diffcheck.DIAGNOSES,
        Trigger.HUNK_COUNT_MISMATCH: "The patch's hunks are miscounted; rewrite it.",
    }
    monkeypatch.setattr(diffcheck, "DIAGNOSES", edited)

    after = retry_template_sha256()

    assert after != before, (
        f"WHY THIS IS A FAILURE: editing a diagnosis sentence left the digest at {before!r}. "
        "A template edit that does not move the contract field is an edit a published run "
        "cannot be checked against"
    )
    assert len(after) == 64 and len(before) == 64, (
        "WHY THIS IS A FAILURE: the digest is not a hex SHA-256, so it could not be "
        "compared across runs by a reader"
    )


# --------------------------------------------------------------------------------------------
# The offline guard: the retry path imports no inference library, no driver, no scoring.
# --------------------------------------------------------------------------------------------

#: Import roots that would mean a model was consulted on the retry path, or that the retry
#: reached for the driver that loads one. Deliberately wider than `mlx`, and including
#: `run.py` and `scoring` — the retry wrapper must not even reach for the driver's module
#: graph, and scoring owns the verifier-facing half this module must stay upstream of.
FORBIDDEN_IMPORT_ROOTS = frozenset({"mlx", "mlx_lm", "torch", "transformers", "run", "scoring"})

#: The paths the no-inference walk covers: the retry module and its own test files — the
#: guard's shape from `test_autopsy_guards.py:225-256`, applied to this module's path.
#: `test_retry_seal.py` composes `freeze` + `Sealed` and is deliberately not walked: it is a
#: run.py-wiring test, like `test_run_transcript.py`, and wiring tests may import the driver.
RETRY_PATHS = (
    "src/whetstone/bakeoff/retry.py",
    "tests/bakeoff/test_retry.py",
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
    imports can then be trusted when it reports none on the retry's path.
    """
    assert "json" in _imported_roots(b"import json\n"), (
        "the AST walk did not see the stdlib import it was handed, so the no-inference "
        "assertions below would pass by seeing nothing at all."
    )


def test_a_planted_inference_import_is_seen_and_flagged() -> None:
    """The guard's predicate, watched failing: a planted inference import must be flagged.

    `CONTRIBUTING.md:56-60` — an honesty guard must be proven able to fail. None of the
    retry paths may import a forbidden root today, so the parametrized guard below would
    pass without ever having refused anything; this pins the detection half by feeding the
    walk a source that does exactly what the guard forbids and asserting the forbidden
    intersection is reported.
    """
    roots = _imported_roots(b"import json\n\nfrom mlx_lm import load\n")
    assert roots & FORBIDDEN_IMPORT_ROOTS == {"mlx_lm"}, roots


@pytest.mark.parametrize("relative", RETRY_PATHS)
def test_the_retry_path_imports_no_inference_library(relative: str) -> None:
    """The retry costs no compute; an import here would spend some — or reach the driver.

    The retry wrapper runs at grading time, before the verifier — every retry decision must
    be offline and instantaneous, or the harness would charge a model call per rollout just
    to decide whether to make another one. The test files are covered too, because a
    fixture that generated its own completions would make the module's own guarantee
    untestable.

    Files that have not landed yet are skipped, not silently dropped — walked the moment
    they exist.
    """
    path = REPO_ROOT / relative
    if not path.is_file():
        pytest.skip(f"{relative} does not exist yet — walked when it lands")

    roots = _imported_roots(path.read_bytes())

    assert not roots & FORBIDDEN_IMPORT_ROOTS, (
        f"{relative} imports {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}.\n\n"
        "WHY THIS IS A FAILURE: the retry exists to decide retries at grading time, "
        "offline. An inference import here means the decision needs the model back; an "
        "import of run.py or scoring means the retry reached for the driver that loads "
        "one, dragging the whole module graph onto the retry path."
    )
    assert roots, (
        f"{relative} contains no import at all, so the assertion above holds for a file "
        "nothing was checked against. A guard that walks a set of files must find imports "
        "in them (`CONTRIBUTING.md:60`)."
    )
