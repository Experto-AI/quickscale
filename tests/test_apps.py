"""Tests for the auth AppConfig startup behavior."""

from __future__ import annotations

from importlib import import_module

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.core.management.commands import migrate, runserver

from quickscale_modules_auth.apps import QuickscaleAuthConfig
from quickscale_modules_auth.checks import check_required_settings


def test_check_passes_when_setting_present(settings) -> None:
    """``ACCOUNT_ALLOW_REGISTRATION`` set means no failure is reported."""
    settings.ACCOUNT_ALLOW_REGISTRATION = True

    assert check_required_settings() == []


def test_check_reports_missing_setting(settings) -> None:
    """A missing ``ACCOUNT_ALLOW_REGISTRATION`` is reported by name."""
    del settings.ACCOUNT_ALLOW_REGISTRATION

    messages = check_required_settings()

    assert messages
    assert "ACCOUNT_ALLOW_REGISTRATION" in messages[0].msg


def test_ready_raises_improperly_configured_when_setting_missing(settings) -> None:
    """``ready()`` refuses startup when the setting is absent."""
    del settings.ACCOUNT_ALLOW_REGISTRATION

    config = QuickscaleAuthConfig(
        "quickscale_modules_auth",
        import_module("quickscale_modules_auth"),
    )

    with pytest.raises(ImproperlyConfigured, match="ACCOUNT_ALLOW_REGISTRATION"):
        config.ready()


@pytest.mark.django_db
def test_missing_setting_fails_check_migrate_and_runserver(settings) -> None:
    """The registered guard fails check, migrate, and runserver alike."""
    del settings.ACCOUNT_ALLOW_REGISTRATION

    with pytest.raises(SystemCheckError, match="ACCOUNT_ALLOW_REGISTRATION"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="ACCOUNT_ALLOW_REGISTRATION"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="ACCOUNT_ALLOW_REGISTRATION"):
        runserver.Command().check()
