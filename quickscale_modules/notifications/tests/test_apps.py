"""Tests for notifications app registration."""

from django.apps import apps


def test_app_config_is_registered() -> None:
    config = apps.get_app_config("quickscale_modules_notifications")

    assert config.name == "quickscale_modules_notifications"
    assert config.verbose_name == "QuickScale Notifications"
