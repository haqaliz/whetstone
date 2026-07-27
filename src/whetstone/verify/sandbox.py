"""The confinement the reward is measured inside: no network, writes scoped, environment pinned.

The reward is a process exit status, so the process had better not be able to reach anything
that would make that status a lie. This module runs a command under macOS Seatbelt with the
network denied wholesale and writes confined to one subtree, and hands back what happened.

**Everything `sandbox-exec`-specific stops here.** Apple has deprecated the binary; it still
works and Belay depends on it, but the day it goes away must be a day we rewrite one module,
not five call sites. Callers get `run_confined`, a `SandboxResult`, and an exception — never a
profile string to compose or an argv to assemble.

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

import os
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from whetstone.verify.verdict import Status, Verdict

#: The kernel's front door. An absolute path, never resolved through `PATH`: the boundary must
#: not be selectable by the environment of whoever launched the verifier.
SANDBOX_EXEC = "/usr/bin/sandbox-exec"

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


def run_confined(
    command: Sequence[str],
    *,
    scope: Path | str,
    timeout: float,
    cwd: Path | str | None = None,
) -> SandboxResult:
    """Run `command` under Seatbelt, writes confined to `scope`, network denied, env pinned.

    `timeout` has no default on purpose. Belay's `run()` defaults to 30 seconds, which is
    right for a probe and wrong for a test suite; a caller that inherited it would get
    UNVERIFIED on every slow task and would have no idea why. Choosing it is the caller's job.

    The scope directory and the temp directory inside it are created if absent — the child
    cannot write its own workspace into existence from inside the sandbox, and both are inside
    the tree the caller already granted.

    Blocks until the child exits, and unlinks the profile on the way out whatever happens.
    """
    if sys.platform != "darwin":
        raise UnsupportedPlatform(
            f"the Seatbelt sandbox is macOS-only and cannot contain anything on "
            f"{sys.platform!r}. Raising rather than running the command unsandboxed: a no-op "
            f"that returned success would be Whetstone claiming a containment boundary that "
            f"does not exist on this platform."
        )
    if not Path(SANDBOX_EXEC).exists():
        raise UnsupportedPlatform(
            f"{SANDBOX_EXEC} is not present, so nothing can be confined. Raising rather than "
            f"running the command unsandboxed: an unconfined run would produce a reward with "
            f"no boundary behind it."
        )

    scope_path = Path(scope).expanduser().resolve()
    tmpdir = scope_path / _TMPDIR_NAME
    tmpdir.mkdir(parents=True, exist_ok=True)

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
                env=_child_env(scope_path, tmpdir),
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as expired:
            return _timed_out(expired, profile=profile, timeout=timeout)
    finally:
        os.unlink(profile_path)


    if completed.returncode != 0 and completed.stderr.startswith(_SANDBOX_EXEC_FAILURE):
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
    SBPL — a policy injection into the boundary. Belay guards the same thing at
    `sandbox/seatbelt.py:87-95`; our profile being smaller does not make the hole smaller.
    """
    return path.replace("\\", "\\\\").replace('"', '\\"')


def _child_env(scope: Path, tmpdir: Path) -> dict[str, str]:
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
    """
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(scope),
        "TMPDIR": str(tmpdir),
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }


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
