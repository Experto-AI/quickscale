"""Private settings snapshot for the analytics module.

Rule 42: the runtime view of the module's settings lives here as a frozen
dataclass built by ``from_settings()``, reading each setting directly with no
default and no coercion.  ``services.py`` re-exports the names defined here
(Module Conventions rule 28) so existing imports and patch targets keep
working; the snapshot stays out of ``services.__all__``.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class AnalyticsRuntimeSettingsSnapshot:
    """Immutable runtime view of the analytics settings contract."""

    enabled: bool
    provider: str
    posthog_api_key_env_var: str
    posthog_host_env_var: str
    posthog_host: str
    exclude_debug: bool
    exclude_staff: bool
    anonymous_by_default: bool

    @classmethod
    def from_settings(cls) -> AnalyticsRuntimeSettingsSnapshot:
        """Create a runtime snapshot from Django settings.

        Rule 3: every value is read directly; apply wrote the canonical
        values and the module's startup check has validated them, so the
        snapshot neither defaults nor coerces.
        """
        return cls(
            enabled=bool(settings.QUICKSCALE_ANALYTICS_ENABLED),
            provider=str(settings.QUICKSCALE_ANALYTICS_PROVIDER),
            posthog_api_key_env_var=str(
                settings.QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR
            ),
            posthog_host_env_var=str(
                settings.QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR
            ),
            posthog_host=str(settings.QUICKSCALE_ANALYTICS_POSTHOG_HOST),
            exclude_debug=bool(settings.QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG),
            exclude_staff=bool(settings.QUICKSCALE_ANALYTICS_EXCLUDE_STAFF),
            anonymous_by_default=bool(
                settings.QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT
            ),
        )

    def resolve_posthog_api_key(self) -> str:
        """Resolve the PostHog API key from the applied secret setting (rule 35)."""
        return str(settings.QUICKSCALE_ANALYTICS_POSTHOG_API_KEY).strip()

    def resolve_posthog_host(self) -> str:
        """Resolve the PostHog host override from the applied setting, else the fallback."""
        return (
            str(settings.QUICKSCALE_ANALYTICS_POSTHOG_HOST_OVERRIDE).strip()
            or self.posthog_host.strip()
        )


def get_analytics_runtime_settings() -> AnalyticsRuntimeSettingsSnapshot:
    """Return the active analytics settings snapshot."""
    return AnalyticsRuntimeSettingsSnapshot.from_settings()
