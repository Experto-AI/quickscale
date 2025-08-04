"""Tests for Stripe webhook integration."""

import pytest
import json
import os
from unittest.mock import patch, MagicMock
from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model

# Set up Django for testing  
from ..base import StripeIntegrationTestCase, setup_django_template_path, setup_core_env_utils_mock, setup_django_settings

# Set up template path and environment
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()

# Import Django and initialize
import django
django.setup()

# Import the modules we're testing
from stripe_manager.models import StripeProduct, StripeCustomer
from stripe_manager.views import webhook as handle_webhook
from stripe_manager.stripe_manager import StripeManager

User = get_user_model()


@pytest.mark.django_component
@pytest.mark.integration
class StripeWebhookIntegrationTests(StripeIntegrationTestCase):
    """Integration tests for Stripe webhook handling."""
    
    def setUp(self):
        """Set up test environment for webhook tests."""
        super().setUp()
        
        # Create test user
        self.user = User.objects.create_user(
            email='webhook@example.com',
            password='testpass123'
        )
        
        # Create test Stripe customer
        self.stripe_customer = StripeCustomer.objects.create(
            user=self.user,
            stripe_id='cus_webhook_test',
            email=self.user.email
        )
        
        # Create test Stripe product
        self.stripe_product = StripeProduct.objects.create(
            name='Webhook Test Plan',
            stripe_id='prod_webhook_test',
            stripe_price_id='price_webhook_test',
            price=29.99,
            currency='USD',
            interval='month',
            credit_amount=1000,
            active=True
        )
    
    @patch('stripe_manager.stripe_manager.StripeManager.get_instance')
    def test_webhook_payment_succeeded(self, mock_get_instance):
        """Test handling of successful payment webhook."""
        # Mock the stripe manager and its client
        mock_stripe_manager = MagicMock()
        mock_client = MagicMock()
        mock_stripe_manager.client = mock_client
        mock_get_instance.return_value = mock_stripe_manager
        
        # Mock webhook event
        webhook_payload = {
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'id': 'in_test123',
                    'customer': 'cus_webhook_test',
                    'subscription': 'sub_test123',
                    'amount_paid': 2999,
                    'currency': 'usd',
                    'status': 'paid'
                }
            }
        }
        
        # Mock the webhook event construction
        mock_event = {
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'id': 'in_test123',
                    'customer': 'cus_webhook_test',
                    'subscription': 'sub_test123',
                    'amount_paid': 2999,
                    'currency': 'usd',
                    'status': 'paid'
                }
            }
        }
        mock_client.webhooks.construct_event.return_value = mock_event
        
        # Create mock request
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post(
            '/stripe/webhook/',
            data=json.dumps(webhook_payload),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        # Mock environment variable for webhook secret
        with patch('stripe_manager.views.get_env') as mock_get_env:
            mock_get_env.return_value = 'test_webhook_secret'
            
            # Process webhook
            response = handle_webhook(request)
            
            # Verify webhook was processed successfully
            self.assertEqual(response.status_code, 200)
    
    @patch('stripe_manager.stripe_manager.StripeManager.get_instance')
    def test_webhook_subscription_created(self, mock_get_instance):
        """Test handling of subscription created webhook."""
        # Mock the stripe manager and its client
        mock_stripe_manager = MagicMock()
        mock_client = MagicMock()
        mock_stripe_manager.client = mock_client
        mock_get_instance.return_value = mock_stripe_manager
        
        webhook_payload = {
            'type': 'customer.subscription.created',
            'data': {
                'object': {
                    'id': 'sub_test123',
                    'customer': 'cus_webhook_test',
                    'status': 'active',
                    'current_period_start': 1640995200,  # 2022-01-01
                    'current_period_end': 1643673600,    # 2022-02-01
                    'items': {
                        'data': [{
                            'price': {
                                'id': 'price_webhook_test'
                            }
                        }]
                    }
                }
            }
        }
        
        # Mock the webhook event construction
        mock_event = {
            'type': 'customer.subscription.created',
            'data': webhook_payload['data']
        }
        mock_client.webhooks.construct_event.return_value = mock_event
        
        # Create mock request
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post(
            '/stripe/webhook/',
            data=json.dumps(webhook_payload),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        # Mock environment variable for webhook secret
        with patch('stripe_manager.views.get_env') as mock_get_env:
            mock_get_env.return_value = 'test_webhook_secret'
            
            response = handle_webhook(request)
            
            self.assertEqual(response.status_code, 200)
    
    @patch('stripe_manager.stripe_manager.StripeManager.get_instance')
    def test_webhook_subscription_deleted(self, mock_get_instance):
        """Test handling of subscription deleted webhook."""
        # Mock the stripe manager and its client
        mock_stripe_manager = MagicMock()
        mock_client = MagicMock()
        mock_stripe_manager.client = mock_client
        mock_get_instance.return_value = mock_stripe_manager
        
        webhook_payload = {
            'type': 'customer.subscription.deleted',
            'data': {
                'object': {
                    'id': 'sub_test123',
                    'customer': 'cus_webhook_test',
                    'status': 'canceled'
                }
            }
        }
        
        # Mock the webhook event construction
        mock_event = {
            'type': 'customer.subscription.deleted',
            'data': webhook_payload['data']
        }
        mock_client.webhooks.construct_event.return_value = mock_event
        
        # Create mock request
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post(
            '/stripe/webhook/',
            data=json.dumps(webhook_payload),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        # Mock environment variable for webhook secret
        with patch('stripe_manager.views.get_env') as mock_get_env:
            mock_get_env.return_value = 'test_webhook_secret'
            
            response = handle_webhook(request)
            
            self.assertEqual(response.status_code, 200)
    
    @patch('stripe_manager.stripe_manager.StripeManager.get_instance')
    def test_webhook_invalid_event_type(self, mock_get_instance):
        """Test handling of unrecognized webhook event type."""
        # Mock the stripe manager and its client
        mock_stripe_manager = MagicMock()
        mock_client = MagicMock()
        mock_stripe_manager.client = mock_client
        mock_get_instance.return_value = mock_stripe_manager
        
        webhook_payload = {
            'type': 'unknown.event.type',
            'data': {
                'object': {}
            }
        }
        
        # Mock the webhook event construction
        mock_event = {
            'type': 'unknown.event.type',
            'data': webhook_payload['data']
        }
        mock_client.webhooks.construct_event.return_value = mock_event
        
        # Create mock request
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post(
            '/stripe/webhook/',
            data=json.dumps(webhook_payload),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        # Mock environment variable for webhook secret
        with patch('stripe_manager.views.get_env') as mock_get_env:
            mock_get_env.return_value = 'test_webhook_secret'
            
            response = handle_webhook(request)
            
            # Should still return 200 to acknowledge receipt
            self.assertEqual(response.status_code, 200)
    
    def test_webhook_with_invalid_json(self):
        """Test webhook handling with invalid JSON payload."""
        # Create mock request with invalid JSON
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post(
            '/stripe/webhook/',
            data="invalid json data",
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        # Mock environment variable for webhook secret
        with patch('stripe_manager.views.get_env') as mock_get_env:
            mock_get_env.return_value = 'test_webhook_secret'
            
            # Mock the stripe manager to raise an exception for invalid JSON
            with patch('stripe_manager.stripe_manager.StripeManager.get_instance') as mock_get_instance:
                mock_stripe_manager = MagicMock()
                mock_client = MagicMock()
                mock_stripe_manager.client = mock_client
                mock_get_instance.return_value = mock_stripe_manager
                
                # Make the construct_event raise an exception for invalid JSON
                mock_client.webhooks.construct_event.side_effect = ValueError("Invalid JSON")
                
                response = handle_webhook(request)
                
                # Should return error status for invalid JSON
                self.assertIn(response.status_code, [400, 500])
    
    @patch('stripe_manager.stripe_manager.StripeManager.get_instance')
    def test_webhook_with_missing_customer(self, mock_get_instance):
        """Test webhook handling when customer doesn't exist in database."""
        # Mock the stripe manager and its client
        mock_stripe_manager = MagicMock()
        mock_client = MagicMock()
        mock_stripe_manager.client = mock_client
        mock_get_instance.return_value = mock_stripe_manager
        
        webhook_payload = {
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'customer': 'cus_nonexistent',
                    'subscription': 'sub_test123'
                }
            }
        }
        
        # Mock the webhook event construction
        mock_event = {
            'type': 'invoice.payment_succeeded',
            'data': webhook_payload['data']
        }
        mock_client.webhooks.construct_event.return_value = mock_event
        
        # Create mock request
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post(
            '/stripe/webhook/',
            data=json.dumps(webhook_payload),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        # Mock environment variable for webhook secret
        with patch('stripe_manager.views.get_env') as mock_get_env:
            mock_get_env.return_value = 'test_webhook_secret'
            
            response = handle_webhook(request)
            
            # Should handle gracefully even if customer not found
            self.assertEqual(response.status_code, 200)
