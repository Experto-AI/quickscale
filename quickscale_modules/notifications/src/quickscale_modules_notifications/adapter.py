"""Module-owned notifications manifest adapter."""

from __future__ import annotations

import re
from typing import Any

from quickscale_core.runtime.manifest import (
    ModuleWiringSpec,
    build_generic_manifest_spec,
    resolve_manifest_module_options,
)

#: Django email backend the module selects when live Resend delivery is ready.
NOTIFICATIONS_LIVE_EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
#: Django email backend the module selects while live delivery is not configured.
NOTIFICATIONS_CONSOLE_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

_PLACEHOLDER_SENDER_EMAIL = "noreply@example.com"
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DOMAIN_PATTERN = re.compile(r"^[A-Za-z0-9.-]+$")
_ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


# ---------------------------------------------------------------------------
# Runtime backend predicates (adapter code, not option validation)
# ---------------------------------------------------------------------------


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_PATTERN.fullmatch(value))


def _uses_placeholder_sender_email(value: Any) -> bool:
    return str(value).strip().casefold() == _PLACEHOLDER_SENDER_EMAIL.casefold()


def _is_valid_domain(value: str) -> bool:
    candidate = value.strip()
    if not candidate or "://" in candidate or "/" in candidate:
        return False
    if candidate.startswith(".") or candidate.endswith("."):
        return False
    return bool(_DOMAIN_PATTERN.fullmatch(candidate) and "." in candidate)


def _is_valid_env_var_reference(value: str) -> bool:
    candidate = value.strip()
    return not candidate or bool(_ENV_VAR_NAME_PATTERN.fullmatch(candidate))


def _production_targeted(resolved: dict[str, Any]) -> bool:
    return bool(resolved.get("enabled", True)) and bool(
        str(resolved.get("resend_domain", "")).strip()
    )


def _live_delivery_configured(resolved: dict[str, Any]) -> bool:
    if not _production_targeted(resolved):
        return False
    sender_name = str(resolved.get("sender_name", "")).strip()
    sender_email = str(resolved.get("sender_email", "")).strip()
    resend_domain = str(resolved.get("resend_domain", "")).strip()
    resend_api_key_env_var = str(resolved.get("resend_api_key_env_var", "")).strip()
    return (
        bool(sender_name)
        and _is_valid_email(sender_email)
        and not _uses_placeholder_sender_email(sender_email)
        and _is_valid_domain(resend_domain)
        and _is_valid_env_var_reference(resend_api_key_env_var)
    )


def _runtime_email_backend(resolved: dict[str, Any]) -> str | None:
    if not bool(resolved.get("enabled", True)):
        return None
    if _live_delivery_configured(resolved):
        return NOTIFICATIONS_LIVE_EMAIL_BACKEND
    return NOTIFICATIONS_CONSOLE_EMAIL_BACKEND


def notifications_production_targeted(options: dict[str, Any] | None) -> bool:
    """Return whether *options* target live Resend delivery."""
    return _production_targeted(
        resolve_manifest_module_options("notifications", options)
    )


def notifications_live_delivery_configured(options: dict[str, Any] | None) -> bool:
    """Return whether live Resend delivery is fully configured."""
    return _live_delivery_configured(
        resolve_manifest_module_options("notifications", options)
    )


def notifications_runtime_email_backend(options: dict[str, Any] | None) -> str | None:
    """Return the resolved Django email backend, or ``None`` when disabled."""
    return _runtime_email_backend(
        resolve_manifest_module_options("notifications", options)
    )


# ---------------------------------------------------------------------------
# Wiring spec
# ---------------------------------------------------------------------------


def _notifications_derived_settings(resolved: dict[str, Any]) -> dict[str, Any]:
    """Project notifications settings with required reads and coercions.

    A null string option reads as blank rather than the literal ``"None"``, so
    a state entry written as ``reply_to_email: null`` still wires an empty
    value.

    Rule 35: each secret is projected as a setting that renders the environment
    variable its ``_ENV_VAR`` option names (core's ``__QS_ENV__`` mechanism),
    so module code reads the setting instead of calling ``os.getenv``.
    """
    enabled = bool(resolved["enabled"])
    resend_api_key_env_var = str(resolved["resend_api_key_env_var"] or "").strip()
    webhook_secret_env_var = str(resolved["webhook_secret_env_var"] or "").strip()
    settings: dict[str, Any] = {
        "QUICKSCALE_NOTIFICATIONS_ENABLED": enabled,
        "QUICKSCALE_NOTIFICATIONS_SENDER_NAME": str(
            resolved["sender_name"] or ""
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL": str(
            resolved["sender_email"] or ""
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL": str(
            resolved["reply_to_email"] or ""
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN": str(
            resolved["resend_domain"] or ""
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR": resend_api_key_env_var,
        "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR": webhook_secret_env_var,
        "QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY": (
            f"__QS_ENV__:{resend_api_key_env_var}" if resend_api_key_env_var else ""
        ),
        "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET": (
            f"__QS_ENV__:{webhook_secret_env_var}" if webhook_secret_env_var else ""
        ),
        "QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS": list(resolved["default_tags"]),
        "QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS": list(resolved["allowed_tags"]),
        "QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS": int(
            resolved["webhook_ttl_seconds"]
        ),
        "QUICKSCALE_NOTIFICATIONS_PROVIDER": str(resolved["provider"]).strip(),
    }
    return settings


def _notifications_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for notifications from its manifest contract."""
    del project_package

    resolved = resolve_manifest_module_options("notifications", options)
    runtime_email_backend = _runtime_email_backend(resolved)
    manifest_spec = build_generic_manifest_spec("notifications", options)
    settings = dict(manifest_spec.settings)
    settings.update(_notifications_derived_settings(resolved))
    spec = ModuleWiringSpec(
        apps=manifest_spec.apps,
        middleware=manifest_spec.middleware,
        settings=settings,
        pre_home_url_includes=manifest_spec.pre_home_url_includes,
        url_includes=manifest_spec.url_includes,
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
