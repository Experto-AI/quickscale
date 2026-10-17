"""Module-owned CRM manifest adapter.

This is the **sole** CRM adapter for monorepo and embedded
``modules/`` contexts.  It is registered dynamically by
:func:`quickscale_core.manifest.entry_point.refresh_managed_adapters`
when the module package is importable.

When the module package is **not** importable,
:func:`refresh_managed_adapters` raises
:class:`~quickscale_core.contracts.module_discovery.ImproperlyConfigured` — bundled/installed
without module source is not a supported context (fail-hard decision).
"""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import (
    ModuleWiringSpec,
    ResolvedOptions,
    build_generic_manifest_spec,
)


def _crm_post_hook(
    spec: ModuleWiringSpec, resolved: ResolvedOptions
) -> ModuleWiringSpec:
    """Apply CRM's off-switch transformation.

    Rule 1 (D3): off keeps the module installed — app, migrations, admin, and
    settings — and mounts none of its public URLs.  The manifest boundary owns
    every option default, normalization rule, check, and projection; the
    per-page counts and the API flag are canonical before this hook runs.
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


def _crm_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the CRM module via the manifest path.

    Uses the generic manifest-driven path that reads every declared default,
    normalization rule, check, and projection from the CRM ``module.yml``
    manifest, then applies the off-switch transformation via the
    post-resolution hook.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for CRM; present for signature parity
            with adapters that need it.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for CRM.
    """
    del project_package
    return build_generic_manifest_spec(
        "crm",
        options,
        post_hook=_crm_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the CRM module's manifest adapter callable.

    The returned callable has the signature::

        (options: dict[str, Any], *, project_package: str | None = None) -> ModuleWiringSpec

    This is the sentinel that
    :func:`~quickscale_core.manifest.entry_point.refresh_managed_adapters`
    uses to discover module-owned adapters.
    """
    return _crm_manifest_adapter
