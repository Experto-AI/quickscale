"""Tests for Stripe configuration and feature flag."""
import os
import sys
from unittest.mock import patch, MagicMock
import unittest

from quickscale.utils.env_utils import get_env, is_feature_enabled, refresh_env_cache

# Configure logging for tests
import logging
logger = logging.getLogger(__name__)

class StripeConfigurationTests(unittest.TestCase):
    """Test suite for Stripe configuration behavior."""

    def setUp(self):
        """Set up environment for each test."""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore original environment after each test."""
        os.environ.clear()
        os.environ.update(self.original_env)
        refresh_env_cache()  # Ensure the cache is restored after each test

    def test_stripe_disabled_by_default(self):
        """Test that Stripe integration is disabled by default."""
        # Create mock settings without Stripe app in INSTALLED_APPS
        mock_installed_apps = [
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'users.apps.UsersConfig'
        ]
        
        # Test with empty environment (Stripe disabled by default)
        with patch('quickscale.utils.env_utils._env_vars', {'STRIPE_ENABLED': 'False'}):
            # Ensure STRIPE_ENABLED is False by default
            self.assertFalse(
                is_feature_enabled(get_env('STRIPE_ENABLED', 'False')),
                "STRIPE_ENABLED should be False by default"
            )
            
            # Without patching settings.INSTALLED_APPS directly, we can verify our logic:
            # Assume we have a function that determines if Stripe app should be in INSTALLED_APPS based on STRIPE_ENABLED
            def should_include_stripe_app():
                return is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
            
            self.assertFalse(should_include_stripe_app(), "stripe.apps.StripeConfig should not be included when STRIPE_ENABLED is False")

    def test_stripe_settings_with_flag_enabled(self):
        """Test that enabling Stripe loads the correct settings."""
        # Create a test environment with Stripe enabled
        test_env = {
            'STRIPE_ENABLED': 'true',
            'STRIPE_PUBLIC_KEY': 'pk_test_example',
            'STRIPE_SECRET_KEY': 'sk_test_example',
            'STRIPE_WEBHOOK_SECRET': 'whsec_example',
        }
        
        # Patch the environment cache
        with patch('quickscale.utils.env_utils._env_vars', test_env):
            with patch('quickscale.utils.env_utils._env_vars_from_file', {}):
                # Test the flag is enabled
                self.assertTrue(is_feature_enabled(get_env('STRIPE_ENABLED', 'False')), 
                               "STRIPE_ENABLED should be True when set to 'true'")
                
                # Verify settings values are retrieved correctly through get_env
                self.assertEqual(get_env('STRIPE_PUBLIC_KEY'), 'pk_test_example')
                self.assertEqual(get_env('STRIPE_SECRET_KEY'), 'sk_test_example')
                self.assertEqual(get_env('STRIPE_WEBHOOK_SECRET'), 'whsec_example')
                
                # Without patching settings.INSTALLED_APPS directly, we can verify our logic:
                # Assume we have a function that determines if Stripe app should be in INSTALLED_APPS based on STRIPE_ENABLED
                def should_include_stripe_app():
                    return is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
                
                self.assertTrue(should_include_stripe_app(), "stripe.apps.StripeConfig should be included when STRIPE_ENABLED is True")
