"""Django settings for storage module tests."""

import os

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
