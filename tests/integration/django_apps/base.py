"""Base classes for Django application integration tests."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
from django.test import TestCase, Client
from django.conf import settings


def setup_django_template_path():
    """Add project templates directory to Python path for imports."""
    quickscale_root = Path(__file__).parent.parent.parent.parent
    template_path = quickscale_root / "quickscale" / "project_templates"
    
    template_path_str = str(template_path)
    if template_path_str not in sys.path:
        sys.path.insert(0, template_path_str)
    
    return template_path


def setup_core_env_utils_mock():
    """Set up core.env_utils mock for integration tests."""
    def get_env(var_name, default=None):
        """Mock implementation of get_env."""
        return os.environ.get(var_name, default)
    
    def is_feature_enabled(feature_name):
        """Mock implementation of is_feature_enabled."""
        env_var = f"{feature_name.upper()}_ENABLED"
        return os.environ.get(env_var, 'false').lower() == 'true'
    
    # Store original module if it exists
    original_module = sys.modules.get('core.env_utils')
    
    mock_env_utils = MagicMock()
    mock_env_utils.get_env = get_env
    mock_env_utils.is_feature_enabled = is_feature_enabled
    sys.modules['core.env_utils'] = mock_env_utils
    
    return mock_env_utils, original_module


def cleanup_core_env_utils_mock(original_module):
    """Clean up core.env_utils mock for integration tests."""
    if original_module is not None:
        sys.modules['core.env_utils'] = original_module
    else:
        sys.modules.pop('core.env_utils', None)


def setup_django_settings():
    """Set up Django settings for integration tests."""
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            USE_TZ=True,
            SECRET_KEY="test-key-for-django-integration",
            STRIPE_SECRET_KEY="sk_test_123",
            STRIPE_PUBLIC_KEY="pk_test_123", 
            STRIPE_WEBHOOK_SECRET="whsec_test_123",
            STRIPE_ENABLED=True,
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
            INSTALLED_APPS=[
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "django.contrib.sites",
                "django.contrib.sessions",
                "django.contrib.messages",
                "django.contrib.admin",
                "allauth",
                "allauth.account",
                "allauth.socialaccount",
                "users",
                "credits", 
                "stripe_manager",
                "admin_dashboard",
                "common",
                "public",
                "services",
                "api",
            ],
            SITE_ID=1,
            MIDDLEWARE=[
                'django.middleware.security.SecurityMiddleware',
                'django.contrib.sessions.middleware.SessionMiddleware',
                'django.middleware.common.CommonMiddleware',
                'django.middleware.csrf.CsrfViewMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
                'django.contrib.messages.middleware.MessageMiddleware',
            ],
            AUTH_USER_MODEL='users.CustomUser',
            ROOT_URLCONF='tests.integration.django_apps.test_urls',
            TEMPLATES=[{
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [],
                'APP_DIRS': True,
                'OPTIONS': {
                    'context_processors': [
                        'django.template.context_processors.debug',
                        'django.template.context_processors.request',
                        'django.contrib.auth.context_processors.auth',
                        'django.contrib.messages.context_processors.messages',
                    ],
                },
            }],
        )


class DjangoIntegrationTestCase(TestCase):
    """Base class for Django integration tests."""
    
    @classmethod 
    def setUpClass(cls):
        """Set up Django environment for integration tests."""
        super().setUpClass()
        setup_django_template_path()
        cls._env_utils_mock, cls._original_env_utils = setup_core_env_utils_mock()
        setup_django_settings()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after integration tests."""
        cleanup_core_env_utils_mock(cls._original_env_utils)
        super().tearDownClass()
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        super().setUp()


class StripeIntegrationTestCase(DjangoIntegrationTestCase):
    """Base class for Stripe integration tests."""
    
    def setUp(self):
        """Set up environment with Stripe configuration."""
        super().setUp()
        # Additional Stripe-specific setup can go here


class CreditSystemIntegrationTestCase(DjangoIntegrationTestCase):
    """Base class for credit system integration tests."""
    
    def setUp(self):
        """Set up environment with credit system configuration."""
        super().setUp()
        # Additional credit system setup can go here
