"""Restore/orchestration contracts and helpers — Django-free DR engine foundation.

These are the platform-level restore contracts and orchestration helpers defined
in docs/technical/decisions.md § Disaster Recovery Engine Boundary Contract
(F5 / M10), phase F5.2b. They have no Django dependency and may be imported
by the CLI layer, the embeddable backups module, or any future consumer.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Iterator, Protocol

from quickscale_core.dr_engine.primitives import (
    BackupError,
    ShellCommandRunner,
    _POSTGRESQL_CUSTOM_ARCHIVE_MAGIC,
    _REQUIRED_POSTGRESQL_MAJOR,
    _build_pg_restore_command,
    _compute_sha256,
    _database_engine_family,
    _expected_backup_format_for_engine,
    _run_shell_command,
)

# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------


class BackupRestoreBlocked(BackupError):
    """Raised when destructive restore execution is intentionally blocked."""


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class ArtifactLike(Protocol):
    """Minimal protocol for the subset of BackupArtifact needed by recovery.

    Any Django-free or Django-backed artifact that provides these fields
    satisfies this protocol.
    """

    backup_format: str
    database_engine: str
    checksum_sha256: str
    size_bytes: int | None
    filename: str
    local_path: str | None
    remote_key: str
    database_server_major: int | None
    dump_client_major: int | None

    def is_export_only(self) -> bool: ...


class RemoteMaterializer(Protocol):
    """Protocol used for temporary private remote restore materialization."""

    def __call__(
        self,
        remote_key: str,
        policy: Any,
        destination: Path,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RestoreWarning:
    """Structured non-fatal warning emitted after restore execution."""

    code: str
    message: str
    details: dict[str, str] | None = None


class RestoreSourceResolutionMode(StrEnum):
    """How restore source resolution may use private remote artifacts."""

    REMOTE_FALLBACK = "remote_fallback"
    LOCAL_ONLY = "local_only"


@dataclass(frozen=True)
class RestoreResult:
    """Return value for guarded restore execution."""

    executed: bool
    dry_run: bool
    message: str
    warnings: tuple[RestoreWarning, ...] = ()


@dataclass(frozen=True)
class ResolvedRestoreSource:
    """Resolved local restore input used by the guarded restore pipeline."""

    confirmation_value: str
    local_path: Path
    backup_format: str
    artifact: ArtifactLike | None = None

    def is_export_only(self) -> bool:
        """Return whether this resolved source is blocked as export-only."""
        if self.artifact is None:
            return self.backup_format == "json"
        return self.artifact.is_export_only()


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _normalize_restore_file_path(file_path: str | Path) -> Path:
    """Resolve operator-supplied restore file paths relative to the current cwd."""
    resolved_path = Path(file_path).expanduser()
    if not resolved_path.is_absolute():
        resolved_path = Path.cwd() / resolved_path
    return resolved_path


def _detect_restore_file_format(file_path: Path) -> str:
    """Infer the operator-supplied restore input format from the file name."""
    if file_path.suffix.lower() == ".json":
        return "json"
    return "pg_dump_custom"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _collect_local_backup_validation_issues(
    local_path: Path | None,
    *,
    backup_format: str,
    expected_checksum: str | None = None,
    expected_size: int | None = None,
) -> list[str]:
    """Validate one local backup file without mutating artifact state."""
    issues: list[str] = []

    if local_path is None or not local_path.exists():
        issues.append("local backup artifact is missing")
        return issues

    if expected_checksum is not None:
        calculated_checksum = _compute_sha256(local_path)
        if calculated_checksum != expected_checksum:
            issues.append("checksum mismatch detected")

    if expected_size is not None:
        actual_size = local_path.stat().st_size
        if actual_size != expected_size:
            issues.append("size mismatch detected")

    if backup_format == "json":
        try:
            json.loads(local_path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            issues.append("json backup payload is not valid JSON")
        except json.JSONDecodeError:
            issues.append("json backup payload is not valid JSON")

    return issues


def _get_restore_source_validation_issues(
    restore_source: ResolvedRestoreSource,
) -> list[str]:
    """Return validation issues for the resolved restore source."""
    if restore_source.artifact is not None:
        return _collect_local_backup_validation_issues(
            restore_source.local_path,
            backup_format=restore_source.artifact.backup_format,
            expected_checksum=restore_source.artifact.checksum_sha256,
            expected_size=restore_source.artifact.size_bytes,
        )

    if not restore_source.local_path.exists():
        return [f"restore file not found: {restore_source.local_path}"]
    if not restore_source.local_path.is_file():
        return [f"restore file is not a regular file: {restore_source.local_path}"]
    return []


# ---------------------------------------------------------------------------
# Compatibility helpers
# ---------------------------------------------------------------------------


def _get_restore_compatibility_issues(
    artifact: ArtifactLike,
    current_engine: str,
) -> list[str]:
    """Return restore guardrail issues for current database engine compatibility."""
    issues: list[str] = []
    current_engine_family = _database_engine_family(current_engine)
    artifact_engine_family = _database_engine_family(artifact.database_engine)

    if artifact_engine_family != current_engine_family:
        issues.append(
            "artifact database engine "
            f"'{artifact.database_engine}' is incompatible with current database "
            f"engine '{current_engine}'"
        )

    expected_format = _expected_backup_format_for_engine(current_engine)
    if artifact.backup_format != expected_format:
        issues.append(
            "artifact backup format "
            f"'{artifact.backup_format}' is incompatible with current database "
            f"engine '{current_engine}' (expected '{expected_format}')"
        )

    if (
        artifact_engine_family == "postgresql"
        and artifact.backup_format == "pg_dump_custom"
    ):
        if (
            artifact.database_server_major is not None
            and artifact.database_server_major != _REQUIRED_POSTGRESQL_MAJOR
        ):
            issues.append(
                "artifact database server major "
                f"'{artifact.database_server_major}' is incompatible with the "
                f"PostgreSQL {_REQUIRED_POSTGRESQL_MAJOR} restore contract"
            )
        if (
            artifact.dump_client_major is not None
            and artifact.dump_client_major != _REQUIRED_POSTGRESQL_MAJOR
        ):
            issues.append(
                "artifact dump client major "
                f"'{artifact.dump_client_major}' is incompatible with the "
                f"PostgreSQL {_REQUIRED_POSTGRESQL_MAJOR} restore contract"
            )

    return issues


def _get_restore_source_compatibility_issues(
    restore_source: ResolvedRestoreSource,
    current_engine: str,
) -> list[str]:
    """Return compatibility issues for artifact and operator-supplied sources."""
    if restore_source.artifact is not None:
        return _get_restore_compatibility_issues(
            restore_source.artifact, current_engine
        )

    if _database_engine_family(current_engine) != "postgresql":
        return ["operator-supplied restore files require a PostgreSQL target database"]
    return []


# ---------------------------------------------------------------------------
# Operator-supplied custom archive validation
# ---------------------------------------------------------------------------


def _ensure_operator_supplied_custom_archive_valid(
    restore_source: ResolvedRestoreSource,
    *,
    shell_runner: ShellCommandRunner | None = None,
) -> None:
    """Require file-mode restore inputs to be real PostgreSQL custom archives."""
    if (
        restore_source.artifact is not None
        or restore_source.backup_format != "pg_dump_custom"
    ):
        return

    try:
        with restore_source.local_path.open("rb") as handle:
            archive_magic = handle.read(len(_POSTGRESQL_CUSTOM_ARCHIVE_MAGIC))
    except OSError as exc:
        raise BackupRestoreBlocked(
            "Restore blocked because the operator-supplied file could not be "
            f"inspected: {exc}"
        ) from exc

    if archive_magic != _POSTGRESQL_CUSTOM_ARCHIVE_MAGIC:
        raise BackupRestoreBlocked(
            "Restore blocked because operator-supplied file is not a valid "
            "PostgreSQL custom archive."
        )

    runner = shell_runner or _run_shell_command
    try:
        runner(["pg_restore", "--list", str(restore_source.local_path)], env=None)
    except BackupError as exc:
        raise BackupRestoreBlocked(
            "Restore blocked because operator-supplied file is not a valid "
            f"PostgreSQL custom archive: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# PostgreSQL 18 restore runtime enforcement
# ---------------------------------------------------------------------------


def _ensure_postgresql_18_restore_runtime(
    current_engine: str,
    *,
    require_contract: Callable[[str, str, str], tuple[str, int, str, int]]
    | None = None,
) -> None:
    """Require the current restore runtime to satisfy the PostgreSQL 18 contract.

    When *require_contract* is provided (the Django-backed checker from the
    backups module), the full server+tools version check runs.  When it is
    *None* the non-PostgreSQL engine check is still enforced but the version
    contract check is deferred to the caller.
    """
    if _database_engine_family(current_engine) != "postgresql":
        return

    if require_contract is not None:
        try:
            require_contract(
                current_engine,
                "pg_restore",
                "restore",
            )
        except BackupError as exc:
            raise BackupRestoreBlocked(str(exc)) from exc


# ---------------------------------------------------------------------------
# Restore execution gate
# ---------------------------------------------------------------------------


def _restore_execution_allowed(*, is_debug: bool = False) -> bool:
    """Return whether destructive restore execution is permitted.

    When *is_debug* is *True* (the Django ``settings.DEBUG`` equivalent),
    execution is always allowed.  Otherwise the
    ``QUICKSCALE_BACKUPS_ALLOW_RESTORE`` environment variable must be set to
    ``"true"``.
    """
    if is_debug:
        return True
    return os.getenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", "").strip().lower() == "true"


# ---------------------------------------------------------------------------
# Restore source resolution
# ---------------------------------------------------------------------------


@contextmanager
def _resolve_restore_source(
    *,
    artifact: ArtifactLike | None = None,
    file_path: str | Path | None = None,
    snapshot_id: str | None = None,
    resolution_mode: RestoreSourceResolutionMode = RestoreSourceResolutionMode.REMOTE_FALLBACK,
    remote_materializer: RemoteMaterializer | None = None,
    snapshot_resolver: Callable[[str], ArtifactLike] | None = None,
    policy_resolver: Callable[[ArtifactLike], Any] | None = None,
) -> Iterator[ResolvedRestoreSource]:
    """Resolve one restore source into a local file path for the guarded pipeline.

    Parameters
    ----------
    artifact:
        A resolved artifact (or artifact-like) instance.
    file_path:
        Operator-supplied file path for direct restore.
    snapshot_id:
        Snapshot identifier, resolved via *snapshot_resolver*.
    resolution_mode:
        Whether remote materialization is allowed as a fallback.
    remote_materializer:
        Callable that materialises a remote key to a local path.
    snapshot_resolver:
        Callable that resolves a *snapshot_id* to an ``ArtifactLike``.
    policy_resolver:
        Callable that resolves the remote-storage policy for an artifact.

    Exactly one of *artifact*, *file_path*, or *snapshot_id* must be
    provided.
    """
    provided_source_count = sum(
        source is not None for source in (artifact, file_path, snapshot_id)
    )
    if provided_source_count != 1:
        raise BackupRestoreBlocked(
            "Choose exactly one restore source: an artifact id, "
            "--snapshot-id, or --file PATH."
        )

    # File path branch — pure path resolution, no Django needed.
    if file_path is not None:
        resolved_path = _normalize_restore_file_path(file_path)
        yield ResolvedRestoreSource(
            confirmation_value=resolved_path.name,
            local_path=resolved_path,
            backup_format=_detect_restore_file_format(resolved_path),
        )
        return

    # Snapshot id branch — delegate to the caller-provided resolver.
    if snapshot_id is not None:
        if snapshot_resolver is None:
            raise BackupRestoreBlocked(
                "Restore blocked because snapshot resolution is not available "
                "in this context."
            )
        artifact = snapshot_resolver(snapshot_id)

    # Artifact branch — local path or remote materialization.
    assert artifact is not None
    local_path = Path(artifact.local_path) if artifact.local_path else None
    if local_path is not None and local_path.exists():
        yield ResolvedRestoreSource(
            confirmation_value=artifact.filename,
            local_path=local_path,
            backup_format=artifact.backup_format,
            artifact=artifact,
        )
        return

    if resolution_mode == RestoreSourceResolutionMode.LOCAL_ONLY:
        raise BackupRestoreBlocked(
            "Restore blocked because the local backup artifact is missing and "
            "this restore source resolution mode does not allow private remote "
            "materialization."
        )

    if not artifact.remote_key:
        raise BackupRestoreBlocked(
            "Restore blocked because the local backup artifact is missing and no "
            "private remote artifact is available."
        )

    if remote_materializer is None:
        raise BackupRestoreBlocked(
            "Restore blocked because private remote materialization is not "
            "available in this context."
        )

    policy: Any = None
    if policy_resolver is not None:
        policy = policy_resolver(artifact)

    with TemporaryDirectory(prefix="quickscale-backups-restore-") as temp_dir:
        materialized_path = Path(temp_dir) / artifact.filename
        try:
            remote_materializer(artifact.remote_key, policy, materialized_path)
        except BackupError as exc:
            raise BackupRestoreBlocked(
                "Restore blocked because private remote materialization failed for "
                f"{artifact.filename}: {exc}"
            ) from exc
        except Exception as exc:
            raise BackupRestoreBlocked(
                "Restore blocked because private remote materialization failed for "
                f"{artifact.filename}: {exc}"
            ) from exc

        if not materialized_path.exists():
            raise BackupRestoreBlocked(
                "Restore blocked because private remote materialization did not "
                f"produce a local file for {artifact.filename}."
            )

        yield ResolvedRestoreSource(
            confirmation_value=artifact.filename,
            local_path=materialized_path,
            backup_format=artifact.backup_format,
            artifact=artifact,
        )


# ---------------------------------------------------------------------------
# Restore execution pipeline
# ---------------------------------------------------------------------------


def _execute_restore_for_resolved_source(
    restore_source: ResolvedRestoreSource,
    *,
    confirmation: str,
    dry_run: bool,
    allow_production: bool,
    shell_runner: ShellCommandRunner | None = None,
    current_engine: str | None = None,
    connection_settings: dict[str, Any] | None = None,
    is_debug: bool = False,
    pg_contract_checker: Callable[..., Any] | None = None,
) -> RestoreResult:
    """Run the guarded restore pipeline for one resolved restore source.

    This is the Django-free core that combines validation, compatibility
    checks, the execution gate, and the ``pg_restore`` call.

    Parameters
    ----------
    restore_source:
        Resolved restore source from ``_resolve_restore_source``.
    confirmation:
        Operator-supplied confirmation value that must match the source name.
    dry_run:
        When *True* run validation checks only without executing restore.
    allow_production:
        When *True* record explicit destructive-restore intent (the env-var
        gate still applies outside ``DEBUG`` mode).
    shell_runner:
        Optional shell command runner override.
    current_engine:
        The current database engine string (e.g.
        ``"django.db.backends.postgresql"``).  Pass *None* to skip
        engine-specific compatibility and runtime checks.
    connection_settings:
        Database connection parameters for ``pg_restore`` (e.g. ``HOST``,
        ``PORT``, ``USER``, ``NAME``, ``PASSWORD``).  Required when
        *dry_run* is *False* and a PostgreSQL restore must execute.
    is_debug:
        When *True* bypass the ``QUICKSCALE_BACKUPS_ALLOW_RESTORE``
        environment-variable gate (callers should pass ``True`` only in
        local development contexts).
    pg_contract_checker:
        Optional callable that enforces the PostgreSQL 18 server and client
        tooling contract.  When *None* only the engine-family check runs; the
        Django-backed caller should provide
        ``_require_postgresql_18_contract`` to enforce full version
        requirements.
    """
    if confirmation.strip() != restore_source.confirmation_value:
        raise BackupRestoreBlocked(
            "Confirmation must exactly match the backup filename."
        )

    if restore_source.is_export_only():
        if restore_source.artifact is None:
            raise BackupRestoreBlocked(
                "Restore blocked because JSON file inputs are not a supported "
                "restore input."
            )
        raise BackupRestoreBlocked(
            "Restore blocked because export_only artifacts are not a supported "
            "restore input."
        )

    source_issues = _get_restore_source_validation_issues(restore_source)
    if source_issues:
        raise BackupRestoreBlocked(
            "Restore blocked because backup validation failed: "
            + "; ".join(source_issues)
        )

    resolved_engine = (current_engine or "").strip()
    compatibility_issues: list[str] = []
    if resolved_engine:
        compatibility_issues = _get_restore_source_compatibility_issues(
            restore_source,
            resolved_engine,
        )
    if compatibility_issues:
        compatibility_prefix = (
            "Restore blocked because artifact compatibility validation failed: "
            if restore_source.artifact is not None
            else "Restore blocked because restore compatibility validation failed: "
        )
        raise BackupRestoreBlocked(
            compatibility_prefix + "; ".join(compatibility_issues)
        )

    if dry_run:
        if resolved_engine:
            _ensure_postgresql_18_restore_runtime(
                resolved_engine,
                require_contract=pg_contract_checker,
            )
        _ensure_operator_supplied_custom_archive_valid(
            restore_source,
            shell_runner=shell_runner,
        )
        return RestoreResult(
            executed=False,
            dry_run=True,
            message="Restore validation completed successfully (dry run).",
        )

    if not _restore_execution_allowed(is_debug=is_debug):
        message = (
            "Restore execution is blocked outside local development until "
            "QUICKSCALE_BACKUPS_ALLOW_RESTORE=true is set."
        )
        if allow_production:
            message += " --allow-production does not bypass this environment gate."
        raise BackupRestoreBlocked(message)

    if restore_source.backup_format != "pg_dump_custom":
        raise BackupRestoreBlocked(
            "Executable restore is only supported for PostgreSQL custom-format "
            "artifacts. Use --dry-run for JSON fallback backups."
        )

    if resolved_engine:
        _ensure_postgresql_18_restore_runtime(
            resolved_engine,
            require_contract=pg_contract_checker,
        )
    _ensure_operator_supplied_custom_archive_valid(
        restore_source,
        shell_runner=shell_runner,
    )

    command, env = _build_pg_restore_command(
        restore_source.local_path,
        connection_settings or {},
    )
    runner = shell_runner or _run_shell_command
    runner(command, env=env)

    return RestoreResult(
        executed=True,
        dry_run=False,
        message=f"Restore executed for {restore_source.confirmation_value}.",
    )
