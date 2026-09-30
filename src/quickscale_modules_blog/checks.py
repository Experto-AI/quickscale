"""Startup checks for the QuickScale blog module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, so a failure refuses
``runserver``, ``migrate``, and ``manage.py check`` alike.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import CheckMessage, Error


def check_required_settings(
    app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup when a required blog setting is absent or trivial."""
    messages: list[CheckMessage] = []

    # -- BLOG_ENABLE_RSS must be explicitly set (no default True) --
    if getattr(settings, "BLOG_ENABLE_RSS", None) is None:
        messages.append(
            Error(
                "BLOG_ENABLE_RSS must be explicitly set to True or False",
                id="quickscale_blog.E001",
            )
        )

    # -- MEDIA_URL must be explicitly configured (no fallback to '/media/') --
    # Note: Django always defines MEDIA_URL (default "") and normalizes
    # empty values to "/", so we reject that trivial sentinel.
    media_url_value = str(getattr(settings, "MEDIA_URL", "")).strip()
    if not media_url_value or media_url_value == "/":
        messages.append(
            Error(
                "MEDIA_URL must be explicitly configured for the blog module",
                id="quickscale_blog.E002",
            )
        )

    return messages
