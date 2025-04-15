"""
Tests for mock Stripe implementation.

These tests verify that the mock Stripe implementation works as expected
and can be used in test environments.
"""

import os
import pytest
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings

from ..utils import (
    MockStripeObject,
    MockStripeCustomer,
    MockStripeSubscription,
    MockStripeAPI,
    get_stripe,
    create_mock_webhook_event
)

User = get_user_model()


class MockStripeObjectTest(TestCase):
    """Test the MockStripeObject class."""
    
    def test_dict_access(self):
        """Test dictionary-style access."""
        obj = MockStripeObject({'foo': 'bar', 'nested': {'baz': 'qux'}})
        self.assertEqual(obj['foo'], 'bar')
        self.assertEqual(obj['nested']['baz'], 'qux')
    
    def test_attribute_access(self):
        """Test attribute-style access."""
        obj = MockStripeObject({'foo': 'bar', 'nested': {'baz': 'qux'}})
        self.assertEqual(obj.foo, 'bar')
        self.assertEqual(obj.nested.baz, 'qux')
    
    def test_nested_lists(self):
        """Test handling of nested lists."""
        obj = MockStripeObject({'items': [{'id': 1}, {'id': 2}]})
        self.assertEqual(obj.items[0].id, 1)
        self.assertEqual(obj.items[1].id, 2)


class MockStripeCustomerTest(TestCase):
    """Test the MockStripeCustomer class."""
    
    def test_create(self):
        """Test creating a mock customer."""
        customer = MockStripeCustomer.create(
            email='test@example.com',
            name='Test User',
            metadata={'user_id': 123}
        )
        
        # Check basic attributes
        self.assertTrue(customer.id.startswith('cus_mock_'))
        self.assertEqual(customer.object, 'customer')
        self.assertEqual(customer.email, 'test@example.com')
        self.assertEqual(customer.name, 'Test User')
        self.assertEqual(customer.metadata['user_id'], 123)


class MockStripeSubscriptionTest(TestCase):
    """Test the MockStripeSubscription class."""
    
    def test_create(self):
        """Test creating a mock subscription."""
        subscription = MockStripeSubscription.create(
            customer='cus_mock_123',
            price='price_mock_456',
            metadata={'plan': 'premium'}
        )
        
        # Check basic attributes
        self.assertTrue(subscription.id.startswith('sub_mock_'))
        self.assertEqual(subscription.object, 'subscription')
        self.assertEqual(subscription.customer, 'cus_mock_123')
        self.assertEqual(subscription.items.data[0].price, 'price_mock_456')
        self.assertEqual(subscription.metadata['plan'], 'premium')
        self.assertEqual(subscription.status, 'active')


class MockStripeAPITest(TestCase):
    """Test the MockStripeAPI class."""
    
    def test_initialization(self):
        """Test initializing the mock API."""
        api = MockStripeAPI()
        self.assertEqual(api.api_key, 'sk_test_mock')
        self.assertIsNone(api.error)
    
    def test_customer_creation(self):
        """Test creating a customer through the mock API."""
        api = MockStripeAPI()
        customer = api.customers.create(email='test@example.com')
        self.assertTrue(customer.id.startswith('cus_mock_'))
        self.assertEqual(customer.email, 'test@example.com')
    
    def test_subscription_creation(self):
        """Test creating a subscription through the mock API."""
        api = MockStripeAPI()
        subscription = api.subscriptions.create(customer='cus_mock_123')
        self.assertTrue(subscription.id.startswith('sub_mock_'))
        self.assertEqual(subscription.customer, 'cus_mock_123')
    
    def test_reset_mocks(self):
        """Test resetting mocks."""
        api = MockStripeAPI()
        api.customers.create(email='test@example.com')
        self.assertEqual(api.customers.create.call_count, 1)
        
        api.reset_mocks()
        self.assertEqual(api.customers.create.call_count, 0)


class GetStripeTest(TestCase):
    """Test the get_stripe utility function."""
    
    @patch.dict(os.environ, {'STRIPE_TEST_MODE': 'true'})
    def test_test_mode(self):
        """Test getting Stripe in test mode."""
        stripe = get_stripe()
        self.assertIsInstance(stripe, MockStripeAPI)
    
    @patch.dict(os.environ, {'STRIPE_TEST_MODE': 'false'})
    def test_real_mode(self):
        """Test getting real Stripe in normal mode."""
        with patch('builtins.__import__', return_value=None):
            # This simulates importing real stripe
            stripe = get_stripe()
            # We might get None if stripe is not installed
            self.assertIsNotNone(stripe)


class MockWebhookEventTest(TestCase):
    """Test creating mock webhook events."""
    
    def test_create_event(self):
        """Test creating a mock webhook event."""
        customer_data = {
            'id': 'cus_mock_123',
            'email': 'test@example.com'
        }
        
        event = create_mock_webhook_event('customer.created', customer_data)
        
        self.assertTrue(event['id'].startswith('evt_mock_'))
        self.assertEqual(event['type'], 'customer.created')
        self.assertEqual(event['data']['object']['id'], 'cus_mock_123')
        self.assertEqual(event['data']['object']['email'], 'test@example.com') 