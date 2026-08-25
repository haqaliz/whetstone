"""Pins the *scope* of the reward-path guard to the shape of the tree, not to a memory of it.

The failure this prevents: ``tests/test_no_inference_on_reward_path.py`` bans inference
imports under a hand-written tuple of roots, and nothing in this repository notices when
that tuple stops describing the tree. Add a package under ``src/whetstone/`` — a rollout
runner, a bake-off harness, a distillation step — and the ban stays green while its coverage
silently shrinks relative to the code that exists. Nothing fails, because nothing is
looking; worse, the message that guard prints on failure still names the roots it *does*
walk, which reads exactly like coverage to whoever reads it next.

That is a different failure from the one the AST guard catches. The AST guard answers "does
any guarded module import a model?". This one answers "is every module in the tree either
guarded or knowingly not?" — and only the second question has an answer that stays true as
the tree grows.

So this refuses to let scope be implicit. Every package and every top-level module directly
under ``src/whetstone/`` must be one of exactly two things, and there is no third:

* **guarded** — named in ``GUARDED_ROOTS``, and therefore walked by the AST ban; or
* **exempt** — named in ``EXEMPT`` below, carrying a written reason a reviewer can read and
  disagree with.

A new package is neither until someone says which, so the build fails until someone does.
That is the whole mechanism: it does not decide anything, it forces the decision to be made
in a diff rather than by omission.

**Writing this test found ``cli.py`` unguarded**, which is the best evidence that the hole is
real rather than hypothetical. ``src/whetstone/cli.py`` calls ``verify_strict`` (``:248-250``)
— it is the reward's entry point — and ``GUARDED_ROOTS`` named only the two packages, so
nothing had ever walked it. It is guarded as of the commit that adds this file. Note the
distinction ``CONTRIBUTING.md:20`` draws: widening the guarded path *to make a failing check
pass* is forbidden; widening it to cover code that should always have been inside it is the
opposite act, and it is recorded here so a reviewer can judge it as one.

**Exemptions are not exceptions.** ``EXEMPT`` is checked in both directions — an entry it
does not name fails the build, and a name it holds that no longer exists on disk fails the
build too. A stale exemption is a hole with a comment on it: the reason reads as though
someone thought about the code, while the code it excused has been gone for months.

**Watched failing, against synthetic trees rather than against ``src/``.** Every control
below was watched failing before the logic under it existed: with ``_unpartitioned`` and
``_stale_exemptions`` returning ``[]`` — the credulous implementation this could decay into
without any of it looking different — all five controls failed while all five real-tree
assertions passed, which is precisely the asymmetry that makes the controls worth their
lines. The real-tree assertion was then watched failing too, naming ``cli.py``, before
``GUARDED_ROOTS`` was widened. The controls build their trees
in ``tmp_path`` and hand them to the *same* functions the real assertions call, so what they
prove is proven about the shipped logic and not about a copy of it — the shape
``tests/test_docs.py:173-185`` uses for the same reason.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest
from test_no_inference_on_reward_path import GUARDED_ROOTS, _imported_names, _modules

SRC = Path(__file__).resolve().parent.parent / "src"

#: The one directory this guard partitions: the import package itself. Its immediate
#: children — packages and top-level modules alike — are the units a decision is made about.
#: Not ``src/`` (which holds only this package) and not the repository root (which holds
#: tests, docs and tooling that no reward ever runs).
PACKAGE_ROOT = SRC / "whetstone"

#: Build artefacts and editor droppings, excluded from the enumeration by name. Kept
#: deliberately short: every name here is a name a package could in principle be called, so
#: each one is a hole, and the only defensible size for this set is "as small as it can be".
_NOT_SOURCE = frozenset({"__pycache__", ".DS_Store"})

#: Entries knowingly outside the AST ban, each with the reason it is outside. This mapping is
#: the whole point of the file: an exemption is cheap to add and impossible to add silently,
#: because it lands in a diff next to a sentence someone had to write and someone else can
#: refuse. A reason that could be written about any file at all ("internal", "trivial") is not
#: a reason — it is the absence of one, spelled at length.
#:
#: What must NOT appear here: any package that carries inference code and is reachable from a
#: verdict. The bake-off package, when it lands, is exempt because nothing guarded may import
#: it and the dependency runs one way only — not because it is harmless.
#:
#: **It holds two entries, and it held none until the bake-off landed.** Every other child of
#: the package is guarded, and a reader should expect that to stay true: the only thing that
#: belongs here is code the inference ban would be *wrong* about. ``bakeoff`` was the first —
#: the first code in this tree that consults a model, and therefore the first thing that could
#: not be guarded without the ban failing honestly — and ``loop`` is the second, for the same
#: reason and with one extra obligation, because unlike the bake-off it is reachable from a
#: guarded root by a single documented, function-local edge. An earlier draft of this change
#: also exempted ``__init__.py`` as a documented residual; it is guarded instead, because
#: closing it cost one line and a residual is for a hole that is hard to close, not one nobody
#: had to accept.
#:
#: Note what a one-entry mapping does *not* weaken: the assertions that read it barely iterate,
#: and their teeth come from the synthetic controls below, which run the same functions over
#: trees carrying exemptions this repository does not have. That is the arrangement
#: ``tests/test_docs.py:173-185`` uses for a guard whose real-tree answer is "nothing wrong".
#:
#: The exemption's own reason names the assertion it depends on, and that assertion sits at
#: the foot of this file for the same reason the reason sits here: a justification and its proof
#: that live in different files drift apart without either one looking wrong.
EXEMPT: Mapping[str, str] = {
    "bakeoff": (
        "the bake-off harness, which imports mlx_lm legitimately in a later phase in order to "
        "run a base model against the verifier — the measurement that settles which open base "
        "P1 starts from. Nothing guarded imports it, and the dependency is one-directional by "
        "design: bakeoff imports whetstone.verify for the Task contract and never the reverse, "
        "so no verdict can reach this code. Guarding it instead would fail the inference ban "
        "the moment the MLX adapter lands, and the pressure would then land on the ban itself. "
        "The one-way edge is asserted directly, by "
        "test_no_module_on_the_reward_path_imports_the_bakeoff_package at the foot of this "
        "file, because the AST ban would not notice it being reversed: it flags first-party "
        "imports whose dotted name carries an inference-shaped component, and neither "
        "'bakeoff' nor 'generator' is one. It lives here rather than beside the bake-off's "
        "own tests deliberately — this exemption is only sound while that assertion holds, "
        "and a reason whose proof sits in a file that may be restructured for unrelated "
        "reasons is a reason that can quietly stop being true."
    ),
    "loop": (
        "the nightly improvement loop and the promotion gate, which import mlx_lm legitimately"
        " for the same reason the bake-off does: the loop samples k attempts per task from a base"
        " model and LoRA-trains on the ones the STRICT verifier passed, and the gate scores a"
        " checkpoint by loading the base with its LoRA adapter and generating a patch per"
        " held-out task. The same library is correct here and fatal under verify/, and the only"
        " thing keeping those two facts apart is where the code lives — so the loop is a SIBLING"
        " of verify/ and tasks/, never nested under either. The dependency runs one way"
        " (loop -> bakeoff -> verify) with exactly TWO documented edges in the other direction:"
        " cli.py holds a FUNCTION-LOCAL import of whetstone.loop.night inside the `run --night`"
        " handler, because the roadmap names that command as the loop's door, and a FUNCTION-"
        " LOCAL import of whetstone.loop.gate inside the `gate` handler, the p3-promotion-gate"
        " unit's door — a subcommand needs a call. Those edges are not holes with comments on"
        " them: test_the_reward_path_reaches_the_exempt_packages_by_exactly_the_documented_edges"
        " at the foot of this file asserts they are the only ones and that they are function-"
        " local, so `whetstone verify` — the reward's own entry point — never executes them and"
        " never imports mlx_lm even transitively. A third such import, or either one moved to"
        " module scope, fails the build. As with bakeoff, the AST ban would not notice any of"
        " this: it flags first-party imports whose dotted name carries an inference-shaped"
        " component, and neither 'loop', 'night' nor 'gate' is one."
    ),
}

#: The import edges that run from a guarded root into an exempt package, spelled exactly.
#: Each is `(module under src/, the dotted prefix it may import)`. Everything else in either
#: direction is a failure — see the `loop` reason above for why these edges exist at all and
#: why they are lines rather than a rule.
_DOCUMENTED_EDGES: tuple[tuple[Path, str], ...] = (
    (Path("whetstone/cli.py"), "whetstone.loop.night"),
    (Path("whetstone/cli.py"), "whetstone.loop.gate"),
)


def _scope(package_root: Path) -> list[str]:
    """Every package and top-level module directly under ``package_root``, by name.

    Takes the root as an argument rather than closing over ``PACKAGE_ROOT`` so the controls
    below can run this exact function over a synthetic tree. A guard hard-wired to this
    repository can only ever be exercised against a tree that already satisfies it, which
    means its failure branch ships untested.

    **Every** directory counts, not only those holding an ``__init__.py``. Keying on
    ``__init__.py`` would mean a package escapes the partition by deleting one empty file —
    and implicit namespace packages import perfectly well without it, so the escape would
    cost nothing and change nothing about what the code can do.
    """
    return sorted(
        child.name
        for child in package_root.iterdir()
        if child.name not in _NOT_SOURCE
        and not child.name.startswith(".")
        and (child.is_dir() or child.suffix == ".py")
    )


def _guarded_names(package_root: Path, guarded: Sequence[Path]) -> set[str]:
    """The names in ``guarded`` that are immediate children of ``package_root``.

    Matched on the parent directory and not on the bare name, so a root pointing at some
    *other* ``verify/`` elsewhere in the filesystem cannot be read as covering this one. A
    guarded root that lives outside this package guards nothing here and is reported as
    nothing here.
    """
    return {root.name for root in guarded if root.parent == package_root}


def _unpartitioned(
    package_root: Path, guarded: Sequence[Path], exempt: Mapping[str, str]
) -> list[str]:
    """Entries that are neither guarded nor exempted — the ones nobody has decided about."""
    decided = _guarded_names(package_root, guarded) | set(exempt)
    return [name for name in _scope(package_root) if name not in decided]


def _stale_exemptions(package_root: Path, exempt: Mapping[str, str]) -> list[str]:
    """Exempted names that no longer exist on disk — holes with comments on them."""
    present = set(_scope(package_root))
    return sorted(name for name in exempt if name not in present)


@pytest.fixture
def synthetic(tmp_path: Path) -> Callable[..., Path]:
    """Builds a package root of a given shape, for handing to the functions above.

    Synthetic rather than real, for the reason the sibling guard gives
    (``test_no_inference_on_reward_path.py:251-260``): demonstrating teeth by editing
    ``src/`` would mean committing the very hole the guard exists to reject and trusting a
    later revert to undo it.
    """

    def _build(*, packages: Sequence[str] = (), modules: Sequence[str] = ()) -> Path:
        root = tmp_path / "src" / "whetstone"
        root.mkdir(parents=True, exist_ok=True)
        for name in packages:
            package = root / name
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
        for name in modules:
            (root / name).write_text("", encoding="utf-8")
        return root

    return _build


def test_the_scope_this_guard_walks_is_not_empty() -> None:
    """Anti-vacuity: a partition of nothing is a partition, and it proves nothing.

    ``CONTRIBUTING.md:53-60`` makes this mandatory rather than nice: a guard that walks a set
    of files must assert the set is non-empty. Move or rename ``src/whetstone/`` and every
    other assertion in this file goes green over an empty iteration — the strongest possible
    result reported by the weakest possible run.
    """
    scope = _scope(PACKAGE_ROOT)
    assert scope, (
        f"nothing enumerated under {PACKAGE_ROOT} — this guard walked an empty tree.\n\n"
        "WHY THIS IS A FAILURE: every other assertion in this file is a statement about the"
        " members of this set, so an empty set satisfies all of them at once. The build would"
        " report that the reward path's scope is fully partitioned at the moment it stopped"
        " being able to see any of it. The likely cause is the package having moved, so"
        " PACKAGE_ROOT now points at nothing."
    )


def test_every_package_and_module_under_src_is_guarded_or_exempted() -> None:
    """The partition itself: no entry may be neither, because neither is where things hide.

    An unlisted package is not merely undocumented — it is code that the AST ban never walks
    and that no reviewer was ever asked about. The bake-off package is the live example: it
    will import ``mlx_lm``, which is legitimate off the reward path and fatal on it, and the
    difference between those two facts is a decision someone has to make out loud.
    """
    missing = _unpartitioned(PACKAGE_ROOT, GUARDED_ROOTS, EXEMPT)
    assert not missing, (
        "these entries under src/whetstone/ are neither guarded nor exempted: "
        + ", ".join(missing)
        + "\n\nWHY THIS IS A FAILURE: the reward-path ban only walks GUARDED_ROOTS, so an"
        " entry that is on neither list is code nothing checks for inference imports, and"
        " nobody has said that is intended. Decide, and say which: add it to GUARDED_ROOTS"
        " in tests/test_no_inference_on_reward_path.py if a verdict can depend on it, or add"
        " it to EXEMPT here with the reason it cannot. Do not pick 'guarded' merely to make"
        " this pass — a package that legitimately imports a model will then fail the ban, and"
        " the pressure will be to weaken the ban itself, which is the one outcome this file"
        " exists to prevent."
    )


def test_no_exemption_names_something_that_no_longer_exists() -> None:
    """A stale exemption is a hole with a comment on it, and it reads like diligence.

    The reason stays on the page long after the code it excused is gone, so the mapping looks
    considered while describing a tree that no longer exists. Worse, the name is then free
    for reuse: something new lands under the old name and arrives pre-exempted, carrying a
    justification written about entirely different code.
    """
    stale = _stale_exemptions(PACKAGE_ROOT, EXEMPT)
    assert not stale, (
        "EXEMPT names entries that do not exist under src/whetstone/: " + ", ".join(stale) + "\n\n"
        "WHY THIS IS A FAILURE: an exemption is a written decision about a specific piece of"
        " code. Once that code is gone the decision is not conservative, it is a trap: the"
        " next thing to take that name inherits an exemption nobody wrote for it and skips"
        " the ban without anyone choosing that. Delete the entry."
    )


def test_every_exemption_carries_a_written_reason() -> None:
    """An exemption with an empty or throwaway reason is an exemption with no author.

    The mapping's entire safety property is that adding a name costs a sentence somebody has
    to defend. ``{"bakeoff": "ok"}`` satisfies a mapping-shaped check while restoring exactly
    the silence this file was written to remove, so the reason is asserted to be substantive
    rather than merely present.
    """
    thin = sorted(name for name, reason in EXEMPT.items() if len(reason.split()) < 12)
    assert not thin, (
        "these exemptions carry no real reason: " + ", ".join(thin) + "\n\n"
        "WHY THIS IS A FAILURE: the reason is the only thing an exemption costs, and it is"
        " what a reviewer reads instead of reading the code. A word or two restores the"
        " silence this guard removes while leaving the mapping looking populated. Write why"
        " a verdict cannot depend on this entry, or guard it."
    )


def test_an_unlisted_package_is_reported(synthetic: Callable[..., Path]) -> None:
    """Watched-failing control: a sibling package nobody listed must fail the build.

    This is the exact scenario ``src/whetstone/bakeoff/`` will be tomorrow, reproduced today
    in a temp directory: a package that exists, is not guarded, and is not exempt. Against a
    credulous ``_unpartitioned`` — one that returns ``[]`` — every other assertion in this
    file still passes, which is why this control is the one that gives them meaning.
    """
    root = synthetic(packages=("verify", "bakeoff"))
    assert _unpartitioned(root, (root / "verify",), {}) == ["bakeoff"]


def test_an_unlisted_top_level_module_is_reported(synthetic: Callable[..., Path]) -> None:
    """Packages are not the only unit: a bare ``.py`` beside them is reward-path code too.

    ``cli.py`` is the proof. A partition that enumerated only directories would have called
    the tree fully covered while the module that calls ``verify_strict`` sat outside every
    root — which is precisely the state this repository was in before this file existed.
    """
    root = synthetic(packages=("verify",), modules=("cli.py",))
    assert _unpartitioned(root, (root / "verify",), {}) == ["cli.py"]


def test_a_package_that_dropped_its_init_is_still_in_scope(
    synthetic: Callable[..., Path],
) -> None:
    """Deleting an empty file is not a way out of the partition.

    Namespace packages import without ``__init__.py``, so a scope that keyed on that file
    would let a directory leave the guard's world while losing none of its ability to run on
    the reward path — an escape hatch costing one ``rm``.
    """
    root = synthetic(packages=("verify",))
    (root / "bakeoff").mkdir()
    (root / "bakeoff" / "runner.py").write_text("", encoding="utf-8")
    assert _unpartitioned(root, (root / "verify",), {}) == ["bakeoff"]


def test_a_stale_exemption_is_reported(synthetic: Callable[..., Path]) -> None:
    """Watched-failing control: an exemption naming something that is gone must fail.

    Asserted over a tree that has ``verify/`` and nothing else, with an exemption for a
    package that was deleted. The name survives, its reason survives, and the code it
    described does not — the state this check exists to make impossible to keep.
    """
    root = synthetic(packages=("verify",))
    assert _stale_exemptions(root, {"rollouts": "deleted three commits ago"}) == ["rollouts"]


def test_a_guarded_or_exempted_entry_is_not_reported(synthetic: Callable[..., Path]) -> None:
    """Precision, not bluntness: the two decisions must actually satisfy the partition.

    A check that reported every entry would pass the controls above and fail permanently on
    the real tree, and the fix under deadline would be to delete the check. Both listings are
    asserted to work, and a guarded root belonging to some *other* directory is asserted not
    to count — otherwise a stale path elsewhere in the filesystem could silently stand in for
    the package it was named after.
    """
    root = synthetic(packages=("verify", "tasks"), modules=("cli.py", "__init__.py"))
    assert (
        _unpartitioned(
            root,
            (root / "verify", root / "tasks", root / "cli.py"),
            {"__init__.py": "the version shim, and nothing a verdict can reach"},
        )
        == []
    )

    elsewhere = root.parent / "other"
    (elsewhere / "tasks").mkdir(parents=True)
    assert _unpartitioned(root, (root / "verify", elsewhere / "tasks"), {}) == [
        "__init__.py",
        "cli.py",
        "tasks",
    ]


def test_an_empty_tree_enumerates_nothing(synthetic: Callable[..., Path]) -> None:
    """The non-emptiness assertion is a real discriminator, not a formality.

    ``test_the_scope_this_guard_walks_is_not_empty`` is only worth its line if ``_scope`` can
    in fact return an empty list — if the walk always found something, the assertion would be
    unfalsifiable and would be protecting nothing.
    """
    assert _scope(synthetic()) == []


def test_no_module_on_the_reward_path_imports_the_bakeoff_package() -> None:
    """The one-way dependency, enforced — the claim the written exemption rests on.

    ``bakeoff`` is kept off the AST ban by an exemption in
    ``tests/test_reward_path_scope_is_partitioned.py``, and that exemption's reason is that the
    dependency runs one way: bake-off imports ``whetstone.verify`` for the ``Task`` type, and
    nothing guarded imports bake-off.

    **Nothing was enforcing that, and the obvious candidate does not.** The AST ban only flags
    first-party imports whose dotted name contains an inference-shaped component (``judge``,
    ``model``, ``llm``, …); ``whetstone.bakeoff.generator`` contains none, so
    ``_is_inference_import`` returns `False` for it and a ``from whetstone.bakeoff import
    generate`` inside ``verify/`` would leave every guard in this tree green while putting a
    model exactly one call away from the verdict. This is that assertion.
    """
    modules = _modules()
    seen = {dotted for path in modules for dotted, _lineno in _imported_names(path, SRC)}
    assert seen, (
        "the walk over the guarded roots observed no imports at all.\n\n"
        "WHY THIS IS A FAILURE: the assertion below is a statement about the members of this"
        " set, so an empty set satisfies it vacuously — the strongest possible result reported"
        " by the weakest possible run."
    )

    offenders = sorted(name for name in seen if name.split(".")[:2] == ["whetstone", "bakeoff"])
    assert not offenders, (
        "the reward path imports the bake-off package: " + ", ".join(offenders) + "\n\n"
        "WHY THIS IS A FAILURE: bakeoff/ is exempt from the inference ban only because nothing"
        " guarded can reach it — the dependency is supposed to run one way, bakeoff -> verify."
        " An import in the other direction puts mlx_lm on the reward path transitively while"
        " every other guard stays green, because the AST ban keys on inference-SHAPED names and"
        " 'bakeoff' is not one. Move the shared code into verify/ or tasks/, or invert the"
        " dependency; do not add bakeoff to GUARDED_ROOTS, which would fail the ban the moment"
        " the MLX adapter lands and put the pressure on the ban itself."
    )


def _edges_into_exempt_packages() -> list[tuple[Path, str, int]]:
    """Every import from a guarded module into an exempt package: `(module, dotted, line)`.

    Both exempt packages, in one walk, because the property is about the *partition* rather than
    about either package: an exemption is sound exactly while nothing guarded can reach what it
    excuses. A per-package copy of this walk would be two things to remember to extend when a
    third exemption lands, and the one that got forgotten would still read as coverage.
    """
    return [
        (path.relative_to(SRC), dotted, lineno)
        for path in _modules()
        for dotted, lineno in _imported_names(path, SRC)
        if dotted.split(".")[:2] in (["whetstone", "bakeoff"], ["whetstone", "loop"])
    ]


def test_the_reward_path_reaches_the_exempt_packages_by_exactly_the_documented_edges() -> None:
    """The `loop` exemption's own claim: the documented edges, spelled out, and nothing else.

    ``bakeoff`` has no edge at all — the assertion above holds it at zero. ``loop`` has exactly
    two, and they exist because ``docs/ROADMAP.md:399-400`` names ``whetstone run --night`` as
    the loop's door and the p3-promotion-gate unit names ``whetstone gate`` as the gate's: a
    subcommand has to call something, and the call has to be written somewhere.

    **What makes those edges sound is not that they are small.** It is that they are
    *function-local* — asserted separately below — so the module graph of ``whetstone verify``
    never contains them and no reward run imports ``mlx_lm`` even transitively. This test is the
    half that says "exactly the documented edges", and it is deliberately spelled as an equality
    against a constant rather than as a rule about what is allowed: a rule ("cli.py may import
    loop") would silently admit a second and a tenth import, and the whole point of an exemption
    in this file is that widening it costs a diff somebody has to defend.
    """
    edges = _edges_into_exempt_packages()
    unexpected = sorted(
        f"{one}:{lineno} imports {dotted!r}"
        for one, dotted, lineno in edges
        if not any(
            one == module and (dotted == prefix or dotted.startswith(f"{prefix}."))
            for module, prefix in _DOCUMENTED_EDGES
        )
    )
    assert not unexpected, (
        "the reward path reaches an exempt package by an undocumented edge: "
        + ", ".join(unexpected)
        + "\n\nWHY THIS IS A FAILURE: bakeoff/ and loop/ are exempt from the inference ban only"
        " because nothing guarded can reach them. Every edge into them is documented — "
        + ", ".join(
            f"{module} importing {prefix!r}, function-locally, for a subcommand door"
            for module, prefix in _DOCUMENTED_EDGES
        )
        + " — and each is written out in _DOCUMENTED_EDGES so that a new one lands in a diff"
        " rather than by omission. Move the shared code, invert the dependency, or argue for"
        " another edge here and extend the constant; do not add these packages to"
        " GUARDED_ROOTS, which would fail the inference ban honestly and put the pressure on"
        " the ban itself."
    )
    assert edges, (
        "no module under the guarded roots imports either exempt package at all.\n\n"
        "WHY THIS IS A FAILURE: this is anti-vacuity, not a requirement that the edges exist for"
        " their own sake. The assertion above is a statement about the members of `edges`, so an"
        " empty walk satisfies it perfectly while proving nothing — and the documented edges are"
        " real lines in cli.py today. If every such command was genuinely removed, delete the"
        " `loop` exemption and this test together rather than leaving a green check over an"
        " empty set."
    )


def test_the_documented_edges_into_the_exempt_packages_are_function_local() -> None:
    """The half that actually protects the reward: the edges are not in the module graph.

    An exemption reasoned as *"cli.py only calls the loop when the operator asked for a night
    or a gate"* is worth nothing if the imports sit at the top of the file: Python executes
    them on **every** invocation, so ``whetstone verify --task ... --patch ...`` would load
    ``whetstone.loop``, which loads the bake-off, which is one function-local import away from
    ``mlx_lm``. The distinction between a sound exemption and a fig leaf is entirely the
    indentation, so it is asserted rather than described.

    Walked with ``ast`` over the file's own bytes, and looked up by *containment* in a function
    body rather than by column offset: an import nested inside a ``try`` inside a function is
    still function-local, and a column check would call it module scope.
    """
    module = Path("whetstone/cli.py")
    tree = ast.parse((SRC / module).read_bytes(), filename=str(SRC / module))

    local: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if isinstance(inner, (ast.Import, ast.ImportFrom)):
                    local.add(inner.lineno)

    edges = [
        (one, dotted, lineno)
        for one, dotted, lineno in _edges_into_exempt_packages()
        if one == module
    ]
    assert edges, (
        f"{module} imports neither exempt package, so this test proves nothing.\n\n"
        "WHY THIS IS A FAILURE: anti-vacuity. The loop exemption's reason names these edges; if"
        " they are gone, the reason is stale and must be removed with it."
    )
    at_module_scope = sorted(
        f"{one}:{lineno} imports {dotted!r}" for one, dotted, lineno in edges if lineno not in local
    )
    assert not at_module_scope, (
        "a documented edge into an exempt package is at module scope: "
        + ", ".join(at_module_scope)
        + "\n\nWHY THIS IS A FAILURE: a module-scope import executes on every invocation of the"
        " CLI, including `whetstone verify` — the reward's own entry point. The loop exemption's"
        " entire argument is that `whetstone.loop.night` and `whetstone.loop.gate` are reached"
        " only when an operator asked for a night or a gate; at module scope that argument is"
        " false and mlx_lm is transitively on the reward path with every guard in this tree"
        " still green. Move the imports back inside the handlers."
    )
