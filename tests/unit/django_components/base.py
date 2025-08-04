"""Base classes for Django component unit tests."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
from django.test import TestCase
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
    """Set up mock for core.env_utils module."""
    def get_env(key, default=None):
        """Mock implementation of get_env."""
        return os.environ.get(key, default)
    
    def is_feature_enabled(value):
        """Mock implementation of is_feature_enabled."""
        if not value:
            return False
        enabled_values = ('true', 'yes', '1', 'on', 'enabled', 'y', 't')
        return str(value).lower() in enabled_values
    
    mock_env_utils = MagicMock()
    mock_env_utils.get_env = get_env
    mock_env_utils.is_feature_enabled = is_feature_enabled
    
    # Store original module if it exists
    original_module = sys.modules.get('core.env_utils')
    sys.modules['core.env_utils'] = mock_env_utils
    
    return mock_env_utils, original_module


def cleanup_core_env_utils_mock(original_module):
    """Clean up mock for core.env_utils module."""
    if original_module is not None:
        sys.modules['core.env_utils'] = original_module
    elif 'core.env_utils' in sys.modules:
        del sys.modules['core.env_utils']


def setup_django_settings():
    """Set up Django settings for template component tests."""
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            USE_TZ=True,
            SECRET_KEY="test-key-for-django-components",
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
                "users",
                "credits", 
                "stripe_manager",
                "admin_dashboard",
                "common",
                "public",
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
            ROOT_URLCONF='core.urls',
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


class DjangoModelTestCase(TestCase):
    """Base class for Django model unit tests."""
    
    _original_module = None
    
    @classmethod
    def setUpClass(cls):
        """Set up Django environment for model tests."""
        setup_django_template_path()
        _, cls._original_module = setup_core_env_utils_mock()
        setup_django_settings()
        super().setUpClass()
        
    @classmethod
    def tearDownClass(cls):
        """Clean up Django environment for model tests."""
        cleanup_core_env_utils_mock(cls._original_module)
        super().tearDownClass()


class DjangoAdminTestCase(TestCase):
    """Base class for Django admin unit tests."""
    
    _original_module = None
    
    @classmethod
    def setUpClass(cls):
        """Set up Django environment for admin tests."""
        setup_django_template_path()
        _, cls._original_module = setup_core_env_utils_mock()
        setup_django_settings()
        super().setUpClass()
        
    @classmethod
    def tearDownClass(cls):
        """Clean up Django environment for admin tests."""
        cleanup_core_env_utils_mock(cls._original_module)
        super().tearDownClass()


class DjangoUtilsTestCase(TestCase):
    """Base class for Django utilities unit tests."""
    
    _original_module = None
    
    @classmethod
    def setUpClass(cls):
        """Set up Django environment for utils tests."""
        setup_django_template_path()
        _, cls._original_module = setup_core_env_utils_mock()
        setup_django_settings()
        super().setUpClass()
        
    @classmethod
    def tearDownClass(cls):
        """Clean up Django environment for utils tests."""
        cleanup_core_env_utils_mock(cls._original_module)
        super().tearDownClass()
