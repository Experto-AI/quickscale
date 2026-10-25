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
from typing import Any, Callable, Iterator, Mapping, Protocol

from quickscale_core.dr_engine.primitives import (
    BackupError,
    ShellCommandRunner,
    _POSTGRESQL_CUSTOM_ARCHIVE_MAGIC,
    _REQUIRED_POSTGRESQL_MAJOR,
    _build_pg_restore_command,
    _compute_sha256,
    _SUPPORTED_BACKUP_MANIFEST_VERSIONS,
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
    metadata_json: dict[str, Any]

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


def _collect_metadata_migration_hashes(
    metadata: Any,
    key: str,
    *,
    allow_empty: bool = False,
) -> dict[str, dict[str, str]] | None:
    """Return one recorded migration content identity from capture metadata.

    Absent or malformed metadata returns ``None`` so the restore guard fails
    closed.  An empty mapping is refused unless *allow_empty* is set, which a
    project identity uses to record a capture with no project-owned apps.
    """
    recorded_hashes = metadata.get(key) if isinstance(metadata, dict) else None
    if not isinstance(recorded_hashes, dict):
        return None
    if not recorded_hashes and not allow_empty:
        return None
    if any(not isinstance(files, dict) for files in recorded_hashes.values()):
        return None
    return {
        str(name): {str(filename): str(digest) for filename, digest in files.items()}
        for name, files in recorded_hashes.items()
    }


def _collect_artifact_migration_hashes(
    artifact: ArtifactLike,
) -> dict[str, dict[str, str]] | None:
    """Return the artifact's recorded module migration content identity, if any.

    Absent, empty, or malformed capture metadata returns ``None`` so the
    restore guard fails closed on a version label alone.
    """
    return _collect_metadata_migration_hashes(
        getattr(artifact, "metadata_json", None),
        "migration_hashes",
    )


def _collect_artifact_project_migration_hashes(
    artifact: ArtifactLike,
) -> dict[str, dict[str, str]] | None:
    """Return the artifact's recorded project-app migration identity, if any."""
    return _collect_metadata_migration_hashes(
        getattr(artifact, "metadata_json", None),
        "project_migration_hashes",
        allow_empty=True,
    )


def _collect_artifact_manifest_version(artifact: ArtifactLike) -> int | None:
    """Return the artifact's recorded format version, if it is well formed."""
    metadata = getattr(artifact, "metadata_json", None)
    version = metadata.get("manifest_version") if isinstance(metadata, dict) else None
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    return version


def _get_migration_content_issues(
    recorded_migration_hashes: Mapping[str, Mapping[str, str]] | None,
    installed_migration_hashes: Mapping[str, Mapping[str, str]],
    *,
    allow_forward: bool = False,
) -> list[str]:
    """Return refusal issues for a recorded migration content identity.

    Every recorded migration file must still be installed byte-identical;
    installed modules may carry newer migrations for ``migrate`` to apply,
    which only a caller passing *allow_forward* may accept.  An identity
    holding no file hashes at all is always refused.
    """
    if not recorded_migration_hashes or not any(recorded_migration_hashes.values()):
        return ["backup records no migration content identity"]

    differences: list[str] = []
    forward_differences: list[str] = []
    module_names = set(recorded_migration_hashes) | set(installed_migration_hashes)
    for module_name in sorted(module_names):
        recorded_files = recorded_migration_hashes.get(module_name, {})
        installed_files = installed_migration_hashes.get(module_name, {})
        for filename in sorted(set(recorded_files) | set(installed_files)):
            recorded_digest = recorded_files.get(filename)
            installed_digest = installed_files.get(filename)
            if recorded_digest is None:
                forward_differences.append(
                    f"{module_name} installed migration '{filename}' is newer"
                )
            elif installed_digest is None:
                differences.append(
                    f"{module_name} recorded migration '{filename}' is not installed"
                )
            elif installed_digest != recorded_digest:
                differences.append(f"{module_name} migration '{filename}' changed")
    if differences:
        return ["backup migration content cannot advance: " + "; ".join(differences)]
    if forward_differences and not allow_forward:
        return [
            "backup migration content is behind the installed modules and this"
            " restore does not complete the forward migration: "
            + "; ".join(forward_differences)
        ]
    return []


def _get_project_migration_content_issues(
    recorded_migration_hashes: Mapping[str, Mapping[str, str]],
    installed_migration_hashes: Mapping[str, Mapping[str, str]],
    *,
    allow_forward: bool = False,
) -> list[str]:
    """Return refusal issues for a recorded project-app migration identity.

    An empty recorded mapping is a valid capture with no project-owned apps;
    an app added after capture is a forward difference.  Every recorded
    migration file must still be installed byte-identical.
    """
    differences: list[str] = []
    forward_differences: list[str] = []
    app_labels = set(recorded_migration_hashes) | set(installed_migration_hashes)
    for app_label in sorted(app_labels):
        recorded_files = recorded_migration_hashes.get(app_label, {})
        installed_files = installed_migration_hashes.get(app_label, {})
        for filename in sorted(set(recorded_files) | set(installed_files)):
            recorded_digest = recorded_files.get(filename)
            installed_digest = installed_files.get(filename)
            if recorded_digest is None:
                forward_differences.append(
                    f"{app_label} installed migration '{filename}' is newer"
                )
            elif installed_digest is None:
                differences.append(
                    f"{app_label} recorded migration '{filename}' is not installed"
                )
            elif installed_digest != recorded_digest:
                differences.append(f"{app_label} migration '{filename}' changed")
    if differences:
        return [
            "backup project migration content cannot advance: " + "; ".join(differences)
        ]
    if forward_differences and not allow_forward:
        return [
            "backup project migration content is behind the installed project apps"
            " and this restore does not complete the forward migration: "
            + "; ".join(forward_differences)
        ]
    return []


def _get_manifest_identity_issues(
    recorded_manifest_version: int | None,
    recorded_project_migration_hashes: Mapping[str, Mapping[str, str]] | None,
    installed_project_migration_hashes: Mapping[str, Mapping[str, str]],
    *,
    allow_forward: bool = False,
) -> list[str]:
    """Return refusal issues for the artifact manifest identity.

    Unknown or missing format versions fail closed, and so does a manifest
    that records no project identity at all.
    """
    if recorded_manifest_version is None:
        return ["backup manifest records no format version"]
    if recorded_manifest_version not in _SUPPORTED_BACKUP_MANIFEST_VERSIONS:
        return [
            f"backup manifest version '{recorded_manifest_version}' is not supported"
        ]
    if recorded_project_migration_hashes is None:
        return ["backup manifest records no project migration content identity"]
    return _get_project_migration_content_issues(
        recorded_project_migration_hashes,
        installed_project_migration_hashes,
        allow_forward=allow_forward,
    )


def _get_restore_source_migration_issues(
    restore_source: ResolvedRestoreSource,
    installed_migration_hashes: Mapping[str, Mapping[str, str]],
    *,
    recorded_migration_hashes: Mapping[str, Mapping[str, str]] | None = None,
    allow_forward: bool = False,
) -> list[str]:
    """Return migration-content refusal issues for the resolved restore source.

    Artifact-backed sources compare the artifact's recorded capture metadata; a
    source with no artifact row is compared only when the caller carries the
    recorded hashes in — a bare file that records none is refused.
    """
    if restore_source.artifact is not None:
        recorded_migration_hashes = _collect_artifact_migration_hashes(
            restore_source.artifact
        )
    return _get_migration_content_issues(
        recorded_migration_hashes,
        installed_migration_hashes,
        allow_forward=allow_forward,
    )


def _get_restore_compatibility_issues(
    artifact: ArtifactLike,
    current_engine: str,
    *,
    installed_migration_hashes: Mapping[str, Mapping[str, str]] | None = None,
    installed_project_migration_hashes: Mapping[str, Mapping[str, str]] | None = None,
    allow_forward: bool = False,
) -> list[str]:
    """Return restore guardrail issues for current database engine compatibility.

    With *installed_migration_hashes* the recorded migration content identity
    must be able to advance under it; a changed, missing, or unrecorded entry
    is refused.  *installed_project_migration_hashes* enables the manifest
    version and project-app identity gate the same way.  The Django-backed
    restore path always supplies both.
    """
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

    if installed_migration_hashes is not None:
        issues.extend(
            _get_migration_content_issues(
                _collect_artifact_migration_hashes(artifact),
                installed_migration_hashes,
                allow_forward=allow_forward,
            )
        )
    if installed_project_migration_hashes is not None:
        issues.extend(
            _get_manifest_identity_issues(
                _collect_artifact_manifest_version(artifact),
                _collect_artifact_project_migration_hashes(artifact),
                installed_project_migration_hashes,
                allow_forward=allow_forward,
            )
        )

    return issues


def _get_restore_source_compatibility_issues(
    restore_source: ResolvedRestoreSource,
    current_engine: str,
    *,
    installed_migration_hashes: Mapping[str, Mapping[str, str]] | None = None,
    installed_project_migration_hashes: Mapping[str, Mapping[str, str]] | None = None,
    recorded_migration_hashes: Mapping[str, Mapping[str, str]] | None = None,
    recorded_manifest_version: int | None = None,
    recorded_project_migration_hashes: Mapping[str, Mapping[str, str]] | None = None,
    allow_forward: bool = False,
) -> list[str]:
    """Return compatibility issues for artifact and operator-supplied sources.

    With *installed_migration_hashes* the source's recorded migration content
    identity must be able to advance under it; *recorded_migration_hashes*
    carries that identity for a source that has no artifact row.
    *installed_project_migration_hashes* enables the manifest version and
    project-app identity gate, using the artifact's recorded manifest or the
    caller-supplied *recorded_manifest_version* and
    *recorded_project_migration_hashes* for a file source.
    """
    issues: list[str] = []
    if restore_source.artifact is not None:
        issues.extend(
            _get_restore_compatibility_issues(restore_source.artifact, current_engine)
        )
    elif _database_engine_family(current_engine) != "postgresql":
        issues.append(
            "operator-supplied restore files require a PostgreSQL target database"
        )

    if installed_migration_hashes is not None:
        issues.extend(
            _get_restore_source_migration_issues(
                restore_source,
                installed_migration_hashes,
                recorded_migration_hashes=recorded_migration_hashes,
                allow_forward=allow_forward,
            )
        )
    if installed_project_migration_hashes is not None:
        artifact = restore_source.artifact
        project_hashes: Mapping[str, Mapping[str, str]] | None
        if artifact is not None:
            manifest_version = _collect_artifact_manifest_version(artifact)
            project_hashes = _collect_artifact_project_migration_hashes(artifact)
        else:
            manifest_version = recorded_manifest_version
            project_hashes = recorded_project_migration_hashes
        issues.extend(
            _get_manifest_identity_issues(
                manifest_version,
                project_hashes,
                installed_project_migration_hashes,
                allow_forward=allow_forward,
            )
        )
    return issues


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
    assert artifact is not None  # noqa: S101 - internal invariant guaranteed by the caller
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
    installed_migration_hashes: Mapping[str, Mapping[str, str]] | None = None,
    installed_project_migration_hashes: Mapping[str, Mapping[str, str]] | None = None,
    recorded_migration_hashes: Mapping[str, Mapping[str, str]] | None = None,
    recorded_manifest_version: int | None = None,
    recorded_project_migration_hashes: Mapping[str, Mapping[str, str]] | None = None,
    allow_forward: bool = False,
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
    installed_migration_hashes:
        Migration content identity of the running code, per module.  When
        provided, an artifact whose recorded migration hashes cannot advance
        under it — or that records none — is refused before any destructive
        step.  The Django-backed restore path always supplies it.
    installed_project_migration_hashes:
        Migration content identity of the running code, per project-owned app.
        When provided, the artifact manifest's format version and recorded
        project identity are enforced the same way as the module identity.
    recorded_migration_hashes:
        Migration content identity recorded for a source that has no artifact
        row, such as a snapshot report restored by file path; a bare file that
        records none is refused.  Ignored for artifact-backed sources.
    recorded_manifest_version:
        Manifest format version recorded for a source that has no artifact row.
    recorded_project_migration_hashes:
        Project-app migration identity recorded for a source that has no
        artifact row.
    allow_forward:
        When *True* the caller completes the forward migration after the
        restore (the DR snapshot route); *False* requires exact content.
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
            installed_migration_hashes=installed_migration_hashes,
            installed_project_migration_hashes=installed_project_migration_hashes,
            recorded_migration_hashes=recorded_migration_hashes,
            recorded_manifest_version=recorded_manifest_version,
            recorded_project_migration_hashes=recorded_project_migration_hashes,
            allow_forward=allow_forward,
        )
    elif installed_migration_hashes is not None:
        compatibility_issues = _get_restore_source_migration_issues(
            restore_source,
            installed_migration_hashes,
            recorded_migration_hashes=recorded_migration_hashes,
            allow_forward=allow_forward,
        )
        if installed_project_migration_hashes is not None:
            artifact = restore_source.artifact
            compatibility_issues.extend(
                _get_manifest_identity_issues(
                    (
                        _collect_artifact_manifest_version(artifact)
                        if artifact is not None
                        else recorded_manifest_version
                    ),
                    (
                        _collect_artifact_project_migration_hashes(artifact)
                        if artifact is not None
                        else recorded_project_migration_hashes
                    ),
                    installed_project_migration_hashes,
                    allow_forward=allow_forward,
                )
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
