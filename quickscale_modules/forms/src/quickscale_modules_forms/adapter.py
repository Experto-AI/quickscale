"""Module-owned forms manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import (
    ModuleWiringSpec,
    ResolvedOptions,
    build_generic_manifest_spec,
)


def _forms_post_hook(
    spec: ModuleWiringSpec, resolved: ResolvedOptions
) -> ModuleWiringSpec:
    """Apply forms' off-switch transformation.

    Rule 32 — the form submission scope carries the module stem and its rate
    is the ``rate_limit`` option, declared in the manifest's
    ``throttle_scopes`` projection; the option's canonical value reaches the
    projected ``spec.throttle_scopes`` before this hook runs, so the hook
    contributes no rate map.  Rule 1 (D3): off keeps the module installed —
    app, migrations, admin, and settings — and mounts none of its public URLs.
    """
    if resolved.enabled:
        return spec
    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=spec.settings,
        pre_home_url_includes=(),
        url_includes=(),
        managed_files=spec.managed_files,
        throttle_scopes=spec.throttle_scopes,
    )


def _forms_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for forms via its manifest."""
    del project_package
    return build_generic_manifest_spec(
        "forms",
        options,
        post_hook=_forms_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the forms module's manifest adapter callable."""
    return _forms_manifest_adapter
