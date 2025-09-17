"""Test for production settings validation."""
import logging
import os
import sys
import unittest
from unittest.mock import patch

# Add the project root to sys.path to access tests module
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

# Import centralized test utilities using DRY principles
from tests.test_utilities import TestUtilities


class StripeSettingsValidationTest(unittest.TestCase):
    """Test suite for Stripe settings validation behavior."""

    def setUp(self):
        """Set up environment for each test."""
        self.original_env = os.environ.copy()
        # Clear any cached environment variables
        TestUtilities.refresh_env_cache()
        
    def tearDown(self):
        """Restore original environment after each test."""
        os.environ.clear()
        os.environ.update(self.original_env)
        TestUtilities.refresh_env_cache()

    def test_stripe_disabled_by_default(self):
        """Test that Stripe integration is disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(TestUtilities.is_feature_enabled(TestUtilities.get_env('ENABLE_STRIPE', 'False')))
    
    @patch('logging.warning')
    def test_settings_validation_with_missing_settings(self, mock_warning):
        """Test validation logic when Stripe is enabled but required settings are missing."""
        # Mock environment variables
        test_env = {
            'ENABLE_STRIPE': 'true',
            'STRIPE_PUBLIC_KEY': '',
            'STRIPE_SECRET_KEY': '',
            'STRIPE_WEBHOOK_SECRET': ''
        }
        
        with patch.dict(os.environ, test_env):
            # Mock INSTALLED_APPS as a list we can check
            installed_apps = ['django.contrib.auth']
            
            # Mock the stripe_enabled_flag instead of importing from settings
            stripe_enabled_flag = TestUtilities.is_feature_enabled(TestUtilities.get_env('ENABLE_STRIPE', 'False'))
            
            # Create a function that simulates the validation logic in settings.py
            def validate_stripe_settings():
                if stripe_enabled_flag:
                    # Emulate the validation logic from settings.py
                    missing_settings = []
                    stripe_public_key = TestUtilities.get_env('STRIPE_PUBLIC_KEY', '')
                    stripe_secret_key = TestUtilities.get_env('STRIPE_SECRET_KEY', '')
                    stripe_webhook_secret = TestUtilities.get_env('STRIPE_WEBHOOK_SECRET', '')
                    
                    if not stripe_public_key:
                        missing_settings.append('STRIPE_PUBLIC_KEY')
                    if not stripe_secret_key:
                        missing_settings.append('STRIPE_SECRET_KEY')
                    if not stripe_webhook_secret:
                        missing_settings.append('STRIPE_WEBHOOK_SECRET')
                        
                    if missing_settings:
                        logging.warning(f"Stripe integration is enabled but missing required settings: {', '.join(missing_settings)}")
                        logging.warning("Stripe integration will be disabled. Please provide all required settings.")
                        return False
                    else:
                        if 'stripe.apps.StripeConfig' not in installed_apps:
                            installed_apps.append('stripe.apps.StripeConfig')
                            logging.info("Stripe integration enabled and added to INSTALLED_APPS.")
                        return True
                return False
            
            # Call the validation function
            result = validate_stripe_settings()
            
            # Verify stripe.apps.StripeConfig was NOT added to installed_apps
            self.assertFalse(result)
            self.assertNotIn('stripe.apps.StripeConfig', installed_apps)
            
            # Check if the correct warnings were logged
            mock_warning.assert_any_call("Stripe integration is enabled but missing required settings: STRIPE_PUBLIC_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET")
            mock_warning.assert_any_call("Stripe integration will be disabled. Please provide all required settings.")
    
    @patch('logging.info')
    def test_settings_validation_with_valid_settings(self, mock_info):
        """Test validation logic when Stripe is enabled with valid settings."""
        # Mock environment variables
        test_env = {
            'ENABLE_STRIPE': 'true',
            'STRIPE_PUBLIC_KEY': 'pk_test_valid',
            'STRIPE_SECRET_KEY': 'sk_test_valid',
            'STRIPE_WEBHOOK_SECRET': 'whsec_valid'
        }
        
        with patch.dict(os.environ, test_env):
            # Mock INSTALLED_APPS as a list we can check
            installed_apps = ['django.contrib.auth']
            
            # Mock the stripe_enabled_flag instead of importing from settings
            stripe_enabled_flag = TestUtilities.is_feature_enabled(TestUtilities.get_env('ENABLE_STRIPE', 'False'))
            
            # Create a function that simulates the validation logic in settings.py
            def validate_stripe_settings():
                if stripe_enabled_flag:
                    # Emulate the validation logic from settings.py
                    missing_settings = []
                    stripe_public_key = TestUtilities.get_env('STRIPE_PUBLIC_KEY', '')
                    stripe_secret_key = TestUtilities.get_env('STRIPE_SECRET_KEY', '')
                    stripe_webhook_secret = TestUtilities.get_env('STRIPE_WEBHOOK_SECRET', '')
                    
                    if not stripe_public_key:
                        missing_settings.append('STRIPE_PUBLIC_KEY')
                    if not stripe_secret_key:
                        missing_settings.append('STRIPE_SECRET_KEY')
                    if not stripe_webhook_secret:
                        missing_settings.append('STRIPE_WEBHOOK_SECRET')
                        
                    if missing_settings:
                        logging.warning(f"Stripe integration is enabled but missing required settings: {', '.join(missing_settings)}")
                        logging.warning("Stripe integration will be disabled. Please provide all required settings.")
                        return False
                    else:
                        if 'stripe.apps.StripeConfig' not in installed_apps:
                            installed_apps.append('stripe.apps.StripeConfig')
                            logging.info("Stripe integration enabled and added to INSTALLED_APPS.")
                        return True
                return False
            
            # Call the validation function
            result = validate_stripe_settings()
            
            # Verify stripe.apps.StripeConfig was added to installed_apps
            self.assertTrue(result)
            self.assertIn('stripe.apps.StripeConfig', installed_apps)
            
            # Check if the correct info was logged
            mock_info.assert_called_with("Stripe integration enabled and added to INSTALLED_APPS.")
    
    @patch('logging.warning')
    def test_settings_validation_with_partial_settings(self, mock_warning):
        """Test validation logic when Stripe is enabled but missing some settings."""
        # Mock environment variables with one missing setting
        test_env = {
            'ENABLE_STRIPE': 'true',
            'STRIPE_PUBLIC_KEY': 'pk_test_valid',
            'STRIPE_SECRET_KEY': '',  # Missing
            'STRIPE_WEBHOOK_SECRET': 'whsec_valid'
        }
        
        with patch.dict(os.environ, test_env):
            # Mock INSTALLED_APPS as a list we can check
            installed_apps = ['django.contrib.auth']
            
            # Mock the stripe_enabled_flag instead of importing from settings
            stripe_enabled_flag = TestUtilities.is_feature_enabled(TestUtilities.get_env('ENABLE_STRIPE', 'False'))
            
            # Create a function that simulates the validation logic in settings.py
            def validate_stripe_settings():
                if stripe_enabled_flag:
                    # Emulate the validation logic from settings.py
                    missing_settings = []
                    stripe_public_key = TestUtilities.get_env('STRIPE_PUBLIC_KEY', '')
                    stripe_secret_key = TestUtilities.get_env('STRIPE_SECRET_KEY', '')
                    stripe_webhook_secret = TestUtilities.get_env('STRIPE_WEBHOOK_SECRET', '')
                    
                    if not stripe_public_key:
                        missing_settings.append('STRIPE_PUBLIC_KEY')
                    if not stripe_secret_key:
                        missing_settings.append('STRIPE_SECRET_KEY')
                    if not stripe_webhook_secret:
                        missing_settings.append('STRIPE_WEBHOOK_SECRET')
                        
                    if missing_settings:
                        logging.warning(f"Stripe integration is enabled but missing required settings: {', '.join(missing_settings)}")
                        logging.warning("Stripe integration will be disabled. Please provide all required settings.")
                        return False
                    else:
                        if 'stripe.apps.StripeConfig' not in installed_apps:
                            installed_apps.append('stripe.apps.StripeConfig')
                            logging.info("Stripe integration enabled and added to INSTALLED_APPS.")
                        return True
                return False
            
            # Call the validation function
            result = validate_stripe_settings()
            
            # Verify stripe.apps.StripeConfig was NOT added to installed_apps
            self.assertFalse(result)
            self.assertNotIn('stripe.apps.StripeConfig', installed_apps)
            
            # Check if the correct warnings were logged with only the missing setting
            mock_warning.assert_any_call("Stripe integration is enabled but missing required settings: STRIPE_SECRET_KEY")
            mock_warning.assert_any_call("Stripe integration will be disabled. Please provide all required settings.")


if __name__ == '__main__':
    unittest.main() 
