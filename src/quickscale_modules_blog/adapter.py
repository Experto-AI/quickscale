"""Module-owned blog manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import (
    ManifestError,
    ModuleWiringSpec,
    build_generic_manifest_spec,
)


def _blog_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply blog-specific type coercions and static markdownx settings."""
    settings = dict(spec.settings)
    settings["QUICKSCALE_BLOG_POSTS_PER_PAGE"] = int(
        settings["QUICKSCALE_BLOG_POSTS_PER_PAGE"]
    )
    settings["QUICKSCALE_BLOG_RSS_ENABLED"] = bool(
        settings["QUICKSCALE_BLOG_RSS_ENABLED"]
    )
    api_rate = str(settings["QUICKSCALE_BLOG_API_RATE_LIMIT"]).strip()
    if not api_rate:
        raise ManifestError(
            "Blog manifest setting QUICKSCALE_BLOG_API_RATE_LIMIT resolved to empty value. "
            "The manifest derivation produced an invalid result."
        )
    settings["QUICKSCALE_BLOG_API_RATE_LIMIT"] = api_rate
    # Rule 32 — the blog automation API's scope carries the module stem and
    # its rate is the module's _RATE_LIMIT option, contributed here for rule
    # 30's merge.
    settings["REST_FRAMEWORK"] = {
        "DEFAULT_THROTTLE_RATES": {
            "quickscale_blog_api": api_rate,
        },
    }
    settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] = [
        "markdown.extensions.fenced_code",
        "markdown.extensions.tables",
        "markdown.extensions.toc",
    ]
    settings["MARKDOWNX_MEDIA_PATH"] = "blog/markdownx/"
    if not bool(resolved["enabled"]):
        # Rule 1 (D3): off keeps the module installed — app, migrations,
        # admin, and settings — and mounts none of its public URLs.  The
        # retained admin editor (`MarkdownxModelAdmin`) keeps its staff-guarded
        # endpoint mount; the manifest already points that mount at the
        # module's guarded URLconf, never at the shared ``markdownx.urls``.
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
            managed_files=spec.managed_files,
        )
    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _blog_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for blog via its manifest."""
    return build_generic_manifest_spec(
        "blog",
        options,
        post_hook=_blog_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the blog module's manifest adapter callable."""
    return _blog_manifest_adapter
