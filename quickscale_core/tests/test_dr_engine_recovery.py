"""Tests for the DR engine restore/orchestration recovery and verification modules."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from quickscale_core.dr_engine.primitives import (
    BackupConfigurationError,
    BackupError,
    _POSTGRESQL_CUSTOM_ARCHIVE_MAGIC,
    _REQUIRED_POSTGRESQL_MAJOR,
)
from quickscale_core.dr_engine.recovery import (
    ArtifactLike,
    BackupRestoreBlocked,
    RemoteMaterializer,
    ResolvedRestoreSource,
    RestoreResult,
    RestoreSourceResolutionMode,
    RestoreWarning,
    _collect_local_backup_validation_issues,
    _detect_restore_file_format,
    _ensure_operator_supplied_custom_archive_valid,
    _ensure_postgresql_18_restore_runtime,
    _execute_restore_for_resolved_source,
    _get_restore_compatibility_issues,
    _get_restore_source_compatibility_issues,
    _get_restore_source_validation_issues,
    _normalize_restore_file_path,
    _resolve_restore_source,
    _restore_execution_allowed,
)
from quickscale_core.dr_engine.verification import (
    _build_clear_rollback_pin_fields,
    _build_verification_payload,
    _compute_rollback_pin_fields,
    _validate_verification_inputs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_restore_source(tmp_path: Path) -> ResolvedRestoreSource:
    """A minimal resolved restore source backed by a real temp file."""
    dump_file = tmp_path / "test-backup.dump"
    dump_file.write_text("not a real pg dump")
    return ResolvedRestoreSource(
        confirmation_value="test-backup.dump",
        local_path=dump_file,
        backup_format="pg_dump_custom",
    )


class FakeArtifact:
    """Minimal ArtifactLike implementation for testing recovery helpers."""

    def __init__(
        self,
        *,
        backup_format: str = "pg_dump_custom",
        database_engine: str = "django.db.backends.postgresql",
        checksum_sha256: str = "",
        size_bytes: int | None = None,
        filename: str = "fake-artifact.dump",
        local_path: str = "",
        remote_key: str = "",
        database_server_major: int | None = _REQUIRED_POSTGRESQL_MAJOR,
        dump_client_major: int | None = _REQUIRED_POSTGRESQL_MAJOR,
        export_only: bool = False,
    ) -> None:
        self.backup_format = backup_format
        self.database_engine = database_engine
        self.checksum_sha256 = checksum_sha256
        self.size_bytes = size_bytes
        self.filename = filename
        self.local_path = local_path
        self.remote_key = remote_key
        self.database_server_major = database_server_major
        self.dump_client_major = dump_client_major
        self._export_only = export_only

    def is_export_only(self) -> bool:
        return self._export_only


# ---------------------------------------------------------------------------
# Test: Error class
# ---------------------------------------------------------------------------


class TestBackupRestoreBlocked:
    def test_is_backup_error_subclass(self) -> None:
        exc = BackupRestoreBlocked("blocked")
        assert isinstance(exc, BackupError)
        assert str(exc) == "blocked"


# ---------------------------------------------------------------------------
# Test: Data contracts
# ---------------------------------------------------------------------------


class TestRestoreWarning:
    def test_minimal(self) -> None:
        w = RestoreWarning(code="test", message="test message")
        assert w.code == "test"
        assert w.message == "test message"
        assert w.details is None

    def test_with_details(self) -> None:
        w = RestoreWarning(
            code="test",
            message="test message",
            details={"key": "value"},
        )
        assert w.details == {"key": "value"}


class TestRestoreSourceResolutionMode:
    def test_values(self) -> None:
        assert RestoreSourceResolutionMode.REMOTE_FALLBACK.value == "remote_fallback"
        assert RestoreSourceResolutionMode.LOCAL_ONLY.value == "local_only"


class TestRestoreResult:
    def test_minimal_executed(self) -> None:
        r = RestoreResult(executed=True, dry_run=False, message="done")
        assert r.executed
        assert not r.dry_run
        assert r.warnings == ()

    def test_with_warnings(self) -> None:
        w = RestoreWarning(code="w", message="warn")
        r = RestoreResult(
            executed=True,
            dry_run=False,
            message="done with warnings",
            warnings=(w,),
        )
        assert len(r.warnings) == 1


class TestResolvedRestoreSource:
    def test_minimal(self) -> None:
        src = ResolvedRestoreSource(
            confirmation_value="file.dump",
            local_path=Path("/tmp/file.dump"),
            backup_format="pg_dump_custom",
        )
        assert not src.is_export_only()

    def test_export_only_json_no_artifact(self) -> None:
        src = ResolvedRestoreSource(
            confirmation_value="file.json",
            local_path=Path("/tmp/file.json"),
            backup_format="json",
        )
        assert src.is_export_only()

    def test_export_only_via_artifact(self) -> None:
        artifact = FakeArtifact(export_only=True)
        src = ResolvedRestoreSource(
            confirmation_value="file.dump",
            local_path=Path("/tmp/file.dump"),
            backup_format="pg_dump_custom",
            artifact=artifact,
        )
        assert src.is_export_only()

    def test_not_export_only_via_artifact(self) -> None:
        artifact = FakeArtifact(export_only=False)
        src = ResolvedRestoreSource(
            confirmation_value="file.dump",
            local_path=Path("/tmp/file.dump"),
            backup_format="pg_dump_custom",
            artifact=artifact,
        )
        assert not src.is_export_only()


# ---------------------------------------------------------------------------
# Test: ArtifactLike protocol conformance
# ---------------------------------------------------------------------------


class TestArtifactLikeProtocol:
    def test_fake_artifact_satisfies_protocol(self) -> None:
        artifact: ArtifactLike = FakeArtifact()
        assert artifact.backup_format == "pg_dump_custom"


# ---------------------------------------------------------------------------
# Test: Path helpers
# ---------------------------------------------------------------------------


class TestNormalizeRestoreFilePath:
    def test_absolute_path_unchanged(self) -> None:
        result = _normalize_restore_file_path("/absolute/path.dump")
        assert result == Path("/absolute/path.dump")

    def test_relative_path_resolved(self) -> None:
        result = _normalize_restore_file_path("relative.dump")
        assert result == Path.cwd() / "relative.dump"

    def test_expands_user(self) -> None:
        result = _normalize_restore_file_path("~/test.dump")
        assert str(result).startswith(str(Path.home()))


class TestDetectRestoreFileFormat:
    def test_json_suffix(self) -> None:
        assert _detect_restore_file_format(Path("backup.json")) == "json"

    def test_json_uppercase_suffix(self) -> None:
        assert _detect_restore_file_format(Path("backup.JSON")) == "json"

    def test_dump_suffix(self) -> None:
        assert _detect_restore_file_format(Path("backup.dump")) == "pg_dump_custom"

    def test_no_suffix(self) -> None:
        assert _detect_restore_file_format(Path("backup")) == "pg_dump_custom"


# ---------------------------------------------------------------------------
# Test: Validation helpers
# ---------------------------------------------------------------------------


class TestCollectLocalBackupValidationIssues:
    def test_none_path_returns_missing(self) -> None:
        issues = _collect_local_backup_validation_issues(
            None,
            backup_format="pg_dump_custom",
        )
        assert "local backup artifact is missing" in issues

    def test_missing_file(self) -> None:
        issues = _collect_local_backup_validation_issues(
            Path("/nonexistent/file.dump"),
            backup_format="pg_dump_custom",
        )
        assert "local backup artifact is missing" in issues

    def test_checksum_match(self, tmp_path: Path) -> None:
        f = tmp_path / "test.dump"
        f.write_text("content")
        from quickscale_core.dr_engine.primitives import _compute_sha256

        expected = _compute_sha256(f)
        issues = _collect_local_backup_validation_issues(
            f,
            backup_format="pg_dump_custom",
            expected_checksum=expected,
        )
        assert issues == []

    def test_checksum_mismatch(self, tmp_path: Path) -> None:
        f = tmp_path / "test.dump"
        f.write_text("content")
        issues = _collect_local_backup_validation_issues(
            f,
            backup_format="pg_dump_custom",
            expected_checksum="wrongchecksum",
        )
        assert "checksum mismatch detected" in issues

    def test_size_match(self, tmp_path: Path) -> None:
        f = tmp_path / "test.dump"
        f.write_text("12345")
        issues = _collect_local_backup_validation_issues(
            f,
            backup_format="pg_dump_custom",
            expected_size=5,
        )
        assert issues == []

    def test_size_mismatch(self, tmp_path: Path) -> None:
        f = tmp_path / "test.dump"
        f.write_text("12345")
        issues = _collect_local_backup_validation_issues(
            f,
            backup_format="pg_dump_custom",
            expected_size=99,
        )
        assert "size mismatch detected" in issues

    def test_valid_json_format(self, tmp_path: Path) -> None:
        f = tmp_path / "data.json"
        f.write_text(json.dumps({"key": "value"}))
        issues = _collect_local_backup_validation_issues(
            f,
            backup_format="json",
        )
        assert issues == []

    def test_invalid_json_format(self, tmp_path: Path) -> None:
        f = tmp_path / "data.json"
        f.write_text("not valid json")
        issues = _collect_local_backup_validation_issues(
            f,
            backup_format="json",
        )
        assert any("JSON" in issue for issue in issues)


class TestGetRestoreSourceValidationIssues:
    def test_missing_artifact_local_file(self, tmp_path: Path) -> None:
        artifact = FakeArtifact(checksum_sha256="abc", size_bytes=10)
        src = ResolvedRestoreSource(
            confirmation_value="test.dump",
            local_path=tmp_path / "nonexistent.dump",
            backup_format="pg_dump_custom",
            artifact=artifact,
        )
        issues = _get_restore_source_validation_issues(src)
        assert "local backup artifact is missing" in issues

    def test_operator_supplied_file_not_found(self) -> None:
        src = ResolvedRestoreSource(
            confirmation_value="missing.dump",
            local_path=Path("/nonexistent/file.dump"),
            backup_format="pg_dump_custom",
        )
        issues = _get_restore_source_validation_issues(src)
        assert any("not found" in issue for issue in issues)

    def test_valid_operator_supplied_file(self, tmp_path: Path) -> None:
        f = tmp_path / "valid.dump"
        f.write_text("content")
        src = ResolvedRestoreSource(
            confirmation_value="valid.dump",
            local_path=f,
            backup_format="pg_dump_custom",
        )
        issues = _get_restore_source_validation_issues(src)
        assert issues == []


# ---------------------------------------------------------------------------
# Test: Compatibility helpers
# ---------------------------------------------------------------------------


class TestGetRestoreCompatibilityIssues:
    def test_compatible_postgresql(self) -> None:
        artifact = FakeArtifact(
            database_engine="django.db.backends.postgresql",
            backup_format="pg_dump_custom",
        )
        issues = _get_restore_compatibility_issues(
            artifact, "django.db.backends.postgresql"
        )
        assert issues == []

    def test_engine_mismatch(self) -> None:
        artifact = FakeArtifact(
            database_engine="django.db.backends.postgresql",
            backup_format="pg_dump_custom",
        )
        issues = _get_restore_compatibility_issues(
            artifact, "django.db.backends.sqlite3"
        )
        assert any("incompatible" in issue for issue in issues)

    def test_format_mismatch(self) -> None:
        artifact = FakeArtifact(
            database_engine="django.db.backends.postgresql",
            backup_format="json",
        )
        issues = _get_restore_compatibility_issues(
            artifact, "django.db.backends.postgresql"
        )
        assert any("format" in issue for issue in issues)

    def test_server_major_mismatch(self) -> None:
        artifact = FakeArtifact(
            database_engine="django.db.backends.postgresql",
            backup_format="pg_dump_custom",
            database_server_major=15,
        )
        issues = _get_restore_compatibility_issues(
            artifact, "django.db.backends.postgresql"
        )
        assert any("server major" in issue for issue in issues)

    def test_dump_client_major_mismatch(self) -> None:
        artifact = FakeArtifact(
            database_engine="django.db.backends.postgresql",
            backup_format="pg_dump_custom",
            database_server_major=_REQUIRED_POSTGRESQL_MAJOR,
            dump_client_major=15,
        )
        issues = _get_restore_compatibility_issues(
            artifact, "django.db.backends.postgresql"
        )
        assert any("client major" in issue for issue in issues)


class TestGetRestoreSourceCompatibilityIssues:
    def test_artifact_delegates_to_compatibility_issues(self) -> None:
        artifact = FakeArtifact(
            database_engine="django.db.backends.postgresql",
            backup_format="pg_dump_custom",
        )
        src = ResolvedRestoreSource(
            confirmation_value="test.dump",
            local_path=Path("/tmp/test.dump"),
            backup_format="pg_dump_custom",
            artifact=artifact,
        )
        issues = _get_restore_source_compatibility_issues(
            src, "django.db.backends.postgresql"
        )
        assert issues == []

    def test_operator_supplied_non_postgresql(self) -> None:
        src = ResolvedRestoreSource(
            confirmation_value="test.dump",
            local_path=Path("/tmp/test.dump"),
            backup_format="pg_dump_custom",
        )
        issues = _get_restore_source_compatibility_issues(
            src, "django.db.backends.sqlite3"
        )
        assert "PostgreSQL" in issues[0]

    def test_operator_supplied_postgresql_allowed(self) -> None:
        src = ResolvedRestoreSource(
            confirmation_value="test.dump",
            local_path=Path("/tmp/test.dump"),
            backup_format="pg_dump_custom",
        )
        issues = _get_restore_source_compatibility_issues(
            src, "django.db.backends.postgresql"
        )
        assert issues == []


# ---------------------------------------------------------------------------
# Test: Operator-supplied custom archive validation
# ---------------------------------------------------------------------------


class TestEnsureOperatorSuppliedCustomArchiveValid:
    def test_skipped_when_artifact_present(self, tmp_path: Path) -> None:
        artifact = FakeArtifact()
        src = ResolvedRestoreSource(
            confirmation_value="test.dump",
            local_path=tmp_path / "test.dump",
            backup_format="pg_dump_custom",
            artifact=artifact,
        )
        # Should not raise for artifact sources
        _ensure_operator_supplied_custom_archive_valid(src)

    def test_skipped_for_json_format(self, tmp_path: Path) -> None:
        src = ResolvedRestoreSource(
            confirmation_value="test.json",
            local_path=tmp_path / "test.json",
            backup_format="json",
        )
        _ensure_operator_supplied_custom_archive_valid(src)

    def test_raises_for_non_pgdmp_magic(self, tmp_path: Path) -> None:
        f = tmp_path / "test.dump"
        f.write_text("not a pgdump")
        src = ResolvedRestoreSource(
            confirmation_value="test.dump",
            local_path=f,
            backup_format="pg_dump_custom",
        )
        with pytest.raises(
            BackupRestoreBlocked, match="not a valid PostgreSQL custom archive"
        ):
            _ensure_operator_supplied_custom_archive_valid(src)

    def test_passes_for_pgdmp_magic(self, tmp_path: Path) -> None:
        f = tmp_path / "test.dump"
        f.write_bytes(_POSTGRESQL_CUSTOM_ARCHIVE_MAGIC + b"rest")
        src = ResolvedRestoreSource(
            confirmation_value="test.dump",
            local_path=f,
            backup_format="pg_dump_custom",
        )
        with patch("quickscale_core.dr_engine.recovery._run_shell_command") as mock_run:
            _ensure_operator_supplied_custom_archive_valid(src)
            mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# Test: PostgreSQL 18 restore runtime
# ---------------------------------------------------------------------------


class TestEnsurePostgresql18RestoreRuntime:
    def test_skipped_non_postgresql(self) -> None:
        # No raise for non-postgresql when no contract checker is provided
        _ensure_postgresql_18_restore_runtime("django.db.backends.sqlite3")

    def test_postgresql_with_valid_contract(self) -> None:
        def fake_contract(
            database_engine: str, executable: str, operation: str
        ) -> tuple[str, int, str, int]:
            return ("18.0", 18, "pg_restore (PostgreSQL) 18.0", 18)

        _ensure_postgresql_18_restore_runtime(
            "django.db.backends.postgresql",
            require_contract=fake_contract,
        )

    def test_postgresql_with_failing_contract(self) -> None:
        def failing_contract(
            database_engine: str, executable: str, operation: str
        ) -> tuple[str, int, str, int]:
            raise BackupError("Version mismatch")

        with pytest.raises(BackupRestoreBlocked, match="Version mismatch"):
            _ensure_postgresql_18_restore_runtime(
                "django.db.backends.postgresql",
                require_contract=failing_contract,
            )


# ---------------------------------------------------------------------------
# Test: Restore execution gate
# ---------------------------------------------------------------------------


class TestRestoreExecutionAllowed:
    def test_debug_allows(self) -> None:
        assert _restore_execution_allowed(is_debug=True) is True

    def test_non_debug_without_env_var(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            assert _restore_execution_allowed(is_debug=False) is False

    def test_non_debug_with_env_var(self) -> None:
        with patch.dict(
            "os.environ",
            {"QUICKSCALE_BACKUPS_ALLOW_RESTORE": "true"},
        ):
            assert _restore_execution_allowed(is_debug=False) is True

    def test_env_var_case_insensitive(self) -> None:
        with patch.dict(
            "os.environ",
            {"QUICKSCALE_BACKUPS_ALLOW_RESTORE": "True"},
        ):
            assert _restore_execution_allowed(is_debug=False) is True

    def test_env_var_false_value(self) -> None:
        with patch.dict(
            "os.environ",
            {"QUICKSCALE_BACKUPS_ALLOW_RESTORE": "false"},
        ):
            assert _restore_execution_allowed(is_debug=False) is False


# ---------------------------------------------------------------------------
# Test: Restore source resolution
# ---------------------------------------------------------------------------


class TestResolveRestoreSource:
    def test_no_source_raises(self) -> None:
        with pytest.raises(
            BackupRestoreBlocked, match="Choose exactly one restore source"
        ):
            with _resolve_restore_source():
                pass  # pragma: no cover

    def test_multiple_sources_raises(self) -> None:
        fake_artifact = FakeArtifact()
        with pytest.raises(
            BackupRestoreBlocked, match="Choose exactly one restore source"
        ):
            with _resolve_restore_source(
                artifact=fake_artifact,
                file_path="/tmp/test.dump",
            ):
                pass  # pragma: no cover

    def test_file_path_resolution(self) -> None:
        with _resolve_restore_source(file_path="/absolute/path.dump") as src:
            assert src.confirmation_value == "path.dump"
            assert str(src.local_path) == "/absolute/path.dump"
            assert src.backup_format == "pg_dump_custom"

    def test_file_path_json(self) -> None:
        with _resolve_restore_source(file_path="/absolute/data.json") as src:
            assert src.backup_format == "json"

    def test_snapshot_without_resolver_raises(self) -> None:
        with pytest.raises(
            BackupRestoreBlocked, match="snapshot resolution is not available"
        ):
            with _resolve_restore_source(snapshot_id="snap-123"):
                pass  # pragma: no cover

    def test_snapshot_with_resolver(self) -> None:
        def resolver(snapshot_id: str) -> FakeArtifact:
            return FakeArtifact(
                local_path="/tmp/existing.dump",
                filename="existing.dump",
            )

        with patch.object(Path, "exists", return_value=True):
            with _resolve_restore_source(
                snapshot_id="snap-123",
                snapshot_resolver=resolver,
            ) as src:
                assert src.confirmation_value == "existing.dump"
                assert src.backup_format == "pg_dump_custom"

    def test_artifact_local_path_exists(self, tmp_path: Path) -> None:
        dump_file = tmp_path / "local.dump"
        dump_file.write_text("content")
        artifact = FakeArtifact(
            local_path=str(dump_file),
            filename="local.dump",
        )
        with _resolve_restore_source(artifact=artifact) as src:
            assert src.confirmation_value == "local.dump"
            assert src.local_path == dump_file

    def test_artifact_local_missing_remote_fallback_no_materializer(self) -> None:
        artifact = FakeArtifact(
            local_path="/nonexistent.dump",
            remote_key="remote/key",
        )
        with pytest.raises(
            BackupRestoreBlocked,
            match="remote materialization is not available",
        ):
            with _resolve_restore_source(
                artifact=artifact,
                resolution_mode=RestoreSourceResolutionMode.REMOTE_FALLBACK,
            ):
                pass  # pragma: no cover

    def test_artifact_local_missing_local_only_raises(self) -> None:
        artifact = FakeArtifact(
            local_path="/nonexistent.dump",
        )
        with pytest.raises(
            BackupRestoreBlocked,
            match="local backup artifact is missing",
        ):
            with _resolve_restore_source(
                artifact=artifact,
                resolution_mode=RestoreSourceResolutionMode.LOCAL_ONLY,
            ):
                pass  # pragma: no cover

    def test_artifact_local_missing_no_remote_key_raises(self) -> None:
        artifact = FakeArtifact(
            local_path="/nonexistent.dump",
            remote_key="",
        )
        with pytest.raises(
            BackupRestoreBlocked,
            match="no private remote artifact is available",
        ):
            with _resolve_restore_source(
                artifact=artifact,
                resolution_mode=RestoreSourceResolutionMode.REMOTE_FALLBACK,
            ):
                pass  # pragma: no cover

    def test_remote_materialization_success(self, tmp_path: Path) -> None:
        dest = tmp_path / "materialized.dump"
        dest.write_text("restored content")

        def materializer(remote_key: str, policy: Any, destination: Path) -> None:
            destination.write_text("restored content")

        artifact = FakeArtifact(
            local_path="",
            filename="materialized.dump",
            remote_key="remote/key",
        )

        with _resolve_restore_source(
            artifact=artifact,
            remote_materializer=materializer,
        ) as src:
            assert src.confirmation_value == "materialized.dump"
            assert src.local_path.exists()

    def test_remote_materialization_failure(self) -> None:
        def failing_materializer(
            remote_key: str, policy: Any, destination: Path
        ) -> None:
            raise BackupError("Network error")

        artifact = FakeArtifact(
            local_path="",
            filename="fail.dump",
            remote_key="remote/key",
        )

        with pytest.raises(
            BackupRestoreBlocked,
            match="remote materialization failed",
        ):
            with _resolve_restore_source(
                artifact=artifact,
                remote_materializer=failing_materializer,
            ):
                pass  # pragma: no cover


# ---------------------------------------------------------------------------
# Test: ArtifactLike protocol — RemoteMaterializer protocol
# ---------------------------------------------------------------------------


class TestRemoteMaterializerProtocol:
    def test_callable_satisfies_protocol(self) -> None:
        def valid_materializer(remote_key: str, policy: Any, destination: Path) -> None:
            pass

        materializer: RemoteMaterializer = valid_materializer
        assert callable(materializer)


# ---------------------------------------------------------------------------
# Test: Verification payload assembly
# ---------------------------------------------------------------------------


class TestBuildVerificationPayload:
    """Tests for ``_build_verification_payload`` — pure dict assembly."""

    def test_minimal_payload(self) -> None:
        now_iso = "2026-06-22T12:00:00+00:00"
        payload = _build_verification_payload(
            snapshot_id="snap-abc123",
            project_slug="myapp",
            source_environment="local",
            captured_at="2026-06-22T10:00:00+00:00",
            status="manual_required",
            updated_at=now_iso,
            full_backup_contract={"status": "complete", "completeness": {"issues": []}},
            existing_reports=[],
            existing_notes="Reserved for route-specific plan and execute reports.",
            rollback_pin_active=False,
            rollback_pin_expires_at=None,
            rollback_pin_reason="",
            route="local-to-railway-develop",
            phase="plan",
            payload={"database": {"status": "ready"}},
        )

        assert payload["manifest_version"] == 1
        assert payload["snapshot_id"] == "snap-abc123"
        assert payload["status"] == "manual_required"
        assert payload["rollback_pin"]["active"] is False
        assert payload["rollback_pin"]["expires_at"] is None
        assert len(payload["reports"]) == 1
        assert payload["reports"][0]["route"] == "local-to-railway-develop"
        assert payload["reports"][0]["phase"] == "plan"
        assert payload["reports"][0]["payload"]["database"]["status"] == "ready"
        assert payload["full_backup"]["status"] == "complete"

    def test_appends_to_existing_reports(self) -> None:
        existing_report = {
            "route": "previous-route",
            "phase": "plan",
            "status": "verified",
            "recorded_at": "2026-06-22T11:00:00+00:00",
        }
        now_iso = "2026-06-22T12:00:00+00:00"
        payload = _build_verification_payload(
            snapshot_id="snap-abc123",
            project_slug="myapp",
            source_environment="local",
            captured_at="2026-06-22T10:00:00+00:00",
            status="ready",
            updated_at=now_iso,
            full_backup_contract={"status": "complete"},
            existing_reports=[existing_report],
            existing_notes="Reserved for route-specific plan and execute reports.",
            rollback_pin_active=True,
            rollback_pin_expires_at="2026-06-23T12:00:00+00:00",
            rollback_pin_reason="production rollback window",
            route="local-to-railway-develop",
            phase="execute",
            payload={},
        )

        assert len(payload["reports"]) == 2
        assert payload["reports"][0]["route"] == "previous-route"
        assert payload["reports"][1]["route"] == "local-to-railway-develop"
        assert payload["rollback_pin"]["active"] is True
        assert payload["rollback_pin"]["expires_at"] == "2026-06-23T12:00:00+00:00"

    def test_rollback_pin_active_true(self) -> None:
        payload = _build_verification_payload(
            snapshot_id="snap-active-pin",
            project_slug="myapp",
            source_environment="local",
            captured_at="2026-06-22T10:00:00+00:00",
            status="ready",
            updated_at="2026-06-22T12:00:00+00:00",
            full_backup_contract={"status": "complete"},
            existing_reports=[],
            existing_notes="",
            rollback_pin_active=True,
            rollback_pin_expires_at="2026-06-23T12:00:00+00:00",
            rollback_pin_reason="deployment window",
            route="test-route",
            phase="plan",
            payload={},
        )
        assert payload["rollback_pin"]["active"] is True
        assert payload["rollback_pin"]["expires_at"] == "2026-06-23T12:00:00+00:00"
        assert payload["rollback_pin"]["reason"] == "deployment window"

    def test_preserves_captured_at_from_existing_payload(self) -> None:
        payload = _build_verification_payload(
            snapshot_id="snap-preserve-captured",
            project_slug="myapp",
            source_environment="local",
            captured_at="2026-05-01T00:00:00+00:00",
            status="ready",
            updated_at="2026-06-22T12:00:00+00:00",
            full_backup_contract={"status": "complete"},
            existing_reports=[],
            existing_notes="",
            rollback_pin_active=False,
            rollback_pin_expires_at=None,
            rollback_pin_reason="",
            route="test-route",
            phase="plan",
            payload={},
        )
        assert payload["captured_at"] == "2026-05-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Test: Rollback-pin field computation
# ---------------------------------------------------------------------------


class TestComputeRollbackPinFields:
    """Tests for ``_compute_rollback_pin_fields`` — pure field computation."""

    def test_computes_expiry(self) -> None:
        now = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)
        fields = _compute_rollback_pin_fields(
            ttl_hours=6,
            reason="production rollback window",
            now=now,
        )

        assert fields["rollback_pin_reason"] == "production rollback window"
        assert fields["rollback_pin_expires_at"] == now + timedelta(hours=6)

    def test_rejects_ttl_below_one(self) -> None:
        with pytest.raises(
            BackupConfigurationError, match="ttl_hours must be at least 1"
        ):
            _compute_rollback_pin_fields(
                ttl_hours=0,
                reason="test reason",
                now=datetime.now(timezone.utc),
            )

    def test_rejects_blank_reason(self) -> None:
        with pytest.raises(BackupConfigurationError, match="reason cannot be blank"):
            _compute_rollback_pin_fields(
                ttl_hours=6,
                reason="  ",
                now=datetime.now(timezone.utc),
            )

    def test_strips_reason_whitespace(self) -> None:
        fields = _compute_rollback_pin_fields(
            ttl_hours=2,
            reason="  deploy window  ",
            now=datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc),
        )
        assert fields["rollback_pin_reason"] == "deploy window"


class TestBuildClearRollbackPinFields:
    """Tests for ``_build_clear_rollback_pin_fields`` — pure field computation."""

    def test_returns_cleared_fields(self) -> None:
        fields = _build_clear_rollback_pin_fields()
        assert fields["rollback_pin_expires_at"] is None
        assert fields["rollback_pin_reason"] == ""


# ---------------------------------------------------------------------------
# Test: Verification input validation
# ---------------------------------------------------------------------------


class TestValidateVerificationInputs:
    """Tests for ``_validate_verification_inputs``."""

    def test_passes_valid_inputs(self) -> None:
        # Should not raise
        _validate_verification_inputs(
            route="local-to-railway-develop",
            phase="plan",
            status="manual_required",
        )

    def test_rejects_blank_route(self) -> None:
        with pytest.raises(BackupConfigurationError, match="route cannot be blank"):
            _validate_verification_inputs(
                route="  ",
                phase="plan",
                status="ready",
            )

    def test_rejects_blank_phase(self) -> None:
        with pytest.raises(BackupConfigurationError, match="phase cannot be blank"):
            _validate_verification_inputs(
                route="test-route",
                phase="",
                status="ready",
            )

    def test_rejects_blank_status(self) -> None:
        with pytest.raises(BackupConfigurationError, match="status cannot be blank"):
            _validate_verification_inputs(
                route="test-route",
                phase="plan",
                status="  ",
            )


# ---------------------------------------------------------------------------
# Test: _execute_restore_for_resolved_source
# ---------------------------------------------------------------------------


class TestExecuteRestoreForResolvedSource:
    """Tests for ``_execute_restore_for_resolved_source`` — guarded pipeline."""

    def test_confirmation_mismatch_raises(
        self, sample_restore_source: ResolvedRestoreSource
    ) -> None:
        with pytest.raises(
            BackupRestoreBlocked, match="Confirmation must exactly match"
        ):
            _execute_restore_for_resolved_source(
                sample_restore_source,
                confirmation="wrong-name",
                dry_run=True,
                allow_production=False,
            )

    def test_export_only_json_no_artifact_raises(self, tmp_path: Path) -> None:
        json_file = tmp_path / "export.json"
        json_file.write_text(json.dumps({"key": "value"}))
        src = ResolvedRestoreSource(
            confirmation_value="export.json",
            local_path=json_file,
            backup_format="json",
        )
        with pytest.raises(
            BackupRestoreBlocked, match="JSON file inputs are not a supported"
        ):
            _execute_restore_for_resolved_source(
                src,
                confirmation="export.json",
                dry_run=True,
                allow_production=False,
            )

    def test_export_only_artifact_raises(self, tmp_path: Path) -> None:
        dump_file = tmp_path / "export.dump"
        dump_file.write_text("content")
        artifact = FakeArtifact(export_only=True)
        src = ResolvedRestoreSource(
            confirmation_value="export.dump",
            local_path=dump_file,
            backup_format="pg_dump_custom",
            artifact=artifact,
        )
        with pytest.raises(
            BackupRestoreBlocked, match="export_only artifacts are not a supported"
        ):
            _execute_restore_for_resolved_source(
                src,
                confirmation="export.dump",
                dry_run=True,
                allow_production=False,
            )

    def test_source_validation_failure_raises(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "nonexistent.dump"
        src = ResolvedRestoreSource(
            confirmation_value="nonexistent.dump",
            local_path=missing_path,
            backup_format="pg_dump_custom",
        )
        with pytest.raises(BackupRestoreBlocked, match="backup validation failed"):
            _execute_restore_for_resolved_source(
                src,
                confirmation="nonexistent.dump",
                dry_run=True,
                allow_production=False,
            )

    def test_dry_run_passes_validation(self, tmp_path: Path) -> None:
        dump_file = tmp_path / "test-backup.dump"
        dump_file.write_bytes(_POSTGRESQL_CUSTOM_ARCHIVE_MAGIC + b"rest")
        src = ResolvedRestoreSource(
            confirmation_value="test-backup.dump",
            local_path=dump_file,
            backup_format="pg_dump_custom",
        )
        with patch("quickscale_core.dr_engine.recovery._run_shell_command") as mock_run:
            result = _execute_restore_for_resolved_source(
                src,
                confirmation="test-backup.dump",
                dry_run=True,
                allow_production=False,
            )
            # The dry run path calls _ensure_operator_supplied_custom_archive_valid
            # which calls _run_shell_command for pg_restore --list
            mock_run.assert_called_once()
        assert result.executed is False
        assert result.dry_run is True
        assert "Restore validation completed successfully" in result.message

    def test_execution_blocked_when_env_gate_closed(self, tmp_path: Path) -> None:
        dump_file = tmp_path / "test-backup.dump"
        dump_file.write_bytes(_POSTGRESQL_CUSTOM_ARCHIVE_MAGIC + b"rest")
        src = ResolvedRestoreSource(
            confirmation_value="test-backup.dump",
            local_path=dump_file,
            backup_format="pg_dump_custom",
        )
        with patch("quickscale_core.dr_engine.recovery._run_shell_command"):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(
                    BackupRestoreBlocked,
                    match="Restore execution is blocked",
                ):
                    _execute_restore_for_resolved_source(
                        src,
                        confirmation="test-backup.dump",
                        dry_run=False,
                        allow_production=False,
                        is_debug=False,
                    )

    def test_execution_blocked_non_pgdmp_format(self, tmp_path: Path) -> None:
        json_file = tmp_path / "data.json"
        content = json.dumps({"key": "value"})
        json_file.write_text(content)
        from quickscale_core.dr_engine.primitives import _compute_sha256

        checksum = _compute_sha256(json_file)
        src = ResolvedRestoreSource(
            confirmation_value="data.json",
            local_path=json_file,
            backup_format="json",
            artifact=FakeArtifact(
                backup_format="json",
                export_only=False,
                checksum_sha256=checksum,
                size_bytes=len(content),
            ),
        )
        # For json format without export-only and with matching checksum,
        # source validation passes but execution is blocked
        # because executable restore requires pg_dump_custom format.
        with patch.dict("os.environ", {"QUICKSCALE_BACKUPS_ALLOW_RESTORE": "true"}):
            with pytest.raises(
                BackupRestoreBlocked,
                match="Executable restore is only supported for PostgreSQL",
            ):
                _execute_restore_for_resolved_source(
                    src,
                    confirmation="data.json",
                    dry_run=False,
                    allow_production=True,
                )

    def test_execution_success(self, tmp_path: Path) -> None:
        dump_file = tmp_path / "test-backup.dump"
        dump_file.write_bytes(_POSTGRESQL_CUSTOM_ARCHIVE_MAGIC + b"rest")
        src = ResolvedRestoreSource(
            confirmation_value="test-backup.dump",
            local_path=dump_file,
            backup_format="pg_dump_custom",
        )
        with (
            patch("quickscale_core.dr_engine.recovery._run_shell_command") as mock_run,
            patch.dict(
                "os.environ",
                {"QUICKSCALE_BACKUPS_ALLOW_RESTORE": "true"},
            ),
        ):
            result = _execute_restore_for_resolved_source(
                src,
                confirmation="test-backup.dump",
                dry_run=False,
                allow_production=True,
                current_engine="django.db.backends.postgresql",
                connection_settings={
                    "HOST": "localhost",
                    "PORT": 5432,
                    "USER": "test",
                    "NAME": "testdb",
                },
            )

        assert result.executed is True
        assert result.dry_run is False
        assert "Restore executed" in result.message
        mock_run.assert_called()
