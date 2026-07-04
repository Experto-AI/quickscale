"""Tests for CRM AppConfig startup behavior.

SA17.3 — fail-hard CRM API-enable flag: ``AppConfig.ready()`` must raise
``ImproperlyConfigured`` when ``CRM_ENABLE_API`` is missing from Django settings.
"""

from importlib import import_module

import pytest
from django.core.exceptions import ImproperlyConfigured

from quickscale_modules_crm.apps import QuickscaleCrmConfig


def test_app_config_exposes_expected_metadata() -> None:
    """AppConfig should expose the expected CRM module metadata."""
    assert QuickscaleCrmConfig.name == "quickscale_modules_crm"
    assert QuickscaleCrmConfig.label == "quickscale_modules_crm"
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
