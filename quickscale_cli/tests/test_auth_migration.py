"""Tests for the extracted auth migration utility."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from quickscale_cli.utils.auth_migration import (
    assess_auth_migration_state,
    format_auth_migration_remediation,
    has_migrations_been_run,
)


def test_missing_manage_py_is_unverifiable(tmp_path: Path) -> None:
    assessment = assess_auth_migration_state(tmp_path)
    assert assessment.unverifiable
    assert "manage.py not found" in assessment.reason


@patch("quickscale_cli.utils.auth_migration.subprocess.run")
def test_probe_classifies_compatible_state(mock_run: Mock, tmp_path: Path) -> None:
    (tmp_path / "manage.py").touch()
    mock_run.return_value = Mock(
        returncode=0, stdout='{"ok": true, "incompatible": false}\n', stderr=""
    )
    assessment = assess_auth_migration_state(tmp_path)
    assert assessment.compatible
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["timeout"] == 15


@patch("quickscale_cli.utils.auth_migration.subprocess.run")
def test_probe_classifies_incompatible_state(mock_run: Mock, tmp_path: Path) -> None:
    (tmp_path / "manage.py").touch()
    mock_run.return_value = Mock(
        returncode=0, stdout='{"ok": true, "incompatible": true}\n', stderr=""
    )
    assert has_migrations_been_run(tmp_path)


@patch("quickscale_cli.utils.auth_migration.subprocess.run")
def test_probe_failures_are_unverifiable(mock_run: Mock, tmp_path: Path) -> None:
    (tmp_path / "manage.py").touch()
    mock_run.side_effect = subprocess.TimeoutExpired(["python"], 15)
    assessment = assess_auth_migration_state(tmp_path)
    assert assessment.unverifiable


@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr", "reason"),
    [
        (1, "", "probe failed", "migration recorder check failed: probe failed"),
        (0, "", "", "migration recorder check produced no output"),
        (0, "not-json\n", "", "unexpected migration recorder output: not-json"),
        (0, '{"ok": false, "error": "probe rejected"}\n', "", "probe rejected"),
    ],
)
@patch("quickscale_cli.utils.auth_migration.subprocess.run")
def test_probe_output_failures_are_unverifiable(
    mock_run: Mock,
    tmp_path: Path,
    returncode: int,
    stdout: str,
    stderr: str,
    reason: str,
) -> None:
    (tmp_path / "manage.py").touch()
    mock_run.return_value = Mock(returncode=returncode, stdout=stdout, stderr=stderr)

    assessment = assess_auth_migration_state(tmp_path)

    assert assessment.unverifiable
    assert assessment.reason == reason


def test_remediation_keeps_project_identity_and_commands(tmp_path: Path) -> None:
    remediation = format_auth_migration_remediation(tmp_path)
    assert f"cd {tmp_path.resolve()}" in remediation
    assert "docker compose down -v" in remediation
    assert "poetry run python manage.py flush --no-input" in remediation
