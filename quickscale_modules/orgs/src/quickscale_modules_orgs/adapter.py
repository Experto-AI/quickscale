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
    """Contribute orgs' throttle scopes and apply its off-switch transformation.

    The manifest declares the ``orgs/`` mount and its mode-dependent placement
    (solo mounts before the project's home route, saas after it) as
    conditional wiring projections, and owns the ``mode`` option's
    normalization and checks, so the canonical mode and URL placement already
    arrive with the spec (Module Conventions rule 7).  It also contributes the
    ``quickscale_orgs_invite`` and ``quickscale_orgs_invite_organization`` DRF
    throttle scopes from the ``invite_rate_limit`` option (rule 32), for rule
    30's merge into the generated ``REST_FRAMEWORK`` block.  Rule 1 (D3): off
    keeps the module installed — apps, middleware, settings, admin, and data —
    and mounts none of its organization URLs in either mode.
    """
    settings = dict(spec.settings)
    invite_rate_limit = settings["QUICKSCALE_ORGS_INVITE_RATE_LIMIT"]
    settings["REST_FRAMEWORK"] = {
        "DEFAULT_THROTTLE_RATES": {
            "quickscale_orgs_invite": invite_rate_limit,
            "quickscale_orgs_invite_organization": invite_rate_limit,
        },
    }

    if resolved.enabled:
        pre_home_url_includes = spec.pre_home_url_includes
        url_includes = spec.url_includes
    else:
        pre_home_url_includes = ()
        url_includes = ()

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=pre_home_url_includes,
        url_includes=url_includes,
        managed_files=spec.managed_files,
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
