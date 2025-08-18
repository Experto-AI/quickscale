"""Test settings for QuickScale template - PostgreSQL only."""

from .settings import *
from .configuration import config

# Use PostgreSQL for testing - NO SQLite fallback
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config.get_env('TEST_DB_NAME', 'quickscale_test'),
        'USER': config.get_env('TEST_DB_USER', 'test_user'),
        'PASSWORD': config.get_env('TEST_DB_PASSWORD', 'test_pass'),
        'HOST': config.get_env('TEST_DB_HOST', 'localhost'),
        'PORT': config.get_env('TEST_DB_PORT', '5433'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
        'TEST': {
            'NAME': 'test_quickscale_test',
        }
    }
}

# Fail hard if PostgreSQL is not available
try:
    import psycopg2
except ImportError:
    raise ImportError(
        "PostgreSQL adapter (psycopg2) is required for testing. "
        "Install it with: pip install psycopg2-binary"
    )

# Disable Stripe for testing
STRIPE_ENABLED = False
STRIPE_LIVE_MODE = False

# Use console email backend for testing
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable logging during tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'root': {
        'handlers': ['null'],
    },
}

# Speed up password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable rate limiting for tests to avoid 429 errors (using new django-allauth format)
ACCOUNT_RATE_LIMITS = {}  # Disable all rate limiting for tests
ACCOUNT_EMAIL_CONFIRMATION_HMAC = False  # Simplify for testing

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True
    
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()
