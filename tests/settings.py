"""Django settings for testing auth module"""

import os
from pathlib import Path

from quickscale_core.manifest.settings_schema import load_settings_schema

_MODULES_ROOT = Path(__file__).resolve().parents[3] / "quickscale_modules"

SECRET_KEY = "test-secret-key-for-auth-module"

# This suite installs billing enabled; billing's rule 35 startup check needs
# the Stripe secret key and webhook secret to resolve.
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_auth_suite")
os.environ.setdefault("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_auth_suite")

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
        "USER": os.environ.get("QS_AUTH_DB_USER", "quickscale_test_role"),
        "PASSWORD": os.environ.get("QS_AUTH_DB_PASSWORD", ""),
        "HOST": os.environ.get("QS_AUTH_DB_HOST", "localhost"),
        "PORT": os.environ.get("QS_AUTH_DB_PORT", "5432"),
    }
}

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

AUTH_USER_MODEL = "quickscale_auth.User"

SITE_ID = 1

# django-allauth 0.62+ settings (new format)
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ALLOW_REGISTRATION = True
SESSION_COOKIE_AGE = 1209600

# billing is installed in this suite; declare its options.
QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR = "STRIPE_PUBLISHABLE_KEY"
QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR = "STRIPE_SECRET_KEY"
QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR = "QUICKSCALE_BILLING_WEBHOOK_SECRET"
QUICKSCALE_BILLING_CURRENCY = "usd"
QUICKSCALE_BILLING_API_RATE_LIMIT = "30/hour"

# Rule 3: schemas for every installed module that registers the generic check.
MODULE_SETTINGS_SCHEMA = {
    name: load_settings_schema(_MODULES_ROOT / name / "module.yml")
    for name in ("auth", "orgs", "billing")
}

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
