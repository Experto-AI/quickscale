"""Startup checks for the QuickScale analytics module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, so a failure refuses
``runserver``, ``migrate``, and ``manage.py check`` alike.

Analytics distinguishes invalid configuration from an unreachable vendor: an
unsupported provider or an empty PostHog key for live analytics fails
startup, while a PostHog client that cannot initialize at startup is logged
and tolerated.
"""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import CheckMessage, Error

from quickscale_modules_analytics.services import (
    ANALYTICS_PROVIDER_POSTHOG,
    AnalyticsRuntimeSettingsSnapshot,
)


def check_analytics_settings(
    app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup on invalid analytics configuration.

    Invalid configuration is a missing ``QUICKSCALE_ANALYTICS_ENABLED`` flag,
    an unsupported provider, or an empty PostHog API key while analytics is
    live.  A runtime that analytics itself excludes (``DEBUG`` with
    ``QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG``) does not need the key, because the
    configurator disables capture before it resolves one.
    """
    messages: list[CheckMessage] = []
    if not hasattr(settings, "QUICKSCALE_ANALYTICS_ENABLED"):
        messages.append(
            Error(
                "The QUICKSCALE_ANALYTICS_ENABLED setting is required. "
                "Set it to True or False in your Django settings.",
                id="quickscale_analytics.E001",
            )
        )
        return messages

    snapshot = AnalyticsRuntimeSettingsSnapshot.from_settings()
    if not snapshot.enabled:
        return messages

    if snapshot.provider != ANALYTICS_PROVIDER_POSTHOG:
        messages.append(
            Error(
                "QUICKSCALE_ANALYTICS_PROVIDER must be "
                f"{ANALYTICS_PROVIDER_POSTHOG!r}, got {snapshot.provider!r}. "
                "Set the provider or set QUICKSCALE_ANALYTICS_ENABLED=False.",
                id="quickscale_analytics.E002",
            )
        )
        return messages

    if snapshot.exclude_debug and bool(getattr(settings, "DEBUG", False)):
        return messages

    host = snapshot.resolve_posthog_host()
    parsed_host = urlparse(host)
    if (
        parsed_host.scheme not in {"http", "https"}
        or not parsed_host.netloc
        or not parsed_host.hostname
    ):
        messages.append(
            Error(
                "QUICKSCALE_ANALYTICS_POSTHOG_HOST must be an absolute http(s) "
                f"URL with a hostname, got {host!r}.",
                id="quickscale_analytics.E004",
            )
        )

    if not snapshot.resolve_posthog_api_key():
        messages.append(
            Error(
                "Analytics is enabled but the PostHog API key environment "
                f"variable {snapshot.posthog_api_key_env_var!r} named by "
                "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR is empty. Set "
                "the key or set QUICKSCALE_ANALYTICS_ENABLED=False.",
                id="quickscale_analytics.E003",
            )
        )
    return messages
