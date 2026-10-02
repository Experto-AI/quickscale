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

import quickscale_core.dr_engine.orchestration as _orchestration


def _get_source_environment() -> str:
    """Return the active QuickScale environment name with a conservative default."""
    return os.getenv("QUICKSCALE_ENVIRONMENT", "local").strip() or "local"


def _get_project_slug() -> str:
    base_dir = Path(getattr(_orchestration.settings, "BASE_DIR", Path.cwd()))
    candidate = base_dir.name.strip()
    if candidate:
        return candidate
    return str(_orchestration.settings.ROOT_URLCONF.split(".", maxsplit=1)[0])


def _collect_module_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for app_config in apps.get_app_configs():
        if not app_config.name.startswith("quickscale_modules_"):
            continue
        try:
            package = _orchestration.import_module(app_config.name)
        except Exception:  # noqa: S112 - best-effort inventory; an unimportable module is omitted
            continue
        versions[app_config.name] = str(getattr(package, "__version__", "unknown"))
    return versions


def _get_git_revision() -> str | None:
    """Return the best-effort current git revision for release metadata."""
    base_dir = Path(getattr(_orchestration.settings, "BASE_DIR", Path.cwd()))
    try:
        result = _orchestration.subprocess.run(
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
        _orchestration._StorageHelpersModule,
        _orchestration.import_module("quickscale_modules_storage.services"),
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
        "manifest_version": 1,
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        "project_slug": _orchestration._get_project_slug(),
        "source_environment": _orchestration._get_source_environment(),
        "status": "ready",
        "app_version": str(
            getattr(_orchestration.settings, "QUICKSCALE_APP_VERSION", "unknown")
        ),
        "django_version": _orchestration.django.get_version(),
        "module_versions": _orchestration._collect_module_versions(),
        "git_sha": _orchestration._get_git_revision(),
    }


def _create_database_dump(
    engine: str,
    resolved_policy: BackupPolicySnapshot,
    *,
    shell_runner: ShellCommandRunner | None,
    now: datetime,
    database_directory: Path,
    operation: str = "backup creation",
) -> tuple[Path, str, str, str | None, int | None, str | None, int | None]:
    """Create a database dump and return structured dump metadata.

    Returns (local_path, backup_format, filename, database_server_version,
    database_server_major, dump_client_version, dump_client_major).
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
        ) = _orchestration._require_postgresql_18_contract(
            database_engine=engine,
            executable="pg_dump",
            operation=operation,
        )
        backup_format = "pg_dump_custom"
        filename = _orchestration.build_backup_filename(
            resolved_policy,
            now=now,
            suffix="dump",
        )
        local_path = database_directory / filename
        _orchestration._dump_postgresql_database(
            local_path,
            _orchestration.django.db.connections["default"].settings_dict,
            shell_runner=shell_runner,
        )
    else:
        backup_format = "json"
        filename = _orchestration.build_backup_filename(
            resolved_policy,
            now=now,
            suffix="json",
        )
        local_path = database_directory / filename
        _orchestration._dump_database_as_json(local_path)

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
    local_path.write_text(buffer.getvalue(), encoding="utf-8")


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
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
        "backup_format": backup_format,
        "database_engine": database_engine,
        "database_name": database_name,
        "django_version": _orchestration.django.get_version(),
        "environment": os.getenv("QUICKSCALE_ENVIRONMENT", "local") or "local",
        "target_mode": target_mode,
        "module_versions": _orchestration._collect_module_versions(),
        "app_version": str(
            getattr(_orchestration.settings, "QUICKSCALE_APP_VERSION", "unknown")
        ),
    }
    resolved_database_server_version = database_server_version
    if resolved_database_server_version is None:
        resolved_database_server_version = _orchestration._get_database_server_version(
            database_engine
        )
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
    version_query = _orchestration._database_server_version_query(engine)
    if version_query is None:
        return None

    connection = _orchestration.django.db.connections["default"]
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
    engine_family = _orchestration._database_engine_family(engine)
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
    if _orchestration._database_engine_family(database_engine) != "postgresql":
        raise _orchestration.BackupConfigurationError(
            "PostgreSQL contract checks require DATABASES['default']['ENGINE'] to "
            "use PostgreSQL."
        )

    database_server_version = _orchestration._get_database_server_version(
        database_engine
    )
    if database_server_version is None:
        raise _orchestration.BackupError(
            "PostgreSQL "
            f"{operation} requires a PostgreSQL {_orchestration._REQUIRED_POSTGRESQL_MAJOR} "
            "server, but the current server version could not be determined."
        )
    database_server_major = _orchestration._extract_leading_major_version(
        database_server_version
    )
    if database_server_major is None:
        raise _orchestration.BackupError(
            "PostgreSQL "
            f"{operation} requires a PostgreSQL {_orchestration._REQUIRED_POSTGRESQL_MAJOR} "
            "server, but the current server version could not be determined."
        )
    if database_server_major != _orchestration._REQUIRED_POSTGRESQL_MAJOR:
        raise _orchestration.BackupError(
            "PostgreSQL "
            f"{operation} requires a PostgreSQL {_orchestration._REQUIRED_POSTGRESQL_MAJOR} "
            f"server, found '{database_server_version}'."
        )

    tool_version = _orchestration._get_postgresql_tool_version(executable)
    tool_major = _orchestration._extract_any_major_version(tool_version)
    if tool_major is None:
        raise _orchestration.BackupError(
            "PostgreSQL "
            f"{operation} requires PostgreSQL {_orchestration._REQUIRED_POSTGRESQL_MAJOR} "
            f"{executable} tooling, but the installed tool version could not be "
            "determined." + _orchestration._get_postgresql_18_guidance()
        )
    if tool_major != _orchestration._REQUIRED_POSTGRESQL_MAJOR:
        raise _orchestration.BackupError(
            "PostgreSQL "
            f"{operation} requires PostgreSQL {_orchestration._REQUIRED_POSTGRESQL_MAJOR} "
            f"{executable} tooling, found '{tool_version}'."
            + _orchestration._get_postgresql_18_guidance()
        )

    return database_server_version, database_server_major, tool_version, tool_major


def _get_postgresql_18_guidance() -> str:
    """Return operator guidance for the PostgreSQL 18 client-tooling contract."""
    from quickscale_core.dr_engine.primitives import (
        _postgresql_18_client_tooling_guidance as _guidance,
    )

    return _guidance()
