"""Module-owned listings manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import ModuleWiringSpec, build_generic_manifest_spec


def _listings_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply listings-specific int coercion and static markdownx settings."""
    settings = dict(spec.settings)
    settings["QUICKSCALE_LISTINGS_PER_PAGE"] = int(
        settings["QUICKSCALE_LISTINGS_PER_PAGE"]
    )
    settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] = [
        "markdown.extensions.fenced_code",
        "markdown.extensions.tables",
        "markdown.extensions.toc",
    ]
    if not bool(resolved["enabled"]):
        # Rule 1 (D3): off keeps the module installed — app, migrations,
        # admin, and settings — and mounts none of its public URLs.  The
        # retained admin editor (`AdminMarkdownxWidget`) keeps its
        # staff-guarded endpoint mount; the manifest already points that mount
        # at the module's guarded URLconf, never at the shared ``markdownx.urls``.
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
