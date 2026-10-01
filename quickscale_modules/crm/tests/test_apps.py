"""Tests for CRM AppConfig startup behavior.

Fail-hard CRM API-enable flag: ``AppConfig.ready()`` must raise
``ImproperlyConfigured`` when ``QUICKSCALE_CRM_API_ENABLED`` is missing from Django settings.
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


def test_app_config_declares_its_removal_label_prefix() -> None:
    """Rule 34: the purge summary takes CRM's display prefix from here."""
    assert QuickscaleCrmConfig.removal_label_prefix == "CRM"


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
    """Missing QUICKSCALE_CRM_API_ENABLED must raise at startup."""
    # Remove the setting to simulate a misconfigured project
    del settings.QUICKSCALE_CRM_API_ENABLED

    config = QuickscaleCrmConfig(
        "quickscale_modules_crm",
        import_module("quickscale_modules_crm"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="QUICKSCALE_CRM_API_ENABLED",
    ):
        config.ready()


def test_ready_raises_improperly_configured_when_retired_setting_present(
    settings,
) -> None:
    """Rule 6: a retired CRM setting fails startup naming the replacement."""
    settings.CRM_DEALS_PER_PAGE = 25

    config = QuickscaleCrmConfig(
        "quickscale_modules_crm",
        import_module("quickscale_modules_crm"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="QUICKSCALE_CRM_DEALS_PER_PAGE",
    ):
        config.ready()


def test_ready_refuses_every_declared_retired_setting(settings) -> None:
    """Rule 6: every declared retired CRM name fails startup."""
    from quickscale_modules_crm.checks import RETIRED_SETTINGS

    config = QuickscaleCrmConfig(
        "quickscale_modules_crm",
        import_module("quickscale_modules_crm"),
    )

    for retired_name in RETIRED_SETTINGS:
        setattr(settings, retired_name, "legacy")
        try:
            with pytest.raises(ImproperlyConfigured, match=retired_name):
                config.ready()
        finally:
            delattr(settings, retired_name)


@pytest.mark.django_db
def test_missing_setting_fails_check_migrate_and_runserver(settings) -> None:
    """The registered CRM check fails check, migrate, and runserver alike."""
    from django.core.management import call_command
    from django.core.management.base import SystemCheckError
    from django.core.management.commands import migrate, runserver

    del settings.QUICKSCALE_CRM_API_ENABLED

    with pytest.raises(SystemCheckError, match="QUICKSCALE_CRM_API_ENABLED"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="QUICKSCALE_CRM_API_ENABLED"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="QUICKSCALE_CRM_API_ENABLED"):
        runserver.Command().check()
