"""Django settings for testing auth module"""

import os

SECRET_KEY = "test-secret-key-for-auth-module"

QUICKSCALE_MODE = "solo"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "quickscale_modules_auth",
    "quickscale_modules_orgs",
    "quickscale_modules_billing",
    "allauth",
    "allauth.account",
]

QUICKSCALE_BILLING_ENABLED = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("QS_AUTH_DB_NAME", "test_quickscale_auth"),
        "USER": os.environ.get("QS_AUTH_DB_USER", "postgres"),
        "PASSWORD": os.environ.get("QS_AUTH_DB_PASSWORD", ""),
        "HOST": os.environ.get("QS_AUTH_DB_HOST", "localhost"),
        "PORT": os.environ.get("QS_AUTH_DB_PORT", "5432"),
    }
}

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

AUTH_USER_MODEL = "quickscale_modules_auth.User"

SITE_ID = 1

# django-allauth 0.62+ settings (new format)
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ALLOW_REGISTRATION = True

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(os.path.dirname(__file__), "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.static",
            ],
        },
    },
]

ROOT_URLCONF = "tests.urls"

USE_TZ = True

# Static files configuration
STATIC_URL = "/static/"
STATIC_ROOT = "/tmp/static"

# Media files configuration
MEDIA_URL = "/media/"
MEDIA_ROOT = "/tmp/media"
