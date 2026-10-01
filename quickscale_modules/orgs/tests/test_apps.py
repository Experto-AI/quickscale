"""Tests for the orgs AppConfig startup behavior."""

from __future__ import annotations

from importlib import import_module

from django.apps import apps

import pytest
from django.core.exceptions import ImproperlyConfigured

from quickscale_modules_orgs.apps import QuickscaleOrgsConfig
from quickscale_modules_orgs._redirects import post_login_redirect, post_signup_redirect
from quickscale_modules_orgs.removal import (
    OWNED_TENANT_ROWS,
    PURGE_TOMBSTONE,
    SOCIAL_CACHE_STATE,
    RemovalBoundary,
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


def test_app_config_declares_its_removal_boundary_implementation() -> None:
    """Each removal boundary's owner declares where its implementation lives."""
    config = QuickscaleOrgsConfig(
        "quickscale_modules_orgs",
        import_module("quickscale_modules_orgs"),
    )

    assert config.removal_boundary_implementations()[RemovalBoundary.PURGE] == (
        "quickscale_modules_orgs",
        "quickscale_modules_orgs.management.commands."
        "quickscale_orgs_purge_organization",
        "Command.handle",
    )


def test_app_config_declares_post_auth_redirect_hooks() -> None:
    """Rule 4: orgs declares its redirects as capabilities, not an adapter.

    Auth's single allauth adapter collects these hooks, so orgs imports no
    part of auth and the ``auth ↔ orgs`` import cycle stays broken.
    """
    config = QuickscaleOrgsConfig(
        "quickscale_modules_orgs",
        import_module("quickscale_modules_orgs"),
    )

    assert config.post_login_redirect_hooks() == (post_login_redirect,)
    assert config.post_signup_redirect_hooks() == (post_signup_redirect,)


def test_invalidate_organization_cache_collects_declared_keys(monkeypatch) -> None:
    """The obligation executor clears the keys installed apps declare."""
    from django.core.cache import cache

    cache.set("qs-test-org-cache-key", "cached")
    requested: list[str] = []

    def fake_collect(capability: str) -> tuple:
        requested.append(capability)
        return (lambda organization_id: ("qs-test-org-cache-key",),)

    monkeypatch.setattr(
        "quickscale_core.runtime.collect_capabilities",
        fake_collect,
    )
    config = QuickscaleOrgsConfig(
        "quickscale_modules_orgs",
        import_module("quickscale_modules_orgs"),
    )

    config.invalidate_organization_cache("00000000-0000-0000-0000-000000000042")

    assert requested == ["organization_cache_keys"]
    assert cache.get("qs-test-org-cache-key") is None


def test_startup_check_refuses_a_missing_mode(settings) -> None:
    """Rule 3: the generic settings check refuses a missing declared setting."""
    del settings.QUICKSCALE_MODE

    config = QuickscaleOrgsConfig(
        "quickscale_modules_orgs",
        import_module("quickscale_modules_orgs"),
    )

    with pytest.raises(ImproperlyConfigured, match="QUICKSCALE_MODE"):
        config.ready()
