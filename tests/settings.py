"""Django settings for QuickScale notifications module tests."""

import os

# SA14.4: BYPASSRLS escape hatch removed from settings.py AND conftest.py.
# No module test code automatically primes QUICKSCALE_ALLOW_BYPASSRLS.
# NOBYPASSRLS is the default for module test suites. Mark individual
# tests that need BYPASSRLS with @pytest.mark.bypass_rls.
# Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include bypass_rls tests.

SECRET_KEY = "test-secret-key-for-notifications-module"
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Required by quickscale_modules_orgs; saas is the correct mode for
# orgs-dependent module test suites (forms, blog, listings, crm, social).
QUICKSCALE_MODE = "saas"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "quickscale_modules_orgs",
    "quickscale_modules_forms",
    "quickscale_modules_notifications",
]

# SA17.4 — required forms settings; forms AppConfig.ready() will fail
# startup otherwise.
FORMS_SUBMISSIONS_API = True
FORMS_RATE_LIMIT = "5/hour"
FORMS_SPAM_PROTECTION = True

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "tests.urls"

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "form_submit": "5/hour",
    },
}

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
        "NAME": os.environ.get(
            "QS_NOTIFICATIONS_DB_NAME", "test_quickscale_notifications"
        ),
        "USER": os.environ.get("QS_NOTIFICATIONS_DB_USER", "postgres"),
        "PASSWORD": os.environ.get("QS_NOTIFICATIONS_DB_PASSWORD", ""),
        "HOST": os.environ.get("QS_NOTIFICATIONS_DB_HOST", "localhost"),
        "PORT": os.environ.get("QS_NOTIFICATIONS_DB_PORT", "5432"),
    }
}

USE_TZ = True
TIME_ZONE = "UTC"
USE_X_FORWARDED_FOR = False
TRUSTED_PROXY_COUNT = 0
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "default@example.com"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

QUICKSCALE_NOTIFICATIONS_ENABLED = True
QUICKSCALE_NOTIFICATIONS_PROVIDER = "resend"
QUICKSCALE_NOTIFICATIONS_SENDER_NAME = "QuickScale"
QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL = "noreply@example.com"
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
