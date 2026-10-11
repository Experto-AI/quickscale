"""Django settings for storage module tests."""

import os
from pathlib import Path

from quickscale_core.manifest.settings_schema import load_settings_schema

SECRET_KEY = "test-secret-key-for-storage-module"
DEBUG = True
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "markdownx",
    "quickscale_modules_storage",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("QS_STORAGE_DB_NAME", "test_quickscale_storage"),
        "USER": os.environ.get("QS_STORAGE_DB_USER", "postgres"),
        "PASSWORD": os.environ.get("QS_STORAGE_DB_PASSWORD", ""),
        "HOST": os.environ.get("QS_STORAGE_DB_HOST", "localhost"),
        "PORT": os.environ.get("QS_STORAGE_DB_PORT", "5432"),
    }
}

ROOT_URLCONF = "tests.urls"

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MEDIA_URL = "/media/"

# Rule 41: the settings the module's adapter writes for the one shared
# staff-guarded Markdownx editor mount.
MARKDOWNX_MARKDOWN_EXTENSIONS = [
    "markdown.extensions.fenced_code",
    "markdown.extensions.tables",
    "markdown.extensions.toc",
]
MARKDOWNX_MEDIA_PATH = "markdownx/"

# Rule 3: every declared storage setting plus the applied credential settings,
# so the generic startup check and the rule 35 vendor check both run against a
# complete stub.  The credential values mirror what apply writes for unset
# environment variables (empty strings from the env-var projection).
QUICKSCALE_STORAGE_ENABLED = True
QUICKSCALE_STORAGE_BACKEND = "local"
QUICKSCALE_STORAGE_PUBLIC_BASE_URL = ""
AWS_STORAGE_BUCKET_NAME = ""
AWS_S3_ENDPOINT_URL = ""
AWS_S3_REGION_NAME = ""
QUICKSCALE_STORAGE_ACCESS_KEY_ID_ENV_VAR = "AWS_ACCESS_KEY_ID"
QUICKSCALE_STORAGE_SECRET_ACCESS_KEY_ENV_VAR = "AWS_SECRET_ACCESS_KEY"
AWS_DEFAULT_ACL = ""
AWS_QUERYSTRING_AUTH = False
AWS_ACCESS_KEY_ID = ""
AWS_SECRET_ACCESS_KEY = ""

# Rule 3: the compiled option schema the generic startup check reads, derived
# from the module's own manifest so it can never drift from the declarations.
MODULE_SETTINGS_SCHEMA = {
    "storage": load_settings_schema(
        Path(__file__).resolve().parent.parent / "module.yml"
    )
}
