"""Tests for Forms AppConfig startup behavior.

SA17.4 — fail-hard forms settings: ``AppConfig.ready()`` must raise
``ImproperlyConfigured`` when any of ``FORMS_SUBMISSIONS_API``,
``FORMS_RATE_LIMIT``, or ``FORMS_SPAM_PROTECTION`` is missing from
Django settings.
"""

from importlib import import_module

import pytest
from django.core.exceptions import ImproperlyConfigured

from quickscale_modules_forms.apps import QuickscaleFormsConfig


def test_app_config_exposes_expected_metadata() -> None:
    """AppConfig should expose the expected Forms module metadata."""
    assert QuickscaleFormsConfig.name == "quickscale_modules_forms"
    assert QuickscaleFormsConfig.label == "quickscale_modules_forms"
    assert QuickscaleFormsConfig.verbose_name == "QuickScale Forms"
    assert QuickscaleFormsConfig.default_auto_field == "django.db.models.BigAutoField"


def test_app_config_ready_is_safe_to_call() -> None:
    """AppConfig.ready() should not raise when all required settings are present."""
    config = QuickscaleFormsConfig(
        "quickscale_modules_forms",
        import_module("quickscale_modules_forms"),
    )

    assert config.ready() is None


def test_ready_raises_improperly_configured_when_submissions_api_missing(
    settings,
) -> None:
    """Missing FORMS_SUBMISSIONS_API must raise at startup."""
    del settings.FORMS_SUBMISSIONS_API

    config = QuickscaleFormsConfig(
        "quickscale_modules_forms",
        import_module("quickscale_modules_forms"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="FORMS_SUBMISSIONS_API",
    ):
        config.ready()


def test_ready_raises_improperly_configured_when_rate_limit_missing(
    settings,
) -> None:
    """Missing FORMS_RATE_LIMIT must raise at startup."""
    del settings.FORMS_RATE_LIMIT

    config = QuickscaleFormsConfig(
        "quickscale_modules_forms",
        import_module("quickscale_modules_forms"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="FORMS_RATE_LIMIT",
    ):
        config.ready()


def test_ready_raises_improperly_configured_when_spam_protection_missing(
    settings,
) -> None:
    """Missing FORMS_SPAM_PROTECTION must raise at startup."""
    del settings.FORMS_SPAM_PROTECTION

    config = QuickscaleFormsConfig(
        "quickscale_modules_forms",
        import_module("quickscale_modules_forms"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="FORMS_SPAM_PROTECTION",
    ):
        config.ready()
