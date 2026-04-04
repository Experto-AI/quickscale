"""Django settings for QuickScale analytics module tests."""

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
        "DIRS": [],
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
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
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
