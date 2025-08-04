"""Utilities for template validation tests.

This module provides utilities to help template validation tests
properly import and test Django template components.
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

def setup_template_path():
    """Add project templates directory to Python path for imports."""
    # Get the QuickScale root directory
    quickscale_root = Path(__file__).parent.parent.parent
    template_path = quickscale_root / "quickscale" / "project_templates"
    
    # Remove any existing template paths to avoid conflicts
    template_path_str = str(template_path)
    if template_path_str in sys.path:
        sys.path.remove(template_path_str)
    
    # Insert at the beginning to prioritize template imports over test directory imports
    sys.path.insert(0, template_path_str)
    
    # Also remove any test directory paths that might conflict
    test_paths_to_remove = []
    quickscale_test_path = str(quickscale_root / "tests")
    for path in sys.path:
        if path.startswith(quickscale_test_path) and "template_validation" not in path:
            test_paths_to_remove.append(path)
    
    for path in test_paths_to_remove:
        sys.path.remove(path)
    
    return template_path


def setup_core_env_utils_mock():
    """Set up mock for core.env_utils module."""
    # Import the mock utilities
    from .stripe_manager.mock_env_utils import get_env, is_feature_enabled
    
    # Create a mock for 'core.env_utils' module
    mock_env_utils = MagicMock()
    mock_env_utils.get_env = get_env
    mock_env_utils.is_feature_enabled = is_feature_enabled
    sys.modules['core.env_utils'] = mock_env_utils
    
    return mock_env_utils


def setup_django_settings():
    """Set up Django settings for template validation tests."""
    from django.conf import settings
    
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            USE_TZ=True,
            SECRET_KEY="test-key-for-template-validation",
            # Stripe-specific settings
            STRIPE_SECRET_KEY="sk_test_123",
            STRIPE_PUBLIC_KEY="pk_test_123", 
            STRIPE_WEBHOOK_SECRET="whsec_test_123",
            STRIPE_ENABLED=True,
            # Database settings
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
            INSTALLED_APPS=[
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "django.contrib.sites",
                "django.contrib.sessions",
                "django.contrib.messages",
                "django.contrib.admin",
                # Template apps that we're testing
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
        
    # Initialize Django
    import django
    django.setup()
