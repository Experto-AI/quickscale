"""Module-owned backups manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    ManifestError,
    ModuleWiringSpec,
    build_generic_manifest_spec,
    load_module_manifest,
    validate_module_options,
)


def _backups_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Project backups' operational settings from the resolved options.

    The manifest declares every option's default, normalization rule, and
    validation block; this hook only applies the coercions the declarative
    resolver cannot express (integer and boolean settings), after validating
    the resolved values through the same engine ``plan`` and ``apply`` use.
    """
    issues = validate_module_options(load_module_manifest("backups"), resolved)
    if issues:
        raise ManifestError(
            "Module 'backups' has validation issues that must be resolved before "
            "assembly:\n" + "\n".join(f"  • {issue}" for issue in issues)
        )

    settings = dict(spec.settings)
    settings["QUICKSCALE_BACKUPS_RETENTION_DAYS"] = int(
        settings["QUICKSCALE_BACKUPS_RETENTION_DAYS"]
    )
    settings["QUICKSCALE_BACKUPS_AUTOMATION_ENABLED"] = bool(
        settings["QUICKSCALE_BACKUPS_AUTOMATION_ENABLED"]
    )
    settings["QUICKSCALE_BACKUPS_SCHEDULE"] = str(
        settings["QUICKSCALE_BACKUPS_SCHEDULE"]
    )

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _backups_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for backups from its manifest contract."""
    del project_package

    return build_generic_manifest_spec(
        "backups",
        options,
        post_hook=_backups_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the backups module's manifest adapter callable."""
    return _backups_manifest_adapter
