"""Railway CLI interaction utilities for deployment."""

import json
import subprocess
import time
from pathlib import Path
from typing import Any


def is_npm_installed() -> bool:
    """Check if npm is installed."""
    try:
        subprocess.run(
            ["npm", "--version"],
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
            ["railway", "--version"],
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
            ["npm", "install", "-g", "@railway/cli"],
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
            ["npm", "update", "-g", "@railway/cli"],
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
            ["railway", "login", "--browserless"],
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
            ["railway", "--version"],
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
            ["railway", "--version"],
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
            return _compare_versions(current_version, minimum) >= 0
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
            ["railway", "whoami"],
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
    if not is_railway_project_initialized():
        return None

    try:
        result = subprocess.run(
            ["railway", "status"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        # Parse status output for project information
        info = {"status": result.stdout.strip()}
        return info
    except (subprocess.SubprocessError, subprocess.TimeoutExpired):
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
            result = subprocess.run(
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
            result = subprocess.run(cmd, **run_kwargs)
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
    return run_railway_command(
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
        result = run_railway_command(cmd, timeout=30, input_data=value)
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
        if not set_railway_variable(
            key,
            value,
            service=service,
            environment=environment,
            skip_deploy=True,
        ):
            failed_keys.append(key)
    return len(failed_keys) == 0, failed_keys


def generate_django_secret_key() -> str:
    """Generate a secure Django SECRET_KEY."""
    import secrets
    import string

    # Ensure we include at least one of each required character type
    chars = string.ascii_letters + string.digits + "!@#$%^&*(-_=+)"

    # Generate a key with guaranteed character diversity
    key_chars = []

    # Add at least one lowercase
    key_chars.append(secrets.choice(string.ascii_lowercase))
    # Add at least one uppercase
    key_chars.append(secrets.choice(string.ascii_uppercase))
    # Add at least one digit
    key_chars.append(secrets.choice(string.digits))

    # Fill the rest randomly
    for _ in range(47):  # 50 - 3 = 47
        key_chars.append(secrets.choice(chars))

    # Shuffle to avoid predictable pattern
    secrets.SystemRandom().shuffle(key_chars)

    return "".join(key_chars)


def get_deployment_url(service: str | None = None) -> str | None:
    """
    Get deployment URL from Railway project.

    Args:
    ----
        service: Service name (unused - kept for compatibility)

    Note:
    ----
        Railway CLI v4's `status` command does not accept --service flag.
        This function returns the first deployment URL found.

    """
    try:
        result = run_railway_command(["status"], timeout=10)

        if result.returncode == 0:
            # Parse output for deployment URL
            found_https = False
            for line in result.stdout.split("\n"):
                if "https://" in line:
                    found_https = True
                    # Extract URL from line
                    parts = line.split()
                    for part in parts:
                        if part.startswith("https://") and len(part) > len("https://"):
                            return str(part)
            if found_https:
                raise ValueError(
                    f"Found https:// in Railway status output but could not "
                    f"extract a valid URL. Output format may have changed: "
                    f"{result.stdout.strip()[:200]}"
                )
        return None
    except (TimeoutError, FileNotFoundError):
        return None


def get_app_service_name(project_name: str | None = None) -> str:
    """
    Determine the app service name for Railway deployment.

    Args:
    ----
        project_name: Project name (must be provided)

    Returns:
    -------
        Service name to use for the app

    Raises:
    ------
        ValueError: If *project_name* is ``None`` or empty

    """
    if project_name:
        return project_name

    raise ValueError(
        "project_name is required for get_app_service_name(). "
        "Pass an explicit project slug instead of relying on CWD."
    )


def generate_railway_domain(service: str) -> str | None:
    """
    Generate Railway public domain for a service.

    Args:
    ----
        service: Service name to generate domain for

    Returns:
    -------
        Generated domain URL or None if failed

    """
    try:
        result = run_railway_command(["domain", "--service", service], timeout=30)

        if result.returncode == 0:
            # Parse output for generated domain
            # Railway outputs something like: "Generated domain: https://myapp-production-abc123.up.railway.app"
            output: str = result.stdout.strip()

            # Look for URLs in the output
            import re

            url_pattern = r"https://[a-zA-Z0-9.-]+\.up\.railway\.app"
            match = re.search(url_pattern, output)

            if match:
                return match.group(0)

            # If no match, check if entire output is a URL
            if output.startswith("https://") and ".railway.app" in output:
                return output

            # Detect Railway domain pattern that couldn't be parsed — format drift
            if "https://" in output and (
                ".up.railway.app" in output or ".railway.app" in output
            ):
                raise ValueError(
                    f"Found Railway domain pattern in status output but could not "
                    f"parse a valid URL. Output format may have changed: "
                    f"{output[:200]}"
                )

        return None
    except (TimeoutError, FileNotFoundError):
        return None


def check_uncommitted_changes() -> tuple[bool, str]:
    """
    Check if there are uncommitted changes in the Git repository.

    Returns
    -------
        Tuple of (has_changes, status_output)
        - has_changes: True if there are uncommitted changes
        - status_output: Git status output string

    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        status_output = result.stdout.strip()
        has_changes = bool(status_output)
        return has_changes, status_output
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        # If git is not available or not a git repo, return False
        return False, ""


def verify_railway_json() -> tuple[bool, str]:
    """
    Verify that railway.json exists and is valid JSON.

    Returns
    -------
        Tuple of (is_valid, error_message)
        - is_valid: True if file exists and is valid JSON
        - error_message: Error description if validation fails, empty string otherwise

    """
    railway_json_path = Path("railway.json")

    if not railway_json_path.exists():
        return False, "railway.json not found in project root"

    try:
        with open(railway_json_path) as f:
            json.load(f)
        return True, ""
    except json.JSONDecodeError as e:
        return False, f"railway.json is not valid JSON: {e}"
    except Exception as e:
        return False, f"Error reading railway.json: {e}"


def verify_dockerfile() -> tuple[bool, str]:
    """
    Verify that Dockerfile exists in the project root.

    Returns
    -------
        Tuple of (exists, error_message)
        - exists: True if Dockerfile exists
        - error_message: Error description if check fails, empty string otherwise

    """
    dockerfile_path = Path("Dockerfile")

    if not dockerfile_path.exists():
        return False, "Dockerfile not found in project root"

    return True, ""


def verify_railway_dependencies() -> tuple[bool, list[str]]:
    """
    Verify that pyproject.toml has required Railway dependencies.

    Required dependencies for Railway deployment:
    - gunicorn (WSGI server)
    - psycopg2-binary (PostgreSQL adapter)
    - dj-database-url (Database URL parsing)
    - whitenoise (Static file serving)

    Returns
    -------
        Tuple of (all_present, missing_deps)
        - all_present: True if all required dependencies are present
        - missing_deps: List of missing dependency names

    """
    pyproject_path = Path("pyproject.toml")

    if not pyproject_path.exists():
        return False, ["pyproject.toml not found"]

    required_deps = ["gunicorn", "psycopg2-binary", "dj-database-url", "whitenoise"]
    missing_deps = []

    try:
        with open(pyproject_path) as f:
            content = f.read()

        # Simple check - look for dependency names in the file
        # This is a basic check and may have false positives/negatives
        for dep in required_deps:
            if dep not in content:
                missing_deps.append(dep)

        return len(missing_deps) == 0, missing_deps
    except Exception as e:
        return False, [f"Error reading pyproject.toml: {e}"]


def check_poetry_lock_consistency() -> tuple[bool, str]:
    """
    Check if poetry.lock is consistent with pyproject.toml.

    Returns
    -------
        Tuple of (is_consistent, message)
        - is_consistent: True if poetry.lock is consistent with pyproject.toml
        - message: Status message

    """
    pyproject_path = Path("pyproject.toml")
    poetry_lock_path = Path("poetry.lock")

    if not pyproject_path.exists():
        return False, "pyproject.toml not found"

    if not poetry_lock_path.exists():
        return False, "poetry.lock not found - run 'poetry lock' to create it"

    try:
        # Run poetry check to verify lock file consistency
        result = subprocess.run(
            ["poetry", "check", "--lock"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            return True, "poetry.lock is consistent with pyproject.toml"
        else:
            return False, "poetry.lock is inconsistent with pyproject.toml"
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        # If poetry is not available, we can't check
        return True, "Unable to verify poetry.lock consistency (poetry not found)"


def fix_poetry_lock() -> tuple[bool, str]:
    """
    Fix poetry.lock by running poetry lock.

    Returns
    -------
        Tuple of (success, message)
        - success: True if lock file was fixed successfully
        - message: Status message

    """
    try:
        result = subprocess.run(
            ["poetry", "lock"],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            return True, "poetry.lock updated successfully"

        return False, f"Failed to update poetry.lock: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "poetry lock timed out"
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        return False, f"Failed to run poetry lock: {e}"


def get_railway_variables(
    service: str | None = None,
    environment: str | None = None,
) -> dict[str, str] | None:
    """
    Get all environment variables for a Railway service.

    Tries JSON output first (--json flag) for reliable structured parsing,
    then falls back to KEY=VALUE line parsing for older CLI versions.

    Args:
    ----
        service: Service name (optional)
        environment: Railway environment name (optional)

    Returns:
    -------
        Dictionary of variable names and values, or None if failed

    """
    try:
        cmd = ["variables"]
        if service:
            cmd.extend(["--service", service])
        if environment:
            cmd.extend(["--environment", environment])

        # Try JSON output first for reliable parsing
        json_vars = _get_railway_variables_json(cmd)
        if json_vars is not None:
            return json_vars

        # Fall back to text parsing for older CLI versions
        result = run_railway_command(cmd, timeout=30)

        if result.returncode == 0:
            # Parse output to extract variables
            # Railway CLI outputs variables in format: KEY=VALUE
            variables = {}
            for line in result.stdout.split("\n"):
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    # Split only on first = to handle values with =
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key, value = parts
                        variables[key.strip()] = value.strip()
            # CR-SA18.7-002: Non-empty output with zero parseable KEY=VALUE pairs
            # is evidence of an unexpected output format — fail hard instead of
            # silently collapsing to {}. Truly empty output is benign.
            if not variables and result.stdout.strip():
                raise ValueError(
                    f"Railway CLI returned success with non-empty output but no "
                    f"KEY=VALUE pairs could be parsed. Output may have changed "
                    f"format: {result.stdout[:200]}"
                )
            return variables
        return None
    except (TimeoutError, FileNotFoundError):
        return None


def _get_railway_variables_json(
    base_cmd: list[str],
) -> dict[str, str] | None:
    """Try to get variables using Railway CLI --json flag.

    Args:
    ----
        base_cmd: Base command list (e.g. ["variables", "--service", "myapp"])

    Returns:
    -------
        Dictionary of variable names and values, or None if JSON output unavailable

    """
    try:
        result = run_railway_command(base_cmd + ["--json"], timeout=30)
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise ValueError(
                f"Railway CLI returned success but JSON output could not be "
                f"parsed (output format may have changed): "
                f"{result.stdout[:200]}"
            )
        # Railway JSON output can be a dict of {key: value} or a list of objects
        if isinstance(data, dict):
            return {k: str(v) for k, v in data.items()}
        if isinstance(data, list):
            variables: dict[str, str] = {}
            for item in data:
                if isinstance(item, dict) and "name" in item and "value" in item:
                    variables[item["name"]] = str(item["value"])
            if variables:
                return variables
            # Empty list — no variables set, which is benign
            return {}
        raise ValueError(
            f"Railway CLI returned success but output format is unrecognized "
            f"(expected dict or list, got {type(data).__name__}). "
            f"Output may have changed: {result.stdout[:200]}"
        )
    except TimeoutError:
        return None


def link_database_to_service(service: str) -> tuple[bool, str]:
    """
    Link PostgreSQL DATABASE_URL reference to app service.

    In Railway v4+, services need explicit variable references to connect.
    This creates a DATABASE_URL reference variable that points to the PostgreSQL service.

    Args:
    ----
        service: App service name to link database to

    Returns:
    -------
        Tuple of (success, message)
        - success: True if link was created successfully
        - message: Status or error message

    """
    reference_services = ("Postgres", "PostgreSQL")
    max_attempts = 12
    retry_delay_seconds = 10
    max_wait_seconds = 180
    last_error: str = "Unknown error"
    start_time = time.monotonic()
    attempts_completed = 0

    for attempt in range(1, max_attempts + 1):
        if time.monotonic() - start_time >= max_wait_seconds:
            break

        attempts_completed = attempt
        for reference in reference_services:
            if time.monotonic() - start_time >= max_wait_seconds:
                break

            try:
                result = run_railway_command(
                    [
                        "variables",
                        "--set",
                        f"DATABASE_URL=${{{{{reference}.DATABASE_URL}}}}",
                        "--service",
                        service,
                    ],
                    timeout=45,
                )
            except TimeoutError:
                last_error = (
                    f"Timed out while waiting for {reference}.DATABASE_URL reference"
                )
                continue
            except Exception as e:
                error_text = str(e).strip()
                if error_text:
                    last_error = error_text
                if _is_non_retryable_database_link_error(error_text):
                    return False, f"Error linking DATABASE_URL: {error_text}"
                continue

            if result.returncode == 0:
                return True, "DATABASE_URL reference linked successfully"

            error_text = (result.stderr or result.stdout or "").strip()
            if error_text:
                last_error = error_text

            if _is_non_retryable_database_link_error(error_text):
                return False, f"Failed to link DATABASE_URL: {error_text}"

        deployed_vars = get_railway_variables(service)
        if deployed_vars:
            db_val = deployed_vars.get("DATABASE_URL", "")
            if db_val and not db_val.startswith("${"):
                return True, "DATABASE_URL reference linked successfully"

        if attempt < max_attempts and time.monotonic() - start_time < max_wait_seconds:
            time.sleep(retry_delay_seconds)

    return (
        False,
        "Failed to link DATABASE_URL after "
        f"{attempts_completed} attempts (~{max_wait_seconds}s max wait): {last_error}",
    )


def _is_non_retryable_database_link_error(error_text: str) -> bool:
    """Return True if the DATABASE_URL link error should fail fast."""
    normalized = error_text.lower()
    if not normalized:
        return False

    non_retryable_markers = (
        "railway cli not found",
        "cli not found",
        "not authenticated",
        "unauthorized",
        "forbidden",
        "permission denied",
        "no project found",
        "project not found",
        "not linked to a project",
        "not in a project",
        "run railway link",
        "invalid token",
        "invalid argument",
        "unknown option",
        "unknown argument",
        "usage:",
    )
    return any(marker in normalized for marker in non_retryable_markers)
