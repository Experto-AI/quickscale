"""
Django Stripe Utilities

Helper functions that abstract Stripe-specific logic from the rest of the application.
This separation creates a clear boundary between payment processing and business logic,
allowing the core application to remain agnostic to the payment provider implementation.

By centralizing Stripe operations here, we reduce duplication and maintain consistent 
error handling across the codebase, while also simplifying any future provider changes
or testing in environments without Stripe connectivity.
"""

import logging
import uuid
import time
from unittest.mock import MagicMock
from typing import Dict, Any, Optional, List
from core.env_utils import get_env, is_feature_enabled

logger = logging.getLogger(__name__)


class MockStripeObject(dict):
    """Provides attribute access to dictionary keys for Stripe API response compatibility."""
    
    def __init__(self, data: Dict[str, Any]) -> None:
        super().__init__(data)
        for key, value in data.items():
            if isinstance(value, dict):
                self[key] = MockStripeObject(value)
            elif isinstance(value, list):
                self[key] = [
                    MockStripeObject(item) if isinstance(item, dict) else item
                    for item in value
                ]
    
    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'MockStripeObject' has no attribute '{key}'")


class MockStripeCustomer(MockStripeObject):
    """Simulates Stripe customer API responses for testing without real API calls."""
    
    @classmethod
    def create(cls, **kwargs) -> 'MockStripeCustomer':
        """Generates mock customer objects with the same structure as Stripe's API."""
        # Use hex prefix to make mock IDs visually distinct from real ones
        customer_id = f"cus_mock_{uuid.uuid4().hex[:10]}"
        timestamp = int(time.time())
        
        # Match the real Stripe API response structure for seamless test switching
        customer_data = {
            'id': customer_id,
            'object': 'customer',
            'created': timestamp,
            'email': kwargs.get('email', ''),
            'name': kwargs.get('name', ''),
            'description': kwargs.get('description', ''),
            'metadata': kwargs.get('metadata', {}),
            'livemode': False,
            'currency': 'usd',
            'default_source': None,
            'delinquent': False,
            'address': None,
            'balance': 0,
            'discount': None,
            'invoice_settings': {
                'custom_fields': None,
                'default_payment_method': None,
                'footer': None,
            },
            'shipping': None,
            'tax_exempt': 'none',
        }
        
        return cls(customer_data)


class MockStripeSubscription(MockStripeObject):
    """Simulates Stripe subscription API responses for testing payment flows."""
    
    @classmethod
    def create(cls, **kwargs) -> 'MockStripeSubscription':
        """Generates mock subscription objects for testing billing scenarios."""
        # Use hex prefix for mock IDs to distinguish from real ones
        subscription_id = f"sub_mock_{uuid.uuid4().hex[:10]}"
        timestamp = int(time.time())
        
        # Match the structure of real subscription objects for test compatibility
        subscription_data = {
            'id': subscription_id,
            'object': 'subscription',
            'created': timestamp,
            'customer': kwargs.get('customer', ''),
            'current_period_start': timestamp,
            'current_period_end': timestamp + (30 * 24 * 60 * 60),  # +30 days for billing cycle
            'status': 'active',
            'items': {
                'object': 'list',
                'data': [
                    {
                        'id': f"si_mock_{uuid.uuid4().hex[:10]}",
                        'object': 'subscription_item',
                        'price': kwargs.get('price', ''),
                    }
                ],
                'has_more': False,
                'total_count': 1,
            },
            'metadata': kwargs.get('metadata', {}),
            'livemode': False,
            'cancel_at_period_end': False,
            'canceled_at': None,
            'ended_at': None,
            'trial_start': None,
            'trial_end': None,
        }
        
        return cls(subscription_data)


class MockStripeAPI:
    """Enables testing payment flows without requiring a real Stripe account."""
    
    def __init__(self) -> None:
        """Sets up the mock API structure to match real Stripe's organization."""
        # Set up MagicMock with side_effects to mimic the real API behavior
        self.customers = MagicMock()
        self.customers.create.side_effect = MockStripeCustomer.create
        
        self.subscriptions = MagicMock()
        self.subscriptions.create.side_effect = MockStripeSubscription.create
        
        # Match the structure of the real API for transparent mocking
        self.api_key = "sk_test_mock"
        self.error = None
    
    def reset_mocks(self) -> None:
        """Prevents test cross-contamination by clearing previous test state."""
        # Allow fresh start between tests to prevent state contamination
        self.customers.reset_mock()
        self.subscriptions.reset_mock()


def get_stripe():
    """Provides consistent Stripe API access across both test and production environments."""
    # Support transparent test mode to allow running tests without Stripe account
    test_mode = is_feature_enabled(get_env('STRIPE_TEST_MODE', 'False'))
    
    if test_mode:
        # Return mock API to avoid real API calls during testing
        logger.info("Using mock Stripe API for testing")
        mock_api = MockStripeAPI()
        return mock_api
    else:
        # Return real Stripe library for production use
        try:
            import stripe
            return stripe
        except ImportError:
            logger.error("Failed to import Stripe library")
            return None


def create_mock_webhook_event(event_type: str, object_data: Dict[str, Any]) -> Dict[str, Any]:
    """Enables testing webhook handlers without real Stripe events."""
    timestamp = int(time.time())
    
    # Match structure of real webhook events for test compatibility
    event_data = {
        'id': f"evt_mock_{uuid.uuid4().hex[:16]}",
        'object': 'event',
        'api_version': '2020-08-27',
        'created': timestamp,
        'data': {
            'object': object_data
        },
        'livemode': False,
        'pending_webhooks': 0,
        'request': {
            'id': None,
            'idempotency_key': None
        },
        'type': event_type
    }
    
    return event_data