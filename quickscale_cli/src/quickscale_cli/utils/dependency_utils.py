"""System dependency checking utilities."""

import shutil
import subprocess
from typing import NamedTuple


class DependencyStatus(NamedTuple):
    """Status of a system dependency check."""

    name: str
    installed: bool
    version: str | None
    required: bool
    purpose: str


def check_python_version() -> DependencyStatus:
    """Check Python version (3.11+ required)."""
    import sys

    version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    meets_requirement = sys.version_info >= (3, 11)

    return DependencyStatus(
        name="Python",
        installed=meets_requirement,
        version=version if meets_requirement else None,
        required=True,
        purpose="Runtime for QuickScale and generated projects",
    )


def check_poetry_installed() -> DependencyStatus:
    """Check if Poetry is installed."""
    try:
        result = subprocess.run(
            ["poetry", "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        version_str = result.stdout.strip()
        # Extract version (format: "Poetry (version X.Y.Z)")
        version = version_str.split()[-1].strip("()")

        return DependencyStatus(
            name="Poetry",
            installed=True,
            version=version,
            required=True,
            purpose="Dependency management for generated projects",
        )
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        return DependencyStatus(
            name="Poetry",
            installed=False,
            version=None,
            required=True,
            purpose="Dependency management for generated projects",
        )


def check_git_installed() -> DependencyStatus:
    """Check if Git is installed."""
    git_path = shutil.which("git")

    if git_path:
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            version_str = result.stdout.strip()
            # Extract version (format: "git version X.Y.Z")
            version = version_str.split()[-1]

            return DependencyStatus(
                name="Git",
                installed=True,
                version=version,
                required=False,
                purpose="Version control and module management (quickscale embed/update)",
            )
        except (
            subprocess.SubprocessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            pass

    return DependencyStatus(
        name="Git",
        installed=False,
        version=None,
        required=False,
        purpose="Version control and module management (quickscale embed/update)",
    )


def check_docker_installed() -> DependencyStatus:
    """Check if Docker is installed."""
    docker_path = shutil.which("docker")

    if docker_path:
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            version_str = result.stdout.strip()
            # Extract version (format: "Docker version X.Y.Z, build ...")
            parts = version_str.split()
            version = parts[2].rstrip(",") if len(parts) >= 3 else None

            return DependencyStatus(
                name="Docker",
                installed=True,
                version=version,
                required=False,
                purpose="Containerized development (quickscale up/down)",
            )
        except (
            subprocess.SubprocessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            pass

    return DependencyStatus(
        name="Docker",
        installed=False,
        version=None,
        required=False,
        purpose="Containerized development (quickscale up/down)",
    )


def check_postgresql_installed() -> DependencyStatus:
    """Check if PostgreSQL client is installed."""
    psql_path = shutil.which("psql")

    if psql_path:
        try:
            result = subprocess.run(
                ["psql", "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            version_str = result.stdout.strip()
            # Extract version (format: "psql (PostgreSQL) X.Y.Z")
            parts = version_str.split()
            version = parts[-1] if parts else None

            return DependencyStatus(
                name="PostgreSQL",
                installed=True,
                version=version,
                required=False,
                purpose="Database server (required for production, Docker provides for dev)",
            )
        except (
            subprocess.SubprocessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            pass

    return DependencyStatus(
        name="PostgreSQL",
        installed=False,
        version=None,
        required=False,
        purpose="Database server (required for production, Docker provides for dev)",
    )


def check_all_dependencies() -> list[DependencyStatus]:
    """Check all system dependencies."""
    return [
        check_python_version(),
        check_poetry_installed(),
        check_git_installed(),
        check_docker_installed(),
        check_postgresql_installed(),
    ]


def verify_required_dependencies() -> tuple[bool, list[DependencyStatus]]:
    """
    Verify all required dependencies are installed.

    Returns
    -------
        Tuple of (all_required_present, missing_dependencies)

    """
    all_deps = check_all_dependencies()
    missing = [dep for dep in all_deps if dep.required and not dep.installed]
    return (len(missing) == 0, missing)
