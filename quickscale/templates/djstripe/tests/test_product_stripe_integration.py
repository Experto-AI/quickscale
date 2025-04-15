"""
Tests for Stripe product integration.

These tests verify that products sync correctly with Stripe.
"""

import os
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.urls import reverse
from ..models import Product
from ..services import ProductService
from ..utils import MockStripeObject


@override_settings(STRIPE_TEST_MODE=True)
class ProductStripeIntegrationTest(TestCase):
    """Test the integration between Product model and Stripe."""
    
    def setUp(self):
        """Set up test case with environment variables and mocks."""
        # Set up environment variables for test
        self.env_patcher = patch.dict(os.environ, {
            'STRIPE_ENABLED': 'true',
            'STRIPE_TEST_MODE': 'true'
        })
        self.env_patcher.start()
        
        # Create a mock stripe product response
        self.stripe_product_id = 'prod_mock12345'
        self.stripe_price_id = 'price_mock12345'
        
        self.mock_product = MockStripeObject({
            'id': self.stripe_product_id,
            'name': 'Test Product from Stripe',
            'description': 'This is a test product from Stripe',
            'active': True,
            'metadata': {'key': 'value'}
        })
        
        self.mock_price = MockStripeObject({
            'id': self.stripe_price_id,
            'product': self.stripe_product_id,
            'unit_amount': 2999,  # $29.99
            'currency': 'usd',
            'active': True,
            'metadata': {}
        })
        
        # Create mock stripe API methods
        self.stripe_mock = MagicMock()
        self.stripe_mock.Product.create.return_value = self.mock_product
        self.stripe_mock.Product.modify.return_value = self.mock_product
        self.stripe_mock.Product.retrieve.return_value = self.mock_product
        
        self.stripe_mock.Price.create.return_value = self.mock_price
        self.stripe_mock.Price.retrieve.return_value = self.mock_price
        self.stripe_mock.Price.list.return_value = MockStripeObject({
            'data': [self.mock_price],
            'has_more': False
        })
        
        # Mock the get_stripe function
        self.stripe_patcher = patch('djstripe.utils.get_stripe', return_value=self.stripe_mock)
        self.get_stripe_mock = self.stripe_patcher.start()
        
        # Mock Django settings
        self.settings_patcher = patch('django.conf.settings')
        self.settings_mock = self.settings_patcher.start()
        self.settings_mock.STRIPE_SECRET_KEY = 'sk_test_mock'
        self.settings_mock.DJSTRIPE_WEBHOOK_SECRET = 'whsec_mock'
        
        # Create a test product
        self.product = Product.objects.create(
            name='Test Product',
            description='This is a test product',
            base_price=Decimal('29.99'),
            currency='USD',
            status=Product.ACTIVE
        )
    
    def tearDown(self):
        """Clean up patchers."""
        self.env_patcher.stop()
        self.stripe_patcher.stop()
        self.settings_patcher.stop()
    
    def test_create_in_stripe(self):
        """Test creating a product in Stripe."""
        # Test the service method
        stripe_id = ProductService.create_in_stripe(self.product)
        
        # Check that the mock was called correctly
        self.stripe_mock.Product.create.assert_called_once()
        self.stripe_mock.Price.create.assert_called_once()
        
        # Check that the product was updated with the Stripe IDs
        self.product.refresh_from_db()
        self.assertEqual(self.product.stripe_product_id, self.stripe_product_id)
        self.assertEqual(self.product.metadata.get('stripe_price_id'), self.stripe_price_id)
        
        # Check the return value
        self.assertEqual(stripe_id, self.stripe_product_id)
    
    def test_update_in_stripe(self):
        """Test updating a product in Stripe."""
        # First, set a Stripe ID on the product
        self.product.stripe_product_id = self.stripe_product_id
        self.product.save()
        
        # Update some fields
        self.product.name = 'Updated Product'
        self.product.base_price = Decimal('39.99')
        
        # Test the service method
        result = ProductService.update_in_stripe(self.product)
        
        # Check that the mock was called correctly
        self.stripe_mock.Product.modify.assert_called_once()
        
        # Check that a new price was created (since prices can't be updated)
        self.stripe_mock.Price.create.assert_called_once()
        
        # Check the return value
        self.assertTrue(result)
    
    def test_sync_from_stripe(self):
        """Test syncing a product from Stripe to the local database."""
        # Test the service method
        product = ProductService.sync_from_stripe(self.stripe_product_id)
        
        # Check that the mock was called correctly
        self.stripe_mock.Product.retrieve.assert_called_once_with(self.stripe_product_id)
        self.stripe_mock.Price.list.assert_called_once()
        
        # Check that the product was created with the correct data
        self.assertIsNotNone(product)
        self.assertEqual(product.name, 'Test Product from Stripe')
        self.assertEqual(product.description, 'This is a test product from Stripe')
        self.assertEqual(product.status, Product.ACTIVE)
        self.assertEqual(product.base_price, Decimal('29.99'))
        self.assertEqual(product.currency, 'USD')
        self.assertEqual(product.stripe_product_id, self.stripe_product_id)
        self.assertEqual(product.metadata.get('stripe_price_id'), self.stripe_price_id)
    
    def test_delete_from_stripe(self):
        """Test deleting (archiving) a product in Stripe."""
        # First, set a Stripe ID on the product
        self.product.stripe_product_id = self.stripe_product_id
        self.product.save()
        
        # Test the service method
        result = ProductService.delete_from_stripe(self.product)
        
        # Check that the mock was called correctly to archive the product
        self.stripe_mock.Product.modify.assert_called_once_with(
            self.stripe_product_id,
            active=False
        )
        
        # Check the return value
        self.assertTrue(result)
    
    def test_sync_all_to_stripe(self):
        """Test syncing all products to Stripe."""
        # Create another product without a Stripe ID
        Product.objects.create(
            name='Another Product',
            base_price=Decimal('19.99'),
            currency='USD',
            status=Product.ACTIVE
        )
        
        # Create an inactive product that shouldn't be synced
        Product.objects.create(
            name='Inactive Product',
            base_price=Decimal('9.99'),
            currency='USD',
            status=Product.INACTIVE
        )
        
        # First, set a Stripe ID on the original product
        self.product.stripe_product_id = self.stripe_product_id
        self.product.save()
        
        # Test the service method
        created, updated, failed = ProductService.sync_all_to_stripe()
        
        # Should have created 1 product, updated 1 product
        self.assertEqual(created, 1)
        self.assertEqual(updated, 1)
        self.assertEqual(failed, 0)
    
    @patch('threading.Thread')
    def test_product_save_signal(self, mock_thread):
        """Test that saving a product triggers the sync signal."""
        # Create a new product (should trigger create in Stripe)
        product = Product.objects.create(
            name='Signal Test Product',
            base_price=Decimal('49.99'),
            currency='USD',
            status=Product.ACTIVE
        )
        
        # Check that a thread was started to sync the product
        mock_thread.assert_called()
        mock_thread.return_value.start.assert_called_once()
        
        # Update the product (should trigger update in Stripe)
        product.stripe_product_id = 'prod_mock67890'
        product.name = 'Updated Signal Test Product'
        product.save()
        
        # Check that another thread was started to update the product
        self.assertEqual(mock_thread.call_count, 2)
    
    @patch('djstripe.services.ProductService.delete_from_stripe')
    def test_product_delete_signal(self, mock_delete):
        """Test that deleting a product triggers the delete signal."""
        # First, set a Stripe ID on the product
        self.product.stripe_product_id = self.stripe_product_id
        self.product.save()
        
        # Delete the product
        self.product.delete()
        
        # Check that the delete method was called
        mock_delete.assert_called_once_with(self.product)
    
    def test_webhook_product_created(self):
        """Test handling a product.created webhook event."""
        # Create a mock webhook event
        event_data = {
            'id': 'evt_mock12345',
            'type': 'product.created',
            'data': {
                'object': {
                    'id': 'prod_mock67890',
                    'name': 'Webhook Product',
                    'description': 'Created via webhook',
                    'active': True,
                    'metadata': {}
                }
            }
        }
        
        # Mock the webhook verification
        with patch('stripe.Webhook.construct_event', return_value=event_data):
            # Mock the request object
            request = self.client.post(
                reverse('djstripe:webhook'),
                data=json.dumps(event_data),
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='mock_signature'
            )
            
            # Check that a product was created with the webhook data
            self.assertEqual(request.status_code, 200)
            
            # A real integration test would check the database here
            # Since we mocked the entire webhook flow, we can check
            # that the service was called correctly
            self.stripe_mock.Product.retrieve.assert_called()
    
    def test_sync_to_stripe_method(self):
        """Test the sync_to_stripe method on the Product model."""
        # Test without a Stripe ID (should create)
        result = self.product.sync_to_stripe()
        self.assertTrue(result)
        self.stripe_mock.Product.create.assert_called_once()
        
        # Reset mock and set a Stripe ID
        self.stripe_mock.reset_mock()
        self.product.stripe_product_id = self.stripe_product_id
        self.product.save()
        
        # Test with a Stripe ID (should update)
        result = self.product.sync_to_stripe()
        self.assertTrue(result)
        self.stripe_mock.Product.modify.assert_called_once()
    
    def test_delete_from_stripe_method(self):
        """Test the delete_from_stripe method on the Product model."""
        # Set a Stripe ID on the product
        self.product.stripe_product_id = self.stripe_product_id
        self.product.save()
        
        # Test the method
        result = self.product.delete_from_stripe()
        self.assertTrue(result)
        self.stripe_mock.Product.modify.assert_called_once_with(
            self.stripe_product_id,
            active=False
        ) 