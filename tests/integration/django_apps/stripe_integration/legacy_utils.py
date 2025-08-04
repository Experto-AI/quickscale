"""
Utility functions for Stripe tests.
"""

import uuid
import time
from typing import Dict, Any, Optional, List


def create_mock_webhook_event(event_type: str, object_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a mock Stripe webhook event for testing.
    
    Args:
        event_type (str): The type of event (e.g., 'customer.created')
        object_data (Dict[str, Any]): The data for the object that triggered the event
        
    Returns:
        Dict[str, Any]: A mock webhook event
    """
    event_id = f"evt_mock_{uuid.uuid4().hex[:8]}"
    
    return {
        'id': event_id,
        'object': 'event',
        'api_version': '2020-08-27',
        'created': int(time.time()),
        'data': {
            'object': object_data
        },
        'livemode': False,
        'pending_webhooks': 0,
        'request': {
            'id': f"req_mock_{uuid.uuid4().hex[:8]}",
            'idempotency_key': f"idempotency_{uuid.uuid4().hex[:8]}"
        },
        'type': event_type
    }


def create_mock_product(
    id: Optional[str] = None,
    name: str = "Mock Product",
    description: Optional[str] = None,
    active: bool = True,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a mock Stripe product for testing.
    
    Args:
        id (Optional[str]): Product ID
        name (str): Product name
        description (Optional[str]): Product description
        active (bool): Whether the product is active
        metadata (Optional[Dict[str, Any]]): Additional metadata
        
    Returns:
        Dict[str, Any]: A mock product object
    """
    product_id = id or f"prod_mock_{uuid.uuid4().hex[:8]}"
    
    return {
        'id': product_id,
        'object': 'product',
        'active': active,
        'created': int(time.time()),
        'description': description,
        'name': name,
        'metadata': metadata or {},
        'updated': int(time.time())
    }


def create_mock_price(
    id: Optional[str] = None,
    product_id: str = "prod_mock_default",
    unit_amount: int = 1000,
    currency: str = "usd",
    active: bool = True,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a mock Stripe price for testing.
    
    Args:
        id (Optional[str]): Price ID
        product_id (str): Product ID
        unit_amount (int): Price amount in cents
        currency (str): Price currency
        active (bool): Whether the price is active
        metadata (Optional[Dict[str, Any]]): Additional metadata
        
    Returns:
        Dict[str, Any]: A mock price object
    """
    price_id = id or f"price_mock_{uuid.uuid4().hex[:8]}"
    
    return {
        'id': price_id,
        'object': 'price',
        'active': active,
        'billing_scheme': 'per_unit',
        'created': int(time.time()),
        'currency': currency,
        'product': product_id,
        'type': 'one_time',
        'unit_amount': unit_amount,
        'metadata': metadata or {}
    }


def create_mock_products_with_prices(count: int = 3) -> List[Dict[str, Any]]:
    """
    Create a list of mock products with associated prices.
    
    Args:
        count (int): Number of products to create
        
    Returns:
        List[Dict[str, Any]]: List of mock products with prices
    """
    products = []
    for i in range(count):
        product_id = f"prod_mock_{i}"
        product = create_mock_product(
            id=product_id,
            name=f"Mock Product {i}",
            description=f"Description for mock product {i}"
        )
        
        # Add prices to the product
        product['prices'] = [
            create_mock_price(
                product_id=product_id,
                unit_amount=1000 * (i + 1),
                currency='usd'
            ),
            create_mock_price(
                product_id=product_id,
                unit_amount=900 * (i + 1),
                currency='eur'
            )
        ]
        
        products.append(product) 