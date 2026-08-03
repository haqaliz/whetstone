"""The task contract and its operator-file loader.

A `Task` is what the verifier is pointed at: a known-broken commit, the tests that must go
green, the tests that must stay green, and — the part that makes the reward mean anything —
the **operator-held golden test blobs**.

**`test_blobs` is the whole boundary.** It is both the restore source (STRICT rewrites every
operator-held test from golden after applying the patch) and the rejection set (a patch that
touches one of those paths is refused before anything runs). A policy that could author its
own `test_blobs` would be handing the verifier the exam it is graded against, so the only way
to obtain a Task is `load_task(operator_file)`. Nothing here reads a patch, a diff, or a
rollout, and `test_no_task_is_ever_sourced_from_policy_output` asserts that absence
structurally — by census of what returns a `Task` — so a future policy-output loader breaks
the build rather than silently opening the hole.

**Blob contents are raw bytes, never `str`.** A path or a file decoded to text reintroduces
the unicode-normalisation trap: two genuinely different byte sequences can compare equal once
decoded, and the comparisons downstream (does this patch touch a held path, does the restored
file match golden) must run on the same bytes throughout. The manifest therefore carries each
blob base64-encoded, and it is decoded to bytes here and left that way.

**A verdict must not be decided by the dependency resolver's clock.** `environment` pins the
interpreter and the exact dependency set a task is verified under, and it is required. This is
not a precaution — it is an incident. SWE-bench's `pallets__flask-5063` declares `click>=8.0`
with no upper bound; resolved today that is click 8.4.2, which removed `CliRunner(mix_stderr=)`,
so four `pass_to_pass` tests failed and STRICT returned FAIL for a patch that was correct. A
**false FAIL**, produced by the calendar rather than by the code. Pinning click 8.1.3, werkzeug
2.3.0 and jinja2 3.1.2 made the same task fully green. Those pins were chosen by hand; they are
not derivable from the repository's own metadata, which is why the manifest has to carry them.

No adversary is involved, so this is not one of the ten catalogued cheats — but it corrupts the
reward identically, and a reward that moves with the index is not execution-grounded. Hence
every pin must be an exact `==`: a range does not weaken the guarantee, it removes it, handing
the version — and the verdict — back to whatever the index serves that morning.

**Nor may a verdict be decided by a checkout outside the run.** `environment.import_roots` is
the second half of the same requirement, and it is an incident too. A `src`-layout project is
imported by package name (`import <pkg>`, never `import src.donor A`), so the name resolves
through whatever the interpreter's `sys.path` offers — and a venv provisioned with an editable
install rooted at some *other* checkout answers it first. Measured on the first real donor: a
task **PASSED with no patch applied**, because the tree that satisfied its tests was the
provisioning checkout, not the one the patch was applied to. Declaring the import roots is what
lets the reward put the run's own checkout ahead of any residual install, so the verdict is a
statement about *this* checkout. Like the pins, they cannot be inferred from the repository at
verification time, which is why the manifest has to carry them.

**Fail-closed.** A malformed file, a missing field, an unknown field, an empty `test_blobs` —
each is a named `ValueError`, never a silent default. The failure mode this refuses is
specific and severe: a Task that silently loaded with no `test_blobs` has no restore source
and an empty rejection set, so STRICT would report PASS on a patch that deleted the failing
test. A quiet default here is a false reward downstream.

Zero runtime dependencies: stdlib `json` and `base64` only. No model is consulted — this is a
parse and a set of type checks — and the reward-path import guard covers this package.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

#: The provenance labels the contract understands. `source` is a record, not a check: the
#: contract a public task is verified against is identical to a private one's. An unknown
#: value is still rejected, because a manifest that says `synthetic` means something the
#: loader was never told how to treat, and guessing is how a silent default gets in.
_SOURCES = frozenset({"public", "private"})

#: Exactly the fields a manifest may carry. Both halves matter: a MISSING field is rejected
#: so nothing loads as a default, and an UNKNOWN field is rejected so a typo'd `fail_to_pas`
#: cannot leave the operator verifying against less than they wrote.
_FIELDS = frozenset(
    {
        "task_id",
        "source",
        "repo_url",
        "base_commit",
        "environment",
        "problem_statement",
        "fail_to_pass",
        "pass_to_pass",
        "test_blobs",
        "provenance",
    }
)

#: Exactly the keys an `environment` may carry, enforced for the same reason as `_FIELDS`: a
#: typo'd `pin` that was ignored would leave the task resolving nothing while looking pinned.
_ENVIRONMENT_KEYS = frozenset({"python", "pins", "import_roots"})

#: An exact pin, and nothing else. Deliberately stricter than PEP 508, and deliberately parsed
#: here rather than by a requirements library: the reward path carries zero runtime dependencies,
#: and everything PEP 508 additionally allows — a range, an extra, an environment marker, a URL —
#: is a way for the resolved version to depend on the resolving machine or the resolving day.
#: Only `name==version` cannot. `===` (PEP 440 arbitrary equality) fails the version half, since
#: its leading `=` is not an alphanumeric; whitespace around the operator fails for the same
#: reason a non-canonical blob path does — the manifest is not rewritten on the operator's behalf.
_PIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9._+!-]*$")

#: PEP 503 name normalisation, used ONLY to decide whether two pins name the same package.
#: `Flask_Login` and `flask-login` are one package, and pinning it twice is the resolver's clock
#: again — the pin the operator wrote is stored verbatim either way.
_NAME_SEPARATORS = re.compile(r"[-_.]+")


@dataclass(frozen=True)
class Environment:
    """The interpreter, the exact dependency set, and where the code under test lives.

    `pins` is a **tuple**, not a list inside a mapping. The difference is the whole point: a
    `Mapping[str, Any]` would satisfy the manifest and leave the list mutable, so code holding
    a frozen `Task` could still append a pin between the load and the run — and the set that
    decided the verdict would no longer be the set the operator declared.

    Empty `pins` is legitimate and is not the same as an absent `environment`. `[]` says
    *nothing is installed, so nothing can drift*; an absent field says nothing at all, and the
    resolver would answer for it.

    `python` is checked to be a non-empty string and no further. Which interpreter that names,
    and how it is provisioned, is the ingester's business — the reward path is a runner, not a
    package manager.

    `import_roots` are the repository-relative directories the interpreter is told to import
    from: `["src"]` for a `src` layout, `["."]` for a flat one. Empty is legitimate and means
    *nothing needs adding* — a flat repository already has its code at `sys.path[0]` under
    `python -m pytest`. See `_import_roots` for why the field is required rather than inferred.
    """

    python: str
    pins: tuple[str, ...]
    import_roots: tuple[str, ...]


@dataclass(frozen=True)
class Task:
    """One verifiable task. Frozen, and obtainable only from `load_task`.

    `fail_to_pass` must go green and `pass_to_pass` must stay green; together they are the
    exact set of node ids the verifier expects to see executed, which is why neither may
    contain a duplicate. `test_blobs` maps a repository-relative path to that file's golden
    contents **as bytes** — the operator's artifact, and the one thing the policy must never
    supply. `environment` pins what the task runs under and says where its code lives, so the
    verdict is decided by the patch — not by the day it was resolved, and not by a checkout
    somewhere else on the disk. `source` and `provenance` are records of how the task was
    obtained; they do not change how it is verified.
    """

    task_id: str
    source: str
    repo_url: str
    base_commit: str
    environment: Environment
    problem_statement: str
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    test_blobs: Mapping[str, bytes]
    provenance: Mapping[str, str]


def load_task(path: Path) -> Task:
    """Load a task from an operator-controlled JSON manifest. The ONLY way to obtain a Task.

    The manifest is a JSON object carrying exactly `_FIELDS`, with `test_blobs` as a mapping
    from a repository-relative path to that file's golden contents, base64-encoded. Anything
    malformed — unreadable, not JSON, not an object, a missing or unknown field, a wrongly
    typed value, an unusable blob — raises `ValueError` naming the problem. Never a silent
    default, never a raw traceback.

    It takes a filesystem `path`, never a patch, a diff, or a rollout. That signature IS the
    provenance boundary: the task is sourced from a file the operator controls, not from
    anything the policy produced.
    """
    file_path = Path(path)
    try:
        text = file_path.read_text()
    except OSError as exc:
        raise ValueError(f"could not read task manifest {str(file_path)!r}: {exc}") from exc

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"task manifest {str(file_path)!r} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(
            f"task manifest {str(file_path)!r} must contain a JSON object, "
            f"got {type(raw).__name__}"
        )

    where = f"task manifest {str(file_path)!r}"
    _check_fields(raw, where=where)

    source = _string(raw, "source", where=where)
    if source not in _SOURCES:
        known = ", ".join(sorted(_SOURCES))
        raise ValueError(f"{where} declares unknown source {source!r}; known sources are: {known}")

    fail_to_pass = _node_ids(raw, "fail_to_pass", where=where)
    if not fail_to_pass:
        raise ValueError(
            f"{where} has an empty fail_to_pass; a task with no test that must go green "
            "would reward a patch that changed nothing"
        )
    pass_to_pass = _node_ids(raw, "pass_to_pass", where=where)

    shared = set(fail_to_pass) & set(pass_to_pass)
    if shared:
        raise ValueError(
            f"{where} lists {sorted(shared)!r} in both fail_to_pass and pass_to_pass; the "
            "verifier compares the executed node ids against these lists, and a node id in "
            "both makes that comparison ambiguous"
        )

    return Task(
        task_id=_string(raw, "task_id", where=where),
        source=source,
        repo_url=_string(raw, "repo_url", where=where),
        base_commit=_string(raw, "base_commit", where=where),
        environment=_environment(raw, where=where),
        problem_statement=_string(raw, "problem_statement", where=where),
        fail_to_pass=fail_to_pass,
        pass_to_pass=pass_to_pass,
        test_blobs=_test_blobs(raw, where=where),
        provenance=_provenance(raw, where=where),
    )


def _check_fields(raw: dict[str, Any], *, where: str) -> None:
    """Exactly `_FIELDS`, no more and no less — missing and unknown are both errors."""
    missing = sorted(_FIELDS - raw.keys())
    if missing:
        named = ", ".join(repr(name) for name in missing)
        raise ValueError(f"{where} is missing required field {named}")

    unknown = sorted(raw.keys() - _FIELDS)
    if unknown:
        named = ", ".join(repr(name) for name in unknown)
        raise ValueError(
            f"{where} carries unknown field {named}; an unknown field is rejected rather "
            "than ignored, because a typo'd key would otherwise verify the task against "
            "less than the operator declared"
        )


def _string(raw: dict[str, Any], key: str, *, where: str) -> str:
    value = raw[key]
    if not isinstance(value, str):
        raise ValueError(f"{where} has a non-string {key} ({type(value).__name__}); expected str")
    return value


def _node_ids(raw: dict[str, Any], key: str, *, where: str) -> tuple[str, ...]:
    """A list of pytest node ids, with duplicates rejected rather than collapsed."""
    value = raw[key]
    if not isinstance(value, list):
        raise ValueError(
            f"{where} has a non-list {key} ({type(value).__name__}); expected a list of "
            "pytest node ids"
        )
    for item in value:
        if not isinstance(item, str):
            raise ValueError(
                f"{where} has a non-string entry in {key} ({type(item).__name__}); every "
                "node id must be a string"
            )
    duplicates = sorted({item for item in value if value.count(item) > 1})
    if duplicates:
        raise ValueError(
            f"{where} repeats {duplicates!r} in {key}; the verifier compares the executed "
            "node ids against this list, and a duplicate makes that comparison ambiguous"
        )
    return tuple(value)


def _test_blobs(raw: dict[str, Any], *, where: str) -> Mapping[str, bytes]:
    """The operator-held golden tests: repository-relative path -> raw bytes.

    Decoded from base64 to `bytes` and left there. The paths are checked to be relative and
    non-escaping because STRICT restores each one into a checkout, and a path that resolved
    outside it would write wherever the manifest said — and canonical, because it also
    compares them literally against what git reports. See `_check_blob_path`.
    """
    value = raw["test_blobs"]
    if not isinstance(value, dict):
        raise ValueError(
            f"{where} has a non-object test_blobs ({type(value).__name__}); expected a "
            "mapping from path to base64-encoded contents"
        )
    if not value:
        raise ValueError(
            f"{where} has an empty test_blobs; it is both the restore source and the "
            "rejection set, so an empty one leaves the verifier with nothing to restore and "
            "nothing to refuse"
        )

    blobs: dict[str, bytes] = {}
    for path, encoded in value.items():
        if not isinstance(path, str):
            raise ValueError(f"{where} has a non-string test_blobs path ({path!r})")
        _check_blob_path(path, where=where)
        if not isinstance(encoded, str):
            raise ValueError(
                f"{where} has non-string contents for test_blobs path {path!r} "
                f"({type(encoded).__name__}); expected a base64-encoded string"
            )
        try:
            blobs[path] = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                f"{where} has contents for test_blobs path {path!r} that are not valid "
                f"base64: {exc}"
            ) from exc
    return blobs


def _check_blob_path(path: str, *, where: str) -> None:
    """Repository-relative, staying inside the repository, and spelled the way git spells it.

    The third of those is not cosmetic. A blob path is stored as the raw manifest string and
    is compared **literally** downstream: STRICT asks whether a patch touched one of these
    paths by matching the strings git reports against these keys. Git always reports its own
    canonical spelling, so a key written `./tests/x.py` matches nothing git ever says and
    drops straight out of the patch-REJECTION set — while `checkout / "./tests/x.py"` still
    resolves to the very file the restore writes golden bytes over. The refusal and the
    restore would then disagree about which files the operator holds, and the disagreement is
    invisible: the manifest looks right, the file is right, only the comparison is blind.

    **Rejected, not normalised.** Rewriting the operator's path for them would be exactly the
    silent default this loader refuses everywhere else — and the caller who wrote a
    non-canonical path has a bug worth hearing about, not a spelling worth fixing behind
    their back. An ingester emits canonical paths; a human is told which one to write.
    """
    pure = PurePosixPath(path)
    if pure.is_absolute() or path.startswith("/"):
        raise ValueError(
            f"{where} has an absolute test_blobs path {path!r}; blob paths must be relative "
            "to the repository under test"
        )
    if ".." in pure.parts:
        raise ValueError(
            f"{where} has a test_blobs path {path!r} that would escape the repository under "
            "test; blob paths must stay inside the checkout"
        )
    if not pure.parts:
        raise ValueError(
            f"{where} has an empty test_blobs path {path!r}; a blob path must name a file "
            "inside the repository under test"
        )
    canonical = str(pure)
    if canonical != path:
        raise ValueError(
            f"{where} has a non-canonical test_blobs path {path!r}; write it as {canonical!r}. "
            "Blob paths are compared literally against the paths git reports, so a second "
            "spelling of a held test is a path the patch-rejection check will never match"
        )


def _environment(raw: dict[str, Any], *, where: str) -> Environment:
    """The interpreter, the exact dependency set, and the import roots. All three required.

    A missing `environment` is rejected rather than defaulted because the default would be
    "whatever the resolver picks", and that is a verdict decided by the calendar: flask's
    unbounded `click>=8.0` resolves today to a click that removed `CliRunner(mix_stderr=)`,
    turning a correct patch into a FAIL. A pin that is not an exact `==` is the same failure
    written out longhand, so it is refused by name — including the extras and markers that make
    the resolved set depend on the machine doing the resolving.

    `import_roots` is required for the same reason and not a weaker one, which is worth stating
    because `[]` is a legal value and looks like a default. It is not: `[]` is the operator
    saying *this repository needs nothing added to the import path*, which is true of a flat
    layout and false of every `src` layout. An **absent** field would have to mean "nobody
    said", and the code that ran would then be whatever the interpreter happened to have
    installed — the inert-checkout hole in the module docstring, reopened by omission.
    """
    value = raw["environment"]
    if not isinstance(value, dict):
        raise ValueError(
            f"{where} has a non-object environment ({type(value).__name__}); expected an "
            "object carrying 'python', 'pins' and 'import_roots'"
        )

    missing = sorted(_ENVIRONMENT_KEYS - value.keys())
    if missing:
        named = ", ".join(repr(name) for name in missing)
        raise ValueError(f"{where} is missing required environment key {named}")
    unknown = sorted(value.keys() - _ENVIRONMENT_KEYS)
    if unknown:
        named = ", ".join(repr(name) for name in unknown)
        raise ValueError(
            f"{where} carries unknown environment key {named}; an unknown key is rejected "
            "rather than ignored, because a typo'd one would leave the task looking pinned "
            "while pinning nothing"
        )

    python = value["python"]
    if not isinstance(python, str):
        raise ValueError(
            f"{where} has a non-string environment python ({type(python).__name__}); expected "
            "an interpreter version such as '3.12'"
        )
    if not python:
        raise ValueError(
            f"{where} has an empty environment python; an unnamed interpreter is the same "
            "silence a missing environment would be"
        )

    pins = value["pins"]
    if not isinstance(pins, list):
        raise ValueError(
            f"{where} has non-list environment pins ({type(pins).__name__}); expected a list "
            "of exact '==' requirements"
        )

    seen: dict[str, str] = {}
    for pin in pins:
        if not isinstance(pin, str):
            raise ValueError(
                f"{where} has a non-string entry in environment pins "
                f"({type(pin).__name__}); every pin must be a string"
            )
        if not _PIN.match(pin):
            raise ValueError(
                f"{where} has environment pin {pin!r}, which is not an exact '==' requirement; "
                "write it as 'name==version'. A range, an extra, or a marker does not weaken "
                "the pin, it removes it — the version, and with it the verdict, goes back to "
                "whatever the index serves at resolution time, which is the hole this field "
                "exists to close"
            )
        package = _NAME_SEPARATORS.sub("-", pin.split("==", 1)[0]).lower()
        if package in seen:
            raise ValueError(
                f"{where} pins {package!r} twice ({seen[package]!r} and {pin!r}); two versions "
                "of one package leaves the choice to the resolver, which is the same hole a "
                "range opens"
            )
        seen[package] = pin

    return Environment(
        python=python, pins=tuple(pins), import_roots=_import_roots(value, where=where)
    )


def _import_roots(value: dict[str, Any], *, where: str) -> tuple[str, ...]:
    """Where the code under test lives, relative to the checkout. Never absolute, never escaping.

    Each entry is joined onto the run's own checkout and handed to the interpreter as an import
    path, ahead of anything installed. The three checks below are the three ways that join could
    stop being about this checkout: an absolute path ignores it outright, a `..` segment climbs
    out of it, and a non-canonical spelling is the trap `_check_blob_path` documents at length —
    written here as its own function rather than shared, because the two differ in exactly one
    place and it matters. A blob path must name a **file**, so an empty path is rejected there;
    an import root may name the **checkout root itself**, which is the flat layout and is spelled
    `"."`. Sharing the check would have meant either allowing an empty blob path or forbidding
    the commonest import root.

    Order is preserved, not sorted: it is the order the interpreter will search, and a manifest
    that listed two roots both providing a module meant the first one.
    """
    roots = value["import_roots"]
    if not isinstance(roots, list):
        raise ValueError(
            f"{where} has non-list environment import_roots ({type(roots).__name__}); expected "
            "a list of repository-relative directories such as ['src']"
        )
    for root in roots:
        if not isinstance(root, str):
            raise ValueError(
                f"{where} has a non-string entry in environment import_roots "
                f"({type(root).__name__}); every import root must be a string"
            )
        pure = PurePosixPath(root)
        if pure.is_absolute() or root.startswith("/"):
            raise ValueError(
                f"{where} has an absolute environment import root {root!r}; import roots are "
                "relative to the checkout under test, and an absolute one would point the run "
                "at code no patch was applied to"
            )
        if ".." in pure.parts:
            raise ValueError(
                f"{where} has an environment import root {root!r} that would escape the "
                "checkout under test; the code under test must be the checkout the patch was "
                "applied to"
            )
        canonical = str(pure)
        if canonical != root:
            raise ValueError(
                f"{where} has a non-canonical environment import root {root!r}; write it as "
                f"{canonical!r}"
            )
    return tuple(roots)


def _provenance(raw: dict[str, Any], *, where: str) -> Mapping[str, str]:
    """How the task was obtained, and when. A record — it does not gate the reward.

    Empty is allowed: an operator who recorded nothing has recorded nothing, and inventing a
    provenance would be worse than an absent one. Non-string values are still rejected, so
    the record cannot quietly become a structure nothing downstream knows how to render.
    """
    value = raw["provenance"]
    if not isinstance(value, dict):
        raise ValueError(
            f"{where} has a non-object provenance ({type(value).__name__}); expected a "
            "mapping of strings"
        )
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(
                f"{where} has a non-string provenance entry ({key!r}: {item!r}); every "
                "provenance key and value must be a string"
            )
    return dict(value)


__all__ = ["Environment", "Task", "load_task"]
