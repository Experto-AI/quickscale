"""Structured module wiring specs for managed settings/URL generation."""

from __future__ import annotations

from typing import Any, Mapping

from quickscale_core.module_wiring import ModuleWiringSpec


def _auth_wiring(options: Mapping[str, Any]) -> ModuleWiringSpec:
    registration_enabled = options.get("registration_enabled")
    if registration_enabled is None:
        # Legacy key compatibility for older config snapshots.
        registration_enabled = options.get("allow_registration", True)

    email_verification = options.get("email_verification", "none")
    authentication_method = options.get("authentication_method", "email")
    session_cookie_age = options.get("session_cookie_age", 1209600)

    signup_fields: list[str]
    login_methods: set[str]
    if authentication_method == "username":
        login_methods = {"username"}
        signup_fields = ["username*", "password1*", "password2*"]
    elif authentication_method == "both":
        login_methods = {"email", "username"}
        signup_fields = ["email*", "username*", "password1*", "password2*"]
    else:
        login_methods = {"email"}
        signup_fields = ["email*", "password1*", "password2*"]

    settings = {
        "AUTHENTICATION_BACKENDS": [
            "django.contrib.auth.backends.ModelBackend",
            "allauth.account.auth_backends.AuthenticationBackend",
        ],
        "AUTH_USER_MODEL": "quickscale_modules_auth.User",
        "SITE_ID": 1,
        "ACCOUNT_LOGIN_METHODS": login_methods,
        "ACCOUNT_SIGNUP_FIELDS": signup_fields,
        "ACCOUNT_EMAIL_VERIFICATION": email_verification,
        "ACCOUNT_ALLOW_REGISTRATION": bool(registration_enabled),
        "ACCOUNT_ADAPTER": "quickscale_modules_auth.adapters.QuickscaleAccountAdapter",
        "ACCOUNT_SIGNUP_FORM_CLASS": "quickscale_modules_auth.forms.SignupForm",
        "LOGIN_REDIRECT_URL": "/accounts/profile/",
        "LOGOUT_REDIRECT_URL": "/",
        "SESSION_COOKIE_AGE": int(session_cookie_age),
    }

    return ModuleWiringSpec(
        apps=(
            "django.contrib.sites",
            "quickscale_modules_auth",
            "allauth",
            "allauth.account",
        ),
        middleware=("allauth.account.middleware.AccountMiddleware",),
        settings=settings,
        url_includes=(("accounts/", "quickscale_modules_auth.urls"),),
    )


def _blog_wiring(options: Mapping[str, Any]) -> ModuleWiringSpec:
    posts_per_page = int(options.get("posts_per_page", 10))
    enable_rss = bool(options.get("enable_rss", True))

    url_includes: list[tuple[str, str]] = [
        ("blog/", "quickscale_modules_blog.urls"),
    ]
    if enable_rss:
        url_includes.append(("markdownx/", "markdownx.urls"))

    settings = {
        "BLOG_POSTS_PER_PAGE": posts_per_page,
        "BLOG_ENABLE_RSS": enable_rss,
        "MARKDOWNX_MARKDOWN_EXTENSIONS": [
            "markdown.extensions.fenced_code",
            "markdown.extensions.tables",
            "markdown.extensions.toc",
        ],
        "MARKDOWNX_MEDIA_PATH": "blog/markdownx/",
    }

    return ModuleWiringSpec(
        apps=("markdownx", "quickscale_modules_blog"),
        settings=settings,
        url_includes=tuple(url_includes),
    )


def _listings_wiring(options: Mapping[str, Any]) -> ModuleWiringSpec:
    listings_per_page = int(options.get("listings_per_page", 12))
    return ModuleWiringSpec(
        apps=("django_filters", "quickscale_modules_listings"),
        settings={"LISTINGS_PER_PAGE": listings_per_page},
        url_includes=(("listings/", "quickscale_modules_listings.urls"),),
    )


def _crm_wiring(options: Mapping[str, Any]) -> ModuleWiringSpec:
    enable_api = bool(options.get("enable_api", True))

    settings: dict[str, Any] = {
        "CRM_DEALS_PER_PAGE": int(options.get("deals_per_page", 25)),
        "CRM_CONTACTS_PER_PAGE": int(options.get("contacts_per_page", 50)),
        "CRM_ENABLE_API": enable_api,
    }

    if enable_api:
        settings["REST_FRAMEWORK"] = {
            "DEFAULT_AUTHENTICATION_CLASSES": [
                "rest_framework.authentication.SessionAuthentication"
            ],
            "DEFAULT_PERMISSION_CLASSES": [
                "rest_framework.permissions.IsAuthenticated"
            ],
            "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
            "PAGE_SIZE": int(options.get("deals_per_page", 25)),
            "DEFAULT_FILTER_BACKENDS": [
                "django_filters.rest_framework.DjangoFilterBackend",
                "rest_framework.filters.SearchFilter",
                "rest_framework.filters.OrderingFilter",
            ],
        }

    return ModuleWiringSpec(
        apps=("rest_framework", "django_filters", "quickscale_modules_crm"),
        settings=settings,
        url_includes=(("crm/", "quickscale_modules_crm.urls"),),
    )


MODULE_WIRING_BUILDERS = {
    "auth": _auth_wiring,
    "blog": _blog_wiring,
    "listings": _listings_wiring,
    "crm": _crm_wiring,
}


def build_module_wiring_specs(
    modules_options: Mapping[str, Mapping[str, Any]],
) -> dict[str, ModuleWiringSpec]:
    """Build wiring specs for selected modules and their options."""
    specs: dict[str, ModuleWiringSpec] = {}
    for module_name, options in modules_options.items():
        builder = MODULE_WIRING_BUILDERS.get(module_name)
        if builder is None:
            continue
        specs[module_name] = builder(options)
    return specs
