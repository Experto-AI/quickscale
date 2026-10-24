"""The dump and restore connection is the privileged role, not the runtime role.

These tests need a PostgreSQL 18 server reachable as the ``postgres`` superuser
over the integration harness's trust connection.  They create a scratch
database, a restricted runtime role, and a FORCE-RLS table, then prove that:

* the runtime role cannot dump the table with ``pg_dump``;
* the backup engine dumps and restores it under ``DATABASE_URL``;
* the engine refuses the runtime role before it runs either command.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import pytest
from psycopg2 import sql

from django.db import connections

from quickscale_core.dr_engine._connection import _resolve_backup_connection
from quickscale_core.dr_engine.primitives import (
    BackupConfigurationError,
    BackupPolicySnapshot,
    _run_shell_command,
)
from quickscale_modules_backups.services import (
    create_backup,
    restore_backup_artifact,
)


_FORCE_RLS_TABLE = "backup_role_tenant_rows"
_ROWS = [(1, 10, "alpha"), (2, 20, "beta")]
_MODULE_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _connection_parameters() -> dict[str, str]:
    settings_dict = connections["default"].settings_dict
    return {
        "host": str(settings_dict.get("HOST") or "localhost"),
        "port": str(settings_dict.get("PORT") or "5432"),
    }


def _admin_connection(database: str = "postgres") -> Any:
    parameters = _connection_parameters()
    connection = psycopg2.connect(
        host=parameters["host"],
        port=parameters["port"],
        user="postgres",
        dbname=database,
    )
    connection.autocommit = True
    return connection


def _database_url(database: str, *, role: str) -> str:
    parameters = _connection_parameters()
    return f"postgresql://{role}@{parameters['host']}:{parameters['port']}/{database}"


def _close_connection(connection: Any) -> None:
    connection.close()


@pytest.fixture
def scratch_database() -> Iterator[dict[str, str]]:
    """Create a scratch database, a restricted runtime role, and its table."""
    suffix = uuid.uuid4().hex[:12]
    role_name = f"qs_backup_runtime_{suffix}"
    database_name = f"qs_backup_scratch_{suffix}"
    admin = _admin_connection()

    try:
        with admin.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOBYPASSRLS "
                    "NOCREATEDB NOCREATEROLE"
                ).format(sql.Identifier(role_name))
            )
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER postgres").format(
                    sql.Identifier(database_name)
                )
            )
            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database_name), sql.Identifier(role_name)
                )
            )

        scratch = {
            "database": database_name,
            "runtime_role": role_name,
            "runtime_url": _database_url(database_name, role=role_name),
            "privileged_url": _database_url(database_name, role="postgres"),
        }
        database_connection = _admin_connection(database_name)
        try:
            with database_connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        "CREATE TABLE {} ("
                        "id integer PRIMARY KEY, "
                        "organization_id integer NOT NULL, "
                        "payload text NOT NULL)"
                    ).format(sql.Identifier(_FORCE_RLS_TABLE))
                )
                cursor.execute(
                    sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(
                        sql.Identifier(_FORCE_RLS_TABLE)
                    )
                )
                cursor.execute(
                    sql.SQL("ALTER TABLE {} FORCE ROW LEVEL SECURITY").format(
                        sql.Identifier(_FORCE_RLS_TABLE)
                    )
                )
                cursor.execute(
                    sql.SQL(
                        "CREATE POLICY {} ON {} "
                        "USING (organization_id = "
                        "current_setting('app.current_org_id', true)::integer) "
                        "WITH CHECK (organization_id = "
                        "current_setting('app.current_org_id', true)::integer)"
                    ).format(
                        sql.Identifier(f"{_FORCE_RLS_TABLE}_org"),
                        sql.Identifier(_FORCE_RLS_TABLE),
                    )
                )
                cursor.execute(
                    sql.SQL(
                        "INSERT INTO {} VALUES (1, 10, 'alpha'), (2, 20, 'beta')"
                    ).format(sql.Identifier(_FORCE_RLS_TABLE))
                )
                cursor.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                        sql.Identifier(role_name)
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT SELECT ON {} TO {}").format(
                        sql.Identifier(_FORCE_RLS_TABLE), sql.Identifier(role_name)
                    )
                )
        finally:
            _close_connection(database_connection)

        yield scratch
    finally:
        with admin.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(database_name)
                )
            )
            cursor.execute(
                sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role_name))
            )
        _close_connection(admin)


_PRODUCTION_DRILL_SETTINGS = '''"""Production-shaped settings for the scratch backup drill."""

import os

import dj_database_url

from tests.settings import *  # noqa: F401, F403

DEBUG = False
os.environ.pop("QUICKSCALE_BACKUP_DATABASE_URL", None)
QUICKSCALE_BACKUPS_LOCAL_DIRECTORY = os.environ["QS_DRILL_BACKUP_DIRECTORY"]
DATABASES = {
    "default": dj_database_url.parse(
        os.environ["QS_DRILL_DATABASE_URL"],
        conn_max_age=0,
        conn_health_checks=False,
    ),
}
'''


def _drill_environment(
    *,
    settings_module: str,
    database_url: str,
    backup_directory: Path,
    privileged_url: str | None = None,
) -> dict[str, str]:
    """Build a child-process environment for the production-settings drill."""
    environment = os.environ.copy()
    environment["DJANGO_SETTINGS_MODULE"] = settings_module
    environment["QS_DRILL_DATABASE_URL"] = database_url
    environment["QS_DRILL_BACKUP_DIRECTORY"] = str(backup_directory)
    environment["QUICKSCALE_BACKUPS_ALLOW_RESTORE"] = "true"
    environment.pop("QUICKSCALE_BACKUP_DATABASE_URL", None)
    environment.pop("RUNTIME_DATABASE_URL", None)
    environment.pop("QUICKSCALE_PRIVILEGED_COMMAND", None)
    if privileged_url is None:
        environment.pop("DATABASE_URL", None)
    else:
        environment["DATABASE_URL"] = privileged_url
    existing_python_path = environment.get("PYTHONPATH", "")
    python_paths = [
        str(_MODULE_ROOT),
        str(_MODULE_ROOT / "src"),
        str(_REPO_ROOT),
    ]
    if existing_python_path:
        python_paths.append(existing_python_path)
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    return environment


def _run_django(
    arguments: list[str],
    *,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run one Django command in a subprocess with the drill settings."""
    return subprocess.run(  # noqa: S603 - fixed argv list in a test
        [sys.executable, "-m", "django", *arguments],
        cwd=_MODULE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _grant_runtime_application_access(database_url: str, role_name: str) -> None:
    """Grant the runtime role the DML a Django process needs after migration."""
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                    sql.Identifier(role_name)
                )
            )
            cursor.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                    "IN SCHEMA public TO {}"
                ).format(sql.Identifier(role_name))
            )
            cursor.execute(
                sql.SQL(
                    "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}"
                ).format(sql.Identifier(role_name))
            )
    finally:
        connection.close()


def _policy(local_directory: Path) -> BackupPolicySnapshot:
    return BackupPolicySnapshot(
        retention_days=14,
        naming_prefix="db",
        target_mode="local",
        local_directory=str(local_directory),
        remote_bucket_name="",
        remote_prefix="backups/private",
        remote_endpoint_url="",
        remote_region_name="",
        remote_access_key_id_env_var="QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID",
        remote_secret_access_key_env_var="QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY",
        automation_enabled=False,
        schedule="0 2 * * *",
    )


def _fetch_rows(database_url: str) -> list[tuple[int, int, str]]:
    connection = psycopg2.connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    "SELECT id, organization_id, payload FROM {} ORDER BY id"
                ).format(sql.Identifier(_FORCE_RLS_TABLE))
            )
            return [tuple(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def _delete_rows(database_url: str) -> None:
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("DELETE FROM {}").format(sql.Identifier(_FORCE_RLS_TABLE))
            )
    finally:
        connection.close()


def _configure_production_environment(
    monkeypatch: pytest.MonkeyPatch,
    scratch: dict[str, str],
) -> None:
    """Set both production URLs; no dedicated backup URL, so DATABASE_URL wins."""
    monkeypatch.delenv("QUICKSCALE_BACKUP_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", scratch["privileged_url"])
    monkeypatch.setenv("RUNTIME_DATABASE_URL", scratch["runtime_url"])


def test_runtime_role_cannot_dump_a_force_rls_table(
    tmp_path: Path,
    scratch_database: dict[str, str],
) -> None:
    """Reproduce the defect: the restricted role cannot pg_dump the table."""
    runtime_dump = tmp_path / "runtime.dump"

    result = subprocess.run(  # noqa: S603 - fixed argv list in a test
        [
            "pg_dump",
            "--format=c",
            "--file",
            str(runtime_dump),
            scratch_database["runtime_url"],
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "row-level security" in result.stderr.lower()


def test_privileged_dump_and_restore_preserve_every_force_rls_row(
    tmp_path: Path,
    db: None,
    scratch_database: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The engine dumps and restores all rows under the superuser connection."""
    _configure_production_environment(monkeypatch, scratch_database)
    monkeypatch.setenv("QUICKSCALE_BACKUPS_ALLOW_RESTORE", "true")
    resolved = _resolve_backup_connection(connections["default"].settings_dict)
    assert resolved.source == "DATABASE_URL"
    assert resolved.settings["USER"] == "postgres"

    commands: list[tuple[list[str], dict[str, str]]] = []

    def recording_runner(
        command: Any,
        *,
        env: dict[str, str] | None = None,
    ) -> None:
        commands.append((list(command), dict(env or {})))
        _run_shell_command(command, env=env)

    artifact = create_backup(
        policy=_policy(tmp_path / "private-backups"),
        shell_runner=recording_runner,
        now=datetime.now(timezone.utc),
    )

    assert artifact.status == "ready"
    assert artifact.backup_format == "pg_dump_custom"
    assert artifact.database_name == scratch_database["database"]

    dump_commands = [command for command, _env in commands if command[0] == "pg_dump"]
    assert len(dump_commands) == 1
    dump_command = dump_commands[0]
    dump_index = dump_command.index("--username")
    assert dump_command[dump_index + 1] == "postgres"
    assert scratch_database["runtime_role"] not in " ".join(dump_command)
    assert all(
        scratch_database["runtime_role"] != value
        for _command, environment in commands
        for value in environment.values()
    )

    _delete_rows(scratch_database["privileged_url"])
    assert _fetch_rows(scratch_database["privileged_url"]) == []

    result = restore_backup_artifact(
        artifact,
        confirmation=artifact.filename,
        dry_run=False,
        shell_runner=recording_runner,
    )

    assert result.executed is True
    restore_commands = [
        command
        for command, _env in commands
        if command[0] == "pg_restore" and "--clean" in command
    ]
    assert len(restore_commands) == 1
    restore_command = restore_commands[0]
    restore_index = restore_command.index("--username")
    assert restore_command[restore_index + 1] == "postgres"
    assert scratch_database["runtime_role"] not in " ".join(restore_command)
    assert _fetch_rows(scratch_database["privileged_url"]) == _ROWS


def test_management_commands_run_under_production_settings(
    tmp_path: Path,
    db: None,
    scratch_database: dict[str, str],
) -> None:
    """Create and restore through production-shaped settings and Django commands."""
    settings_directory = tmp_path / "drill-settings"
    settings_directory.mkdir()
    (settings_directory / "production_drill_settings.py").write_text(
        _PRODUCTION_DRILL_SETTINGS, encoding="utf-8"
    )
    backup_directory = tmp_path / "private-backups"

    migrate_environment = _drill_environment(
        settings_module="production_drill_settings",
        database_url=scratch_database["privileged_url"],
        backup_directory=backup_directory,
        privileged_url=scratch_database["privileged_url"],
    )
    settings_python_path = str(settings_directory)
    migrate_environment["PYTHONPATH"] = os.pathsep.join(
        [settings_python_path, migrate_environment["PYTHONPATH"]]
    )
    migrated = _run_django(["migrate", "--noinput"], environment=migrate_environment)
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr
    _grant_runtime_application_access(
        scratch_database["privileged_url"], scratch_database["runtime_role"]
    )

    runtime_environment = _drill_environment(
        settings_module="production_drill_settings",
        database_url=scratch_database["runtime_url"],
        backup_directory=backup_directory,
        privileged_url=scratch_database["privileged_url"],
    )
    runtime_environment["PYTHONPATH"] = migrate_environment["PYTHONPATH"]

    probe = _run_django(
        [
            "shell",
            "-c",
            (
                "from django.db import connection\n"
                "with connection.cursor() as cursor:\n"
                "    cursor.execute(\n"
                '        "SELECT current_user, rolsuper, rolbypassrls "\n'
                '        "FROM pg_catalog.pg_roles WHERE rolname = current_user"\n'
                "    )\n"
                "    print(cursor.fetchone())\n"
            ),
        ],
        environment=runtime_environment,
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr
    assert probe.stdout.strip().splitlines()[-1] == (
        f"('{scratch_database['runtime_role']}', False, False)"
    )

    created = _run_django(
        ["quickscale_backups_create", "--json"],
        environment=runtime_environment,
    )
    assert created.returncode == 0, created.stdout + created.stderr
    report = json.loads(created.stdout)
    authoritative_dump = report["authoritative_dump"]
    assert report["status"] == "ready"
    assert authoritative_dump["backup_format"] == "pg_dump_custom"
    assert Path(authoritative_dump["local_path"]).exists()

    _delete_rows(scratch_database["privileged_url"])
    assert _fetch_rows(scratch_database["privileged_url"]) == []

    restored = _run_django(
        [
            "quickscale_backups_restore",
            str(authoritative_dump["artifact_id"]),
            "--confirm",
            authoritative_dump["filename"],
        ],
        environment=runtime_environment,
    )
    assert restored.returncode == 0, restored.stdout + restored.stderr
    assert _fetch_rows(scratch_database["privileged_url"]) == _ROWS


def test_capture_refuses_the_runtime_role_before_dumping(
    tmp_path: Path,
    db: None,
    scratch_database: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A NOBYPASSRLS role is refused while the database holds a FORCE-RLS table."""
    monkeypatch.setenv(
        "QUICKSCALE_BACKUP_DATABASE_URL", scratch_database["runtime_url"]
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)

    commands: list[list[str]] = []

    def recording_runner(
        command: Any,
        *,
        env: dict[str, str] | None = None,
    ) -> None:
        del env
        commands.append(list(command))

    with pytest.raises(
        BackupConfigurationError,
        match="SUPERUSER or BYPASSRLS.*FORCE-RLS table",
    ):
        create_backup(
            policy=_policy(tmp_path / "private-backups"),
            shell_runner=recording_runner,
            now=datetime.now(timezone.utc),
        )

    assert commands == []


def test_restore_refuses_the_runtime_role_before_restoring(
    tmp_path: Path,
    db: None,
    scratch_database: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The restore path applies the same privileged-role guard."""
    _configure_production_environment(monkeypatch, scratch_database)
    artifact = create_backup(
        policy=_policy(tmp_path / "private-backups"),
        now=datetime.now(timezone.utc),
    )

    monkeypatch.setenv(
        "QUICKSCALE_BACKUP_DATABASE_URL", scratch_database["runtime_url"]
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    restore_commands: list[list[str]] = []

    def recording_runner(
        command: Any,
        *,
        env: dict[str, str] | None = None,
    ) -> None:
        del env
        restore_commands.append(list(command))

    with pytest.raises(
        BackupConfigurationError,
        match="SUPERUSER or BYPASSRLS.*FORCE-RLS table",
    ):
        restore_backup_artifact(
            artifact,
            confirmation=artifact.filename,
            dry_run=False,
            shell_runner=recording_runner,
        )

    assert restore_commands == []
