"""Django settings for storage module tests."""

import os
from pathlib import Path

from quickscale_core.manifest.settings_schema import load_settings_schema

SECRET_KEY = "test-secret-key-for-storage-module"
DEBUG = True
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "quickscale_modules_storage",
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

# Rule 3: every declared storage setting plus the applied credential settings,
# so the generic startup check and the rule 35 vendor check both run against a
# complete stub.  The credential values mirror what apply writes for unset
# environment variables (empty strings from the env-var projection).
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
