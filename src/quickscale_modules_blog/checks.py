"""Startup checks for the QuickScale blog module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, so a failure refuses
``runserver``, ``migrate``, and ``manage.py check`` alike.

Rule 12: a module check covers what options cannot express.  The blog
module's declared options are validated by the generic settings check
(``register_module_settings_check``); the check here is the operational
``MEDIA_URL`` requirement the manifest cannot state.
"""

from __future__ import annotations

from collections.abc import Mapping

from django.conf import settings
from django.core.checks import CheckMessage, Error

#: Retired setting names refused at startup, each naming its replacement
#: (rule 6).  The declaration lives here, with the module's other checks,
#: because the refusal must work before the project is re-applied: the
#: settings a previous release wrote are exactly the ones still carrying
#: these names.
RETIRED_SETTINGS: Mapping[str, str] = {
    "BLOG_API_ALLOWED_IMAGE_FORMATS": (
        "Legacy setting 'BLOG_API_ALLOWED_IMAGE_FORMATS' is no longer supported. "
        "Use 'QUICKSCALE_BLOG_API_ALLOWED_IMAGE_FORMATS' instead."
    ),
    "BLOG_API_RATE_LIMIT": (
        "Legacy setting 'BLOG_API_RATE_LIMIT' is no longer supported. "
        "Use 'QUICKSCALE_BLOG_API_RATE_LIMIT' instead."
    ),
    "BLOG_API_UPLOAD_MAX_BYTES": (
        "Legacy setting 'BLOG_API_UPLOAD_MAX_BYTES' is no longer supported. "
        "Use 'QUICKSCALE_BLOG_API_UPLOAD_MAX_BYTES' instead."
    ),
    "BLOG_API_UPLOAD_MAX_HEIGHT": (
        "Legacy setting 'BLOG_API_UPLOAD_MAX_HEIGHT' is no longer supported. "
        "Use 'QUICKSCALE_BLOG_API_UPLOAD_MAX_HEIGHT' instead."
    ),
    "BLOG_API_UPLOAD_MAX_WIDTH": (
        "Legacy setting 'BLOG_API_UPLOAD_MAX_WIDTH' is no longer supported. "
        "Use 'QUICKSCALE_BLOG_API_UPLOAD_MAX_WIDTH' instead."
    ),
    "BLOG_ENABLE_RSS": (
        "Legacy setting 'BLOG_ENABLE_RSS' is no longer supported. "
        "Use 'QUICKSCALE_BLOG_RSS_ENABLED' instead."
    ),
    "BLOG_POSTS_PER_PAGE": (
        "Legacy setting 'BLOG_POSTS_PER_PAGE' is no longer supported. "
        "Use 'QUICKSCALE_BLOG_POSTS_PER_PAGE' instead."
    ),
}


def check_media_url(
    app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup when ``MEDIA_URL`` is not explicitly configured."""
    messages: list[CheckMessage] = []

    # -- MEDIA_URL must be explicitly configured (no fallback to '/media/') --
    # Note: Django always defines MEDIA_URL (default "") and normalizes
    # empty values to "/", so we reject that trivial sentinel.
    media_url_value = str(settings.MEDIA_URL).strip()
    if not media_url_value or media_url_value == "/":
        messages.append(
            Error(
                "MEDIA_URL must be explicitly configured for the blog module",
                id="quickscale_blog.E002",
            )
        )

    return messages
