"""Django settings for testing CRM module"""

import os

# SA14.4: BYPASSRLS escape hatch removed from settings.py AND conftest.py.
# No module test code automatically primes QUICKSCALE_ALLOW_BYPASSRLS.
# NOBYPASSRLS is the default for module test suites. Mark individual
# tests that need BYPASSRLS with @pytest.mark.bypass_rls.
# Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include bypass_rls tests.

SECRET_KEY = "test-secret-key-for-crm-module"
DEBUG = True

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "django_filters",
    "quickscale_modules_orgs",
    "quickscale_modules_crm",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "quickscale_modules_orgs.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("QS_CRM_DB_NAME", "test_quickscale_crm"),
        "USER": os.environ.get("QS_CRM_DB_USER", "postgres"),
        "PASSWORD": os.environ.get("QS_CRM_DB_PASSWORD", ""),
        "HOST": os.environ.get("QS_CRM_DB_HOST", "localhost"),
        "PORT": os.environ.get("QS_CRM_DB_PORT", "5432"),
    }
}

ROOT_URLCONF = "tests.urls"

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
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

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

QUICKSCALE_MODE = "saas"

LOGIN_URL = "/accounts/login/"

# SA17.3 — Required CRM settings (fail-hard: no silent defaults)
CRM_ENABLE_API = True
CRM_DEALS_PER_PAGE = 25
CRM_CONTACTS_PER_PAGE = 50
