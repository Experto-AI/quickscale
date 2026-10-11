"""Module-owned listings manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import ModuleWiringSpec, build_generic_manifest_spec


def _listings_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Contribute listings' throttle scope and apply its off-switch transformation.

    Rule 32 — the publish scope carries the module stem and its rate is the
    ``api_rate_limit`` option, contributed here for rule 30's merge; the
    canonical value arrives from the manifest boundary.  Rule 1 (D3): off
    keeps the module installed — app, migrations, admin, and settings — and
    mounts none of its public URLs.  The retained admin editor
    (``AdminMarkdownxWidget``) keeps its staff-guarded endpoint mount; the
    manifest already points that mount at the module's guarded URLconf, never
    at the shared ``markdownx.urls``.
    """
    settings = dict(spec.settings)
    settings["REST_FRAMEWORK"] = {
        "DEFAULT_THROTTLE_RATES": {
            "quickscale_listings_api": settings["QUICKSCALE_LISTINGS_API_RATE_LIMIT"],
        },
    }
    if resolved["enabled"]:
        return ModuleWiringSpec(
            apps=spec.apps,
            middleware=spec.middleware,
            settings=settings,
            pre_home_url_includes=spec.pre_home_url_includes,
            url_includes=spec.url_includes,
            spa_routes=spec.spa_routes,
            managed_files=spec.managed_files,
        )
    editor_includes = tuple(
        (prefix, target)
        for prefix, target in spec.url_includes
        if target == "quickscale_modules_listings.markdownx_urls"
    )
    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=(),
        url_includes=editor_includes,
        spa_routes=(),
        managed_files=spec.managed_files,
    )


def _listings_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for listings via its manifest."""
    del project_package
    return build_generic_manifest_spec(
        "listings",
        options,
        post_hook=_listings_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the listings module's manifest adapter callable."""
    return _listings_manifest_adapter
