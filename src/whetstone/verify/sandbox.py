"""The confinement the reward is measured inside: no network, writes scoped, environment pinned.

The reward is a process exit status, so the process had better not be able to reach anything
that would make that status a lie. This module runs a command under macOS Seatbelt with the
network denied wholesale and writes confined to one subtree, and hands back what happened.

**Everything `sandbox-exec`-specific stops here.** Apple has deprecated the binary; it still
works and the sibling project depends on it, but the day it goes away must be a day we rewrite one
module, not five call sites. Callers get `run_confined`, a `SandboxResult`, and an exception — never
a profile string to compose or an argv to assemble.

**What this contains, and what it does not.** It contains what the child can *change*: writes
land inside `scope` or they do not land. It does not contain what the child can *see* —
`file-read*` is allowed wholesale, and the spike confirmed a sandboxed process reads outside
its scope freely. Nothing here may be described as read-blindness. That matters downstream:
the operator's golden tests are restored *into* the sandbox before pytest runs, so code under
test can read the assertions it must satisfy. The verifier's guarantee is "the unmodified
operator tests genuinely passed", never "the policy never saw them".

**A run that did not complete is not a run that failed.** `SandboxResult.verdict` is the
sandbox's verdict about *itself* — did the confined command run to completion? — and it is
UNVERIFIED when the answer is no. It is never FAIL: a task the sandbox could not run is one
we could not check, not one the patch got wrong, and collapsing the two would understate the
policy and hide sandbox unreliability from the loop that needs to see it. The verdict is
deliberately shaped to fold through `verdict.reduce`, so a caller that includes it in a task's
sub-checks gets the UNVERIFIED sinking the task with no extra code. Its PASS says only that
the run completed; the exit status is the caller's to interpret.

Stdlib only, and no model: this is a subprocess and a string.
"""

from __future__ import annotations

import functools
import os
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from whetstone.verify.verdict import Status, Verdict

#: The kernel's front door on macOS. An absolute path, never resolved through `PATH`: the
#: boundary must not be selectable by the environment of whoever launched the verifier.
SANDBOX_EXEC = "/usr/bin/sandbox-exec"

#: The kernel's front door on Linux. Absolute for `SANDBOX_EXEC`'s reason, and the two standard
#: locations are tried in order rather than `PATH` being consulted.
BWRAP_PATHS = ("/usr/bin/bwrap", "/usr/local/bin/bwrap")

#: The two mechanisms that can confine, named so a result can say which one did.
SEATBELT = "seatbelt"
BUBBLEWRAP = "bubblewrap"

#: The `kind` on every verdict this module emits, so a reader can tell a sandbox verdict from
#: the pytest verdict it will sit beside.
_VERDICT_KIND = "sandbox-run"

#: Written inside the scope, because a child that cannot write its temp directory cannot run.
#: Pinning it also stops the child inheriting the launcher's `TMPDIR` and leaving artefacts
#: outside the tree the caller granted.
_TMPDIR_NAME = ".whetstone-tmp"

#: The one write the profile permits outside the scope. A sink, not a destination — see
#: `build_profile` for why refusing it costs a working pytest and buys no containment.
_BIT_BUCKET = os.devnull

#: `sandbox-exec` prefixes its own failures — a profile that would not compile, a binary it
#: could not exec. That is not the child's exit status, because there was no child.
_SANDBOX_EXEC_FAILURE = b"sandbox-exec:"

#: bubblewrap's equivalent prefix. Both are needed and neither is optional: this marker is what
#: separates "the task failed" from "the task never ran", which is the UNVERIFIED-vs-FAIL
#: contract at its sharpest. Matching only Seatbelt's prefix meant a command bubblewrap could not
#: start came back `FAIL` — a task recorded as *solved wrongly* when in truth nothing executed.
#: Found by running the containment suite on a real Linux host, where `bwrap: execvp ...` on
#: stderr was being read as a failing task.
_BWRAP_FAILURE = b"bwrap:"

#: Every prefix that means the mechanism itself refused to start the child.
_NEVER_STARTED_MARKERS = (_SANDBOX_EXEC_FAILURE, _BWRAP_FAILURE)


class UnsupportedPlatform(RuntimeError):
    """Raised where Seatbelt cannot contain anything, rather than running the command anyway.

    There is no fallback and there must not be one. A no-op that returned success would be
    Whetstone claiming a containment boundary that does not exist on this platform, and every
    reward computed after it would be a number nobody bounded.
    """


@dataclass(frozen=True)
class SandboxResult:
    """What the confined run did, and the policy it did it under.

    `rc` is the child's exit status, or `None` exactly when there was no exit status to
    report — the run timed out, or `sandbox-exec` never got as far as a child. `profile` is
    the policy *actually applied*, not the one we meant to apply, so an audit reads what the
    kernel read. `verdict` is the sandbox's finding about the run itself; see the module
    docstring for why it is never FAIL.
    """

    rc: int | None
    stdout: bytes
    stderr: bytes
    profile: str
    verdict: Verdict


def build_profile(scope: Path | str) -> str:
    """The SBPL policy: allow by default, then deny the network and every write but one tree.

    `(allow default)` first is deliberate. An allow-list profile would have to enumerate every
    syscall a Python interpreter makes to start, and a profile that must be extended whenever
    a task needs something is a profile that gets extended until it denies nothing. The two
    things the reward depends on — that the child could not reach the network, and could not
    write outside its workspace — are denied explicitly and are the only claims made.

    The scope is resolved before interpolation: macOS hands out symlinked temp paths
    (`/tmp` -> `/private/tmp`), and Seatbelt matches the resolved path, so an unresolved
    `subpath` grants nothing while looking like it grants everything.

    `/dev/null` is granted as a `literal`, and it is not an erosion of the boundary: the
    boundary is about what the child can *change*, and a write to the bit bucket changes
    nothing anywhere. Denying it is not free — pytest's logging plugin opens `/dev/null` as
    its default log file while configuring, so without this every confined pytest run dies
    with an INTERNALERROR before collecting a test. `literal` rather than `subpath` so this
    grants that one path and not `/dev`.
    """
    resolved = Path(scope).expanduser().resolve()
    return (
        "(version 1)\n"
        "(allow default)\n"
        "(deny network*)\n"
        "(deny file-write*)\n"
        f'(allow file-write* (subpath "{_quote(str(resolved))}"))\n'
        f'(allow file-write* (literal "{_quote(_BIT_BUCKET)}"))\n'
    )


def bubblewrap_binary() -> str | None:
    """The `bwrap` this host would use, or `None`. Absolute paths only, never `PATH`."""
    for candidate in BWRAP_PATHS:
        if Path(candidate).exists():
            return candidate
    return None


def build_bubblewrap_argv(binary: str, scope: Path | str) -> list[str]:
    """The Linux confinement spec: no network, everything read-only but the scope, no host /tmp.

    The counterpart of `build_profile`, and it enforces the same three properties by different
    means — namespaces rather than a policy language:

    - `--unshare-all` drops the network namespace along with the rest, so the child has no route
      off the machine. This is the property the reward depends on: a task that can reach the
      network can fetch a patch, or a test result, from somewhere the operator never granted.
    - `--ro-bind / /` mounts the whole filesystem **read-only**, then `--bind <scope> <scope>`
      punches exactly one writable hole. That is the inverse of Seatbelt's `(deny file-write*)`
      plus one allow, and lands in the same place: writes land inside `scope` or they do not
      land.
    - **There is deliberately no `--tmpfs /tmp`.** An earlier version mounted one, reasoning that
      a private empty `/tmp` keeps the child's temp writes off the host. It does — but it also
      hands the child a *writable* `/tmp`, and the property this sandbox owes the reward is not
      "the host is unharmed", it is **writes land inside the scope or they do not land**. With a
      tmpfs there, a write outside the scope succeeds and the child can read it back, which is a
      thing macOS refuses outright. Measured on a real Linux host: the containment suite's
      `OUTSIDE DENIED` assertion failed and reported `OUTSIDE WROTE`. `_child_env` already points
      `TMPDIR` inside the scope, so nothing needed the writable `/tmp` in the first place.
    - `--die-with-parent` means an abandoned child cannot outlive the verifier that launched it.

    Like the SBPL profile, this is returned rather than executed, so a caller auditing a run can
    read exactly what the kernel was asked for.
    """
    resolved = Path(scope).expanduser().resolve()
    return [
        binary,
        "--unshare-all",
        "--die-with-parent",
        "--ro-bind", "/", "/",
        "--dev", "/dev",
        "--proc", "/proc",
        "--bind", str(resolved), str(resolved),
    ]


@functools.cache
def confinement() -> str:
    """Which mechanism confines on this host — **probed**, never inferred from a filename.

    Presence is not capability, and Linux is where that bites. Ubuntu 24.04 ships `bwrap` and
    sets `kernel.apparmor_restrict_unprivileged_userns=1`, which stops an unprivileged user
    creating the namespaces `bwrap` needs: the binary is on disk, executable, and confines
    nothing. A check that stopped at `which bwrap` would hand back a sandbox that silently
    fails open, which is the one outcome this module exists to prevent — the reward is only
    worth anything if the boundary behind it is real.

    So the probe **runs the thing**: it asks the mechanism to confine `true` and requires
    success. Cheap (milliseconds) and cached, because a host's confinement does not change
    under a running night, and paying for it per rollout would be paying for an answer that
    cannot have changed.
    """
    if sys.platform == "darwin":
        if not Path(SANDBOX_EXEC).exists():
            raise UnsupportedPlatform(
                f"{SANDBOX_EXEC} is not present, so nothing can be confined. Raising rather "
                "than running the command unsandboxed: an unconfined run would produce a "
                "reward with no boundary behind it."
            )
        return SEATBELT

    if sys.platform.startswith("linux"):
        binary = bubblewrap_binary()
        if binary is None:
            raise UnsupportedPlatform(
                "no `bwrap` at " + " or ".join(BWRAP_PATHS) + ", so nothing can be confined on "
                "this host. Install bubblewrap (`apt install bubblewrap`). Raising rather than "
                "running the command unsandboxed: an unconfined run would produce a reward with "
                "no boundary behind it."
            )
        probe = subprocess.run(
            [*build_bubblewrap_argv(binary, Path(tempfile.gettempdir())), "/bin/true"],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if probe.returncode != 0:
            raise UnsupportedPlatform(
                f"{binary} is installed and cannot confine anything here: it exited "
                f"{probe.returncode} with {probe.stderr.decode(errors='replace').strip()!r}. On "
                "Ubuntu 24.04 and later this is usually "
                "`kernel.apparmor_restrict_unprivileged_userns=1`, which stops an unprivileged "
                "user creating the namespaces bwrap needs; an administrator can set it to 0, "
                "install an AppArmor profile for bwrap, or make bwrap setuid. Raising rather "
                "than running the command unsandboxed: a sandbox that fails open is worse than "
                "none, because the reward would look verified."
            )
        return BUBBLEWRAP

    raise UnsupportedPlatform(
        f"no confinement mechanism is known for {sys.platform!r}. Raising rather than running "
        "the command unsandboxed: a no-op that returned success would be Whetstone claiming a "
        "containment boundary that does not exist on this platform."
    )


def run_confined(
    command: Sequence[str],
    *,
    scope: Path | str,
    timeout: float,
    cwd: Path | str | None = None,
    python_path: Sequence[str] | None = None,
) -> SandboxResult:
    """Run `command` under Seatbelt, writes confined to `scope`, network denied, env pinned.

    `timeout` has no default on purpose. The sibling project's `run()` defaults to 30 seconds, which
    is right for a probe and wrong for a test suite; a caller that inherited it would get UNVERIFIED
    on every slow task and would have no idea why. Choosing it is the caller's job.

    `python_path` becomes the child's `PYTHONPATH`, and it is a **parameter rather than an
    inheritance** — see `_child_env`, which builds the environment from scratch and would
    otherwise have no way to say this. Absent or empty means the variable is not set at all,
    which is distinct from setting it to `""`: an empty `PYTHONPATH` puts the current directory
    on the import path, which is a claim about the code under test that no caller made.

    The scope directory and the temp directory inside it are created if absent — the child
    cannot write its own workspace into existence from inside the sandbox, and both are inside
    the tree the caller already granted.

    Blocks until the child exits, and unlinks the profile on the way out whatever happens.
    """
    # Probed, not inferred. `confinement` raises `UnsupportedPlatform` when this host cannot
    # confine — including the case where the mechanism is installed and cannot create the
    # namespaces it needs, which is Ubuntu 24.04 out of the box.
    mechanism = confinement()

    scope_path = Path(scope).expanduser().resolve()
    tmpdir = scope_path / _TMPDIR_NAME
    tmpdir.mkdir(parents=True, exist_ok=True)
    env = _child_env(scope_path, tmpdir, python_path)

    if mechanism == BUBBLEWRAP:
        binary = bubblewrap_binary()
        assert binary is not None  # `confinement` already proved it runs
        argv = build_bubblewrap_argv(binary, scope_path)
        profile = " ".join(argv)
        try:
            completed = subprocess.run(
                [*argv, *command],
                capture_output=True,
                cwd=str(cwd) if cwd is not None else None,
                env=env,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as expired:
            return _timed_out(expired, profile=profile, timeout=timeout)
    else:
        profile = build_profile(scope_path)
        handle, profile_path = tempfile.mkstemp(prefix="whetstone-sandbox-", suffix=".sb")
        try:
            with os.fdopen(handle, "w") as fh:
                fh.write(profile)
            try:
                completed = subprocess.run(
                    [SANDBOX_EXEC, "-f", profile_path, *command],
                    capture_output=True,
                    cwd=str(cwd) if cwd is not None else None,
                    env=env,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as expired:
                return _timed_out(expired, profile=profile, timeout=timeout)
        finally:
            os.unlink(profile_path)


    if completed.returncode != 0 and completed.stderr.startswith(_NEVER_STARTED_MARKERS):
        return _never_started(completed, profile=profile)

    return SandboxResult(
        rc=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        profile=profile,
        verdict=Verdict(
            kind=_VERDICT_KIND,
            status=Status.PASS,
            observed=completed.returncode,
            expected=None,
            message=(
                f"the confined run completed with exit status {completed.returncode}; "
                f"the exit status is the caller's to interpret"
            ),
        ),
    )


def _quote(path: str) -> str:
    """Escape a path for an SBPL string literal. The backslash first, or it escapes itself.

    The scope is data being pasted into the policy language that enforces the policy. An
    unescaped `"` would close the literal early and let the remainder of the path parse as
    SBPL — a policy injection into the boundary. The sibling project guards the same thing at
    `sandbox/seatbelt.py:87-95`; our profile being smaller does not make the hole smaller.
    """
    return path.replace("\\", "\\\\").replace('"', '\\"')


def _child_env(scope: Path, tmpdir: Path, python_path: Sequence[str] | None) -> dict[str, str]:
    """The child's entire environment, built rather than inherited.

    Inheriting `os.environ` would make a verified result depend on the shell that launched the
    verifier — a stray `PYTHONHASHSEED`, a `PYTEST_ADDOPTS`, an installed plugin autoloading
    into collection. Each name below is here for a reason:

    - `PATH` is the one value carried over. The child must be able to exec the operator's
      toolchain, and hardcoding `os.defpath` would silently pick a different `git`.
    - `HOME` points inside the scope, so ambient dotfiles are neither read nor written and
      anything that insists on a home directory gets a writable one.
    - `TMPDIR` points inside the scope for the same reason, and because a temp directory
      outside it would be denied by the profile mid-run.
    - `PYTHONHASHSEED=0` and `PYTHONDONTWRITEBYTECODE=1` pin hash ordering and keep `.pyc`
      files out of the checkout being verified.
    - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` stops an installed plugin reordering or deselecting
      collection — the same class of hole as the `addopts` cheat, arriving through the
      environment instead of through a config file.

    **`PYTHONPATH` is passed in, and is never read from `os.environ`.** Everything above is
    about what the launching shell may not decide; this is the one variable a *caller* has to
    decide, and the reason is what it does to import resolution: `PYTHONPATH` is searched
    **before** `site-packages`, so a run's own checkout placed on it shadows any copy of the
    project that happens to be installed in the interpreter. That shadowing is what makes the
    verdict a statement about **this** checkout rather than about whatever the venv was
    provisioned from — see `verify/task.py`'s module docstring for the run that PASSED with no
    patch applied because it did not hold. Inheriting the variable would hand that decision back
    to the shell, which is the failure the rest of this function exists to prevent.
    """
    child = {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(scope),
        "TMPDIR": str(tmpdir),
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    if python_path:
        child["PYTHONPATH"] = os.pathsep.join(python_path)
    return child


def _timed_out(
    expired: subprocess.TimeoutExpired, *, profile: str, timeout: float
) -> SandboxResult:
    """UNVERIFIED, never FAIL — see the module docstring. `rc` is None: there was no exit."""
    return SandboxResult(
        rc=None,
        stdout=_as_bytes(expired.stdout),
        stderr=_as_bytes(expired.stderr),
        profile=profile,
        verdict=Verdict(
            kind=_VERDICT_KIND,
            status=Status.UNVERIFIED,
            observed=None,
            expected=None,
            message=(
                f"the confined run did not finish within {timeout}s and was killed; a task "
                f"the sandbox could not run is one we could not check, not one the patch got "
                f"wrong"
            ),
        ),
    )


def _never_started(completed: subprocess.CompletedProcess[bytes], *, profile: str) -> SandboxResult:
    """`sandbox-exec` failed before there was a child, so its exit status is not the task's.

    Reported UNVERIFIED for the same reason a timeout is: a profile that would not compile or
    a command that could not be exec'd tells us nothing about the patch. Left as FAIL it would
    read downstream as "the tests did not pass", which is a reward decided by a broken harness.
    """
    return SandboxResult(
        rc=None,
        stdout=completed.stdout,
        stderr=completed.stderr,
        profile=profile,
        verdict=Verdict(
            kind=_VERDICT_KIND,
            status=Status.UNVERIFIED,
            observed=completed.stderr.decode(errors="replace").strip(),
            expected=None,
            message=(
                "sandbox-exec did not start the command, so there is no exit status to read "
                "and nothing was checked"
            ),
        ),
    )


def _as_bytes(stream: bytes | str | None) -> bytes:
    """`TimeoutExpired` carries whatever was captured before the kill, or nothing at all."""
    if stream is None:
        return b""
    return stream if isinstance(stream, bytes) else stream.encode()


__all__ = ["SandboxResult", "UnsupportedPlatform", "build_profile", "run_confined"]
