"""Module-owned notifications manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    ModuleWiringSpec,
    ResolvedOptions,
    build_generic_manifest_spec,
    collect_resolved_option_validation_issues,
    load_module_manifest,
    resolve_manifest_module_options,
)

#: Django email backend the module selects when live Resend delivery is ready.
NOTIFICATIONS_LIVE_EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
#: Django email backend the module selects while live delivery is not configured.
NOTIFICATIONS_CONSOLE_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

#: The delivery options whose declared validation decides whether live Resend
#: delivery is configured: the sender identity, the sending domain, and the
#: API-key environment-variable reference.  Their ``validation`` blocks are the
#: one home of the email, domain, and env-var-name patterns and of the
#: placeholder-sender exclusion, so the predicates below evaluate the
#: manifest's declared rules instead of restating them (rule 12).
_LIVE_DELIVERY_OPTIONS = frozenset(
    {"resend_api_key_env_var", "resend_domain", "sender_email", "sender_name"}
)


# ---------------------------------------------------------------------------
# Runtime backend predicates (adapter code, not option validation)
# ---------------------------------------------------------------------------


def _production_targeted(resolved: ResolvedOptions) -> bool:
    return bool(resolved.enabled) and bool(str(resolved.resend_domain).strip())


def _live_delivery_configured(resolved: ResolvedOptions) -> bool:
    """Return whether live Resend delivery is fully configured.

    The configuration must target live delivery, and the options it depends on
    must satisfy the validation the manifest declares next to them — the
    sender-email pattern and placeholder exclusion included.
    """
    if not _production_targeted(resolved):
        return False
    issues = collect_resolved_option_validation_issues(
        load_module_manifest("notifications"), resolved
    )
    return all(issue.option_name not in _LIVE_DELIVERY_OPTIONS for issue in issues)


def _runtime_email_backend(resolved: ResolvedOptions) -> str | None:
    if not bool(resolved.enabled):
        return None
    if _live_delivery_configured(resolved):
        return NOTIFICATIONS_LIVE_EMAIL_BACKEND
    return NOTIFICATIONS_CONSOLE_EMAIL_BACKEND


def notifications_production_targeted(options: dict[str, Any] | None) -> bool:
    """Return whether *options* target live Resend delivery."""
    return _production_targeted(
        ResolvedOptions(resolve_manifest_module_options("notifications", options))
    )


def notifications_live_delivery_configured(options: dict[str, Any] | None) -> bool:
    """Return whether live Resend delivery is fully configured."""
    return _live_delivery_configured(
        ResolvedOptions(resolve_manifest_module_options("notifications", options))
    )


def notifications_runtime_email_backend(options: dict[str, Any] | None) -> str | None:
    """Return the resolved Django email backend, or ``None`` when disabled."""
    return _runtime_email_backend(
        ResolvedOptions(resolve_manifest_module_options("notifications", options))
    )


# ---------------------------------------------------------------------------
# Wiring spec
# ---------------------------------------------------------------------------


def _notifications_post_hook(
    spec: ModuleWiringSpec, resolved: ResolvedOptions
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
        throttle_scopes=spec.throttle_scopes,
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
