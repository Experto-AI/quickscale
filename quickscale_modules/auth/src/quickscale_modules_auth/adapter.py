"""Module-owned auth manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import ModuleWiringSpec, build_generic_manifest_spec


def _auth_post_hook(
    spec: ModuleWiringSpec, resolved: dict[str, Any]
) -> ModuleWiringSpec:
    """Project auth's login/signup composites and off-switch transformation.

    The manifest owns every option default, normalization rule, and check,
    and declares the module's static settings (AUTHENTICATION_BACKENDS,
    AUTH_USER_MODEL, SITE_ID, ACCOUNT_ADAPTER, ACCOUNT_SIGNUP_FORM_CLASS, and
    the redirects) through the derived-setting vocabulary.  The login-method
    and signup-field projections are computed from ``authentication_method``
    here because the declarative resolver cannot branch a set and an ordered
    list from one option.  Rule 1 (D3): off keeps the module installed — apps,
    middleware, settings, and the retained admin — and mounts none of its
    public account URLs.
    """
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
    settings["ACCOUNT_LOGIN_METHODS"] = login_methods
    settings["ACCOUNT_SIGNUP_FIELDS"] = signup_fields

    if resolved["enabled"]:
        url_includes = spec.url_includes
    else:
        url_includes = ()

    return ModuleWiringSpec(
        apps=spec.apps,
        middleware=spec.middleware,
        settings=settings,
        pre_home_url_includes=spec.pre_home_url_includes,
        url_includes=url_includes,
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
