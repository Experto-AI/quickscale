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
    """Project orgs settings and URL placement from the resolved options.

    Every option is validated against the manifest's own declared rules before
    the mode decides whether the module's URLs mount before the project's home
    route (``solo``) or after it (``saas``), so an invalid mode fails closed
    instead of producing contradictory URLs.
    """
    issues = validate_module_options(load_module_manifest("orgs"), resolved)
    if issues:
        raise ManifestError(
            "Module 'orgs' has validation issues that must be resolved before "
            "assembly:\n" + "\n".join(f"  • {issue}" for issue in issues)
        )

    mode = str(resolved["mode"]).strip().lower()
    settings = dict(spec.settings)
    settings.update(
        {
            "ACCOUNT_ADAPTER": "quickscale_modules_orgs.adapters.OrgsAccountAdapter",
            "QUICKSCALE_MODE": mode,
        }
    )

    root_include = ("", "quickscale_modules_orgs.urls")
    if mode == "solo":
        pre_home_url_includes: tuple[tuple[str, str], ...] = (root_include,)
        url_includes: tuple[tuple[str, str], ...] = ()
    else:
        pre_home_url_includes = ()
        url_includes = (root_include,)

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
