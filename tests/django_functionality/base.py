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
    else:
        sys.modules.pop('core.env_utils', None)


def setup_django_settings():
    """Set up Django settings for Django functionality tests."""
    if not settings.configured:
        # Use PostgreSQL test database configuration
        db_config = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'quickscale_test',
            'USER': 'test_user',
            'PASSWORD': 'test_pass',
            'HOST': 'localhost',
            'PORT': '5433',
            'TEST': {
                'NAME': 'test_django_functionality',
            },
        }
        
        # Get paths for templates
        quickscale_root = Path(__file__).parent.parent.parent
        project_templates_path = quickscale_root / "quickscale" / "project_templates" / "templates"
        
        settings.configure(
            DEBUG=True,
            USE_TZ=True,
            SECRET_KEY="test-key-for-django-functionality-tests",
            PROJECT_NAME="Test QuickScale Project",
            STRIPE_SECRET_KEY="sk_test_123",
            STRIPE_PUBLIC_KEY="pk_test_123",
            STRIPE_WEBHOOK_SECRET="whsec_test_123",
            STRIPE_ENABLED=True,
            DATABASES={"default": db_config},
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
            ROOT_URLCONF='core.urls',
            TEMPLATES=[{
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [str(project_templates_path)],
                'APP_DIRS': True,
                'OPTIONS': {
                    'context_processors': [
                        'core.context_processors.project_settings',
                        'django.template.context_processors.debug',
                        'django.template.context_processors.request',
                        'django.contrib.auth.context_processors.auth',
                        'django.contrib.messages.context_processors.messages',
                    ],
                },
            }],
        )


# Import Django test classes
from django.test import TestCase, Client


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


class PaymentWorkflowTestCase(DjangoIntegrationTestCase):
    """Base class for payment workflow tests."""
    
    def setUp(self):
        """Set up environment for payment workflow tests."""
        super().setUp()
        # Additional payment workflow setup can go here


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


def setup_core_env_utils_mock():
    """Clean up core.env_utils module if it exists."""
    original_env_utils = None
    if 'core.env_utils' in sys.modules:
        original_env_utils = sys.modules['core.env_utils']
        del sys.modules['core.env_utils']
    return None, original_env_utils


def setup_django_settings():
    """Set up Django settings for template component tests."""
    if not settings.configured:
        # Import PostgreSQL test configuration
        from core.test_db_config import get_test_db_config
        
        settings.configure(
            DEBUG=True,
            USE_TZ=True,
            SECRET_KEY="test-key-for-django-components",
            STRIPE_SECRET_KEY="sk_test_123",
            STRIPE_PUBLIC_KEY="pk_test_123", 
            STRIPE_WEBHOOK_SECRET="whsec_test_123",
            STRIPE_ENABLED=True,
            DATABASES={"default": get_test_db_config()},
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
