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
    settings["BLOG_POSTS_PER_PAGE"] = int(settings["BLOG_POSTS_PER_PAGE"])
    settings["BLOG_ENABLE_RSS"] = bool(settings["BLOG_ENABLE_RSS"])
    api_rate = str(settings["BLOG_API_RATE_LIMIT"]).strip()
    if not api_rate:
        raise ManifestError(
            "Blog manifest setting BLOG_API_RATE_LIMIT resolved to empty value. "
            "The manifest derivation produced an invalid result."
        )
    settings["BLOG_API_RATE_LIMIT"] = api_rate
    settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] = [
        "markdown.extensions.fenced_code",
        "markdown.extensions.tables",
        "markdown.extensions.toc",
    ]
    settings["MARKDOWNX_MEDIA_PATH"] = "blog/markdownx/"
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
