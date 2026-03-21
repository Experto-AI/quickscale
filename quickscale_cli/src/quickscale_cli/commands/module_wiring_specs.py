"""Structured module wiring specs for managed settings/URL generation."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlparse

from quickscale_core.module_wiring import ModuleWiringSpec


def _normalize_media_url(media_url: str) -> str:
    normalized = (media_url or "/media/").strip()
    if not normalized.startswith("/") and not normalized.startswith("http"):
        normalized = "/" + normalized
    if not normalized.endswith("/"):
        normalized += "/"
    return normalized


def _normalize_custom_domain(value: str) -> str:
    normalized = (value or "").strip().rstrip("/")
    if not normalized:
        return ""
    if normalized.startswith(("http://", "https://")):
        parsed = urlparse(normalized)
        return parsed.netloc.strip()
    return normalized.split("/", 1)[0].strip()


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
        # Include allauth globally so reverse("account_login") /
        # reverse("account_signup") resolve outside auth namespace.
        url_includes=(
            ("accounts/", "allauth.urls"),
            ("accounts/", "quickscale_modules_auth.urls"),
        ),
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
        apps=("django_filters", "markdownx", "quickscale_modules_listings"),
        settings={
            "LISTINGS_PER_PAGE": listings_per_page,
            "MARKDOWNX_MARKDOWN_EXTENSIONS": [
                "markdown.extensions.fenced_code",
                "markdown.extensions.tables",
                "markdown.extensions.toc",
            ],
        },
        url_includes=(
            ("listings/", "quickscale_modules_listings.urls"),
            ("markdownx/", "markdownx.urls"),
        ),
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


def _forms_wiring(options: Mapping[str, Any]) -> ModuleWiringSpec:
    submissions_api_enabled = bool(options.get("submissions_api_enabled", True))
    forms_per_page = int(options.get("forms_per_page", 25))
    spam_protection_enabled = bool(options.get("spam_protection_enabled", True))
    rate_limit = str(options.get("rate_limit", "5/hour"))
    data_retention_days = int(options.get("data_retention_days", 365))

    settings: dict[str, Any] = {
        "FORMS_PER_PAGE": forms_per_page,
        "FORMS_SPAM_PROTECTION": spam_protection_enabled,
        "FORMS_RATE_LIMIT": rate_limit,
        "FORMS_DATA_RETENTION_DAYS": data_retention_days,
        "FORMS_SUBMISSIONS_API": submissions_api_enabled,
    }

    if submissions_api_enabled:
        # NOTE: REST_FRAMEWORK uses last-writer-wins keyed by setting name (not merged).
        # This dict is intentionally identical to _crm_wiring's REST_FRAMEWORK dict.
        # Any divergence will silently drop the other module's settings.
        settings["REST_FRAMEWORK"] = {
            "DEFAULT_AUTHENTICATION_CLASSES": [
                "rest_framework.authentication.SessionAuthentication"
            ],
            "DEFAULT_PERMISSION_CLASSES": [
                "rest_framework.permissions.IsAuthenticated"
            ],
            "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
            "PAGE_SIZE": forms_per_page,
            "DEFAULT_FILTER_BACKENDS": [
                "django_filters.rest_framework.DjangoFilterBackend",
                "rest_framework.filters.SearchFilter",
                "rest_framework.filters.OrderingFilter",
            ],
        }

    return ModuleWiringSpec(
        apps=("rest_framework", "django_filters", "quickscale_modules_forms"),
        settings=settings,
        url_includes=(("", "quickscale_modules_forms.urls"),),
    )


def _storage_wiring(options: Mapping[str, Any]) -> ModuleWiringSpec:
    backend = str(options.get("backend", "local")).lower()
    if backend not in {"local", "s3", "r2"}:
        backend = "local"

    media_url = _normalize_media_url(str(options.get("media_url", "/media/")))
    public_base_url = str(options.get("public_base_url", "")).strip()
    custom_domain = _normalize_custom_domain(str(options.get("custom_domain", "")))
    if not public_base_url and backend in {"s3", "r2"} and custom_domain:
        public_base_url = f"https://{custom_domain}"

    settings: dict[str, Any] = {
        "QUICKSCALE_STORAGE_BACKEND": backend,
        "QUICKSCALE_STORAGE_PUBLIC_BASE_URL": public_base_url,
        "MEDIA_URL": media_url,
        "QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED": bool(
            options.get("private_media_enabled", False)
        ),
    }

    if backend in {"s3", "r2"}:
        bucket_name = str(options.get("bucket_name", "")).strip()
        endpoint_url = str(options.get("endpoint_url", "")).strip()
        region_name = str(options.get("region_name", "")).strip()
        access_key_id = str(options.get("access_key_id", "")).strip()
        secret_access_key = str(options.get("secret_access_key", "")).strip()
        default_acl = str(options.get("default_acl", "")).strip()
        querystring_auth = bool(options.get("querystring_auth", False))

        storage_options: dict[str, Any] = {
            "querystring_auth": querystring_auth,
        }
        if access_key_id:
            storage_options["access_key"] = access_key_id
        if secret_access_key:
            storage_options["secret_key"] = secret_access_key
        if bucket_name:
            storage_options["bucket_name"] = bucket_name
        if endpoint_url:
            storage_options["endpoint_url"] = endpoint_url
        if region_name:
            storage_options["region_name"] = region_name
        if default_acl:
            storage_options["default_acl"] = default_acl
        if custom_domain:
            storage_options["custom_domain"] = custom_domain

        settings["STORAGES"] = {
            "default": {
                "BACKEND": "storages.backends.s3.S3Storage",
                "OPTIONS": storage_options,
            },
            "staticfiles": {
                "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
            },
        }

        settings["AWS_QUERYSTRING_AUTH"] = querystring_auth
        if bucket_name:
            settings["AWS_STORAGE_BUCKET_NAME"] = bucket_name
        if endpoint_url:
            settings["AWS_S3_ENDPOINT_URL"] = endpoint_url
        if region_name:
            settings["AWS_S3_REGION_NAME"] = region_name
        if access_key_id:
            settings["AWS_ACCESS_KEY_ID"] = access_key_id
        if secret_access_key:
            settings["AWS_SECRET_ACCESS_KEY"] = secret_access_key
        if default_acl:
            settings["AWS_DEFAULT_ACL"] = default_acl
        if custom_domain:
            settings["AWS_S3_CUSTOM_DOMAIN"] = custom_domain

    return ModuleWiringSpec(
        apps=("quickscale_modules_storage",),
        settings=settings,
    )


MODULE_WIRING_BUILDERS = {
    "auth": _auth_wiring,
    "blog": _blog_wiring,
    "listings": _listings_wiring,
    "crm": _crm_wiring,
    "forms": _forms_wiring,
    "storage": _storage_wiring,
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
