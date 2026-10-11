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


def _notifications_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Select the runtime email backend for the resolved options.

    The manifest owns every option default, normalization rule, check, and
    projection: the ``QUICKSCALE_NOTIFICATIONS_*`` settings (each secret
    included, through the generic ``_ENV_VAR`` boundary) and the
    ``DEFAULT_FROM_EMAIL``/``SERVER_EMAIL`` aliases arrive already projected,
    so this hook only contributes the runtime-selected backend.  Rule 1 (D3):
    the email settings stay in place while the module is off, so the settings
    surface does not change with the switch; delivery is refused at the
    runtime service boundary instead.
    """
    settings = dict(spec.settings)
    settings["EMAIL_BACKEND"] = (
        _runtime_email_backend(resolved) or NOTIFICATIONS_CONSOLE_EMAIL_BACKEND
    )
    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _notifications_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for notifications from its manifest contract."""
    del project_package
    return build_generic_manifest_spec(
        "notifications",
        options,
        post_hook=_notifications_post_hook,
    )


def get_manifest_adapter() -> Any:
    """Return the notifications module's manifest adapter callable."""
    return _notifications_manifest_adapter
