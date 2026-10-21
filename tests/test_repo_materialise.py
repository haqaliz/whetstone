"""Making a task's checkout from an explicit local mirror, and reusing one already there.

The failure these tests prevent was measured, twice: the one public task is processed last, and
at the end of a five-hour night the Mac had let the network go, so `materialise` raised
`could not clone 'https://github.com/pallets/flask.git'` and the whole run refused as UNVERIFIED.
The fix has to sit at `materialise`, because `provision`, both verifiers and the oracle all clone
through it into fresh destinations.

Two things are asserted here. A mapping in `WHETSTONE_REPO_MIRRORS` is an *explicit operator
input*, so an unreachable canonical URL is not an obstacle — but a mapped mirror that is missing
is a named refusal and never a quiet fall back to the network. And a destination that is already a
clean checkout is reused rather than deleted or cloned over, because the pre-warm and a killed
run's workspace both arrive that way.

Real git, real repositories (``tests/fixtures/repos``). The URLs in these tests are on
``.invalid``, so an accidental network attempt cannot succeed and cannot be mistaken for the
mirror working.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fixtures.repos import CALC_FIXED, build_task, make_patch

from whetstone.bakeoff import scoring
from whetstone.verify import repo
from whetstone.verify.repo import CheckoutError, materialise
from whetstone.verify.strict import verify_strict
from whetstone.verify.task import Task, load_task
from whetstone.verify.verdict import Status

#: Unreachable by construction (RFC 2606). A test that accidentally cloned it would fail, which
#: is the point: the mirror is the only way these tests can succeed.
_UNREACHABLE = "https://example.invalid/pallets/flask.git"

#: The env var `materialise` reads. Spelled out rather than imported so a rename is a test
#: failure and not a silent change of the operator contract.
_MIRRORS = "WHETSTONE_REPO_MIRRORS"


def _run_git(args: list[str], *, cwd: Path) -> str:
    """git with machine config off and a pinned identity, like the fixture builders."""
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "Whetstone Fixtures",
            "GIT_AUTHOR_EMAIL": "fixtures@whetstone.invalid",
            "GIT_AUTHOR_DATE": "2026-01-02T00:00:00+00:00",
            "GIT_COMMITTER_NAME": "Whetstone Fixtures",
            "GIT_COMMITTER_EMAIL": "fixtures@whetstone.invalid",
            "GIT_COMMITTER_DATE": "2026-01-02T00:00:00+00:00",
        }
    )
    completed = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, env=environment, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


def _bare_mirror(origin: Path, into: Path) -> Path:
    """A local bare repository that can stand in for the canonical remote."""
    _run_git(["clone", "--quiet", "--bare", str(origin), str(into)], cwd=into.parent)
    return into


def _retarget(manifest: Path, repo_url: str) -> Task:
    """The same task, with `repo_url` pointed somewhere else — the manifest alone changes."""
    data = json.loads(manifest.read_text())
    data["repo_url"] = repo_url
    retargeted = manifest.parent / "retargeted.json"
    retargeted.write_text(json.dumps(data))
    return load_task(retargeted)


def _head(checkout: Path) -> str:
    return _run_git(["rev-parse", "HEAD"], cwd=checkout).strip()


def _second_commit(origin: Path) -> str:
    """Give `origin` a commit after its base, and return that new commit."""
    (origin / "later.txt").write_text("a later change\n")
    _run_git(["add", "--all"], cwd=origin)
    _run_git(["commit", "--quiet", "--message", "a later commit"], cwd=origin)
    return _head(origin)


def _record_git(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Every git invocation `materialise` makes, in order, without changing what it does."""
    calls: list[list[str]] = []
    original = repo._git

    def recording(args: list[str], *, cwd: Path, stdin: str | None = None) -> str:
        calls.append(list(args))
        return original(args, cwd=cwd, stdin=stdin)

    monkeypatch.setattr(repo, "_git", recording)
    return calls


def _clone(origin: Path, into: Path) -> Path:
    _run_git(["clone", "--quiet", "--no-hardlinks", str(origin), str(into)], cwd=into.parent)
    return into


# --------------------------------------------------------------------------------------
# M1 — the mirror mapping
# --------------------------------------------------------------------------------------


def test_a_mapped_mirror_is_the_clone_source_when_the_canonical_url_is_unreachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = build_task(tmp_path / "fixture")
    mirror = _bare_mirror(fixture.origin, tmp_path / "flask-mirror.git")
    task = _retarget(tmp_path / "fixture" / "task.json", _UNREACHABLE)
    monkeypatch.setenv(_MIRRORS, json.dumps({_UNREACHABLE: str(mirror)}))

    destination = tmp_path / "checkout"
    materialise(task, destination)

    assert _head(destination) == task.base_commit
    assert (destination / "calc.py").is_file()


def test_without_a_mapping_the_canonical_url_is_still_cloned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(_MIRRORS, raising=False)
    fixture = build_task(tmp_path / "fixture")

    destination = tmp_path / "checkout"
    materialise(fixture.task, destination)

    assert _head(destination) == fixture.task.base_commit


@pytest.mark.parametrize("broken", ["missing", "not-a-repo"])
def test_a_broken_mirror_refuses_by_name_and_never_clones_the_canonical_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, broken: str
) -> None:
    build_task(tmp_path / "fixture")
    task = _retarget(tmp_path / "fixture" / "task.json", _UNREACHABLE)
    mirror = tmp_path / "flask-mirror.git"
    if broken == "not-a-repo":
        mirror.mkdir()
    monkeypatch.setenv(_MIRRORS, json.dumps({_UNREACHABLE: str(mirror)}))
    calls = _record_git(monkeypatch)

    with pytest.raises(CheckoutError) as raised:
        materialise(task, tmp_path / "checkout")

    message = str(raised.value)
    assert _UNREACHABLE in message, message
    assert str(mirror) in message, message
    assert not any(call[0] == "clone" for call in calls), (
        "a broken mirror fell back to cloning the canonical URL, which is the network access an "
        f"offline run exists to refuse: {calls}"
    )


def test_malformed_mirror_json_is_a_named_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_task(tmp_path / "fixture")
    task = _retarget(tmp_path / "fixture" / "task.json", _UNREACHABLE)
    monkeypatch.setenv(_MIRRORS, "{not json")
    calls = _record_git(monkeypatch)

    with pytest.raises(CheckoutError) as raised:
        materialise(task, tmp_path / "checkout")

    assert _MIRRORS in str(raised.value)
    assert not calls, f"a malformed mapping reached git: {calls}"


# --------------------------------------------------------------------------------------
# M2 — reusing a populated destination
# --------------------------------------------------------------------------------------


def test_a_clean_checkout_at_base_is_reused_without_cloning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(_MIRRORS, raising=False)
    fixture = build_task(tmp_path / "fixture")
    destination = _clone(fixture.origin, tmp_path / "checkout")
    task = _retarget(tmp_path / "fixture" / "task.json", _UNREACHABLE)
    calls = _record_git(monkeypatch)

    materialise(task, destination)

    assert _head(destination) == task.base_commit
    assert not any(call[0] in {"clone", "fetch"} for call in calls), calls


def test_a_clean_checkout_at_another_commit_moves_to_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(_MIRRORS, raising=False)
    fixture = build_task(tmp_path / "fixture")
    later = _second_commit(fixture.origin)
    destination = _clone(fixture.origin, tmp_path / "checkout")
    assert _head(destination) == later

    materialise(fixture.task, destination)

    assert _head(destination) == fixture.task.base_commit


def test_a_clean_checkout_without_the_base_object_is_refused_and_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(_MIRRORS, raising=False)
    fixture = build_task(tmp_path / "fixture")
    destination = tmp_path / "checkout"
    destination.mkdir()
    (destination / "keep.txt").write_text("unrelated\n")
    _run_git(["init", "--quiet"], cwd=destination)
    _run_git(["add", "--all"], cwd=destination)
    _run_git(["commit", "--quiet", "--message", "an unrelated commit"], cwd=destination)
    unrelated = _head(destination)

    with pytest.raises(CheckoutError) as raised:
        materialise(fixture.task, destination)

    assert fixture.task.base_commit in str(raised.value), str(raised.value)
    assert _head(destination) == unrelated
    assert (destination / "keep.txt").read_text() == "unrelated\n"


def test_a_dirty_checkout_is_refused_and_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(_MIRRORS, raising=False)
    fixture = build_task(tmp_path / "fixture")
    destination = _clone(fixture.origin, tmp_path / "checkout")
    (destination / "calc.py").write_text("dirty on purpose\n")

    with pytest.raises(CheckoutError) as raised:
        materialise(fixture.task, destination)

    assert "clean" in str(raised.value) or "dirty" in str(raised.value), str(raised.value)
    assert (destination / "calc.py").read_text() == "dirty on purpose\n"


def test_a_populated_non_git_directory_is_refused_and_not_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(_MIRRORS, raising=False)
    fixture = build_task(tmp_path / "fixture")
    destination = tmp_path / "checkout"
    destination.mkdir()
    (destination / "notes.txt").write_text("operator work\n")

    with pytest.raises(CheckoutError):
        materialise(fixture.task, destination)

    assert (destination / "notes.txt").read_text() == "operator work\n"


def test_a_destination_nested_in_another_repository_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(_MIRRORS, raising=False)
    fixture = build_task(tmp_path / "fixture")
    outer = tmp_path / "outer"
    outer.mkdir()
    _run_git(["init", "--quiet"], cwd=outer)
    destination = outer / "nested"
    destination.mkdir()
    (destination / "notes.txt").write_text("operator work\n")

    with pytest.raises(CheckoutError):
        materialise(fixture.task, destination)

    assert destination.is_dir()


def test_a_planted_post_checkout_hook_does_not_run_on_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(_MIRRORS, raising=False)
    fixture = build_task(tmp_path / "fixture")
    _second_commit(fixture.origin)
    destination = _clone(fixture.origin, tmp_path / "checkout")

    marker = tmp_path / "hook-ran"
    hook = destination / ".git" / "hooks" / "post-checkout"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(f'#!/bin/sh\necho ran > "{marker}"\n')
    hook.chmod(0o755)

    # The hook works; prove it before asserting the verifier's git does not run it.
    subprocess.run([str(hook), "old", "new", "1"], check=True)
    assert marker.is_file()
    marker.unlink()

    materialise(fixture.task, destination)

    assert _head(destination) == fixture.task.base_commit
    assert not marker.exists(), (
        "a repo-local post-checkout hook ran during the verifier's checkout; a reused checkout "
        "is an operator-supplied trust surface and its hooks must not execute outside the sandbox"
    )


# --------------------------------------------------------------------------------------
# M5 — the callers, and the committed artifact
# --------------------------------------------------------------------------------------


def test_provision_succeeds_offline_from_the_mirror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = build_task(tmp_path / "fixture", pins=("iniconfig==2.3.0",))
    mirror = _bare_mirror(fixture.origin, tmp_path / "flask-mirror.git")
    task = _retarget(tmp_path / "fixture" / "task.json", _UNREACHABLE)
    monkeypatch.setenv(_MIRRORS, json.dumps({_UNREACHABLE: str(mirror)}))

    seen: list[tuple[str, ...]] = []

    def stub_check_environment(pins: list[str], *, venv: Path, python: str) -> object:
        # Stubbed because the real one installs: the claim under test is the checkout, and the
        # pins were already proven installable offline by test_provisioning_from_pins.
        seen.append(tuple(pins))
        venv.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(interpreter=Path(sys.executable))

    monkeypatch.setattr(scoring, "check_environment", stub_check_environment)

    interpreter = scoring.provision(task, tmp_path / "environment")

    assert interpreter == Path(sys.executable)
    assert seen == [task.environment.pins]
    assert (tmp_path / "environment" / "checkout" / "calc.py").is_file()


def test_verify_strict_succeeds_offline_from_the_mirror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = build_task(tmp_path / "fixture")
    mirror = _bare_mirror(fixture.origin, tmp_path / "flask-mirror.git")
    task = _retarget(tmp_path / "fixture" / "task.json", _UNREACHABLE)
    monkeypatch.setenv(_MIRRORS, json.dumps({_UNREACHABLE: str(mirror)}))
    patch = make_patch(fixture.origin, {"calc.py": CALC_FIXED})

    result = verify_strict(task, patch, sandbox_root=tmp_path / "sandbox", timeout=120.0)

    assert result.status is Status.PASS, result.verdicts


def test_the_committed_public_instance_pins_digest_to_the_prewarmed_directory() -> None:
    """The sheet pre-warms `environments/b885fb84763091db` by literal; this keeps it honest.

    The digest expression is `Interpreters._build`'s (scoring.py): python, then the pins, joined
    by newlines and hashed. If the manifest's pins change, the digest changes, the pre-wave is
    stale, and an offline night would fail to provision — so the drift has to fail here first.
    """
    import hashlib

    root = Path(__file__).resolve().parents[1]
    task = load_task(root / "tasks/public/instances/pallets__flask-4045.json")
    digest = hashlib.sha256(
        "\n".join((task.environment.python, *task.environment.pins)).encode("utf-8")
    ).hexdigest()[:16]

    assert digest == "b885fb84763091db", (
        f"the committed public instance's pins hash to {digest}, not the pre-warmed "
        "b885fb84763091db; the sheet's pre-warm would point at an empty directory"
    )
