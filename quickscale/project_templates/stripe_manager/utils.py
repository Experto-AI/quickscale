"""
Utility functions for Stripe integration.
"""

import os
import uuid
from typing import Dict, Any, Optional


class MockStripeCustomer:
    """
    Mock implementation of Stripe Customer for testing and development.
    
    This class provides a simple way to create mock Stripe Customer objects
    when the Stripe API is not available or when running in test mode.
    """
    
    @classmethod
    def create(cls, 
              id: Optional[str] = None,
              email: Optional[str] = None, 
              name: Optional[str] = None, 
              metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a mock Stripe Customer object.
        
        Args:
            id (Optional[str]): Customer ID
            email (Optional[str]): Customer's email address
            name (Optional[str]): Customer's name
            metadata (Optional[Dict[str, Any]]): Additional metadata
            
        Returns:
            Dict[str, Any]: A mock customer object
        """
        customer_id = id or f"cus_mock_{uuid.uuid4().hex[:8]}"
        return {
            'id': customer_id,
            'object': 'customer',
            'email': email or f"mock.user+{customer_id}@example.com",
            'name': name or "Mock User",
            'description': "Mock customer for development",
            'metadata': metadata or {},
            'created': 1234567890,  # Unix timestamp
            'default_source': None,
            'invoice_settings': {
                'default_payment_method': None,
                'footer': None,
            },
            'livemode': False,
        } 