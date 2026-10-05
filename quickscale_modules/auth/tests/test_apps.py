"""Tests for the auth AppConfig startup behavior."""

from __future__ import annotations

from importlib import import_module

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.core.management.commands import migrate, runserver

from quickscale_modules_auth.apps import QuickscaleAuthConfig
from quickscale_modules_orgs.removal import (
    AUTH_PERSONAL_DATA,
    RemovalAction,
    RemovalBoundary,
)


def _auth_config() -> QuickscaleAuthConfig:
    return QuickscaleAuthConfig(
        "quickscale_modules_auth",
        import_module("quickscale_modules_auth"),
    )


def test_app_config_declares_its_account_deletion_boundary_implementation() -> None:
    """Auth owns the anonymize boundary and declares its implementation."""
    implementations = _auth_config().removal_boundary_implementations()

    assert implementations[RemovalBoundary.ANONYMIZE] == (
        "quickscale_modules_auth",
        "quickscale_modules_auth.views",
        "AccountDeleteView.form_valid",
    )


def test_app_config_declares_the_account_personal_data_obligation() -> None:
    """The account row is auth's own anonymize obligation, skipped at purge."""
    (obligation,) = _auth_config().removal_obligations()

    assert obligation.name == AUTH_PERSONAL_DATA
    assert obligation.anonymize_action is RemovalAction.ANONYMIZE
    assert obligation.purge_action is RemovalAction.SKIP


def test_app_config_exposes_the_anonymize_executor() -> None:
    """The declared ANONYMIZE action's executor lives on the AppConfig."""
    config = _auth_config()

    assert callable(config.anonymize_account)
    assert config.anonymize_handlers() == (config,)


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
