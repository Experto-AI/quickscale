"""Module-owned forms manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import ModuleWiringSpec, build_generic_manifest_spec


def _forms_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply forms-specific int/bool/str coercions."""
    settings = dict(spec.settings)
    settings["FORMS_PER_PAGE"] = int(settings["FORMS_PER_PAGE"])
    settings["FORMS_SPAM_PROTECTION"] = bool(settings["FORMS_SPAM_PROTECTION"])
    settings["FORMS_RATE_LIMIT"] = str(settings["FORMS_RATE_LIMIT"])
    settings["FORMS_DATA_RETENTION_DAYS"] = int(settings["FORMS_DATA_RETENTION_DAYS"])
    settings["FORMS_SUBMISSIONS_API"] = bool(settings["FORMS_SUBMISSIONS_API"])
    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _forms_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for forms via its manifest."""
    return build_generic_manifest_spec(
        "forms",
        options,
        post_hook=_forms_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the forms module's manifest adapter callable."""
    return _forms_manifest_adapter
