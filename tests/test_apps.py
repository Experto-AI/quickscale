"""Tests for the storage AppConfig startup behavior."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.core.management.commands import migrate, runserver

from quickscale_modules_storage.checks import check_vendor_secrets


def test_local_backend_needs_no_credentials(settings) -> None:
    """Local storage needs no vendor credentials."""
    settings.QUICKSCALE_STORAGE_BACKEND = "local"

    assert check_vendor_secrets() == []


def test_s3_backend_reports_a_half_configured_pair(settings) -> None:
    """An s3-compatible backend with only one credential set is invalid."""
    settings.QUICKSCALE_STORAGE_BACKEND = "s3"
    settings.AWS_ACCESS_KEY_ID = "key-id"
    settings.AWS_SECRET_ACCESS_KEY = ""

    messages = check_vendor_secrets()

    assert messages
    assert "AWS_SECRET_ACCESS_KEY" in messages[0].msg


def test_s3_backend_without_credentials_uses_the_default_chain(settings) -> None:
    """Both credentials empty defer to boto3's default credential chain."""
    settings.QUICKSCALE_STORAGE_BACKEND = "s3"
    settings.AWS_ACCESS_KEY_ID = ""
    settings.AWS_SECRET_ACCESS_KEY = ""

    assert check_vendor_secrets() == []


def test_s3_backend_passes_with_credentials(settings) -> None:
    """Configured credentials satisfy the check for an s3-compatible backend."""
    settings.QUICKSCALE_STORAGE_BACKEND = "r2"
    settings.AWS_ACCESS_KEY_ID = "key-id"
    settings.AWS_SECRET_ACCESS_KEY = "secret-key"

    assert check_vendor_secrets() == []


def test_missing_backend_setting_is_reported(settings) -> None:
    """A missing backend selection is invalid configuration."""
    del settings.QUICKSCALE_STORAGE_BACKEND

    messages = check_vendor_secrets()

    assert messages
    assert "QUICKSCALE_STORAGE_BACKEND" in messages[0].msg


def test_missing_credentials_fail_check_migrate_and_runserver(settings) -> None:
    """The registered check fails check, migrate, and runserver alike."""
    settings.QUICKSCALE_STORAGE_BACKEND = "s3"
    settings.AWS_ACCESS_KEY_ID = "key-id"
    settings.AWS_SECRET_ACCESS_KEY = ""

    with pytest.raises(SystemCheckError, match="AWS_SECRET_ACCESS_KEY"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="AWS_SECRET_ACCESS_KEY"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="AWS_SECRET_ACCESS_KEY"):
        runserver.Command().check()
