"""Django settings for QuickScale organizations module tests.

Uses PostgreSQL unconditionally.  Configure the connection via env vars:

* ``QS_ORGS_DB_NAME`` (default: ``test_quickscale_orgs``)
* ``QS_ORGS_DB_USER`` (default: ``postgres``)
* ``QS_ORGS_DB_PASSWORD`` (default: ``""``)
* ``QS_ORGS_DB_HOST`` (default: ``localhost``)
* ``QS_ORGS_DB_PORT`` (default: ``5432``)
"""

import os
from pathlib import Path

from quickscale_core.manifest.settings_schema import load_settings_schema

_MODULES_ROOT = Path(__file__).resolve().parents[3] / "quickscale_modules"

# BYPASSRLS escape hatch removed from settings.py AND conftest.py.
# No module test code automatically primes QUICKSCALE_ALLOW_BYPASSRLS.
# NOBYPASSRLS is the default for module test suites. Mark individual
# tests that need BYPASSRLS with @pytest.mark.bypass_rls.
# Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include bypass_rls tests.

SECRET_KEY = "test-secret-key-for-orgs-module"
DEBUG = True
ALLOWED_HOSTS = ["*"]

# This suite installs billing and notifications enabled; their rule 35
# startup checks need the Stripe and Resend webhook secrets to resolve.
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_orgs_suite")
os.environ.setdefault("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_orgs_suite")
os.environ.setdefault(
    "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET", "whsec_notifications_orgs_suite"
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "quickscale_modules_auth",
    "quickscale_modules_orgs",
    "quickscale_modules_billing",
    "quickscale_modules_social",
    "quickscale_modules_forms",
    "quickscale_modules_listings",
    "quickscale_modules_blog",
    "quickscale_modules_crm",
    "quickscale_modules_backups",
    "quickscale_modules_notifications",
    "tests.project_tenant_app.apps.ProjectTenantAppConfig",
    "tests.provider_id_app.apps.ProviderIdAppConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "quickscale_modules_orgs.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(os.path.dirname(__file__), "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("QS_ORGS_DB_NAME", "test_quickscale_orgs"),
        "USER": os.environ.get("QS_ORGS_DB_USER", "postgres"),
        "PASSWORD": os.environ.get("QS_ORGS_DB_PASSWORD", ""),
        "HOST": os.environ.get("QS_ORGS_DB_HOST", "localhost"),
        "PORT": os.environ.get("QS_ORGS_DB_PORT", "5432"),
    }
}

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
SITE_ID = 1
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ALLOW_REGISTRATION = True
ACCOUNT_ADAPTER = "quickscale_modules_auth.allauth_adapter.QuickscaleAccountAdapter"
AUTH_USER_MODEL = "quickscale_auth.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
LOGIN_REDIRECT_URL = "/"
QUICKSCALE_MODE = "solo"
USE_X_FORWARDED_FOR = False
TRUSTED_PROXY_COUNT = 0

# DRF configuration mirroring the generated settings: session authentication
# only and the one QuickScale error shape (Module Conventions rule 9).
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "EXCEPTION_HANDLER": "quickscale_core.runtime.conventions.exception_handler",
}

# Rule 3: every declared setting of the installed modules, so each module's
# generic startup check runs against a complete stub.
# auth
SESSION_COOKIE_AGE = 1209600
# billing
QUICKSCALE_BILLING_ENABLED = True
QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR = "STRIPE_PUBLISHABLE_KEY"
QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR = "STRIPE_SECRET_KEY"
QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR = "QUICKSCALE_BILLING_WEBHOOK_SECRET"
QUICKSCALE_BILLING_CURRENCY = "usd"
QUICKSCALE_BILLING_API_RATE_LIMIT = "30/hour"
# social
QUICKSCALE_SOCIAL_LINK_TREE_ENABLED = True
QUICKSCALE_SOCIAL_LAYOUT_VARIANT = "list"
QUICKSCALE_SOCIAL_EMBEDS_ENABLED = True
QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST = [
    "facebook",
    "instagram",
    "linkedin",
    "tiktok",
    "x",
    "youtube",
]
QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS = 300
QUICKSCALE_SOCIAL_LINKS_PER_PAGE = 24
QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE = 12
# forms
FORMS_SUBMISSIONS_API = True
FORMS_RATE_LIMIT = "5/hour"
FORMS_SPAM_PROTECTION = True
FORMS_PER_PAGE = 25
FORMS_DATA_RETENTION_DAYS = 365
# listings
LISTINGS_PER_PAGE = 12
# blog
BLOG_ENABLE_RSS = True
BLOG_API_RATE_LIMIT = "5/hour"
BLOG_POSTS_PER_PAGE = 10
# crm
CRM_ENABLE_API = True
CRM_DEALS_PER_PAGE = 25
CRM_CONTACTS_PER_PAGE = 50
# backups
QUICKSCALE_BACKUPS_RETENTION_DAYS = 14
QUICKSCALE_BACKUPS_NAMING_PREFIX = "db"
QUICKSCALE_BACKUPS_TARGET_MODE = "local"
QUICKSCALE_BACKUPS_LOCAL_DIRECTORY = ".quickscale/backups"
QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME = ""
QUICKSCALE_BACKUPS_REMOTE_PREFIX = "backups/private"
QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL = ""
QUICKSCALE_BACKUPS_REMOTE_REGION_NAME = ""
QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR = (
    "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
)
QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR = (
    "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
)
QUICKSCALE_BACKUPS_AUTOMATION_ENABLED = False
QUICKSCALE_BACKUPS_SCHEDULE = "0 2 * * *"
# notifications
QUICKSCALE_NOTIFICATIONS_ENABLED = True
QUICKSCALE_NOTIFICATIONS_PROVIDER = "log"
QUICKSCALE_NOTIFICATIONS_SENDER_NAME = "QuickScale"
QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL = "noreply@quickscale.example"
QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL = "support@example.com"
QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN = "mg.example.com"
QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR = "RESEND_API_KEY"
QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR = (
    "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"
)
QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS = ["quickscale", "transactional"]
QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS = [
    "quickscale",
    "transactional",
    "notifications",
    "auth",
    "forms",
    "ops",
    "testing",
]
QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS = 300
MEDIA_URL = "/media/"

MODULE_SETTINGS_SCHEMA = {
    name: load_settings_schema(_MODULES_ROOT / name / "module.yml")
    for name in (
        "auth",
        "orgs",
        "billing",
        "social",
        "forms",
        "listings",
        "blog",
        "crm",
        "backups",
        "notifications",
    )
}
