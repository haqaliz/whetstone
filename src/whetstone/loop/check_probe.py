"""The probe decision: night #1's go/no-go as a deterministic answer over one run directory.

`docs/planning/p2-rollouts/night-door/runbook.md:78-80` pre-commits the rule in prose — *"the
night proceeds iff the probe completes with the control arm `PASS` on every draw and a
non-empty seed map"* — and this module turns that sentence into a pure, read-only,
inference-free decision: `run_check(run)` reads **one** probe run directory's `ledger.json`
and returns a `ProbeReport`. Nothing runs, nothing is generated, nothing is published.

Two conditions carry the decision, exactly as pre-committed and nothing more:

- **The control fold is `PASS` on every draw**, read from `draws_recorded[].harness` per draw
  per source and compared against `Status` by identity. This is a *document assertion*, never
  a measurement: the night's own rankable gate aborts with `HarnessNotProven` before a ledger
  is written, so a genuinely-written ledger cannot carry a non-`PASS` fold — the exit-1 case
  exists to catch a doctored ledger or a future regression in the night's own gate.
- **The recorded seed map is non-empty** (`len(seeds) > 0`, literally). Recorded-only, never
  re-derived, and never grown into a coverage assertion: the pre-committed rule sets no bar
  beyond non-emptiness.

Refusals come first, each by name and all exit-2: a directory without a ledger is not a run
(`NotARun`), a ledger that fails the schema gate is unreadable (`LedgerUnreadable`, via
`ledger.read` by identity), a run whose `task_set.probe` is not an int is a full night
(`NotAProbe`), and a run that is missing a recorded draw, a declared source, or a draw's
journal is incomplete (`IncompleteRun`). Journals are checked for **existence only** — a
journal full of corrupt lines still exists, deliberately: the ledger is the completeness
authority, and parsing journal content would silently grow a new bar the pre-committed rule
never set.

The two sources, the ledger's name and reader, the verdict vocabulary, and the evidence path
derivation are all composed **by identity** from the modules that write them, asserted `is`
in the test suite: a second spelling of any of them would be a second answer to a question
one document already answers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whetstone.loop.draws import evidence_paths
from whetstone.loop.ledger import LEDGER_FILE, LedgerUnreadable
from whetstone.loop.ledger import read as read_ledger
from whetstone.loop.night import EVIDENCE_DIR, PRIVATE, PUBLIC
from whetstone.verify.verdict import Status

#: The two sources, by identity from the night that writes them. A third name here would be
#: a second answer to "which sources exist", and the check would then be able to disagree
#: with the document it is reading.
SOURCES = (PRIVATE, PUBLIC)


class NotARun(ValueError):
    """The directory named holds no `ledger.json`, so it is not a night-written run.

    Refused rather than read for what happens to be there: a probe decision over an
    unidentified run directory would prove nothing about any night.
    """


class NotAProbe(ValueError):
    """The run's ledger declares a full night (`task_set.probe` null), never a probe.

    A decision gate over a run that was never a probe would prove nothing about the night:
    the probe exists to prove the harness cheaply before a night commits behind it, and a
    full night's ledger answers none of that.
    """


class IncompleteRun(ValueError):
    """A probe run missing a recorded draw, a declared source, or a draw's journal.

    Refused before any decision: a gate over a half-recorded run would prove nothing about
    the night, and a schema-valid-but-empty state is a different fact from an absent one.
    """


#: What the CLI turns into a usage error rather than a traceback: everything an operator can
#: fix by retyping the command or by pointing at a different directory. Collected here so the
#: door maps them to the usage code without a chain of per-module excepts; `ValueError`
#: closes the tuple — the named refusals first, and a door that crashes on an unforeseen
#: `ValueError` with a traceback is worse than a named exit-2.
REFUSALS: tuple[type[Exception], ...] = (
    NotARun,
    LedgerUnreadable,
    NotAProbe,
    IncompleteRun,
    ValueError,
)


@dataclass(frozen=True)
class ProbeReport:
    """What the check decided, and the counts it read the decision from."""

    #: Whether the probe satisfies the pre-committed rule.
    proceed: bool

    #: The named violation when the probe fails the rule, else `None`.
    violation: str | None

    #: The declared draw count.
    draws: int

    #: How many draws the ledger actually records.
    draws_recorded: int

    #: How many sources the control fold was read over.
    sources: int

    #: The probe's declared sample size.
    probe: int

    #: How many seeds the ledger records.
    seeds: int


def run_check(run: Path) -> ProbeReport:
    """Decide a probe run's go/no-go from one run directory.

    The order is the design: the run is identified before it is read (a directory without a
    ledger is not a night-written run, whatever else it holds), the ledger goes through
    `ledger.read` by identity (a doctored document refuses before any decision), the probe
    identity is proven, and only then is anything decided. A check that read a doctored
    document and reported "proceed" would be worse than no check.
    """
    ledger = run / LEDGER_FILE
    if not ledger.is_file():
        raise NotARun(
            f"{str(run)!r} holds no {LEDGER_FILE!r}, so it is not a night-written run. "
            "Refused rather than read for whatever is there: a probe decision over an "
            "unidentified run proves nothing about any night"
        )
    payload = read_ledger(ledger)
    probe = _probe_of(payload, run)
    _require_complete(payload, run)
    for entry in payload["draws_recorded"]:
        for source in SOURCES:
            value = entry["harness"].get(source)
            if value != Status.PASS:
                return _report(
                    proceed=False,
                    violation=(
                        f"draw {entry['attempt']} ({source}): harness is {value}"
                    ),
                    payload=payload,
                    probe=probe,
                )
    seeds: Any = payload.get("seeds", ())
    if len(seeds) == 0:
        return _report(
            proceed=False,
            violation="the seed map is empty",
            payload=payload,
            probe=probe,
        )
    return _report(proceed=True, violation=None, payload=payload, probe=probe)


def disclosure(report: ProbeReport) -> tuple[str, ...]:
    """The lines the check's caller prints: the decision and the counts it was read from.

    A refused run's harness values are never rendered: the violation names the draw and the
    source, and a status vocabulary has no place in a decision that reads none — `UNVERIFIED`
    is never rendered as `PASS`.
    """
    lines = [
        f"probe: {'PROCEED' if report.proceed else 'DO NOT PROCEED'}",
        f"draws: {report.draws}; recorded: {report.draws_recorded}",
        f"sources: {report.sources}",
        f"probe: {report.probe}",
        f"seeds: {report.seeds}",
    ]
    if report.violation is not None:
        lines.append(f"violation: {report.violation}")
    return tuple(lines)


def _report(
    *,
    proceed: bool,
    violation: str | None,
    payload: Mapping[str, Any],
    probe: int,
) -> ProbeReport:
    """One `ProbeReport` with every count read from the payload the decision was made on."""
    return ProbeReport(
        proceed=proceed,
        violation=violation,
        draws=payload["draws"],
        draws_recorded=len(payload["draws_recorded"]),
        sources=len(SOURCES),
        probe=probe,
        seeds=len(payload.get("seeds", ())),
    )


def _probe_of(payload: Mapping[str, Any], run: Path) -> int:
    """The declared probe size, refusing a run whose ledger never declared one."""
    task_set = payload.get("task_set")
    if not isinstance(task_set, dict):
        raise NotAProbe(
            f"{str(run)!r} is not a probe run: its ledger carries no task set. A decision "
            "gate over a run that was never a probe would prove nothing about the night"
        )
    probe = task_set.get("probe")
    if not isinstance(probe, int):
        raise NotAProbe(
            f"{str(run)!r} is not a probe run: task_set.probe is {probe!r}, not an int. A "
            "decision gate over a run that was never a probe would prove nothing about the "
            "night"
        )
    return probe


def _require_complete(payload: Mapping[str, Any], run: Path) -> None:
    """Every declared draw, source, and journal must be present before any decision.

    Journals are checked for existence only, never parsed — content is the night's own
    record, and reading it as a bar would re-litigate what "control arm PASS" means.
    """
    recorded: Any = payload.get("draws_recorded", ())
    draws = payload.get("draws")
    if len(recorded) != draws:
        raise IncompleteRun(
            f"{str(run)!r} records {len(recorded)} of {draws} declared draws. Refused before "
            "any decision: a gate over a half-recorded run proves nothing about the night"
        )
    for entry in recorded:
        attempt = entry.get("attempt")
        if not isinstance(attempt, int):
            raise IncompleteRun(
                f"{str(run)!r} records a draw without an attempt number. Refused rather than "
                "skipped: a draw the gate cannot name is a draw it cannot prove complete"
            )
        harness = entry.get("harness") or {}
        missing = [source for source in SOURCES if source not in harness]
        if missing:
            raise IncompleteRun(
                f"draw {attempt} records no harness for {missing[0]!r}. Refused rather than "
                "skipped: a draw whose control fold cannot be read is a draw the gate cannot "
                "decide"
            )
        journal, _ = evidence_paths(run / EVIDENCE_DIR, attempt)
        if not journal.is_file():
            raise IncompleteRun(
                f"draw {attempt} declares no journal at {str(journal)!r}. Refused before any "
                "decision: a draw that left no evidence is a draw that cannot be proven to "
                "have run"
            )


__all__ = [
    "REFUSALS",
    "SOURCES",
    "IncompleteRun",
    "NotAProbe",
    "NotARun",
    "ProbeReport",
    "disclosure",
    "run_check",
]