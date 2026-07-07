"""Django settings for QuickScale organizations module tests.

Uses PostgreSQL unconditionally.  Configure the connection via env vars:

* ``QS_ORGS_DB_NAME`` (default: ``test_quickscale_orgs``)
* ``QS_ORGS_DB_USER`` (default: ``postgres``)
* ``QS_ORGS_DB_PASSWORD`` (default: ``""``)
* ``QS_ORGS_DB_HOST`` (default: ``localhost``)
* ``QS_ORGS_DB_PORT`` (default: ``5432``)
"""

import os

# SA14.4: BYPASSRLS escape hatch removed from settings.py AND conftest.py.
# No module test code automatically primes QUICKSCALE_ALLOW_BYPASSRLS.
# NOBYPASSRLS is the default for module test suites. Mark individual
# tests that need BYPASSRLS with @pytest.mark.bypass_rls.
# Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include bypass_rls tests.

SECRET_KEY = "test-secret-key-for-orgs-module"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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
        "DIRS": [],
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
ACCOUNT_ADAPTER = "quickscale_modules_orgs.adapters.OrgsAccountAdapter"
AUTH_USER_MODEL = "quickscale_modules_auth.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
LOGIN_REDIRECT_URL = "/"
QUICKSCALE_MODE = "solo"

# Required by modules in INSTALLED_APPS that have AppConfig.ready() guards:
# SA17.2 — billing enabled-flag
QUICKSCALE_BILLING_ENABLED = True
# SA17.3 — CRM API-enable flag
CRM_ENABLE_API = True
# SA17.4 — forms settings
FORMS_SUBMISSIONS_API = True
FORMS_RATE_LIMIT = "5/hour"
FORMS_SPAM_PROTECTION = True
# SA17.5 — blog settings
BLOG_ENABLE_RSS = True
MEDIA_URL = "/media/"
