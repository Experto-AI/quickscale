"""Tests for listings app configuration."""

from django.apps import apps


def test_listings_app_config_matches_packaged_module_contract() -> None:
    """The packaged app config should expose the expected name, label, and title."""
    config = apps.get_app_config("quickscale_listings")

    assert config.name == "quickscale_modules_listings"
    assert config.label == "quickscale_listings"
    assert config.verbose_name == "QuickScale Listings"
    assert config.default_auto_field == "django.db.models.BigAutoField"
