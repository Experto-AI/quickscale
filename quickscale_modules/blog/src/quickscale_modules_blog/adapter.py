"""Module-owned blog manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import (
    ModuleWiringSpec,
    ResolvedOptions,
    build_generic_manifest_spec,
)


def _blog_post_hook(
    spec: ModuleWiringSpec, resolved: ResolvedOptions
) -> ModuleWiringSpec:
    """Apply blog's off-switch transformation.

    Rule 32 — the blog automation API's scope carries the module stem and its
    rate is the module's ``api_rate_limit`` option, declared in the manifest's
    ``throttle_scopes`` projection.  The option's canonical value reaches the
    projected ``spec.throttle_scopes`` before this hook runs; the hook never
    re-coerces or re-reads a raw option and contributes no rate map.  The one
    shared staff-guarded Markdownx editor mount, and its global settings,
    belong to storage (rule 41), so blog contributes neither for it.
    """
    if resolved.enabled:
        return spec
    # Rule 1 (D3): off keeps the module installed — app, migrations,
    # admin, and settings — and mounts none of its public URLs; the one
    # shared staff-guarded Markdownx editor mount is storage's (rule 41).
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
