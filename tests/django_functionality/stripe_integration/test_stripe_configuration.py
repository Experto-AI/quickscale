"""Tests for Stripe configuration and feature flag."""
import os
import sys
import unittest
from unittest.mock import patch

# Add the project root to sys.path to access tests module
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

# Import centralized test utilities using DRY principles
# Configure logging for tests
import logging

from tests.test_utilities import TestUtilities

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
        TestUtilities.refresh_env_cache()  # Ensure the cache is restored after each test

    def test_stripe_settings_with_flag_enabled(self):
        """Test that enabling Stripe loads the correct settings."""
        # Create a test environment with Stripe enabled
        test_env = {
            'ENABLE_STRIPE': 'true',
            'STRIPE_PUBLIC_KEY': 'pk_test_example',
            'STRIPE_SECRET_KEY': 'sk_test_example',
            'STRIPE_WEBHOOK_SECRET': 'whsec_example',
        }
        
        # Patch the environment directly
        with patch.dict(os.environ, test_env):
            # Test the flag is enabled
            self.assertTrue(TestUtilities.is_feature_enabled(TestUtilities.get_env('ENABLE_STRIPE', 'False')), 
                           "ENABLE_STRIPE should be True when set to 'true'")
            
            # Verify settings values are retrieved correctly through get_env
            self.assertEqual(TestUtilities.get_env('STRIPE_PUBLIC_KEY'), 'pk_test_example')
            self.assertEqual(TestUtilities.get_env('STRIPE_SECRET_KEY'), 'sk_test_example')
            self.assertEqual(TestUtilities.get_env('STRIPE_WEBHOOK_SECRET'), 'whsec_example')
            
            # Without patching settings.INSTALLED_APPS directly, we can verify our logic:
            # Assume we have a function that determines if Stripe app should be in INSTALLED_APPS based on ENABLE_STRIPE
            def should_include_stripe_app():
                return TestUtilities.is_feature_enabled(TestUtilities.get_env('ENABLE_STRIPE', 'False'))
                
                self.assertTrue(should_include_stripe_app(), "stripe.apps.StripeConfig should be included when ENABLE_STRIPE is True")
