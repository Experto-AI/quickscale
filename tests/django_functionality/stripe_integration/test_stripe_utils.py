"""Tests for Stripe manager utility classes."""

import pytest
import os
from unittest.mock import patch, MagicMock
from decimal import Decimal

# Set up Django for testing
from ..base import DjangoModelTestCase, setup_django_template_path, setup_core_env_utils_mock, setup_core_configuration_mock, setup_django_settings

# Set up template path and environment
setup_django_template_path()
setup_core_env_utils_mock()
setup_core_configuration_mock()
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
            'ENABLE_STRIPE': 'true',
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
    @patch('stripe_manager.stripe_manager.config')
    def test_stripe_manager_initialization_with_valid_config(self, mock_config, mock_stripe_client):
        """Test StripeManager initializes correctly with valid configuration."""
        # Mock the configuration
        mock_config.is_stripe_enabled_and_configured.return_value = True
        mock_config.get_env_bool.return_value = True
        mock_config.stripe.secret_key = 'sk_test_123'
        
        # Mock the StripeClient to prevent real API calls
        mock_client_instance = MagicMock()
        mock_stripe_client.return_value = mock_client_instance
        
        manager = StripeManager.get_instance()
        
        self.assertIsNotNone(manager)
        self.assertIsInstance(manager, StripeManager)
        self.assertTrue(StripeManager._initialized)
    
    @patch('stripe.StripeClient')
    @patch('stripe_manager.stripe_manager.config')
    def test_stripe_manager_singleton_behavior(self, mock_config, mock_stripe_client):
        """Test that StripeManager follows singleton pattern."""
        # Mock the configuration
        mock_config.is_stripe_enabled_and_configured.return_value = True
        mock_config.get_env_bool.return_value = True
        mock_config.stripe.secret_key = 'sk_test_123'
        
        # Mock the StripeClient to prevent real API calls
        mock_client_instance = MagicMock()
        mock_stripe_client.return_value = mock_client_instance
        
        manager1 = StripeManager.get_instance()
        manager2 = StripeManager.get_instance()
        
        self.assertIs(manager1, manager2)
    
    @patch('stripe_manager.stripe_manager.config')
    def test_stripe_disabled_raises_error(self, mock_config):
        """Test that StripeManager raises error when Stripe is disabled."""
        # Reset singleton state
        StripeManager._instance = None
        StripeManager._initialized = False
        
        # Mock config to indicate Stripe is disabled
        mock_config.is_stripe_enabled_and_configured.return_value = False
        
        with self.assertRaises(StripeConfigurationError):
            StripeManager.get_instance()
    
    @patch('stripe_manager.stripe_manager.config')
    def test_missing_api_key_raises_error(self, mock_config):
        """Test that StripeManager raises error when API key is missing."""
        # Reset singleton state
        StripeManager._instance = None
        StripeManager._initialized = False
        
        # Mock config to indicate Stripe is enabled but API key is missing
        mock_config.is_stripe_enabled_and_configured.return_value = False
        
        with self.assertRaises(StripeConfigurationError):
            StripeManager.get_instance()
    

if __name__ == '__main__':
    unittest.main()
