"""Module-owned notifications manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    NOTIFICATIONS_LIVE_EMAIL_BACKEND,
    ModuleWiringSpec,
    build_generic_manifest_spec,
    notifications_runtime_email_backend,
    resolve_notifications_module_options,
)


def _notifications_derived_settings(resolved: dict[str, Any]) -> dict[str, Any]:
    """Project notifications settings with required reads and legacy coercions."""
    settings: dict[str, Any] = {
        "QUICKSCALE_NOTIFICATIONS_ENABLED": bool(resolved["enabled"]),
        "QUICKSCALE_NOTIFICATIONS_SENDER_NAME": str(resolved["sender_name"]).strip(),
        "QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL": str(resolved["sender_email"]).strip(),
        "QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL": str(
            resolved["reply_to_email"]
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN": str(
            resolved["resend_domain"]
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR": str(
            resolved["resend_api_key_env_var"]
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR": str(
            resolved["webhook_secret_env_var"]
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS": list(resolved["default_tags"]),
        "QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS": list(resolved["allowed_tags"]),
        "QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS": int(
            resolved["webhook_ttl_seconds"]
        ),
        "QUICKSCALE_NOTIFICATIONS_PROVIDER": "resend",
    }
    return settings


def _notifications_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for notifications from its manifest contract."""
    del project_package

    resolved = resolve_notifications_module_options(options)
    runtime_email_backend = notifications_runtime_email_backend(resolved)
    manifest_spec = build_generic_manifest_spec("notifications", options)
    settings = dict(manifest_spec.settings)
    settings.update(_notifications_derived_settings(resolved))
    spec = ModuleWiringSpec(
        apps=manifest_spec.apps,
        middleware=manifest_spec.middleware,
        settings=settings,
        pre_home_url_includes=manifest_spec.pre_home_url_includes,
        url_includes=(
            *manifest_spec.url_includes,
            ("", "quickscale_modules_notifications.urls"),
        ),
        managed_files=manifest_spec.managed_files,
    )

    apps = list(spec.apps)
    if runtime_email_backend == NOTIFICATIONS_LIVE_EMAIL_BACKEND:
        if "anymail" not in apps:
            apps.insert(0, "anymail")

    settings = dict(spec.settings)
    if runtime_email_backend is not None:
        settings["EMAIL_BACKEND"] = runtime_email_backend
        sender_email = settings.get("QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL", "")
        settings["DEFAULT_FROM_EMAIL"] = sender_email
        settings["SERVER_EMAIL"] = sender_email

    return ModuleWiringSpec(
        apps=tuple(apps),
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def get_manifest_adapter() -> Any:
    """Return the notifications module's manifest adapter callable."""
    return _notifications_manifest_adapter
