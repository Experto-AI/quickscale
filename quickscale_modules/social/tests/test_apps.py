"""Tests for social app configuration."""

from django.apps import apps


def test_social_app_config_matches_packaged_module_contract() -> None:
    """The packaged app config should expose the expected name, label, and title."""
    config = apps.get_app_config("quickscale_modules_social")

    assert config.name == "quickscale_modules_social"
    assert config.label == "quickscale_modules_social"
    assert config.verbose_name == "QuickScale Social"
    assert config.default_auto_field == "django.db.models.BigAutoField"
