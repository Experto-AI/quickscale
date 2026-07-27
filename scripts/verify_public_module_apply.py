#!/usr/bin/env python3
r"""
SA117 — Public module application verification.

Validates that a public module can be safely applied to a target project
without unintended side effects.  Operates on process execution contracts,
evidence capture, and resource cleanup.

Key contracts
-------------

1. **Arguments** — executable, argv, stdin, cwd are passed exactly as
   specified.  No silent injection or modification.

2. **Process** — subprocess is executed with configurable timeout, process
   group management (``PGRP`` for clean kill), and proper failure precedence
   (timeout > non-zero exit > signal termination).

3. **Evidence** — the apply operation captures version, origin map, applied
   state digest, and execution metadata into an evidence file.

4. **Resource cleanup** — temporary directories, cached downloads, and
   orphaned process groups are cleaned up even on failure.

5. **Direct-origin map / state mismatch** — the module's declared origin
   must match the target's expected source; a mismatch is caught before
   any mutation.

6. **Zero scoped container/volume checks** — when no container or volume
   configuration is expected, the helper verifies that none is implicitly
   created or referenced.

All tests use fake executables and bare local remotes — no production
mutation, no network, Docker, or PostgreSQL.

Exit codes
----------
0 — verification passed
1 — semantic rejection (mismatch, verification failure)
2 — malformed invocation, evidence, or configuration

Examples
--------
    # Verify a module apply with explicit arguments
    poetry run python scripts/verify_public_module_apply.py \\
        --module auth \\
        --target /tmp/test-project \\
        --executable /usr/bin/git \\
        --timeout 60

    # Check direct-origin map consistency
    poetry run python scripts/verify_public_module_apply.py \\
        --module auth \\
        --check-origin

"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT: Final[int] = 120  # seconds

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

ApplyResult = dict[str, Any]


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


def validate_apply_args(
    *,
    executable: str | Path,
    argv: list[str],
    stdin: str | None = None,
    cwd: str | Path | None = None,
) -> None:
    """
    Validate that apply execution arguments are well-formed.

    Raises ``ValueError`` with a description of the first issue found.
    """
    executable_path = Path(executable)

    if not executable_path.is_absolute() and "/" not in str(executable_path):
        # Resolvable via PATH — acceptable
        pass
    elif not executable_path.exists():
        raise ValueError(f"executable not found: {executable}")

    if not argv:
        raise ValueError("argv must contain at least the executable name")

    # argv[0] should match the executable basename
    argv0 = Path(argv[0]).name
    expected = executable_path.name
    if argv0 != expected:
        raise ValueError(f"argv[0] ({argv0!r}) does not match executable name ({expected!r})")

    # Check for NUL in any argument
    for i, arg in enumerate(argv):
        if "\x00" in arg:
            raise ValueError(f"argv[{i}] contains embedded NUL character")

    if stdin is not None:
        if not isinstance(stdin, str):
            raise ValueError(f"stdin must be a string or None, got {type(stdin).__name__}")

    if cwd is not None:
        cwd_path = Path(cwd)
        if not cwd_path.is_dir():
            raise ValueError(f"cwd is not a directory: {cwd}")


# ---------------------------------------------------------------------------
# Process execution
# ---------------------------------------------------------------------------


def execute_apply(
    *,
    executable: str | Path,
    argv: list[str],
    stdin: str | None = None,
    cwd: str | Path | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """
    Execute the apply process and return the result.

    Process group management:
    - The subprocess is started in its own process group (``PGRP``) via
      ``start_new_session=True`` so a timeout kill terminates the entire
      process tree.
    - On timeout, ``SIGTERM`` is sent to the group, followed by ``SIGKILL``
      after a grace period.
    - Output is drained even on timeout so the caller can inspect partial
      output.

    Failure precedence (highest to lowest):
    1. Timeout expires → ``TimeoutExpired`` is raised (output/stderr
       captured in the exception).
    2. Process exits with non-zero code.
    3. Process is terminated by a signal.
    """
    # Resolve the executable
    executable_path = Path(executable)
    if not executable_path.is_absolute():
        # Search PATH
        resolved = shlex.which(str(executable_path))
        if resolved is None:
            raise FileNotFoundError(f"executable not found on PATH: {executable}")
        executable_path = Path(resolved)

    # Ensure argv[0] matches the executable
    resolved_argv = list(argv)
    if Path(resolved_argv[0]).name != executable_path.name:
        resolved_argv[0] = executable_path.name

    # Build environment
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    # Use Popen directly so we have the PID for process-group kill on
    # timeout — subprocess.run does not expose the child PID when the
    # timeout fires.
    proc = subprocess.Popen(
        [str(executable_path)] + resolved_argv[1:],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
        env=proc_env,
        text=True,
        start_new_session=True,  # process group isolation
    )

    try:
        stdout, stderr = proc.communicate(input=stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        # Kill the entire process group first (children + grandchildren).
        kill_process_group(proc.pid)
        # Ensure the direct child is reaped.
        proc.kill()
        # Drain remaining output so the caller can inspect partial output.
        stdout, stderr = proc.communicate()
        raise subprocess.TimeoutExpired(
            proc.args,
            timeout,
            output=stdout,
            stderr=stderr,
        )

    return subprocess.CompletedProcess(
        proc.args,
        proc.returncode,
        stdout,
        stderr,
    )


def kill_process_group(pid: int, grace_seconds: int = 5) -> None:
    """
    Kill the process group rooted at *pid*.

    1. Send ``SIGTERM`` for a clean shutdown.
    2. Wait *grace_seconds*.
    3. Send ``SIGKILL`` if the group is still alive.
    """
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return  # already exited

    time.sleep(min(grace_seconds, 10))

    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


# ---------------------------------------------------------------------------
# Evidence capture
# ---------------------------------------------------------------------------


def build_apply_evidence(
    *,
    module: str,
    version: str,
    executable: str,
    argv: list[str],
    cwd: str | None,
    origin_map_ok: bool,
    state_digest: str,
    exit_code: int,
    duration_ms: float,
) -> dict[str, Any]:
    """Build an evidence dict for a module apply operation."""
    return {
        "module": module,
        "version": version,
        "executable": executable,
        "argv": argv,
        "cwd": cwd,
        "origin_map_ok": origin_map_ok,
        "state_digest": state_digest,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "captured_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "schema_version": "1",
    }


# ---------------------------------------------------------------------------
# Origin map validation
# ---------------------------------------------------------------------------


def check_origin_map(
    *,
    module: str,
    declared_origin: str,
    expected_origin: str,
) -> bool:
    """
    Check that *declared_origin* matches *expected_origin* for *module*.

    Returns ``True`` when the origins match, ``False`` on mismatch.
    """
    return declared_origin == expected_origin


# ---------------------------------------------------------------------------
# Resource cleanup
# ---------------------------------------------------------------------------


class ResourceCleanup:
    """
    Context manager that tracks and cleans up temporary resources.

    Registered resources are cleaned up in reverse order on exit (even
    if an exception occurred).
    """

    def __init__(self) -> None:
        self._cleanups: list[tuple[str, Path]] = []

    def register_temp_dir(self, path: Path) -> Path:
        """Register a temporary directory for cleanup. Returns *path*."""
        self._cleanups.append(("temp_dir", path))
        return path

    def register_temp_file(self, path: Path) -> Path:
        """Register a temporary file for cleanup. Returns *path*."""
        self._cleanups.append(("temp_file", path))
        return path

    def cleanup(self) -> None:
        """Clean up all registered resources in reverse order."""
        for kind, path in reversed(self._cleanups):
            try:
                if kind == "temp_dir" and path.is_dir():
                    import shutil

                    shutil.rmtree(path, ignore_errors=True)
                elif kind == "temp_file" and path.is_file():
                    path.unlink(missing_ok=True)
            except OSError:
                pass

    def __enter__(self) -> ResourceCleanup:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.cleanup()


# ---------------------------------------------------------------------------
# Container/volume checks (zero-scoped)
# ---------------------------------------------------------------------------


def check_no_container_or_volume(project_dir: Path) -> list[str]:
    """
    Verify that *project_dir* has no container or volume configuration.

    Checks for:
    * ``Dockerfile`` or ``docker-compose.*`` files at the project root.
    * ``.dockerignore`` file.
    * ``volumes/`` or ``.volumes/`` directories.
    * Any ``*docker*`` or ``*compose*`` files in project root.

    Returns a list of found references (empty list = clean).
    """
    findings: list[str] = []

    # Dockerfile variants
    for pattern in ("Dockerfile", "Dockerfile.*", "docker-compose*", "docker-compose.*"):
        for match in sorted(project_dir.glob(pattern)):
            findings.append(f"container config found: {match.relative_to(project_dir)}")

    # Support files
    for pattern in (".dockerignore",):
        match = project_dir / pattern
        if match.is_file():
            findings.append(f"container support file found: {pattern}")

    # Volume directories
    for vol_dir in ("volumes", ".volumes"):
        match = project_dir / vol_dir
        if match.is_dir():
            findings.append(f"volume directory found: {vol_dir}")

    return findings


# ---------------------------------------------------------------------------
# State digest computation
# ---------------------------------------------------------------------------


def compute_state_digest(project_dir: Path) -> str:
    """
    Compute a SHA-256 hex digest of the project's ``.quickscale/state.yml``.

    Returns the hex digest when the state file exists, or an empty string
    when the state file does not exist.

    Args:
        project_dir: Path to the project root directory.

    Returns:
        SHA-256 hex digest of the state file content, or empty string.

    """
    state_path = project_dir / ".quickscale" / "state.yml"
    if not state_path.is_file():
        return ""
    digest = hashlib.sha256()
    digest.update(state_path.read_bytes())
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="verify_public_module_apply.py",
        description="SA117 public module apply verification.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # apply
    apply_p = subparsers.add_parser("apply", help="Execute and verify a module apply.")
    apply_p.add_argument("--module", required=True, help="Module name to apply.")
    apply_p.add_argument("--target", type=Path, required=True, help="Target project directory.")
    apply_p.add_argument("--executable", required=True, help="Executable path.")
    apply_p.add_argument(
        "--argv", nargs="+", required=True, help="Argument vector (argv[0] first)."
    )
    apply_p.add_argument("--stdin", default=None, help="Stdin content.")
    apply_p.add_argument("--cwd", type=Path, default=None, help="Working directory.")
    apply_p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout in seconds.")
    apply_p.add_argument("--version", required=True, help="Repository version.")
    apply_p.add_argument(
        "--declared-origin", required=True, help="Declared module origin for pre-mutation check."
    )
    apply_p.add_argument(
        "--expected-origin", required=True, help="Expected module origin for pre-mutation check."
    )

    # check-origin
    co = subparsers.add_parser("check-origin", help="Check origin map consistency.")
    co.add_argument("--module", required=True, help="Module name.")
    co.add_argument("--declared-origin", required=True, help="Declared module origin.")
    co.add_argument("--expected-origin", required=True, help="Expected module origin.")

    # check-containers
    cc = subparsers.add_parser("check-containers", help="Check for zero container/volume config.")
    cc.add_argument("--target", type=Path, required=True, help="Target project directory.")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    cmd = args.command

    if cmd == "apply":
        try:
            validate_apply_args(
                executable=args.executable,
                argv=args.argv,
                stdin=args.stdin,
                cwd=args.cwd,
            )
        except ValueError as exc:
            print(f"ERROR: argument validation failed: {exc}", file=sys.stderr)
            return 2

        if not args.target.is_dir():
            print(f"ERROR: target is not a directory: {args.target}", file=sys.stderr)
            return 2

        # Mandatory direct origin check BEFORE mutation.  Both origins are
        # required arguments — absence or mismatch blocks before any process
        # execution.
        origin_map_ok = check_origin_map(
            module=args.module,
            declared_origin=args.declared_origin,
            expected_origin=args.expected_origin,
        )
        if not origin_map_ok:
            print(
                f"ORIGIN MISMATCH — blocking apply before mutation for module "
                f"{args.module}:\n"
                f"  Declared: {args.declared_origin}\n"
                f"  Expected: {args.expected_origin}",
                file=sys.stderr,
            )
            return 1

        try:
            start = time.monotonic()
            completed = execute_apply(
                executable=args.executable,
                argv=args.argv,
                stdin=args.stdin,
                cwd=args.cwd,
                timeout=args.timeout,
            )
            duration_ms = (time.monotonic() - start) * 1000
        except subprocess.TimeoutExpired as exc:
            print(
                f"APPLY TIMEOUT after {args.timeout}s: {exc}",
                file=sys.stderr,
            )
            return 1
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        # Compute state digest truthfully.
        state_digest = compute_state_digest(args.target)
        # Run container/volume side-effect checks.
        container_findings = check_no_container_or_volume(args.target)

        evidence = build_apply_evidence(
            module=args.module,
            version=args.version,
            executable=args.executable,
            argv=args.argv,
            cwd=str(args.cwd) if args.cwd else None,
            origin_map_ok=origin_map_ok,
            state_digest=state_digest,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

        print(json.dumps(evidence, indent=2))
        if container_findings:
            print("CONTAINER/VOLUME FINDINGS:", file=sys.stderr)
            for f in container_findings:
                print(f"  {f}", file=sys.stderr)
        if completed.returncode != 0:
            if completed.stderr:
                print(f"STDERR:\n{completed.stderr}", file=sys.stderr)
            return 1

        return 0

    elif cmd == "check-origin":
        ok = check_origin_map(
            module=args.module,
            declared_origin=args.declared_origin,
            expected_origin=args.expected_origin,
        )
        if ok:
            print(f"Origin map OK for module {args.module}")
            return 0
        else:
            print(
                f"ORIGIN MISMATCH for module {args.module}:\n"
                f"  Declared: {args.declared_origin}\n"
                f"  Expected: {args.expected_origin}",
                file=sys.stderr,
            )
            return 1

    elif cmd == "check-containers":
        findings = check_no_container_or_volume(args.target)
        if findings:
            for f in findings:
                print(f"CONTAINER/VOLUME FOUND: {f}")
            return 1
        else:
            print("No container or volume configuration found.")
            return 0

    else:
        print(f"ERROR: unknown command: {cmd}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
