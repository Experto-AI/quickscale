"""Django settings for QuickScale backups module tests."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "test-secret-key-for-backups-module"
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

WSGI_APPLICATION = "tests.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test.sqlite3",
    }
}

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"

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
