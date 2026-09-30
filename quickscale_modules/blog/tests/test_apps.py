"""Tests for blog AppConfig startup behavior.

Fail-hard blog module settings: ``AppConfig.ready()`` must raise
``ImproperlyConfigured`` when ``BLOG_ENABLE_RSS`` or ``MEDIA_URL`` is
missing.
"""

from importlib import import_module
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured


from quickscale_modules_blog.apps import QuickscaleBlogConfig


def test_app_config_exposes_expected_metadata() -> None:
    """AppConfig should expose the expected blog module metadata."""
    assert QuickscaleBlogConfig.name == "quickscale_modules_blog"
    assert QuickscaleBlogConfig.label == "quickscale_blog"
    assert QuickscaleBlogConfig.verbose_name == "QuickScale Blog"
    assert QuickscaleBlogConfig.default_auto_field == "django.db.models.BigAutoField"


def test_app_config_ready_is_safe_to_call() -> None:
    """AppConfig.ready() should not raise when all required settings are present."""
    config = QuickscaleBlogConfig(
        "quickscale_modules_blog",
        import_module("quickscale_modules_blog"),
    )

    # ready() returns None implicitly; calling it without raising is the check.
    config.ready()


def test_ready_raises_improperly_configured_when_blog_enable_rss_missing(
    settings: Any,
) -> None:
    """Missing BLOG_ENABLE_RSS must raise at startup."""
    del settings.BLOG_ENABLE_RSS

    config = QuickscaleBlogConfig(
        "quickscale_modules_blog",
        import_module("quickscale_modules_blog"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="BLOG_ENABLE_RSS",
    ):
        config.ready()


def test_ready_raises_improperly_configured_when_media_url_is_trivial(
    settings: Any,
) -> None:
    """Trivial MEDIA_URL ('/') must raise at startup.

    Django normalizes empty MEDIA_URL to ``/``, so we treat that
    sentinel value as "not explicitly configured".
    """
    settings.MEDIA_URL = "/"

    config = QuickscaleBlogConfig(
        "quickscale_modules_blog",
        import_module("quickscale_modules_blog"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="MEDIA_URL",
    ):
        config.ready()


@pytest.mark.django_db
def test_missing_rss_setting_fails_check_migrate_and_runserver(settings: Any) -> None:
    """The registered blog check fails check, migrate, and runserver alike."""
    from django.core.management import call_command
    from django.core.management.base import SystemCheckError
    from django.core.management.commands import migrate, runserver

    del settings.BLOG_ENABLE_RSS

    with pytest.raises(SystemCheckError, match="BLOG_ENABLE_RSS"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="BLOG_ENABLE_RSS"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="BLOG_ENABLE_RSS"):
        runserver.Command().check()
