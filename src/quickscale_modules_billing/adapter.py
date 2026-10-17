"""Module-owned billing manifest adapter.

This is the **sole** billing adapter for monorepo and embedded
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


def _billing_post_hook(
    spec: ModuleWiringSpec, resolved: ResolvedOptions
) -> ModuleWiringSpec:
    """Apply billing's off-switch behaviour.

    Rule 32 — every Stripe-calling billing endpoint carries an explicit scope
    stemmed as ``quickscale_billing_<purpose>``, and the rate for those scopes
    is the module's ``api_rate_limit`` option, declared in the manifest's
    ``throttle_scopes`` projection.  The option's canonical value reaches the
    projected ``spec.throttle_scopes`` before this hook runs; the hook never
    re-coerces or re-reads a raw option and contributes no rate map.

    Rule 1 (D3): off keeps the module installed — app, middleware, settings,
    and admin — and unmounts its public pages and APIs.  The Stripe webhook
    stays mounted through its own URLconf and answers the module's 404
    refusal (rule 26), so provider retries get a clean answer.
    """
    if resolved.enabled:
        return spec
    webhook_includes = tuple(
        (prefix, "quickscale_modules_billing.webhook_urls")
        for prefix, target in spec.url_includes
        if target == "quickscale_modules_billing.urls"
    )
    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=spec.settings,
        pre_home_url_includes=(),
        url_includes=webhook_includes,
        spa_routes=(),
        managed_files=spec.managed_files,
        throttle_scopes=spec.throttle_scopes,
    )


def _billing_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for the billing module via the manifest path.

    Uses the generic manifest-driven path that reads every declared default,
    normalization rule, check, projection, and secret reference from the
    billing ``module.yml`` manifest, then applies the off-switch URL
    transformation via the post-resolution hook.

    Args:
        options: Module options (e.g. from ``quickscale.yml``).
        project_package: Unused for billing; present for signature parity
            with adapters that need it.

    Returns:
        A :class:`~quickscale_core.module_wiring.ModuleWiringSpec` for billing.
    """
    del project_package
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
