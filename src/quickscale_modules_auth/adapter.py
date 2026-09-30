"""Module-owned auth manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    ManifestError,
    ModuleWiringSpec,
    build_generic_manifest_spec,
    load_module_manifest,
    validate_module_options,
)


def _auth_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Project auth's login/signup settings from the resolved options.

    The manifest declares the option-to-setting mapping; the login-method and
    signup-field projections are computed from ``authentication_method`` here
    because the declarative resolver cannot branch a set and an ordered list
    from one option.  Every option is validated against the manifest's own
    declared rules, so a retired legacy key or an unknown value fails before a
    spec is assembled.
    """
    issues = validate_module_options(load_module_manifest("auth"), resolved)
    if issues:
        raise ManifestError(
            "Module 'auth' has validation issues that must be resolved before "
            "assembly:\n" + "\n".join(f"  • {issue}" for issue in issues)
        )

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

    settings = dict(spec.settings)
    settings.update(
        {
            "AUTHENTICATION_BACKENDS": [
                "django.contrib.auth.backends.ModelBackend",
                "allauth.account.auth_backends.AuthenticationBackend",
            ],
            "AUTH_USER_MODEL": "quickscale_auth.User",
            "SITE_ID": 1,
            "ACCOUNT_LOGIN_METHODS": login_methods,
            "ACCOUNT_SIGNUP_FIELDS": signup_fields,
            "ACCOUNT_EMAIL_VERIFICATION": resolved["email_verification"],
            "ACCOUNT_ALLOW_REGISTRATION": bool(resolved["registration_enabled"]),
            # ACCOUNT_ADAPTER belongs to this module: auth owns the single
            # allauth adapter, which collects installed modules' declared
            # post-auth redirect hooks as AppConfig capabilities.
            "ACCOUNT_ADAPTER": (
                "quickscale_modules_auth.allauth_adapter.QuickscaleAccountAdapter"
            ),
            "ACCOUNT_SIGNUP_FORM_CLASS": "quickscale_modules_auth.forms.SignupForm",
            "LOGIN_REDIRECT_URL": "/accounts/profile/",
            "LOGOUT_REDIRECT_URL": "/",
            "SESSION_COOKIE_AGE": int(resolved["session_cookie_age"]),
        }
    )

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=("allauth.account.middleware.AccountMiddleware",),
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=spec.url_includes,
        managed_files=spec.managed_files,
    )


def _auth_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build the auth module's manifest-driven wiring specification."""
    del project_package
    return build_generic_manifest_spec("auth", options, post_hook=_auth_post_hook)


def get_manifest_adapter() -> Any:
    """Return the auth module's manifest adapter callable."""
    return _auth_manifest_adapter
