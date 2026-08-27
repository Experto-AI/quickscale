"""Module-owned analytics manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import (
    ManifestError,
    ModuleWiringSpec,
    build_generic_manifest_spec,
)


def _analytics_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply analytics-specific type coercions and fallback defaults."""
    settings = dict(spec.settings)
    for bool_key in (
        "QUICKSCALE_ANALYTICS_ENABLED",
        "QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG",
        "QUICKSCALE_ANALYTICS_EXCLUDE_STAFF",
        "QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT",
    ):
        if bool_key in settings:
            settings[bool_key] = bool(settings[bool_key])

    for str_key in (
        "QUICKSCALE_ANALYTICS_PROVIDER",
        "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST",
    ):
        if str_key in settings:
            settings[str_key] = str(settings[str_key]).strip()

    # Analytics remains disabled in the app and URL wiring when requested, but
    # its manifest-owned settings still need to reach generated settings.
    if not bool(resolved["enabled"]):
        return ModuleWiringSpec(settings=settings)

    required_nonempty = (
        "QUICKSCALE_ANALYTICS_PROVIDER",
        "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST",
    )
    empty_keys = [
        key for key in required_nonempty if key in settings and not settings[key]
    ]
    if empty_keys:
        raise ManifestError(
            "Analytics manifest settings resolved to empty values: "
            f"{', '.join(sorted(empty_keys))}. "
            "The manifest derivation produced an invalid result."
        )

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _analytics_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for analytics via its manifest."""
    return build_generic_manifest_spec(
        "analytics",
        options,
        post_hook=_analytics_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the analytics module's manifest adapter callable."""
    return _analytics_manifest_adapter
