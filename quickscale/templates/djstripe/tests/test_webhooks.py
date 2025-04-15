"""
Tests for Stripe webhook handlers.

These tests verify that the Stripe webhook handlers work correctly.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory, override_settings
from django.conf import settings
from django.http import HttpResponse

from ..webhooks import stripe_webhook, handle_customer_created
from ..utils import create_mock_webhook_event


@override_settings(STRIPE_TEST_MODE=True)
class StripeWebhookTest(TestCase):
    """Test the Stripe webhook handler."""
    
    def setUp(self):
        """Set up test case with environment variables and mocks."""
        # Set up environment variables for test
        self.env_patcher = patch.dict(os.environ, {
            'STRIPE_ENABLED': 'true',
            'STRIPE_TEST_MODE': 'true'
        })
        self.env_patcher.start()
        
        # Mock the stripe module
        self.stripe_mock = MagicMock()
        self.stripe_mock.api_key = None
        self.webhook_constructed_event = MagicMock(return_value={
            'type': 'customer.created',
            'data': {
                'object': {
                    'id': 'cus_mock_12345',
                    'email': 'webhook@example.com'
                }
            }
        })
        self.stripe_mock.Webhook.construct_event = self.webhook_constructed_event
        
        self.stripe_patcher = patch('djstripe.utils.get_stripe', return_value=self.stripe_mock)
        self.get_stripe_mock = self.stripe_patcher.start()
        
        # Mock the settings
        self.settings_patcher = patch('django.conf.settings')
        self.settings_mock = self.settings_patcher.start()
        self.settings_mock.STRIPE_SECRET_KEY = 'sk_test_mock'
        self.settings_mock.DJSTRIPE_WEBHOOK_SECRET = 'whsec_mock'
        
        # Set up request factory
        self.factory = RequestFactory()
    
    def tearDown(self):
        """Clean up patchers."""
        self.env_patcher.stop()
        self.stripe_patcher.stop()
        self.settings_patcher.stop()
    
    def test_webhook_processing(self):
        """Test processing a webhook event."""
        # Create a POST request with webhook data
        payload = json.dumps({
            'id': 'evt_mock_12345',
            'type': 'customer.created',
            'data': {
                'object': {
                    'id': 'cus_mock_12345',
                    'email': 'webhook@example.com'
                }
            }
        })
        
        request = self.factory.post(
            '/stripe/webhook/',
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='sig_mock_12345'
        )
        
        # Call the webhook handler
        with patch('djstripe.webhooks.handle_customer_created') as mock_handler:
            response = stripe_webhook(request)
            
            # Check that the response is OK
            self.assertEqual(response.status_code, 200)
            
            # Check that construct_event was called with the right arguments
            self.webhook_constructed_event.assert_called_once_with(
                payload, 'sig_mock_12345', 'whsec_mock'
            )
            
            # Check that the handler was called
            mock_handler.assert_called_once()
    
    def test_webhook_disabled_stripe(self):
        """Test webhook handling when Stripe is disabled."""
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'false'}):
            request = self.factory.post('/stripe/webhook/')
            response = stripe_webhook(request)
            
            # Check that the response is an error
            self.assertEqual(response.status_code, 400)
    
    def test_webhook_missing_signature(self):
        """Test webhook handling when Stripe signature is missing."""
        request = self.factory.post('/stripe/webhook/')
        response = stripe_webhook(request)
        
        # Check that the response is an error
        self.assertEqual(response.status_code, 400)
    
    def test_webhook_invalid_signature(self):
        """Test webhook handling when Stripe signature is invalid."""
        self.stripe_mock.Webhook.construct_event.side_effect = self.stripe_mock.error.SignatureVerificationError(
            'Invalid signature', 'sig_mock', 'payload'
        )
        
        request = self.factory.post(
            '/stripe/webhook/',
            data='{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='invalid_sig'
        )
        
        response = stripe_webhook(request)
        
        # Check that the response is an error
        self.assertEqual(response.status_code, 400)
    
    def test_handle_customer_created(self):
        """Test the customer.created event handler."""
        event = {
            'type': 'customer.created',
            'data': {
                'object': {
                    'id': 'cus_mock_12345',
                    'email': 'webhook@example.com'
                }
            }
        }
        
        # Just make sure it doesn't raise an exception
        with patch('djstripe.webhooks.logger') as mock_logger:
            handle_customer_created(event)
            
            # Verify that logging occurred
            mock_logger.info.assert_called_once()


class CreateMockWebhookEventTest(TestCase):
    """Test the create_mock_webhook_event utility function."""
    
    def test_customer_created_event(self):
        """Test creating a mock customer.created event."""
        customer_data = {
            'id': 'cus_mock_12345',
            'email': 'webhook@example.com'
        }
        
        event = create_mock_webhook_event('customer.created', customer_data)
        
        self.assertEqual(event['type'], 'customer.created')
        self.assertEqual(event['data']['object']['id'], 'cus_mock_12345')
        self.assertEqual(event['data']['object']['email'], 'webhook@example.com')
    
    def test_subscription_updated_event(self):
        """Test creating a mock subscription.updated event."""
        subscription_data = {
            'id': 'sub_mock_12345',
            'status': 'active',
            'customer': 'cus_mock_12345'
        }
        
        event = create_mock_webhook_event('customer.subscription.updated', subscription_data)
        
        self.assertEqual(event['type'], 'customer.subscription.updated')
        self.assertEqual(event['data']['object']['id'], 'sub_mock_12345')
        self.assertEqual(event['data']['object']['status'], 'active') 