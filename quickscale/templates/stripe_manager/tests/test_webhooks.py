"""Tests for Stripe webhook handlers with StripeManager."""

import os
import json
import sys
import pytest
from unittest.mock import patch, MagicMock

# Create mocks before importing anything from Django
# Create a mock for 'core.env_utils' module - must be before importing views or urls
from quickscale.templates.stripe.tests.mock_env_utils import get_env, is_feature_enabled
mock_env_utils = MagicMock()
mock_env_utils.get_env = get_env
mock_env_utils.is_feature_enabled = is_feature_enabled
sys.modules['core.env_utils'] = mock_env_utils

# Also mock the stripe_manager module before importing anything from Django
mock_stripe_manager = MagicMock()
mock_stripe_manager.stripe = MagicMock()

class MockStripeManagerModule(MagicMock):
    StripeConfigurationError = Exception
    get_stripe_manager = MagicMock(return_value=mock_stripe_manager)

sys.modules['quickscale.templates.stripe.stripe_manager'] = MockStripeManagerModule()
sys.modules['stripe.stripe_manager'] = MockStripeManagerModule()  # For older imports

# Configure Django settings before importing anything from Django
from django.conf import settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        USE_TZ=True,
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        ROOT_URLCONF="quickscale.templates.stripe.tests.test_webhooks",  # Use this module as URLconf
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sites",
        ],
        SITE_ID=1,
        MIDDLEWARE_CLASSES=(),
        SECRET_KEY="test-key",
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.debug",
                        "django.template.context_processors.request",
                    ],
                },
            },
        ],
        STRIPE_TEST_MODE=True,
    )

# Initialize Django
import django
django.setup()

# Now import Django test utilities
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse
from django.urls import path, include

# Now import the views module
from quickscale.templates.stripe import views as views_module
from quickscale.templates.stripe.views import webhook
from quickscale.templates.stripe.utils import MockStripeCustomer

# For tests, use a hardcoded URL instead of reverse()
WEBHOOK_URL = '/stripe/webhook/'

# Define URLconf for the tests
urlpatterns = [
    path('stripe/webhook/', webhook, name='webhook'),
]

@override_settings(STRIPE_TEST_MODE=True)
class StripeWebhookTest(TestCase):
    """Test the Stripe webhook handler."""
    
    def setUp(self) -> None:
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
        
        # Set the stripe attribute on the stripe_manager
        mock_stripe_manager.stripe = self.stripe_mock
        
        # Mock settings using our mock_env_utils
        self.settings_patcher = patch.object(views_module, 'get_env', return_value='whsec_mock')
        self.get_env_mock = self.settings_patcher.start()
        
        # Set up request factory
        self.factory = RequestFactory()
    
    def tearDown(self) -> None:
        """Clean up patchers."""
        self.env_patcher.stop()
        self.settings_patcher.stop()
    
    def test_webhook_processing(self) -> None:
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
            WEBHOOK_URL,
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='sig_mock_12345'
        )
        
        # Call the webhook handler
        response = webhook(request)
            
        # Check that the response is OK
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(str(response.content, encoding='utf-8'), {'status': 'success'})
        
        # Check that construct_event was called with the right arguments
        self.webhook_constructed_event.assert_called_once_with(
            payload.encode(), 'sig_mock_12345', 'whsec_mock'
        )
    
    def test_webhook_method_not_allowed(self) -> None:
        """Test webhook handling with invalid HTTP method."""
        request = self.factory.get(WEBHOOK_URL)
        response = webhook(request)
        
        # Check that the response is an error
        self.assertEqual(response.status_code, 405)
        self.assertJSONEqual(str(response.content, encoding='utf-8'), {'error': 'Invalid request method'})
    
    def test_webhook_missing_signature(self) -> None:
        """Test webhook handling when Stripe signature is missing."""
        request = self.factory.post(
            WEBHOOK_URL,
            data='{}',
            content_type='application/json'
        )
        response = webhook(request)
        
        # Check that the response is an error
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(str(response.content, encoding='utf-8'), {'error': 'No Stripe signature header'})
    
    def test_webhook_invalid_signature(self) -> None:
        """Test webhook handling when Stripe signature is invalid."""
        self.stripe_mock.error.SignatureVerificationError = ValueError
        self.stripe_mock.Webhook.construct_event.side_effect = ValueError('Invalid signature')
        
        request = self.factory.post(
            WEBHOOK_URL,
            data='{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='invalid_sig'
        )
        
        response = webhook(request)
        
        # Check that the response is an error
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(str(response.content, encoding='utf-8'), {'error': 'Invalid payload'})
    
    def test_webhook_products_processing(self) -> None:
        """Test handling product-related webhook events."""
        # Test data for each event type
        event_types = [
            ('product.created', {'id': 'prod_mock_1', 'name': 'New Product'}),
            ('product.updated', {'id': 'prod_mock_1', 'name': 'Updated Product'}),
            ('price.created', {'id': 'price_mock_1', 'product': 'prod_mock_1', 'unit_amount': 1000})
        ]
        
        for event_type, object_data in event_types:
            # Reset mock
            self.webhook_constructed_event.reset_mock()
            
            # Set up mock event data
            self.webhook_constructed_event.return_value = {
                'type': event_type,
                'data': {
                    'object': object_data
                }
            }
            
            # Create request
            payload = json.dumps({
                'id': f'evt_mock_{event_type}',
                'type': event_type,
                'data': {
                    'object': object_data
                }
            })
            
            request = self.factory.post(
                WEBHOOK_URL,
                data=payload,
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE=f'sig_mock_{event_type}'
            )
            
            # Call webhook
            response = webhook(request)
            
            # Check response
            self.assertEqual(response.status_code, 200, f"Failed for event type: {event_type}")
            self.assertJSONEqual(
                str(response.content, encoding='utf-8'), 
                {'status': 'success'},
                f"Failed for event type: {event_type}"
            )


class MockStripeCustomerTest(TestCase):
    """Test the MockStripeCustomer utility class."""
    
    def test_create_with_defaults(self) -> None:
        """Test creating a mock customer with default values."""
        customer = MockStripeCustomer.create()
        
        self.assertTrue(customer['id'].startswith('cus_mock_'))
        self.assertTrue('@example.com' in customer['email'])
        self.assertEqual(customer['name'], 'Mock User')
        self.assertEqual(customer['metadata'], {})
    
    def test_create_with_custom_values(self) -> None:
        """Test creating a mock customer with custom values."""
        custom_id = 'cus_test_123'
        custom_email = 'test@example.com'
        custom_name = 'Test User'
        custom_metadata = {'role': 'tester'}
        
        customer = MockStripeCustomer.create(
            id=custom_id,
            email=custom_email,
            name=custom_name,
            metadata=custom_metadata
        )
        
        self.assertEqual(customer['id'], custom_id)
        self.assertEqual(customer['email'], custom_email)
        self.assertEqual(customer['name'], custom_name)
        self.assertEqual(customer['metadata'], custom_metadata) 