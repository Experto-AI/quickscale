"""Pure-mock A-II coverage for restore, admin upload, verification, and pins."""

from __future__ import annotations
import quickscale_core.dr_engine._restore as _restore

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

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
                "django.db",
                SimpleNamespace(
                    connections={
                        "default": SimpleNamespace(settings_dict={"ENGINE": "sqlite"})
                    }
                ),
            ),
            patch(
                "quickscale_core.dr_engine._metadata._collect_module_migration_hashes",
                return_value={
                    "quickscale_modules_auth": {"0001_initial.py": "hash-1"},
                },
            ),
            patch(
                "quickscale_core.dr_engine.recovery._get_restore_compatibility_issues",
                return_value=["issue"],
            ) as checker,
        ):
            result = _restore._get_restore_compatibility_issues(artifact)
        assert result == ["issue"]
        checker.assert_called_once_with(
            artifact,
            "sqlite",
            installed_migration_hashes={
                "quickscale_modules_auth": {"0001_initial.py": "hash-1"},
            },
        )

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
        with patch(
            "quickscale_core.dr_engine._state.get_backup_snapshot",
            return_value=snapshot,
        ):
            with pytest.raises(BackupRestoreBlocked, match=message):
                _restore._resolve_authoritative_snapshot_dump("snap-b2")

    def test_resolve_authoritative_snapshot_dump_returns_trusted_artifact(self) -> None:
        artifact = _artifact()
        with patch(
            "quickscale_core.dr_engine._state.get_backup_snapshot",
            return_value=_snapshot(authoritative_dump=artifact),
        ):
            assert _restore._resolve_authoritative_snapshot_dump("snap-b2") is artifact

    def test_runtime_wrapper_provides_django_contract_checker(self) -> None:
        with (
            patch(
                "quickscale_core.dr_engine._metadata._require_postgresql_18_contract"
            ) as contract,
            patch(
                "quickscale_core.dr_engine.recovery._ensure_postgresql_18_restore_runtime"
            ) as core,
        ):
            _restore._ensure_postgresql_18_restore_runtime(
                "django.db.backends.postgresql"
            )
        core.assert_called_once_with(
            "django.db.backends.postgresql",
            require_contract=contract,
        )

    def test_restore_execution_allowed_delegates_debug_setting(self) -> None:
        with (
            patch("django.conf.settings", SimpleNamespace(DEBUG=False)),
            patch(
                "quickscale_core.dr_engine.recovery._restore_execution_allowed",
                return_value=False,
            ) as allowed,
        ):
            assert _restore._restore_execution_allowed() is False
        allowed.assert_called_once_with(is_debug=False)

    def test_resolve_restore_source_wrapper_passes_snapshot_and_materializer(
        self,
    ) -> None:
        artifact = _artifact(local_path="/tmp/source.dump")
        with (
            patch("quickscale_core.dr_engine.recovery._resolve_restore_source") as core,
            patch(
                "quickscale_core.dr_engine._policy._load_active_policy_snapshot",
                return_value="policy",
            ),
        ):
            core.return_value.__enter__.return_value = _source(
                Path("/tmp/source.dump"), artifact
            )
            core.return_value.__exit__.return_value = None
            with _restore._resolve_restore_source(snapshot_id="snap-b2") as result:
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
        restore_snapshot = _snapshot()
        result = RestoreResult(executed=True, dry_run=False, message="done")
        warning = RestoreWarning(code="metadata", message="warning")
        ordered = MagicMock()
        with (
            patch(
                "django.db",
                SimpleNamespace(
                    connections={
                        "default": SimpleNamespace(settings_dict={"ENGINE": "pg"})
                    }
                ),
            ),
            patch("django.conf.settings", SimpleNamespace(DEBUG=True)),
            patch(
                "quickscale_core.dr_engine._metadata._collect_module_migration_hashes",
                return_value={},
            ),
            patch(
                "quickscale_core.dr_engine._metadata._collect_project_migration_hashes",
                return_value={},
            ),
            patch(
                "quickscale_core.dr_engine.persistence.get_authoritative_snapshot_for_artifact",
                return_value=restore_snapshot,
            ) as resolve_snapshot,
            patch(
                "quickscale_core.dr_engine._restore._resolve_restore_lock_directory",
                return_value=tmp_path,
            ),
            patch(
                "quickscale_core.dr_engine.recovery._execute_restore_for_resolved_source",
                return_value=result,
            ) as core,
            patch(
                "quickscale_core.dr_engine._restore._persist_restore_artifact_metadata",
                return_value=(warning,),
            ) as persist,
            patch("django.utils.timezone.now", return_value=_NOW),
        ):
            ordered.attach_mock(resolve_snapshot, "snapshot")
            ordered.attach_mock(core, "core")
            ordered.attach_mock(persist, "persist")
            executed = _restore._execute_restore_for_resolved_source(
                source,
                confirmation="trusted.dump",
                dry_run=False,
                allow_production=False,
                shell_runner=None,
            )
        assert executed.warnings == (warning,)
        persist.assert_called_once_with(
            source.artifact, restored_at=_NOW, snapshot=restore_snapshot
        )
        assert core.call_args.kwargs["current_engine"] == "pg"
        assert core.call_args.kwargs["connection_settings"] == {"ENGINE": "pg"}
        assert [item[0] for item in ordered.mock_calls] == [
            "snapshot",
            "core",
            "persist",
        ]

    def test_execute_restore_wrapper_does_not_persist_metadata_for_dry_run(
        self, tmp_path: Path
    ) -> None:
        source = _source(tmp_path / "trusted.dump", _artifact())
        result = RestoreResult(executed=False, dry_run=True, message="dry")
        with (
            patch(
                "django.db",
                SimpleNamespace(
                    connections={"default": SimpleNamespace(settings_dict={})}
                ),
            ),
            patch("django.conf.settings", SimpleNamespace(DEBUG=True)),
            patch(
                "quickscale_core.dr_engine._metadata._collect_module_migration_hashes",
                return_value={},
            ),
            patch(
                "quickscale_core.dr_engine._metadata._collect_project_migration_hashes",
                return_value={},
            ),
            patch(
                "quickscale_core.dr_engine.persistence.get_authoritative_snapshot_for_artifact",
                return_value=None,
            ),
            patch(
                "quickscale_core.dr_engine.recovery._execute_restore_for_resolved_source",
                return_value=result,
            ),
            patch(
                "quickscale_core.dr_engine._restore._persist_restore_artifact_metadata"
            ) as persist,
        ):
            executed = _restore._execute_restore_for_resolved_source(
                source,
                confirmation="trusted.dump",
                dry_run=True,
                allow_production=False,
                shell_runner=None,
            )
        assert executed.dry_run is True
        assert [warning.code for warning in executed.warnings] == ["media_not_captured"]
        persist.assert_not_called()

    def test_execute_restore_wrapper_supplies_installed_migration_hashes(
        self, tmp_path: Path
    ) -> None:
        source = _source(tmp_path / "trusted.dump", _artifact())
        result = RestoreResult(executed=False, dry_run=True, message="dry")
        with (
            patch(
                "django.db",
                SimpleNamespace(
                    connections={
                        "default": SimpleNamespace(settings_dict={"ENGINE": "pg"})
                    }
                ),
            ),
            patch("django.conf.settings", SimpleNamespace(DEBUG=True)),
            patch(
                "quickscale_core.dr_engine._metadata._collect_module_migration_hashes",
                return_value={
                    "quickscale_modules_auth": {"0001_initial.py": "hash-1"},
                },
            ),
            patch(
                "quickscale_core.dr_engine._metadata._collect_project_migration_hashes",
                return_value={"properties": {"0001_initial.py": "project-hash"}},
            ),
            patch(
                "quickscale_core.dr_engine.persistence.get_authoritative_snapshot_for_artifact",
                return_value=None,
            ),
            patch(
                "quickscale_core.dr_engine.recovery._execute_restore_for_resolved_source",
                return_value=result,
            ) as core,
        ):
            _restore._execute_restore_for_resolved_source(
                source,
                confirmation="trusted.dump",
                dry_run=True,
                allow_production=False,
                shell_runner=None,
            )
        assert core.call_args.kwargs["installed_migration_hashes"] == {
            "quickscale_modules_auth": {"0001_initial.py": "hash-1"}
        }
        assert core.call_args.kwargs["installed_project_migration_hashes"] == {
            "properties": {"0001_initial.py": "project-hash"}
        }

    def test_restore_backup_source_resolves_then_executes_in_order(self) -> None:
        source = _source(Path("/tmp/file.dump"))
        result = RestoreResult(executed=False, dry_run=True, message="ok")
        with (
            patch(
                "quickscale_core.dr_engine._restore._resolve_restore_source"
            ) as resolver,
            patch(
                "quickscale_core.dr_engine._restore._execute_restore_for_resolved_source",
                return_value=result,
            ) as execute,
        ):
            resolver.return_value.__enter__.return_value = source
            resolver.return_value.__exit__.return_value = None
            assert (
                _restore.restore_backup_source(
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
            recorded_migration_hashes=None,
            recorded_manifest_version=None,
            recorded_project_migration_hashes=None,
            allow_forward=False,
            policy=None,
        )

    def test_restore_backup_source_passes_recorded_migration_hashes(self) -> None:
        source = _source(Path("/tmp/file.dump"))
        result = RestoreResult(executed=False, dry_run=True, message="ok")
        with (
            patch(
                "quickscale_core.dr_engine._restore._resolve_restore_source"
            ) as resolver,
            patch(
                "quickscale_core.dr_engine._restore._execute_restore_for_resolved_source",
                return_value=result,
            ) as execute,
        ):
            resolver.return_value.__enter__.return_value = source
            resolver.return_value.__exit__.return_value = None
            _restore.restore_backup_source(
                file_path="/tmp/file.dump",
                confirmation="file.dump",
                dry_run=True,
                recorded_migration_hashes={
                    "quickscale_modules_auth": {"0001_initial.py": "hash-1"},
                },
            )
        assert execute.call_args.kwargs["recorded_migration_hashes"] == {
            "quickscale_modules_auth": {"0001_initial.py": "hash-1"}
        }
        assert execute.call_args.kwargs["recorded_manifest_version"] is None
        assert execute.call_args.kwargs["recorded_project_migration_hashes"] is None

    def test_restore_backup_artifact_is_thin_source_wrapper(self) -> None:
        artifact = _artifact()
        result = RestoreResult(executed=False, dry_run=True, message="ok")
        with patch(
            "quickscale_core.dr_engine._restore.restore_backup_source",
            return_value=result,
        ) as restore:
            assert (
                _restore.restore_backup_artifact(artifact, confirmation="trusted.dump")
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
        assert list(_restore._iter_admin_restore_upload_chunks(uploaded)) == [
            b"one",
            b"two",
        ]
        uploaded.read.assert_not_called()

    def test_iter_upload_chunks_falls_back_to_read_for_empty_chunks(self) -> None:
        uploaded = SimpleNamespace(
            chunks=lambda: [], read=MagicMock(return_value="payload")
        )
        assert list(_restore._iter_admin_restore_upload_chunks(uploaded)) == [
            b"payload"
        ]

    @pytest.mark.parametrize(
        "uploaded",
        [SimpleNamespace(read=lambda: bytearray(b"no")), SimpleNamespace()],
    )
    def test_iter_upload_chunks_rejects_unreadable_or_nonbytes_payload(
        self, uploaded: object
    ) -> None:
        with pytest.raises(BackupError, match="readable|bytes"):
            list(_restore._iter_admin_restore_upload_chunks(uploaded))

    def test_stage_upload_sanitizes_name_and_returns_deterministic_fingerprint(
        self, tmp_path: Path
    ) -> None:
        uploaded = SimpleNamespace(
            name="../../unsafe.dump", chunks=lambda: [b"ab", b"cd"]
        )
        staged = _restore._stage_admin_restore_upload(
            uploaded, staging_directory=tmp_path
        )
        assert staged.local_path == tmp_path / "unsafe.dump"
        assert staged.local_path.read_bytes() == b"abcd"
        assert staged.size_bytes == 4
        assert staged.checksum_sha256 == (
            "88d4266fd4e6338d13b845fcf289579d209c897823b9217da3e161936f031589"
        )

    def test_stage_upload_rejects_empty_payload(self, tmp_path: Path) -> None:
        with pytest.raises(BackupRestoreBlocked, match="empty"):
            _restore._stage_admin_restore_upload(
                SimpleNamespace(name="empty.dump", chunks=lambda: [b"", b""]),
                staging_directory=tmp_path,
            )

    def test_cleanup_upload_directory_is_idempotent_and_reports_os_errors(
        self, tmp_path: Path
    ) -> None:
        directory = tmp_path / "stage"
        directory.mkdir()
        assert _restore._cleanup_admin_restore_upload_directory(directory) is None
        assert _restore._cleanup_admin_restore_upload_directory(directory) is None
        with patch("shutil.rmtree", side_effect=OSError("busy")):
            assert _restore._cleanup_admin_restore_upload_directory(directory) == "busy"

    def test_admin_artifact_resolution_and_metadata_delegate_to_persistence(
        self,
    ) -> None:
        artifact = _artifact()
        snapshot = _snapshot()
        warning = RestoreWarning(code="w", message="warning")
        with (
            patch(
                "quickscale_core.dr_engine.persistence.resolve_admin_uploaded_restore_artifact",
                return_value=artifact,
            ) as resolve,
            patch(
                "quickscale_core.dr_engine.persistence.update_artifact_after_restore",
                return_value=(warning,),
            ) as persist,
        ):
            assert (
                _restore._resolve_admin_uploaded_restore_artifact(
                    checksum_sha256="sum", size_bytes=4
                )
                is artifact
            )
            assert _restore._persist_restore_artifact_metadata(
                artifact, restored_at=_NOW, snapshot=snapshot
            ) == (warning,)
        resolve.assert_called_once_with(checksum_sha256="sum", size_bytes=4)
        persist.assert_called_once_with(artifact, restored_at=_NOW, snapshot=snapshot)


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
            patch("tempfile.mkdtemp", return_value=str(stage_dir)),
            patch(
                "quickscale_core.dr_engine._restore._stage_admin_restore_upload",
                return_value=staged,
            ),
            patch(
                "quickscale_core.dr_engine._restore._resolve_admin_uploaded_restore_artifact",
                return_value=artifact,
            ),
            patch(
                "quickscale_core.dr_engine._restore._execute_restore_for_resolved_source",
                return_value=result,
            ) as execute,
            patch(
                "quickscale_core.dr_engine._restore._cleanup_admin_restore_upload_directory",
                return_value=None,
            ) as cleanup,
        ):
            ordered.attach_mock(execute, "execute")
            ordered.attach_mock(cleanup, "cleanup")
            assert (
                _restore.restore_admin_uploaded_backup(
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
            patch("tempfile.mkdtemp", return_value=str(tmp_path / "stage")),
            patch(
                "quickscale_core.dr_engine._restore._stage_admin_restore_upload",
                return_value=staged,
            ),
            patch(
                "quickscale_core.dr_engine._restore._resolve_admin_uploaded_restore_artifact",
                return_value=artifact,
            ),
            patch("django.utils.timezone.now", return_value=_NOW),
            patch(
                "quickscale_core.dr_engine._restore._cleanup_admin_restore_upload_directory",
                return_value=None,
            ) as cleanup,
        ):
            with pytest.raises(BackupRestoreBlocked, match=expected):
                _restore.restore_admin_uploaded_backup(
                    SimpleNamespace(), confirmation="canonical.dump"
                )
        cleanup.assert_called_once()

    def test_admin_restore_failure_still_cleans_staging(self, tmp_path: Path) -> None:
        staged = self._staged(tmp_path)
        artifact = _artifact()
        ordered = MagicMock()
        with (
            patch("tempfile.mkdtemp", return_value=str(tmp_path / "stage")),
            patch(
                "quickscale_core.dr_engine._restore._stage_admin_restore_upload",
                return_value=staged,
            ),
            patch(
                "quickscale_core.dr_engine._restore._resolve_admin_uploaded_restore_artifact",
                return_value=artifact,
            ),
            patch(
                "quickscale_core.dr_engine._restore._execute_restore_for_resolved_source",
                side_effect=BackupError("blocked"),
            ) as execute,
            patch(
                "quickscale_core.dr_engine._restore._cleanup_admin_restore_upload_directory",
                return_value=None,
            ) as cleanup,
        ):
            ordered.attach_mock(execute, "execute")
            ordered.attach_mock(cleanup, "cleanup")
            with pytest.raises(BackupError, match="blocked"):
                _restore.restore_admin_uploaded_backup(
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
            patch("tempfile.mkdtemp", return_value=str(tmp_path / "stage")),
            patch(
                "quickscale_core.dr_engine._restore._stage_admin_restore_upload",
                return_value=staged,
            ),
            patch(
                "quickscale_core.dr_engine._restore._resolve_admin_uploaded_restore_artifact",
                return_value=artifact,
            ),
            patch(
                "quickscale_core.dr_engine._restore._execute_restore_for_resolved_source",
                return_value=result,
            ),
            patch(
                "quickscale_core.dr_engine._restore._cleanup_admin_restore_upload_directory",
                return_value="permission denied",
            ),
        ):
            returned = _restore.restore_admin_uploaded_backup(
                SimpleNamespace(), confirmation="trusted.dump"
            )
        assert returned.warnings[0].code == "admin_restore_upload_cleanup_failed"
        assert returned.warnings[0].details == {
            "staging_directory": str(tmp_path / "stage"),
            "error": "permission denied",
        }


class TestRestoreLeaseAndMediaWarnings:
    def _locked_source(self, tmp_path: Path) -> tuple[Any, Path]:
        artifact = _artifact(
            local_path=str(
                tmp_path / "snapshots" / "snap-1" / "database" / "trusted.dump"
            ),
        )
        return _source(tmp_path / "trusted.dump", artifact), tmp_path

    def _patched_environment(
        self,
        *,
        restore_snapshot: Any,
        result: RestoreResult,
        tmp_path: Path,
        persist_side_effect: Any = (),
    ) -> Any:
        from contextlib import ExitStack
        from unittest.mock import patch

        stack = ExitStack()
        stack.enter_context(
            patch(
                "django.db",
                SimpleNamespace(
                    connections={
                        "default": SimpleNamespace(settings_dict={"ENGINE": "pg"})
                    }
                ),
            )
        )
        stack.enter_context(patch("django.conf.settings", SimpleNamespace(DEBUG=True)))
        stack.enter_context(patch("django.utils.timezone.now", return_value=_NOW))
        stack.enter_context(
            patch(
                "quickscale_core.dr_engine._metadata._collect_module_migration_hashes",
                return_value={},
            )
        )
        stack.enter_context(
            patch(
                "quickscale_core.dr_engine._metadata._collect_project_migration_hashes",
                return_value={},
            )
        )
        stack.enter_context(
            patch(
                "quickscale_core.dr_engine.persistence.get_authoritative_snapshot_for_artifact",
                return_value=restore_snapshot,
            )
        )
        stack.enter_context(
            patch(
                "quickscale_core.dr_engine._restore._resolve_restore_lock_directory",
                return_value=tmp_path,
            )
        )
        stack.enter_context(
            patch(
                "quickscale_core.dr_engine.recovery._execute_restore_for_resolved_source",
                return_value=result,
            )
        )
        persist_patch = (
            patch(
                "quickscale_core.dr_engine._restore._persist_restore_artifact_metadata",
                side_effect=persist_side_effect,
            )
            if callable(persist_side_effect)
            else patch(
                "quickscale_core.dr_engine._restore._persist_restore_artifact_metadata",
                return_value=persist_side_effect,
            )
        )
        stack.enter_context(persist_patch)
        return stack

    def test_execute_restore_holds_the_restore_lock_for_the_run(
        self, tmp_path: Path
    ) -> None:
        source, lock_directory = self._locked_source(tmp_path)
        snapshot = _snapshot(local_root_path=str(tmp_path / "snapshots" / "snap-1"))
        result = RestoreResult(executed=True, dry_run=False, message="done")
        observed_lock_states: list[bool] = []

        def persist_side_effect(*_args: Any, **_kwargs: Any) -> tuple[()]:
            observed_lock_states.append(
                (lock_directory / ".quickscale-backup-restore.lock").exists()
            )
            return ()

        with self._patched_environment(
            restore_snapshot=snapshot,
            result=result,
            tmp_path=lock_directory,
            persist_side_effect=persist_side_effect,
        ):
            executed = _restore._execute_restore_for_resolved_source(
                source,
                confirmation="trusted.dump",
                dry_run=False,
                allow_production=False,
                shell_runner=None,
            )

        assert executed.executed is True
        assert observed_lock_states == [True]
        assert not (lock_directory / ".quickscale-backup-restore.lock").exists()

    def test_execute_restore_refuses_while_another_restore_holds_the_lock(
        self, tmp_path: Path
    ) -> None:
        from quickscale_core.dr_engine._lock import (
            BackupLockError,
            _acquire_backup_lock,
            _release_backup_lock,
            _RESTORE_LOCK_FILENAME,
        )

        source, lock_directory = self._locked_source(tmp_path)
        snapshot = _snapshot(local_root_path=str(tmp_path / "snapshots" / "snap-1"))
        result = RestoreResult(executed=True, dry_run=False, message="done")
        lock_path = _acquire_backup_lock(
            lock_directory,
            lock_filename=_RESTORE_LOCK_FILENAME,
        )
        try:
            with self._patched_environment(
                restore_snapshot=snapshot,
                result=result,
                tmp_path=lock_directory,
            ):
                with pytest.raises(BackupLockError, match="backup restore is already"):
                    _restore._execute_restore_for_resolved_source(
                        source,
                        confirmation="trusted.dump",
                        dry_run=False,
                        allow_production=False,
                        shell_runner=None,
                    )
        finally:
            _release_backup_lock(lock_path)

    def _write_media_manifest(self, snapshot_root: Path, payload: dict) -> None:
        import json

        snapshot_root.mkdir(parents=True, exist_ok=True)
        (snapshot_root / "media-sync-manifest.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    def test_v1_artifact_restore_warns_that_media_is_not_captured(
        self, tmp_path: Path
    ) -> None:
        snapshot_root = tmp_path / "snapshots" / "snap-1"
        self._write_media_manifest(
            snapshot_root,
            {
                "manifest_version": 1,
                "status": "ready",
                "inventory": [],
            },
        )
        source, lock_directory = self._locked_source(tmp_path)
        snapshot = _snapshot(local_root_path=str(snapshot_root))
        result = RestoreResult(executed=True, dry_run=False, message="done")

        with self._patched_environment(
            restore_snapshot=snapshot,
            result=result,
            tmp_path=lock_directory,
        ):
            executed = _restore._execute_restore_for_resolved_source(
                source,
                confirmation="trusted.dump",
                dry_run=False,
                allow_production=False,
                shell_runner=None,
            )

        assert [warning.code for warning in executed.warnings] == ["media_not_captured"]

    def test_v2_artifact_restore_warns_on_an_incomplete_captured_set(
        self, tmp_path: Path
    ) -> None:
        snapshot_root = tmp_path / "snapshots" / "snap-1"
        self._write_media_manifest(
            snapshot_root,
            {
                "manifest_version": 2,
                "status": "ready",
                "capture": {
                    "status": "captured",
                    "relative_root": "media",
                    "file_count": 1,
                },
                "inventory": [{"relative_path": "blog/hero.png"}],
            },
        )
        source = _source(
            tmp_path / "trusted.dump",
            _artifact(metadata_json={"manifest_version": 2}),
        )
        snapshot = _snapshot(local_root_path=str(snapshot_root))
        result = RestoreResult(executed=True, dry_run=False, message="done")

        with self._patched_environment(
            restore_snapshot=snapshot,
            result=result,
            tmp_path=tmp_path,
        ):
            executed = _restore._execute_restore_for_resolved_source(
                source,
                confirmation="trusted.dump",
                dry_run=False,
                allow_production=False,
                shell_runner=None,
            )

        assert [warning.code for warning in executed.warnings] == [
            "media_capture_incomplete"
        ]
        assert "blog/hero.png" in executed.warnings[0].message

    def test_dry_run_validates_media_without_taking_the_restore_lock(
        self, tmp_path: Path
    ) -> None:
        snapshot_root = tmp_path / "snapshots" / "snap-1"
        self._write_media_manifest(
            snapshot_root,
            {
                "manifest_version": 1,
                "status": "ready",
                "inventory": [],
            },
        )
        source, lock_directory = self._locked_source(tmp_path)
        snapshot = _snapshot(local_root_path=str(snapshot_root))
        result = RestoreResult(executed=False, dry_run=True, message="dry")

        with self._patched_environment(
            restore_snapshot=snapshot,
            result=result,
            tmp_path=lock_directory,
        ):
            executed = _restore._execute_restore_for_resolved_source(
                source,
                confirmation="trusted.dump",
                dry_run=True,
                allow_production=False,
                shell_runner=None,
            )

        assert [warning.code for warning in executed.warnings] == ["media_not_captured"]
        assert not (lock_directory / ".quickscale-backup-restore.lock").exists()


class TestRestoreLockDirectory:
    def test_role_differences_share_the_database_lock(self) -> None:
        from quickscale_core.dr_engine import _restore as restore_module

        serving_role = {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": "db.internal",
            "PORT": "5432",
            "NAME": "app",
            "USER": "serving_role",
        }
        backup_role = {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": "db.internal",
            "PORT": "5432",
            "NAME": "app",
            "USER": "backup_role",
        }

        assert restore_module._resolve_restore_lock_directory(
            serving_role
        ) == restore_module._resolve_restore_lock_directory(backup_role)
        assert "quickscale-backup-restore" in str(
            restore_module._resolve_restore_lock_directory(serving_role)
        )

    def test_privileged_url_target_drives_the_lock_identity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quickscale_core.dr_engine import _restore as restore_module
        from quickscale_core.dr_engine._connection import _resolve_backup_connection

        monkeypatch.delenv("QUICKSCALE_BACKUP_DATABASE_URL", raising=False)
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql://backup_role:secret@db.internal:5432/app",
        )
        resolved = _resolve_backup_connection(
            {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "serving.internal",
                "PORT": "5432",
                "NAME": "serving",
                "USER": "serving_role",
            }
        )

        directory = restore_module._resolve_restore_lock_directory(resolved.settings)

        assert directory.name == restore_module._restore_lock_identity(
            {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "db.internal",
                "PORT": "5432",
                "NAME": "app",
            }
        )

    def test_default_port_matches_an_explicit_default_port(self) -> None:
        from quickscale_core.dr_engine import _restore as restore_module

        base = {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": "DB.internal",
            "NAME": "app",
        }

        assert restore_module._restore_lock_identity(
            base
        ) == restore_module._restore_lock_identity({**base, "PORT": "5432"})

    def test_a_different_target_database_uses_a_different_lock(self) -> None:
        from quickscale_core.dr_engine import _restore as restore_module

        first = restore_module._resolve_restore_lock_directory(
            {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "db.internal",
                "PORT": "5432",
                "NAME": "app_one",
                "USER": "app",
            }
        )
        second = restore_module._resolve_restore_lock_directory(
            {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "db.internal",
                "PORT": "5432",
                "NAME": "app_two",
                "USER": "app",
            }
        )

        assert first != second

    def test_wrapper_lease_follows_the_privileged_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from contextlib import contextmanager

        from quickscale_core.dr_engine import _restore as restore_module

        monkeypatch.delenv("QUICKSCALE_BACKUP_DATABASE_URL", raising=False)
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql://backup_role:secret@db.internal:5432/app",
        )
        observed: list[Path] = []

        @contextmanager
        def fake_restore_lock(directory: Path, **_kwargs: Any) -> Any:
            observed.append(directory)
            yield

        def run_with_serving_host(serving_host: str) -> None:
            source = _source(tmp_path / "file.dump")
            result = RestoreResult(executed=False, dry_run=False, message="ok")
            with (
                patch(
                    "django.db",
                    SimpleNamespace(
                        connections={
                            "default": SimpleNamespace(
                                settings_dict={
                                    "ENGINE": "django.db.backends.postgresql",
                                    "HOST": serving_host,
                                    "PORT": "5432",
                                    "NAME": "serving",
                                    "USER": "serving_role",
                                }
                            )
                        }
                    ),
                ),
                patch("django.conf.settings", SimpleNamespace(DEBUG=True)),
                patch(
                    "quickscale_core.dr_engine._connection._ensure_backup_connection_is_privileged"
                ),
                patch(
                    "quickscale_core.dr_engine._metadata._collect_module_migration_hashes",
                    return_value={},
                ),
                patch(
                    "quickscale_core.dr_engine._metadata._collect_project_migration_hashes",
                    return_value={},
                ),
                patch(
                    "quickscale_core.dr_engine.recovery._execute_restore_for_resolved_source",
                    return_value=result,
                ),
                patch(
                    "quickscale_core.dr_engine._lock._restore_advisory_lock",
                    fake_restore_lock,
                ),
            ):
                restore_module._execute_restore_for_resolved_source(
                    source,
                    confirmation="file.dump",
                    dry_run=False,
                    allow_production=False,
                    shell_runner=None,
                    recorded_manifest_version=1,
                )

        run_with_serving_host("serving-one.internal")
        run_with_serving_host("serving-two.internal")

        assert observed[0] == observed[1]
        assert observed[0].name == restore_module._restore_lock_identity(
            {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "db.internal",
                "PORT": "5432",
                "NAME": "app",
            }
        )

    def test_v2_artifact_without_a_snapshot_warns_database_only(
        self, tmp_path: Path
    ) -> None:
        from quickscale_core.dr_engine import _restore as restore_module

        warnings = restore_module._collect_media_restore_warnings(
            _artifact(metadata_json={"manifest_version": 2}),
            None,
        )

        assert [warning.code for warning in warnings] == ["media_not_captured"]

    def test_v1_artifact_without_a_snapshot_still_warns(self, tmp_path: Path) -> None:
        from quickscale_core.dr_engine import _restore as restore_module

        warnings = restore_module._collect_media_restore_warnings(
            _artifact(metadata_json={"manifest_version": 1}),
            None,
        )

        assert [warning.code for warning in warnings] == ["media_not_captured"]

    def test_file_source_warns_from_its_recorded_manifest_version(self) -> None:
        from quickscale_core.dr_engine import _restore as restore_module

        warnings = restore_module._collect_media_restore_warnings(
            None,
            None,
            recorded_manifest_version=1,
        )

        assert [warning.code for warning in warnings] == ["media_not_captured"]
