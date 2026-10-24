"""Privileged database connection resolution for backup capture and restore.

The generated runtime role is deliberately restricted (``NOSUPERUSER`` and
``NOBYPASSRLS``).  It cannot dump a FORCE-RLS tenant table, because ``pg_dump``
turns ``row_security`` off, and it cannot restore objects owned by the migration
role.  Backup operations therefore resolve their own privileged connection for
the one command that needs it instead of reusing Django's serving connection.

Resolution order for a PostgreSQL project:

1. ``QUICKSCALE_BACKUP_DATABASE_URL`` — an optional dedicated backup role.
2. ``DATABASE_URL`` — the superuser connection the deployment already uses for
   migrations and other privileged commands.
3. Django's default connection — accepted for SQLite and for a PostgreSQL role
   that is already privileged.

The resolved URL never enters Django's ``DATABASES`` and is never exported: it
reaches only the ``pg_dump``/``pg_restore`` child process.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from django.conf import settings as _django_settings
from django.db import connections as _django_connections

import quickscale_core.dr_engine.primitives as _primitives

_POSTGRESQL_ENGINE = "django.db.backends.postgresql"
_BACKUP_DATABASE_URL_ENV_VAR = "QUICKSCALE_BACKUP_DATABASE_URL"
_DATABASE_URL_ENV_VAR = "DATABASE_URL"

#: The URL parameters that become Django connection ``OPTIONS``.  The one
#: translation table in ``primitives`` owns the libpq environment variable each
#: one becomes, so a URL and a Django connection share one TLS posture.
_URL_OPTION_PARAMETERS = frozenset(_primitives._LIBPQ_OPTION_ENVIRONMENT_VARIABLES)

_URL_PARAMETERS = frozenset(
    {"user", "password", "dbname", "host", "port", *_URL_OPTION_PARAMETERS}
)

_NOT_OWNED_TABLE_COUNT_SQL = """
SELECT count(*)
FROM pg_catalog.pg_class AS relation
JOIN pg_catalog.pg_namespace AS namespace
  ON namespace.oid = relation.relnamespace
WHERE relation.relkind IN ('r', 'p')
  AND namespace.nspname NOT IN ('pg_catalog', 'information_schema')
  AND relation.relowner <> (
      SELECT role.oid FROM pg_catalog.pg_roles AS role
      WHERE role.rolname = current_user
  )
"""


@dataclass(frozen=True)
class ResolvedBackupConnection:
    """One resolved dump/restore connection and where it came from."""

    settings: dict[str, Any]
    url: str | None
    source: str


def _resolve_backup_connection(
    default_settings: Mapping[str, Any],
) -> ResolvedBackupConnection:
    """Resolve the connection the DR engine uses for dump and restore.

    A non-PostgreSQL project keeps its default connection.  A PostgreSQL
    project prefers an explicit backup URL, then the superuser ``DATABASE_URL``;
    the caller's privilege check decides whether the default connection is an
    acceptable last resort.
    """
    engine = str(default_settings.get("ENGINE") or "").strip()
    if _primitives._database_engine_family(engine) != "postgresql":
        return ResolvedBackupConnection(dict(default_settings), None, "default")

    for environment_variable in (
        _BACKUP_DATABASE_URL_ENV_VAR,
        _DATABASE_URL_ENV_VAR,
    ):
        database_url = _read_configuration_value(environment_variable)
        if database_url:
            return ResolvedBackupConnection(
                _postgresql_settings_from_url(
                    database_url,
                    environment_variable=environment_variable,
                ),
                database_url,
                environment_variable,
            )

    return ResolvedBackupConnection(dict(default_settings), None, "default")


def _postgresql_settings_from_url(
    database_url: str,
    *,
    environment_variable: str,
) -> dict[str, Any]:
    """Parse one libpq URL into the Django connection settings the tools use.

    ``psycopg2.extensions.parse_dsn`` is libpq's own parser, so a
    percent-encoded password, an IPv6 host, and ``?sslmode=require`` are read
    exactly as the application connection reads them.  A parameter the dump
    and restore commands cannot carry is refused rather than silently dropped.
    """
    try:
        from psycopg2 import ProgrammingError
        from psycopg2.extensions import parse_dsn
    except ImportError as exc:  # pragma: no cover - generated projects pin psycopg2
        raise _primitives.BackupConfigurationError(
            f"{environment_variable} requires psycopg2 to parse the connection URL."
        ) from exc

    try:
        parameters = parse_dsn(database_url)
    except (ProgrammingError, ValueError) as exc:
        raise _primitives.BackupConfigurationError(
            f"{environment_variable} is not a valid PostgreSQL connection URL: {exc}"
        ) from exc

    unsupported = sorted(set(parameters) - _URL_PARAMETERS)
    if unsupported:
        raise _primitives.BackupConfigurationError(
            f"{environment_variable} carries unsupported connection "
            "parameter(s): " + ", ".join(unsupported)
        )

    database_name = str(parameters.get("dbname") or "").strip()
    if not database_name:
        raise _primitives.BackupConfigurationError(
            f"{environment_variable} must name a database "
            "(postgresql://USER:PASSWORD@HOST:PORT/NAME)."
        )

    host = str(parameters.get("host") or "").strip()
    if "," in host:
        raise _primitives.BackupConfigurationError(
            f"{environment_variable} must name exactly one host; "
            f"pg_dump and pg_restore receive one --host value."
        )

    return {
        "ENGINE": _POSTGRESQL_ENGINE,
        "NAME": database_name,
        "USER": str(parameters.get("user") or "").strip(),
        "PASSWORD": str(parameters.get("password") or ""),
        "HOST": host,
        "PORT": str(parameters.get("port") or "").strip(),
        "OPTIONS": {
            parameter: parameters[parameter]
            for parameter in _URL_OPTION_PARAMETERS
            if parameter in parameters
        },
    }


def _ensure_backup_connection_is_privileged(
    connection: ResolvedBackupConnection,
    *,
    operation: str,
) -> None:
    """Refuse a dump or restore the resolved role cannot complete.

    ``operation`` is ``"capture"`` or ``"restore"``.  Both require
    ``SUPERUSER`` or ``BYPASSRLS``: backups never run under the restricted
    runtime role, which cannot dump a FORCE-RLS table because ``pg_dump``
    disables row security.  A restore additionally needs to own every table
    ``pg_restore --clean`` drops and recreates, or be a superuser.  The check
    runs before any snapshot row or destructive step.
    """
    if operation not in {"capture", "restore"}:
        raise ValueError(f"Unsupported backup connection operation {operation!r}")

    engine = str(connection.settings.get("ENGINE") or "").strip()
    if _primitives._database_engine_family(engine) != "postgresql":
        return

    with _open_connection(connection) as cursor:
        cursor.execute(
            "SELECT current_user, rolsuper, rolbypassrls "
            "FROM pg_catalog.pg_roles WHERE rolname = current_user"
        )
        role_row = cursor.fetchone()
        role_name = str(role_row[0]) if role_row else "the current role"
        is_superuser = bool(role_row and role_row[1])
        can_bypass_rls = bool(role_row and role_row[2])

        if not (is_superuser or can_bypass_rls):
            raise _primitives.BackupConfigurationError(
                f"Backup {operation} requires a PostgreSQL role with SUPERUSER "
                f"or BYPASSRLS; role '{role_name}' has neither. Backups never "
                "run under the restricted runtime role, which cannot dump a "
                "FORCE-RLS table or own the objects a restore recreates. Set "
                f"{_BACKUP_DATABASE_URL_ENV_VAR} (preferred) or "
                f"{_DATABASE_URL_ENV_VAR} to the privileged role's connection "
                "string."
            )

        if operation == "restore" and not is_superuser:
            cursor.execute(_NOT_OWNED_TABLE_COUNT_SQL)
            not_owned_count = int(cursor.fetchone()[0])
            if not_owned_count:
                raise _primitives.BackupConfigurationError(
                    "Backup restore requires a PostgreSQL superuser or the "
                    f"owner of every table it recreates; role '{role_name}' "
                    f"does not own {not_owned_count} table(s). Set "
                    f"{_BACKUP_DATABASE_URL_ENV_VAR} (preferred) or "
                    f"{_DATABASE_URL_ENV_VAR} to the migration role's "
                    "connection string."
                )


def _read_configuration_value(name: str) -> str:
    """Read one connection value the way generated settings read it.

    The process environment wins.  When it is absent, ``python-decouple`` reads
    the generated project's ``.env`` file, exactly as the local and production
    settings do, so a project launched by ``manage.py`` does not silently lose
    its privileged URL.  ``quickscale_core`` does not require decouple: a
    process without it keeps the environment-only behavior.
    """
    value = os.environ.get(name, "").strip()
    if value:
        return value

    try:
        from decouple import AutoConfig
    except ImportError:
        return ""

    try:
        search_path = str(_django_settings.BASE_DIR)
    except Exception:  # noqa: BLE001 - settings may be unconfigured outside Django
        search_path = os.getcwd()
    return str(AutoConfig(search_path=search_path)(name, default="") or "").strip()


@contextmanager
def _open_connection(connection: ResolvedBackupConnection) -> Iterator[Any]:
    """Yield a read-only cursor on the resolved connection, then close it."""
    if connection.url is None:
        with _django_connections["default"].cursor() as cursor:
            yield cursor
        return

    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover - generated projects pin psycopg2
        raise _primitives.BackupConfigurationError(
            f"{connection.source} requires psycopg2 to verify the connection role."
        ) from exc

    try:
        database_connection = psycopg2.connect(connection.url)
    except psycopg2.Error as exc:
        raise _primitives.BackupConfigurationError(
            f"Unable to open the privileged backup connection from "
            f"{connection.source}: {exc}"
        ) from exc

    try:
        with database_connection.cursor() as cursor:
            yield cursor
    finally:
        database_connection.close()
