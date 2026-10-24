"""Tests for the DR engine's privileged backup connection resolution."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import quickscale_core.dr_engine._connection as connection_module
from quickscale_core.dr_engine._connection import (
    ResolvedBackupConnection,
    _ensure_backup_connection_is_privileged,
    _open_connection,
    _postgresql_settings_from_url,
    _resolve_backup_connection,
)
from quickscale_core.dr_engine.primitives import BackupConfigurationError


_POSTGRESQL_DEFAULT: dict[str, Any] = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "app",
    "USER": "runtime_role",
    "PASSWORD": "",
    "HOST": "db",
    "PORT": "5432",
}
_SQLITE_DEFAULT: dict[str, Any] = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": "db.sqlite3",
}


class _FakeCursor:
    """A cursor that returns one queued row per ``fetchone`` call."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = list(rows)
        self.executed: list[str] = []

    def execute(self, statement: str) -> None:
        self.executed.append(statement)

    def fetchone(self) -> tuple[Any, ...]:
        return self._rows.pop(0)


@contextmanager
def _fake_open(connection: ResolvedBackupConnection) -> Iterator[_FakeCursor]:
    del connection
    assert _FAKE_CURSOR is not None
    yield _FAKE_CURSOR


_FAKE_CURSOR: _FakeCursor | None = None


def _patch_connection(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[tuple[Any, ...]],
) -> _FakeCursor:
    global _FAKE_CURSOR
    cursor = _FakeCursor(rows)
    _FAKE_CURSOR = cursor
    monkeypatch.setattr(connection_module, "_open_connection", _fake_open)
    return cursor


class TestParsePostgresqlUrl:
    def test_parses_userinfo_ipv6_tls_and_port(self) -> None:
        settings = _postgresql_settings_from_url(
            "postgresql://backup:p%40ss@[::1]:6543/app"
            "?sslmode=require&connect_timeout=5",
            environment_variable="DATABASE_URL",
        )

        assert settings == {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "app",
            "USER": "backup",
            "PASSWORD": "p@ss",
            "HOST": "::1",
            "PORT": "6543",
            "OPTIONS": {"sslmode": "require", "connect_timeout": "5"},
        }

    def test_accepts_postgres_scheme(self) -> None:
        settings = _postgresql_settings_from_url(
            "postgres://backup@db:5432/app",
            environment_variable="QUICKSCALE_BACKUP_DATABASE_URL",
        )

        assert settings["USER"] == "backup"
        assert settings["HOST"] == "db"
        assert settings["NAME"] == "app"

    def test_requires_database_name(self) -> None:
        with pytest.raises(BackupConfigurationError, match="must name a database"):
            _postgresql_settings_from_url(
                "postgresql://backup@db:5432",
                environment_variable="DATABASE_URL",
            )

    def test_refuses_unsupported_parameters(self) -> None:
        with pytest.raises(
            BackupConfigurationError,
            match="unsupported connection parameter.*application_name",
        ):
            _postgresql_settings_from_url(
                "postgresql://backup@db/app?application_name=backups",
                environment_variable="DATABASE_URL",
            )

    def test_refuses_multiple_hosts(self) -> None:
        with pytest.raises(BackupConfigurationError, match="exactly one host"):
            _postgresql_settings_from_url(
                "postgresql://backup@db1,db2/app",
                environment_variable="DATABASE_URL",
            )

    def test_refuses_invalid_url(self) -> None:
        with pytest.raises(
            BackupConfigurationError,
            match="not a valid PostgreSQL connection URL",
        ):
            _postgresql_settings_from_url(
                "not a connection string",
                environment_variable="DATABASE_URL",
            )


class TestResolveBackupConnection:
    def test_non_postgresql_keeps_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql://backup@db/app")

        resolved = _resolve_backup_connection(_SQLITE_DEFAULT)

        assert resolved.settings == _SQLITE_DEFAULT
        assert resolved.url is None
        assert resolved.source == "default"

    def test_dedicated_url_wins_over_database_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("QUICKSCALE_BACKUP_DATABASE_URL", "postgresql://ded@db/app")
        monkeypatch.setenv("DATABASE_URL", "postgresql://super@db/app")

        resolved = _resolve_backup_connection(_POSTGRESQL_DEFAULT)

        assert resolved.settings["USER"] == "ded"
        assert resolved.source == "QUICKSCALE_BACKUP_DATABASE_URL"

    def test_database_url_is_the_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("QUICKSCALE_BACKUP_DATABASE_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "  postgresql://super@db/app  ")

        resolved = _resolve_backup_connection(_POSTGRESQL_DEFAULT)

        assert resolved.settings["USER"] == "super"
        assert resolved.url == "postgresql://super@db/app"
        assert resolved.source == "DATABASE_URL"

    def test_no_url_keeps_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("QUICKSCALE_BACKUP_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        resolved = _resolve_backup_connection(_POSTGRESQL_DEFAULT)

        assert resolved.settings == _POSTGRESQL_DEFAULT
        assert resolved.url is None
        assert resolved.source == "default"

    def test_reads_dotenv_when_environment_is_absent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("QUICKSCALE_BACKUP_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        (tmp_path / ".env").write_text(
            "DATABASE_URL=postgresql://dotenv@db/app\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            connection_module,
            "_django_settings",
            SimpleNamespace(BASE_DIR=tmp_path),
        )

        resolved = _resolve_backup_connection(_POSTGRESQL_DEFAULT)

        assert resolved.settings["USER"] == "dotenv"
        assert resolved.source == "DATABASE_URL"

    def test_environment_wins_over_dotenv(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("QUICKSCALE_BACKUP_DATABASE_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql://environment@db/app")
        (tmp_path / ".env").write_text(
            "DATABASE_URL=postgresql://dotenv@db/app\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            connection_module,
            "_django_settings",
            SimpleNamespace(BASE_DIR=tmp_path),
        )

        resolved = _resolve_backup_connection(_POSTGRESQL_DEFAULT)

        assert resolved.settings["USER"] == "environment"


class TestPrivilegeGuard:
    def test_non_postgresql_is_not_checked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            connection_module,
            "_open_connection",
            lambda _connection: pytest.fail("no connection expected"),
        )

        _ensure_backup_connection_is_privileged(
            ResolvedBackupConnection(dict(_SQLITE_DEFAULT), None, "default"),
            operation="capture",
        )

    @pytest.mark.parametrize("operation", ["capture", "restore"])
    def test_restricted_role_is_refused(
        self, monkeypatch: pytest.MonkeyPatch, operation: str
    ) -> None:
        cursor = _patch_connection(monkeypatch, [("runtime_role", False, False)])

        with pytest.raises(
            BackupConfigurationError,
            match="never run under the restricted runtime role",
        ):
            _ensure_backup_connection_is_privileged(
                ResolvedBackupConnection(dict(_POSTGRESQL_DEFAULT), None, "default"),
                operation=operation,
            )

        assert len(cursor.executed) == 1

    def test_bypass_rls_capture_is_allowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cursor = _patch_connection(monkeypatch, [("backup_role", False, True)])

        _ensure_backup_connection_is_privileged(
            ResolvedBackupConnection(dict(_POSTGRESQL_DEFAULT), None, "default"),
            operation="capture",
        )

        assert len(cursor.executed) == 1

    def test_bypass_rls_restore_that_owns_every_table_is_allowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cursor = _patch_connection(
            monkeypatch,
            [("backup_role", False, True), (0,)],
        )

        _ensure_backup_connection_is_privileged(
            ResolvedBackupConnection(dict(_POSTGRESQL_DEFAULT), None, "default"),
            operation="restore",
        )

        assert len(cursor.executed) == 2

    def test_bypass_rls_restore_still_requires_ownership(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_connection(monkeypatch, [("backup_role", False, True), (1,)])

        with pytest.raises(BackupConfigurationError, match="does not own 1 table"):
            _ensure_backup_connection_is_privileged(
                ResolvedBackupConnection(dict(_POSTGRESQL_DEFAULT), None, "default"),
                operation="restore",
            )

    def test_superuser_skips_the_ownership_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cursor = _patch_connection(monkeypatch, [("postgres", True, True)])

        _ensure_backup_connection_is_privileged(
            ResolvedBackupConnection(dict(_POSTGRESQL_DEFAULT), None, "default"),
            operation="restore",
        )

        assert len(cursor.executed) == 1

    def test_unknown_operation_is_refused(self) -> None:
        with pytest.raises(ValueError, match="Unsupported backup connection"):
            _ensure_backup_connection_is_privileged(
                ResolvedBackupConnection(dict(_SQLITE_DEFAULT), None, "default"),
                operation="prune",
            )


class TestOpenConnection:
    def test_url_connection_is_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import psycopg2

        closed: list[bool] = []

        class _Handle:
            @contextmanager
            def cursor(self) -> Iterator[str]:
                yield "cursor"

            def close(self) -> None:
                closed.append(True)

        monkeypatch.setattr(psycopg2, "connect", lambda _url: _Handle())

        with _open_connection(
            ResolvedBackupConnection(
                dict(_POSTGRESQL_DEFAULT),
                "postgresql://super@db/app",
                "DATABASE_URL",
            )
        ) as cursor:
            assert cursor == "cursor"

        assert closed == [True]

    def test_connection_failure_is_a_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import psycopg2

        def fail(_url: str) -> Any:
            raise psycopg2.OperationalError("connection refused")

        monkeypatch.setattr(psycopg2, "connect", fail)

        with pytest.raises(
            BackupConfigurationError,
            match="Unable to open the privileged backup connection from DATABASE_URL",
        ):
            with _open_connection(
                ResolvedBackupConnection(
                    dict(_POSTGRESQL_DEFAULT),
                    "postgresql://super@db/app",
                    "DATABASE_URL",
                )
            ):
                pytest.fail("no cursor expected")
