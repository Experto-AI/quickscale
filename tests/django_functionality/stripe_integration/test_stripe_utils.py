"""Tests for Stripe manager utility classes."""

import pytest
import os
from unittest.mock import patch, MagicMock
from decimal import Decimal

# Set up Django for testing
from ..base import DjangoModelTestCase, setup_django_template_path, setup_core_env_utils_mock, setup_django_settings

# Set up template path and environment
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()

# Import Django and initialize
import django
django.setup()

# Import the modules we're testing
from stripe_manager.stripe_manager import StripeManager, StripeConfigurationError


@pytest.mark.django_component
@pytest.mark.unit
class StripeManagerTests(DjangoModelTestCase):
    """Unit tests for StripeManager utility class."""
    
    def setUp(self):
        """Set up test environment."""
        # Reset StripeManager singleton state for each test
        StripeManager._instance = None
        StripeManager._initialized = False
        
        # Patch environment settings
        self.env_patcher = patch.dict(os.environ, {
            'STRIPE_ENABLED': 'true',
            'STRIPE_SECRET_KEY': 'sk_test_123',
            'STRIPE_PUBLIC_KEY': 'pk_test_123',
            'STRIPE_WEBHOOK_SECRET': 'whsec_test_123'
        })
        self.env_patcher.start()
        
    def tearDown(self):
        """Clean up after each test."""
        self.env_patcher.stop()
        # Reset StripeManager singleton state
        StripeManager._instance = None
        StripeManager._initialized = False
    
    @patch('stripe.StripeClient')
    @patch('stripe_manager.stripe_manager.is_feature_enabled')
    @patch('stripe_manager.stripe_manager.get_env')
    def test_stripe_manager_initialization_with_valid_config(self, mock_get_env, mock_is_feature_enabled, mock_stripe_client):
        """Test StripeManager initializes correctly with valid configuration."""
        # Mock the environment functions to return the expected values
        mock_is_feature_enabled.return_value = True
        mock_get_env.return_value = 'true'  # For STRIPE_ENABLED check
        
        # Mock the StripeClient to prevent real API calls
        mock_client_instance = MagicMock()
        mock_stripe_client.return_value = mock_client_instance
        
        # Use override_settings to set Django settings
        from django.test import override_settings
        with override_settings(STRIPE_SECRET_KEY="sk_test_123"):
            manager = StripeManager.get_instance()
            
            self.assertIsNotNone(manager)
            self.assertIsInstance(manager, StripeManager)
            self.assertTrue(StripeManager._initialized)
    
    @patch('stripe.StripeClient')
    @patch('stripe_manager.stripe_manager.is_feature_enabled')
    @patch('stripe_manager.stripe_manager.get_env')
    def test_stripe_manager_singleton_behavior(self, mock_get_env, mock_is_feature_enabled, mock_stripe_client):
        """Test that StripeManager follows singleton pattern."""
        # Mock the environment functions to return the expected values
        mock_is_feature_enabled.return_value = True
        mock_get_env.return_value = 'true'  # For STRIPE_ENABLED check
        
        # Mock the StripeClient to prevent real API calls
        mock_client_instance = MagicMock()
        mock_stripe_client.return_value = mock_client_instance
        
        # Use override_settings to set Django settings
        from django.test import override_settings
        with override_settings(STRIPE_SECRET_KEY="sk_test_123"):
            manager1 = StripeManager.get_instance()
            manager2 = StripeManager.get_instance()
            
            self.assertIs(manager1, manager2)
    
    def test_stripe_disabled_raises_error(self):
        """Test that StripeManager raises error when Stripe is disabled."""
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'false'}):
            # Reset singleton state
            StripeManager._instance = None
            StripeManager._initialized = False
            
            with self.assertRaises(StripeConfigurationError):
                StripeManager.get_instance()
    
    @patch('django.conf.settings.STRIPE_SECRET_KEY', '')
    def test_missing_api_key_raises_error(self):
        """Test that StripeManager raises error when API key is missing."""
        # Reset singleton state
        StripeManager._instance = None
        StripeManager._initialized = False
        
        with self.assertRaises(StripeConfigurationError):
            StripeManager.get_instance()
    

if __name__ == '__main__':
    unittest.main()
