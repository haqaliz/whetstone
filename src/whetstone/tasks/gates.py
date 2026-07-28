"""The four eligibility gates, and the ledger of everything they turned away.

**The filter is the deliverable, not the instances.** Source A is far narrower than the roadmap
assumed — measured over the real 300 rows of SWE-bench-Lite, 192 are not addressable as pytest
node ids at all, 61 need a compiled scientific stack, 12 carry node ids SWE-bench itself has
corrupted, and 11 sit in an interpreter era that is verified dead on anything modern. What
survives is a ceiling of 24, of which one is proven end to end. A corpus that small is only worth
publishing if the *reason* each instance is in or out is proven per instance rather than assumed,
and that is what this module does.

**Each gate proves. None assumes.**

1. **Format** — every declared id parses as a pytest node id. This is the one gate that is a pure
   string question, and it is deliberately narrow: it kills django's unittest-runner form and
   sympy's bare names, and it lets SWE-bench's 12 truncated parametrised ids **through**. A
   bracket-balance rule would catch those and would be a guess wearing a gate's clothes; the only
   assumption-free detector is asking pytest to find them.
2. **Collectability** — every id is collectable in the **real checkout**. This is where the
   truncated ids die, by execution rather than by pattern. It matters more than it sounds: an
   unfindable id makes pytest exit 4, which `strict.py` maps to UNVERIFIED, and an UNVERIFIED
   aborts the whole run rather than grading anything.
3. **Environment** — the pinned set resolves **and imports** on the nominated interpreter.
   **Install-exit-0 is not evidence**, and that is measured rather than feared: `sphinx==3.5.4`,
   `pytest==4.6.9`, `pylint==2.13.9` and `requests==2.4.0` all install cleanly on arm64 CPython
   3.12, and two of them cannot be imported there. It is the same false green the CI `mlx` step
   already guards against.
4. **Liveness** — the two-run FAIL-then-PASS proof, which is `liveness.prove_live` unchanged. A
   second implementation of that check would be a second definition of what a task is.

**The gates are numbered in the order the PRD defines them and executed in a different order,
which is stated here rather than left for a reader to discover.** Proving an id collectable *in
the real checkout* requires the checkout to be importable, and that is gate 3's answer. Run
before it, gate 2 would report every instance uncollectable for a reason that has nothing to do
with its ids — an assumption dressed as a proof, which is exactly what these gates exist to
refuse. So the execution order is format, environment, collectability, liveness, and the ledger
records the gate that decided, never the position it ran in.

**Era-pins are not derivable, and are therefore not guessed.** A repository declares ranges —
flask says `click>=8.0` at every commit it has ever had — so `environment_setup_commit` cannot
answer which versions the era used. Source B escapes this because a donor's `uv.lock` is its
owner's own recorded resolution; source A has no such artifact. The pins come from a committed,
hand-determined table, and an instance with no entry is **rejected at gate 3 and ledgered**,
never resolved on the day the filter happened to run.

**Nothing vanishes.** Every refusal is a `Rejection` carrying the gate that made it, and
`write_ineligible` refuses to write a ledger whose counts do not account for every input. That
arithmetic is what makes "24 of 300 were eligible" evidence rather than a claim.

Zero runtime dependencies. No model. The network is never touched: gate 2 and gate 4 execute
inside the Seatbelt sandbox, which denies it outright, and gate 3's installs are `--offline`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

#: The four gates, named. The ledger's `gate` field is only meaningful against a closed set:
#: a typo'd value would silently create a fifth category nobody could count.
GATE_FORMAT = "format"
GATE_COLLECTABILITY = "collectability"
GATE_ENVIRONMENT = "environment"
GATE_LIVENESS = "liveness"
GATES = (GATE_FORMAT, GATE_COLLECTABILITY, GATE_ENVIRONMENT, GATE_LIVENESS)

#: The order the gates actually run in, recorded in the ledger so the discrepancy with the
#: numbering above is published rather than discovered. See the module docstring.
EXECUTION_ORDER = (GATE_FORMAT, GATE_ENVIRONMENT, GATE_COLLECTABILITY, GATE_LIVENESS)

#: Names the shape of the committed rejection ledger.
INELIGIBLE_SCHEMA = "whetstone-source-a-ineligible/1"

#: The separator that makes a string addressable by pytest at all. Everything before the first
#: one is a file path; everything after is a chain of classes and a test name.
_SEPARATOR = "::"

#: A python module pytest can import. Checked rather than assumed because sympy's declarations
#: name no file at all and django's name a dotted module, and neither is a path.
_SUFFIX = ".py"

#: Leading or trailing whitespace on a declared id. Rejected rather than stripped, exactly as
#: `task._check_blob_path` refuses to normalise a path on the operator's behalf: an id the
#: manifest carries is compared literally against what pytest reports.
_UNTRIMMED = re.compile(r"^\s|\s$")


class Ineligible(ValueError):
    """One instance did not clear a gate, and the gate is part of the exception.

    The gate is carried on the exception rather than parsed back out of the message, because the
    ledger records it as a field and a message is prose. A rejection whose gate a reader has to
    infer is a rejection they cannot count.
    """

    def __init__(self, gate: str, message: str) -> None:
        if gate not in GATES:
            raise ValueError(f"unknown gate {gate!r}; the gates are {list(GATES)}")
        super().__init__(message)
        self.gate = gate


@dataclass(frozen=True)
class Rejection:
    """One instance the filter turned away, and the gate that turned it away.

    Frozen and validated in `__post_init__` so a rejection cannot be constructed under a gate
    name that exists nowhere else — the same fail-closed posture `load_task` takes towards an
    unknown field.
    """

    instance_id: str
    gate: str
    reason: str

    def __post_init__(self) -> None:
        if self.gate not in GATES:
            raise ValueError(f"unknown gate {self.gate!r}; the gates are {list(GATES)}")


@dataclass(frozen=True)
class Ineligibility:
    """The rejection ledger as read back: the counts, and every refusal behind them."""

    counts: Mapping[str, int]
    rejections: tuple[Rejection, ...]


def check_format(node_ids: Sequence[str]) -> None:
    """Gate 1. Every declared id must parse as a pytest node id, or `Ineligible`.

    **What this gate is for.** django declares its tests in the form its own unittest runner
    prints — `test_ticket_11293 (queries.tests.Queries1Tests)` — and sympy declares bare function
    names with no file path at all. Between them that is 192 of Lite's 300 instances. Neither is
    a node id, and neither becomes one by parsing harder: addressing them would mean a second
    execution path with its own adversarial-corpus obligation, which is out of scope by name.

    **What this gate deliberately is not for.** SWE-bench itself carries 12 parametrised ids
    split on whitespace, of the shape
    `tests/test_cli.py::test_locate_app[cliapp.factory-create_app2("foo",`. A bracket-balance
    rule would reject them here and would look like a stronger gate. It would be a string
    heuristic standing in for a proof — and the day the corruption takes another shape, it passes
    silently. Those ids leave here intact and die at gate 2, where pytest is asked to find them.

    Every offending id is reported, not just the first: a rejection naming one of three makes a
    three-line problem look like a one-line one.
    """
    if not node_ids:
        raise Ineligible(
            GATE_FORMAT,
            "the instance declares no tests at all. Every id check would pass vacuously — there "
            "is nothing to check — and the resulting task would have nothing that must go green",
        )

    offenders = [(node_id, reason) for node_id in node_ids if (reason := _malformed(node_id))]
    if offenders:
        detail = "; ".join(f"{node_id!r} ({reason})" for node_id, reason in offenders)
        raise Ineligible(
            GATE_FORMAT,
            f"{len(offenders)} of {len(node_ids)} declared test(s) are not addressable as pytest "
            f"node ids: {detail}. An id pytest cannot address is not a test this reward can be "
            f"grounded on, and there is no parse that turns one into one",
        )


def _malformed(node_id: str) -> str | None:
    """Why this id is not a pytest node id, or `None` if it is one.

    Returns the reason rather than a boolean so the rejection can say which of six problems it
    hit. A gate that reports "malformed" gets "fixed" by whatever silences it.
    """
    if not node_id:
        return "empty"
    if _UNTRIMMED.search(node_id):
        return "leading or trailing whitespace, which is not stripped on the caller's behalf"
    if _SEPARATOR not in node_id:
        return (
            "no '::' separator — this is django's unittest-runner form or a bare sympy test "
            "name, neither of which names a file pytest can address"
        )

    file_part, _, remainder = node_id.partition(_SEPARATOR)
    if not file_part.endswith(_SUFFIX):
        return f"the part before '::' is not a {_SUFFIX} file"

    pure = PurePosixPath(file_part)
    if pure.is_absolute() or file_part.startswith("/"):
        return "an absolute path, which names a checkout other than the one under test"
    if ".." in pure.parts:
        return "a path escaping the repository under test"
    if str(pure) != file_part:
        return f"a non-canonical path; write it as {str(pure)!r}"

    if not remainder or any(not part for part in remainder.split(_SEPARATOR)):
        return "an empty component after '::', which addresses nothing"
    return None


def write_ineligible(
    path: Path,
    rejections: Sequence[Rejection],
    *,
    eligible: Sequence[str],
    input_count: int,
) -> None:
    """Write the rejection ledger, refusing any ledger that does not account for every input.

    **The arithmetic is enforced here rather than reviewed.** The failure it prevents is
    invisible in a diff: a run that lost three instances between the draw and the gates writes a
    perfectly well-formed ledger describing a smaller world, and every rate computed over it is
    correct about the wrong denominator.

    Identity is checked as well as the totals, because the totals alone can be satisfied by an
    instance counted twice — one rejection that is also in the eligible set balances the sum
    while an input has still disappeared.
    """
    ineligible = [rejection.instance_id for rejection in rejections]
    overlap = sorted(set(ineligible) & set(eligible))
    if overlap:
        raise ValueError(
            f"{overlap} are recorded as both eligible and rejected. The counts would still add "
            f"up, and an input would still have vanished"
        )
    if len(ineligible) + len(eligible) != input_count:
        raise ValueError(
            f"the ledger does not account for every input: {len(eligible)} eligible plus "
            f"{len(ineligible)} rejected is not {input_count}. A silently dropped instance is a "
            f"denominator nobody chose, and the whole value of this file is that it has none"
        )

    document = {
        "schema": INELIGIBLE_SCHEMA,
        "gates": list(GATES),
        "execution_order": list(EXECUTION_ORDER),
        "counts": {
            "input": input_count,
            "eligible": len(eligible),
            "ineligible": len(ineligible),
            **{
                gate: sum(1 for rejection in rejections if rejection.gate == gate)
                for gate in GATES
            },
        },
        "eligible": sorted(eligible),
        "instances": [
            {
                "instance_id": rejection.instance_id,
                "gate": rejection.gate,
                "reason": rejection.reason,
            }
            for rejection in sorted(rejections, key=lambda rejection: rejection.instance_id)
        ],
    }
    location = Path(path)
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


def read_ineligible(path: Path) -> Ineligibility:
    """Read the rejection ledger back, or raise `ValueError` naming the file."""
    location = Path(path)
    try:
        raw = json.loads(location.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"ledger {str(location)!r} could not be read: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema") != INELIGIBLE_SCHEMA:
        raise ValueError(
            f"ledger {str(location)!r} is not a source-A rejection ledger: expected an object "
            f"whose schema is {INELIGIBLE_SCHEMA!r}"
        )
    counts = raw.get("counts")
    instances = raw.get("instances")
    if not isinstance(counts, dict) or not isinstance(instances, list):
        raise ValueError(f"ledger {str(location)!r} carries no counts or no instances")

    try:
        rejections = tuple(
            Rejection(
                instance_id=str(entry["instance_id"]),
                gate=str(entry["gate"]),
                reason=str(entry["reason"]),
            )
            for entry in instances
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"ledger {str(location)!r} carries a malformed rejection: {exc}") from exc
    return Ineligibility(counts=dict(counts), rejections=rejections)


__all__ = [
    "EXECUTION_ORDER",
    "GATES",
    "GATE_COLLECTABILITY",
    "GATE_ENVIRONMENT",
    "GATE_FORMAT",
    "GATE_LIVENESS",
    "INELIGIBLE_SCHEMA",
    "Ineligibility",
    "Ineligible",
    "Rejection",
    "check_format",
    "read_ineligible",
    "write_ineligible",
]
