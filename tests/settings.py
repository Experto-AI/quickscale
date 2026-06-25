"""Django settings for QuickScale social module tests.

Default database is SQLite (``:memory:``).  Set the environment variable
``QUICKSCALE_TEST_DB=postgres`` to run the full test suite against
PostgreSQL — the following env vars configure the connection:

* ``QS_SOCIAL_DB_NAME`` (default: ``test_quickscale_social``)
* ``QS_SOCIAL_DB_USER`` (default: ``postgres``)
* ``QS_SOCIAL_DB_PASSWORD`` (default: ``""``)
* ``QS_SOCIAL_DB_HOST`` (default: ``localhost``)
* ``QS_SOCIAL_DB_PORT`` (default: ``5432``)
"""

import os

SECRET_KEY = "test-secret-key-for-social-module"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "quickscale_modules_orgs",
    "quickscale_modules_social",
]

QUICKSCALE_MODE = "saas"

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

if os.environ.get("QUICKSCALE_TEST_DB") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("QS_SOCIAL_DB_NAME", "test_quickscale_social"),
            "USER": os.environ.get("QS_SOCIAL_DB_USER", "postgres"),
            "PASSWORD": os.environ.get("QS_SOCIAL_DB_PASSWORD", ""),
            "HOST": os.environ.get("QS_SOCIAL_DB_HOST", "localhost"),
            "PORT": os.environ.get("QS_SOCIAL_DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

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
