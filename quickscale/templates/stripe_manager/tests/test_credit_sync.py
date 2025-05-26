"""Tests for StripeManager sync functionality with credit amounts."""

import os
import sys
from unittest.mock import patch, MagicMock, PropertyMock

# Configure Django settings first
from django.conf import settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        USE_TZ=True,
        SECRET_KEY="test-key",
        STRIPE_SECRET_KEY="sk_test_123",
        STRIPE_PUBLIC_KEY="pk_test_123",
        STRIPE_WEBHOOK_SECRET="whsec_test_123",
        STRIPE_ENABLED=True,
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sites",
        ],
        SITE_ID=1,
        MIDDLEWARE_CLASSES=(),
    )

# Initialize Django
import django
django.setup()

# Import mock_env_utils before importing StripeManager
from quickscale.templates.stripe_manager.tests.mock_env_utils import get_env, is_feature_enabled

# Create a mock for 'core.env_utils' module
mock_env_utils = MagicMock()
mock_env_utils.get_env = get_env
mock_env_utils.is_feature_enabled = is_feature_enabled
sys.modules['core.env_utils'] = mock_env_utils

from django.test import TestCase
from quickscale.templates.stripe_manager.stripe_manager import StripeManager


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


class TestStripeCreditSync(TestCase):
    """Test credit amount synchronization from Stripe metadata."""
    
    def setUp(self):
        """Set up test environment."""
        # Reset StripeManager singleton state
        StripeManager._instance = None
        StripeManager._initialized = False
        
        # Set up environment for StripeManager
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            # Mock the Stripe client
            self.stripe_mock = MagicMock()
            
            with patch('stripe.StripeClient', return_value=self.stripe_mock):
                self.manager = StripeManager.get_instance()
                
    def test_sync_product_from_stripe_reads_credit_amount_from_metadata(self):
        """Test that sync_product_from_stripe correctly reads credit amount from Stripe metadata."""
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
            with patch.object(self.manager, 'retrieve_product', return_value=stripe_product_data):
                # Mock the price retrieval
                self.stripe_mock.prices.retrieve.return_value = stripe_price_data
                
                # Create a mock product model
                product_model = create_mock_model()
                
                # Execute the sync
                result = self.manager.sync_product_from_stripe('prod_test123', product_model)
                
                # Verify the credit amount was read from metadata
                self.assertIsNotNone(result)
                self.assertEqual(result.credit_amount, 2500)  # Should be set from metadata, not default 1000
                self.assertEqual(result.name, 'Premium Credits')
                self.assertEqual(result.metadata, {'credit_amount': '2500'})

    def test_sync_product_from_stripe_different_metadata_keys(self):
        """Test that sync supports different metadata keys for credit amounts."""
        test_cases = [
            ('credits', '1500'),
            ('credit_count', '3000'),
            ('credits_included', '500'),
        ]
        
        for metadata_key, expected_credits in test_cases:
            with self.subTest(metadata_key=metadata_key):
                stripe_product_data = {
                    'id': f'prod_test_{metadata_key}',
                    'name': f'Test Product {metadata_key}',
                    'description': 'Test Description',
                    'active': True,
                    'metadata': {
                        metadata_key: expected_credits
                    },
                    'default_price': 'price_test123'
                }
                
                stripe_price_data = {
                    'id': 'price_test123',
                    'unit_amount': 1000,
                    'currency': 'usd',
                    'recurring': {'interval': 'month'}
                }
                
                # Mock environment variables to enable Stripe
                with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
                    with patch.object(self.manager, 'retrieve_product', return_value=stripe_product_data):
                        self.stripe_mock.prices.retrieve.return_value = stripe_price_data
                        
                        product_model = create_mock_model()
                        
                        result = self.manager.sync_product_from_stripe(f'prod_test_{metadata_key}', product_model)
                        
                        self.assertIsNotNone(result)
                        self.assertEqual(result.credit_amount, int(expected_credits))

    def test_sync_product_from_stripe_invalid_credit_amount(self):
        """Test that invalid credit amounts are handled gracefully."""
        stripe_product_data = {
            'id': 'prod_test_invalid',
            'name': 'Invalid Credits',
            'description': 'Test Description',
            'active': True,
            'metadata': {
                'credit_amount': 'invalid_number'  # Invalid value
            },
            'default_price': 'price_test123'
        }
        
        stripe_price_data = {
            'id': 'price_test123',
            'unit_amount': 1000,
            'currency': 'usd',
            'recurring': {'interval': 'month'}
        }
        
        # Mock environment variables to enable Stripe
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch.object(self.manager, 'retrieve_product', return_value=stripe_product_data):
                self.stripe_mock.prices.retrieve.return_value = stripe_price_data
                
                product_model = create_mock_model()
                
                result = self.manager.sync_product_from_stripe('prod_test_invalid', product_model)
                
                # Should not crash and should keep default credit amount
                self.assertIsNotNone(result)
                self.assertEqual(result.credit_amount, 1000)  # Default value unchanged

    def test_sync_product_from_stripe_no_metadata(self):
        """Test that products without metadata don't crash."""
        stripe_product_data = {
            'id': 'prod_test_no_metadata',
            'name': 'No Metadata Product',
            'description': 'Test Description',
            'active': True,
            # No metadata field
            'default_price': 'price_test123'
        }
        
        stripe_price_data = {
            'id': 'price_test123',
            'unit_amount': 1000,
            'currency': 'usd',
            'recurring': {'interval': 'month'}
        }
        
        # Mock environment variables to enable Stripe
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch.object(self.manager, 'retrieve_product', return_value=stripe_product_data):
                self.stripe_mock.prices.retrieve.return_value = stripe_price_data
                
                product_model = create_mock_model()
                
                result = self.manager.sync_product_from_stripe('prod_test_no_metadata', product_model)
                
                # Should not crash and should keep default credit amount
                self.assertIsNotNone(result)
                self.assertEqual(result.credit_amount, 1000)  # Default value unchanged

    def test_sync_product_to_stripe_includes_credit_amount_in_metadata(self):
        """Test that sync_product_to_stripe includes credit amount in product metadata."""
        # Create a product with custom credit amount
        product = MockStripeProduct()
        product.credit_amount = 3500  # Custom credit amount different from default
        
        # Mock environment variables to enable Stripe
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            # Mock the Stripe client methods
            # Mock product.create call
            mock_product = MagicMock()
            mock_product.id = 'prod_test_new'
            self.stripe_mock.products.create.return_value = mock_product
            
            # Mock price.create call
            mock_price = MagicMock()
            mock_price.id = 'price_test_new'
            self.stripe_mock.prices.create.return_value = mock_price
            
            # Call the sync method
            result = self.manager.sync_product_to_stripe(product)
            
            # Verify results
            self.assertIsNotNone(result)
            self.assertEqual(result, ('prod_test_new', 'price_test_new'))
            
            # Verify that product.create was called with credit_amount in metadata
            product_data_arg = self.stripe_mock.products.create.call_args[1]['params']
            self.assertIn('metadata', product_data_arg)
            self.assertIn('credit_amount', product_data_arg['metadata'])
            self.assertEqual(product_data_arg['metadata']['credit_amount'], '3500')
