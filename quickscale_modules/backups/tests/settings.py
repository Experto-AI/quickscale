"""Django settings for QuickScale backups module tests."""

import os
from pathlib import Path

from quickscale_core.testing.settings import (
    module_settings_schema,
    suite_database,
    suite_secret_key,
)

# BYPASSRLS escape hatch removed from settings.py AND conftest.py.
# No module test code automatically primes QUICKSCALE_ALLOW_BYPASSRLS.
# NOBYPASSRLS is the default for module test suites. Mark individual
# tests that need BYPASSRLS with @pytest.mark.bypass_rls.
# Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include bypass_rls tests.

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = suite_secret_key("backups")
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "quickscale_modules_backups",
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

WSGI_APPLICATION = "tests._wsgi.application"

# Backups module now uses the PostgreSQL/RLS integration seam
# via QS_BACKUPS_DB_* env vars, matching every other module's pattern.
# SQLite-specific backup-format coverage is preserved in the one test
# that exercises the JSON export codepath (test_create_backup_uses_json_export_for_sqlite).
DATABASES = {
    "default": suite_database("backups"),
}

# The DR engine never runs a dump or restore under the restricted runtime role.
# The integration harness connects this suite as that role, so point the
# privileged backup URL at the harness superuser (the provisioning contract
# uses trust authentication). The `backups` profile already connects as the
# superuser, so it needs no extra URL.
_backup_database = DATABASES["default"]
if os.environ.get("QS_BACKUPS_DB_USER", "postgres") != "postgres":
    os.environ.setdefault(
        "QUICKSCALE_BACKUP_DATABASE_URL",
        "postgresql://postgres@{HOST}:{PORT}/{NAME}".format(**_backup_database),
    )

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"

QUICKSCALE_BACKUPS_ENABLED = True
QUICKSCALE_BACKUPS_RETENTION_DAYS = 14
QUICKSCALE_BACKUPS_NAMING_PREFIX = "db"
QUICKSCALE_BACKUPS_TARGET_MODE = "local"
QUICKSCALE_BACKUPS_LOCAL_DIRECTORY = ".quickscale/backups"
QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME = ""
QUICKSCALE_BACKUPS_REMOTE_PREFIX = "backups/private"
QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL = ""
QUICKSCALE_BACKUPS_REMOTE_REGION_NAME = ""
QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR = (
    "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
)
QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR = (
    "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
)
QUICKSCALE_BACKUPS_AUTOMATION_ENABLED = False
QUICKSCALE_BACKUPS_SCHEDULE = "0 2 * * *"
QUICKSCALE_APP_VERSION = "test-app"
QUICKSCALE_STORAGE_BACKEND = "local"

_MODULES_ROOT = Path(__file__).resolve().parents[3] / "quickscale_modules"
MODULE_SETTINGS_SCHEMA = module_settings_schema(_MODULES_ROOT, "backups")
