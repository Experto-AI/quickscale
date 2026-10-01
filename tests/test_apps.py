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


def test_switched_off_module_skips_the_vendor_check(settings) -> None:
    """Rule 1 (D3): a switched-off module has no switched-on feature, so a
    half-configured credential pair is not reported while it is off."""
    settings.QUICKSCALE_STORAGE_ENABLED = False
    settings.QUICKSCALE_STORAGE_BACKEND = "s3"
    settings.AWS_ACCESS_KEY_ID = "key-id"
    settings.AWS_SECRET_ACCESS_KEY = ""

    assert check_vendor_secrets() == []


def test_s3_backend_reports_a_missing_projected_credential(settings) -> None:
    """A projected credential missing entirely is reported, not skipped."""
    settings.QUICKSCALE_STORAGE_BACKEND = "s3"
    del settings.AWS_SECRET_ACCESS_KEY

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


def test_missing_backend_setting_fails_startup(settings) -> None:
    """Rule 3: the generic settings check refuses a missing declared setting."""
    from django.apps import apps
    from django.core.exceptions import ImproperlyConfigured

    del settings.QUICKSCALE_STORAGE_BACKEND

    with pytest.raises(ImproperlyConfigured, match="QUICKSCALE_STORAGE_BACKEND"):
        apps.get_app_config("quickscale_storage").ready()


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
