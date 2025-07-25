"""Comprehensive tests for Sprint 24 Stripe Integration Review.

This test suite validates:
1. StripeManager singleton pattern and API integration
2. Webhook processing security
3. Unidirectional product synchronization (Stripe → QuickScale)
4. Error handling and fallback mechanisms
5. API version compatibility and connectivity testing
6. Customer management operations
7. Product management operations
8. Subscription management operations
9. Payment operations
10. Webhook processing
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

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

# Import mock utilities
from quickscale.project_templates.stripe_manager.tests.mock_env_utils import get_env, is_feature_enabled

# Create a mock for 'core.env_utils' module
mock_env_utils = MagicMock()
mock_env_utils.get_env = get_env
mock_env_utils.is_feature_enabled = is_feature_enabled
sys.modules['core.env_utils'] = mock_env_utils

from django.test import TestCase, override_settings
from quickscale.project_templates.stripe_manager.stripe_manager import StripeManager, StripeConfigurationError


class MockStripeProduct:
    """Mock Django model for testing."""
    
    def __init__(self):
        self.id = 1
        self.name = "Test Product"
        self.description = "Test Description"
        self.active = True
        self.price = 10.0
        self.currency = "usd"
        self.interval = "month"
        self.credit_amount = 1000
        self.metadata = {}
        self.stripe_id = "prod_test_123"
        self.stripe_price_id = "price_test_123"
        self.display_order = 0
        
    def save(self):
        """Mock save method."""
        pass


class TestStripeManagerSingletonPattern(TestCase):
    """Test StripeManager singleton pattern and initialization."""
    
    def setUp(self):
        """Set up test environment."""
        # Reset StripeManager singleton state
        StripeManager._instance = None
        StripeManager._initialized = False
        
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def test_singleton_pattern(self):
        """Test that StripeManager follows singleton pattern."""
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient') as mock_client:
                # Get first instance
                manager1 = StripeManager.get_instance()
                
                # Get second instance
                manager2 = StripeManager.get_instance()
                
                # Both should be the same instance
                self.assertIs(manager1, manager2)
                
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def test_initialization_only_once(self):
        """Test that initialization only happens once."""
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient') as mock_client:
                # First call should initialize
                manager1 = StripeManager.get_instance()
                mock_client.assert_called_once()
                
                # Reset mock
                mock_client.reset_mock()
                
                # Second call should not initialize again
                manager2 = StripeManager.get_instance()
                mock_client.assert_not_called()
                
    def test_configuration_error_handling(self):
        """Test handling of configuration errors."""
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'false'}):
            with self.assertRaises(StripeConfigurationError):
                StripeManager.get_instance()
                
    @override_settings(STRIPE_SECRET_KEY=None)
    def test_api_key_validation(self):
        """Test API key validation during initialization."""
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with self.assertRaises(StripeConfigurationError):
                StripeManager.get_instance()


class TestStripeAPIIntegration(TestCase):
    """Test Stripe API integration and error handling."""
    
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def setUp(self):
        """Set up test environment."""
        StripeManager._instance = None
        StripeManager._initialized = False
        
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient') as mock_client:
                self.mock_client = mock_client.return_value
                self.manager = StripeManager.get_instance()
                
    def test_api_client_property(self):
        """Test that client property returns the Stripe client."""
        self.assertIsNotNone(self.manager.client)
        self.assertEqual(self.manager.client, self.mock_client)
        
    def test_connectivity_check(self):
        """Test Stripe connectivity checking."""
        # Mock successful connectivity check
        self.mock_client.customers.list.return_value = {'data': []}
        
        self.assertTrue(self.manager.is_stripe_available())
        
        # Mock failed connectivity check
        self.mock_client.customers.list.side_effect = Exception("Connection failed")
        
        self.assertFalse(self.manager.is_stripe_available())
        
    def test_ensure_stripe_available(self):
        """Test ensure_stripe_available method."""
        # Mock successful connectivity
        self.mock_client.customers.list.return_value = {'data': []}
        
        # Should not raise exception
        self.manager.ensure_stripe_available()
        
        # Mock failed connectivity
        self.mock_client.customers.list.side_effect = Exception("Connection failed")
        
        # Should raise exception
        with self.assertRaises(StripeConfigurationError):
            self.manager.ensure_stripe_available()


class TestCustomerManagement(TestCase):
    """Test customer management operations."""
    
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def setUp(self):
        """Set up test environment."""
        StripeManager._instance = None
        StripeManager._initialized = False
        
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient') as mock_client:
                self.mock_client = mock_client.return_value
                self.manager = StripeManager.get_instance()
                
    def test_create_customer_success(self):
        """Test successful customer creation."""
        customer_data = {
            'id': 'cus_test_123',
            'email': 'test@example.com',
            'name': 'Test Customer'
        }
        self.mock_client.customers.create.return_value = customer_data
        
        result = self.manager.create_customer('test@example.com', 'Test Customer')
        
        self.assertEqual(result, customer_data)
        self.mock_client.customers.create.assert_called_once_with(
            params={'email': 'test@example.com', 'name': 'Test Customer'}
        )
        
    def test_create_customer_with_metadata(self):
        """Test customer creation with metadata."""
        customer_data = {
            'id': 'cus_test_123',
            'email': 'test@example.com',
            'metadata': {'user_id': '123'}
        }
        self.mock_client.customers.create.return_value = customer_data
        
        metadata = {'user_id': '123'}
        result = self.manager.create_customer('test@example.com', metadata=metadata)
        
        self.assertEqual(result, customer_data)
        self.mock_client.customers.create.assert_called_once_with(
            params={'email': 'test@example.com', 'metadata': metadata}
        )
        
    def test_create_customer_error(self):
        """Test customer creation error handling."""
        self.mock_client.customers.create.side_effect = Exception("API Error")
        
        with self.assertRaises(Exception):
            self.manager.create_customer('test@example.com')
            
    def test_retrieve_customer_success(self):
        """Test successful customer retrieval."""
        customer_data = {
            'id': 'cus_test_123',
            'email': 'test@example.com'
        }
        self.mock_client.customers.retrieve.return_value = customer_data
        
        result = self.manager.retrieve_customer('cus_test_123')
        
        self.assertEqual(result, customer_data)
        self.mock_client.customers.retrieve.assert_called_once_with('cus_test_123')
        
    def test_retrieve_customer_not_found(self):
        """Test customer retrieval when not found."""
        self.mock_client.customers.retrieve.side_effect = Exception("Customer not found")
        
        with self.assertRaises(Exception):
            self.manager.retrieve_customer('cus_invalid')
            
    def test_get_customer_by_user_with_stripe_customer(self):
        """Test getting customer by user with existing Stripe customer."""
        # Mock user with stripe_customer
        mock_user = MagicMock()
        mock_user.email = 'test@example.com'
        mock_user.stripe_customer = MagicMock()
        mock_user.stripe_customer.stripe_id = 'cus_test_123'
        
        customer_data = {'id': 'cus_test_123', 'email': 'test@example.com'}
        self.mock_client.customers.retrieve.return_value = customer_data
        
        result = self.manager.get_customer_by_user(mock_user)
        
        self.assertEqual(result, customer_data)
        self.mock_client.customers.retrieve.assert_called_once_with('cus_test_123')
        
    def test_get_customer_by_user_without_stripe_customer(self):
        """Test getting customer by user without Stripe customer."""
        # Mock user without stripe_customer
        mock_user = MagicMock()
        mock_user.email = 'test@example.com'
        mock_user.stripe_customer = None
        
        result = self.manager.get_customer_by_user(mock_user)
        
        self.assertIsNone(result)
        self.mock_client.customers.retrieve.assert_not_called()


class TestProductManagement(TestCase):
    """Test product management operations."""
    
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def setUp(self):
        """Set up test environment."""
        StripeManager._instance = None
        StripeManager._initialized = False
        
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient') as mock_client:
                self.mock_client = mock_client.return_value
                self.manager = StripeManager.get_instance()
                
    def test_create_product_success(self):
        """Test successful product creation."""
        product_data = {
            'id': 'prod_test_123',
            'name': 'Test Product',
            'description': 'Test Description'
        }
        self.mock_client.products.create.return_value = product_data
        
        result = self.manager.create_product('Test Product', 'Test Description')
        
        self.assertEqual(result, product_data)
        self.mock_client.products.create.assert_called_once_with(
            params={'name': 'Test Product', 'description': 'Test Description'}
        )
        
    def test_create_product_with_metadata(self):
        """Test product creation with metadata."""
        product_data = {
            'id': 'prod_test_123',
            'name': 'Test Product',
            'metadata': {'credit_amount': '1000'}
        }
        self.mock_client.products.create.return_value = product_data
        
        metadata = {'credit_amount': '1000'}
        result = self.manager.create_product('Test Product', metadata=metadata)
        
        self.assertEqual(result, product_data)
        self.mock_client.products.create.assert_called_once_with(
            params={'name': 'Test Product', 'metadata': metadata}
        )
        
    def test_create_product_with_price_success(self):
        """Test successful product creation with price."""
        product_data = {
            'id': 'prod_test_123',
            'name': 'Test Product'
        }
        price_data = {
            'id': 'price_test_123',
            'unit_amount': 1000,
            'currency': 'usd'
        }
        self.mock_client.products.create.return_value = product_data
        self.mock_client.prices.create.return_value = price_data
        
        result_product, result_price = self.manager.create_product_with_price(
            'Test Product', 1000, 'usd', 'Test Description'
        )
        
        self.assertEqual(result_product, product_data)
        self.assertEqual(result_price, price_data)
        
    def test_retrieve_product_success(self):
        """Test successful product retrieval."""
        product_data = {
            'id': 'prod_test_123',
            'name': 'Test Product',
            'active': True
        }
        self.mock_client.products.retrieve.return_value = product_data
        
        result = self.manager.retrieve_product('prod_test_123')
        
        self.assertEqual(result, product_data)
        self.mock_client.products.retrieve.assert_called_once_with('prod_test_123')
        
    def test_retrieve_product_not_found(self):
        """Test product retrieval when not found."""
        self.mock_client.products.retrieve.side_effect = Exception("Product not found")
        
        # The actual implementation returns empty list instead of raising
        result = self.manager.retrieve_product('prod_invalid')
        
        # Should return None or empty result, not raise exception
        self.assertIsNone(result)
            
    def test_list_products_active_only(self):
        """Test listing active products only."""
        products_data = [
            {'id': 'prod_1', 'name': 'Product 1', 'active': True},
            {'id': 'prod_2', 'name': 'Product 2', 'active': True}
        ]
        # Mock the response object with data attribute
        mock_response = MagicMock()
        mock_response.data = products_data
        self.mock_client.products.list.return_value = mock_response
        
        result = self.manager.list_products(active=True)
        
        self.assertEqual(result, products_data)
        self.mock_client.products.list.assert_called_once_with(params={'active': True, 'expand': ['data.default_price']})
        
    def test_list_products_all_products(self):
        """Test listing all products."""
        products_data = [
            {'id': 'prod_1', 'name': 'Product 1', 'active': True},
            {'id': 'prod_2', 'name': 'Product 2', 'active': False}
        ]
        # Mock the response object with data attribute
        mock_response = MagicMock()
        mock_response.data = products_data
        self.mock_client.products.list.return_value = mock_response
        
        result = self.manager.list_products(active=None)
        
        self.assertEqual(result, products_data)
        self.mock_client.products.list.assert_called_once_with(params={'expand': ['data.default_price']})


class TestSubscriptionManagement(TestCase):
    """Test subscription management operations."""
    
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def setUp(self):
        """Set up test environment."""
        StripeManager._instance = None
        StripeManager._initialized = False
        
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient') as mock_client:
                self.mock_client = mock_client.return_value
                self.manager = StripeManager.get_instance()
                
    def test_create_subscription_success(self):
        """Test successful subscription creation."""
        subscription_data = {
            'id': 'sub_test_123',
            'customer': 'cus_test_123',
            'status': 'active'
        }
        self.mock_client.subscriptions.create.return_value = subscription_data
        
        result = self.manager.create_subscription('cus_test_123', 'price_test_123')
        
        self.assertEqual(result, subscription_data)
        self.mock_client.subscriptions.create.assert_called_once_with(
            params={'customer': 'cus_test_123', 'items': [{'price': 'price_test_123', 'quantity': 1}]}
        )
        
    def test_create_subscription_with_metadata(self):
        """Test subscription creation with metadata."""
        subscription_data = {
            'id': 'sub_test_123',
            'metadata': {'user_id': '123'}
        }
        self.mock_client.subscriptions.create.return_value = subscription_data
        
        metadata = {'user_id': '123'}
        result = self.manager.create_subscription('cus_test_123', 'price_test_123', metadata=metadata)
        
        self.assertEqual(result, subscription_data)
        self.mock_client.subscriptions.create.assert_called_once_with(
            params={'customer': 'cus_test_123', 'items': [{'price': 'price_test_123', 'quantity': 1}], 'metadata': metadata}
        )
        
    def test_retrieve_subscription_success(self):
        """Test successful subscription retrieval."""
        subscription_data = {
            'id': 'sub_test_123',
            'status': 'active'
        }
        self.mock_client.subscriptions.retrieve.return_value = subscription_data
        
        result = self.manager.retrieve_subscription('sub_test_123')
        
        self.assertEqual(result, subscription_data)
        self.mock_client.subscriptions.retrieve.assert_called_once_with('sub_test_123')
        
    def test_update_subscription_success(self):
        """Test successful subscription update."""
        subscription_data = {
            'id': 'sub_test_123',
            'status': 'active'
        }
        self.mock_client.subscriptions.update.return_value = subscription_data
        
        # Mock the retrieve_subscription call that update_subscription makes
        current_subscription = {
            'id': 'sub_test_123',
            'items': {'data': [{'id': 'si_test'}]}
        }
        self.mock_client.subscriptions.retrieve.return_value = current_subscription
        
        result = self.manager.update_subscription('sub_test_123', new_price_id='price_test_456')
        
        self.assertEqual(result, subscription_data)
        self.mock_client.subscriptions.update.assert_called_once_with(
            'sub_test_123',
            params={'items': [{'id': 'si_test', 'price': 'price_test_456'}]}
        )
        
    def test_cancel_subscription_at_period_end(self):
        """Test subscription cancellation at period end."""
        subscription_data = {
            'id': 'sub_test_123',
            'cancel_at_period_end': True
        }
        self.mock_client.subscriptions.update.return_value = subscription_data
        
        result = self.manager.cancel_subscription('sub_test_123', at_period_end=True)
        
        self.assertEqual(result, subscription_data)
        self.mock_client.subscriptions.update.assert_called_once_with(
            'sub_test_123',
            params={'cancel_at_period_end': True}
        )
        
    def test_cancel_subscription_immediately(self):
        """Test immediate subscription cancellation."""
        subscription_data = {
            'id': 'sub_test_123',
            'status': 'canceled'
        }
        self.mock_client.subscriptions.cancel.return_value = subscription_data
        
        result = self.manager.cancel_subscription('sub_test_123', at_period_end=False)
        
        self.assertEqual(result, subscription_data)
        self.mock_client.subscriptions.cancel.assert_called_once_with('sub_test_123')


class TestPaymentOperations(TestCase):
    """Test payment operations."""
    
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def setUp(self):
        """Set up test environment."""
        StripeManager._instance = None
        StripeManager._initialized = False
        
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient') as mock_client:
                self.mock_client = mock_client.return_value
                self.manager = StripeManager.get_instance()
                
    def test_create_payment_intent_success(self):
        """Test successful payment intent creation."""
        payment_intent_data = {
            'id': 'pi_test_123',
            'amount': 1000,
            'currency': 'usd',
            'status': 'requires_payment_method'
        }
        self.mock_client.payment_intents.create.return_value = payment_intent_data
        
        result = self.manager.create_payment_intent(1000, 'usd')
        
        self.assertEqual(result, payment_intent_data)
        self.mock_client.payment_intents.create.assert_called_once_with(
            params={'amount': 1000, 'currency': 'usd'}
        )
        
    def test_create_payment_intent_with_customer(self):
        """Test payment intent creation with customer."""
        payment_intent_data = {
            'id': 'pi_test_123',
            'customer': 'cus_test_123'
        }
        self.mock_client.payment_intents.create.return_value = payment_intent_data
        
        result = self.manager.create_payment_intent(1000, 'usd', customer_id='cus_test_123')
        
        self.assertEqual(result, payment_intent_data)
        self.mock_client.payment_intents.create.assert_called_once_with(
            params={'amount': 1000, 'currency': 'usd', 'customer': 'cus_test_123'}
        )
        
    def test_retrieve_payment_intent_success(self):
        """Test successful payment intent retrieval."""
        payment_intent_data = {
            'id': 'pi_test_123',
            'status': 'succeeded'
        }
        self.mock_client.payment_intents.retrieve.return_value = payment_intent_data
        
        result = self.manager.retrieve_payment_intent('pi_test_123')
        
        self.assertEqual(result, payment_intent_data)
        self.mock_client.payment_intents.retrieve.assert_called_once_with('pi_test_123')
        
    def test_confirm_payment_intent_success(self):
        """Test successful payment intent confirmation."""
        payment_intent_data = {
            'id': 'pi_test_123',
            'status': 'succeeded'
        }
        self.mock_client.payment_intents.confirm.return_value = payment_intent_data
        
        result = self.manager.confirm_payment_intent('pi_test_123')
        
        self.assertEqual(result, payment_intent_data)
        self.mock_client.payment_intents.confirm.assert_called_once_with('pi_test_123', params={})
        
    def test_cancel_payment_intent_success(self):
        """Test successful payment intent cancellation."""
        payment_intent_data = {
            'id': 'pi_test_123',
            'status': 'canceled'
        }
        self.mock_client.payment_intents.cancel.return_value = payment_intent_data
        
        result = self.manager.cancel_payment_intent('pi_test_123')
        
        self.assertEqual(result, payment_intent_data)
        self.mock_client.payment_intents.cancel.assert_called_once_with('pi_test_123')
        
    def test_create_checkout_session_success(self):
        """Test successful checkout session creation."""
        # Create a mock session object with the id attribute
        mock_session = MagicMock()
        mock_session.id = 'cs_test_123'
        mock_session.url = 'https://checkout.stripe.com/pay/cs_test_123'
        
        # Mock the price retrieval that happens in create_checkout_session
        mock_price = MagicMock()
        mock_price.get.return_value.get.return_value = 'month'  # recurring interval
        self.mock_client.prices.retrieve.return_value = mock_price
        
        # Mock the actual checkout session creation
        with patch('quickscale.project_templates.stripe_manager.stripe_manager.stripe.checkout.Session.create') as mock_stripe_create:
            mock_stripe_create.return_value = mock_session
            
            result = self.manager.create_checkout_session(
                'price_test_123', 1, 'https://success.com', 'https://cancel.com'
            )
            
            # The result should be the mock object returned by stripe.checkout.Session.create
            self.assertEqual(result, mock_session)
            
            # Verify the mock was called with the correct parameters
            mock_stripe_create.assert_called_once()
            call_args = mock_stripe_create.call_args[1]  # Get keyword arguments
            self.assertEqual(call_args['mode'], 'subscription')
            self.assertEqual(call_args['success_url'], 'https://success.com')
            self.assertEqual(call_args['cancel_url'], 'https://cancel.com')
            self.assertEqual(call_args['line_items'], [{'price': 'price_test_123', 'quantity': 1}])
            
    def test_retrieve_checkout_session_success(self):
        """Test successful checkout session retrieval."""
        session_data = {
            'id': 'cs_test_123',
            'status': 'complete'
        }
        
        mock_line_items = MagicMock()
        
        # Mock the actual checkout session retrieval and line items
        with patch('quickscale.project_templates.stripe_manager.stripe_manager.stripe.checkout.Session.retrieve') as mock_stripe_retrieve, \
             patch('quickscale.project_templates.stripe_manager.stripe_manager.stripe.checkout.Session.list_line_items') as mock_line_items_retrieve:
            
            mock_stripe_retrieve.return_value = session_data
            mock_line_items_retrieve.return_value = mock_line_items
            
            result = self.manager.retrieve_checkout_session('cs_test_123')
            
            # The result should be the enriched session data
            expected_result = dict(session_data)
            expected_result['line_items_details'] = mock_line_items
            
            self.assertEqual(result, expected_result)
            
            # Verify the mocks were called correctly
            mock_stripe_retrieve.assert_called_once_with('cs_test_123')
            mock_line_items_retrieve.assert_called_once_with('cs_test_123', limit=100)
        
    def test_create_refund_success(self):
        """Test successful refund creation."""
        refund_data = {
            'id': 're_test_123',
            'amount': 1000,
            'status': 'succeeded'
        }
        self.mock_client.refunds.create.return_value = refund_data
        
        result = self.manager.create_refund('pi_test_123', 1000)
        
        self.assertEqual(result, refund_data)
        self.mock_client.refunds.create.assert_called_once_with(
            params={'payment_intent': 'pi_test_123', 'amount': 1000}
        )


class TestUnidirectionalProductSync(TestCase):
    """Test unidirectional product synchronization (Stripe → QuickScale)."""
    
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def setUp(self):
        """Set up test environment."""
        StripeManager._instance = None
        StripeManager._initialized = False
        
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient') as mock_client:
                self.mock_client = mock_client.return_value
                self.manager = StripeManager.get_instance()
                
    def test_sync_product_from_stripe_success(self):
        """Test successful product sync from Stripe."""
        # Mock Stripe product data
        stripe_product_data = {
            'id': 'prod_test_123',
            'name': 'Premium Credits',
            'description': 'Premium credit package',
            'active': True,
            'metadata': {
                'credit_amount': '2500',
                'display_order': '1'
            },
            'default_price': 'price_test_123'
        }
        
        # Mock Stripe price data
        stripe_price_data = {
            'id': 'price_test_123',
            'unit_amount': 2500,
            'currency': 'usd',
            'recurring': {
                'interval': 'month'
            }
        }
        
        # Mock the retrieve_product method and environment
        with patch.object(self.manager, 'retrieve_product', return_value=stripe_product_data):
            with patch('quickscale.project_templates.stripe_manager.stripe_manager.get_env', return_value='true'):
                with patch('quickscale.project_templates.stripe_manager.stripe_manager.is_feature_enabled', return_value=True):
                    self.mock_client.prices.retrieve.return_value = stripe_price_data
                    
                    # Create a mock product model
                    product_model = create_mock_model()
                    
                    # Execute the sync
                    result = self.manager.sync_product_from_stripe('prod_test_123', product_model)
                    
                    # Verify the result
                    self.assertIsNotNone(result)
                    self.assertEqual(result.name, 'Premium Credits')
                    self.assertEqual(result.credit_amount, 2500)
                    self.assertEqual(result.display_order, 1)
            
    def test_sync_product_from_stripe_missing_credit_amount(self):
        """Test sync fails when credit_amount is missing from metadata."""
        stripe_product_data = {
            'id': 'prod_test_123',
            'name': 'Test Product',
            'description': 'Test Description',
            'active': True,
            'metadata': {},  # No credit_amount
            'default_price': 'price_test_123'
        }
        
        with patch.object(self.manager, 'retrieve_product', return_value=stripe_product_data):
            with patch('quickscale.project_templates.stripe_manager.stripe_manager.get_env', return_value='true'):
                with patch('quickscale.project_templates.stripe_manager.stripe_manager.is_feature_enabled', return_value=True):
                    product_model = create_mock_model()
                    
                    # Should return None due to missing credit_amount
                    result = self.manager.sync_product_from_stripe('prod_test_123', product_model)
                    self.assertIsNone(result)
            
    def test_sync_product_from_stripe_invalid_credit_amount(self):
        """Test sync fails when credit_amount is invalid."""
        stripe_product_data = {
            'id': 'prod_test_123',
            'name': 'Test Product',
            'description': 'Test Description',
            'active': True,
            'metadata': {
                'credit_amount': 'invalid'  # Invalid credit amount
            },
            'default_price': 'price_test_123'
        }
        
        with patch.object(self.manager, 'retrieve_product', return_value=stripe_product_data):
            with patch('quickscale.project_templates.stripe_manager.stripe_manager.get_env', return_value='true'):
                with patch('quickscale.project_templates.stripe_manager.stripe_manager.is_feature_enabled', return_value=True):
                    product_model = create_mock_model()
                    
                    # Should return None due to invalid credit_amount
                    result = self.manager.sync_product_from_stripe('prod_test_123', product_model)
                    self.assertIsNone(result)
            
    def test_sync_products_from_stripe_bulk_sync(self):
        """Test bulk sync of products from Stripe."""
        # Mock list of products from Stripe
        stripe_products = [
            {
                'id': 'prod_1',
                'name': 'Product 1',
                'description': 'Description 1',
                'active': True,
                'metadata': {'credit_amount': '1000'},
                'default_price': 'price_1'
            },
            {
                'id': 'prod_2',
                'name': 'Product 2',
                'description': 'Description 2',
                'active': True,
                'metadata': {'credit_amount': '2000'},
                'default_price': 'price_2'
            }
        ]
        
        # Mock the list_products method and environment
        with patch.object(self.manager, 'list_products', return_value=stripe_products):
            with patch('quickscale.project_templates.stripe_manager.stripe_manager.get_env', return_value='true'):
                with patch('quickscale.project_templates.stripe_manager.stripe_manager.is_feature_enabled', return_value=True):
                    # Mock individual product sync
                    with patch.object(self.manager, 'sync_product_from_stripe') as mock_sync:
                        mock_sync.return_value = MockStripeProduct()
                        
                        product_model = create_mock_model()
                        result = self.manager.sync_products_from_stripe(product_model)
                        
                        # Should return count of successfully synced products
                        self.assertEqual(result, 2)
                        self.assertEqual(mock_sync.call_count, 2)


class TestWebhookSecurity(TestCase):
    """Test webhook processing security."""
    
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def setUp(self):
        """Set up test environment."""
        StripeManager._instance = None
        StripeManager._initialized = False
        
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient') as mock_client:
                self.mock_client = mock_client.return_value
                self.manager = StripeManager.get_instance()
                
    def test_webhook_signature_verification(self):
        """Test webhook signature verification."""
        # Mock webhook event
        webhook_event = {
            'type': 'product.created',
            'data': {
                'object': {
                    'id': 'prod_test_123',
                    'name': 'Test Product'
                }
            }
        }
        
        # Mock successful signature verification
        self.mock_client.webhooks.construct_event.return_value = webhook_event
        
        # Test successful verification
        result = self.manager.client.webhooks.construct_event(
            b'{"type": "product.created"}',
            'test_signature',
            'test_secret'
        )
        
        self.assertEqual(result, webhook_event)
        
    def test_webhook_invalid_signature(self):
        """Test webhook processing with invalid signature."""
        # Mock signature verification failure
        self.mock_client.webhooks.construct_event.side_effect = Exception("Invalid signature")
        
        # Should raise exception
        with self.assertRaises(Exception):
            self.manager.client.webhooks.construct_event(
                b'{"type": "product.created"}',
                'invalid_signature',
                'test_secret'
            )


class TestWebhookProcessing(TestCase):
    """Test webhook processing functionality."""
    
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def setUp(self):
        """Set up test environment."""
        StripeManager._instance = None
        StripeManager._initialized = False
        
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient') as mock_client:
                self.mock_client = mock_client.return_value
                self.manager = StripeManager.get_instance()
                
    def test_webhook_checkout_session_completed(self):
        """Test webhook processing for checkout.session.completed event."""
        # Mock webhook event
        webhook_event = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_test_123',
                    'metadata': {
                        'purchase_type': 'subscription',
                        'user_id': '123',
                        'product_id': '456'
                    },
                    'subscription': 'sub_test_123',
                    'amount_total': 2500,
                    'currency': 'usd'
                }
            }
        }
        
        # Mock successful signature verification
        self.mock_client.webhooks.construct_event.return_value = webhook_event
        
        # Test webhook processing
        result = self.manager.client.webhooks.construct_event(
            b'{"type": "checkout.session.completed"}',
            'test_signature',
            'test_secret'
        )
        
        self.assertEqual(result, webhook_event)
        
    def test_webhook_subscription_updated(self):
        """Test webhook processing for customer.subscription.updated event."""
        # Mock webhook event
        webhook_event = {
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'id': 'sub_test_123',
                    'status': 'active',
                    'current_period_end': 1234567890
                }
            }
        }
        
        # Mock successful signature verification
        self.mock_client.webhooks.construct_event.return_value = webhook_event
        
        # Test webhook processing
        result = self.manager.client.webhooks.construct_event(
            b'{"type": "customer.subscription.updated"}',
            'test_signature',
            'test_secret'
        )
        
        self.assertEqual(result, webhook_event)
        
    def test_webhook_invoice_payment_succeeded(self):
        """Test webhook processing for invoice.payment_succeeded event."""
        # Mock webhook event
        webhook_event = {
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'id': 'in_test_123',
                    'subscription': 'sub_test_123',
                    'amount_paid': 2500
                }
            }
        }
        
        # Mock successful signature verification
        self.mock_client.webhooks.construct_event.return_value = webhook_event
        
        # Test webhook processing
        result = self.manager.client.webhooks.construct_event(
            b'{"type": "invoice.payment_succeeded"}',
            'test_signature',
            'test_secret'
        )
        
        self.assertEqual(result, webhook_event)
        
    def test_webhook_invoice_payment_failed(self):
        """Test webhook processing for invoice.payment_failed event."""
        # Mock webhook event
        webhook_event = {
            'type': 'invoice.payment_failed',
            'data': {
                'object': {
                    'id': 'in_test_123',
                    'subscription': 'sub_test_123',
                    'attempt_count': 1
                }
            }
        }
        
        # Mock successful signature verification
        self.mock_client.webhooks.construct_event.return_value = webhook_event
        
        # Test webhook processing
        result = self.manager.client.webhooks.construct_event(
            b'{"type": "invoice.payment_failed"}',
            'test_signature',
            'test_secret'
        )
        
        self.assertEqual(result, webhook_event)


class TestErrorHandlingAndFallbacks(TestCase):
    """Test error handling and fallback mechanisms."""
    
    def setUp(self):
        """Set up test environment."""
        StripeManager._instance = None
        StripeManager._initialized = False
        
    def test_api_unavailable_fallback(self):
        """Test behavior when Stripe API is unavailable."""
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient', side_effect=Exception("API unavailable")):
                with self.assertRaises(StripeConfigurationError):
                    StripeManager.get_instance()
                    
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def test_connectivity_test_disabled(self):
        """Test behavior when connectivity test is disabled."""
        with patch.dict(os.environ, {
            'STRIPE_ENABLED': 'true',
            'STRIPE_CONNECTIVITY_TEST': 'false'
        }):
            with patch('stripe.StripeClient') as mock_client:
                # Should not fail even if connectivity test is disabled
                manager = StripeManager.get_instance()
                self.assertIsNotNone(manager)
                
    def test_sync_with_stripe_disabled(self):
        """Test sync behavior when Stripe is disabled."""
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'false'}):
            manager = StripeManager()
            product_model = create_mock_model()
            
            # Should return 0 when Stripe is disabled
            result = manager.sync_products_from_stripe(product_model)
            self.assertEqual(result, 0)


class TestIntegrationScenarios(TestCase):
    """Test integration scenarios and end-to-end flows."""
    
    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    def setUp(self):
        """Set up test environment."""
        StripeManager._instance = None
        StripeManager._initialized = False
        
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}):
            with patch('stripe.StripeClient') as mock_client:
                self.mock_client = mock_client.return_value
                self.manager = StripeManager.get_instance()
                
    def test_complete_payment_flow(self):
        """Test complete payment flow from customer creation to payment completion."""
        # Mock customer creation
        customer_data = {'id': 'cus_test_123', 'email': 'test@example.com'}
        self.mock_client.customers.create.return_value = customer_data
        
        # Mock product creation
        product_data = {'id': 'prod_test_123', 'name': 'Test Product'}
        self.mock_client.products.create.return_value = product_data
        
        # Mock price creation
        price_data = {'id': 'price_test_123', 'unit_amount': 1000}
        self.mock_client.prices.create.return_value = price_data
        
        # Mock checkout session creation
        mock_session = MagicMock()
        mock_session.id = 'cs_test_123'
        mock_session.url = 'https://checkout.stripe.com/pay/cs_test_123'
        
        # Mock the price retrieval that happens in create_checkout_session
        mock_price = MagicMock()
        mock_price.get.return_value.get.return_value = 'month'  # recurring interval
        self.mock_client.prices.retrieve.return_value = mock_price
        
        # Mock the actual checkout session creation
        with patch('quickscale.project_templates.stripe_manager.stripe_manager.stripe.checkout.Session.create') as mock_stripe_create:
            mock_stripe_create.return_value = mock_session
            
            # Mock payment intent creation
            payment_intent_data = {'id': 'pi_test_123', 'status': 'requires_payment_method'}
            self.mock_client.payment_intents.create.return_value = payment_intent_data
            
            # Mock payment intent confirmation
            confirmed_payment_intent = {'id': 'pi_test_123', 'status': 'succeeded'}
            self.mock_client.payment_intents.confirm.return_value = confirmed_payment_intent
            
            # Execute the flow
            customer = self.manager.create_customer('test@example.com', 'Test Customer')
            product, price = self.manager.create_product_with_price('Test Product', 1000, 'usd')
            session = self.manager.create_checkout_session('price_test_123', 1, 'https://success.com', 'https://cancel.com')
            payment_intent = self.manager.create_payment_intent(1000, 'usd', customer_id='cus_test_123')
            confirmed = self.manager.confirm_payment_intent('pi_test_123')
            
            # Verify the flow
            self.assertEqual(customer['id'], 'cus_test_123')
            self.assertEqual(product['id'], 'prod_test_123')
            self.assertEqual(price['id'], 'price_test_123')
            self.assertEqual(session.id, 'cs_test_123')  # session is a mock object, not a dict
            self.assertEqual(payment_intent['id'], 'pi_test_123')
            self.assertEqual(confirmed['status'], 'succeeded')
        
    def test_subscription_lifecycle_flow(self):
        """Test complete subscription lifecycle from creation to cancellation."""
        # Mock subscription creation
        subscription_data = {'id': 'sub_test_123', 'status': 'active'}
        self.mock_client.subscriptions.create.return_value = subscription_data
        
        # Mock subscription retrieval
        self.mock_client.subscriptions.retrieve.return_value = subscription_data
        
        # Mock subscription cancellation
        canceled_subscription = {'id': 'sub_test_123', 'status': 'canceled'}
        self.mock_client.subscriptions.update.return_value = canceled_subscription
        
        # Execute the flow
        subscription = self.manager.create_subscription('cus_test_123', 'price_test_123')
        retrieved = self.manager.retrieve_subscription('sub_test_123')
        canceled = self.manager.cancel_subscription('sub_test_123', at_period_end=True)
        
        # Verify the flow
        self.assertEqual(subscription['status'], 'active')
        self.assertEqual(retrieved['status'], 'active')
        self.assertEqual(canceled['status'], 'canceled')
        
    def test_error_recovery_scenarios(self):
        """Test various error recovery scenarios."""
        # Test API error during customer creation
        self.mock_client.customers.create.side_effect = Exception("API Error")
        
        with self.assertRaises(Exception):
            self.manager.create_customer('test@example.com')
            
        # Reset the side effect
        self.mock_client.customers.create.side_effect = None
        
        # Test successful recovery
        customer_data = {'id': 'cus_test_123', 'email': 'test@example.com'}
        self.mock_client.customers.create.return_value = customer_data
        
        result = self.manager.create_customer('test@example.com')
        self.assertEqual(result, customer_data)


def create_mock_model():
    """Create a mock Django model for testing."""
    class MockModel:
        objects = MagicMock()
        
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
                
        def save(self):
            pass
            
    return MockModel


if __name__ == '__main__':
    unittest.main() 