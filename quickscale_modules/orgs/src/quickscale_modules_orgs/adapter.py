"""Module-owned orgs manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    ModuleWiringSpec,
    ResolverResult,
    assemble_wiring_spec,
    build_generic_manifest_spec,
    resolve_orgs_module_options,
    validate_orgs_module_options,
)


def _orgs_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build the orgs module's manifest-driven wiring specification."""
    del project_package

    resolved = resolve_orgs_module_options(options)
    validation_issues = validate_orgs_module_options(options)
    manifest_spec = build_generic_manifest_spec("orgs", options)
    mode = str(resolved["mode"]).strip().lower()

    settings = dict(manifest_spec.settings)
    settings.update(
        {
            "ACCOUNT_ADAPTER": "quickscale_modules_orgs.adapters.OrgsAccountAdapter",
            "QUICKSCALE_MODE": mode,
        }
    )

    root_include = ("", "quickscale_modules_orgs.urls")
    if mode == "solo":
        pre_home_url_includes = (root_include,)
        url_includes: tuple[tuple[str, str], ...] = ()
    else:
        pre_home_url_includes = ()
        url_includes = (root_include,)

    result = ResolverResult(
        module_name="orgs",
        defaults={},
        resolved=resolved,
        validation_issues=validation_issues,
        derived_settings=settings,
        apps=manifest_spec.apps,
        middleware=("quickscale_modules_orgs.middleware.TenantMiddleware",),
        url_includes=url_includes,
        pre_home_url_includes=pre_home_url_includes,
    )
    return assemble_wiring_spec(result)


def get_manifest_adapter() -> Any:
    """Return the orgs module's manifest adapter callable."""
    return _orgs_manifest_adapter
