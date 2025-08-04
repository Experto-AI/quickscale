"""Base classes for Django workflow e2e tests."""

import os
import sys
from pathlib import Path


def setup_core_env_utils_mock():
    """Set up core.env_utils mock for e2e tests."""
    def get_env(var_name, default=None):
        """Mock implementation of get_env."""
        return os.environ.get(var_name, default)
    
    def is_feature_enabled(feature_name):
        """Mock implementation of is_feature_enabled."""
        env_var = f"{feature_name.upper()}_ENABLED"
        return os.environ.get(env_var, 'false').lower() == 'true'
    
    # Store original module if it exists
    original_module = sys.modules.get('core.env_utils')
    
    # Create a simple object instead of MagicMock to avoid interference
    class MockEnvUtils:
        def __init__(self):
            self.get_env = get_env
            self.is_feature_enabled = is_feature_enabled
    
    sys.modules['core.env_utils'] = MockEnvUtils()
    
    return sys.modules['core.env_utils'], original_module


def cleanup_core_env_utils_mock(original_module):
    """Clean up core.env_utils mock for e2e tests."""
    if original_module is not None:
        sys.modules['core.env_utils'] = original_module
    else:
        sys.modules.pop('core.env_utils', None)


import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
from django.test import TestCase, TransactionTestCase, Client
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
    # Store original module if it exists
    original_module = sys.modules.get('core.env_utils')
    
    def get_env(key, default=None):
        """Mock implementation of get_env."""
        return os.environ.get(key, default)
    
    def is_feature_enabled(feature_name):
        """Mock implementation of is_feature_enabled."""
        env_var = f"{feature_name.upper()}_ENABLED"
        return os.environ.get(env_var, 'false').lower() == 'true'
    
    # Create a simple object instead of MagicMock to avoid interference
    class MockEnvUtils:
        def __init__(self):
            self.get_env = get_env
            self.is_feature_enabled = is_feature_enabled
    
    mock_module = MockEnvUtils()
    sys.modules['core.env_utils'] = mock_module
    
    return mock_module, original_module


def setup_django_settings():
    """Set up Django settings for e2e tests."""
    if not settings.configured:
        # Get paths for templates
        quickscale_root = Path(__file__).parent.parent.parent.parent
        test_templates_path = quickscale_root / "tests" / "admin_dashboard" / "templates"
        project_templates_path = quickscale_root / "quickscale" / "project_templates" / "templates"
        
        settings.configure(
            DEBUG=True,
            USE_TZ=True,
            SECRET_KEY="test-key-for-django-e2e",
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
                'DIRS': [str(test_templates_path), str(project_templates_path)],
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


class DjangoE2ETestCase(TestCase):
    """Base class for Django E2E workflow tests."""
    
    @classmethod 
    def setUpClass(cls):
        """Set up Django environment for E2E tests."""
        super().setUpClass()
        setup_django_template_path()
        cls._env_utils_mock, cls._original_env_utils = setup_core_env_utils_mock()
        setup_django_settings()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after E2E tests."""
        cleanup_core_env_utils_mock(cls._original_env_utils)
        super().tearDownClass()
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        super().setUp()


class DjangoE2ETransactionTestCase(TransactionTestCase):
    """Base class for Django E2E tests requiring transaction testing."""
    
    @classmethod 
    def setUpClass(cls):
        """Set up Django environment for E2E transaction tests."""
        super().setUpClass()
        setup_django_template_path()
        cls._env_utils_mock, cls._original_env_utils = setup_core_env_utils_mock()
        setup_django_settings()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after E2E transaction tests."""
        cleanup_core_env_utils_mock(cls._original_env_utils)
        super().tearDownClass()
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        super().setUp()


class UserWorkflowTestCase(DjangoE2ETestCase):
    """Base class for user workflow E2E tests."""
    
    def setUp(self):
        """Set up environment for user workflow tests."""
        super().setUp()
        # Additional user workflow setup can go here


class PaymentWorkflowTestCase(DjangoE2ETestCase):
    """Base class for payment workflow E2E tests."""
    
    def setUp(self):
        """Set up environment for payment workflow tests."""
        super().setUp()
        # Additional payment workflow setup can go here


class AdminWorkflowTestCase(DjangoE2ETestCase):
    """Base class for admin workflow E2E tests."""
    
    def setUp(self):
        """Set up environment for admin workflow tests."""
        super().setUp()
        # Additional admin workflow setup can go here
