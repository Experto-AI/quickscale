"""Pure-mock A-II coverage for restore, admin upload, verification, and pins."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.dr_engine import orchestration as orch
from quickscale_core.dr_engine.primitives import (
    BackupError,
    ShellCommandRunner,
)
from quickscale_core.dr_engine.recovery import (
    ArtifactLike,
    BackupRestoreBlocked,
    ResolvedRestoreSource,
    RestoreResult,
    RestoreSourceResolutionMode,
    RestoreWarning,
)


_ORCH = "quickscale_core.dr_engine.orchestration"
_NOW = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)


def _artifact(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "filename": "trusted.dump",
        "local_path": "/tmp/trusted.dump",
        "backup_format": "pg_dump_custom",
        "database_engine": "django.db.backends.postgresql",
        "checksum_sha256": "checksum",
        "size_bytes": 8,
        "remote_key": "",
        "status": "validated",
        "restore_started_at": None,
        "validated_at": None,
        "validation_notes": "",
        "restored_at": None,
        "is_export_only": lambda: False,
    }
    return SimpleNamespace(**(values | overrides))


def _snapshot(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "snapshot_id": "snap-b2",
        "status": "ready",
        "source_environment": "local",
        "authoritative_dump": _artifact(),
        "created_at": _NOW - timedelta(hours=1),
        "rollback_pin_expires_at": None,
        "rollback_pin_reason": "",
        "has_active_rollback_pin": lambda now=None: False,
    }
    return SimpleNamespace(**(values | overrides))


def _source(path: Path, artifact: object | None = None) -> ResolvedRestoreSource:
    return ResolvedRestoreSource(
        confirmation_value=path.name,
        local_path=path,
        backup_format="pg_dump_custom",
        artifact=cast(ArtifactLike | None, artifact),
    )


class TestRestoreResolutionAndGuards:
    def test_compatibility_wrapper_reads_current_database_engine(self) -> None:
        artifact = _artifact()
        with (
            patch(
                f"{_ORCH}.django.db",
                SimpleNamespace(
                    connections={
                        "default": SimpleNamespace(settings_dict={"ENGINE": "sqlite"})
                    }
                ),
            ),
            patch(
                f"{_ORCH}._core_get_restore_compatibility_issues",
                return_value=["issue"],
            ) as checker,
        ):
            result = orch._get_restore_compatibility_issues(artifact)
        assert result == ["issue"]
        checker.assert_called_once_with(artifact, "sqlite")

    @pytest.mark.parametrize(
        ("snapshot", "message"),
        [
            (_snapshot(status="deleted"), "deleted or pruned"),
            (_snapshot(authoritative_dump=None), "authoritative database dump"),
        ],
    )
    def test_resolve_authoritative_snapshot_dump_rejects_unusable_snapshots(
        self, snapshot: SimpleNamespace, message: str
    ) -> None:
        with patch(f"{_ORCH}.get_backup_snapshot", return_value=snapshot):
            with pytest.raises(BackupRestoreBlocked, match=message):
                orch._resolve_authoritative_snapshot_dump("snap-b2")

    def test_resolve_authoritative_snapshot_dump_returns_trusted_artifact(self) -> None:
        artifact = _artifact()
        with patch(
            f"{_ORCH}.get_backup_snapshot",
            return_value=_snapshot(authoritative_dump=artifact),
        ):
            assert orch._resolve_authoritative_snapshot_dump("snap-b2") is artifact

    def test_runtime_wrapper_provides_django_contract_checker(self) -> None:
        with (
            patch(f"{_ORCH}._require_postgresql_18_contract") as contract,
            patch(
                "quickscale_core.dr_engine.recovery._ensure_postgresql_18_restore_runtime"
            ) as core,
        ):
            orch._ensure_postgresql_18_restore_runtime("django.db.backends.postgresql")
        core.assert_called_once_with(
            "django.db.backends.postgresql",
            require_contract=contract,
        )

    def test_restore_execution_allowed_delegates_debug_setting(self) -> None:
        with (
            patch(f"{_ORCH}.settings", SimpleNamespace(DEBUG=False)),
            patch(
                f"{_ORCH}._core_restore_execution_allowed", return_value=False
            ) as allowed,
        ):
            assert orch._restore_execution_allowed() is False
        allowed.assert_called_once_with(is_debug=False)

    def test_resolve_restore_source_wrapper_passes_snapshot_and_materializer(
        self,
    ) -> None:
        artifact = _artifact(local_path="/tmp/source.dump")
        with (
            patch(f"{_ORCH}._core_resolve_restore_source") as core,
            patch(f"{_ORCH}._load_active_policy_snapshot", return_value="policy"),
        ):
            core.return_value.__enter__.return_value = _source(
                Path("/tmp/source.dump"), artifact
            )
            core.return_value.__exit__.return_value = None
            with orch._resolve_restore_source(snapshot_id="snap-b2") as result:
                assert result.artifact is artifact
        kwargs = core.call_args.kwargs
        assert kwargs["snapshot_id"] == "snap-b2"
        assert kwargs["resolution_mode"] is RestoreSourceResolutionMode.REMOTE_FALLBACK
        assert callable(kwargs["snapshot_resolver"])
        assert callable(kwargs["remote_materializer"])

    def test_execute_restore_wrapper_persists_metadata_only_after_execution(
        self, tmp_path: Path
    ) -> None:
        source = _source(tmp_path / "trusted.dump", _artifact())
        result = RestoreResult(executed=True, dry_run=False, message="done")
        warning = RestoreWarning(code="metadata", message="warning")
        ordered = MagicMock()
        with (
            patch(
                f"{_ORCH}.django.db",
                SimpleNamespace(
                    connections={
                        "default": SimpleNamespace(settings_dict={"ENGINE": "pg"})
                    }
                ),
            ),
            patch(f"{_ORCH}.settings", SimpleNamespace(DEBUG=True)),
            patch(
                f"{_ORCH}._core_execute_restore_for_resolved_source",
                return_value=result,
            ) as core,
            patch(
                f"{_ORCH}._persist_restore_artifact_metadata", return_value=(warning,)
            ) as persist,
            patch(f"{_ORCH}.django_timezone.now", return_value=_NOW),
        ):
            ordered.attach_mock(core, "core")
            ordered.attach_mock(persist, "persist")
            executed = orch._execute_restore_for_resolved_source(
                source,
                confirmation="trusted.dump",
                dry_run=False,
                allow_production=False,
                shell_runner=None,
            )
        assert executed.warnings == (warning,)
        persist.assert_called_once_with(source.artifact, restored_at=_NOW)
        assert core.call_args.kwargs["current_engine"] == "pg"
        assert core.call_args.kwargs["connection_settings"] == {"ENGINE": "pg"}
        assert [item[0] for item in ordered.mock_calls] == ["core", "persist"]

    def test_execute_restore_wrapper_does_not_persist_metadata_for_dry_run(
        self, tmp_path: Path
    ) -> None:
        source = _source(tmp_path / "trusted.dump", _artifact())
        result = RestoreResult(executed=False, dry_run=True, message="dry")
        with (
            patch(
                f"{_ORCH}.django.db",
                SimpleNamespace(
                    connections={"default": SimpleNamespace(settings_dict={})}
                ),
            ),
            patch(f"{_ORCH}.settings", SimpleNamespace(DEBUG=True)),
            patch(
                f"{_ORCH}._core_execute_restore_for_resolved_source",
                return_value=result,
            ),
            patch(f"{_ORCH}._persist_restore_artifact_metadata") as persist,
        ):
            assert (
                orch._execute_restore_for_resolved_source(
                    source,
                    confirmation="trusted.dump",
                    dry_run=True,
                    allow_production=False,
                    shell_runner=None,
                )
                is result
            )
        persist.assert_not_called()

    def test_restore_backup_source_resolves_then_executes_in_order(self) -> None:
        source = _source(Path("/tmp/file.dump"))
        result = RestoreResult(executed=False, dry_run=True, message="ok")
        with (
            patch(f"{_ORCH}._resolve_restore_source") as resolver,
            patch(
                f"{_ORCH}._execute_restore_for_resolved_source", return_value=result
            ) as execute,
        ):
            resolver.return_value.__enter__.return_value = source
            resolver.return_value.__exit__.return_value = None
            assert (
                orch.restore_backup_source(
                    file_path="/tmp/file.dump",
                    confirmation="file.dump",
                    dry_run=True,
                    shell_runner=cast(ShellCommandRunner, "runner"),
                )
                is result
            )
        assert resolver.call_args.kwargs["file_path"] == "/tmp/file.dump"
        execute.assert_called_once_with(
            source,
            confirmation="file.dump",
            dry_run=True,
            allow_production=False,
            shell_runner="runner",
        )

    def test_restore_backup_artifact_is_thin_source_wrapper(self) -> None:
        artifact = _artifact()
        result = RestoreResult(executed=False, dry_run=True, message="ok")
        with patch(f"{_ORCH}.restore_backup_source", return_value=result) as restore:
            assert (
                orch.restore_backup_artifact(artifact, confirmation="trusted.dump")
                is result
            )
        assert restore.call_args.kwargs["artifact"] is artifact
        assert restore.call_args.kwargs["confirmation"] == "trusted.dump"


class TestAdminUploadStaging:
    def test_iter_upload_chunks_prefers_nonempty_chunks_and_converts_values(
        self,
    ) -> None:
        uploaded = SimpleNamespace(
            chunks=lambda: [b"one", bytearray(b"two")], read=MagicMock()
        )
        assert list(orch._iter_admin_restore_upload_chunks(uploaded)) == [
            b"one",
            b"two",
        ]
        uploaded.read.assert_not_called()

    def test_iter_upload_chunks_falls_back_to_read_for_empty_chunks(self) -> None:
        uploaded = SimpleNamespace(
            chunks=lambda: [], read=MagicMock(return_value="payload")
        )
        assert list(orch._iter_admin_restore_upload_chunks(uploaded)) == [b"payload"]

    @pytest.mark.parametrize(
        "uploaded",
        [SimpleNamespace(read=lambda: bytearray(b"no")), SimpleNamespace()],
    )
    def test_iter_upload_chunks_rejects_unreadable_or_nonbytes_payload(
        self, uploaded: object
    ) -> None:
        with pytest.raises(BackupError, match="readable|bytes"):
            list(orch._iter_admin_restore_upload_chunks(uploaded))

    def test_stage_upload_sanitizes_name_and_returns_deterministic_fingerprint(
        self, tmp_path: Path
    ) -> None:
        uploaded = SimpleNamespace(
            name="../../unsafe.dump", chunks=lambda: [b"ab", b"cd"]
        )
        staged = orch._stage_admin_restore_upload(uploaded, staging_directory=tmp_path)
        assert staged.local_path == tmp_path / "unsafe.dump"
        assert staged.local_path.read_bytes() == b"abcd"
        assert staged.size_bytes == 4
        assert staged.checksum_sha256 == (
            "88d4266fd4e6338d13b845fcf289579d209c897823b9217da3e161936f031589"
        )

    def test_stage_upload_rejects_empty_payload(self, tmp_path: Path) -> None:
        with pytest.raises(BackupRestoreBlocked, match="empty"):
            orch._stage_admin_restore_upload(
                SimpleNamespace(name="empty.dump", chunks=lambda: [b"", b""]),
                staging_directory=tmp_path,
            )

    def test_cleanup_upload_directory_is_idempotent_and_reports_os_errors(
        self, tmp_path: Path
    ) -> None:
        directory = tmp_path / "stage"
        directory.mkdir()
        assert orch._cleanup_admin_restore_upload_directory(directory) is None
        assert orch._cleanup_admin_restore_upload_directory(directory) is None
        with patch("shutil.rmtree", side_effect=OSError("busy")):
            assert orch._cleanup_admin_restore_upload_directory(directory) == "busy"

    def test_admin_artifact_resolution_and_metadata_delegate_to_persistence(
        self,
    ) -> None:
        artifact = _artifact()
        warning = RestoreWarning(code="w", message="warning")
        with (
            patch(
                f"{_ORCH}.resolve_admin_uploaded_restore_artifact",
                return_value=artifact,
            ) as resolve,
            patch(
                f"{_ORCH}.update_artifact_after_restore", return_value=(warning,)
            ) as persist,
        ):
            assert (
                orch._resolve_admin_uploaded_restore_artifact(
                    checksum_sha256="sum", size_bytes=4
                )
                is artifact
            )
            assert orch._persist_restore_artifact_metadata(
                artifact, restored_at=_NOW
            ) == (warning,)
        resolve.assert_called_once_with(checksum_sha256="sum", size_bytes=4)
        persist.assert_called_once_with(artifact, restored_at=_NOW)


class TestAdminUploadRestore:
    def _staged(self, tmp_path: Path) -> SimpleNamespace:
        return SimpleNamespace(
            local_path=tmp_path / "staged.dump",
            checksum_sha256="sum",
            size_bytes=4,
        )

    def test_successful_admin_restore_cleans_staging_and_uses_trusted_filename(
        self, tmp_path: Path
    ) -> None:
        result = RestoreResult(executed=False, dry_run=True, message="validated")
        artifact = _artifact(filename="canonical.dump")
        staged = self._staged(tmp_path)
        stage_dir = tmp_path / "stage"
        ordered = MagicMock()
        with (
            patch(f"{_ORCH}.mkdtemp", return_value=str(stage_dir)),
            patch(f"{_ORCH}._stage_admin_restore_upload", return_value=staged),
            patch(
                f"{_ORCH}._resolve_admin_uploaded_restore_artifact",
                return_value=artifact,
            ),
            patch(
                f"{_ORCH}._execute_restore_for_resolved_source", return_value=result
            ) as execute,
            patch(
                f"{_ORCH}._cleanup_admin_restore_upload_directory", return_value=None
            ) as cleanup,
        ):
            ordered.attach_mock(execute, "execute")
            ordered.attach_mock(cleanup, "cleanup")
            assert (
                orch.restore_admin_uploaded_backup(
                    SimpleNamespace(), confirmation="canonical.dump", dry_run=True
                )
                is result
            )
        execute.assert_called_once()
        resolved_source = execute.call_args.args[0]
        assert resolved_source.confirmation_value == "canonical.dump"
        assert resolved_source.local_path == staged.local_path
        cleanup.assert_called_once_with(Path(stage_dir))
        assert [item[0] for item in ordered.mock_calls] == ["execute", "cleanup"]

    @pytest.mark.parametrize("minutes_old", [31, 0])
    def test_admin_restore_stale_guard_distinguishes_old_and_current_restoring(
        self, tmp_path: Path, minutes_old: int
    ) -> None:
        started = _NOW - timedelta(minutes=minutes_old)
        artifact = _artifact(status="restoring", restore_started_at=started)
        staged = self._staged(tmp_path)
        expected = "stale" if minutes_old else "currently being"
        with (
            patch(f"{_ORCH}.mkdtemp", return_value=str(tmp_path / "stage")),
            patch(f"{_ORCH}._stage_admin_restore_upload", return_value=staged),
            patch(
                f"{_ORCH}._resolve_admin_uploaded_restore_artifact",
                return_value=artifact,
            ),
            patch(f"{_ORCH}.django_timezone.now", return_value=_NOW),
            patch(
                f"{_ORCH}._cleanup_admin_restore_upload_directory", return_value=None
            ) as cleanup,
        ):
            with pytest.raises(BackupRestoreBlocked, match=expected):
                orch.restore_admin_uploaded_backup(
                    SimpleNamespace(), confirmation="canonical.dump"
                )
        cleanup.assert_called_once()

    def test_admin_restore_failure_still_cleans_staging(self, tmp_path: Path) -> None:
        staged = self._staged(tmp_path)
        artifact = _artifact()
        ordered = MagicMock()
        with (
            patch(f"{_ORCH}.mkdtemp", return_value=str(tmp_path / "stage")),
            patch(f"{_ORCH}._stage_admin_restore_upload", return_value=staged),
            patch(
                f"{_ORCH}._resolve_admin_uploaded_restore_artifact",
                return_value=artifact,
            ),
            patch(
                f"{_ORCH}._execute_restore_for_resolved_source",
                side_effect=BackupError("blocked"),
            ) as execute,
            patch(
                f"{_ORCH}._cleanup_admin_restore_upload_directory", return_value=None
            ) as cleanup,
        ):
            ordered.attach_mock(execute, "execute")
            ordered.attach_mock(cleanup, "cleanup")
            with pytest.raises(BackupError, match="blocked"):
                orch.restore_admin_uploaded_backup(
                    SimpleNamespace(), confirmation="trusted.dump"
                )
        cleanup.assert_called_once()
        assert [item[0] for item in ordered.mock_calls] == ["execute", "cleanup"]

    def test_admin_restore_success_returns_cleanup_warning_when_cleanup_fails(
        self, tmp_path: Path
    ) -> None:
        staged = self._staged(tmp_path)
        artifact = _artifact()
        result = RestoreResult(executed=True, dry_run=False, message="done")
        with (
            patch(f"{_ORCH}.mkdtemp", return_value=str(tmp_path / "stage")),
            patch(f"{_ORCH}._stage_admin_restore_upload", return_value=staged),
            patch(
                f"{_ORCH}._resolve_admin_uploaded_restore_artifact",
                return_value=artifact,
            ),
            patch(f"{_ORCH}._execute_restore_for_resolved_source", return_value=result),
            patch(
                f"{_ORCH}._cleanup_admin_restore_upload_directory",
                return_value="permission denied",
            ),
        ):
            returned = orch.restore_admin_uploaded_backup(
                SimpleNamespace(), confirmation="trusted.dump"
            )
        assert returned.warnings[0].code == "admin_restore_upload_cleanup_failed"
        assert returned.warnings[0].details == {
            "staging_directory": str(tmp_path / "stage"),
            "error": "permission denied",
        }
