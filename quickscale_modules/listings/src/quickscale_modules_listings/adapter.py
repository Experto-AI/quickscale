"""Module-owned listings manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import ModuleWiringSpec, build_generic_manifest_spec


def _listings_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply listings-specific int coercion and rule 30/32 contributions."""
    settings = dict(spec.settings)
    settings["QUICKSCALE_LISTINGS_PER_PAGE"] = int(
        settings["QUICKSCALE_LISTINGS_PER_PAGE"]
    )
    # Rule 32 — the publish scope carries the module stem and its rate is the
    # api_rate_limit option, contributed here for rule 30's merge.
    api_rate_limit = str(settings["QUICKSCALE_LISTINGS_API_RATE_LIMIT"]).strip()
    settings["REST_FRAMEWORK"] = {
        "DEFAULT_THROTTLE_RATES": {"quickscale_listings_api": api_rate_limit},
    }
    if not bool(resolved["enabled"]):
        # Rule 1 (D3): off keeps the module installed — app, migrations,
        # admin, and settings — and mounts none of its public URLs.  The
        # shared Markdownx editor mount stays with storage (rule 41).
        return ModuleWiringSpec(
            apps=spec.apps,
            middleware=spec.middleware,
            settings=settings,
            pre_home_url_includes=(),
            url_includes=(),
            spa_routes=(),
            managed_files=spec.managed_files,
        )
    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        spa_routes=spec.spa_routes,
        managed_files=spec.managed_files,
    )


def _listings_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for listings via its manifest."""
    return build_generic_manifest_spec(
        "listings",
        options,
        post_hook=_listings_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the listings module's manifest adapter callable."""
    return _listings_manifest_adapter
