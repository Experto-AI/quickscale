"""Startup checks for the QuickScale analytics module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, so a failure refuses
``runserver``, ``migrate``, and ``manage.py check`` alike.

Rule 12: the declared options (presence, type, choices) are validated by the
generic settings check registered first; this check covers what options
cannot express: the resolved PostHog host must be a usable absolute URL, and
a live runtime must resolve a non-empty API key.

Analytics distinguishes invalid configuration from an unreachable vendor: an
invalid host or an empty PostHog key for live analytics fails startup, while
a PostHog client that cannot initialize at startup is logged and tolerated.
"""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import CheckMessage, Error

from quickscale_core.runtime import module_settings_are_supplied
from quickscale_modules_analytics._settings import (
    AnalyticsRuntimeSettingsSnapshot,
)

# The projected settings apply writes beyond the declared options — the
# `_ENV_VAR` secret settings (rule 35) and the manifest's derived settings —
# are validated by the generic settings check (rule 10), which names a
# missing one before this check reads it; a module check does not re-test a
# projected setting's presence.


def check_analytics_settings(
    _app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup on an invalid resolved analytics runtime.

    The resolved host must be an absolute http(s) URL with a hostname and a
    valid port, and a live runtime must resolve a non-empty PostHog API key.
    A runtime that analytics itself excludes (``DEBUG`` with
    ``QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG``) does not need the key, because the
    configurator disables capture before it resolves one.
    """
    if not module_settings_are_supplied("analytics"):
        # The generic settings check names the missing declared setting;
        # Django runs every registered check independently, so this check
        # stays silent until the project is fully applied.
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
