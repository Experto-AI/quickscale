"""Tests for Forms AppConfig startup behavior.

Fail-hard forms settings: ``AppConfig.ready()`` must raise
``ImproperlyConfigured`` when any of ``QUICKSCALE_FORMS_API_ENABLED``,
``QUICKSCALE_FORMS_RATE_LIMIT``, or ``QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED`` is missing from
Django settings.
"""

from importlib import import_module

import pytest
from django.core.exceptions import ImproperlyConfigured

from quickscale_modules_forms.apps import QuickscaleFormsConfig


def test_app_config_exposes_expected_metadata() -> None:
    """AppConfig should expose the expected Forms module metadata."""
    assert QuickscaleFormsConfig.name == "quickscale_modules_forms"
    assert QuickscaleFormsConfig.label == "quickscale_forms"
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
    """Missing QUICKSCALE_FORMS_API_ENABLED must raise at startup."""
    del settings.QUICKSCALE_FORMS_API_ENABLED

    config = QuickscaleFormsConfig(
        "quickscale_modules_forms",
        import_module("quickscale_modules_forms"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="QUICKSCALE_FORMS_API_ENABLED",
    ):
        config.ready()


def test_ready_raises_improperly_configured_when_rate_limit_missing(
    settings,
) -> None:
    """Missing QUICKSCALE_FORMS_RATE_LIMIT must raise at startup."""
    del settings.QUICKSCALE_FORMS_RATE_LIMIT

    config = QuickscaleFormsConfig(
        "quickscale_modules_forms",
        import_module("quickscale_modules_forms"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="QUICKSCALE_FORMS_RATE_LIMIT",
    ):
        config.ready()


def test_ready_raises_improperly_configured_when_spam_protection_missing(
    settings,
) -> None:
    """Missing QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED must raise at startup."""
    del settings.QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED

    config = QuickscaleFormsConfig(
        "quickscale_modules_forms",
        import_module("quickscale_modules_forms"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED",
    ):
        config.ready()


def test_ready_raises_improperly_configured_when_retired_setting_present(
    settings,
) -> None:
    """Rule 6: a retired forms setting fails startup naming the replacement."""
    settings.FORMS_PER_PAGE = 25

    config = QuickscaleFormsConfig(
        "quickscale_modules_forms",
        import_module("quickscale_modules_forms"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE",
    ):
        config.ready()


def test_ready_refuses_every_declared_retired_setting(settings) -> None:
    """Rule 6: every declared retired forms name fails startup."""
    from quickscale_modules_forms.checks import RETIRED_SETTINGS

    config = QuickscaleFormsConfig(
        "quickscale_modules_forms",
        import_module("quickscale_modules_forms"),
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
    """The registered forms check fails check, migrate, and runserver alike."""
    from django.core.management import call_command
    from django.core.management.base import SystemCheckError
    from django.core.management.commands import migrate, runserver

    del settings.QUICKSCALE_FORMS_RATE_LIMIT

    with pytest.raises(SystemCheckError, match="QUICKSCALE_FORMS_RATE_LIMIT"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="QUICKSCALE_FORMS_RATE_LIMIT"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="QUICKSCALE_FORMS_RATE_LIMIT"):
        runserver.Command().check()
