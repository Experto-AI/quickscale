"""Module-owned orgs manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    ManifestError,
    ModuleWiringSpec,
    build_generic_manifest_spec,
    load_module_manifest,
    validate_module_options,
)


def _orgs_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Project orgs settings from the resolved options.

    Every option is validated against the manifest's own declared rules before
    assembly, so an invalid mode fails closed.  The manifest declares the
    ``orgs/`` mount and its mode-dependent placement (solo mounts before the
    project's home route, saas after it) as conditional wiring projections;
    this hook projects the settings the declarative resolver cannot, and
    carries the resolved URL includes through unchanged (Module Conventions
    rule 7).  It also contributes the ``quickscale_orgs_invite`` and
    ``quickscale_orgs_invite_organization`` DRF throttle scopes from the
    ``invite_rate_limit`` option (rule 32), for rule 30's merge into the
    generated ``REST_FRAMEWORK`` block.
    """
    issues = validate_module_options(load_module_manifest("orgs"), resolved)
    if issues:
        raise ManifestError(
            "Module 'orgs' has validation issues that must be resolved before "
            "assembly:\n" + "\n".join(f"  • {issue}" for issue in issues)
        )

    mode = str(resolved["mode"]).strip().lower()
    settings = dict(spec.settings)
    invite_rate_limit = str(settings["QUICKSCALE_ORGS_INVITE_RATE_LIMIT"]).strip()
    settings.update(
        {
            "QUICKSCALE_ORGS_MODE": mode,
            "QUICKSCALE_ORGS_INVITE_RATE_LIMIT": invite_rate_limit,
            "QUICKSCALE_ORGS_PENDING_INVITATION_LIMIT": int(
                settings["QUICKSCALE_ORGS_PENDING_INVITATION_LIMIT"]
            ),
        }
    )
    # Rule 32 — both invitation scopes carry the module stem and take the
    # invite_rate_limit option's rate: one bucket per sender, one per target
    # organization, contributed here for rule 30's merge.
    settings["REST_FRAMEWORK"] = {
        "DEFAULT_THROTTLE_RATES": {
            "quickscale_orgs_invite": invite_rate_limit,
            "quickscale_orgs_invite_organization": invite_rate_limit,
        },
    }

    if not bool(resolved["enabled"]):
        # Rule 1 (D3): off keeps the module installed — apps, middleware,
        # settings, admin, and data — and mounts none of its organization URLs
        # in either mode.
        pre_home_url_includes: tuple[tuple[str, str], ...] = ()
        url_includes: tuple[tuple[str, str], ...] = ()
    else:
        pre_home_url_includes = spec.pre_home_url_includes
        url_includes = spec.url_includes

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=("quickscale_modules_orgs.middleware.TenantMiddleware",),
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
