"""Tests for billing app registration."""

from django.apps import apps


def test_app_config_is_registered() -> None:
    config = apps.get_app_config("quickscale_modules_billing")

    assert config.name == "quickscale_modules_billing"
    assert config.label == "quickscale_modules_billing"
    assert config.verbose_name == "QuickScale Billing"
    assert config.default_auto_field == "django.db.models.BigAutoField"
