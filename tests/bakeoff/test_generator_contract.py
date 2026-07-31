"""Pins the seam every later phase substitutes: one method, deterministic, and mlx-free.

The failure this prevents is not one bug but a class of them, and all three members of it are
cheap to introduce and expensive to notice.

**First: a model reached at import time.** The bake-off is the first inference-carrying code in
this repository. If ``mlx_lm`` is imported at module scope anywhere the suite imports
unconditionally, then `uv run pytest` stops being runnable in the environment CI actually
builds — `.github/workflows/ci.yml:32` runs the suite under a plain `uv sync`, and the `mlx`
extra (`pyproject.toml:29`) is not in it. The failure mode is worse than a red build: the fix
under deadline is to add `mlx-lm` to the `dev` group, which is precisely the thing
``pyproject.toml:26-29`` refuses, because a dev-group inference library is one careless import
away from the reward path. So the import discipline is asserted here rather than intended, and
it is asserted **against a tree where mlx is forcibly absent** — not against this machine's
luck.

**Second: a stub that is not actually deterministic.** Every test in aspects 2 and 3 substitutes
this stub for a real base. If two calls with the same prompt can differ — because the stub reads
a mapping the caller still holds and can mutate, say — then a failure in a *later* aspect is
attributable to nothing: the harness under test and the double it was measured with both moved.
Determinism is the only property a test double owes, and it is stated as an assertion here so no
later test has to take it on trust.

**Third: a silent empty answer.** A stub asked for a prompt it holds no answer for must raise,
not return `""`. ``verify_strict(task, "")`` is charged `FAIL` at ``patch-apply``
(``liveness.py:14-20``), indistinguishable from a wrong fix — so a stub that answered an unknown
prompt with the empty string would let a *mis-wired test* read exactly like a *model that failed
the task*. That is spec AC4's confusion arriving through the back door, in the fixture rather
than in the extractor.

**And the claim the package's own docstring makes is checked here too.** The exemption that
keeps ``bakeoff`` out of the AST ban (``tests/test_reward_path_scope_is_partitioned.py``) rests
on the dependency running one way: bake-off imports ``whetstone.verify``, and nothing guarded
imports bake-off. Nothing enforced that. The AST ban does **not**:
``_is_inference_import("whetstone.bakeoff.generator")`` is `False`, because `bakeoff` and
`generator` are not inference-shaped names — so a guarded module could import this package today
and every guard in the tree would stay green. ``test_no_module_on_the_reward_path_imports_the_
bakeoff_package`` closes that, and it is the assertion the written exemption is worth.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from whetstone.bakeoff.generator import Generator, StubGenerator, UnstubbedPrompt

#: Two prompts and their answers, the smallest mapping that can show a stub *selecting* rather
#: than returning a constant. One entry would be satisfied by a stub that ignored its argument
#: entirely, which is a stub that would make every later substitution meaningless.
ANSWERS = {
    "fix the off-by-one in slice()": "--- a/x.py\n+++ b/x.py\n@@\n-i + 1\n+i\n",
    "fix the missing import": "--- a/y.py\n+++ b/y.py\n@@\n+import os\n",
}

#: Run in a **fresh interpreter** with every ``mlx`` import forcibly refused, so the answer is
#: about this package's imports and not about whether this particular machine happens to have
#: run ``uv sync --extra mlx``. A test that merely checked ``sys.modules`` inside the running
#: suite would report success on a laptop where mlx is absent and would keep reporting it after
#: someone added a module-scope ``import mlx_lm`` on a laptop where it is present.
_NO_MLX_PROBE = """
import sys

BANNED = ("mlx", "mlx_lm")


class Refuse:
    \"\"\"A meta-path finder that makes mlx unimportable, however this venv is provisioned.\"\"\"

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BANNED:
            raise ImportError(f"mlx is absent in this environment (refused {fullname!r})")
        return None


sys.meta_path.insert(0, Refuse())
for name in [n for n in sys.modules if n.split(".")[0] in BANNED]:
    del sys.modules[name]

# Anti-vacuity: if the blocker did not bite, the import below would prove nothing at all on a
# machine that has the mlx extra installed. Where mlx is genuinely absent this arm is satisfied
# by the absence itself; where it is installed, the blocker is what satisfies it, and that is
# the case this arm exists for.
try:
    import mlx_lm
except ImportError:
    pass
else:
    raise SystemExit("BLOCKER-INERT: mlx_lm imported despite the meta-path refusal")

import whetstone.bakeoff
import whetstone.bakeoff.generator

print("IMPORTED-WITHOUT-MLX")
"""


def test_the_stub_answers_the_same_prompt_the_same_way_every_time() -> None:
    """Determinism, asserted on bytes: the one property a test double owes its callers.

    Byte-identical rather than merely equal, because what aspects 2 and 3 will do with this
    output is hash it and feed it to a diff extractor, and both of those read bytes.
    """
    stub = StubGenerator(ANSWERS)
    prompt = "fix the off-by-one in slice()"

    first = stub.generate(prompt)
    repeats = [stub.generate(prompt) for _ in range(5)]

    assert all(answer.encode("utf-8") == first.encode("utf-8") for answer in repeats), (
        f"the stub returned differing text for the same prompt: {first!r} then {repeats!r}.\n\n"
        "WHY THIS IS A FAILURE: every later test in this slice substitutes this stub for a real"
        " base, so a stub that can answer the same prompt two ways makes those tests"
        " unattributable — a red result would be consistent with a broken harness AND with a"
        " moving double, and nothing in the failure output would say which."
    )


def test_the_stub_selects_on_the_prompt_rather_than_returning_a_constant() -> None:
    """Anti-vacuity for determinism: a stub that ignores its argument is trivially determinstic.

    ``return ""`` satisfies the repeatability assertion above perfectly. What makes the seam
    worth having is that the prompt reaches the other side of it, so that is asserted directly.
    """
    stub = StubGenerator(ANSWERS)
    answers = {prompt: stub.generate(prompt) for prompt in ANSWERS}
    assert answers == ANSWERS, (
        f"the stub did not return the answer it was built with: {answers!r} vs {ANSWERS!r}.\n\n"
        "WHY THIS IS A FAILURE: a double that returns the same text whatever it is asked would"
        " pass every repeatability check in this file while proving nothing about the seam. If"
        " the prompt does not reach the generator, then no test that substitutes this stub is"
        " testing that the harness built a prompt at all."
    )


def test_two_stubs_built_from_the_same_answers_agree() -> None:
    """Determinism across instances, which is what determinism across processes reduces to here.

    A stub that memoised its first answer, or seeded anything from ``id()`` or the clock, would
    pass the repeated-call check on one instance and fail this one.
    """
    prompt = "fix the missing import"
    assert StubGenerator(ANSWERS).generate(prompt) == StubGenerator(ANSWERS).generate(prompt)


def test_mutating_the_mapping_a_stub_was_built_from_does_not_change_its_answers() -> None:
    """The stub owns its answers; the caller's dict is a constructor argument, not shared state.

    Without a defensive copy the stub's determinism is a property of every *caller's* discipline
    rather than of the stub — and the caller here is a future test fixture that may reuse one
    module-level dict across a parameterised run. This is watched most easily as its opposite:
    delete the copy in ``__post_init__`` and this test is the only one in the file that notices.
    """
    answers = dict(ANSWERS)
    stub = StubGenerator(answers)
    prompt = "fix the missing import"
    before = stub.generate(prompt)

    answers[prompt] = "--- a/z.py\n+++ b/z.py\n@@\n+raise SystemExit\n"

    assert stub.generate(prompt) == before, (
        "mutating the caller's mapping changed what the stub returns.\n\n"
        "WHY THIS IS A FAILURE: the stub is the fixed point every later measurement is taken"
        " against. If it aliases a mapping someone else holds, then its answers depend on"
        " whatever else ran in the same session, and a determinism claim made about it is a"
        " claim about test-ordering luck."
    )


def test_a_prompt_the_stub_holds_no_answer_for_raises_rather_than_returning_empty() -> None:
    """A missing answer is a wiring bug; an empty string is a model that produced no diff.

    Those two must never be spelled the same way. ``verify_strict(task, "")`` is charged FAIL at
    ``patch-apply`` (``liveness.py:14-20``), so a stub that answered an unknown prompt with `""`
    would let a test that mis-built its prompt read as a base model that got the task wrong —
    spec AC4's confusion, arriving through the fixture instead of through the extractor.
    """
    stub = StubGenerator(ANSWERS)

    with pytest.raises(UnstubbedPrompt) as raised:
        stub.generate("a prompt nobody stubbed")

    assert "a prompt nobody stubbed" in str(raised.value), (
        f"the refusal did not name the prompt it refused: {raised.value!r}.\n\n"
        "WHY THIS IS A FAILURE: the whole value of raising here instead of returning empty text"
        " is that the person reading the traceback learns which prompt went unmatched. A refusal"
        " that does not name it costs the reader the same debugging session an empty string"
        " would have cost them."
    )


def test_the_stub_satisfies_the_generator_protocol_structurally() -> None:
    """The seam is real at runtime, not only in the type checker's opinion of it.

    ``mypy`` runs over ``src/`` only (``pyproject.toml``: ``files = ["src"]``), so nothing type
    checks this file — a conformance that existed solely as an annotation here would be
    unchecked by anything. ``isinstance`` against a ``runtime_checkable`` protocol is checked.

    But ``isinstance`` on a protocol checks **only that the attribute exists**, not what it
    accepts: a ``generate(self)`` taking no prompt passes it. So the signature is compared to
    the protocol's own, which is the part that would actually break a caller.
    """
    stub = StubGenerator(ANSWERS)
    assert isinstance(stub, Generator), (
        "StubGenerator does not satisfy the Generator protocol at runtime.\n\n"
        "WHY THIS IS A FAILURE: the protocol is the entire point of this phase — it is what"
        " lets aspect 2's runner be tested with no model and aspect 4 swap a real one in"
        " unchanged. A stub that does not satisfy it means the two halves of that swap were"
        " never the same shape, and the substitution would be discovered to be a fiction at the"
        " moment the real adapter lands."
    )

    expected = inspect.signature(Generator.generate)
    actual = inspect.signature(StubGenerator.generate)
    assert actual == expected, (
        f"the stub's generate{actual} does not match the protocol's generate{expected}.\n\n"
        "WHY THIS IS A FAILURE: isinstance against a runtime_checkable protocol asserts that an"
        " attribute called 'generate' exists and nothing more, so a double whose method takes"
        " different arguments passes the check above and fails at the call site. The protocol is"
        " only a seam if both sides of it accept the same call."
    )


def test_an_object_that_lacks_the_method_is_not_a_generator() -> None:
    """Anti-vacuity for the check above: ``isinstance`` must be able to say no.

    A ``runtime_checkable`` protocol with no members returns True for every object alive, so the
    conformance assertion would hold against a protocol that had quietly lost its method — for
    instance if ``generate`` were moved into a base class the protocol no longer names.
    """

    class NotAGenerator:
        def complete(self, prompt: str) -> str:
            return ""

    assert not isinstance(NotAGenerator(), Generator)
    assert not isinstance(object(), Generator)


def test_the_package_imports_with_mlx_absent() -> None:
    """CI's real state, reproduced deliberately: no `mlx` anywhere, and the package still loads.

    Run in a subprocess with a meta-path finder that refuses every ``mlx``/``mlx_lm`` import,
    because the honest question is "does this package import without mlx", not "did this machine
    happen to lack it today". The subprocess proves its own blocker bites before it proves
    anything about the package.

    Scope note: this covers ``whetstone.bakeoff`` and ``whetstone.bakeoff.generator``, the
    modules that must import unconditionally. The MLX adapter that lands in a later phase is
    deliberately *not* covered — it is the one module allowed to need mlx, and its own tests skip
    loudly when the extra is absent (``tests/conftest.py:66-69`` on why the skip must be loud).
    """
    probe = subprocess.run(
        [sys.executable, "-c", dedent(_NO_MLX_PROBE)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent,
    )

    assert probe.returncode == 0 and "IMPORTED-WITHOUT-MLX" in probe.stdout, (
        f"importing whetstone.bakeoff without mlx failed (exit {probe.returncode}).\n"
        f"stdout: {probe.stdout}\nstderr: {probe.stderr}\n\n"
        "WHY THIS IS A FAILURE: `.github/workflows/ci.yml:32` runs the suite under a plain `uv"
        " sync`, which does not install the `mlx` extra, so a module-scope `import mlx_lm`"
        " anywhere the suite imports unconditionally makes the whole suite uncollectable there."
        " The tempting fix — moving `mlx-lm` into the `dev` group — is the one `pyproject.toml"
        ":26-29` refuses, because a dev-group inference library is one careless import away from"
        " the reward path. Keep the import inside the adapter module instead."
    )
    assert "BLOCKER-INERT" not in probe.stdout, (
        "the probe's mlx blocker did not bite, so its success proves nothing.\n\n"
        "WHY THIS IS A FAILURE: the point of the subprocess is to answer the question with mlx"
        " forcibly absent. If the meta-path refusal is not in effect, this test degrades into"
        ' "mlx happens not to be installed here", which is exactly the machine-dependent answer'
        " it was written to replace."
    )
