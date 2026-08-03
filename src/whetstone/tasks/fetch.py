"""SWE-bench-Lite rows -> the committed source-A pool. The one place Whetstone touches a network.

Source A is the **externally checkable half** of the corpus, and that is the whole reason it is
worth its cost: source B is mined from the user's own repositories and can only ever be attested
to (`tasks/README.md`), while anyone can re-fetch these 300 rows and check our manifests against
them. This module is where they come from.

**Two halves, kept apart as a correctness property rather than a tidiness one.**

- `rows_to_pool` and `pool_document` are **pure**. No clock, no randomness and — by construction
  — no network: `urllib` is imported *inside* `main`, so importing this module cannot put an HTTP
  client in scope. `tests/test_public_fetch.py` asserts that with an `ast` walk, which is the only
  thing that can assert it, and carries an anti-vacuity control so the guard cannot go quietly
  dead. That property is what keeps the whole test suite offline.
- `main` touches the network exactly once and is **run by a human**. Its output,
  `tasks/public/pool.json`, is committed; everything downstream reads the committed artifact. So
  a dataset outage cannot break CI, and a refetch is a reviewable diff rather than a silent
  change to what the corpus is about.

**Why Whetstone needs its own fetch rather than the sibling project's pool.** That committed
pool carries exactly six keys, and none of `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS` or
`environment_setup_commit`. Those five are the difference between describing an instance and
being able to ground a reward on it: without `test_patch` a task has no held tests, without
`FAIL_TO_PASS` it has nothing that must go green, and without `patch` there is no reference patch
to prove it live with. The sibling project's pool contributes provenance and base commits; the
grounding has to come from here.

**The dataset server truncates large cells, and that is the failure this module exists to catch
early.** `/rows` returns `truncated_cells` beside each record, and a truncated `test_patch` is
the worst possible shape of bad data: every field is present, the record is well-formed, and the
diff simply stops in the middle. Committed, it would produce an instance that fails at a gate for
a reason that has nothing to do with the instance. So a row whose *needed* columns were truncated
is dropped and **its id is published in the header** — the pool never silently carries a fragment,
and a reader can see exactly what the server would not hand over.

**No row filter is applied here, deliberately.** The four gates decide eligibility and the
rejection ledger records every refusal with the gate that made it, and that ledger's whole value
is the conservation property: rejected plus eligible equals the input. A fetch that quietly
dropped repositories would make that true of a denominator somebody had already trimmed. The
header states the projection rule and states that it filters nothing.

Zero runtime dependencies: stdlib `json` and `re`, plus `urllib` inside `main`. No model.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The dataset coordinates, published verbatim into the header so the pool is re-issuable
#: without reading this file.
DATASET = "princeton-nlp/SWE-bench_Lite"
CONFIG = "default"
SPLIT = "test"
ROWS_ENDPOINT = "https://datasets-server.huggingface.co/rows"

#: Names the shape of the committed file, so a later format change is a visible one rather than
#: new code silently reinterpreting an old file. Same discipline as `ledger.LEDGER_SCHEMA`.
POOL_SCHEMA = "whetstone-source-a-pool/1"

#: How a `repo` slug becomes a clone URL. Stated here because `main` never builds one and the
#: manifest does: a reader comparing our `repo_url` against the dataset needs the rule.
GITHUB_URL = "https://github.com/{repo}.git"

#: The dataset columns the pool carries, mapped to the name it carries them under. The two
#: shouted ones are lower-cased so the pool reads like what it becomes — a manifest's
#: `fail_to_pass` and `pass_to_pass` — and so no downstream module has to remember which
#: spelling it is holding. Everything the dataset additionally carries (`hints_text`,
#: `version`, `created_at`) is deliberately not projected: an unused column is a column whose
#: truncation would drop rows for nothing.
COLUMNS: Mapping[str, str] = {
    "instance_id": "instance_id",
    "repo": "repo",
    "base_commit": "base_commit",
    "environment_setup_commit": "environment_setup_commit",
    "problem_statement": "problem_statement",
    "patch": "patch",
    "test_patch": "test_patch",
    "FAIL_TO_PASS": "fail_to_pass",
    "PASS_TO_PASS": "pass_to_pass",
}

#: The two columns SWE-bench stores as a JSON-encoded string rather than as a list. Left as
#: strings they stay truthy, serialise fine and round-trip fine — and every downstream loop over
#: them iterates over *characters*.
_ENCODED_LISTS = ("FAIL_TO_PASS", "PASS_TO_PASS")

#: `owner/name`, anchored at both ends, so a URL, a bare name or a three-segment path all fail.
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")

#: Where the header's revision may be reported. The envelope has never carried one at the time
#: of writing, so `null` is the honest value and `REVISION_NOTE` says why.
_REVISION_KEYS = ("revision", "dataset_revision", "sha")

REVISION_NOTE = (
    "the /rows envelope reported no dataset revision when this pool was fetched; a null "
    "revision means the fetch could not be pinned to one, not that it was not checked"
)

#: What the header promises about filtering, in the file rather than in a docstring, because the
#: rejection ledger's conservation property is stated against this pool's own count.
_ELIGIBILITY_NOTE = (
    "no row is filtered at fetch. Eligibility is decided by the four gates and every refusal "
    "is recorded in tasks/public/ineligible.json with the gate that made it, so the pool is the "
    "denominator the ledger conserves"
)


class PoolError(ValueError):
    """The dataset is not the shape this transform was written against.

    Raised rather than repaired. Every case below is a statement that our assumption about
    SWE-bench's schema is wrong, and the remedy is a human reading the message — not a silent
    normalisation that produces a corpus built on a guess.
    """


@dataclass(frozen=True)
class Instance:
    """One pool record, as everything downstream reads it.

    A dataclass rather than the raw mapping because the gates ask it questions —
    `repo_url`, `fail_to_pass` — and a mapping would let a typo'd key read `None` and be
    filtered out as "an instance with no declared tests" rather than raise.

    `environment_setup_commit` is carried and is deliberately *not* used to pick versions.
    SWE-bench nominates it as the commit whose metadata describes the era's environment, but
    that metadata is exactly what does not answer the question — flask declares `click>=8.0` at
    every commit it has ever had. It is provenance here, and the era-pins come from a committed,
    hand-determined table (see `gates`).
    """

    instance_id: str
    repo: str
    base_commit: str
    environment_setup_commit: str
    problem_statement: str
    patch: str
    test_patch: str
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]

    @property
    def repo_url(self) -> str:
        """The clone URL, built from the slug the fetch refused to let be a URL."""
        return GITHUB_URL.format(repo=self.repo)


def rows_to_pool(
    envelopes: Sequence[Mapping[str, Any]],
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    """Project `/rows` envelopes into pool records. Returns `(records, truncated_instance_ids)`.

    Pure: no clock, no network, no randomness. Every envelope is either projected or accounted
    for — a truncated one is dropped **and named**, and anything else that does not fit the
    schema raises. There is no third outcome, because the third outcome is a silent drop.

    Records come back sorted by `instance_id` so the committed pool's bytes do not move when the
    server changes page ordering.
    """
    records: list[dict[str, Any]] = []
    truncated: list[str] = []
    for envelope in envelopes:
        row = envelope.get("row")
        if not isinstance(row, dict):
            raise PoolError(
                f"a /rows envelope carries no 'row' object (got {type(row).__name__}); the "
                f"server's response shape is not the one this transform was written against"
            )

        instance_id = _column(row, "instance_id")
        cut = sorted(set(envelope.get("truncated_cells") or []) & set(COLUMNS))
        if cut:
            truncated.append(instance_id)
            continue

        records.append(_record(row, instance_id=instance_id))

    records.sort(key=lambda record: str(record["instance_id"]))
    return tuple(records), tuple(sorted(truncated))


def pool_document(
    records: Sequence[Mapping[str, Any]],
    truncated: Sequence[str],
    *,
    revision: str | None,
    fetched_at: str,
    num_rows_total: int | None,
) -> dict[str, Any]:
    """The committed file: a provenance header, the dropped ids, and the records.

    The header is a **claim**, and `tests/test_public_fetch.py` checks it against the records in
    the same document — the counts equal what is beneath them, and the filter note says outright
    that nothing was filtered. That is what makes the published composition falsifiable rather
    than decorative: a regeneration that moved the data but not the claim fails loudly.

    `fetched_at` and `revision` are arguments rather than read here, which is what keeps this
    function free of the clock and the network and therefore testable offline.
    """
    return {
        "schema": POOL_SCHEMA,
        "dataset": DATASET,
        "config": CONFIG,
        "split": SPLIT,
        "revision": revision,
        "revision_note": REVISION_NOTE,
        "source_url": ROWS_ENDPOINT,
        "repo_url_rule": GITHUB_URL,
        "fetched_at": fetched_at,
        "num_rows_total": num_rows_total,
        "filters": {
            "columns": sorted(COLUMNS.values()),
            "rows_filtered": 0,
            "eligibility_decided_by": _ELIGIBILITY_NOTE,
            "truncated_cell_rule": (
                "a row whose response reported any of the projected columns as truncated is "
                "dropped and its instance_id is listed under 'truncated'; a truncated patch is "
                "corrupt data that looks well-formed"
            ),
        },
        "counts": {"records": len(records), "truncated": len(truncated)},
        "truncated": sorted(truncated),
        "instances": [dict(record) for record in records],
    }


def read_pool(path: Path) -> tuple[Instance, ...]:
    """Read the committed pool, or raise `ValueError` naming the file.

    Fail-closed like `load_task` and `read_ledger`: a pool that half-parsed would let the gates
    run against a corpus smaller than the one on disk, and every rate computed downstream would
    have a denominator nobody chose.
    """
    location = Path(path)
    try:
        raw = json.loads(location.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"pool {str(location)!r} could not be read: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema") != POOL_SCHEMA:
        raise ValueError(
            f"pool {str(location)!r} is not a source-A pool: expected an object whose schema is "
            f"{POOL_SCHEMA!r}"
        )
    instances = raw.get("instances")
    if not isinstance(instances, list):
        raise ValueError(f"pool {str(location)!r} carries no 'instances' list")

    try:
        return tuple(
            Instance(
                instance_id=str(record["instance_id"]),
                repo=str(record["repo"]),
                base_commit=str(record["base_commit"]),
                environment_setup_commit=str(record["environment_setup_commit"]),
                problem_statement=str(record["problem_statement"]),
                patch=str(record["patch"]),
                test_patch=str(record["test_patch"]),
                fail_to_pass=tuple(record["fail_to_pass"]),
                pass_to_pass=tuple(record["pass_to_pass"]),
            )
            for record in instances
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"pool {str(location)!r} carries a malformed instance: {exc}") from exc


def _record(row: Mapping[str, Any], *, instance_id: str) -> dict[str, Any]:
    """One projected record, with every column present and both id lists parsed."""
    record: dict[str, Any] = {}
    for column, name in COLUMNS.items():
        if column in _ENCODED_LISTS:
            record[name] = _node_ids(row, column, instance_id=instance_id)
            continue
        record[name] = _column(row, column)

    if not _SLUG.match(record["repo"]):
        raise PoolError(
            f"instance {instance_id!r} reports repo {record['repo']!r}, which is not an "
            f"'owner/name' slug. The clone URL is built as {GITHUB_URL!r}, so a URL here would "
            f"double-prefix and fail at checkout time — long after a batch had started. This is "
            f"refused rather than normalised: it means the dataset's shape is not the one we "
            f"assumed, and that is the thing a human needs to see"
        )
    return record


def _column(row: Mapping[str, Any], column: str) -> str:
    """One string column, present and a string, or `PoolError` naming it."""
    if column not in row:
        raise PoolError(
            f"a /rows record is missing the column {column!r}; the pool cannot be projected from "
            f"a dataset that no longer carries it, and defaulting it would produce instances "
            f"missing exactly the field a reward is grounded on"
        )
    value = row[column]
    if not isinstance(value, str):
        raise PoolError(
            f"a /rows record has a non-string {column!r} ({type(value).__name__}); expected str"
        )
    return value


def _node_ids(row: Mapping[str, Any], column: str, *, instance_id: str) -> list[str]:
    """One declared-id column, whether the server sent a list or a JSON-encoded string.

    Both shapes are accepted because only one of them is a fact about SWE-bench today; a server
    that stopped encoding the column must not become a parse failure. What is *not* accepted is
    a string that is not JSON, or a list holding anything but strings — either would put a
    non-id into a manifest, where it would be reported as a test that never ran.
    """
    if column not in row:
        raise PoolError(
            f"instance {instance_id!r} is missing the column {column!r}; a task with no declared "
            f"node ids cannot be verified against anything"
        )
    value = row[column]
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise PoolError(
                f"instance {instance_id!r} has a {column!r} that is neither a list nor valid "
                f"JSON ({exc}); left as a string every downstream loop over it would iterate "
                f"over characters"
            ) from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PoolError(
            f"instance {instance_id!r} has a {column!r} that is not a list of strings "
            f"({type(value).__name__})"
        )
    return list(value)


def main(argv: Sequence[str] | None = None) -> int:
    """Fetch the dataset and write the pool. **The only thing in Whetstone that hits a network.**

    Run by a human; its output is committed and everything else reads that. `urllib` is imported
    *inside* this function on purpose (see the module docstring): importing this module must not
    put an HTTP client in scope, and a static guard in `tests/test_public_fetch.py` enforces it
    with an anti-vacuity control.

    Run it as::

        python -m whetstone.tasks.fetch --out tasks/public/pool.json

    Deliberately not a `whetstone` subcommand. Every subcommand the CLI advertises claims to be
    offline, and a network-touching one would make that claim conditional on which flag was
    passed — a distinction nobody reads a `--help` carefully enough to keep.
    """
    import argparse
    import urllib.error
    import urllib.parse
    import urllib.request
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(
        prog="python -m whetstone.tasks.fetch",
        description=(
            "Fetch SWE-bench-Lite and write the source-A pool. Touches the network; its output "
            "is committed and is read by everything else. Applies no row filter — eligibility "
            "is decided by the four gates and recorded in tasks/public/ineligible.json."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("tasks") / "public" / "pool.json",
        help="where to write the pool (default: tasks/public/pool.json)",
    )
    parser.add_argument(
        "--page-size", type=int, default=20, help="rows per request (default: 20)"
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=300,
        help="stop after this many rows (default: the 300 rows of SWE-bench-Lite)",
    )
    args = parser.parse_args(argv)

    envelopes: list[Mapping[str, Any]] = []
    revision: str | None = None
    num_rows_total: int | None = None
    offset = 0
    while offset < args.max_rows:
        query = urllib.parse.urlencode(
            {
                "dataset": DATASET,
                "config": CONFIG,
                "split": SPLIT,
                "offset": offset,
                "length": min(args.page_size, args.max_rows - offset),
            }
        )
        url = f"{ROWS_ENDPOINT}?{query}"
        try:
            with urllib.request.urlopen(url) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise PoolError(f"{url} returned HTTP {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise PoolError(f"{url} is unreachable: {exc.reason}") from exc

        page = payload.get("rows")
        if not isinstance(page, list):
            raise PoolError(f"{url} returned no 'rows' list")
        if not page:
            break

        for key in _REVISION_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                revision = value
                break
        reported = payload.get("num_rows_total")
        if isinstance(reported, int):
            num_rows_total = reported

        envelopes.extend(page)
        offset += len(page)

    records, truncated = rows_to_pool(envelopes)
    document = pool_document(
        records,
        truncated,
        revision=revision,
        fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        num_rows_total=num_rows_total,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(
        f"wrote {out}: {len(records)} instance(s) from {len(envelopes)} row(s), "
        f"{len(truncated)} dropped as truncated"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - the human-run entry point
    raise SystemExit(main())


__all__ = [
    "COLUMNS",
    "CONFIG",
    "DATASET",
    "GITHUB_URL",
    "POOL_SCHEMA",
    "REVISION_NOTE",
    "ROWS_ENDPOINT",
    "SPLIT",
    "Instance",
    "PoolError",
    "main",
    "pool_document",
    "read_pool",
    "rows_to_pool",
]
