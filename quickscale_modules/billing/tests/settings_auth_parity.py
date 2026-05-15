"""Billing test settings that exercise the auth module custom user model."""

from copy import deepcopy

from tests import settings as base_settings

SECRET_KEY = base_settings.SECRET_KEY
DEBUG = base_settings.DEBUG
ALLOWED_HOSTS = deepcopy(base_settings.ALLOWED_HOSTS)

INSTALLED_APPS = [
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "quickscale_modules_auth",
    *base_settings.INSTALLED_APPS,
]

MIDDLEWARE = [
    *base_settings.MIDDLEWARE,
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = base_settings.ROOT_URLCONF
TEMPLATES = deepcopy(base_settings.TEMPLATES)
DATABASES = deepcopy(base_settings.DATABASES)
USE_TZ = base_settings.USE_TZ
TIME_ZONE = base_settings.TIME_ZONE
DEFAULT_AUTO_FIELD = base_settings.DEFAULT_AUTO_FIELD
STATIC_URL = base_settings.STATIC_URL

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
AUTH_USER_MODEL = "quickscale_modules_auth.User"
SITE_ID = 1
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ALLOW_REGISTRATION = True
