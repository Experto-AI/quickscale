"""Django settings for QuickScale social module tests."""

SECRET_KEY = "test-secret-key-for-social-module"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "quickscale_modules_social",
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

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

QUICKSCALE_SOCIAL_LINK_TREE_ENABLED = True
QUICKSCALE_SOCIAL_LAYOUT_VARIANT = "list"
QUICKSCALE_SOCIAL_EMBEDS_ENABLED = True
QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST = [
    "facebook",
    "instagram",
    "linkedin",
    "tiktok",
    "x",
    "youtube",
]
QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS = 300
QUICKSCALE_SOCIAL_LINKS_PER_PAGE = 24
QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE = 12
