"""Tests for blog AppConfig startup behavior.

SA17.5 — fail-hard blog module settings: ``AppConfig.ready()`` must raise
``ImproperlyConfigured`` when ``BLOG_ENABLE_RSS`` or ``MEDIA_URL`` is
missing, or when any ``BLOG_API_TOKENS`` entry is malformed.
"""

from importlib import import_module
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured


from quickscale_modules_blog.apps import QuickscaleBlogConfig


def test_app_config_exposes_expected_metadata() -> None:
    """AppConfig should expose the expected blog module metadata."""
    assert QuickscaleBlogConfig.name == "quickscale_modules_blog"
    assert QuickscaleBlogConfig.label == "quickscale_modules_blog"
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


class TestBlogApiTokensValidation:
    """Startup validation for BLOG_API_TOKENS entries (SA17.5)."""

    def test_missing_tokens_does_not_raise(self, settings: Any) -> None:
        """Absent BLOG_API_TOKENS should not trigger validation."""
        if hasattr(settings, "BLOG_API_TOKENS"):
            del settings.BLOG_API_TOKENS

        config = QuickscaleBlogConfig(
            "quickscale_modules_blog",
            import_module("quickscale_modules_blog"),
        )

        # ready() returns None implicitly; calling it without raising is the check.
        config.ready()

    def test_non_list_tokens_raises(self, settings: Any) -> None:
        """BLOG_API_TOKENS must be a list."""
        settings.BLOG_API_TOKENS = "not-a-list"

        config = QuickscaleBlogConfig(
            "quickscale_modules_blog",
            import_module("quickscale_modules_blog"),
        )

        with pytest.raises(
            ImproperlyConfigured,
            match="BLOG_API_TOKENS must be a list",
        ):
            config.ready()

    def test_non_dict_entry_raises(self, settings: Any) -> None:
        """Each BLOG_API_TOKENS entry must be a dict."""
        settings.BLOG_API_TOKENS = ["invalid-entry"]

        config = QuickscaleBlogConfig(
            "quickscale_modules_blog",
            import_module("quickscale_modules_blog"),
        )

        with pytest.raises(
            ImproperlyConfigured,
            match="BLOG_API_TOKENS\\[0\\].*not a dict",
        ):
            config.ready()

    def test_entry_missing_token_raises(self, settings: Any) -> None:
        """An entry without a 'token' key must raise naming the entry."""
        settings.BLOG_API_TOKENS = [
            {"username": "author"},
        ]

        config = QuickscaleBlogConfig(
            "quickscale_modules_blog",
            import_module("quickscale_modules_blog"),
        )

        with pytest.raises(
            ImproperlyConfigured,
            match="missing or empty 'token'",
        ):
            config.ready()

    def test_entry_empty_token_raises(self, settings: Any) -> None:
        """An entry with an empty 'token' must raise naming the entry."""
        settings.BLOG_API_TOKENS = [
            {"token": "", "username": "author"},
        ]

        config = QuickscaleBlogConfig(
            "quickscale_modules_blog",
            import_module("quickscale_modules_blog"),
        )

        with pytest.raises(
            ImproperlyConfigured,
            match="missing or empty 'token'",
        ):
            config.ready()

    def test_entry_missing_username_raises(self, settings: Any) -> None:
        """An entry without a 'username' key must raise naming the entry."""
        settings.BLOG_API_TOKENS = [
            {"token": "valid-token"},
        ]

        config = QuickscaleBlogConfig(
            "quickscale_modules_blog",
            import_module("quickscale_modules_blog"),
        )

        with pytest.raises(
            ImproperlyConfigured,
            match="missing or empty 'username'",
        ):
            config.ready()

    def test_entry_empty_username_raises(self, settings: Any) -> None:
        """An entry with an empty 'username' must raise naming the entry."""
        settings.BLOG_API_TOKENS = [
            {"token": "valid-token", "username": ""},
        ]

        config = QuickscaleBlogConfig(
            "quickscale_modules_blog",
            import_module("quickscale_modules_blog"),
        )

        with pytest.raises(
            ImproperlyConfigured,
            match="missing or empty 'username'",
        ):
            config.ready()

    def test_valid_entries_do_not_raise(self, settings: Any) -> None:
        """Well-formed BLOG_API_TOKENS entries should pass validation."""
        settings.BLOG_API_TOKENS = [
            {"token": "token-one", "username": "user-one"},
            {"token": "token-two", "username": "user-two"},
        ]

        config = QuickscaleBlogConfig(
            "quickscale_modules_blog",
            import_module("quickscale_modules_blog"),
        )

        # ready() returns None implicitly; calling it without raising is the check.
        config.ready()
