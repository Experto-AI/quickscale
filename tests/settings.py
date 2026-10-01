"""Django settings for listings module tests"""

import os
from pathlib import Path

from quickscale_core.manifest.settings_schema import load_settings_schema

BASE_DIR = Path(__file__).resolve().parent.parent
SHARED_TEST_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "tests_shared" / "templates"
)

# BYPASSRLS escape hatch removed from settings.py AND conftest.py.
# No module test code automatically primes QUICKSCALE_ALLOW_BYPASSRLS.
# NOBYPASSRLS is the default for module test suites. Mark individual
# tests that need BYPASSRLS with @pytest.mark.bypass_rls.
# Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include bypass_rls tests.

SECRET_KEY = "test-secret-key-for-listings-module"

DEBUG = True

ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "markdownx",
    "quickscale_modules_orgs",
    "quickscale_modules_listings",
    "tests",  # Required for ConcreteListing model
]

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

# SaaS mode for org-scoped route testing
QUICKSCALE_MODE = "saas"

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [SHARED_TEST_TEMPLATES],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("QS_LISTINGS_DB_NAME", "test_quickscale_listings"),
        "USER": os.environ.get("QS_LISTINGS_DB_USER", "postgres"),
        "PASSWORD": os.environ.get("QS_LISTINGS_DB_PASSWORD", ""),
        "HOST": os.environ.get("QS_LISTINGS_DB_HOST", "localhost"),
        "PORT": os.environ.get("QS_LISTINGS_DB_PORT", "5432"),
    }
}

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "tests" / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging settings required when tests configure this module as default settings
LOGGING_CONFIG = None
LOGGING: dict[str, object] = {}

# Listings module settings
QUICKSCALE_LISTINGS_PER_PAGE = 12

# Rule 3: the compiled option schema the generic startup check reads.  The
# test settings generate it from the module's own manifest, the form rule 3
# allows, so it can never drift from the declared options.
_MODULES_ROOT = Path(__file__).resolve().parents[3] / "quickscale_modules"
MODULE_SETTINGS_SCHEMA = {
    name: load_settings_schema(_MODULES_ROOT / name / "module.yml")
    for name in ("listings", "orgs")
}

# DRF configuration mirroring the generated settings: session authentication
# only and the one QuickScale error shape (Module Conventions rule 9).
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "EXCEPTION_HANDLER": "quickscale_core.runtime.conventions.exception_handler",
}

# Markdownx settings
MARKDOWNX_MARKDOWN_EXTENSIONS = [
    "markdown.extensions.fenced_code",
    "markdown.extensions.tables",
    "markdown.extensions.toc",
]
MARKDOWNX_MEDIA_PATH = "listings/markdownx/"
