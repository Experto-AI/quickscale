"""Module-owned billing manifest adapter.

This is the **sole** billing adapter for monorepo and embedded
``modules/`` contexts.  It is registered dynamically by
:func:`quickscale_core.manifest.entry_point.refresh_managed_adapters`
when the module package is importable.

When the module package is **not** importable,
:func:`refresh_managed_adapters` raises
:class:`~quickscale_core.contracts.module_discovery.ImproperlyConfigured` — bundled/installed
without module source is not a supported context (AF7 fail-hard decision).
"""

from __future__ import annotations

from typing import Any

from quickscale_core.manifest.entry_point import build_generic_manifest_spec
from quickscale_core.module_wiring import ModuleWiringSpec


def _billing_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply billing-specific bool/string coercions.

    Reproduces the legacy coercion behaviour that the declarative resolver
    cannot express: ``QUICKSCALE_BILLING_ENABLED`` is forced to ``bool``
    and env-var name settings are forced to ``str``.
    """
    settings = dict(spec.settings)

    # SA17.2 — Legacy bool() coercion on required enabled flag.
    # The key must already be present (AppConfig.ready() enforces it).
    settings["QUICKSCALE_BILLING_ENABLED"] = bool(
        settings["QUICKSCALE_BILLING_ENABLED"]
    )

    # Legacy str() coercion on string fields.
    for str_key in (
        "QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR",
        "QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR",
        "QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR",
        "QUICKSCALE_BILLING_CURRENCY",
    ):
        if str_key in settings:
            settings[str_key] = str(settings[str_key])

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _billing_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the billing module via the manifest path.

    Uses the generic manifest-driven path that reads derivation rules from the
    billing ``module.yml`` manifest, then applies module-specific bool/string
    coercions via the post-resolution hook.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for billing; present for signature parity
            with adapters that need it.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for billing.
    """
    return build_generic_manifest_spec(
        "billing",
        options,
        post_hook=_billing_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the billing module's manifest adapter callable.

    The returned callable has the signature::

        (options: dict[str, Any], *, project_package: str | None = None) -> ModuleWiringSpec

    This is the sentinel that
    :func:`~quickscale_core.manifest.entry_point.refresh_managed_adapters`
    uses to discover module-owned adapters.
    """
    return _billing_manifest_adapter
