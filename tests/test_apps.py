"""Tests for the auth AppConfig startup behavior."""

from __future__ import annotations

from importlib import import_module

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.core.management.commands import migrate, runserver

from quickscale_modules_auth.apps import QuickscaleAuthConfig


def _auth_config() -> QuickscaleAuthConfig:
    return QuickscaleAuthConfig(
        "quickscale_modules_auth",
        import_module("quickscale_modules_auth"),
    )


def test_ready_raises_improperly_configured_when_setting_missing(settings) -> None:
    """Rule 3: a missing declared setting refuses startup naming it."""
    del settings.ACCOUNT_ALLOW_REGISTRATION

    with pytest.raises(ImproperlyConfigured, match="ACCOUNT_ALLOW_REGISTRATION"):
        _auth_config().ready()


@pytest.mark.django_db
def test_missing_setting_fails_check_migrate_and_runserver(settings) -> None:
    """The registered generic check fails check, migrate, and runserver alike."""
    del settings.ACCOUNT_ALLOW_REGISTRATION

    with pytest.raises(SystemCheckError, match="ACCOUNT_ALLOW_REGISTRATION"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="ACCOUNT_ALLOW_REGISTRATION"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="ACCOUNT_ALLOW_REGISTRATION"):
        runserver.Command().check()
