"""What a base model is shown, fixed and disclosed before any number exists — and what it isn't.

This module is the *generation contract*: a `Task` in, one prompt string out, plus a digest of
that string. It is deliberately the least clever file in the bake-off, and the two reasons are
worth stating because each is a failure this module exists to prevent.

**One: the prompt must never contain the operator's tests.** `task.test_blobs` is the whole
provenance boundary (`whetstone.verify.task`). STRICT restores every one of those files from
golden *after* applying the patch and grades against them, and refuses outright any patch that
touches one of their paths. Their contents are therefore the answer key. Quoting them here would
make cheat 6 — *special-casing the known input* (`docs/ROADMAP.md` § 3) — the cheapest strategy
available to any base, and cheat 6 is precisely the residual that no execution-grounded check can
catch: a patch returning the graded answers for the graded inputs genuinely makes the graded
tests pass. Nothing downstream could tell that apart from a fix. Note what the defence is *not*:
the sandbox allows `file-read*` wholesale (`sandbox.py:12-18`), so the policy is not read-blind
and this module cannot claim to make it so. The claim is narrower and honest — the prompt does
not hand the key over for free. `tests/bakeoff/test_prompt_contract.py` holds that shut against
the whole decoded blob and against its revealing lines individually.

The declared `fail_to_pass` node ids *are* included, and that is a distinction rather than an
inconsistency. A node id is what the task asks the policy to fix; it names a test without
revealing its body. `tests/test_addition.py::test_add_is_addition` says which assertions must go
green and nothing whatever about what they assert.

**Two: the contract is fixed and disclosed, never tuned.** PRD M7b: the prompt has no precedent
to inherit, and iterating it against the scored result is optimising on the outcome — so the
rendered contract is hashed into the run's provenance block (M8) and *any* change to it after the
first scored run invalidates that run and restarts it. That rule is only enforceable if the hash
moves when the prompt moves and stays put when nothing does. Hence `prompt_hash`, and hence the
plainness: every section below is a module constant, assembled in a fixed order, with **no set,
no `dict` iteration keyed on anything the interpreter hashes, and nothing read from the clock,
the environment, or the filesystem.** A renderer that iterated a `set` of node ids would be
byte-stable within a process and different between two — measured, not hypothesised — which
would make M7b's invalidation rule fire on runs where nothing had changed and drown the one
signal that reveals a genuinely edited contract. `sandbox.py` pins `PYTHONHASHSEED=0` for the
*reward*; this module runs outside the sandbox and inherits no such pin.

**Three: the prompt shows the source, and that is a disclosed handicap on what the number means.**
Until this slice the prompt carried the problem statement and the node ids and no code whatever.
Measured against a real base over three real tasks, every rollout came back `NOT_APPLIED`: a
unified diff is written out of a file's exact context lines, and the base had never seen the file.
That is not a hard task, it is an impossible one, and a bake-off run that way would compare
prompts rather than bases. So the non-test files the task's reference patch touches are rendered
here, as they stand at `base_commit` — the standard SWE-bench **oracle** setting.

**What it costs, stated here because this is where it is spent.** The file set is derived from the
reference patch, which is to say **from the location of the answer**. The prompt therefore tells
the base *which files to change*, and a task posed this way is easier than the real setting, where
finding the file is part of the work. Every figure produced under this contract is a figure about
the oracle setting and must be published as one; it is an upper bound on what the same base would
do given only the bug report, and nothing here licenses quoting it as retrieval-free performance.
`whetstone.bakeoff.sources` carries the same statement at the derivation.

**The held-test ban is unchanged and is now load-bearing rather than structural.** It used to hold
because this module read two fields and no files; it now renders whatever mapping it is handed, so
it is enforced instead of assumed: a `sources` map naming any key of `task.test_blobs` is
**refused**, and an empty map is refused too, because rendering the pre-oracle question would put
two different experiments under one denominator.

**Deliberately outside the reward path.** See the package docstring: nothing under `verify/` or
`tasks/` may import this. Stdlib only — `hashlib`, `re` and string formatting; in particular this
module reads no file and takes the sources as an argument, so nothing about the rendered contract
depends on the filesystem the renderer happened to run on. No model is consulted here; this file
builds the question, and something else entirely decides what the answer earns.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping

from whetstone.verify.task import Task

#: The opening line. Names the task family in one sentence, because a base handed a bare bug
#: report and a list of node ids has to infer what kind of artifact is wanted, and inferring it
#: differently per base is variance in the measurement rather than in the bases.
_PREAMBLE = "You are fixing a bug in a Python repository."

#: The operator's own description of the defect, verbatim under the heading. `Task` guarantees it
#: is a `str` and nothing else about it — it may be a sentence or a full issue thread — so it is
#: interpolated rather than reformatted. Rewriting an operator's problem statement is the first
#: step onto the tuning slope M7b forbids.
_PROBLEM_HEADING = "# Problem"

#: The declared `fail_to_pass` set, introduced by what it *means*. "These fail today and must
#: pass" is the task's actual success condition, stated once, so the base is answering the
#: question the verifier grades rather than a paraphrase of it.
_TESTS_HEADING = "# Tests that must pass"
_TESTS_INTRO = (
    "These pytest node ids fail against the code as it stands and must pass after your change:"
)

#: The patch-scope rule, disclosed rather than left to be discovered by refusal. STRICT rejects a
#: patch touching any operator-held test path before anything runs, so a base that edits a test
#: scores zero for a reason that is about the rules rather than about its ability — and P1 exists
#: to compare abilities. Telling every base the same rule is disclosure; telling one of them more
#: than another would be tuning. Note what this deliberately does NOT say: which files are held.
#: That list is `test_blobs`' key set, and naming it would narrow the search for the answer key.
_SCOPE_RULE = (
    "The test files are held by the operator and restored from a golden copy before grading, so"
    " a patch that modifies any test file is refused before it is run. Change the source code"
    " instead."
)

#: The oracle section, introduced by exactly what it is. The sentence says the files are the ones
#: the fix touches and that they are shown as they stand *now* — both facts the base needs: the
#: first is the retrieval hint (and the honesty cost, see the module docstring), the second is
#: what makes the lines usable as diff context, since a file quoted from after the fix would have
#: the base writing context lines that are not in the checkout.
_SOURCES_HEADING = "# Source files"
_SOURCES_INTRO = (
    "These are the repository files the fix touches, shown exactly as they stand in the checkout"
    " you are patching. Write your diff against these lines."
)

#: How one file's body is delimited. A markdown fence, but with its length **computed** from the
#: content rather than fixed at three: a source file containing a fenced example — a docstring
#: with a ```python block in it — would otherwise close its own block, and everything after it
#: would read as prose. The base would then be shown a truncated file while this module believed
#: it had shown a whole one, which is the same wrong experiment the character budget refuses to
#: run, arriving with no reason recorded anywhere.
_FENCE = "`"
_MINIMUM_FENCE = 3
_BACKTICKS = re.compile(r"`+")

#: The output contract. A fenced `diff` block is what the extractor (`patch.py`) looks for, and
#: an unfenced or prose-wrapped answer is charged as no-diff rather than as a wrong fix. Asking
#: for the shape the extractor reads is not tuning — it is the two halves of one contract agreeing
#: about what a response is.
_RESPONSE_HEADING = "# Response format"
_RESPONSE_FORMAT = (
    "Reply with a single unified diff and nothing else, inside one fenced block tagged `diff`:\n"
    "\n"
    "```diff\n"
    "--- a/path/to/file.py\n"
    "+++ b/path/to/file.py\n"
    "@@ ... @@\n"
    "```\n"
    "\n"
    "Paths are relative to the repository root."
)

#: The digest's encoding, pinned rather than left to the platform. `str.encode()` defaults to
#: UTF-8 today, but the hash is published as provenance and must be reproducible by a reader with
#: nothing but the prompt text and a stdlib — so the encoding is written down at the one place it
#: is applied. Matches `whetstone.tasks.ledger`'s construction for manifest hashes.
_ENCODING = "utf-8"


class HeldTestInSources(ValueError):
    """A source map offered a path the operator holds. The one refusal this module must never skip.

    Raised rather than silently dropping the entry, for two reasons pointing the same way. A
    dropped path would leave the caller believing it had shown the base a file it never did — a
    prompt quietly different from the one recorded — and it would hide the real defect, which is
    always upstream: something is classifying an operator-held file as ordinary source. Since the
    contents of `test_blobs` are exactly what STRICT grades against, that mistake reaching the
    context window is cheat 6 handed over pre-solved, and no execution-grounded check downstream
    can tell the resulting patch from a fix.
    """


class EmptySources(ValueError):
    """No source at all was offered, so the prompt would be the impossible pre-oracle question.

    Refused rather than rendered, because the fall-back is silent and expensive: a prompt with no
    code asks for a unified diff against a file the base has never seen, every rollout is charged
    `NOT_APPLIED`, and the resulting column of zeroes reads exactly like a weak base. Worse, a run
    where *some* tasks fell back this way would publish one denominator over two different
    experiments. `scoring.score` records such a task as skipped-with-reason; this is the lock that
    stops a caller reaching the renderer without its sources anyway.
    """


def render_prompt(task: Task, sources: Mapping[str, str]) -> str:
    """The prompt a base model is shown for `task`. Deterministic, and free of held-test content.

    Reads exactly two fields — `problem_statement` and `fail_to_pass` — plus the `sources` mapping
    the caller derived, and nothing else the `Task` carries. `test_blobs` is read for one purpose
    only: to refuse a `sources` map that names one of its paths. Its **values** are never touched.
    See the module docstring for why that is the single most important property of this function.

    `sources` is a required argument with no default, and that is deliberate to the point of being
    inconvenient. A default of `{}` would let a call site that lost its sources render the
    pre-oracle prompt — the impossible question — and record it beside oracle prompts under one
    heading. There is no spelling of this call that quietly asks a different question.

    The files are emitted in **sorted path order**, unlike the node ids below them. There is no
    operator-chosen order to preserve here: the mapping is derived from a commit's changed-path
    set, and iterating it as it arrives would make the prompt depend on how the caller built its
    dict — which is the byte-instability across processes that M7b's invalidation rule would then
    fire on every honest run.

    The node ids are emitted in the order the manifest declared them, not sorted. Two things
    follow, and both are intended. Declared order is the operator's, and a task listing a
    reproducing case first meant that; and a tuple's order is fixed by the manifest rather than by
    the interpreter, which is what makes the output byte-identical across processes and hash
    seeds. Sorting would also be deterministic — but it would silently discard an ordering the
    operator chose, in exchange for nothing.

    `problem_statement` is stripped of surrounding whitespace and otherwise passed through
    verbatim. Stripping keeps a trailing newline in a manifest from changing the recorded hash,
    which would read as an edited contract under M7b when nothing about the contract had changed.
    """
    if not sources:
        raise EmptySources(
            f"no source files were offered for task {task.task_id!r}, so the prompt would ask for "
            f"a unified diff against files the base has never seen. That question is not hard, it "
            f"is impossible — measured, every rollout comes back NOT_APPLIED — and scoring it "
            f"beside oracle prompts would put two different experiments under one denominator"
        )

    held = sorted(path for path in sources if path in task.test_blobs)
    if held:
        raise HeldTestInSources(
            f"the source map for task {task.task_id!r} offers operator-held {held}, whose contents "
            f"are what STRICT restores from golden and grades against. Rendering them would hand "
            f"the policy the answer key and make cheat 6 — special-casing the graded inputs — the "
            f"cheapest strategy available, which no execution-grounded check downstream can catch"
        )

    lines = [
        _PREAMBLE,
        "",
        _PROBLEM_HEADING,
        "",
        task.problem_statement.strip(),
        "",
        _TESTS_HEADING,
        "",
        _TESTS_INTRO,
        "",
        *(f"- {node_id}" for node_id in task.fail_to_pass),
        "",
        _SCOPE_RULE,
        "",
        _SOURCES_HEADING,
        "",
        _SOURCES_INTRO,
        "",
        *(line for path in sorted(sources) for line in _shown(path, sources[path])),
        _RESPONSE_HEADING,
        "",
        _RESPONSE_FORMAT,
        "",
    ]
    return "\n".join(lines)


def _shown(path: str, contents: str) -> tuple[str, ...]:
    """One file's section: its path, then its whole body inside a fence the body cannot close.

    Trailing newlines are dropped so the closing fence sits against the last line of the file,
    for the same reason `problem_statement` is stripped: whether a file ends in one blank line or
    two is not part of the question, and letting it move the recorded prompt hash would read as an
    edited contract under M7b. Nothing else about the bytes is touched — a diff is written from
    these lines, so re-indenting, re-wrapping or normalising them would be handing the base
    context lines that are not in the checkout.
    """
    # A list rather than `max(minimum, *runs)`: a file with no backticks in it at all makes that
    # spelling `max(3)`, which raises rather than returning three.
    fence = _FENCE * max([_MINIMUM_FENCE, *(len(run) + 1 for run in _BACKTICKS.findall(contents))])
    return (f"## {path}", "", fence, contents.rstrip("\n"), fence, "")


def prompt_hash(prompt: str) -> str:
    """The SHA-256 of `prompt`'s UTF-8 bytes, hex-encoded. The evidence behind M7b.

    Takes the rendered string rather than the `Task` on purpose. What the anti-tuning rule needs
    recorded is *what the model was actually shown* — a hash derived from the task would still
    match after the template beneath it had been rewritten, which is exactly the substitution M7b
    exists to make impossible.

    Deliberately the most boring construction available, and deliberately not salted, truncated
    or prefixed: a reader auditing a published run must be able to recompute it from the
    published prompt with `hashlib` and no knowledge of this file.
    """
    return hashlib.sha256(prompt.encode(_ENCODING)).hexdigest()


__all__ = ["EmptySources", "HeldTestInSources", "prompt_hash", "render_prompt"]
