"""Railway CLI installation, authentication, and command execution.

Implementation detail of :mod:`quickscale_cli.utils.railway_utils`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import quickscale_cli.utils.railway_utils as _railway_utils


def is_npm_installed() -> bool:
    """Check if npm is installed."""
    try:
        subprocess.run(
            ["npm", "--version"],  # noqa: S607 - PATH-resolved executable by design
            capture_output=True,
            check=True,
            timeout=5,
        )
        return True
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def get_railway_cli_version() -> str | None:
    """
    Get the current Railway CLI version string.

    Returns
    -------
        Version string (e.g., "4.0.0") or None if not installed or error

    """
    try:
        result = subprocess.run(
            ["railway", "--version"],  # noqa: S607 - PATH-resolved executable by design
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        version_str = result.stdout.strip()

        # Extract version number (format: "railway version X.Y.Z")
        parts = version_str.split()
        if len(parts) >= 3:
            return parts[2]
        return None
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return None


def install_railway_cli() -> bool:
    """
    Install Railway CLI via npm.

    Returns
    -------
        True if installation successful, False otherwise

    """
    try:
        result = subprocess.run(
            ["npm", "install", "-g", "@railway/cli"],  # noqa: S607 - PATH-resolved executable by design
            capture_output=True,
            text=True,
            timeout=180,  # npm install can take a while
        )
        return result.returncode == 0
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def upgrade_railway_cli() -> bool:
    """
    Upgrade Railway CLI to the latest version via npm.

    Returns
    -------
        True if upgrade successful, False otherwise

    """
    try:
        result = subprocess.run(
            ["npm", "update", "-g", "@railway/cli"],  # noqa: S607 - PATH-resolved executable by design
            capture_output=True,
            text=True,
            timeout=180,  # npm update can take a while
        )
        return result.returncode == 0
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def login_railway_cli_browserless() -> bool:
    """
    Login to Railway using browserless mode.

    This will prompt the user to visit a URL and enter a pairing code.

    Returns
    -------
        True if login successful, False otherwise

    """
    try:
        # Run interactively so user can see the authentication URL and instructions
        result = subprocess.run(
            ["railway", "login", "--browserless"],  # noqa: S607 - PATH-resolved executable by design
            timeout=300,  # Give user 5 minutes to complete auth
        )
        return result.returncode == 0
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def is_railway_cli_installed() -> bool:
    """Check if Railway CLI is installed."""
    try:
        subprocess.run(
            ["railway", "--version"],  # noqa: S607 - PATH-resolved executable by design
            capture_output=True,
            check=True,
            timeout=5,
        )
        return True
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def check_railway_cli_version(minimum: str = "3.0.0") -> bool:
    """Check if Railway CLI meets minimum version requirement."""
    try:
        result = subprocess.run(
            ["railway", "--version"],  # noqa: S607 - PATH-resolved executable by design
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        version_str = result.stdout.strip()

        # Extract version number (format: "railway version X.Y.Z")
        parts = version_str.split()
        if len(parts) >= 3:
            current_version = parts[2]
            return _railway_utils._compare_versions(current_version, minimum) >= 0
        return False
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def _compare_versions(version1: str, version2: str) -> int:
    """Compare two semantic version strings."""
    v1_parts = [int(x) for x in version1.split(".")]
    v2_parts = [int(x) for x in version2.split(".")]

    for v1, v2 in zip(v1_parts, v2_parts):
        if v1 > v2:
            return 1
        elif v1 < v2:
            return -1
    return 0


def is_railway_authenticated() -> bool:
    """Check if user is authenticated with Railway."""
    try:
        result = subprocess.run(
            ["railway", "whoami"],  # noqa: S607 - PATH-resolved executable by design
            capture_output=True,
            check=True,
            timeout=5,
        )
        return result.returncode == 0
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def is_railway_project_initialized() -> bool:
    """Check if Railway project is initialized in current directory."""
    from pathlib import Path

    railway_config = Path(".railway")
    return railway_config.exists()


def get_railway_project_info() -> dict[str, Any] | None:
    """Get current Railway project information."""
    if not _railway_utils.is_railway_project_initialized():
        return None

    try:
        result = subprocess.run(
            ["railway", "status"],  # noqa: S607 - PATH-resolved executable by design
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        # Parse status output for project information
        info = {"status": result.stdout.strip()}
        return info
    except subprocess.SubprocessError, subprocess.TimeoutExpired:
        return None


def run_railway_command(
    args: list[str],
    timeout: int = 60,
    interactive: bool = False,
    cwd: str | Path | None = None,
    input_data: str | None = None,
) -> subprocess.CompletedProcess:
    """
    Execute Railway CLI command with error handling.

    Args:
    ----
        args: Command arguments to pass to railway CLI
        timeout: Command timeout in seconds
        interactive: If True, run command interactively without capturing output
        cwd: Working directory for the command (if None, uses current directory)
        input_data: String data to pipe to stdin (non-interactive only)

    Returns:
    -------
        CompletedProcess result

    """
    cmd = ["railway"] + args

    try:
        if interactive:
            if input_data is not None:
                raise ValueError("input_data is not supported in interactive mode.")
            # Run interactively - let user see prompts and provide input
            result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
                cmd,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
        else:
            # Run non-interactively - capture output
            run_kwargs: dict[str, Any] = {
                "capture_output": True,
                "text": True,
                "timeout": timeout,
                "cwd": cwd,
            }
            if input_data is not None:
                run_kwargs["input"] = input_data
            result = subprocess.run(cmd, **run_kwargs)  # noqa: S603 - fixed argv list, shell disabled
        return result
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(
            f"Railway command timed out after {timeout}s: {' '.join(cmd)}"
        ) from e
    except FileNotFoundError as e:
        raise FileNotFoundError(
            "Railway CLI not found. Install with: npm install -g @railway/cli"
        ) from e


def deploy_railway_service(
    project_path: str | Path,
    service_name: str,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    """Deploy the application at *project_path* to Railway as a detached trigger.

    This is a **non-interactive** shared seam intended for use by the
    apply step pipeline as well as the ``quickscale deploy railway`` CLI
    command.  It does **not** call ``sys.exit`` or ``click`` — callers
    are responsible for converting the return value into appropriate
    user-facing behaviour.

    Args:
    ----
        project_path: Absolute or relative path to the project root
            (where ``railway.json`` lives).
        service_name: The Railway service name to deploy.
        timeout: Command timeout in seconds (default 60).

    Returns:
    -------
        The :class:`subprocess.CompletedProcess` from the Railway CLI
        ``up --detach`` invocation.  Callers should check ``returncode``.

    Raises:
    ----
        FileNotFoundError: If the Railway CLI is not installed.
        TimeoutError: If the command times out.

    """
    return _railway_utils.run_railway_command(
        ["up", "--service", service_name, "--detach"],
        timeout=timeout,
        cwd=project_path,
    )


def set_railway_variable(
    key: str,
    value: str,
    service: str | None = None,
    environment: str | None = None,
    skip_deploy: bool = False,
) -> bool:
    """
    Set Railway environment variable via stdin (SA31).

    The value is piped through stdin (``railway variable set KEY --stdin``)
    rather than passed on the command line, avoiding secret exposure in
    ``ps``/``/proc`` on shared hosts.

    Args:
    ----
        key: Environment variable name
        value: Environment variable value
        service: Service name to set variable for (optional)
        environment: Railway environment name to target (optional)
        skip_deploy: If True, pass ``--skip-deploys`` to avoid triggering a
            deployment (used by batch callers to reduce deploy churn)

    """
    try:
        cmd = ["variable", "set", key, "--stdin"]
        if service:
            cmd.extend(["--service", service])
        if environment:
            cmd.extend(["--environment", environment])
        if skip_deploy:
            cmd.append("--skip-deploys")
        result = _railway_utils.run_railway_command(cmd, timeout=30, input_data=value)
        return result.returncode == 0
    except Exception:
        return False


def set_railway_variables_batch(
    variables: dict[str, str],
    service: str | None = None,
    environment: str | None = None,
) -> tuple[bool, list[str]]:
    """
    Set multiple Railway environment variables via per-variable stdin calls.

    Railway CLI does **not** support batch-stdin or env-file input
    (confirmed 2026-07-05).  Each variable is set individually through
    ``railway variable set KEY --stdin``, which keeps the value off
    process argv.      ``--skip-deploys`` is forced on **all** writes so
    that an auto-deploy is never triggered after a partial failure
    (CR-SA31-001).  Callers are responsible for triggering a deploy
    after confirming 100% success.

    Args:
    ----
        variables: Dictionary of environment variable names and values
        service: Service name to set variables for (optional)
        environment: Railway environment name to target (optional)

    Returns:
    -------
        Tuple of (success, failed_keys)
        - success: True if all variables were set successfully
        - failed_keys: List of variable keys that failed to set

    """
    if not variables:
        return True, []

    failed_keys: list[str] = []
    for key, value in variables.items():
        if not _railway_utils.set_railway_variable(
            key,
            value,
            service=service,
            environment=environment,
            skip_deploy=True,
        ):
            failed_keys.append(key)
    return len(failed_keys) == 0, failed_keys
