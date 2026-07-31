"""One rollout, one record. The module that keeps an honest zero readable.

A bake-off between open bases on a 66-task private corpus may well come back all zeroes. That
is a legitimate finding and P1's base decision has to be able to rest on it — but only if the
zero can be *read*. Three different things produce a zero, they have three different fixes, and
exactly one of them is about the model:

* the base wrote **no diff at all** — a prompt problem, or a base too small to emit a patch;
* it wrote a diff that **would not apply** — a format problem, with the intent visible;
* it wrote a diff that **applied and did not fix the bug** — a capability result.

Collapse them and an all-zero bake-off is indistinguishable from a harness that never applied a
patch. So this module produces a *record*, never a count: `Outcome` names which zero it was, and
the strict sub-verdict kinds carry the verifier's own grounding for that name so the tag is a
finding rather than this module's opinion.

**The empty string is the trap, and it is one line wide.** `verify_strict(task, "")` is charged
FAIL at `patch-apply` — byte-for-byte the record a genuinely malformed diff produces. Handing the
verifier `""` when the extractor found nothing would therefore relabel every no-diff rollout as a
malformed-diff rollout, silently, with every guard in the tree still green. `patch.NoDiff` has no
`.diff` attribute for precisely this reason, and this module never invents one: when there is no
diff, **no verifier is entered at all**.

**A fourth zero must never be charged to the candidate.** If the task's environment cannot be
built, the result is about the machine, not the base. `verify_weak` cannot be used to detect
that — measured, it charges a broken-but-executable interpreter as FAIL, not UNVERIFIED — so
provisioning is classified *here*, before either verifier is reached, and its failure is recorded
`UNVERIFIED` under `Outcome.UNPROVISIONED`. UNVERIFIED never counts as a win, which is the
direction an unknown has to fall.

**What this module refuses to do.** It does not aggregate, count, rank, average or write
anything. Every number in the published baseline is derived downstream from these records, from
one place, so there is exactly one definition of each. A convenience `solved_count` here would
become a second definition the moment the report's own differed.

**Off the reward path, and one-way.** This is `whetstone.bakeoff`; it imports `whetstone.verify`
and `whetstone.tasks` to run and provision. Neither may import it back — see the package
docstring, and `tests/bakeoff/test_generator_contract.py` for the assertion.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path

from whetstone.bakeoff.generator import Generator
from whetstone.bakeoff.patch import Extracted, extract_patch
from whetstone.bakeoff.rendering import prompt_hash, render_prompt
from whetstone.tasks.environment import NotProvisionable, capture
from whetstone.verify.repo import CheckoutError, materialise
from whetstone.verify.strict import verify_strict
from whetstone.verify.task import Task
from whetstone.verify.verdict import Status
from whetstone.verify.weak import verify_weak

#: The sub-verdict kind STRICT returns, alone, when the patch could not be applied to the
#: checkout. Named here because `Outcome.NOT_APPLIED` is defined as "STRICT said exactly this"
#: and a literal spelled inline would let the tag drift away from the verifier that grounds it.
_PATCH_APPLY = "patch-apply"

#: The sub-verdict kind STRICT returns, alone, when the patch touched an operator-held test
#: path. A separate outcome because "tried to edit the tests" and "got the fix wrong" are
#: different findings — the first is a caught hack attempt and belongs in that count.
_PATCH_SCOPE = "patch-scope"


class Outcome(str, Enum):
    """Why this rollout came out the way it did. The tag that makes a zero readable.

    `str` mixin so an outcome serialises as its name, matching `Status`.

    The four not-solved members are the point of the type. They are **not** severity-ordered and
    must not be reduced against each other: they name distinct causes, and the only ordering
    anything downstream may apply is over `Status`, which has its own.
    """

    #: The declared fail-to-pass tests pass and nothing else broke. STRICT returned PASS.
    SOLVED = "SOLVED"

    #: The base produced no unified diff — prose, an unrecognised fence, or nothing. **No
    #: verifier ran**, because there was no patch to run one against.
    NO_DIFF = "NO_DIFF"

    #: A diff was produced and the checkout refused it. Shape without substance: the base got
    #: far enough to emit a patch and wrong enough that git would not take it.
    NOT_APPLIED = "NOT_APPLIED"

    #: The patch aimed at an operator-held test file and was refused before anything ran. A
    #: caught reward-hacking attempt, kept apart from every other zero so it can be counted as
    #: one rather than buried among honest failures.
    OUT_OF_SCOPE = "OUT_OF_SCOPE"

    #: The patch applied and the task still failed. The only zero of the four that is a
    #: statement about the base's ability to fix bugs.
    NOT_SOLVED = "NOT_SOLVED"

    #: The verifier could not reach a verdict — an unsupported platform, a timeout, a sandbox
    #: that would not start. A fact about the run, not about the base.
    UNVERIFIED = "UNVERIFIED"

    #: The task's environment could not be built, so nothing was ever executed. A fact about the
    #: machine, and the one outcome that must never be read as the candidate's failure.
    UNPROVISIONED = "UNPROVISIONED"


@dataclass(frozen=True)
class Rollout:
    """What one candidate did on one task. A record, deliberately not a score.

    Everything here is either something a verifier returned or something observed while getting
    there. Nothing is derived, nothing is summed, and there is no boolean "solved" field: a
    caller that wants one writes `record.outcome is Outcome.SOLVED` at the single place the
    report defines it, rather than inheriting a second definition from here.

    **The verdict fields are `None` when no verifier ran**, which is not the same as UNVERIFIED.
    UNVERIFIED means the harness tried to determine an outcome and could not; `None` means it
    never tried, because there was no patch (`NO_DIFF`). Folding the second into the first would
    inflate the UNVERIFIED count that the pivot signal reads, with rollouts where nothing was
    wrong except that the base said nothing.

    **The durations are outside the verdict**, and `StrictResult` deliberately carries none of
    its own for the same reason: two runs of the same candidate on the same task must compare
    equal on everything that decides the outcome. A millisecond count inside the verdict would
    make "the bake-off is reproducible" untestable.
    """

    #: Which base this was. An operator-chosen identifier, carried through unread — this module
    #: never parses it, so a candidate may be named after a checkpoint, a path or a revision.
    candidate: str

    #: The task's own id, from its manifest.
    task_id: str

    #: Which of the outcomes above this rollout was, and the field every downstream count reads.
    outcome: Outcome

    #: STRICT's reduced status — the reward — or `None` if STRICT never ran.
    strict: Status | None

    #: WEAK's `observed_status`, or `None` if WEAK never ran. Recorded alongside STRICT on every
    #: rollout because the two together are the measurement: the gap between them is how many
    #: patches a naive exit-status check would have accepted and the reward did not.
    weak: Status | None

    #: The `kind` of every STRICT sub-verdict, in the order STRICT emitted them. This is what
    #: grounds `outcome`: `NOT_APPLIED` is not a judgement made here, it is `("patch-apply",)`.
    verdict_kinds: tuple[str, ...]

    #: How many node ids pytest reported running, or `None` when no report could be read. A
    #: count rather than the ids: the ids are the task's declared set and belong to the task.
    executed: int | None

    #: SHA-256 of the exact prompt the base was shown. The evidence behind the anti-tuning rule
    #: — a hash over the task would still match after the template beneath it was rewritten.
    prompt_sha256: str

    #: A sentence for whoever is reading a zero: the extractor's reason, or the provisioning
    #: error. Empty when the verifier ran and its own verdicts are the explanation.
    detail: str

    #: Wall-clock seconds asking the base for text. Separate from the two below because a base
    #: that is slow to generate and a task that is slow to verify are different problems, and a
    #: single total would hide which of them a long bake-off was spending its night on.
    generation_seconds: float

    #: Wall-clock seconds inside `verify_strict`. `0.0` when it did not run.
    strict_seconds: float

    #: Wall-clock seconds inside `verify_weak`. `0.0` when it did not run.
    weak_seconds: float


#: How a task's environment is built. Takes the task and a private directory to build it in,
#: and returns the interpreter its declared tests must run under. Injectable so the caching
#: claim can be asserted by counting calls rather than by timing two real `uv sync` runs, and so
#: a later phase can substitute a provisioner without this module learning about it.
Provision = Callable[[Task, Path], Path]


def provision_from_lock(task: Task, into: Path) -> Path:
    """Materialise `task` at its base commit and build its environment from that checkout's lock.

    **One checkout serves both halves, and it has to.** `capture` reads the donor's `uv.lock`,
    and the lock that matters is the one *at `base_commit`* — a donor's dependencies move over
    its history, so provisioning from the working tree, or from a second checkout at some other
    revision, would build an environment for a different commit than the one under verification.
    The clone is therefore made here, once, and handed straight to `capture`.

    Note what is *not* shared: `verify_strict` makes its own pristine checkout inside its own
    sandbox, deliberately, because the reward has to apply the patch to a tree nothing else has
    touched. Only the resolved interpreter crosses over, which is the shipped boundary —
    provisioning happens outside the sandbox, execution happens inside it.

    Raises rather than returning a failure, because a caller that ignored a returned error would
    verify under the wrong interpreter and record the result as the candidate's.
    """
    checkout = into / "checkout"
    materialise(task, checkout)
    return capture(checkout, venv=into / "venv", python=task.environment.python).interpreter


@dataclass(frozen=True)
class Acquired:
    """An interpreter to verify under, or the reason there is none.

    `interpreter is None` with no `failure` is the third, legitimate case: the task declares no
    pins, so there is nothing to install and the verifiers' own default — this process's
    interpreter — is the right answer. That is not a degraded outcome and must not be recorded
    as one.
    """

    #: The python the task's declared tests run under, or `None` for the verifiers' default.
    interpreter: Path | None

    #: Why the environment could not be built, or `None` if it could. A non-`None` value here is
    #: what becomes `Outcome.UNPROVISIONED`.
    failure: str | None


@dataclass
class Interpreters:
    """One provisioned environment per *distinct pin set*, not per task.

    The saving is the reason this class exists rather than a call inside `score`. Source B's 66
    tasks were mined from two donors, so they share far fewer environments than manifests: keyed
    on the pin set, a bake-off builds a handful of venvs instead of 66, and it builds them once
    across every candidate rather than once per candidate per task.

    **Failures are cached too**, which is not an optimisation but the same correctness argument
    read backwards: a donor that cannot be provisioned cannot be provisioned 66 times either, and
    retrying it would spend the night discovering the same missing lockfile.

    The key is the pin set *and* the interpreter version, because those are exactly what decide
    what gets installed. `import_roots` is deliberately excluded: it is a fact about where a
    repository keeps its code, it is passed to the verifier per task, and including it would
    split the cache on something that cannot change a venv's contents.

    Mutable by design — it is a cache — and therefore explicitly not frozen. It is not
    thread-safe, and nothing in this phase runs rollouts concurrently.
    """

    #: Where the venvs and their checkouts are built. Each environment gets a subdirectory named
    #: for the digest of its key, so a run can be pointed at an existing workspace later without
    #: this class needing to know that resumability exists.
    workspace: Path

    #: How to build one. Defaults to the real thing; substituted in tests.
    provision: Provision = provision_from_lock

    #: Pin set -> what came of building it. `init=False` so the cache cannot be seeded from
    #: outside, which would make "provisioned once" a claim about the caller.
    _built: dict[tuple[str, tuple[str, ...]], Acquired] = field(
        init=False, default_factory=dict, repr=False
    )

    def acquire(self, task: Task) -> Acquired:
        """The interpreter for `task`'s declared environment, building it at most once."""
        environment = task.environment
        if not environment.pins:
            # `[]` pins is a positive claim — nothing is installed, so nothing can drift — and
            # the honest response is to install nothing. The verifiers' own default interpreter
            # runs it, which is what every fixture task in this repository already does.
            return Acquired(interpreter=None, failure=None)

        key = (environment.python, environment.pins)
        built = self._built.get(key)
        if built is None:
            built = self._build(key, task)
            self._built[key] = built
        return built

    def _build(self, key: tuple[str, tuple[str, ...]], task: Task) -> Acquired:
        """Build one environment, turning any failure into a recordable sentence.

        The exception list is closed on purpose. `NotProvisionable` covers a donor with no lock,
        an unreadable layout and a `uv` that exited non-zero; `CheckoutError` covers a repository
        or commit that is not there; `SubprocessError` and `OSError` cover a `uv` that could not
        be started or timed out. Anything else is a defect in this harness rather than a fact
        about the donor, and it is left to propagate — swallowing it would report a bug in
        Whetstone as a property of the user's repository.
        """
        digest = hashlib.sha256("\n".join((key[0], *key[1])).encode("utf-8")).hexdigest()[:16]
        try:
            interpreter = self.provision(task, self.workspace / digest)
        except (NotProvisionable, CheckoutError, subprocess.SubprocessError, OSError) as exc:
            return Acquired(interpreter=None, failure=f"{type(exc).__name__}: {exc}")
        return Acquired(interpreter=interpreter, failure=None)


def score(
    *,
    candidate: str,
    task: Task,
    generator: Generator,
    sandbox_root: Path | str,
    timeout: float,
    interpreters: Interpreters,
) -> Rollout:
    """Ask `candidate` for a patch to `task`, verify it both ways, and record what happened.

    Returns a record for *every* input, including the ones where nothing could be run. It raises
    only for a broken caller — an unstubbed prompt, a task that will not load — never for a
    candidate that did badly, because a bake-off that aborts on the first hopeless base measures
    the bases that came before it and nothing else.

    `timeout` has no default, matching the verifiers: a limit inherited from somewhere else turns
    every slow task into an UNVERIFIED nobody can explain. `interpreters` has no default either,
    and that one is deliberate to the point of being inconvenient: a default cache would let a
    caller who forgot it run all 66 tasks under whatever interpreter this process happens to be,
    quietly, and publish the result.

    **The environment is built before the base is asked anything.** A task that cannot be
    provisioned can never be verified, so generating a patch for it is model time spent on a
    rollout that has no possible verdict — negligible on one task, hours across a corpus.
    """
    prompt = render_prompt(task)
    record = _partial(candidate, task, prompt)

    acquired = interpreters.acquire(task)
    if acquired.failure is not None:
        # Neither verifier is entered, and that is the reason this classification lives here
        # rather than being read off a verdict: `verify_weak` charges a broken-but-executable
        # interpreter as FAIL, so letting a provisioning failure fall through to it would record
        # a fact about the machine as the candidate failing the task.
        return replace(
            record,
            outcome=Outcome.UNPROVISIONED,
            strict=Status.UNVERIFIED,
            weak=Status.UNVERIFIED,
            detail=acquired.failure,
        )

    started = time.perf_counter()
    completion = generator.generate(prompt)
    record = replace(record, generation_seconds=time.perf_counter() - started)

    extraction = extract_patch(completion)
    if not isinstance(extraction, Extracted):
        # The verifier is not reached. `extraction` has no `.diff` and this module does not
        # supply one: `verify_strict(task, "")` is FAIL at patch-apply, which would make this
        # rollout indistinguishable from a malformed diff.
        return replace(record, outcome=Outcome.NO_DIFF, detail=extraction.reason)

    return _verify(
        record,
        task,
        extraction.diff,
        sandbox_root=Path(sandbox_root),
        timeout=timeout,
        interpreter=acquired.interpreter,
    )


def _verify(
    record: Rollout,
    task: Task,
    diff: str,
    *,
    sandbox_root: Path,
    timeout: float,
    interpreter: Path | None,
) -> Rollout:
    """Run both verifiers over `diff` and fold what they returned into `record`.

    STRICT first and unconditionally: it is the reward, and WEAK is measurement that only means
    something next to it. Both are given their own sandbox subdirectory so neither can see what
    the other left behind, and **both are given the same interpreter** — a WEAK reading taken
    under a different python would not be a control for anything.

    `UnsupportedPlatform` is a `RuntimeError` and a timeout is a `subprocess.TimeoutExpired`;
    both mean the reward could not be computed, which is UNVERIFIED and never FAIL. WEAK is not
    attempted afterwards: whatever stopped the sandbox would stop it too, and an observation
    taken outside a containment boundary is not a measurement this project reports.
    """
    started = time.perf_counter()
    try:
        strict = verify_strict(
            task,
            diff,
            sandbox_root=sandbox_root / "strict",
            timeout=timeout,
            interpreter=interpreter,
        )
    except (subprocess.TimeoutExpired, OSError, RuntimeError) as exc:
        return replace(
            record,
            outcome=Outcome.UNVERIFIED,
            strict=Status.UNVERIFIED,
            weak=Status.UNVERIFIED,
            detail=f"the reward could not be computed: {exc}",
            strict_seconds=time.perf_counter() - started,
        )
    strict_seconds = time.perf_counter() - started

    started = time.perf_counter()
    weak = verify_weak(
        task, diff, sandbox_root=sandbox_root / "weak", timeout=timeout, interpreter=interpreter
    )
    weak_seconds = time.perf_counter() - started

    kinds = tuple(verdict.kind for verdict in strict.verdicts)
    return replace(
        record,
        outcome=_classify(strict.status, kinds),
        strict=strict.status,
        weak=weak.observed_status,
        verdict_kinds=kinds,
        executed=None if strict.executed is None else len(strict.executed),
        strict_seconds=strict_seconds,
        weak_seconds=weak_seconds,
    )


def _classify(status: Status, kinds: tuple[str, ...]) -> Outcome:
    """Name the zero, from STRICT's own status and sub-verdict kinds.

    The mapping is deliberately narrow. `NOT_APPLIED` and `OUT_OF_SCOPE` are recognised only
    when the named kind is the *sole* verdict, because that is the shape STRICT actually
    produces for them — it stops before anything else runs. A patch-apply verdict sitting among
    others would mean something changed in the verifier, and the honest answer to that is
    `NOT_SOLVED` (a zero, unclassified) rather than a tag this function guessed at.
    """
    if status is Status.PASS:
        return Outcome.SOLVED
    if status is Status.UNVERIFIED:
        return Outcome.UNVERIFIED
    if kinds == (_PATCH_APPLY,):
        return Outcome.NOT_APPLIED
    if kinds == (_PATCH_SCOPE,):
        return Outcome.OUT_OF_SCOPE
    return Outcome.NOT_SOLVED


def _partial(candidate: str, task: Task, prompt: str) -> Rollout:
    """The record as it stands before anything has been asked or run.

    Exists so every return path above starts from the same fully-populated object: a record
    assembled field-by-field at each exit is a record where one path forgets `prompt_sha256`.
    The `UNVERIFIED` outcome it carries is the safe default — a path that fell through without
    setting one reports "we could not tell", never a win.
    """
    return Rollout(
        candidate=candidate,
        task_id=task.task_id,
        outcome=Outcome.UNVERIFIED,
        strict=None,
        weak=None,
        verdict_kinds=(),
        executed=None,
        prompt_sha256=prompt_hash(prompt),
        detail="",
        generation_seconds=0.0,
        strict_seconds=0.0,
        weak_seconds=0.0,
    )


__all__ = [
    "Acquired",
    "Interpreters",
    "Outcome",
    "Provision",
    "Rollout",
    "provision_from_lock",
    "score",
]
