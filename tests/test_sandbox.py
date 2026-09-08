"""Pins the containment the reward is measured inside: no network, writes confined, env fixed.

The failure this prevents: a sandbox that *looks* applied and contains nothing. Three shapes
of that lie, each with a test below.

1. **The probe fails for an unrelated reason.** A connection refused on an offline machine
   looks exactly like a connection refused by the kernel, and a suite that asserts only "the
   probe failed" reports a working boundary on a machine where the sandbox did nothing.
   ``test_the_unsandboxed_control_reaches_the_network_that_the_sandbox_denies`` is the
   control, and it is the most load-bearing test in this file: it runs the SAME probe with no
   profile applied and requires it to genuinely connect. If it cannot, both network tests
   SKIP with a named reason — never pass. A skip says "undetermined here"; a pass would say
   "the sandbox held", and only one of those is honest on an offline machine.

2. **The policy is injected through its own scope path.** The scope is data pasted into the
   language that enforces the policy, so ``test_a_scope_path_containing_a_quote_is_escaped``
   reads the generated profile directly rather than inferring escaping from behaviour.

3. **A run that never happened is scored.** A timeout is not a wrong answer; it is an absent
   one, so it must reduce to UNVERIFIED and never to FAIL.

This file runs the real ``sandbox-exec``. It is the one place in the suite that touches the
network, and it does so exactly once, unsandboxed, in the control described above — the
sandboxed probe's *refusal* is what the other test asserts.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from whetstone.verify.sandbox import (
    BUBBLEWRAP,
    SandboxResult,
    UnsupportedPlatform,
    bubblewrap_binary,
    build_bubblewrap_argv,
    build_profile,
    confinement,
    run_confined,
)
from whetstone.verify.verdict import Status

#: A well-known resolver that answers on TCP/53. The target is deliberately an address rather
#: than a hostname: a hostname would make the probe's failure ambiguous between "the sandbox
#: denied the socket" and "DNS did not resolve".
_NETWORK_TARGET = ("1.1.1.1", 53)

#: Attempts one outbound TCP connection and prints a single word saying what happened.
#: PermissionError is checked before OSError because it is a subclass — the whole point is to
#: tell a kernel refusal (DENIED) apart from an ordinary network failure (UNREACHABLE).
_NETWORK_PROBE = f"""
import socket
try:
    sock = socket.create_connection({_NETWORK_TARGET!r}, timeout=5)
except PermissionError as exc:
    print("DENIED", exc)
except OSError as exc:
    print("UNREACHABLE", type(exc).__name__, exc)
else:
    sock.close()
    print("CONNECTED")
"""

_WRITE_PROBE = """
import sys
for label, path in (("INSIDE", sys.argv[1]), ("OUTSIDE", sys.argv[2])):
    try:
        with open(path, "w") as handle:
            handle.write("written")
    except PermissionError as exc:
        print(label, "DENIED", exc)
    except OSError as exc:
        print(label, "FAILED", type(exc).__name__, exc)
    else:
        print(label, "WROTE")
"""

_ENV_PROBE = """
import os
import tempfile
print("PYTHONHASHSEED", os.environ.get("PYTHONHASHSEED"))
print("PYTHONDONTWRITEBYTECODE", os.environ.get("PYTHONDONTWRITEBYTECODE"))
print("PYTEST_DISABLE_PLUGIN_AUTOLOAD", os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD"))
print("TMPDIR", os.environ.get("TMPDIR"))
print("GETTEMPDIR", tempfile.gettempdir())
"""

def _confines() -> bool:
    """Can this host confine anything at all? Probed, so the answer is the truth about the host."""
    try:
        confinement()
    except UnsupportedPlatform:
        return False
    return True


#: Skipped only where nothing can confine — not "unless macOS". Every property below is a
#: property of `run_confined`, which is mechanism-agnostic: Seatbelt on Darwin, bubblewrap on
#: Linux. Gating on the platform name instead would mean the network denial, the write
#: confinement and the pinned environment were asserted on exactly one operating system while
#: the other shipped them unproven — and the sandbox is the reward's boundary, so "unproven"
#: there is the whole product unproven.
pytestmark = pytest.mark.skipif(
    not _confines(),
    reason=(
        "no confinement mechanism works on this host, so there is nothing to contain anything "
        "with. On Linux this is usually bubblewrap missing, or "
        "`kernel.apparmor_restrict_unprivileged_userns=1` stopping it creating namespaces"
    ),
)


@dataclass(frozen=True)
class Probe:
    """What the network probe reported, and the raw output it reported it in."""

    outcome: str
    stdout: str


def _probe_outcome(stdout: bytes) -> str:
    """The first word the probe printed — DENIED, UNREACHABLE, or CONNECTED."""
    text = stdout.decode(errors="replace").strip()
    return text.split(" ", 1)[0] if text else "NO-OUTPUT"


@pytest.fixture(scope="session")
def unsandboxed_probe() -> Probe:
    """The control: the same probe with NO profile applied, run once for the session.

    This is the only outbound connection the suite attempts. Its job is to establish that a
    network exists to be denied, so that the sandboxed probe's refusal means the sandbox and
    not the machine.
    """
    completed = subprocess.run(
        [sys.executable, "-c", _NETWORK_PROBE],
        capture_output=True,
        timeout=30,
        check=False,
    )
    stdout = completed.stdout.decode(errors="replace")
    return Probe(outcome=_probe_outcome(completed.stdout), stdout=stdout)


@pytest.fixture
def reachable_network(unsandboxed_probe: Probe) -> Probe:
    """Skips — never passes — when the control could not reach the network.

    Without a reachable network, a denial proves nothing: an absent route and a kernel
    refusal are indistinguishable from the probe's side. The honest outcome is "undetermined
    on this machine", and pytest spells that skip.
    """
    if unsandboxed_probe.outcome != "CONNECTED":
        pytest.skip(
            f"the unsandboxed control could not reach {_NETWORK_TARGET[0]}:{_NETWORK_TARGET[1]} "
            f"(it reported {unsandboxed_probe.stdout.strip()!r}), so a sandboxed denial would "
            "be indistinguishable from an absent network"
        )
    return unsandboxed_probe


def test_the_sandbox_denies_the_network_to_the_child(
    tmp_path: Path, reachable_network: Probe
) -> None:
    """The probe's *refusal* is the assertion; the test itself opens no socket."""
    result = run_confined(
        [sys.executable, "-c", _NETWORK_PROBE],
        scope=tmp_path,
        timeout=60,
    )
    # Both refusal shapes count, and the difference is the mechanism rather than the strength.
    # Seatbelt denies the syscall on an interface that exists, so the probe sees `PermissionError`
    # and prints DENIED. bwrap's `--unshare-all` puts the child in an empty network namespace, so
    # there is no interface to deny on and the probe sees `ENETUNREACH` and prints UNREACHABLE —
    # if anything the stronger confinement, since nothing is reachable to be refused. What must
    # never appear is CONNECTED, and the control test beside this one proves the network was
    # there to be reached. Pinning the errno vocabulary of one kernel would have made the other
    # platform's containment look like a failure while it was in fact working.
    assert _probe_outcome(result.stdout) in {"DENIED", "UNREACHABLE"}, (
        f"expected the kernel to refuse the connection, got "
        f"{result.stdout.decode(errors='replace')!r}"
    )


def test_the_unsandboxed_control_reaches_the_network_that_the_sandbox_denies(
    tmp_path: Path, reachable_network: Probe
) -> None:
    """Anti-vacuity control — the difference between testing the sandbox and testing the wire.

    The same probe, run twice, differing only in whether the profile was applied. Without
    this, a probe that failed for an unrelated reason would make the sandbox look effective
    while it did nothing at all.
    """
    sandboxed = run_confined(
        [sys.executable, "-c", _NETWORK_PROBE],
        scope=tmp_path,
        timeout=60,
    )
    assert reachable_network.outcome == "CONNECTED"
    assert _probe_outcome(sandboxed.stdout) != reachable_network.outcome, (
        "the sandboxed and unsandboxed probes behaved identically, so this suite is measuring "
        "the network's absence rather than the sandbox"
    )


def test_writes_land_inside_the_scope_and_are_refused_outside_it(tmp_path: Path) -> None:
    """Both halves: the second alone would pass under a profile that denied every write."""
    scope = tmp_path / "scope"
    scope.mkdir()
    outside = tmp_path / "outside.txt"

    result = run_confined(
        [sys.executable, "-c", _WRITE_PROBE, str(scope / "inside.txt"), str(outside)],
        scope=scope,
        timeout=60,
    )

    stdout = result.stdout.decode(errors="replace")
    assert "INSIDE WROTE" in stdout, stdout
    # `DENIED` is Seatbelt's `PermissionError`; `FAILED` covers the read-only-filesystem
    # refusal bubblewrap produces from `--ro-bind / /`. The property is that the write
    # did not land, not which errno said so — `OUTSIDE WROTE` must never appear.
    assert ("OUTSIDE DENIED" in stdout) or ("OUTSIDE FAILED" in stdout), stdout
    assert (scope / "inside.txt").exists()
    assert not outside.exists()


def test_the_bit_bucket_is_writable_while_real_writes_stay_confined(tmp_path: Path) -> None:
    """``/dev/null`` is a sink, not a place data can land, so denying it contains nothing.

    Denying it does break things: pytest's logging plugin opens ``/dev/null`` as its default
    log file during ``pytest_configure``, so under a profile without this exception *every*
    confined pytest run dies with an INTERNALERROR before collecting a single test — which is
    how this was found. The exception is a literal, not a subpath: it grants exactly the one
    path whose semantics are "discard", and the second half of this test is what keeps it from
    quietly becoming a general write permission.
    """
    outside = tmp_path / "outside.txt"
    probe = f"""
import sys
with open("/dev/null", "w") as handle:
    handle.write("discarded")
print("DEVNULL WROTE")
try:
    with open({str(outside)!r}, "w") as handle:
        handle.write("landed")
except PermissionError:
    print("OUTSIDE DENIED")
except OSError as exc:
    # Seatbelt denies the write (`PermissionError`); bubblewrap's read-only bind refuses it
    # with `EROFS`, which is an `OSError` and not a `PermissionError`. Catching only the
    # narrower type let the probe die on its own traceback and report nothing at all.
    print("OUTSIDE FAILED", type(exc).__name__, exc)
else:
    print("OUTSIDE WROTE")
"""
    scope = tmp_path / "scope"
    scope.mkdir()

    result = run_confined([sys.executable, "-c", probe], scope=scope, timeout=60)

    stdout = result.stdout.decode(errors="replace")
    assert "DEVNULL WROTE" in stdout, stdout
    # `DENIED` is Seatbelt's `PermissionError`; `FAILED` covers the read-only-filesystem
    # refusal bubblewrap produces from `--ro-bind / /`. The property is that the write
    # did not land, not which errno said so — `OUTSIDE WROTE` must never appear.
    assert ("OUTSIDE DENIED" in stdout) or ("OUTSIDE FAILED" in stdout), stdout
    assert not outside.exists()


def test_a_scope_path_containing_a_quote_is_escaped_not_injected(tmp_path: Path) -> None:
    """The scope is data pasted into the policy language that enforces the policy.

    An unescaped ``"`` closes the literal early and lets the remainder of the path parse as
    SBPL — a policy injection into the boundary. Asserted on the generated profile rather
    than through behaviour, because the behavioural symptom of a successful injection is a
    profile that still applies cleanly.
    """
    scope = tmp_path / 'we"ird\\name'
    profile = build_profile(scope)

    # Read the one line that interpolates the scope. Splitting the whole profile on the last
    # `")` would swallow every rule after it — as it did the moment a second quoted rule was
    # added — and would then be asserting about a string no single directive contains.
    (scope_rule,) = [line for line in profile.splitlines() if "(subpath " in line]
    subpath = scope_rule.split('(subpath "', 1)[1].rsplit('")', 1)[0]
    assert '\\"' in subpath, profile
    assert '\\\\' in subpath, profile
    # No bare quote survives: every `"` inside the literal is preceded by a backslash.
    assert '"' not in subpath.replace('\\"', ""), profile
    assert "(deny network*)" in profile
    assert "(deny file-write*)" in profile


def test_a_run_that_times_out_is_unverified_and_never_fail(tmp_path: Path) -> None:
    """A task the sandbox could not run is one we could not check, not one the patch got wrong."""
    result = run_confined(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        scope=tmp_path,
        timeout=0.5,
    )
    assert result.rc is None
    assert result.verdict.status is Status.UNVERIFIED
    assert result.verdict.status is not Status.FAIL


def test_a_completed_run_reports_its_exit_status_and_leaves_the_verdict_to_the_caller(
    tmp_path: Path,
) -> None:
    """Anti-vacuity for the timeout test: a run that completes is NOT reported UNVERIFIED."""
    result = run_confined([sys.executable, "-c", "raise SystemExit(7)"], scope=tmp_path, timeout=60)
    assert result.rc == 7
    assert result.verdict.status is Status.PASS, (
        "the sandbox verdict is about whether the confined run completed, not about whether "
        "the task passed — the exit status is the caller's to interpret"
    )


def test_a_command_sandbox_exec_never_started_is_unverified_and_never_fail(tmp_path: Path) -> None:
    """``sandbox-exec``'s own failure is not the task's exit status — there was no child.

    Left to fall through as a non-zero return code this reads downstream as "the tests did
    not pass", which is a reward decided by a broken harness rather than by the patch.
    """
    result = run_confined([str(tmp_path / "no-such-binary")], scope=tmp_path, timeout=60)

    assert result.rc is None
    assert result.verdict.status is Status.UNVERIFIED
    assert b"execvp" in result.stderr


def test_the_child_observes_the_pinned_deterministic_environment(tmp_path: Path) -> None:
    """A stray ``PYTHONHASHSEED`` or an ambient ``TMPDIR`` is a reproducibility hole."""
    result = run_confined([sys.executable, "-c", _ENV_PROBE], scope=tmp_path, timeout=60)

    stdout = result.stdout.decode(errors="replace")
    assert "PYTHONHASHSEED 0" in stdout, stdout
    assert "PYTHONDONTWRITEBYTECODE 1" in stdout, stdout
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD 1" in stdout, stdout

    reported = dict(line.split(" ", 1) for line in stdout.splitlines() if " " in line)
    scope = str(tmp_path.resolve())
    assert reported["TMPDIR"].startswith(scope), stdout
    assert reported["GETTEMPDIR"].startswith(scope), stdout


def test_the_pinned_environment_is_explicit_and_does_not_inherit_the_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity for the env test: the values are handed over, not inherited by luck.

    Watched failing against an implementation that passed ``env=None``; the parent's
    ``WHETSTONE_AMBIENT`` reached the child and the assertion caught it.
    """
    monkeypatch.setenv("WHETSTONE_AMBIENT", "leaked")
    monkeypatch.setenv("PYTHONHASHSEED", "12345")

    result = run_confined(
        [sys.executable, "-c", 'import os; print("AMBIENT", os.environ.get("WHETSTONE_AMBIENT"))'],
        scope=tmp_path,
        timeout=60,
    )
    assert "AMBIENT None" in result.stdout.decode(errors="replace")


def _reported_python_path(result: SandboxResult) -> str:
    """What the child said its ``PYTHONPATH`` was, as a bare string."""
    return result.stdout.decode(errors="replace").partition("PYTHONPATH ")[2].strip()


def test_the_caller_can_put_directories_on_the_childs_import_path(tmp_path: Path) -> None:
    """The one seam through which a caller may add to the child's environment, and why it exists.

    ``PYTHONPATH`` is searched **before** ``site-packages``, so a directory placed on it shadows
    anything installed in the interpreter. STRICT uses that to put the run's own checkout ahead
    of any residual copy of the project under test — which is what makes a verdict a statement
    about *that* checkout. Asserted on both entries and their order, because the order is the
    order the interpreter searches and a caller that listed two roots meant the first one.
    """
    result = run_confined(
        [sys.executable, "-c", 'import os; print("PYTHONPATH", os.environ.get("PYTHONPATH"))'],
        scope=tmp_path,
        timeout=60,
        python_path=(str(tmp_path / "src"), str(tmp_path / "vendor")),
    )

    assert _reported_python_path(result) == f"{tmp_path / 'src'}{os.pathsep}{tmp_path / 'vendor'}"


def test_the_import_path_is_never_inherited_from_the_launching_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The seam is explicit in **both** directions: a caller may add, the shell may not.

    An inherited ``PYTHONPATH`` would be the whole reason ``_child_env`` builds from scratch,
    undone for the one variable that decides which code the reward imports — the shell that
    launched the verifier could point the run at any tree on the machine, and the verdict would
    be about that one.

    Unset in the child rather than empty, which is a distinction with teeth: ``PYTHONPATH=""``
    puts the current directory on the import path, so an implementation that always set the
    variable would be making a claim about the code under test that no caller made.
    """
    monkeypatch.setenv("PYTHONPATH", "/somewhere/else")

    result = run_confined(
        [sys.executable, "-c", 'import os; print("PYTHONPATH", os.environ.get("PYTHONPATH"))'],
        scope=tmp_path,
        timeout=60,
    )

    assert _reported_python_path(result) == "None", (
        "the launching shell's PYTHONPATH reached the child, so which code a reward run imports "
        "is decided by whoever started the verifier"
    )


def test_a_platform_with_no_mechanism_raises_rather_than_running_unsandboxed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never silently unsandboxed: a no-op returning success would claim a boundary we lack.

    This used to read "a non-darwin platform", and that is no longer the property — Linux
    confines through bubblewrap. What survives, and is the thing actually worth asserting, is
    that a host with *no* mechanism refuses rather than running the command bare.

    The cache is cleared around the monkeypatch because `confinement` memoises: a host's
    confinement does not change under a running night, so paying for the probe per rollout
    would be paying for an answer that cannot have moved. That makes it invisible to a
    monkeypatched platform unless the cache is dropped, which is exactly what a caller
    changing platforms mid-process would need — and no caller does.
    """
    confinement.cache_clear()
    monkeypatch.setattr(sys, "platform", "plan9")
    try:
        with pytest.raises(UnsupportedPlatform, match="plan9"):
            run_confined([sys.executable, "-c", ""], scope=tmp_path, timeout=60)
    finally:
        confinement.cache_clear()


def test_the_mechanism_is_probed_rather_than_inferred_from_a_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Presence is not capability, and on Linux that distinction is the whole ballgame.

    Ubuntu 24.04 ships `bwrap` and sets `kernel.apparmor_restrict_unprivileged_userns=1`, which
    stops an unprivileged user creating the namespaces it needs. The binary is on disk,
    executable, and confines nothing — measured on a real 24.04 host, where `bwrap` exits with
    `setting up uid map: Permission denied`. A check that stopped at "the file exists" would
    hand back a sandbox that fails **open**, and a reward with no boundary behind it still looks
    verified, which is the one outcome this module exists to prevent.

    So the probe runs the mechanism and requires success. Simulated here by a `bwrap` that
    exists and always fails, because the real failure needs a host configured to produce it.
    """
    import subprocess as sp

    from whetstone.verify import sandbox as module

    broken = tmp_path / "bwrap"
    broken.write_text("#!/bin/sh\nexit 1\n")
    broken.chmod(0o755)

    confinement.cache_clear()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(module, "BWRAP_PATHS", (str(broken),))
    original = sp.run

    def failing(argv: object, **kwargs: object) -> object:
        return sp.CompletedProcess(argv, 1, b"", b"setting up uid map: Permission denied")

    monkeypatch.setattr(module.subprocess, "run", failing)
    try:
        with pytest.raises(UnsupportedPlatform, match="apparmor_restrict_unprivileged_userns"):
            module.confinement()
    finally:
        monkeypatch.setattr(module.subprocess, "run", original)
        confinement.cache_clear()


def test_the_result_carries_the_profile_that_was_actually_applied(tmp_path: Path) -> None:
    """Not the one we meant to apply — a caller auditing a run reads what the kernel got."""
    result = run_confined([sys.executable, "-c", ""], scope=tmp_path, timeout=60)
    assert isinstance(result, SandboxResult)

    # The spec of whichever mechanism actually ran — an SBPL policy under Seatbelt, the argv
    # under bubblewrap. Pinning the SBPL text would assert that the *macOS* profile was applied
    # on a host where it never could be, and the property here is "what the result reports is
    # what the kernel got", not "the kernel is Apple's".
    if confinement() == BUBBLEWRAP:
        binary = bubblewrap_binary()
        assert binary is not None
        assert result.profile == " ".join(build_bubblewrap_argv(binary, tmp_path))
    else:
        assert result.profile == build_profile(tmp_path)
