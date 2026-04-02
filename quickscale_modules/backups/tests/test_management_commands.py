"""Tests for backups module management commands."""

from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from quickscale_modules_backups.services import BackupError


def test_backups_create_command_reports_created_artifact() -> None:
    stdout = StringIO()

    with patch(
        "quickscale_modules_backups.management.commands.backups_create.create_backup",
        return_value=SimpleNamespace(
            filename="db-20260402.dump",
            pk=42,
            local_path="/tmp/db-20260402.dump",
            remote_key="ops/backups/db-20260402.dump",
        ),
    ) as mocked_create:
        call_command("backups_create", stdout=stdout, stderr=StringIO())

    mocked_create.assert_called_once_with(trigger="manual")
    assert stdout.getvalue() == (
        "Created backup db-20260402.dump\n"
        "Artifact id: 42\n"
        "Local path: /tmp/db-20260402.dump\n"
        "Remote key: ops/backups/db-20260402.dump\n"
    )


def test_backups_create_command_routes_scheduled_trigger() -> None:
    stdout = StringIO()

    with patch(
        "quickscale_modules_backups.management.commands.backups_create.create_backup",
        return_value=SimpleNamespace(
            filename="db-20260402.dump",
            pk=7,
            local_path="/tmp/db-20260402.dump",
            remote_key="",
        ),
    ) as mocked_create:
        call_command(
            "backups_create",
            "--scheduled",
            stdout=stdout,
            stderr=StringIO(),
        )

    mocked_create.assert_called_once_with(trigger="scheduled")
    assert stdout.getvalue() == (
        "Created backup db-20260402.dump\n"
        "Artifact id: 7\n"
        "Local path: /tmp/db-20260402.dump\n"
    )


def test_backups_create_command_wraps_backup_errors() -> None:
    with patch(
        "quickscale_modules_backups.management.commands.backups_create.create_backup",
        side_effect=BackupError("pg_dump exploded"),
    ):
        with pytest.raises(CommandError, match="pg_dump exploded"):
            call_command("backups_create", stdout=StringIO(), stderr=StringIO())


def test_backups_prune_command_reports_deleted_count() -> None:
    stdout = StringIO()

    with patch(
        "quickscale_modules_backups.management.commands.backups_prune.prune_expired_backups",
        return_value=3,
    ) as mocked_prune:
        call_command("backups_prune", stdout=stdout, stderr=StringIO())

    mocked_prune.assert_called_once_with()
    assert stdout.getvalue() == "Pruned 3 expired backup artifact(s)\n"


@pytest.mark.django_db
def test_backups_validate_command_requires_existing_artifact() -> None:
    with pytest.raises(CommandError, match="Backup artifact not found"):
        call_command("backups_validate", "999999", stdout=StringIO(), stderr=StringIO())


@pytest.mark.django_db
def test_backups_validate_command_reports_validation_issues(
    backup_artifact,
) -> None:
    with patch(
        "quickscale_modules_backups.management.commands.backups_validate.validate_backup_artifact",
        return_value=["checksum mismatch detected", "size mismatch detected"],
    ) as mocked_validate:
        with pytest.raises(
            CommandError,
            match="checksum mismatch detected; size mismatch detected",
        ):
            call_command(
                "backups_validate",
                str(backup_artifact.pk),
                stdout=StringIO(),
                stderr=StringIO(),
            )

    mocked_validate.assert_called_once_with(backup_artifact)


@pytest.mark.django_db
def test_backups_validate_command_reports_success(backup_artifact) -> None:
    stdout = StringIO()

    with patch(
        "quickscale_modules_backups.management.commands.backups_validate.validate_backup_artifact",
        return_value=[],
    ) as mocked_validate:
        call_command(
            "backups_validate",
            str(backup_artifact.pk),
            stdout=stdout,
            stderr=StringIO(),
        )

    mocked_validate.assert_called_once_with(backup_artifact)
    assert stdout.getvalue() == f"Validated {backup_artifact.filename}\n"
