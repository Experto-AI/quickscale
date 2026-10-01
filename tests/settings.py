"""Django settings for testing CRM module"""

import os
from pathlib import Path

from quickscale_core.manifest.settings_schema import load_settings_schema

SHARED_TEST_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "tests_shared" / "templates"
)

# BYPASSRLS escape hatch removed from settings.py AND conftest.py.
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
        "USER": os.environ.get("QS_CRM_DB_USER", "quickscale_test_role"),
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
        "DIRS": [SHARED_TEST_TEMPLATES],
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

QUICKSCALE_ORGS_ENABLED = True
QUICKSCALE_ORGS_MODE = "saas"

LOGIN_URL = "/accounts/login/"

# Required CRM settings (fail-hard: no silent defaults)
QUICKSCALE_CRM_ENABLED = True
QUICKSCALE_CRM_API_ENABLED = True
QUICKSCALE_CRM_DEALS_PER_PAGE = 25
QUICKSCALE_CRM_CONTACTS_PER_PAGE = 50

# Rule 3: the compiled option schema the generic startup check reads, derived
# from the module's own manifest so it can never drift from the declarations.
_MODULES_ROOT = Path(__file__).resolve().parents[3] / "quickscale_modules"
MODULE_SETTINGS_SCHEMA = {
    name: load_settings_schema(_MODULES_ROOT / name / "module.yml")
    for name in ("crm", "orgs")
}
