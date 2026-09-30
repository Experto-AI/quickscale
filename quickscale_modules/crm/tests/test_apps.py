"""Tests for CRM AppConfig startup behavior.

Fail-hard CRM API-enable flag: ``AppConfig.ready()`` must raise
``ImproperlyConfigured`` when ``CRM_ENABLE_API`` is missing from Django settings.
"""

from importlib import import_module

import pytest
from django.core.exceptions import ImproperlyConfigured

from quickscale_modules_crm.apps import QuickscaleCrmConfig


def test_app_config_exposes_expected_metadata() -> None:
    """AppConfig should expose the expected CRM module metadata."""
    assert QuickscaleCrmConfig.name == "quickscale_modules_crm"
    assert QuickscaleCrmConfig.label == "quickscale_crm"
    assert QuickscaleCrmConfig.verbose_name == "QuickScale CRM"
    assert QuickscaleCrmConfig.default_auto_field == "django.db.models.BigAutoField"


def test_app_config_ready_is_safe_to_call() -> None:
    """AppConfig.ready() should not raise when all required settings are present."""
    config = QuickscaleCrmConfig(
        "quickscale_modules_crm",
        import_module("quickscale_modules_crm"),
    )

    assert config.ready() is None


def test_ready_raises_improperly_configured_when_crm_enable_api_missing(
    settings,
) -> None:
    """Missing CRM_ENABLE_API must raise at startup."""
    # Remove the setting to simulate a misconfigured project
    del settings.CRM_ENABLE_API

    config = QuickscaleCrmConfig(
        "quickscale_modules_crm",
        import_module("quickscale_modules_crm"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="CRM_ENABLE_API",
    ):
        config.ready()


@pytest.mark.django_db
def test_missing_setting_fails_check_migrate_and_runserver(settings) -> None:
    """The registered CRM check fails check, migrate, and runserver alike."""
    from django.core.management import call_command
    from django.core.management.base import SystemCheckError
    from django.core.management.commands import migrate, runserver

    del settings.CRM_ENABLE_API

    with pytest.raises(SystemCheckError, match="CRM_ENABLE_API"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="CRM_ENABLE_API"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="CRM_ENABLE_API"):
        runserver.Command().check()
