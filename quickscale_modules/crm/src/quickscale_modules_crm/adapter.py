"""Module-owned CRM manifest adapter.

This is the **sole** CRM adapter for monorepo and embedded
``modules/`` contexts.  It is registered dynamically by
:func:`quickscale_core.manifest.entry_point.refresh_managed_adapters`
when the module package is importable.

When the module package is **not** importable,
:func:`refresh_managed_adapters` raises
:class:`~django.core.exceptions.ImproperlyConfigured` — bundled/installed
without module source is not a supported context (AF7 fail-hard decision).
"""

from __future__ import annotations

from typing import Any

from quickscale_core.manifest.entry_point import build_generic_manifest_spec
from quickscale_core.module_wiring import ModuleWiringSpec


def _crm_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply CRM-specific int/bool coercions.

    Reproduces the legacy coercion behaviour that the declarative resolver
    cannot express: per-page counts are forced to ``int`` and the API
    enabled flag is forced to ``bool``.
    """
    settings = dict(spec.settings)

    # Legacy int()/bool() coercions.
    settings["CRM_DEALS_PER_PAGE"] = int(settings.get("CRM_DEALS_PER_PAGE", 25))
    settings["CRM_CONTACTS_PER_PAGE"] = int(settings.get("CRM_CONTACTS_PER_PAGE", 50))
    settings["CRM_ENABLE_API"] = bool(settings.get("CRM_ENABLE_API", True))

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _crm_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the CRM module via the manifest path.

    Uses the generic manifest-driven path that reads derivation rules from the
    CRM ``module.yml`` manifest, then applies module-specific int/bool
    coercions via the post-resolution hook.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for CRM; present for signature parity
            with adapters that need it.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for CRM.
    """
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
