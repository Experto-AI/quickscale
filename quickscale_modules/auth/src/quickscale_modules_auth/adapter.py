"""Module-owned auth manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    ModuleWiringSpec,
    ResolverResult,
    assemble_wiring_spec,
    build_generic_manifest_spec,
    resolve_auth_module_options,
)


def _auth_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build the auth module's manifest-driven wiring specification."""
    del project_package

    resolved = resolve_auth_module_options(options)
    authentication_method = resolved["authentication_method"]
    if authentication_method == "username":
        login_methods: set[str] = {"username"}
        signup_fields = ["username*", "password1*", "password2*"]
    elif authentication_method == "both":
        login_methods = {"email", "username"}
        signup_fields = ["email*", "username*", "password1*", "password2*"]
    else:
        login_methods = {"email"}
        signup_fields = ["email*", "password1*", "password2*"]

    manifest_spec = build_generic_manifest_spec("auth", options)
    settings = dict(manifest_spec.settings)
    settings.update(
        {
            "AUTHENTICATION_BACKENDS": [
                "django.contrib.auth.backends.ModelBackend",
                "allauth.account.auth_backends.AuthenticationBackend",
            ],
            "AUTH_USER_MODEL": "quickscale_modules_auth.User",
            "SITE_ID": 1,
            "ACCOUNT_LOGIN_METHODS": login_methods,
            "ACCOUNT_SIGNUP_FIELDS": signup_fields,
            "ACCOUNT_EMAIL_VERIFICATION": resolved["email_verification"],
            "ACCOUNT_ALLOW_REGISTRATION": bool(resolved["registration_enabled"]),
            "ACCOUNT_ADAPTER": "quickscale_modules_auth.adapters.QuickscaleAccountAdapter",
            "ACCOUNT_SIGNUP_FORM_CLASS": "quickscale_modules_auth.forms.SignupForm",
            "LOGIN_REDIRECT_URL": "/accounts/profile/",
            "LOGOUT_REDIRECT_URL": "/",
            "SESSION_COOKIE_AGE": int(resolved["session_cookie_age"]),
        }
    )

    result = ResolverResult(
        module_name="auth",
        defaults={},
        resolved=resolved,
        derived_settings=settings,
        apps=manifest_spec.apps,
        middleware=("allauth.account.middleware.AccountMiddleware",),
        url_includes=(
            ("accounts/", "allauth.urls"),
            ("accounts/", "quickscale_modules_auth.urls"),
        ),
    )
    return assemble_wiring_spec(result)


def get_manifest_adapter() -> Any:
    """Return the auth module's manifest adapter callable."""
    return _auth_manifest_adapter
