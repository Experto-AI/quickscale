"""Tests for the DR engine snapshot and archive primitives."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from quickscale_core.dr_engine import primitives as primitives_module
from quickscale_core.dr_engine.primitives import (
    BackupConfigurationError,
    BackupError,
    _POSTGRESQL_CUSTOM_ARCHIVE_MAGIC,
    _REQUIRED_POSTGRESQL_MAJOR,
    _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES,
    _SNAPSHOTS_DIRECTORY_NAME,
    _SNAPSHOT_DATABASE_DIRECTORY_NAME,
    _build_pg_dump_command,
    _build_pg_restore_command,
    _build_snapshot_child_descriptor,
    _compute_sha256,
    _database_engine_family,
    _dump_postgresql_database,
    _expected_backup_format_for_engine,
    _extract_any_major_version,
    _extract_leading_major_version,
    _get_postgresql_tool_version,
    _mint_snapshot_id,
    _missing_executable_backup_error,
    _postgresql_18_client_tooling_guidance,
    _relative_snapshot_child_path,
    _run_shell_command,
    _write_json_file,
)


class TestConstants:
    def test_required_postgresql_major(self) -> None:
        assert _REQUIRED_POSTGRESQL_MAJOR == 18

    def test_postgresql_custom_archive_magic(self) -> None:
        assert _POSTGRESQL_CUSTOM_ARCHIVE_MAGIC == b"PGDMP"

    def test_snapshots_directory_name(self) -> None:
        assert _SNAPSHOTS_DIRECTORY_NAME == "snapshots"

    def test_snapshot_database_directory_name(self) -> None:
        assert _SNAPSHOT_DATABASE_DIRECTORY_NAME == "database"

    def test_required_snapshot_sidecar_filenames(self) -> None:
        assert "media-sync-manifest.json" in _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES
        assert "env-var-manifest.json" in _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES
        assert "release-metadata.json" in _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES
        assert "promotion-verification.json" in _REQUIRED_SNAPSHOT_SIDECAR_FILENAMES


class TestErrorClasses:
    def test_backup_error_is_exception(self) -> None:
        exc = BackupError("test")
        assert isinstance(exc, Exception)
        assert str(exc) == "test"

    def test_backup_configuration_error_is_backup_error(self) -> None:
        exc = BackupConfigurationError("config")
        assert isinstance(exc, BackupError)


class TestVersionExtraction:
    def test_extract_leading_major_version_basic(self) -> None:
        assert _extract_leading_major_version("18.1") == 18

    def test_extract_leading_major_version_with_prefix_text(self) -> None:
        assert _extract_leading_major_version("PostgreSQL 18.1") is None

    def test_extract_leading_major_version_none_input(self) -> None:
        assert _extract_leading_major_version(None) is None

    def test_extract_leading_major_version_empty(self) -> None:
        assert _extract_leading_major_version("") is None

    def test_extract_leading_major_version_zero_returns_none(self) -> None:
        assert _extract_leading_major_version("0.1") is None

    def test_extract_any_major_version_finds_first_number(self) -> None:
        assert _extract_any_major_version("pg_dump (PostgreSQL) 18.1") == 18

    def test_extract_any_major_version_none_input(self) -> None:
        assert _extract_any_major_version(None) is None

    def test_extract_any_major_version_empty(self) -> None:
        assert _extract_any_major_version("") is None

    def test_extract_any_major_version_zero_returns_none(self) -> None:
        assert _extract_any_major_version("version 0.1") is None

    def test_extract_any_major_version_no_digits_returns_none(self) -> None:
        assert _extract_any_major_version("no digits here") is None


class TestDatabaseEngineHelpers:
    def test_postgresql_engine_family(self) -> None:
        assert _database_engine_family("django.db.backends.postgresql") == "postgresql"

    def test_sqlite_engine_family(self) -> None:
        assert _database_engine_family("django.db.backends.sqlite3") == "sqlite"

    def test_unknown_engine_returns_normalized(self) -> None:
        assert _database_engine_family("custom.backend") == "custom.backend"

    def test_postgresql_expected_format(self) -> None:
        assert (
            _expected_backup_format_for_engine("django.db.backends.postgresql")
            == "pg_dump_custom"
        )

    def test_sqlite_expected_format(self) -> None:
        assert (
            _expected_backup_format_for_engine("django.db.backends.sqlite3") == "json"
        )


class TestPgDumpCommandBuilding:
    def test_build_pg_dump_command_basic(self, tmp_path: Path) -> None:
        local_path = tmp_path / "dump.dump"
        connection_settings = {
            "HOST": "localhost",
            "PORT": "5432",
            "USER": "user",
            "NAME": "mydb",
            "PASSWORD": "secret",
        }
        command, env = _build_pg_dump_command(local_path, connection_settings)
        assert "pg_dump" in command
        assert "--format=c" in command
        assert "mydb" in command
        assert env == {"PGPASSWORD": "secret"}

    def test_build_pg_dump_command_no_password(self, tmp_path: Path) -> None:
        local_path = tmp_path / "dump.dump"
        connection_settings = {"NAME": "mydb"}
        command, env = _build_pg_dump_command(local_path, connection_settings)
        assert env is None

    def test_build_pg_dump_command_missing_name_raises(self, tmp_path: Path) -> None:
        local_path = tmp_path / "dump.dump"
        with pytest.raises(BackupConfigurationError, match="NAME"):
            _build_pg_dump_command(local_path, {"NAME": ""})

    def test_build_pg_restore_command_basic(self, tmp_path: Path) -> None:
        local_path = tmp_path / "dump.dump"
        connection_settings = {
            "HOST": "localhost",
            "PORT": "5432",
            "USER": "user",
            "NAME": "mydb",
            "PASSWORD": "secret",
        }
        command, env = _build_pg_restore_command(local_path, connection_settings)
        assert "pg_restore" in command
        assert "--clean" in command
        assert "mydb" in command
        assert env == {"PGPASSWORD": "secret"}

    def test_build_pg_restore_command_missing_name_raises(self, tmp_path: Path) -> None:
        local_path = tmp_path / "dump.dump"
        with pytest.raises(BackupConfigurationError, match="NAME"):
            _build_pg_restore_command(local_path, {"NAME": ""})


_CONNECTION_SETTING_KEYS = {"HOST", "PORT", "USER", "NAME", "PASSWORD", "OPTIONS"}
_CONNECTION_PARAMETER_OWNER = "_resolve_postgres_connection_parameters"
_TLS_CONNECTION_SETTINGS = {
    "HOST": "db.example.com",
    "PORT": "5432",
    "USER": "app",
    "NAME": "app",
    "PASSWORD": "secret",
    "OPTIONS": {"sslmode": "verify-full", "sslrootcert": "/etc/ssl/ca.pem"},
}


class TestPgCommandTlsTranslation:
    """pg_dump/pg_restore run under the database's own TLS posture."""

    def test_build_pg_dump_command_demands_connection_tls(self, tmp_path: Path) -> None:
        command, env = _build_pg_dump_command(
            tmp_path / "dump.dump", dict(_TLS_CONNECTION_SETTINGS)
        )
        assert env == {
            "PGPASSWORD": "secret",
            "PGSSLMODE": "verify-full",
            "PGSSLROOTCERT": "/etc/ssl/ca.pem",
        }
        assert "verify-full" not in command
        assert "/etc/ssl/ca.pem" not in command

    def test_build_pg_restore_command_demands_connection_tls(
        self, tmp_path: Path
    ) -> None:
        command, env = _build_pg_restore_command(
            tmp_path / "dump.dump", dict(_TLS_CONNECTION_SETTINGS)
        )
        assert env == {
            "PGPASSWORD": "secret",
            "PGSSLMODE": "verify-full",
            "PGSSLROOTCERT": "/etc/ssl/ca.pem",
        }
        assert "verify-full" not in command
        assert "/etc/ssl/ca.pem" not in command

    def test_translates_client_certificate_and_timeout_options(
        self, tmp_path: Path
    ) -> None:
        connection_settings = {
            "NAME": "mydb",
            "OPTIONS": {
                "sslcert": "/etc/ssl/client.crt",
                "sslkey": "/etc/ssl/client.key",
                "connect_timeout": 5,
            },
        }
        command, env = _build_pg_dump_command(
            tmp_path / "dump.dump", connection_settings
        )
        assert env == {
            "PGSSLCERT": "/etc/ssl/client.crt",
            "PGSSLKEY": "/etc/ssl/client.key",
            "PGCONNECT_TIMEOUT": "5",
        }
        assert "/etc/ssl/client.key" not in command

    def test_empty_options_behaves_exactly_as_before(self, tmp_path: Path) -> None:
        with_password = {
            "HOST": "localhost",
            "PORT": "5432",
            "USER": "user",
            "NAME": "mydb",
            "PASSWORD": "secret",
            "OPTIONS": {},
        }
        _, dump_env = _build_pg_dump_command(tmp_path / "dump.dump", with_password)
        _, restore_env = _build_pg_restore_command(
            tmp_path / "dump.dump", with_password
        )
        assert dump_env == {"PGPASSWORD": "secret"}
        assert restore_env == {"PGPASSWORD": "secret"}

        without_password = {"NAME": "mydb", "OPTIONS": {}}
        _, dump_env = _build_pg_dump_command(tmp_path / "dump.dump", without_password)
        _, restore_env = _build_pg_restore_command(
            tmp_path / "dump.dump", without_password
        )
        assert dump_env is None
        assert restore_env is None

    def test_dump_postgresql_database_hands_tls_environment_to_the_child(
        self, tmp_path: Path
    ) -> None:
        calls: list[tuple[list[str], dict[str, str] | None]] = []

        def fake_runner(
            command: list[str], *, env: dict[str, str] | None = None
        ) -> None:
            calls.append((command, env))

        _dump_postgresql_database(
            tmp_path / "dump.dump",
            dict(_TLS_CONNECTION_SETTINGS),
            shell_runner=fake_runner,
        )
        assert len(calls) == 1
        assert calls[0][1] == {
            "PGPASSWORD": "secret",
            "PGSSLMODE": "verify-full",
            "PGSSLROOTCERT": "/etc/ssl/ca.pem",
        }


class TestConnectionParameterOwnership:
    """Command builders must route through the single connection owner."""

    def test_only_the_owner_reads_connection_setting_keys(self) -> None:
        source = Path(primitives_module.__file__).read_text(encoding="utf-8")
        offenders: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name == _CONNECTION_PARAMETER_OWNER:
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "get"
                    and inner.args
                    and isinstance(inner.args[0], ast.Constant)
                    and inner.args[0].value in _CONNECTION_SETTING_KEYS
                ):
                    offenders.append(f"{node.name}:{inner.lineno}")
        assert offenders == [], (
            "connection settings may be read only by "
            f"{_CONNECTION_PARAMETER_OWNER}; direct readers: {offenders}"
        )

    @pytest.mark.parametrize(
        "builder_name",
        ["_build_pg_dump_command", "_build_pg_restore_command"],
    )
    def test_command_builders_delegate_to_the_connection_parameter_owner(
        self, builder_name: str
    ) -> None:
        source = Path(primitives_module.__file__).read_text(encoding="utf-8")
        builders = {
            node.name: node
            for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef)
        }
        builder = builders[builder_name]
        connection_parameter_name = builder.args.args[1].arg

        owner_calls = 0
        direct_reads: list[int] = []
        for inner in ast.walk(builder):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == _CONNECTION_PARAMETER_OWNER
            ):
                owner_calls += 1
            if (
                isinstance(inner, ast.Attribute)
                and inner.attr == "get"
                and isinstance(inner.value, ast.Name)
                and inner.value.id == connection_parameter_name
            ):
                direct_reads.append(inner.lineno)
            if (
                isinstance(inner, ast.Subscript)
                and isinstance(inner.value, ast.Name)
                and inner.value.id == connection_parameter_name
            ):
                direct_reads.append(inner.lineno)

        assert owner_calls == 1, (
            f"{builder_name} must call {_CONNECTION_PARAMETER_OWNER} exactly once"
        )
        assert direct_reads == [], (
            f"{builder_name} reads connection settings directly at lines "
            f"{direct_reads}; use {_CONNECTION_PARAMETER_OWNER} instead"
        )


class TestShellRunner:
    def test_run_shell_command_success(self) -> None:
        _run_shell_command(["echo", "ok"])

    def test_run_shell_command_with_env(self) -> None:
        _run_shell_command(["echo", "ok"], env={"EXTRA": "value"})

    def test_run_shell_command_failure_raises_backup_error(self) -> None:
        with pytest.raises(BackupError, match="Command failed"):
            _run_shell_command(["false"])

    def test_run_shell_command_missing_executable_raises(self) -> None:
        with pytest.raises(BackupError, match="not installed"):
            _run_shell_command(["__nonexistent_binary__"])

    def test_missing_executable_error_pg_dump_includes_guidance(self) -> None:
        err = _missing_executable_backup_error("pg_dump")
        assert "pg_dump" in str(err)
        assert "PostgreSQL 18" in str(err)

    def test_missing_executable_error_other_has_no_guidance(self) -> None:
        err = _missing_executable_backup_error("somebin")
        assert "somebin" in str(err)
        assert "PostgreSQL 18" not in str(err)


class TestGetPostgresqlToolVersion:
    def test_returns_version_string_for_existing_tool(self) -> None:
        version = _get_postgresql_tool_version("python")
        assert version

    def test_raises_for_nonexistent_executable(self) -> None:
        with pytest.raises(BackupError, match="not installed"):
            _get_postgresql_tool_version("__nonexistent_binary__42__")

    def test_raises_for_non_zero_return(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "some error"
            mock_run.return_value.stdout = ""
            with pytest.raises(BackupError, match="Unable to determine"):
                _get_postgresql_tool_version("pg_dump")

    def test_raises_when_output_is_empty(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            with pytest.raises(BackupError, match="command returned no output"):
                _get_postgresql_tool_version("pg_restore")

    def test_pg_dump_guidance_in_empty_output_error(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            with pytest.raises(BackupError, match="pg_dump"):
                _get_postgresql_tool_version("pg_dump")


class TestDumpPostgresql:
    def test_dump_postgresql_database_calls_shell_runner(self, tmp_path: Path) -> None:
        calls: list[tuple[list[str], dict[str, str] | None]] = []

        def fake_runner(
            command: list[str], *, env: dict[str, str] | None = None
        ) -> None:
            calls.append((command, env))

        _dump_postgresql_database(
            tmp_path / "dump.dump",
            {"NAME": "mydb", "HOST": "localhost", "PORT": "5432"},
            shell_runner=fake_runner,
        )
        assert len(calls) == 1
        assert "pg_dump" in calls[0][0]


class TestSnapshotStructure:
    def test_mint_snapshot_id_is_hex(self) -> None:
        snapshot_id = _mint_snapshot_id()
        assert len(snapshot_id) == 32
        int(snapshot_id, 16)

    def test_mint_snapshot_id_unique(self) -> None:
        assert _mint_snapshot_id() != _mint_snapshot_id()

    def test_relative_snapshot_child_path(self, tmp_path: Path) -> None:
        root = tmp_path / "snapshot"
        child = root / "database" / "dump.dump"
        rel = _relative_snapshot_child_path(root, child)
        assert rel == "database/dump.dump"

    def test_build_snapshot_child_descriptor_minimal(self) -> None:
        desc = _build_snapshot_child_descriptor(
            kind="database_dump",
            status="ready",
            relative_path="database/dump.dump",
        )
        assert desc["kind"] == "database_dump"
        assert desc["status"] == "ready"
        assert desc["relative_path"] == "database/dump.dump"
        assert desc["local_path"] == ""

    def test_build_snapshot_child_descriptor_with_optional_fields(
        self, tmp_path: Path
    ) -> None:
        local = tmp_path / "dump.dump"
        desc = _build_snapshot_child_descriptor(
            kind="database_dump",
            status="ready",
            relative_path="database/dump.dump",
            local_path=local,
            remote_key="remote/key",
            error="some error",
            size_bytes=1024,
            checksum_sha256="abc123",
            metadata={"format": "pg_dump_custom"},
        )
        assert desc["local_path"] == str(local)
        assert desc["remote_key"] == "remote/key"
        assert desc["error"] == "some error"
        assert desc["size_bytes"] == 1024
        assert desc["checksum_sha256"] == "abc123"
        assert desc["metadata"] == {"format": "pg_dump_custom"}

    def test_write_json_file(self, tmp_path: Path) -> None:
        target = tmp_path / "sub" / "file.json"
        payload = {"key": "value", "num": 42}
        _write_json_file(target, payload)
        assert target.exists()
        loaded = json.loads(target.read_text())
        assert loaded == payload

    def test_write_json_file_creates_parents(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c" / "file.json"
        _write_json_file(target, {"x": 1})
        assert target.exists()


class TestComputeSha256:
    def test_compute_sha256_matches_hashlib(self, tmp_path: Path) -> None:
        content = b"hello world"
        f = tmp_path / "test.bin"
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert _compute_sha256(f) == expected


class TestGuidanceText:
    def test_guidance_mentions_postgresql_18(self) -> None:
        guidance = _postgresql_18_client_tooling_guidance()
        assert "18" in guidance
        assert "pg_dump" in guidance
