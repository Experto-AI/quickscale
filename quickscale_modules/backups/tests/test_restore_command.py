"""Tests for the backups_restore management command."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from quickscale_core.runtime import BackupError
from quickscale_modules_backups.models import BackupArtifact


@pytest.mark.django_db
class TestBackupsRestoreCommand:
    """Command-surface tests for restore source selection."""

    def test_command_requires_one_restore_source(self) -> None:
        with pytest.raises(
            CommandError,
            match="Provide either an artifact_id, --snapshot-id, or --file PATH",
        ):
            call_command(
                "backups_restore",
                "--confirm",
                "sample-backup.dump",
                stdout=StringIO(),
                stderr=StringIO(),
            )

    def test_command_rejects_multiple_restore_sources(
        self,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        with pytest.raises(
            CommandError,
            match="Choose exactly one restore source",
        ):
            call_command(
                "backups_restore",
                str(postgresql_backup_artifact.pk),
                "--file",
                str(postgresql_artifact_file),
                "--confirm",
                postgresql_backup_artifact.filename,
                stdout=StringIO(),
                stderr=StringIO(),
            )

    def test_command_routes_file_mode_through_shared_restore_service(
        self,
        postgresql_artifact_file: Path,
    ) -> None:
        stdout = StringIO()
        mock_restore = MagicMock(
            return_value={
                "message": "Restore validation completed successfully (dry run).",
                "warnings": [],
            }
        )

        with patch.dict(
            "quickscale_core.runtime.ADAPTER_FUNCTIONS",
            {"restore_backup": mock_restore},
        ):
            call_command(
                "backups_restore",
                "--file",
                str(postgresql_artifact_file),
                "--confirm",
                postgresql_artifact_file.name,
                "--dry-run",
                stdout=stdout,
                stderr=StringIO(),
            )

        mock_restore.assert_called_once_with(
            artifact_id=None,
            snapshot_id=None,
            file_path=str(postgresql_artifact_file),
            confirmation=postgresql_artifact_file.name,
            dry_run=True,
            allow_production=False,
            resolution_mode=None,
        )
        assert "Restore validation completed successfully" in stdout.getvalue()

    def test_command_routes_snapshot_id_through_shared_restore_service(self) -> None:
        stdout = StringIO()
        mock_restore = MagicMock(
            return_value={
                "message": "Restore validation completed successfully (dry run).",
                "warnings": [],
            }
        )

        with patch.dict(
            "quickscale_core.runtime.ADAPTER_FUNCTIONS",
            {"restore_backup": mock_restore},
        ):
            call_command(
                "backups_restore",
                "--snapshot-id",
                "snap-restore-123",
                "--confirm",
                "sample-backup.dump",
                "--dry-run",
                stdout=stdout,
                stderr=StringIO(),
            )

        mock_restore.assert_called_once_with(
            artifact_id=None,
            snapshot_id="snap-restore-123",
            file_path=None,
            confirmation="sample-backup.dump",
            dry_run=True,
            allow_production=False,
            resolution_mode=None,
        )
        assert "Restore validation completed successfully" in stdout.getvalue()

    def test_command_renders_structured_restore_warnings_without_erroring(
        self,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        stdout = StringIO()
        stderr = StringIO()
        mock_restore = MagicMock(
            return_value={
                "message": (
                    f"Restore executed for {postgresql_backup_artifact.filename}."
                ),
                "warnings": [
                    {
                        "code": "artifact_row_missing_after_restore",
                        "message": (
                            "Restore executed, but the original backup artifact row "
                            "no longer exists in the restored database."
                        ),
                    },
                ],
            }
        )

        with patch.dict(
            "quickscale_core.runtime.ADAPTER_FUNCTIONS",
            {"restore_backup": mock_restore},
        ):
            call_command(
                "backups_restore",
                str(postgresql_backup_artifact.pk),
                "--confirm",
                postgresql_backup_artifact.filename,
                stdout=stdout,
                stderr=stderr,
            )

        mock_restore.assert_called_once_with(
            artifact_id=postgresql_backup_artifact.pk,
            snapshot_id=None,
            file_path=None,
            confirmation=postgresql_backup_artifact.filename,
            dry_run=False,
            allow_production=False,
            resolution_mode=None,
        )
        assert stdout.getvalue() == (
            f"Restore executed for {postgresql_backup_artifact.filename}.\n"
            "Warning [artifact_row_missing_after_restore]: Restore executed, but the original backup artifact row no longer exists in the restored database.\n"
        )
        assert stderr.getvalue() == ""

    # ------------------------------------------------------------------
    # CR-SA20-006: --local-only passes resolution_mode to the adapter
    # ------------------------------------------------------------------

    def test_command_passes_local_only_resolution_mode(
        self,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """``--local-only`` maps to ``resolution_mode="local_only"``."""
        stdout = StringIO()
        mock_restore = MagicMock(
            return_value={
                "message": "Restore executed.",
                "warnings": [],
            }
        )

        with patch.dict(
            "quickscale_core.runtime.ADAPTER_FUNCTIONS",
            {"restore_backup": mock_restore},
        ):
            call_command(
                "backups_restore",
                str(postgresql_backup_artifact.pk),
                "--confirm",
                postgresql_backup_artifact.filename,
                "--local-only",
                stdout=stdout,
                stderr=StringIO(),
            )

        mock_restore.assert_called_once()
        _call_kwargs = mock_restore.call_args[1]
        assert _call_kwargs.get("resolution_mode") == "local_only"

    def test_command_omits_local_only_by_default(
        self,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """Without ``--local-only``, resolution_mode is ``None`` (REMOTE_FALLBACK)."""
        stdout = StringIO()
        mock_restore = MagicMock(
            return_value={
                "message": "Restore executed.",
                "warnings": [],
            }
        )

        with patch.dict(
            "quickscale_core.runtime.ADAPTER_FUNCTIONS",
            {"restore_backup": mock_restore},
        ):
            call_command(
                "backups_restore",
                str(postgresql_backup_artifact.pk),
                "--confirm",
                postgresql_backup_artifact.filename,
                stdout=stdout,
                stderr=StringIO(),
            )

        mock_restore.assert_called_once()
        _call_kwargs = mock_restore.call_args[1]
        assert _call_kwargs.get("resolution_mode") is None

    # ------------------------------------------------------------------
    # CR-SA20-007: Failure recording for STATUS_RESTORING artifacts
    # ------------------------------------------------------------------

    def test_command_records_failed_on_backup_error_for_restoring_artifact(
        self,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """BackupError on a STATUS_RESTORING artifact records STATUS_FAILED."""
        postgresql_backup_artifact.status = BackupArtifact.STATUS_RESTORING
        postgresql_backup_artifact.restore_error = ""
        postgresql_backup_artifact.save(
            update_fields=["status", "restore_error", "updated_at"]
        )

        mock_restore = MagicMock(
            side_effect=BackupError("pg_restore crashed: disk full"),
        )

        with patch.dict(
            "quickscale_core.runtime.ADAPTER_FUNCTIONS",
            {"restore_backup": mock_restore},
        ):
            with pytest.raises(CommandError, match="pg_restore crashed: disk full"):
                call_command(
                    "backups_restore",
                    str(postgresql_backup_artifact.pk),
                    "--confirm",
                    postgresql_backup_artifact.filename,
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_FAILED
        assert "disk full" in postgresql_backup_artifact.restore_error

    def test_command_records_failed_on_generic_exception_for_restoring_artifact(
        self,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """Any Exception on a STATUS_RESTORING artifact records STATUS_FAILED."""
        postgresql_backup_artifact.status = BackupArtifact.STATUS_RESTORING
        postgresql_backup_artifact.restore_error = ""
        postgresql_backup_artifact.save(
            update_fields=["status", "restore_error", "updated_at"]
        )

        mock_restore = MagicMock(
            side_effect=ValueError("unexpected null in restore plan"),
        )

        with patch.dict(
            "quickscale_core.runtime.ADAPTER_FUNCTIONS",
            {"restore_backup": mock_restore},
        ):
            with pytest.raises(CommandError, match="unexpected null"):
                call_command(
                    "backups_restore",
                    str(postgresql_backup_artifact.pk),
                    "--confirm",
                    postgresql_backup_artifact.filename,
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_FAILED
        assert "unexpected null" in postgresql_backup_artifact.restore_error

    def test_command_does_not_record_failed_for_non_restoring_artifact(
        self,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """Artifacts not in STATUS_RESTORING are left untouched on failure."""
        postgresql_backup_artifact.status = BackupArtifact.STATUS_READY
        postgresql_backup_artifact.restore_error = ""
        postgresql_backup_artifact.save(
            update_fields=["status", "restore_error", "updated_at"]
        )

        mock_restore = MagicMock(
            side_effect=BackupError("pg_restore crashed: disk full"),
        )

        with patch.dict(
            "quickscale_core.runtime.ADAPTER_FUNCTIONS",
            {"restore_backup": mock_restore},
        ):
            with pytest.raises(CommandError, match="pg_restore crashed: disk full"):
                call_command(
                    "backups_restore",
                    str(postgresql_backup_artifact.pk),
                    "--confirm",
                    postgresql_backup_artifact.filename,
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

        postgresql_backup_artifact.refresh_from_db()
        # Status must NOT have changed from READY to FAILED
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_READY
        assert postgresql_backup_artifact.restore_error == ""
