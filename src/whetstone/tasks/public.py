"""The source-A filter: pool -> draw -> four gates -> manifests, and a ledger of everything else.

**The filter is the deliverable; the instances are its output.** Source A is far narrower than
the roadmap assumed, and a corpus this small is only worth publishing if the reason each instance
is in or out was *proved* per instance. So this module composes the four gates in
`whetstone.tasks.gates`, mints a manifest for every survivor, and records every refusal in
`tasks/public/ineligible.json` with the gate that made it. Rejected plus eligible equals the
input — enforced at write time, not reviewed.

**The order the gates run in, and why it is not the order they are numbered in.** Proving an id
collectable *in the real checkout* requires the checkout to be importable, which is gate 3's
answer; run before it, gate 2 would report every instance uncollectable for a reason that has
nothing to do with its ids. So one instance goes:

1. **declare** — deduplicate the two id lists and make them disjoint (PRD C4). SWE-bench's lists
   commonly overlap, and `load_task` refuses an overlap outright.
2. **gate 1, format** — string-only, and cheap enough to pay before a clone.
3. **checkout** — clone at `base_commit`; compute the held set; refuse an instance whose test
   patch **adds** a test file (see `held_for`).
4. **gate 3, environment** — the hand-determined era-pins, provisioned and *imported*.
5. **overlay** — apply the test patch. It is the test patch and there is no second mechanism:
   STRICT's unconditional restore reproduces exactly this overlay from `test_blobs` before every
   reward run (PRD § 5.4).
6. **gate 2, collectability** — pytest is asked to find exactly the declared ids.
7. **mint** — write the manifest to scratch and load it through `load_task`.
8. **gate 4, liveness** — `prove_live`, the shipped reward run twice, unchanged and unaided.

Only then is the manifest copied into the corpus. **The corpus directory never holds an unproven
manifest**, not even transiently, because `load_tasks` deliberately refuses to skip anything it
finds there — an unproven file sitting in it would be verified as though somebody had vouched for
it.

**A rejection is a finding and the run continues.** A filter that stopped at the first awkward
instance would produce a corpus whose size was decided by the dataset's ordering.

**Where the network is.** Cloning a public repository and provisioning an era-pinned environment
both reach out, so — exactly like the fetch — the filter is a **human-run step whose output is
committed**. Everything downstream reads that output. No test in this suite runs it: the loop is
tested with the gates stubbed, and the gates are tested for real in their own files.
"""

from __future__ import annotations

import base64
import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from whetstone import __version__
from whetstone.tasks.donor import GitFailed, run_git
from whetstone.tasks.environment import NotProvisionable, import_roots
from whetstone.tasks.fetch import DATASET, Instance, read_pool
from whetstone.tasks.gates import (
    GATE_COLLECTABILITY,
    GATE_ENVIRONMENT,
    GATE_LIVENESS,
    EraPins,
    Ineligible,
    Rejection,
    check_collectable,
    check_environment,
    check_format,
    era_pins,
    read_era_pins,
    write_ineligible,
)
from whetstone.tasks.held import conftest_floor_at
from whetstone.tasks.ledger import Clock, utc_now
from whetstone.tasks.liveness import Liveness, NotLive, prove_live
from whetstone.verify.repo import PatchError, apply_patch, declared_paths
from whetstone.verify.task import load_task

#: Where the committed source-A artifacts live, relative to the tasks root. Named here because
#: this module writes them and `tasks/README.md` documents them; a second spelling would let the
#: two drift apart silently.
INELIGIBLE_NAME = "ineligible.json"
INSTANCES_DIRECTORY = "instances"
PUBLIC_DIRECTORY = "public"

#: What `pass_to_pass` means for a source-A task, recorded in every manifest's provenance. It is
#: SWE-bench's own declaration and nothing more — not "the repository's suite" — and a reader who
#: assumed the broader reading would overstate what the corpus covers.
PASS_TO_PASS_SCOPE = "swe-bench-declared"

#: The suffix that makes a repository file a test module the overlay is allowed to hold. Anything
#: else a test patch touches (a fixture, a golden file) is deliberately **not** held: the held set
#: is the restore source and the rejection set, and holding a data file the gold patch legitimately
#: rewrites would make the task permanently unpassable.
_TEST_SUFFIX = ".py"

#: How one instance is run through the gates. Injected so the loop's conservation property can be
#: asserted against the real bookkeeping with the gates stubbed out — what is under test there is
#: which instances came out, and that is exactly where a silent drop hides.
Runner = Callable[..., Path]


@dataclass(frozen=True)
class Eligible:
    """One instance that cleared all four gates and is now in the corpus."""

    instance_id: str
    manifest: Path
    liveness: Liveness | None
    python: str


@dataclass(frozen=True)
class FilterReport:
    """What one filter run produced, including — especially — what it refused.

    `rejected` is carried rather than dropped because it is the publishable half. "24 of 300 were
    eligible" is a claim; the ledger behind it is evidence.
    """

    eligible: tuple[Eligible, ...]
    rejected: tuple[Rejection, ...]
    ledger: Path | None


def declared(instance: Instance) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The instance's two id lists, deduplicated and made disjoint (PRD C4).

    SWE-bench's lists commonly overlap and commonly repeat, and `load_task` refuses both outright
    — an id in both makes the executed-set comparison ambiguous, and so does a duplicate. The
    overlap is resolved in favour of `fail_to_pass` because that is the stronger claim: a test
    that must go green must also end green, so dropping it from `pass_to_pass` loses nothing,
    while the reverse would drop a required flip.

    Declaration order is preserved rather than sorted. It costs nothing and it is a fact the
    dataset carries.
    """
    fail: list[str] = []
    for node_id in instance.fail_to_pass:
        if node_id not in fail:
            fail.append(node_id)
    passing: list[str] = []
    for node_id in instance.pass_to_pass:
        if node_id not in passing and node_id not in fail:
            passing.append(node_id)
    return tuple(fail), tuple(passing)


def held_for(checkout: Path, base_commit: str, test_patch: str) -> tuple[str, ...]:
    """The held set for one instance: the test files its test patch touches, plus the floor.

    **The refusal here is the one that costs source A most of what is left, and it is honest.**
    SWE-bench's test patches frequently *add* a test file. `strict.py` answers UNVERIFIED for a
    task whose `test_blobs` are not in the checkout at `base_commit` — there is nothing to restore
    them over, so the task is malformed rather than the patch being wrong — and that guard is
    fail-closed on the reward path. Relaxing it is out of scope by name. Deriving a different
    `base_commit` at which the added files exist is not available either: the file does not exist
    at any ancestor, because the test patch is what creates it. So the instance is rejected at a
    gate, with the added paths in the message, rather than minted as something no one could ever
    verify.

    The `conftest.py` floor is the cheat-10 structural minimum (PRD D4/M5) and applies to every
    ingested task, source A included: pytest loads a conftest by position, so a held test can
    depend on one without naming it, and a patch that rewrites an undeclared conftest passes the
    declared tests against fixtures it wrote itself. Computed by `held.conftest_floor_at`, the
    same rule source B uses — two spellings would be two rules.
    """
    try:
        touched = declared_paths(test_patch, Path(checkout))
    except PatchError as exc:
        raise Ineligible(
            GATE_COLLECTABILITY,
            f"the instance's test patch could not be parsed against its own base commit: {exc}",
        ) from exc

    tests = tuple(path for path in touched if path.endswith(_TEST_SUFFIX))
    if not tests:
        raise Ineligible(
            GATE_COLLECTABILITY,
            f"the instance's test patch touches no python file ({list(touched)}), so there is "
            f"nothing for the task to hold. test_blobs is both the restore source and the "
            f"rejection set, and an empty one leaves the reward nothing to restore and nothing "
            f"to refuse",
        )

    present = _tree(Path(checkout), base_commit)
    added = sorted(path for path in tests if path not in present)
    if added:
        raise Ineligible(
            GATE_COLLECTABILITY,
            f"the instance's test patch ADDS {added}, which do not exist at base_commit "
            f"{base_commit[:12]}. strict.py refuses a task whose test_blobs are not in the "
            f"checkout — there is nothing to restore them over, so it answers UNVERIFIED for "
            f"every patch forever. That guard is fail-closed on the reward path and is not "
            f"relaxed here, and no ancestor commit carries these files because the test patch is "
            f"what creates them. The instance is refused rather than minted unverifiable",
        )

    floor = conftest_floor_at(Path(checkout), base_commit, tests)
    return tuple(sorted({*tests, *floor}))


def manifest_for(
    instance: Instance,
    *,
    checkout: Path,
    held: Sequence[str],
    python: str,
    pins: Sequence[str],
    import_roots: Sequence[str],
    filtered_at: str,
) -> dict[str, object]:
    """The manifest for one instance, in the shape `load_task` accepts.

    **The blobs are read from the checkout the test patch has already been applied to**, as raw
    bytes. That is what makes the overlay the test patch: STRICT restores every held path from
    these bytes after applying a candidate patch, so what the manifest carries *is* what the
    reward will put on disk. Read as bytes and left that way — a round trip through this
    process's text handling would translate a line ending the reward would then report as a
    difference nobody made.

    `provenance` is flat strings only, because `load_task` refuses anything else, and it records
    what a later train/held-out split will need: the dataset the instance came from, its id, the
    commit SWE-bench nominates for environment setup, and what `pass_to_pass` is scoped to.
    """
    blobs = {path: (Path(checkout) / path).read_bytes() for path in held}
    fail, passing = declared(instance)
    return {
        "task_id": instance.instance_id,
        "source": "public",
        "repo_url": instance.repo_url,
        "base_commit": instance.base_commit,
        "environment": {
            "python": python,
            "pins": list(pins),
            "import_roots": list(import_roots),
        },
        "problem_statement": instance.problem_statement,
        "fail_to_pass": list(fail),
        "pass_to_pass": list(passing),
        "test_blobs": {
            path: base64.b64encode(contents).decode("ascii") for path, contents in blobs.items()
        },
        "provenance": {
            "dataset": DATASET,
            "instance_id": instance.instance_id,
            "environment_setup_commit": instance.environment_setup_commit,
            "pass_to_pass_scope": PASS_TO_PASS_SCOPE,
            "filtered_at": filtered_at,
            "filter": f"whetstone {__version__}",
        },
    }


def filter_instances(
    instances: Sequence[Instance],
    *,
    out: Path,
    tasks_root: Path,
    run: Runner,
    **options: object,
) -> FilterReport:
    """Run every instance through `run`, mint the survivors, ledger the rest. Nothing vanishes.

    `run` is the per-instance pipeline — `run_gates` in production — and is a parameter so this
    loop's bookkeeping can be asserted with the gates stubbed out. What is under test in that
    case is which instances came out the other side, which is exactly where a silent drop hides.

    The ledger is written **even when nothing survives**, and that is deliberate: if source A
    yields no eligible instance at all, the record of every refusal is the entire result, and a
    filter that wrote no file when it minted no task would leave that result nowhere.
    """
    destination = Path(out)
    destination.mkdir(parents=True, exist_ok=True)

    eligible: list[Eligible] = []
    rejected: list[Rejection] = []
    for instance in instances:
        try:
            manifest = run(instance, out=destination, **options)
        except Ineligible as exc:
            rejected.append(
                Rejection(instance_id=instance.instance_id, gate=exc.gate, reason=str(exc))
            )
            continue
        eligible.append(
            Eligible(
                instance_id=instance.instance_id,
                manifest=manifest,
                liveness=None,
                python="",
            )
        )

    ledger = Path(tasks_root) / INELIGIBLE_NAME
    write_ineligible(
        ledger,
        rejected,
        eligible=[entry.instance_id for entry in eligible],
        input_count=len(instances),
    )
    return FilterReport(
        eligible=tuple(eligible), rejected=tuple(rejected), ledger=ledger
    )


def run_gates(
    instance: Instance,
    *,
    out: Path,
    scratch: Path,
    table: Mapping[str, EraPins],
    timeout: float,
    index: Path | None = None,
    clock: Clock = utc_now,
) -> Path:
    """One instance, all four gates, or `Ineligible` naming the gate that refused it.

    Written to a scratch directory and proved there; only a manifest that has cleared gate 4 is
    copied into `out`. The corpus directory never holds an unproven task, because `load_tasks`
    refuses to skip anything it finds there — an unproven manifest sitting in it would be
    verified as though somebody had vouched for it.
    """
    fail, passing = declared(instance)
    check_format([*fail, *passing])

    # Gate 3's cheapest half, and it runs before the clone on purpose. Era-pins are recorded by
    # hand, so the table is sparse by construction — measured over the real pool, 107 of the 108
    # instances that clear gate 1 have no entry. Cloning each of those to discover a fact that
    # was already on disk would cost hours and would teach nobody anything; the provisioning half
    # still runs where it belongs, below, because it is the half that has to prove something.
    pins = era_pins(table, instance.instance_id)

    # Per instance, never shared: two instances in one workspace would clone into the same
    # directory and provision into the same venv, and the second one's verdict would be about
    # the first one's tree.
    workspace = (Path(scratch) / instance.instance_id).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    checkout = workspace / "repo"
    try:
        run_git(
            ["clone", "--quiet", "--no-checkout", instance.repo_url, str(checkout)],
            cwd=workspace,
        )
        run_git(["checkout", "--quiet", "--detach", instance.base_commit], cwd=checkout)
    except GitFailed as exc:
        raise Ineligible(
            GATE_COLLECTABILITY,
            f"the instance's checkout could not be materialised from {instance.repo_url} at "
            f"{instance.base_commit[:12]}: {exc}. Nothing about its declared ids could be "
            f"proved, so it is refused rather than assumed eligible",
        ) from exc

    held = held_for(checkout, instance.base_commit, instance.test_patch)

    try:
        roots = import_roots(checkout)
    except NotProvisionable as exc:
        raise Ineligible(
            GATE_ENVIRONMENT,
            f"where the instance's code lives could not be read from its own layout: {exc}. It "
            f"is refused rather than guessed at — a wrong import root does not fail loudly, it "
            f"leaves the declared tests importing a copy of the project from outside the run and "
            f"reporting PASS",
        ) from exc

    provisioned = check_environment(
        pins.requirements, venv=workspace / "venv", python=pins.python, index=index
    )

    # The overlay IS the test patch (PRD 5.4). STRICT's unconditional restore reproduces exactly
    # this state from `test_blobs` before every reward run, so no second mechanism exists here.
    try:
        apply_patch(instance.test_patch, checkout)
    except PatchError as exc:
        raise Ineligible(
            GATE_COLLECTABILITY,
            f"the instance's own test patch does not apply at base_commit "
            f"{instance.base_commit[:12]}: {exc}",
        ) from exc

    check_collectable(
        [*fail, *passing],
        checkout=checkout,
        workspace=workspace,
        timeout=timeout,
        interpreter=provisioned.interpreter,
        import_roots=roots,
    )

    staged = workspace / f"{instance.instance_id}.json"
    staged.write_text(
        json.dumps(
            manifest_for(
                instance,
                checkout=checkout,
                held=held,
                python=provisioned.python,
                pins=provisioned.pins,
                import_roots=roots,
                filtered_at=clock(),
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    task = load_task(staged)

    try:
        prove_live(
            task,
            instance.patch,
            sandbox_root=workspace / "liveness",
            timeout=timeout,
            interpreter=provisioned.interpreter,
        )
    except NotLive as exc:
        raise Ineligible(GATE_LIVENESS, str(exc)) from exc

    destination = Path(out) / staged.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(staged, destination)
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    """Run the filter over the committed pool and write the corpus and the ledger.

    A **human-run step**, like the fetch, and for the same reason: it clones public repositories
    and provisions era-pinned environments, both of which reach out. Its output is committed and
    everything downstream reads that. Run it as::

        python -m whetstone.tasks.public --pool tasks/public/pool.json

    Deliberately not a `whetstone` subcommand. Every subcommand the CLI advertises claims to be
    offline, and a networked one would make that claim conditional on which flag was passed.

    `--only` restricts the run to named instances, which is how a single instance is re-proved
    without spending the whole funnel again. It narrows the ledger's denominator to exactly what
    was run, which is why the ledger records that denominator rather than assuming 300.
    """
    import argparse
    import tempfile

    parser = argparse.ArgumentParser(
        prog="python -m whetstone.tasks.public",
        description=(
            "Filter the committed source-A pool through the four eligibility gates. Mints a "
            "manifest for every instance that clears all four and records every refusal, with "
            "the gate that made it, in ineligible.json. Clones repositories and provisions "
            "environments, so it is run by a human and its output is committed."
        ),
    )
    parser.add_argument("--pool", type=Path, default=Path("tasks/public/pool.json"))
    parser.add_argument("--era-pins", type=Path, default=Path("tasks/public/era-pins.json"))
    parser.add_argument("--tasks-root", type=Path, default=Path("tasks/public"))
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        metavar="<instance_id>",
        help="restrict the run to these instances; the ledger records the narrowed denominator",
    )
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args(argv)

    instances = read_pool(args.pool)
    if args.only:
        wanted = set(args.only)
        instances = tuple(
            instance for instance in instances if instance.instance_id in wanted
        )
        missing = sorted(wanted - {instance.instance_id for instance in instances})
        if missing:
            parser.error(f"the pool carries no instance(s) {missing}")
    table = read_era_pins(args.era_pins)

    out = Path(args.tasks_root) / INSTANCES_DIRECTORY
    with tempfile.TemporaryDirectory(prefix="whetstone-filter-") as root:
        report = filter_instances(
            instances,
            out=out,
            tasks_root=Path(args.tasks_root),
            run=run_gates,
            scratch=Path(root).resolve(),
            table=table,
            timeout=args.timeout,
        )

    for entry in report.eligible:
        print(f"{entry.instance_id}: eligible — {entry.manifest}")
    print(
        f"eligible {len(report.eligible)}, ineligible {len(report.rejected)}, "
        f"of {len(instances)} instance(s)"
    )
    print(f"ledger: {report.ledger}")
    return 0 if report.eligible else 1



def _tree(repo: Path, sha: str) -> frozenset[str]:
    """Every file path in the commit's tree. One git call, then set membership."""
    try:
        raw = run_git(["ls-tree", "-r", "-z", "--name-only", sha], cwd=Path(repo))
    except GitFailed as exc:
        raise Ineligible(
            GATE_COLLECTABILITY,
            f"the instance's base commit {sha[:12]} could not be read in the checkout: {exc}",
        ) from exc
    return frozenset(path for path in raw.split("\0") if path)


__all__ = [
    "INELIGIBLE_NAME",
    "INSTANCES_DIRECTORY",
    "PASS_TO_PASS_SCOPE",
    "PUBLIC_DIRECTORY",
    "Eligible",
    "FilterReport",
    "Runner",
    "declared",
    "filter_instances",
    "held_for",
    "main",
    "manifest_for",
    "run_gates",
]


if __name__ == "__main__":  # pragma: no cover - the human-run entry point
    raise SystemExit(main())
