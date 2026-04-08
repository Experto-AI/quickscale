"""Django settings for QuickScale notifications module tests."""

SECRET_KEY = "test-secret-key-for-notifications-module"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "quickscale_modules_forms",
    "quickscale_modules_notifications",
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

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "form_submit": "5/hour",
    },
}

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

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "default@example.com"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

QUICKSCALE_NOTIFICATIONS_ENABLED = True
QUICKSCALE_NOTIFICATIONS_PROVIDER = "resend"
QUICKSCALE_NOTIFICATIONS_SENDER_NAME = "QuickScale"
QUICKSCALE_NOTIFICATIONS_SENDER_EMAIL = "noreply@example.com"
QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL = "support@example.com"
QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN = "mg.example.com"
QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR = "RESEND_API_KEY"
QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR = (
    "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"
)
QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS = ["quickscale", "transactional"]
QUICKSCALE_NOTIFICATIONS_ALLOWED_TAGS = [
    "quickscale",
    "transactional",
    "notifications",
    "auth",
    "forms",
    "ops",
    "testing",
]
QUICKSCALE_NOTIFICATIONS_WEBHOOK_TTL_SECONDS = 300
