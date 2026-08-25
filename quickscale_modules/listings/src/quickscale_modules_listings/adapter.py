"""Module-owned listings manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import ModuleWiringSpec, build_generic_manifest_spec


def _listings_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply listings-specific int coercion and static markdownx settings."""
    settings = dict(spec.settings)
    settings["LISTINGS_PER_PAGE"] = int(settings["LISTINGS_PER_PAGE"])
    settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] = [
        "markdown.extensions.fenced_code",
        "markdown.extensions.tables",
        "markdown.extensions.toc",
    ]
    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
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
