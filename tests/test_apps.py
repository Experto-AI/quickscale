"""Tests for the orgs AppConfig startup behavior."""

from __future__ import annotations

from importlib import import_module

from django.apps import apps

from quickscale_modules_orgs.apps import QuickscaleOrgsConfig
from quickscale_modules_orgs.checks import check_quickscale_mode
from quickscale_modules_orgs.removal import (
    OWNED_TENANT_ROWS,
    PURGE_TOMBSTONE,
    SOCIAL_CACHE_STATE,
)


def test_app_config_exposes_expected_metadata() -> None:
    """The packaged app config should expose the expected name, label, and title."""
    config = apps.get_app_config("quickscale_orgs")

    assert config.name == "quickscale_modules_orgs"
    assert config.label == "quickscale_orgs"
    assert config.verbose_name == "QuickScale Organizations"
    assert config.default_auto_field == "django.db.models.BigAutoField"


def test_app_config_declares_its_removal_obligations() -> None:
    """orgs declares the obligations it owns on its AppConfig."""
    config = QuickscaleOrgsConfig(
        "quickscale_modules_orgs",
        import_module("quickscale_modules_orgs"),
    )

    obligation_names = {obligation.name for obligation in config.removal_obligations()}

    assert obligation_names == {
        OWNED_TENANT_ROWS,
        SOCIAL_CACHE_STATE,
        PURGE_TOMBSTONE,
    }


def test_mode_check_passes_when_setting_present(settings) -> None:
    """A supported ``QUICKSCALE_MODE`` reports no failure."""
    settings.QUICKSCALE_MODE = "solo"

    assert check_quickscale_mode() == []


def test_mode_check_reports_missing_setting(settings) -> None:
    """A missing ``QUICKSCALE_MODE`` is reported by name."""
    del settings.QUICKSCALE_MODE

    messages = check_quickscale_mode()

    assert messages
    assert "QUICKSCALE_MODE" in messages[0].msg
