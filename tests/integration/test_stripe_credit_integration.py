"""Migrated from template validation tests."""

"""Tests for StripeManager sync functionality with credit amounts."""

import os
import sys
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase, override_settings

# Set up template path and Django settings
from ..django_functionality.base import DjangoIntegrationTestCase, setup_django_template_path, setup_core_env_utils_mock, setup_django_settings
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()

from stripe_manager.stripe_manager import StripeManager


class MockStripeProduct:
    """Mock Django model for testing credit amount sync."""
    
    def __init__(self):
        self.id = 1
        self.name = "Test Product"
        self.description = "Test Description"
        self.active = True
        self.price = 10.0
        self.currency = "usd"
        self.interval = "month"
        self.credit_amount = 1000  # Default value that should be overridden
        self.metadata = {}
        self.stripe_id = None
        self.stripe_price_id = None
        self.display_order = 0
        
    def save(self):
        """Mock save method."""
        pass


class MockDoesNotExist(Exception):
    """Mock DoesNotExist exception."""
    pass


# Create a proper mock for the Django model
def create_mock_model(return_instance=None):
    """Create a properly mocked Django model class.
    
    Args:
        return_instance: If provided, will be returned by the model constructor
    """
    # Define a mock objects manager that properly handles kwargs
    class MockManager:
        @staticmethod
        def get(**kwargs):
            """Mock get method that raises DoesNotExist."""
            raise MockDoesNotExist()
    
    # Create a mock model class that creates a new instance when called
    class MockModel:
        objects = MockManager()
        DoesNotExist = MockDoesNotExist
        
        def __new__(cls, **kwargs):
            """Return a new instance of MockStripeProduct."""
            if return_instance:
                return return_instance
            return MockStripeProduct()
    
    return MockModel


@override_settings(
    STRIPE_ENABLED=True,
    STRIPE_LIVE_MODE=False,
    STRIPE_SECRET_KEY='sk_test_123',
    STRIPE_PUBLIC_KEY='pk_test_123',
    STRIPE_WEBHOOK_SECRET='whsec_test_123'
)
class TestStripeCreditSync(TestCase):
    """Test credit amount synchronization from Stripe metadata."""
    
    def setUp(self):
        """Set up test environment."""
        # Reset StripeManager singleton state
        StripeManager._instance = None
        StripeManager._initialized = False
        
        # Don't initialize the manager in setUp - let each test do it with proper mocks
    
    @patch.dict(os.environ, {'STRIPE_ENABLED': 'true'})
    @patch('stripe_manager.stripe_manager.is_feature_enabled', return_value=True)
    @patch('stripe.StripeClient')
    def test_sync_product_from_stripe_reads_credit_amount_from_metadata(self, mock_stripe_client, mock_is_feature_enabled):
        """Test that sync_product_from_stripe correctly reads credit amount from Stripe metadata."""
        # Mock the Stripe client
        stripe_mock = MagicMock()
        mock_stripe_client.return_value = stripe_mock
        
        # Initialize the manager
        manager = StripeManager.get_instance()
        
        # Mock Stripe product data with credit amount in metadata
        stripe_product_data = {
            'id': 'prod_test123',
            'name': 'Premium Credits',
            'description': 'Premium credit package',
            'active': True,
            'metadata': {
                'credit_amount': '2500'  # This should override the default 1000
            },
            'default_price': 'price_test123'
        }
        
        # Mock Stripe price data
        stripe_price_data = {
            'id': 'price_test123',
            'unit_amount': 2500,  # $25.00
            'currency': 'usd',
            'recurring': {
                'interval': 'month'
            }
        }
        
        # Mock environment variables to enable Stripe
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            # Mock the retrieve_product method to return our test data
            with patch.object(manager, 'retrieve_product', return_value=stripe_product_data):
                # Mock the price retrieval
                stripe_mock.prices.retrieve.return_value = stripe_price_data
                
                # Create a mock product model
                product_model = create_mock_model()
                
                # Execute the sync
                result = manager.sync_product_from_stripe('prod_test123', product_model)
                
                # Verify the credit amount was read from metadata
                self.assertIsNotNone(result)
                self.assertEqual(result.credit_amount, 2500)  # Should be set from metadata, not default 1000
                self.assertEqual(result.name, 'Premium Credits')
                self.assertEqual(result.metadata, {'credit_amount': '2500'})

    @patch.dict(os.environ, {'STRIPE_ENABLED': 'true'})
    @patch('stripe_manager.stripe_manager.is_feature_enabled', return_value=True)
    @patch('stripe.StripeClient')
    def test_sync_product_from_stripe_different_metadata_keys(self, mock_stripe_client, mock_is_feature_enabled):
        """Test that sync_product_from_stripe handles different metadata key naming patterns."""
        # Mock the Stripe client
        stripe_mock = MagicMock()
        mock_stripe_client.return_value = stripe_mock
        
        # Initialize the manager
        manager = StripeManager.get_instance()
        
        # Test different metadata key formats



    @patch.dict(os.environ, {'STRIPE_ENABLED': 'true'})
    @patch('stripe_manager.stripe_manager.is_feature_enabled', return_value=True)
    @patch('stripe.StripeClient')
    def test_sync_product_from_stripe_no_metadata(self, mock_stripe_client, mock_is_feature_enabled):
        """Test that sync_product_from_stripe uses default credit amount when no metadata."""
        # Mock the Stripe client
        stripe_mock = MagicMock()
        mock_stripe_client.return_value = stripe_mock
        
        # Initialize the manager
        manager = StripeManager.get_instance()
        
        # Test with no metadata
