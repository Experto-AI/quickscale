"""Django settings for testing Forms module"""

import os
from pathlib import Path

from quickscale_core.manifest.settings_schema import load_settings_schema

# BYPASSRLS escape hatch removed from settings.py AND conftest.py.
# No module test code automatically primes QUICKSCALE_ALLOW_BYPASSRLS.
# NOBYPASSRLS is the default for module test suites. Mark individual
# tests that need BYPASSRLS with @pytest.mark.bypass_rls.
# Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include bypass_rls tests.

SECRET_KEY = "test-secret-key-for-forms-module"
DEBUG = True

QUICKSCALE_MODE = "saas"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "django_filters",
    "quickscale_modules_orgs",
    "quickscale_modules_forms",
]

# required settings; AppConfig.ready() will fail startup otherwise.
QUICKSCALE_FORMS_API_ENABLED = True
QUICKSCALE_FORMS_RATE_LIMIT = "5/hour"
QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED = True
QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE = 25
QUICKSCALE_FORMS_RETENTION_DAYS = 365

# Rule 3: the compiled option schema the generic startup check reads, derived
# from the module's own manifest so it can never drift from the declarations.
_MODULES_ROOT = Path(__file__).resolve().parents[3] / "quickscale_modules"
MODULE_SETTINGS_SCHEMA = {
    name: load_settings_schema(_MODULES_ROOT / name / "module.yml")
    for name in ("forms", "orgs")
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "quickscale_modules_orgs.middleware.TenantMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("QS_FORMS_DB_NAME", "test_quickscale_forms"),
        "USER": os.environ.get("QS_FORMS_DB_USER", "postgres"),
        "PASSWORD": os.environ.get("QS_FORMS_DB_PASSWORD", ""),
        "HOST": os.environ.get("QS_FORMS_DB_HOST", "localhost"),
        "PORT": os.environ.get("QS_FORMS_DB_PORT", "5432"),
    }
}

ROOT_URLCONF = "tests.urls"

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "quickscale_core.runtime.conventions.exception_handler",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "quickscale_forms_submit": "5/hour",
    },
}

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# trusted-proxy settings required by get_client_ip()
USE_X_FORWARDED_FOR = False
TRUSTED_PROXY_COUNT = 0

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

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
    },
]

DEFAULT_FROM_EMAIL = "noreply@example.com"
