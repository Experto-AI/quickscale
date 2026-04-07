"""Structured module wiring specs for managed settings/URL generation."""

from __future__ import annotations

from pprint import pformat
from textwrap import dedent
from typing import Any, Mapping

from quickscale_cli.analytics_contract import (
    resolve_analytics_module_options,
)
from quickscale_cli.backups_contract import (
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    normalize_backups_module_options,
)
from quickscale_cli.notifications_contract import (
    NOTIFICATIONS_LIVE_EMAIL_BACKEND,
    notifications_runtime_email_backend,
    resolve_notifications_module_options,
)
from quickscale_cli.social_contract import (
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH,
    SOCIAL_STATUS_DISABLED,
    SOCIAL_STATUS_EMPTY,
    SOCIAL_STATUS_ENABLED,
    SOCIAL_STATUS_ERROR,
    resolve_social_module_options,
    social_provider_supports_embeds,
)
from quickscale_core.module_wiring import ModuleWiringSpec


def _normalize_media_url(media_url: str) -> str:
    normalized = (media_url or "/media/").strip()
    if not normalized.startswith("/") and not normalized.startswith("http"):
        normalized = "/" + normalized
    if not normalized.endswith("/"):
        normalized += "/"
    return normalized


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
        ("markdownx/", "markdownx.urls"),
    ]

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

    return ModuleWiringSpec(
        apps=("quickscale_modules_storage",),
        settings=settings,
    )


def _backups_wiring(options: Mapping[str, Any]) -> ModuleWiringSpec:
    resolved = normalize_backups_module_options(options)
    retention_days = int(resolved.get("retention_days", 14))
    naming_prefix = str(resolved.get("naming_prefix", "db")).strip() or "db"
    target_mode = str(resolved.get("target_mode", "local")).strip().lower()
    if target_mode not in {"local", "private_remote"}:
        target_mode = "local"

    access_key_id_env_var = str(
        resolved.get(BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION, "")
    ).strip()
    secret_access_key_env_var = str(
        resolved.get(BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION, "")
    ).strip()
    if target_mode == "private_remote" and not access_key_id_env_var:
        access_key_id_env_var = DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
    if target_mode == "private_remote" and not secret_access_key_env_var:
        secret_access_key_env_var = DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR

    settings: dict[str, Any] = {
        "QUICKSCALE_BACKUPS_RETENTION_DAYS": retention_days,
        "QUICKSCALE_BACKUPS_NAMING_PREFIX": naming_prefix,
        "QUICKSCALE_BACKUPS_TARGET_MODE": target_mode,
        "QUICKSCALE_BACKUPS_LOCAL_DIRECTORY": str(
            resolved.get("local_directory", ".quickscale/backups")
        ).strip()
        or ".quickscale/backups",
        "QUICKSCALE_BACKUPS_AUTOMATION_ENABLED": bool(
            resolved.get("automation_enabled", False)
        ),
        "QUICKSCALE_BACKUPS_SCHEDULE": str(resolved.get("schedule", "0 2 * * *")),
        "QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME": str(
            resolved.get("remote_bucket_name", "")
        ).strip(),
        "QUICKSCALE_BACKUPS_REMOTE_PREFIX": str(
            resolved.get("remote_prefix", "backups/private")
        ).strip()
        or "backups/private",
        "QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL": str(
            resolved.get("remote_endpoint_url", "")
        ).strip(),
        "QUICKSCALE_BACKUPS_REMOTE_REGION_NAME": str(
            resolved.get("remote_region_name", "")
        ).strip(),
        "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR": access_key_id_env_var,
        "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR": (
            secret_access_key_env_var
        ),
    }

    return ModuleWiringSpec(
        apps=("quickscale_modules_backups",),
        settings=settings,
    )


def _analytics_wiring(options: Mapping[str, Any]) -> ModuleWiringSpec:
    resolved = resolve_analytics_module_options(options)
    if not bool(resolved.get("enabled", True)):
        return ModuleWiringSpec()

    settings = {
        "QUICKSCALE_ANALYTICS_ENABLED": True,
        "QUICKSCALE_ANALYTICS_PROVIDER": str(
            resolved.get("provider", "posthog")
        ).strip()
        or "posthog",
        "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR": str(
            resolved.get("posthog_api_key_env_var", "POSTHOG_API_KEY")
        ).strip()
        or "POSTHOG_API_KEY",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR": str(
            resolved.get("posthog_host_env_var", "POSTHOG_HOST")
        ).strip()
        or "POSTHOG_HOST",
        "QUICKSCALE_ANALYTICS_POSTHOG_HOST": str(
            resolved.get("posthog_host", "https://us.i.posthog.com")
        ).strip()
        or "https://us.i.posthog.com",
        "QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG": bool(resolved.get("exclude_debug", True)),
        "QUICKSCALE_ANALYTICS_EXCLUDE_STAFF": bool(
            resolved.get("exclude_staff", False)
        ),
        "QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT": bool(
            resolved.get("anonymous_by_default", True)
        ),
    }

    return ModuleWiringSpec(
        apps=("quickscale_modules_analytics",),
        settings=settings,
    )


def _notifications_wiring(options: Mapping[str, Any]) -> ModuleWiringSpec:
    resolved = resolve_notifications_module_options(options)
    runtime_email_backend = notifications_runtime_email_backend(resolved)

    settings: dict[str, Any] = {
        "QUICKSCALE_NOTIFICATIONS_ENABLED": bool(resolved.get("enabled", True)),
        "QUICKSCALE_NOTIFICATIONS_PROVIDER": "resend",
        "QUICKSCALE_NOTIFICATIONS_SENDER_NAME": str(
            resolved.get("sender_name", "QuickScale")
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL": str(
            resolved.get("sender_email", "noreply@example.com")
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL": str(
            resolved.get("reply_to_email", "")
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN": str(
            resolved.get("resend_domain", "")
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR": str(
            resolved.get("resend_api_key_env_var", "")
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR": str(
            resolved.get("webhook_secret_env_var", "")
        ).strip(),
        "QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS": list(resolved.get("default_tags", [])),
        "QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS": list(resolved.get("allowed_tags", [])),
        "QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS": int(
            resolved.get("webhook_ttl_seconds", 300)
        ),
    }

    apps = ["quickscale_modules_notifications"]
    if runtime_email_backend == NOTIFICATIONS_LIVE_EMAIL_BACKEND:
        apps.insert(0, "anymail")

    if runtime_email_backend is not None:
        settings["EMAIL_BACKEND"] = runtime_email_backend
        settings["DEFAULT_FROM_EMAIL"] = settings[
            "QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL"
        ]
        settings["SERVER_EMAIL"] = settings["QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL"]

    return ModuleWiringSpec(
        apps=tuple(apps),
        settings=settings,
        url_includes=(("", "quickscale_modules_notifications.urls"),),
    )


def _render_social_managed_init_module() -> str:
    return (
        '"""QuickScale managed integration package.\n\n'
        "DO NOT EDIT MANUALLY. This package is regenerated by QuickScale.\n"
        '"""\n'
    )


def _render_social_managed_urls_module() -> str:
    return dedent(
        '''
        """QuickScale managed social integration URLs.

        DO NOT EDIT MANUALLY. This file is regenerated by QuickScale.
        """

        from django.urls import path

        from .social_views import social_embeds_payload, social_link_tree_payload

        app_name = "quickscale_managed_social"

        urlpatterns = [
            path("", social_link_tree_payload, name="quickscale-social-link-tree"),
            path("embeds/", social_embeds_payload, name="quickscale-social-embeds"),
        ]
        '''
    ).lstrip()


def _render_social_managed_views_module(
    provider_allowlist: list[str],
    embed_provider_allowlist: list[str],
    *,
    layout_variant: str,
    cache_ttl_seconds: int,
    links_per_page: int,
    embeds_per_page: int,
) -> str:
    provider_allowlist_text = pformat(provider_allowlist, width=88)
    embed_provider_allowlist_text = pformat(embed_provider_allowlist, width=88)

    return (
        '"""QuickScale managed social integration views.\n\n'
        "DO NOT EDIT MANUALLY. This file is regenerated by QuickScale.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "from django.http import HttpRequest, JsonResponse\n\n"
        f"DEFAULT_PROVIDER_ALLOWLIST = {provider_allowlist_text}\n"
        f"DEFAULT_EMBED_PROVIDER_ALLOWLIST = {embed_provider_allowlist_text}\n"
        f'DEFAULT_LINK_TREE_PATH = "{SOCIAL_LINK_TREE_PATH}"\n'
        f'DEFAULT_EMBEDS_PATH = "{SOCIAL_EMBEDS_PATH}"\n'
        f'DEFAULT_INTEGRATION_BASE_PATH = "{SOCIAL_INTEGRATION_BASE_PATH}"\n'
        f'DEFAULT_INTEGRATION_EMBEDS_PATH = "{SOCIAL_INTEGRATION_EMBEDS_PATH}"\n\n'
        f'DEFAULT_LAYOUT_VARIANT = "{layout_variant}"\n'
        f"DEFAULT_CACHE_TTL_SECONDS = {cache_ttl_seconds}\n"
        f"DEFAULT_LINKS_PER_PAGE = {links_per_page}\n"
        f"DEFAULT_EMBEDS_PER_PAGE = {embeds_per_page}\n"
        "PAYLOAD_STATUS_HTTP = {\n"
        f'    "{SOCIAL_STATUS_ENABLED}": 200,\n'
        f'    "{SOCIAL_STATUS_EMPTY}": 200,\n'
        f'    "{SOCIAL_STATUS_DISABLED}": 200,\n'
        f'    "{SOCIAL_STATUS_ERROR}": 503,\n'
        "}\n\n"
        "def _error_message(exc: Exception, fallback: str) -> str:\n"
        "    message = str(exc).strip()\n"
        "    return message or fallback\n\n"
        "def _error_payload(\n"
        "    *,\n"
        "    surface: str,\n"
        "    public_path: str,\n"
        "    items_key: str,\n"
        "    total_key: str,\n"
        "    per_page_key: str,\n"
        "    per_page_value: int,\n"
        "    message: str,\n"
        "    include_layout: bool = False,\n"
        ") -> dict[str, object]:\n"
        "    payload = {\n"
        '        "module": "social",\n'
        '        "surface": surface,\n'
        f'        "status": "{SOCIAL_STATUS_ERROR}",\n'
        '        "enabled": False,\n'
        '        "public_path": public_path,\n'
        '        "integration_base_path": DEFAULT_INTEGRATION_BASE_PATH,\n'
        '        "integration_embeds_path": DEFAULT_INTEGRATION_EMBEDS_PATH,\n'
        '        "provider_allowlist": list(DEFAULT_PROVIDER_ALLOWLIST),\n'
        '        "embed_provider_allowlist": list(DEFAULT_EMBED_PROVIDER_ALLOWLIST),\n'
        "        per_page_key: per_page_value,\n"
        "        total_key: 0,\n"
        "        items_key: [],\n"
        '        "error": message,\n'
        "    }\n"
        "    if include_layout:\n"
        '        payload["layout_variant"] = DEFAULT_LAYOUT_VARIANT\n'
        "    else:\n"
        '        payload["cache_ttl_seconds"] = DEFAULT_CACHE_TTL_SECONDS\n'
        "    return payload\n\n"
        "def _payload_response(payload: dict[str, object]) -> JsonResponse:\n"
        f'    status = str(payload.get("status", "{SOCIAL_STATUS_ERROR}"))\n'
        f"    return JsonResponse(payload, status=PAYLOAD_STATUS_HTTP.get(status, 503))\n\n"
        "def social_link_tree_payload(request: HttpRequest) -> JsonResponse:\n"
        "    del request\n"
        "    try:\n"
        "        from quickscale_modules_social.services import build_social_link_tree_payload\n"
        "\n"
        "        payload = build_social_link_tree_payload()\n"
        "    except Exception as exc:\n"
        "        payload = _error_payload(\n"
        '            surface="link_tree",\n'
        "            public_path=DEFAULT_LINK_TREE_PATH,\n"
        '            items_key="links",\n'
        '            total_key="total_links",\n'
        '            per_page_key="links_per_page",\n'
        "            per_page_value=DEFAULT_LINKS_PER_PAGE,\n"
        "            include_layout=True,\n"
        '            message=_error_message(exc, "Unable to load social link tree payload."),\n'
        "        )\n"
        "    return _payload_response(payload)\n\n"
        "def social_embeds_payload(request: HttpRequest) -> JsonResponse:\n"
        "    del request\n"
        "    try:\n"
        "        from quickscale_modules_social.services import build_social_embeds_payload\n"
        "\n"
        "        payload = build_social_embeds_payload()\n"
        "    except Exception as exc:\n"
        "        payload = _error_payload(\n"
        '            surface="embeds",\n'
        "            public_path=DEFAULT_EMBEDS_PATH,\n"
        '            items_key="embeds",\n'
        '            total_key="total_embeds",\n'
        '            per_page_key="embeds_per_page",\n'
        "            per_page_value=DEFAULT_EMBEDS_PER_PAGE,\n"
        '            message=_error_message(exc, "Unable to load social embeds payload."),\n'
        "        )\n"
        "    return _payload_response(payload)\n"
    )


def _social_wiring(
    options: Mapping[str, Any],
    *,
    project_package: str,
) -> ModuleWiringSpec:
    resolved = resolve_social_module_options(dict(options))
    provider_allowlist = list(resolved["provider_allowlist"])
    embed_provider_allowlist = [
        provider
        for provider in provider_allowlist
        if social_provider_supports_embeds(provider)
    ]

    settings = {
        "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED": bool(
            resolved.get("link_tree_enabled", True)
        ),
        "QUICKSCALE_SOCIAL_LAYOUT_VARIANT": str(resolved.get("layout_variant", "list")),
        "QUICKSCALE_SOCIAL_EMBEDS_ENABLED": bool(resolved.get("embeds_enabled", True)),
        "QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST": provider_allowlist,
        "QUICKSCALE_SOCIAL_EMBED_PROVIDER_ALLOWLIST": embed_provider_allowlist,
        "QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS": int(
            resolved.get("cache_ttl_seconds", 300)
        ),
        "QUICKSCALE_SOCIAL_LINKS_PER_PAGE": int(resolved.get("links_per_page", 24)),
        "QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE": int(resolved.get("embeds_per_page", 12)),
        "QUICKSCALE_SOCIAL_LINK_TREE_PATH": SOCIAL_LINK_TREE_PATH,
        "QUICKSCALE_SOCIAL_EMBEDS_PATH": SOCIAL_EMBEDS_PATH,
        "QUICKSCALE_SOCIAL_INTEGRATION_BASE_PATH": SOCIAL_INTEGRATION_BASE_PATH,
        "QUICKSCALE_SOCIAL_INTEGRATION_EMBEDS_PATH": (SOCIAL_INTEGRATION_EMBEDS_PATH),
    }

    managed_files = {
        "quickscale_managed/__init__.py": _render_social_managed_init_module(),
        "quickscale_managed/social_urls.py": _render_social_managed_urls_module(),
        "quickscale_managed/social_views.py": _render_social_managed_views_module(
            provider_allowlist,
            embed_provider_allowlist,
            layout_variant=str(resolved.get("layout_variant", "list")),
            cache_ttl_seconds=int(resolved.get("cache_ttl_seconds", 300)),
            links_per_page=int(resolved.get("links_per_page", 24)),
            embeds_per_page=int(resolved.get("embeds_per_page", 12)),
        ),
    }

    return ModuleWiringSpec(
        settings=settings,
        url_includes=(
            (
                SOCIAL_INTEGRATION_BASE_PATH.lstrip("/"),
                f"{project_package}.quickscale_managed.social_urls",
            ),
        ),
        managed_files=managed_files,
    )


MODULE_WIRING_BUILDERS = {
    "auth": _auth_wiring,
    "blog": _blog_wiring,
    "listings": _listings_wiring,
    "crm": _crm_wiring,
    "forms": _forms_wiring,
    "storage": _storage_wiring,
    "backups": _backups_wiring,
    "analytics": _analytics_wiring,
    "notifications": _notifications_wiring,
}


def build_module_wiring_specs(
    modules_options: Mapping[str, Mapping[str, Any]],
    *,
    project_package: str | None = None,
) -> dict[str, ModuleWiringSpec]:
    """Build wiring specs for selected modules and their options."""
    specs: dict[str, ModuleWiringSpec] = {}
    for module_name, options in modules_options.items():
        if module_name == "social":
            if project_package is None:
                raise ValueError(
                    "project_package is required for managed social wiring"
                )
            specs[module_name] = _social_wiring(
                options,
                project_package=project_package,
            )
            continue

        builder = MODULE_WIRING_BUILDERS.get(module_name)
        if builder is None:
            continue
        specs[module_name] = builder(options)
    return specs
