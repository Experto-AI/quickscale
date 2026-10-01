"""Django settings for QuickScale analytics module tests."""

import os
from pathlib import Path

from quickscale_core.manifest.settings_schema import load_settings_schema

SHARED_TEST_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "tests_shared" / "templates"
)

SECRET_KEY = "test-secret-key-for-analytics-module"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "quickscale_modules_analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [SHARED_TEST_TEMPLATES],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("QS_ANALYTICS_DB_NAME", "test_quickscale_analytics"),
        "USER": os.environ.get("QS_ANALYTICS_DB_USER", "postgres"),
        "PASSWORD": os.environ.get("QS_ANALYTICS_DB_PASSWORD", ""),
        "HOST": os.environ.get("QS_ANALYTICS_DB_HOST", "localhost"),
        "PORT": os.environ.get("QS_ANALYTICS_DB_PORT", "5432"),
    }
}

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"

QUICKSCALE_ANALYTICS_ENABLED = True
QUICKSCALE_ANALYTICS_PROVIDER = "posthog"
QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR = "POSTHOG_API_KEY"
QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR = "POSTHOG_HOST"
QUICKSCALE_ANALYTICS_POSTHOG_HOST = "https://us.i.posthog.com"
QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG = True
QUICKSCALE_ANALYTICS_EXCLUDE_STAFF = False
QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT = True

# Rule 35: apply renders the projected secret settings from the environment
# variables the `_ENV_VAR` options name.  Tests set these settings directly,
# as storage's suite does, so resolution is exercised through the setting.
QUICKSCALE_ANALYTICS_POSTHOG_API_KEY = ""
QUICKSCALE_ANALYTICS_POSTHOG_HOST_OVERRIDE = ""

# Rule 3: the compiled option schema the generic startup check reads, derived
# from the module's own manifest so it can never drift from the declarations.
MODULE_SETTINGS_SCHEMA = {
    "analytics": load_settings_schema(
        Path(__file__).resolve().parent.parent / "module.yml"
    )
}
