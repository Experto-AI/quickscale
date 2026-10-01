"""Django settings for blog module tests"""

import os
import tempfile
from pathlib import Path

from quickscale_core.manifest.settings_schema import load_settings_schema

BASE_DIR = Path(__file__).resolve().parent.parent
SHARED_TEST_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "tests_shared" / "templates"
)

# BYPASSRLS escape hatch removed from settings.py AND conftest.py.
# No module test code automatically primes QUICKSCALE_ALLOW_BYPASSRLS.
# NOBYPASSRLS is the default for module test suites. Mark individual
# tests that need BYPASSRLS with @pytest.mark.bypass_rls.
# Set QUICKSCALE_ALLOW_BYPASSRLS=1 in the shell to include bypass_rls tests.

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
    "rest_framework",
    "markdownx",
    "quickscale_modules_orgs",
    "quickscale_modules_storage",
    "quickscale_modules_blog",
]

QUICKSCALE_ORGS_MODE = "saas"

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
        "DIRS": [SHARED_TEST_TEMPLATES],
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
        "USER": os.environ.get("QS_BLOG_DB_USER", "quickscale_test_role"),
        "PASSWORD": os.environ.get("QS_BLOG_DB_PASSWORD", ""),
        "HOST": os.environ.get("QS_BLOG_DB_HOST", "localhost"),
        "PORT": os.environ.get("QS_BLOG_DB_PORT", "5432"),
    }
}

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
# Use a temporary directory so test media files never land in the
# tracked worktree. The conftest.py session fixture overrides this with
# a pytest-managed tmp_path for proper cleanup; this is the safe fallback.
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="qs_blog_test_media_"))

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Blog module required settings (fail-hard defaults)
QUICKSCALE_BLOG_ENABLED = True
QUICKSCALE_BLOG_RSS_ENABLED = True
QUICKSCALE_BLOG_API_RATE_LIMIT = "5/hour"
QUICKSCALE_BLOG_POSTS_PER_PAGE = 10
QUICKSCALE_BLOG_API_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
QUICKSCALE_BLOG_API_UPLOAD_MAX_WIDTH = 4096
QUICKSCALE_BLOG_API_UPLOAD_MAX_HEIGHT = 4096
QUICKSCALE_BLOG_API_ALLOWED_IMAGE_FORMATS = ["PNG", "JPEG", "WEBP", "GIF"]

# Rule 3: storage's declared settings, so installing it here satisfies both
# its generic settings check and the rule 35 vendor check.
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
_MODULES_ROOT = Path(__file__).resolve().parents[3] / "quickscale_modules"
MODULE_SETTINGS_SCHEMA = {
    name: load_settings_schema(_MODULES_ROOT / name / "module.yml")
    for name in ("blog", "orgs", "storage")
}

# DRF configuration mirroring the generated settings: session authentication
# only, the one QuickScale error shape, and the blog API throttle rate the
# module wiring contributes (Module Conventions rules 9 and 32).
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "quickscale_blog_api": QUICKSCALE_BLOG_API_RATE_LIMIT,
    },
    "EXCEPTION_HANDLER": "quickscale_core.runtime.conventions.exception_handler",
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "quickscale-blog-tests",
    }
}

# trusted-proxy settings required by get_client_ip()
USE_X_FORWARDED_FOR = False
TRUSTED_PROXY_COUNT = 0

# Markdownx settings
MARKDOWNX_MARKDOWN_EXTENSIONS = [
    "markdown.extensions.fenced_code",
    "markdown.extensions.tables",
    "markdown.extensions.toc",
]
MARKDOWNX_MEDIA_PATH = "blog/markdownx/"
