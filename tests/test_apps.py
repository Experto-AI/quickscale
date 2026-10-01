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
    settings.QUICKSCALE_LISTINGS_PER_PAGE = "12"

    with pytest.raises(ImproperlyConfigured, match="QUICKSCALE_LISTINGS_PER_PAGE"):
        apps.get_app_config("quickscale_listings").ready()


def test_startup_check_refuses_a_retired_setting(settings) -> None:
    """Rule 6: a retired setting name fails startup naming the replacement."""
    settings.LISTINGS_PER_PAGE = 12

    with pytest.raises(ImproperlyConfigured, match="QUICKSCALE_LISTINGS_PER_PAGE"):
        apps.get_app_config("quickscale_listings").ready()


def test_startup_check_refuses_every_declared_retired_setting(settings) -> None:
    """Rule 6: every declared retired listings name fails startup."""
    from quickscale_modules_listings.checks import RETIRED_SETTINGS

    config = apps.get_app_config("quickscale_listings")

    for retired_name in RETIRED_SETTINGS:
        setattr(settings, retired_name, "legacy")
        try:
            with pytest.raises(ImproperlyConfigured, match=retired_name):
                config.ready()
        finally:
            delattr(settings, retired_name)
