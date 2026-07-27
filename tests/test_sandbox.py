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

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from whetstone.verify.sandbox import (
    SandboxResult,
    UnsupportedPlatform,
    build_profile,
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

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="the Seatbelt sandbox is macOS-only; there is nothing to contain anything with here",
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
    assert _probe_outcome(result.stdout) == "DENIED", (
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
    assert "OUTSIDE DENIED" in stdout, stdout
    assert (scope / "inside.txt").exists()
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

    subpath = profile.split('(subpath "', 1)[1].rsplit('")', 1)[0]
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


def test_a_non_darwin_platform_raises_rather_than_running_unsandboxed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never silently unsandboxed: a no-op returning success would claim a boundary we lack."""
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(UnsupportedPlatform):
        run_confined([sys.executable, "-c", ""], scope=tmp_path, timeout=60)


def test_the_result_carries_the_profile_that_was_actually_applied(tmp_path: Path) -> None:
    """Not the one we meant to apply — a caller auditing a run reads what the kernel got."""
    result = run_confined([sys.executable, "-c", ""], scope=tmp_path, timeout=60)
    assert isinstance(result, SandboxResult)
    assert result.profile == build_profile(tmp_path)
