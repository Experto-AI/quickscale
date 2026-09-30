"""Startup checks for the QuickScale analytics module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, so a failure refuses
``runserver``, ``migrate``, and ``manage.py check`` alike.

Rule 12: the declared options (presence, type, choices) are validated by the
generic settings check registered alongside this one.  This check covers what
options cannot express: the resolved PostHog host must be a usable absolute
URL, and a live runtime must resolve a non-empty API key.  While a declared
setting is absent the check stays silent — the generic check reports it.

Analytics distinguishes invalid configuration from an unreachable vendor: an
invalid host or an empty PostHog key for live analytics fails startup, while
a PostHog client that cannot initialize at startup is logged and tolerated.
"""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import CheckMessage, Error

from quickscale_modules_analytics.services import (
    AnalyticsRuntimeSettingsSnapshot,
)

#: The declared settings this check reads.  Presence is the generic settings
#: check's concern; the guard below keeps this check from raising when one is
#: missing, so ``manage.py check`` reports the missing setting instead.
_DECLARED_SETTINGS = (
    "QUICKSCALE_ANALYTICS_ENABLED",
    "QUICKSCALE_ANALYTICS_PROVIDER",
    "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
    "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
    "QUICKSCALE_ANALYTICS_POSTHOG_HOST",
    "QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG",
    "QUICKSCALE_ANALYTICS_EXCLUDE_STAFF",
    "QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT",
)


def check_analytics_settings(
    app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup on an invalid resolved analytics runtime.

    The resolved host must be an absolute http(s) URL with a hostname and a
    valid port, and a live runtime must resolve a non-empty PostHog API key.
    A runtime that analytics itself excludes (``DEBUG`` with
    ``QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG``) does not need the key, because the
    configurator disables capture before it resolves one.
    """
    if any(not hasattr(settings, name) for name in _DECLARED_SETTINGS):
        return []

    messages: list[CheckMessage] = []
    snapshot = AnalyticsRuntimeSettingsSnapshot.from_settings()
    if not snapshot.enabled:
        return messages

    if snapshot.exclude_debug and bool(settings.DEBUG):
        return messages

    host = snapshot.resolve_posthog_host()
    parsed_host = urlparse(host)
    try:
        parsed_port = parsed_host.port
        invalid_port = parsed_host.netloc.endswith(":") or (
            parsed_port is not None and not 1 <= parsed_port <= 65535
        )
    except ValueError:
        invalid_port = True
    if (
        parsed_host.scheme not in {"http", "https"}
        or not parsed_host.netloc
        or not parsed_host.hostname
        or invalid_port
    ):
        messages.append(
            Error(
                "QUICKSCALE_ANALYTICS_POSTHOG_HOST must be an absolute http(s) "
                f"URL with a hostname and a valid port, got {host!r}.",
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
