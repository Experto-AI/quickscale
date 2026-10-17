"""Module-owned orgs manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import (
    ModuleWiringSpec,
    ResolvedOptions,
    build_generic_manifest_spec,
)


def _orgs_post_hook(
    spec: ModuleWiringSpec, resolved: ResolvedOptions
) -> ModuleWiringSpec:
    """Apply orgs' off-switch transformation.

    The manifest declares the ``orgs/`` mount and its mode-dependent placement
    (solo mounts before the project's home route, saas after it) as
    conditional wiring projections, and owns the ``mode`` option's
    normalization and checks, so the canonical mode and URL placement already
    arrive with the spec (Module Conventions rule 7).  Its
    ``quickscale_orgs_invite`` and ``quickscale_orgs_invite_organization`` DRF
    throttle scopes are declared in the manifest's ``throttle_scopes``
    projection from the ``invite_rate_limit`` option (rule 32), so the
    projected ``spec.throttle_scopes`` already carries their resolved rates
    and the hook contributes no rate map.  Rule 1 (D3): off keeps the module
    installed — apps, middleware, settings, admin, and data — and mounts none
    of its organization URLs in either mode.
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


def _orgs_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build the orgs module's manifest-driven wiring specification."""
    del project_package
    return build_generic_manifest_spec("orgs", options, post_hook=_orgs_post_hook)


def get_manifest_adapter() -> Any:
    """Return the orgs module's manifest adapter callable."""
    return _orgs_manifest_adapter
