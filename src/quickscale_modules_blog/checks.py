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

from django.conf import settings
from django.core.checks import CheckMessage, Error


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
