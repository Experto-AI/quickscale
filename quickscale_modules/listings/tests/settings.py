"""Django settings for listings module tests"""

from pathlib import Path

from quickscale_core.testing.settings import (
    module_settings_schema,
    suite_database,
    suite_secret_key,
)

BASE_DIR = Path(__file__).resolve().parent.parent
SHARED_TEST_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "tests_shared" / "templates"
)

# BYPASSRLS escape hatch removed from settings.py AND conftest.py.
# No module test code automatically primes QUICKSCALE_ALLOW_BYPASSRLS.
# NOBYPASSRLS is the default for module test suites. Mark individual
# tests that need BYPASSRLS with @pytest.mark.bypass_rls.
# Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include bypass_rls tests.

SECRET_KEY = suite_secret_key("listings")

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
    "tests.listing_app.apps.ListingAppConfig",  # ConcreteListing fixture app
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
QUICKSCALE_ORGS_ENABLED = True
QUICKSCALE_ORGS_INVITE_RATE_LIMIT = "20/day"
QUICKSCALE_ORGS_PENDING_INVITATION_LIMIT = 50
QUICKSCALE_ORGS_MODE = "saas"

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
    "default": suite_database("listings"),
}

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "tests" / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True

# Logging settings required when tests configure this module as default settings
LOGGING_CONFIG = None
LOGGING: dict[str, object] = {}

# Listings module settings
QUICKSCALE_LISTINGS_ENABLED = True
QUICKSCALE_LISTINGS_PER_PAGE = 12
QUICKSCALE_LISTINGS_API_RATE_LIMIT = "5/hour"

# Rule 3: the compiled option schema the generic startup check reads.  The
# test settings generate it from the module's own manifest, the form rule 3
# allows, so it can never drift from the declared options.
_MODULES_ROOT = Path(__file__).resolve().parents[3] / "quickscale_modules"
MODULE_SETTINGS_SCHEMA = module_settings_schema(_MODULES_ROOT, "listings", "orgs")

# DRF configuration mirroring the generated settings: session authentication
# only, the composed JSON renderer and parser defaults (rule 9), the one
# QuickScale error shape, core's default throttle classes (the publish view
# attaches its rate by scope alone, rule 32), and the publish scope rate the
# module wiring contributes (Module Conventions rules 9 and 32).
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "quickscale_core.runtime.drf.QuickscaleScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "1200/hour",
        "user": "3000/hour",
        "quickscale_listings_api": "5/hour",
    },
    "EXCEPTION_HANDLER": "quickscale_core.runtime.conventions.exception_handler",
}

# Markdownx settings (the shared mount and its globals belong to storage,
# rule 41; the value mirrors what storage's adapter writes)
MARKDOWNX_MARKDOWN_EXTENSIONS = [
    "markdown.extensions.fenced_code",
    "markdown.extensions.tables",
    "markdown.extensions.toc",
]
MARKDOWNX_MEDIA_PATH = "markdownx/"
