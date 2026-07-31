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

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest
from test_no_inference_on_reward_path import GUARDED_ROOTS

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
#: **It is empty, and empty is the right resting state.** Every child of the package is
#: currently guarded, which is the strongest configuration this file can report and the one a
#: reader should expect to find. An earlier draft of this change exempted ``__init__.py`` as a
#: documented residual; it is guarded instead, because closing it cost one line and a residual
#: is for a hole that is hard to close, not one nobody had to accept.
#:
#: Note what an empty mapping does *not* weaken: the two assertions that read it iterate
#: nothing here, and their teeth come from the synthetic controls below, which run the same
#: functions over trees that do have exemptions. That is the arrangement
#: ``tests/test_docs.py:173-185`` uses for a guard whose real-tree answer is "nothing wrong".
EXEMPT: Mapping[str, str] = {}


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
