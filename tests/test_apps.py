"""Tests for blog AppConfig startup behavior.

Fail-hard blog module settings: ``AppConfig.ready()`` must raise
``ImproperlyConfigured`` when ``QUICKSCALE_BLOG_RSS_ENABLED`` or ``MEDIA_URL`` is
missing.
"""

from importlib import import_module
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured


from quickscale_modules_blog.apps import QuickscaleBlogConfig
from quickscale_modules_orgs.removal import BLOG_PERSONAL_DATA, RemovalAction


def test_app_config_exposes_expected_metadata() -> None:
    """AppConfig should expose the expected blog module metadata."""
    assert QuickscaleBlogConfig.name == "quickscale_modules_blog"
    assert QuickscaleBlogConfig.label == "quickscale_blog"
    assert QuickscaleBlogConfig.verbose_name == "QuickScale Blog"
    assert QuickscaleBlogConfig.default_auto_field == "django.db.models.BigAutoField"


def test_app_config_declares_its_removal_label_prefix() -> None:
    """Rule 34: the purge summary takes blog's display prefix from here."""
    assert QuickscaleBlogConfig.removal_label_prefix == "Blog"


def test_app_config_declares_the_author_profile_personal_data_obligation() -> None:
    """The profile fields are blog's own anonymize obligation."""
    config = QuickscaleBlogConfig(
        "quickscale_modules_blog",
        import_module("quickscale_modules_blog"),
    )

    (obligation,) = config.removal_obligations()

    assert obligation.name == BLOG_PERSONAL_DATA
    assert obligation.anonymize_action is RemovalAction.ANONYMIZE
    assert obligation.purge_action is RemovalAction.SKIP
    assert callable(config.anonymize_account)
    assert config.anonymize_handlers() == (config,)


def test_media_url_check_is_skipped_when_disabled(settings: Any) -> None:
    """Rule 1 (D3): a switched-off blog does not require MEDIA_URL."""
    from quickscale_modules_blog.checks import check_media_url

    settings.QUICKSCALE_BLOG_ENABLED = False
    settings.MEDIA_URL = "/"
    assert check_media_url() == []


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
    """Missing QUICKSCALE_BLOG_RSS_ENABLED must raise at startup."""
    del settings.QUICKSCALE_BLOG_RSS_ENABLED

    config = QuickscaleBlogConfig(
        "quickscale_modules_blog",
        import_module("quickscale_modules_blog"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="QUICKSCALE_BLOG_RSS_ENABLED",
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


def test_ready_raises_improperly_configured_when_retired_setting_present(
    settings: Any,
) -> None:
    """Rule 6: a retired blog setting fails startup naming the replacement."""
    settings.BLOG_POSTS_PER_PAGE = 10

    config = QuickscaleBlogConfig(
        "quickscale_modules_blog",
        import_module("quickscale_modules_blog"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="QUICKSCALE_BLOG_POSTS_PER_PAGE",
    ):
        config.ready()


def test_ready_refuses_every_declared_retired_setting(settings: Any) -> None:
    """Rule 6: every declared retired blog name fails startup."""
    from quickscale_modules_blog.checks import RETIRED_SETTINGS

    config = QuickscaleBlogConfig(
        "quickscale_modules_blog",
        import_module("quickscale_modules_blog"),
    )

    for retired_name in RETIRED_SETTINGS:
        setattr(settings, retired_name, "legacy")
        try:
            with pytest.raises(ImproperlyConfigured, match=retired_name):
                config.ready()
        finally:
            delattr(settings, retired_name)


@pytest.mark.django_db
def test_missing_rss_setting_fails_check_migrate_and_runserver(settings: Any) -> None:
    """The registered blog check fails check, migrate, and runserver alike."""
    from django.core.management import call_command
    from django.core.management.base import SystemCheckError
    from django.core.management.commands import migrate, runserver

    del settings.QUICKSCALE_BLOG_RSS_ENABLED

    with pytest.raises(SystemCheckError, match="QUICKSCALE_BLOG_RSS_ENABLED"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="QUICKSCALE_BLOG_RSS_ENABLED"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="QUICKSCALE_BLOG_RSS_ENABLED"):
        runserver.Command().check()
