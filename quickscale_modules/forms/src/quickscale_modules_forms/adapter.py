"""Module-owned forms manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import ModuleWiringSpec, build_generic_manifest_spec


def _forms_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Apply forms-specific int/bool/str coercions and DRF throttle scope."""
    settings = dict(spec.settings)
    settings["QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE"] = int(
        settings["QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE"]
    )
    settings["QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED"] = bool(
        settings["QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED"]
    )
    settings["QUICKSCALE_FORMS_RATE_LIMIT"] = str(
        settings["QUICKSCALE_FORMS_RATE_LIMIT"]
    )
    settings["QUICKSCALE_FORMS_RETENTION_DAYS"] = int(
        settings["QUICKSCALE_FORMS_RETENTION_DAYS"]
    )
    settings["QUICKSCALE_FORMS_API_ENABLED"] = bool(
        settings["QUICKSCALE_FORMS_API_ENABLED"]
    )
    # Rule 32 — the form submission scope carries the module stem and its rate
    # is the rate_limit option, contributed here for rule 30's merge.
    settings["REST_FRAMEWORK"] = {
        "DEFAULT_THROTTLE_RATES": {
            "quickscale_forms_submit": settings["QUICKSCALE_FORMS_RATE_LIMIT"],
        },
    }
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
