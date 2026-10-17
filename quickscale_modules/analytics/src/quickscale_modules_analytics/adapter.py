"""Module-owned analytics manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import (
    ModuleWiringSpec,
    ResolvedOptions,
    build_generic_manifest_spec,
)


def _analytics_post_hook(
    spec: ModuleWiringSpec, resolved: ResolvedOptions
) -> ModuleWiringSpec:
    """Apply analytics' off-switch transformation.

    Rule 1 (D3): off keeps the module installed — app, middleware, and
    settings — and mounts none of its public URLs.  The template tag library
    stays registered because the app stays.  The manifest boundary already
    owns every option default, normalization rule, and check, and projects
    the complete settings surface (environment-variable references included)
    before this hook runs, so the settings surface does not change with the
    switch.
    """
    if resolved.enabled:
        return spec
    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=spec.settings,
        pre_home_url_includes=(),
        url_includes=(),
        spa_routes=(),
        managed_files=spec.managed_files,
        throttle_scopes=spec.throttle_scopes,
    )


def _analytics_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for analytics via its manifest."""
    del project_package
    return build_generic_manifest_spec(
        "analytics",
        options,
        post_hook=_analytics_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the analytics module's manifest adapter callable."""
    return _analytics_manifest_adapter
