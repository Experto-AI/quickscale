"""Snapshot and archive primitives — Django-free DR engine foundation.

These functions are the platform-level snapshot/archive layer defined in
docs/technical/decisions.md § Disaster Recovery Engine Boundary Contract
(F5 / M10), phase F5.2a. They have no Django dependency and may be imported
by the CLI layer, the embeddable backups module, or any future consumer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REQUIRED_POSTGRESQL_MAJOR: int = 18
_LEADING_MAJOR_VERSION_PATTERN = re.compile(r"^\s*(\d+)")
_ANY_MAJOR_VERSION_PATTERN = re.compile(r"(\d+)")
_POSTGRESQL_CUSTOM_ARCHIVE_MAGIC = b"PGDMP"

_SNAPSHOTS_DIRECTORY_NAME = "snapshots"
_SNAPSHOT_DATABASE_DIRECTORY_NAME = "database"
_MEDIA_SYNC_MANIFEST_FILENAME = "media-sync-manifest.json"
_ENV_VAR_MANIFEST_FILENAME = "env-var-manifest.json"
_RELEASE_METADATA_FILENAME = "release-metadata.json"
_PROMOTION_VERIFICATION_FILENAME = "promotion-verification.json"
_REQUIRED_SNAPSHOT_SIDECAR_FILENAMES = (
    _MEDIA_SYNC_MANIFEST_FILENAME,
    _ENV_VAR_MANIFEST_FILENAME,
    _RELEASE_METADATA_FILENAME,
    _PROMOTION_VERIFICATION_FILENAME,
)

# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------


class BackupError(Exception):
    """Base error for backup operations."""


class BackupConfigurationError(BackupError):
    """Raised when backup policy settings are invalid for the requested operation."""


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class ShellCommandRunner(Protocol):
    """Protocol for shell-based backup and restore runners."""

    def __call__(
        self,
        command: Sequence[str],
        *,
        env: dict[str, str] | None = None,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Shared dataclasses
# ---------------------------------------------------------------------------

_DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR = "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
_DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR = (
    "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
)


@dataclass(frozen=True)
class BackupPolicySnapshot:
    """Immutable view of the active backup policy."""

    retention_days: int
    naming_prefix: str
    target_mode: str
    local_directory: str
    remote_bucket_name: str
    remote_prefix: str
    remote_endpoint_url: str
    remote_region_name: str
    remote_access_key_id_env_var: str
    remote_secret_access_key_env_var: str
    automation_enabled: bool
    schedule: str

    def resolve_remote_access_key_id(self) -> str:
        """Return the runtime private-remote access key id from the environment."""
        env_var_name = (
            self.remote_access_key_id_env_var.strip()
            or _DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR
        )
        return os.getenv(env_var_name, "").strip()

    def resolve_remote_secret_access_key(self) -> str:
        """Return the runtime private-remote secret access key from the environment."""
        env_var_name = (
            self.remote_secret_access_key_env_var.strip()
            or _DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
        )
        return os.getenv(env_var_name, "").strip()


# ---------------------------------------------------------------------------
# PostgreSQL guidance text
# ---------------------------------------------------------------------------


def _postgresql_18_client_tooling_guidance() -> str:
    """Return operator guidance for the PostgreSQL 18 client-tooling contract."""
    return (
        " Install PostgreSQL 18 client tooling via the PGDG apt repository plus "
        "'postgresql-client-18' in Docker/CI runtimes, or run the command in an "
        "environment that already provides PostgreSQL 18 pg_dump/pg_restore. "
        "Existing generated projects must adopt those Docker/CI/E2E file changes "
        "manually because quickscale apply does not rewrite user-owned files."
    )


# ---------------------------------------------------------------------------
# Shell execution
# ---------------------------------------------------------------------------


def _missing_executable_backup_error(executable: str) -> BackupError:
    """Build a consistent missing-executable error for shell-backed operations."""
    hint = ""
    if executable in {"pg_dump", "pg_restore"}:
        hint = _postgresql_18_client_tooling_guidance()
    return BackupError(
        f"Required executable '{executable}' is not installed in this runtime.{hint}"
    )


def _run_shell_command(
    command: Sequence[str],
    *,
    env: dict[str, str] | None = None,
) -> None:
    command_env = os.environ.copy()
    if env:
        command_env.update(env)

    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            check=False,
            text=True,
            env=command_env,
        )
    except FileNotFoundError as exc:
        executable = str(command[0]).strip() if command else "command"
        raise _missing_executable_backup_error(executable) from exc
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise BackupError(f"Command failed: {' '.join(command)} :: {stderr}")


# ---------------------------------------------------------------------------
# Version extraction helpers
# ---------------------------------------------------------------------------


def _extract_leading_major_version(version_text: str | None) -> int | None:
    """Return the leading major version number from a server version string."""
    if not version_text:
        return None

    match = _LEADING_MAJOR_VERSION_PATTERN.match(version_text)
    if match is None:
        return None

    major = int(match.group(1))
    return major if major > 0 else None


def _extract_any_major_version(version_text: str | None) -> int | None:
    """Return the first major version number found in a tool version string."""
    if not version_text:
        return None

    match = _ANY_MAJOR_VERSION_PATTERN.search(version_text)
    if match is None:
        return None

    major = int(match.group(1))
    return major if major > 0 else None


def _get_postgresql_tool_version(executable: str) -> str:
    """Return the installed PostgreSQL client-tool version string."""
    guidance = (
        _postgresql_18_client_tooling_guidance()
        if executable in {"pg_dump", "pg_restore"}
        else ""
    )
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            check=False,
            text=True,
            env=os.environ.copy(),
        )
    except FileNotFoundError as exc:
        raise _missing_executable_backup_error(executable) from exc

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise BackupError(
            f"Unable to determine {executable} version: {stderr}{guidance}"
        )

    output = result.stdout.strip() or result.stderr.strip()
    if not output:
        raise BackupError(
            f"Unable to determine {executable} version: command returned no output."
            + guidance
        )
    return output


# ---------------------------------------------------------------------------
# Database engine helpers
# ---------------------------------------------------------------------------


def _database_engine_family(engine: str) -> str:
    """Normalize database engines into restore compatibility families."""
    normalized_engine = engine.strip().lower()
    if "postgresql" in normalized_engine:
        return "postgresql"
    if "sqlite" in normalized_engine:
        return "sqlite"
    return normalized_engine


def _expected_backup_format_for_engine(engine: str) -> str:
    """Return the backup format QuickScale expects for the current engine."""
    if _database_engine_family(engine) == "postgresql":
        return "pg_dump_custom"
    return "json"


# ---------------------------------------------------------------------------
# PostgreSQL dump/restore command building
# ---------------------------------------------------------------------------


def _build_pg_dump_command(
    local_path: Path,
    connection_settings: dict[str, Any],
) -> tuple[list[str], dict[str, str] | None]:
    command = ["pg_dump", "--format=c", "--file", str(local_path)]
    if host := str(connection_settings.get("HOST") or "").strip():
        command.extend(["--host", host])
    if port := str(connection_settings.get("PORT") or "").strip():
        command.extend(["--port", port])
    if user := str(connection_settings.get("USER") or "").strip():
        command.extend(["--username", user])

    database_name = str(connection_settings.get("NAME") or "").strip()
    if not database_name:
        raise BackupConfigurationError("DATABASES['default']['NAME'] is required")
    command.append(database_name)

    password = str(connection_settings.get("PASSWORD") or "").strip()
    env = None
    if password:
        env = {"PGPASSWORD": password}
    return command, env


def _build_pg_restore_command(
    local_path: Path,
    connection_settings: dict[str, Any],
) -> tuple[list[str], dict[str, str] | None]:
    command = [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
    ]
    if host := str(connection_settings.get("HOST") or "").strip():
        command.extend(["--host", host])
    if port := str(connection_settings.get("PORT") or "").strip():
        command.extend(["--port", port])
    if user := str(connection_settings.get("USER") or "").strip():
        command.extend(["--username", user])

    database_name = str(connection_settings.get("NAME") or "").strip()
    if not database_name:
        raise BackupConfigurationError("DATABASES['default']['NAME'] is required")

    command.extend(["--dbname", database_name, str(local_path)])
    password = str(connection_settings.get("PASSWORD") or "").strip()
    env = None
    if password:
        env = {"PGPASSWORD": password}
    return command, env


def _dump_postgresql_database(
    local_path: Path,
    connection_settings: dict[str, Any],
    *,
    shell_runner: ShellCommandRunner | None = None,
) -> None:
    command, env = _build_pg_dump_command(local_path, connection_settings)
    runner = shell_runner or _run_shell_command
    runner(command, env=env)


# ---------------------------------------------------------------------------
# Snapshot structure
# ---------------------------------------------------------------------------


def _mint_snapshot_id() -> str:
    """Return an opaque stable identifier for one stored snapshot."""
    return uuid4().hex


def _relative_snapshot_child_path(snapshot_root: Path, child_path: Path) -> str:
    """Return a stable snapshot-relative path for one child file."""
    return child_path.relative_to(snapshot_root).as_posix()


def _build_snapshot_child_descriptor(
    *,
    kind: str,
    status: str,
    relative_path: str,
    local_path: Path | None = None,
    remote_key: str = "",
    error: str = "",
    size_bytes: int | None = None,
    checksum_sha256: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build JSON metadata describing one child stored under a snapshot root."""
    descriptor: dict[str, Any] = {
        "kind": kind,
        "status": status,
        "relative_path": relative_path,
        "local_path": str(local_path) if local_path is not None else "",
    }
    if remote_key:
        descriptor["remote_key"] = remote_key
    if error:
        descriptor["error"] = error
    if size_bytes is not None:
        descriptor["size_bytes"] = size_bytes
    if checksum_sha256:
        descriptor["checksum_sha256"] = checksum_sha256
    if metadata:
        descriptor["metadata"] = metadata
    return descriptor


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON payload with deterministic formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 64), b""):
            digest.update(chunk)
    return digest.hexdigest()
