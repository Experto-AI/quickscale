"""Module-owned blog manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import ModuleWiringSpec, build_generic_manifest_spec


def _blog_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Contribute blog's throttle scopes and apply its off-switch transformation.

    Rule 32 — the blog automation API's scope carries the module stem and its
    rate is the module's ``api_rate_limit`` option, contributed here for rule
    30's merge.  The option's canonical value arrives from the manifest
    boundary; the hook never re-coerces or re-reads a raw option.  Rule 1
    (D3): off keeps the module installed — app, migrations, admin, and
    settings — and mounts none of its public URLs.  The retained admin editor
    (``MarkdownxModelAdmin``) keeps its staff-guarded endpoint mount; the
    manifest already points that mount at the module's guarded URLconf, never
    at the shared ``markdownx.urls``.
    """
    settings = dict(spec.settings)
    settings["REST_FRAMEWORK"] = {
        "DEFAULT_THROTTLE_RATES": {
            "quickscale_blog_api": settings["QUICKSCALE_BLOG_API_RATE_LIMIT"],
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
        if target == "quickscale_modules_blog.markdownx_urls"
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


def _blog_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for blog via its manifest."""
    del project_package
    return build_generic_manifest_spec(
        "blog",
        options,
        post_hook=_blog_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the blog module's manifest adapter callable."""
    return _blog_manifest_adapter
