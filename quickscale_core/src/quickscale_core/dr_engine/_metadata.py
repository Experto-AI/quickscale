"""Backup metadata, environment, and database dump helpers."""

from __future__ import annotations


from datetime import datetime
from datetime import timezone
from django.apps import apps
from django.core.management import call_command
from io import StringIO
from pathlib import Path
from quickscale_core.dr_engine._types import _StorageHelpersModule
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot
from quickscale_core.dr_engine.primitives import ShellCommandRunner
from typing import Any
from typing import cast
import os


import quickscale_core.dr_engine._connection as _connection
import quickscale_core.dr_engine._types as _types
import quickscale_core.dr_engine.primitives as _primitives
import django.conf as _conf
import importlib as _importlib
import quickscale_core.dr_engine._paths as _paths
import quickscale_core.migration_hashes as _migration_hashes
import stat
import subprocess
import django


def _get_source_environment() -> str:
    """Return the active QuickScale environment name with a conservative default."""
    return os.getenv("QUICKSCALE_ENVIRONMENT", "local").strip() or "local"


def _get_project_slug() -> str:
    base_dir = Path(getattr(_conf.settings, "BASE_DIR", Path.cwd()))
    candidate = base_dir.name.strip()
    if candidate:
        return candidate
    return str(_conf.settings.ROOT_URLCONF.split(".", maxsplit=1)[0])


def _collect_module_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for app_config in apps.get_app_configs():
        if not app_config.name.startswith("quickscale_modules_"):
            continue
        try:
            package = _importlib.import_module(app_config.name)
        except Exception:  # noqa: S112 - best-effort inventory; an unimportable module is omitted
            continue
        versions[app_config.name] = str(getattr(package, "__version__", "unknown"))
    return versions


def _collect_module_migration_hashes() -> dict[str, dict[str, str]]:
    """Return each installed module's applied-migration content identity.

    One key per installed QuickScale module, mirroring
    :func:`_collect_module_versions`, so a service module's empty mapping stays
    distinguishable from a module the backup does not record.  A module whose
    migration files cannot be hashed fails the capture rather than recording a
    weaker identity.
    """
    hashes: dict[str, dict[str, str]] = {}
    for app_config in apps.get_app_configs():
        if not app_config.name.startswith("quickscale_modules_"):
            continue
        migrations_dir = Path(app_config.path) / "migrations"
        try:
            is_directory = stat.S_ISDIR(migrations_dir.stat().st_mode)
        except FileNotFoundError:
            hashes[app_config.name] = {}
            continue
        except OSError as exc:
            raise _primitives.BackupConfigurationError(
                "Unable to inspect the migrations package for module "
                f"'{app_config.name}': {exc}"
            ) from exc
        if not is_directory:
            raise _primitives.BackupConfigurationError(
                f"Module '{app_config.name}' has a migrations path that is not a directory"
            )
        try:
            hashes[app_config.name] = _migration_hashes.compute_migration_hashes(
                migrations_dir
            )
        except (_migration_hashes.MigrationHashError, OSError) as exc:
            raise _primitives.BackupConfigurationError(
                "Unable to record the migration content identity for module "
                f"'{app_config.name}': {exc}"
            ) from exc
    return hashes


_PROJECT_APP_EXCLUDED_PATH_PARTS: frozenset[str] = frozenset(
    {"site-packages", "dist-packages"}
)


def _is_project_owned_app(app_config: Any) -> bool:
    """Return whether an installed app belongs to the project's own code tree."""
    name = str(getattr(app_config, "name", "")).strip()
    if not name or name.startswith("quickscale_modules_") or name.startswith("django."):
        return False
    path_text = str(getattr(app_config, "path", "") or "").strip()
    if not path_text:
        return False
    path = Path(path_text)
    if _PROJECT_APP_EXCLUDED_PATH_PARTS.intersection(path.parts):
        return False
    base_dir = Path(getattr(_conf.settings, "BASE_DIR", Path.cwd())).resolve()
    try:
        path.resolve().relative_to(base_dir)
    except ValueError:
        return False
    return True


def _collect_project_migration_hashes() -> dict[str, dict[str, str]]:
    """Return each project-owned app's applied-migration content identity.

    A project app records one key by app label, including an empty mapping for
    an app that ships no migrations.  An unreadable or empty migrations
    package fails the capture rather than recording a weaker identity.
    """
    hashes: dict[str, dict[str, str]] = {}
    for app_config in apps.get_app_configs():
        if not _is_project_owned_app(app_config):
            continue
        app_label = str(getattr(app_config, "label", "") or app_config.name)
        migrations_dir = Path(app_config.path) / "migrations"
        try:
            is_directory = stat.S_ISDIR(migrations_dir.stat().st_mode)
        except FileNotFoundError:
            hashes[app_label] = {}
            continue
        except OSError as exc:
            raise _primitives.BackupConfigurationError(
                "Unable to inspect the migrations package for project app "
                f"'{app_label}': {exc}"
            ) from exc
        if not is_directory:
            raise _primitives.BackupConfigurationError(
                f"Project app '{app_label}' has a migrations path that is not a directory"
            )
        try:
            numbered_migrations = [
                path
                for path in migrations_dir.iterdir()
                if path.is_file()
                and _migration_hashes.NUMBERED_MIGRATION_PATTERN.match(path.name)
            ]
        except OSError as exc:
            raise _primitives.BackupConfigurationError(
                "Unable to inspect the migrations package for project app "
                f"'{app_label}': {exc}"
            ) from exc
        if not numbered_migrations:
            hashes[app_label] = {}
            continue
        try:
            hashes[app_label] = _migration_hashes.compute_migration_hashes(
                migrations_dir
            )
        except (_migration_hashes.MigrationHashError, OSError) as exc:
            raise _primitives.BackupConfigurationError(
                "Unable to record the migration content identity for project app "
                f"'{app_label}': {exc}"
            ) from exc
    return hashes


def _get_git_revision() -> str | None:
    """Return the best-effort current git revision for release metadata."""
    base_dir = Path(getattr(_conf.settings, "BASE_DIR", Path.cwd()))
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - PATH-resolved executable by design
            capture_output=True,
            check=False,
            text=True,
            cwd=base_dir,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    revision = result.stdout.strip()
    return revision or None


def _load_storage_helpers() -> _StorageHelpersModule:
    """Load storage's public service module behind a typed local boundary."""
    return cast(
        _types._StorageHelpersModule,
        _importlib.import_module("quickscale_modules_storage.services"),
    )


def _read_setting_value(
    settings_obj: Any,
    key: str,
    default: Any,
) -> Any:
    """Read one setting key from a Django settings object or plain mapping."""
    if isinstance(settings_obj, dict):
        return settings_obj.get(key, default)
    return getattr(settings_obj, key, default)


def _build_release_metadata(*, captured_at: datetime) -> dict[str, Any]:
    """Capture release metadata reserved for later snapshot-aware CLI phases."""
    return {
        "manifest_version": _primitives._BACKUP_MANIFEST_VERSION,
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        "project_slug": _get_project_slug(),
        "source_environment": _get_source_environment(),
        "status": "ready",
        "app_version": str(
            getattr(_conf.settings, "QUICKSCALE_APP_VERSION", "unknown")
        ),
        "django_version": django.get_version(),
        "module_versions": _collect_module_versions(),
        "migration_hashes": _collect_module_migration_hashes(),
        "project_migration_hashes": _collect_project_migration_hashes(),
        "git_sha": _get_git_revision(),
    }


def _create_database_dump(
    engine: str,
    resolved_policy: BackupPolicySnapshot,
    *,
    shell_runner: ShellCommandRunner | None,
    now: datetime,
    database_directory: Path,
    operation: str = "backup creation",
    backup_connection: _connection.ResolvedBackupConnection | None = None,
) -> tuple[Path, str, str, str | None, int | None, str | None, int | None]:
    """Create a database dump and return structured dump metadata.

    Returns (local_path, backup_format, filename, database_server_version,
    database_server_major, dump_client_version, dump_client_major).

    A PostgreSQL dump runs under the resolved privileged backup connection,
    never under Django's restricted serving role.
    """
    database_server_version: str | None = None
    database_server_major: int | None = None
    dump_client_version: str | None = None
    dump_client_major: int | None = None

    if "postgresql" in engine:
        (
            database_server_version,
            database_server_major,
            dump_client_version,
            dump_client_major,
        ) = _require_postgresql_18_contract(
            database_engine=engine,
            executable="pg_dump",
            operation=operation,
        )
        if backup_connection is None:
            backup_connection = _connection._resolve_backup_connection(
                django.db.connections["default"].settings_dict
            )
            _connection._ensure_backup_connection_is_privileged(
                backup_connection,
                operation="capture",
            )
        resolved_connection = backup_connection
        backup_format = "pg_dump_custom"
        filename = _paths.build_backup_filename(
            resolved_policy,
            now=now,
            suffix="dump",
        )
        local_path = database_directory / filename
        _primitives._dump_postgresql_database(
            local_path,
            resolved_connection.settings,
            shell_runner=shell_runner,
        )
        _primitives._ensure_private_file(local_path)
    else:
        backup_format = "json"
        filename = _paths.build_backup_filename(
            resolved_policy,
            now=now,
            suffix="json",
        )
        local_path = database_directory / filename
        _dump_database_as_json(local_path)

    return (
        local_path,
        backup_format,
        filename,
        database_server_version,
        database_server_major,
        dump_client_version,
        dump_client_major,
    )


def _dump_database_as_json(local_path: Path) -> None:
    buffer = StringIO()
    call_command("dumpdata", stdout=buffer)
    _primitives._ensure_private_directory(local_path.parent)
    local_path.write_text(buffer.getvalue(), encoding="utf-8")
    _primitives._ensure_private_file(local_path)


def _build_backup_metadata(
    *,
    created_at: datetime,
    backup_format: str,
    database_engine: str,
    database_name: str,
    target_mode: str,
    database_server_version: str | None = None,
    database_server_major: int | None = None,
    dump_client_version: str | None = None,
    dump_client_major: int | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "manifest_version": _primitives._BACKUP_MANIFEST_VERSION,
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
        "backup_format": backup_format,
        "database_engine": database_engine,
        "database_name": database_name,
        "django_version": django.get_version(),
        "environment": os.getenv("QUICKSCALE_ENVIRONMENT", "local") or "local",
        "target_mode": target_mode,
        "module_versions": _collect_module_versions(),
        "migration_hashes": _collect_module_migration_hashes(),
        "project_migration_hashes": _collect_project_migration_hashes(),
        "app_version": str(
            getattr(_conf.settings, "QUICKSCALE_APP_VERSION", "unknown")
        ),
    }
    resolved_database_server_version = database_server_version
    if resolved_database_server_version is None:
        resolved_database_server_version = _get_database_server_version(database_engine)
    if resolved_database_server_version is not None:
        metadata["database_server_version"] = resolved_database_server_version
    if database_server_major is not None:
        metadata["database_server_major"] = database_server_major
    if dump_client_version is not None:
        metadata["pg_dump_version"] = dump_client_version
    if dump_client_major is not None:
        metadata["dump_client_major"] = dump_client_major
    return metadata


def _get_database_server_version(engine: str) -> str | None:
    """Return best-effort database server version metadata for the active backend."""
    version_query = _database_server_version_query(engine)
    if version_query is None:
        return None

    connection = django.db.connections["default"]
    try:
        with connection.cursor() as cursor:
            cursor.execute(version_query)
            row = cursor.fetchone()
    except Exception:
        return None

    if not row:
        return None

    database_server_version = str(row[0]).strip()
    return database_server_version or None


def _database_server_version_query(engine: str) -> str | None:
    """Return a read-only version query for supported backup backends."""
    engine_family = _primitives._database_engine_family(engine)
    if engine_family == "postgresql":
        return "SHOW server_version"
    if engine_family == "sqlite":
        return "SELECT sqlite_version()"
    return None


def _require_postgresql_18_contract(
    database_engine: str,
    executable: str,
    operation: str,
) -> tuple[str, int, str, int]:
    """Require a PostgreSQL 18 server plus PostgreSQL 18 client tooling."""
    if _primitives._database_engine_family(database_engine) != "postgresql":
        raise _primitives.BackupConfigurationError(
            "PostgreSQL contract checks require DATABASES['default']['ENGINE'] to "
            "use PostgreSQL."
        )

    database_server_version = _get_database_server_version(database_engine)
    if database_server_version is None:
        raise _primitives.BackupError(
            "PostgreSQL "
            f"{operation} requires a PostgreSQL {_primitives._REQUIRED_POSTGRESQL_MAJOR} "
            "server, but the current server version could not be determined."
        )
    database_server_major = _primitives._extract_leading_major_version(
        database_server_version
    )
    if database_server_major is None:
        raise _primitives.BackupError(
            "PostgreSQL "
            f"{operation} requires a PostgreSQL {_primitives._REQUIRED_POSTGRESQL_MAJOR} "
            "server, but the current server version could not be determined."
        )
    if database_server_major != _primitives._REQUIRED_POSTGRESQL_MAJOR:
        raise _primitives.BackupError(
            "PostgreSQL "
            f"{operation} requires a PostgreSQL {_primitives._REQUIRED_POSTGRESQL_MAJOR} "
            f"server, found '{database_server_version}'."
        )

    tool_version = _primitives._get_postgresql_tool_version(executable)
    tool_major = _primitives._extract_any_major_version(tool_version)
    if tool_major is None:
        raise _primitives.BackupError(
            "PostgreSQL "
            f"{operation} requires PostgreSQL {_primitives._REQUIRED_POSTGRESQL_MAJOR} "
            f"{executable} tooling, but the installed tool version could not be "
            "determined." + _get_postgresql_18_guidance()
        )
    if tool_major != _primitives._REQUIRED_POSTGRESQL_MAJOR:
        raise _primitives.BackupError(
            "PostgreSQL "
            f"{operation} requires PostgreSQL {_primitives._REQUIRED_POSTGRESQL_MAJOR} "
            f"{executable} tooling, found '{tool_version}'."
            + _get_postgresql_18_guidance()
        )

    return database_server_version, database_server_major, tool_version, tool_major


def _get_postgresql_18_guidance() -> str:
    """Return operator guidance for the PostgreSQL 18 client-tooling contract."""
    from quickscale_core.dr_engine.primitives import (
        _postgresql_18_client_tooling_guidance as _guidance,
    )

    return _guidance()
