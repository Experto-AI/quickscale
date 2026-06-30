"""Django settings for blog module tests"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Seed the SA2.1 escape hatch before Django setup so the always-on
# boot guard does not block test startup.
os.environ.setdefault("QUICKSCALE_ALLOW_BYPASSRLS", "1")

SECRET_KEY = "test-secret-key-for-blog-module"

DEBUG = True

ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "markdownx",
    "quickscale_modules_orgs",
    "quickscale_modules_blog",
]

QUICKSCALE_MODE = "saas"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "quickscale_modules_orgs.middleware.TenantMiddleware",
]

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "tests" / "templates"],
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

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("QS_BLOG_DB_NAME", "test_quickscale_blog"),
        "USER": os.environ.get("QS_BLOG_DB_USER", "postgres"),
        "PASSWORD": os.environ.get("QS_BLOG_DB_PASSWORD", ""),
        "HOST": os.environ.get("QS_BLOG_DB_HOST", "localhost"),
        "PORT": os.environ.get("QS_BLOG_DB_PORT", "5432"),
    }
}

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "tests" / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Markdownx settings
MARKDOWNX_MARKDOWN_EXTENSIONS = [
    "markdown.extensions.fenced_code",
    "markdown.extensions.tables",
    "markdown.extensions.toc",
]
MARKDOWNX_MEDIA_PATH = "blog/markdownx/"
