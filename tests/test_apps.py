"""Tests for listings app configuration."""

import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured


def test_listings_app_config_matches_packaged_module_contract() -> None:
    """The packaged app config should expose the expected name, label, and title."""
    config = apps.get_app_config("quickscale_listings")

    assert config.name == "quickscale_modules_listings"
    assert config.label == "quickscale_listings"
    assert config.verbose_name == "QuickScale Listings"
    assert config.default_auto_field == "django.db.models.BigAutoField"


def test_startup_check_refuses_a_wrong_typed_setting(settings) -> None:
    """Rule 3: a wrong-typed declared setting fails startup naming the setting."""
    settings.LISTINGS_PER_PAGE = "12"

    with pytest.raises(ImproperlyConfigured, match="LISTINGS_PER_PAGE"):
        apps.get_app_config("quickscale_listings").ready()
