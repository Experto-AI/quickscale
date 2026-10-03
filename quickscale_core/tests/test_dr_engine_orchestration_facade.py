"""Facade-seam regression tests for the split DR orchestration module.

The implementation lives in private sibling modules; every public name stays
importable from ``quickscale_core.dr_engine.orchestration`` and every test
patch target on that path must keep propagating into the moved definitions.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.dr_engine import orchestration as orch
from quickscale_core.dr_engine import persistence
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot

_NOW = datetime(2026, 6, 15, 14, 30, tzinfo=timezone.utc)


def _policy(**overrides: object) -> BackupPolicySnapshot:
    values: dict[str, object] = {
        "retention_days": 30,
        "naming_prefix": "quickscale",
        "target_mode": "local",
        "local_directory": "/var/backups",
        "remote_bucket_name": "",
        "remote_prefix": "snapshots",
        "remote_endpoint_url": "",
        "remote_region_name": "",
        "remote_access_key_id_env_var": "ACCESS_KEY",
        "remote_secret_access_key_env_var": "SECRET_KEY",
        "automation_enabled": False,
        "schedule": "",
    }
    return BackupPolicySnapshot(**(values | overrides))  # type: ignore[arg-type]


class TestFacadePatchTargets:
    """The facade keeps patch targets effective across the split modules."""

    def test_metadata_builder_resolves_helpers_through_the_facade(self) -> None:
        """Patching facade helpers reaches the moved release-metadata builder."""
        with (
            patch.object(orch, "_get_project_slug", return_value="patched-slug"),
            patch.object(orch, "_get_source_environment", return_value="staging"),
            patch.object(orch, "_collect_module_versions", return_value={"m": "1"}),
            patch.object(orch, "_get_git_revision", return_value="abc123"),
            patch.object(
                orch,
                "settings",
                SimpleNamespace(QUICKSCALE_APP_VERSION="9.9"),
            ),
            patch.object(orch, "django") as django_module,
        ):
            django_module.get_version.return_value = "9.9-django"
            metadata = orch._build_release_metadata(captured_at=_NOW)

        assert metadata["project_slug"] == "patched-slug"
        assert metadata["source_environment"] == "staging"
        assert metadata["django_version"] == "9.9-django"
        assert metadata["git_sha"] == "abc123"

    def test_snapshot_failure_resolves_persistence_through_the_facade(self) -> None:
        """Patching the facade persistence seam reaches the state helper."""
        snapshot = SimpleNamespace(status="pending", failure_note="")

        with patch.object(orch, "save_snapshot") as save_snapshot:
            orch._mark_snapshot_failed(snapshot, failure_note="boom")

        assert snapshot.status == "failed"
        assert snapshot.failure_note == "boom"
        save_snapshot.assert_called_once()

    def test_policy_loader_resolves_settings_snapshot_through_the_facade(self) -> None:
        """Patching the facade settings snapshot reaches the policy loader."""
        policy = _policy()

        with (
            patch.object(orch, "settings_policy_snapshot", return_value=policy),
            patch.object(persistence, "has_any_policy", return_value=False),
        ):
            assert orch._load_active_policy_snapshot() is policy

    def test_remote_upload_resolves_seams_through_the_facade(self) -> None:
        """Patching the facade credential resolver and sink reaches the uploader."""
        policy = SimpleNamespace(
            remote_bucket_name="bucket",
            remote_endpoint_url="",
            remote_region_name="",
            remote_prefix="snapshots",
        )

        with (
            patch.object(
                orch,
                "_resolve_private_remote_credentials",
                return_value=("key", "secret"),
            ) as credentials,
            patch.object(orch, "upload_file_to_s3") as upload,
        ):
            remote_key = orch._upload_to_private_remote(Path("/tmp/dump.dump"), policy)

        assert remote_key == "snapshots/dump.dump"
        credentials.assert_called_once_with(policy)
        upload.assert_called_once()

    def test_capture_resume_resolves_snapshot_loader_through_the_facade(self) -> None:
        """Patching the facade snapshot loader reaches the capture resumer."""
        with patch.object(
            orch,
            "get_backup_snapshot",
            side_effect=RuntimeError("sentinel"),
        ):
            with pytest.raises(RuntimeError, match="sentinel"):
                orch._resume_backup_capture(
                    "snap-1",
                    trigger="manual",
                    policy=_policy(),
                    shell_runner=None,
                    remote_uploader=None,
                    remote_deleter=None,
                    now=_NOW,
                )

    def test_rollback_pin_clear_resolves_helpers_through_the_facade(self) -> None:
        """Patching facade helpers reaches the moved rollback-pin clearer."""
        snapshot = SimpleNamespace(status="ready")

        with (
            patch.object(orch, "get_backup_snapshot", return_value=snapshot),
            patch.object(
                orch,
                "_build_clear_rollback_pin_fields",
                return_value={
                    "rollback_pin_expires_at": None,
                    "rollback_pin_reason": "",
                },
            ),
            patch.object(orch, "save_snapshot") as save_snapshot,
            patch.object(
                orch,
                "build_backup_snapshot_report",
                return_value={"status": "ready"},
            ),
            patch.object(orch, "django_timezone") as django_timezone,
        ):
            django_timezone.now.return_value = _NOW
            result = orch.clear_backup_snapshot_rollback_pin("snap-1")

        assert result == {"status": "ready"}
        save_snapshot.assert_called_once()

    def test_prune_resolves_policy_and_iterators_through_the_facade(self) -> None:
        """Patching the facade policy loader and iterators reaches the pruner."""
        policy = _policy(retention_days=1)

        with (
            patch.object(orch, "_load_active_policy_snapshot", return_value=policy),
            patch.object(orch, "iter_expired_snapshots", return_value=[]) as snapshots,
            patch.object(
                orch, "iter_expired_unlinked_artifacts", return_value=[]
            ) as artifacts,
        ):
            deleted = orch.prune_expired_backups(dry_run=True, now=_NOW)

        assert deleted == 0
        snapshots.assert_called_once()
        artifacts.assert_called_once()

    def test_media_runtime_resolves_storage_helpers_through_the_facade(self) -> None:
        """Patching the facade storage-helper loader reaches the media resolver."""
        helpers = MagicMock()
        helpers.select_storage_backend.return_value = SimpleNamespace(
            backend="local",
            use_s3_compatible=False,
            options={},
        )

        with patch.object(
            orch, "_load_storage_helpers", return_value=helpers
        ) as loader:
            runtime = orch._resolve_media_runtime({"MEDIA_ROOT": "/tmp/media"})

        loader.assert_called_once_with()
        assert runtime["backend"] == "local"

    def test_restore_guard_resolves_core_seam_through_the_facade(self) -> None:
        """Patching the facade core guard reaches the restore wrapper."""
        with (
            patch.object(
                orch,
                "_core_restore_execution_allowed",
                return_value=True,
            ) as guard,
            patch.object(orch, "settings", SimpleNamespace(DEBUG=False)),
        ):
            assert orch._restore_execution_allowed() is True

        guard.assert_called_once_with(is_debug=False)


class TestFacadeSurface:
    """The facade preserves the former module surface and canonical identity."""

    def test_module_identity_is_the_facade(self) -> None:
        """The public import path resolves to the facade module object."""
        assert sys.modules["quickscale_core.dr_engine.orchestration"] is orch

    def test_moved_definitions_live_in_the_private_modules(self) -> None:
        """Representative moved callables are owned by their new modules."""
        expected = {
            "create_backup": "quickscale_core.dr_engine._capture",
            "build_backup_snapshot_report": "quickscale_core.dr_engine._report",
            "restore_backup_source": "quickscale_core.dr_engine._restore",
            "prune_expired_backups": "quickscale_core.dr_engine._prune",
            "sync_backup_snapshot_media": "quickscale_core.dr_engine._media",
            "_upload_to_private_remote": "quickscale_core.dr_engine._remote",
            "_get_project_slug": "quickscale_core.dr_engine._metadata",
        }
        for name, module in expected.items():
            assert getattr(orch, name).__module__ == module

    def test_public_names_keep_canonical_identity_with_runtime_facade(self) -> None:
        """runtime.dr re-exports the very objects bound on the orchestration path."""
        import quickscale_core.runtime.dr as runtime_dr

        for name in (
            "BackupLockError",
            "build_backup_filename",
            "build_backup_snapshot_report",
            "clear_backup_snapshot_rollback_pin",
            "create_backup",
            "delete_artifact_files",
            "download_backup_path",
            "get_backup_snapshot",
            "get_local_backup_directory",
            "prune_expired_backups",
            "record_backup_snapshot_verification",
            "report_backup_snapshot",
            "restore_admin_uploaded_backup",
            "restore_backup_artifact",
            "restore_backup_source",
            "set_backup_snapshot_rollback_pin",
            "sync_backup_snapshot_media",
            "validate_backup_artifact",
        ):
            assert getattr(orch, name) is getattr(runtime_dr, name)

    def test_types_helpers_stay_bound_on_the_facade(self) -> None:
        """Protocols and constants moved to ``_types`` are re-exported."""
        assert orch._ROUTE_KIND_KEY == "ROUTE_KIND"
        assert orch._RemoteUploader.__module__ == "quickscale_core.dr_engine._types"
