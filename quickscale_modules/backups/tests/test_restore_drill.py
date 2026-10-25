"""End-to-end restore drills for the versioned backup recovery point.

These tests need a PostgreSQL 18 server reachable as the ``postgres``
superuser over the integration harness's trust connection.  They create
scratch databases so the restore never touches the suite's own database.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg2
import pytest
from psycopg2 import sql

from django.db import connections

from quickscale_core.dr_engine.primitives import _build_pg_restore_command


_MODULE_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]

_PROJECT_APP = {
    "__init__.py": "",
    "apps.py": (
        "from django.apps import AppConfig\n\n\n"
        "class ProjectAppConfig(AppConfig):\n"
        '    name = "projectapp"\n'
    ),
    "models.py": (
        "from django.db import models\n\n\n"
        "class ProjectNote(models.Model):\n"
        "    title = models.CharField(max_length=100)\n"
    ),
    "migrations/__init__.py": "",
    "migrations/0001_initial.py": (
        "from django.db import migrations, models\n\n\n"
        "class Migration(migrations.Migration):\n"
        "    initial = True\n\n"
        "    dependencies = []\n\n"
        "    operations = [\n"
        "        migrations.CreateModel(\n"
        '            name="ProjectNote",\n'
        "            fields=[\n"
        '                ("id", models.BigAutoField(auto_created=True, '
        'primary_key=True, serialize=False, verbose_name="ID")),\n'
        '                ("title", models.CharField(max_length=100)),\n'
        "            ],\n"
        "        ),\n"
        "    ]\n"
    ),
}

_DRILL_SETTINGS = '''"""Production-shaped settings for the restore drill."""

import os

import dj_database_url

from tests.settings import *  # noqa: F401, F403

DEBUG = False
BASE_DIR = os.environ["QS_DRILL_BASE_DIR"]
MEDIA_ROOT = os.environ["QS_DRILL_MEDIA_ROOT"]
QUICKSCALE_BACKUPS_LOCAL_DIRECTORY = os.environ["QS_DRILL_BACKUP_DIRECTORY"]
INSTALLED_APPS = [*INSTALLED_APPS, "projectapp"]
DATABASES = {
    "default": dj_database_url.parse(
        os.environ["QS_DRILL_DATABASE_URL"],
        conn_max_age=0,
        conn_health_checks=False,
    ),
}
os.environ.pop("QUICKSCALE_BACKUP_DATABASE_URL", None)
'''


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


def _database_url(database: str) -> str:
    parameters = _connection_parameters()
    return f"postgresql://postgres@{parameters['host']}:{parameters['port']}/{database}"


def _restore_connection_settings(database: str) -> dict[str, str]:
    parameters = _connection_parameters()
    return {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": parameters["host"],
        "PORT": parameters["port"],
        "USER": "postgres",
        "NAME": database,
        "PASSWORD": "",
    }


def _create_database(admin: Any, database: str) -> None:
    with admin.cursor() as cursor:
        cursor.execute(
            sql.SQL("CREATE DATABASE {} OWNER postgres").format(
                sql.Identifier(database)
            )
        )


def _drop_database(admin: Any, database: str) -> None:
    with admin.cursor() as cursor:
        cursor.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database)
            )
        )


@pytest.fixture
def drill_environment(
    tmp_path: Path,
) -> Iterator[dict[str, Any]]:
    """Create the scratch database, project app, media root, and settings."""
    suffix = uuid.uuid4().hex[:12]
    database_name = f"qs_restore_drill_{suffix}"
    admin = _admin_connection()
    _create_database(admin, database_name)

    try:
        base_dir = tmp_path / "project"
        backup_directory = tmp_path / "private-backups"
        media_root = tmp_path / "media"
        settings_directory = tmp_path / "drill-settings"
        base_dir.mkdir()
        media_root.mkdir()
        settings_directory.mkdir()
        for relative_path, content in _PROJECT_APP.items():
            target = base_dir / "projectapp" / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        (settings_directory / "production_drill_settings.py").write_text(
            _DRILL_SETTINGS,
            encoding="utf-8",
        )

        environment = _drill_environment(
            base_dir=base_dir,
            database_url=_database_url(database_name),
            backup_directory=backup_directory,
            media_root=media_root,
            settings_directory=settings_directory,
        )
        migrated = _run_django(["migrate", "--noinput"], environment=environment)
        assert migrated.returncode == 0, migrated.stdout + migrated.stderr
        _seed_project_note(_database_url(database_name), title="captured note")

        yield {
            "database": database_name,
            "database_url": _database_url(database_name),
            "base_dir": base_dir,
            "backup_directory": backup_directory,
            "media_root": media_root,
            "settings_directory": settings_directory,
            "environment": environment,
        }
    finally:
        _drop_database(admin, database_name)
        admin.close()


@pytest.fixture
def two_scratch_databases() -> Iterator[dict[str, str]]:
    """Create a source and target scratch database for the aborted drill."""
    suffix = uuid.uuid4().hex[:12]
    source_name = f"qs_restore_source_{suffix}"
    target_name = f"qs_restore_target_{suffix}"
    admin = _admin_connection()
    _create_database(admin, source_name)
    _create_database(admin, target_name)
    try:
        yield {
            "source": source_name,
            "source_url": _database_url(source_name),
            "target": target_name,
            "target_url": _database_url(target_name),
        }
    finally:
        _drop_database(admin, target_name)
        _drop_database(admin, source_name)
        admin.close()


def _drill_environment(
    *,
    base_dir: Path,
    database_url: str,
    backup_directory: Path,
    media_root: Path,
    settings_directory: Path,
) -> dict[str, str]:
    environment = os.environ.copy()
    environment["DJANGO_SETTINGS_MODULE"] = "production_drill_settings"
    environment["QS_DRILL_DATABASE_URL"] = database_url
    environment["QS_DRILL_BASE_DIR"] = str(base_dir)
    environment["QS_DRILL_BACKUP_DIRECTORY"] = str(backup_directory)
    environment["QS_DRILL_MEDIA_ROOT"] = str(media_root)
    environment["QUICKSCALE_BACKUPS_ALLOW_RESTORE"] = "true"
    environment.pop("QUICKSCALE_BACKUP_DATABASE_URL", None)
    environment.pop("RUNTIME_DATABASE_URL", None)
    environment.pop("QUICKSCALE_PRIVILEGED_COMMAND", None)
    environment.pop("DATABASE_URL", None)
    python_paths = [
        str(settings_directory),
        str(base_dir),
        str(_MODULE_ROOT),
        str(_MODULE_ROOT / "src"),
        str(_REPO_ROOT),
    ]
    existing_python_path = environment.get("PYTHONPATH", "")
    if existing_python_path:
        python_paths.append(existing_python_path)
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    return environment


def _run_django(
    arguments: list[str],
    *,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed argv list in a test
        [sys.executable, "-m", "django", *arguments],
        cwd=_MODULE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def _seed_project_note(database_url: str, *, title: str) -> None:
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO projectapp_projectnote (title) VALUES (%s)",
                (title,),
            )
    finally:
        connection.close()


def _project_note_titles(database_url: str) -> list[str]:
    connection = psycopg2.connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT title FROM projectapp_projectnote ORDER BY id")
            return [str(row[0]) for row in cursor.fetchall()]
    finally:
        connection.close()


def _drop_project_table(database_url: str) -> None:
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE projectapp_projectnote")
    finally:
        connection.close()


def _table_exists(database_url: str, table: str) -> bool:
    connection = psycopg2.connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass(%s)", (f"public.{table}",))
            return cursor.fetchone()[0] is not None
    finally:
        connection.close()


def _write_media_files(media_root: Path) -> dict[str, bytes]:
    files = {
        "blog/uploads/hero.png": b"hero-bytes",
        "avatars/user one.png": b"avatar-bytes",
    }
    for relative_path, content in files.items():
        target = media_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return files


def _read_snapshot_report(created: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert created.returncode == 0, created.stdout + created.stderr
    report = json.loads(created.stdout)
    assert report["status"] == "ready"
    return report


def test_drill_restores_database_media_and_project_schema(
    drill_environment: dict[str, Any],
) -> None:
    """Capture then restore the database, media set, and project-owned schema."""
    media_root = drill_environment["media_root"]
    captured_files = _write_media_files(media_root)
    environment = drill_environment["environment"]

    created = _run_django(
        ["quickscale_backups_create", "--json"],
        environment=environment,
    )
    report = _read_snapshot_report(created)
    snapshot_id = str(report["snapshot_id"])
    artifact = report["authoritative_dump"]
    assert artifact["backup_format"] == "pg_dump_custom"

    snapshot_root = Path(artifact["local_path"]).parents[1]
    media_manifest = json.loads(
        (snapshot_root / "media-sync-manifest.json").read_text(encoding="utf-8")
    )
    assert media_manifest["manifest_version"] == 2
    assert media_manifest["capture"]["status"] == "captured"
    assert media_manifest["capture"]["file_count"] == len(captured_files)
    captured_inventory = {
        entry["relative_path"]: entry for entry in media_manifest["inventory"]
    }
    assert set(captured_inventory) == set(captured_files)
    for relative_path in captured_files:
        assert (snapshot_root / "media" / relative_path).read_bytes() == (
            captured_files[relative_path]
        )

    _drop_project_table(drill_environment["database_url"])
    for relative_path in captured_files:
        (media_root / relative_path).unlink()
    assert (
        _table_exists(drill_environment["database_url"], "projectapp_projectnote")
        is False
    )

    restored = _run_django(
        [
            "quickscale_backups_restore",
            str(artifact["artifact_id"]),
            "--confirm",
            artifact["filename"],
        ],
        environment=environment,
    )
    assert restored.returncode == 0, restored.stdout + restored.stderr

    assert _project_note_titles(drill_environment["database_url"]) == ["captured note"]

    synced = _run_django(
        [
            "quickscale_backups_sync_media",
            snapshot_id,
            "--target-runtime-json",
            json.dumps(
                {
                    "QUICKSCALE_STORAGE_BACKEND": "local",
                    "MEDIA_ROOT": str(media_root),
                }
            ),
            "--json",
        ],
        environment=environment,
    )
    assert synced.returncode == 0, synced.stdout + synced.stderr
    sync_report = json.loads(synced.stdout)
    assert sync_report["status"] == "completed"
    assert sync_report["source"] == "snapshot"
    assert sync_report["copied_count"] == len(captured_files)
    for relative_path, content in captured_files.items():
        assert (media_root / relative_path).read_bytes() == content


def test_aborted_restore_leaves_the_target_database_unchanged(
    two_scratch_databases: dict[str, str],
    tmp_path: Path,
) -> None:
    """A restore that fails mid-transaction leaves no partially restored tables."""
    source_url = two_scratch_databases["source_url"]
    target_url = two_scratch_databases["target_url"]

    source = psycopg2.connect(source_url)
    source.autocommit = True
    try:
        with source.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE restore_probe_early (id integer PRIMARY KEY, "
                "payload text NOT NULL)"
            )
            cursor.execute("INSERT INTO restore_probe_early VALUES (1, 'captured')")
            cursor.execute("CREATE TABLE restore_probe_marker (id integer PRIMARY KEY)")
    finally:
        source.close()

    dump_path = tmp_path / "restore-drill.dump"
    dumped = subprocess.run(  # noqa: S603 - fixed argv list in a test
        [
            "pg_dump",
            "--format=c",
            "--file",
            str(dump_path),
            source_url,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert dumped.returncode == 0, dumped.stderr

    target = psycopg2.connect(target_url)
    target.autocommit = True
    try:
        with target.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE pre_restore_sentinel (id integer PRIMARY KEY, "
                "payload text NOT NULL)"
            )
            cursor.execute("INSERT INTO pre_restore_sentinel VALUES (1, 'untouched')")
            cursor.execute(
                "CREATE FUNCTION qs_fail_restore() RETURNS event_trigger "
                "LANGUAGE plpgsql AS $$ "
                "DECLARE command record; "
                "BEGIN "
                "FOR command IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP "
                "IF command.command_tag = 'CREATE TABLE' "
                "AND command.object_identity LIKE '%restore_probe_marker%' THEN "
                "RAISE EXCEPTION 'simulated restore failure'; "
                "END IF; "
                "END LOOP; "
                "END; "
                "$$"
            )
            cursor.execute(
                "CREATE EVENT TRIGGER qs_fail_restore ON ddl_command_end "
                "EXECUTE FUNCTION qs_fail_restore()"
            )
    finally:
        target.close()

    command, command_environment = _build_pg_restore_command(
        dump_path,
        _restore_connection_settings(two_scratch_databases["target"]),
    )
    restored = subprocess.run(  # noqa: S603 - fixed argv list in a test
        command,
        env={**os.environ, **(command_environment or {})},
        capture_output=True,
        text=True,
        check=False,
    )

    assert "--single-transaction" in command
    assert restored.returncode != 0
    assert "simulated restore failure" in restored.stderr
    assert _table_exists(target_url, "restore_probe_early") is False
    assert _table_exists(target_url, "restore_probe_marker") is False
    connection = psycopg2.connect(target_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM pre_restore_sentinel")
            assert cursor.fetchall() == [("untouched",)]
    finally:
        connection.close()


def test_killed_restore_rolls_back_the_target_database(
    two_scratch_databases: dict[str, str],
    tmp_path: Path,
) -> None:
    """A SIGKILLed pg_restore leaves the target's previous state intact."""
    source_url = two_scratch_databases["source_url"]
    target_url = two_scratch_databases["target_url"]
    target_name = two_scratch_databases["target"]

    source = psycopg2.connect(source_url)
    source.autocommit = True
    try:
        with source.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE restore_probe_early (id integer PRIMARY KEY, "
                "payload text NOT NULL)"
            )
            cursor.execute("INSERT INTO restore_probe_early VALUES (1, 'captured')")
            cursor.execute("CREATE TABLE restore_probe_marker (id integer PRIMARY KEY)")
    finally:
        source.close()

    dump_path = tmp_path / "restore-kill-drill.dump"
    dumped = subprocess.run(  # noqa: S603 - fixed argv list in a test
        ["pg_dump", "--format=c", "--file", str(dump_path), source_url],
        capture_output=True,
        text=True,
        check=False,
    )
    assert dumped.returncode == 0, dumped.stderr

    target = psycopg2.connect(target_url)
    target.autocommit = True
    try:
        with target.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE pre_restore_sentinel (id integer PRIMARY KEY, "
                "payload text NOT NULL)"
            )
            cursor.execute("INSERT INTO pre_restore_sentinel VALUES (1, 'untouched')")
            cursor.execute(
                "CREATE FUNCTION qs_slow_restore() RETURNS event_trigger "
                "LANGUAGE plpgsql AS $$ "
                "DECLARE command record; "
                "BEGIN "
                "FOR command IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP "
                "IF command.command_tag = 'CREATE TABLE' "
                "AND command.object_identity LIKE '%restore_probe_marker%' THEN "
                "PERFORM pg_sleep(5); "
                "END IF; "
                "END LOOP; "
                "END; "
                "$$"
            )
            cursor.execute(
                "CREATE EVENT TRIGGER qs_slow_restore ON ddl_command_end "
                "EXECUTE FUNCTION qs_slow_restore()"
            )
    finally:
        target.close()

    command, command_environment = _build_pg_restore_command(
        dump_path,
        _restore_connection_settings(target_name),
    )
    environment = {
        **os.environ,
        **(command_environment or {}),
        "PGAPPNAME": "qs-kill-drill",
    }
    restore = subprocess.Popen(  # noqa: S603 - fixed argv list in a test
        command,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_sleeping_restore(target_name)
        restore.kill()
    finally:
        restore.wait(timeout=30)

    assert restore.returncode != 0
    _wait_until_table_missing(target_url, "restore_probe_early")
    assert _table_exists(target_url, "restore_probe_early") is False
    assert _table_exists(target_url, "restore_probe_marker") is False
    connection = psycopg2.connect(target_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM pre_restore_sentinel")
            assert cursor.fetchall() == [("untouched",)]
    finally:
        connection.close()


def _wait_for_sleeping_restore(database: str) -> None:
    """Wait until the restore backend is inside the marker trigger's sleep."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        connection = _admin_connection("postgres")
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM pg_stat_activity "
                    "WHERE datname = %s AND application_name = %s "
                    "AND wait_event = 'PgSleep'",
                    (database, "qs-kill-drill"),
                )
                if cursor.fetchone() is not None:
                    return
        finally:
            connection.close()
        time.sleep(0.05)
    raise AssertionError("the restore never reached the sleep marker")


def _wait_until_table_missing(database_url: str, table: str) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if _table_exists(database_url, table) is False:
            return
        time.sleep(0.1)
    raise AssertionError(f"table '{table}' survived the killed restore")
