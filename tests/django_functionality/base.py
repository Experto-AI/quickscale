"""Base classes for Django component unit tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

from django.conf import settings
from django.test import TestCase


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
    # Import centralized test utilities (DRY principle)
    from tests.test_utilities import TestUtilities
    
    mock_env_utils = MagicMock()
    mock_env_utils.get_env = TestUtilities.get_env
    mock_env_utils.is_feature_enabled = TestUtilities.is_feature_enabled
    
    # Store original module if it exists
    original_module = sys.modules.get('core.env_utils')
    sys.modules['core.env_utils'] = mock_env_utils
    
    return mock_env_utils, original_module


def setup_core_configuration_mock():
    """Set up mock for core.configuration module."""
    import types
    
    class MockStripeConfig:
        secret_key = 'sk_test_mock'
        api_version = '2023-10-16'

    class MockConfig:
        stripe = MockStripeConfig()
        
        def is_stripe_enabled_and_configured(self):
            return True
        
        def get_env_bool(self, key, default):
            return default

    # Create module mock and set config as an attribute
    mock_config_module = types.ModuleType('core.configuration')
    mock_config_module.config = MockConfig()
    
    # Store original module if it exists
    original_module = sys.modules.get('core.configuration')
    sys.modules['core.configuration'] = mock_config_module
    
    return mock_config_module, original_module


def cleanup_core_env_utils_mock(original_module):
    """Clean up mock for core.env_utils module."""
    if original_module is not None:
        sys.modules['core.env_utils'] = original_module
    else:
        sys.modules.pop('core.env_utils', None)


def cleanup_core_configuration_mock(original_module):
    """Clean up mock for core.configuration module."""
    if original_module is not None:
        sys.modules['core.configuration'] = original_module
    else:
        sys.modules.pop('core.configuration', None)


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
            ENABLE_STRIPE=True,
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


# Import Django test classes
from django.test import Client


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
