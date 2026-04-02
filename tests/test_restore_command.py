"""Tests for the backups_restore management command."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from quickscale_modules_backups.models import BackupArtifact
from quickscale_modules_backups.services import RestoreResult, RestoreWarning


@pytest.mark.django_db
class TestBackupsRestoreCommand:
    """Command-surface tests for restore source selection."""

    def test_command_requires_one_restore_source(self) -> None:
        with pytest.raises(
            CommandError,
            match="Provide either an artifact_id or --file PATH",
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

        with patch(
            "quickscale_modules_backups.management.commands.backups_restore.restore_backup_source",
            return_value=RestoreResult(
                executed=False,
                dry_run=True,
                message="Restore validation completed successfully (dry run).",
            ),
        ) as mocked_restore:
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

        mocked_restore.assert_called_once_with(
            artifact=None,
            file_path=str(postgresql_artifact_file),
            confirmation=postgresql_artifact_file.name,
            dry_run=True,
            allow_production=False,
        )
        assert "Restore validation completed successfully" in stdout.getvalue()

    def test_command_renders_structured_restore_warnings_without_erroring(
        self,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        stdout = StringIO()
        stderr = StringIO()

        with patch(
            "quickscale_modules_backups.management.commands.backups_restore.restore_backup_source",
            return_value=RestoreResult(
                executed=True,
                dry_run=False,
                message=f"Restore executed for {postgresql_backup_artifact.filename}.",
                warnings=(
                    RestoreWarning(
                        code="artifact_row_missing_after_restore",
                        message=(
                            "Restore executed, but the original backup artifact row "
                            "no longer exists in the restored database."
                        ),
                    ),
                ),
            ),
        ) as mocked_restore:
            result = call_command(
                "backups_restore",
                str(postgresql_backup_artifact.pk),
                "--confirm",
                postgresql_backup_artifact.filename,
                stdout=stdout,
                stderr=stderr,
            )

        assert result is None
        mocked_restore.assert_called_once_with(
            artifact=postgresql_backup_artifact,
            file_path=None,
            confirmation=postgresql_backup_artifact.filename,
            dry_run=False,
            allow_production=False,
        )
        assert stdout.getvalue() == (
            f"Restore executed for {postgresql_backup_artifact.filename}.\n"
            "Warning [artifact_row_missing_after_restore]: Restore executed, but the original backup artifact row no longer exists in the restored database.\n"
        )
        assert stderr.getvalue() == ""
