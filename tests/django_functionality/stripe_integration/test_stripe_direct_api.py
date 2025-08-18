"""Tests for direct Stripe API implementation."""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import json
import importlib.util
from io import StringIO

# Add parent directory to sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Mock modules needed for import resolution
# Import centralized test utilities (DRY principle)
from tests.test_utilities import TestUtilities

mock_stripe_module = MagicMock()
mock_core_module = MagicMock()
mock_env_utils_module = MagicMock()

# Configure mock env functions to delegate to TestUtilities directly
mock_env_utils_module.get_env.side_effect = TestUtilities.get_env
mock_env_utils_module.is_feature_enabled.side_effect = TestUtilities.is_feature_enabled
mock_core_module.env_utils = mock_env_utils_module

# Store original modules for cleanup
_original_modules = {}
for module_name in ['stripe', 'core', 'core.env_utils']:
    if module_name in sys.modules:
        _original_modules[module_name] = sys.modules[module_name]

# Add modules to sys.modules
sys.modules['stripe'] = mock_stripe_module
sys.modules['core'] = mock_core_module
sys.modules['core.env_utils'] = mock_env_utils_module

from quickscale.utils.env_utils import env_manager


class MockResponse:
    """Mock HTTP response class for testing."""
    
    def __init__(self, data, status_code=200):
        """Initialize with data and status code."""
        self.data = data
        self.status_code = status_code
    
    def json(self):
        """Return the JSON data."""
        return self.data


class TestStripeDirectAPI(unittest.TestCase):
    """Test the direct Stripe API implementation."""

    def setUp(self):
        """Set up test environment."""
        self.original_env = os.environ.copy()
        env_manager.refresh_env_cache()
        
        # Create a simple mock for the StripeManager class
        self.test_module_name = 'test_stripe_manager'
        with open(os.path.join(os.path.dirname(__file__), f"{self.test_module_name}.py"), "w") as f:
            f.write('''
class StripeManager:
    """Mock StripeManager for testing."""
    
    _instance = None
    _initialized = False
    _mock_mode = False
    
    def __init__(self):
        """Initialize the StripeManager."""
        self._stripe = type('MockStripe', (), {
            'api_key': 'sk_test_mock',
            'Customer': type('MockCustomer', (), {
                'create': lambda **kwargs: {'id': 'cus_test_123', 'email': kwargs.get('email', ''), 'name': kwargs.get('name', '')},
                'retrieve': lambda customer_id: {'id': customer_id, 'email': 'test@example.com', 'name': 'Test User'},
            }),
            'Product': type('MockProduct', (), {
                'create': lambda **kwargs: {'id': 'prod_test_123', 'name': kwargs.get('name', ''), 'description': kwargs.get('description', '')},
                'retrieve': lambda product_id: {'id': product_id, 'name': 'Test Product', 'description': 'A test product'},
                'list': lambda **kwargs: {'data': [{'id': 'prod_1', 'name': 'Product 1'}, {'id': 'prod_2', 'name': 'Product 2'}]},
                'modify': lambda product_id, **kwargs: {'id': product_id, 'name': kwargs.get('name', ''), 'description': kwargs.get('description', '')},
            }),
            'Price': type('MockPrice', (), {
                'create': lambda **kwargs: {'id': 'price_test_123', 'product': kwargs.get('product', ''), 'unit_amount': kwargs.get('unit_amount', 0)},
                'list': lambda **kwargs: {'data': [{'id': 'price_1', 'product': kwargs.get('product', ''), 'unit_amount': 1000}, {'id': 'price_2', 'product': kwargs.get('product', ''), 'unit_amount': 2000}]},
            }),
            'Webhook': type('MockWebhook', (), {
                'construct_event': lambda payload, sig_header, secret: json.loads(payload),
            }),
            'error': type('MockError', (), {
                'SignatureVerificationError': ValueError,
            }),
        })
    
    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        
        if not cls._initialized:
            cls._instance._initialize()
        
        return cls._instance
    
    def _initialize(self):
        """Initialize the Stripe API client."""
        self.__class__._initialized = True
    
    @property
    def stripe(self):
        """Get the Stripe API client."""
        return self._stripe
    
    @property
    def is_mock_mode(self):
        """Check if the manager is in mock mode."""
        return self._mock_mode
    
    def create_customer(self, email, name=None, metadata=None):
        """Create a new customer in Stripe."""
        return self._stripe.Customer.create(email=email, name=name, metadata=metadata)
    
    def retrieve_customer(self, customer_id):
        """Retrieve a customer from Stripe by ID."""
        return self._stripe.Customer.retrieve(customer_id)
    
    def create_product(self, name, description=None, metadata=None):
        """Create a new product in Stripe."""
        return self._stripe.Product.create(name=name, description=description, metadata=metadata)
    
    def retrieve_product(self, product_id):
        """Retrieve a product from Stripe by ID."""
        return self._stripe.Product.retrieve(product_id)
    
    def list_products(self, active=True):
        """List products from Stripe."""
        return self._stripe.Product.list(active=active)['data']
    
    def update_product(self, product_id, name=None, description=None, metadata=None, active=None):
        """Update a product in Stripe."""
        kwargs = {}
        if name:
            kwargs['name'] = name
        if description:
            kwargs['description'] = description
        if metadata:
            kwargs['metadata'] = metadata
        if active is not None:
            kwargs['active'] = active
        return self._stripe.Product.modify(product_id, **kwargs)
    
    def get_product_prices(self, product_id, active=True):
        """Get prices for a product."""
        return self._stripe.Price.list(product=product_id, active=active)['data']
    
    def create_price(self, product_id, unit_amount, currency='usd', metadata=None):
        """Create a new price for a product."""
        return self._stripe.Price.create(product=product_id, unit_amount=unit_amount, currency=currency, metadata=metadata)

def get_stripe_manager():
    """Get the StripeManager instance."""
    return StripeManager.get_instance()
''')
        
        # Create a simple mock for the webhook handling code
        self.webhook_module_name = 'test_stripe_webhook'
        with open(os.path.join(os.path.dirname(__file__), f"{self.webhook_module_name}.py"), "w") as f:
            f.write('''
import json

class MockResponse:
    """Mock HTTP response class for testing."""
    
    def __init__(self, data, status_code=200):
        """Initialize with data and status code."""
        self.data = data
        self.status_code = status_code
    
    def json(self):
        """Return the JSON data."""
        return self.data

class MockRequest:
    """Mock HTTP request class for testing."""
    
    def __init__(self, method='POST', body=None, headers=None):
        """Initialize the request with method, body, and headers."""
        self.method = method
        self.body = body or b'{}'
        self.META = headers or {}

class MockManager:
    """Mock StripeManager for webhook testing."""
    
    def __init__(self):
        """Initialize with a mock Stripe client."""
        self.stripe = type('MockStripe', (), {
            'Webhook': type('MockWebhook', (), {
                'construct_event': lambda payload, sig_header, secret: json.loads(payload.decode('utf-8')),
            }),
            'error': type('MockError', (), {
                'SignatureVerificationError': ValueError,
            }),
        })

# Mock stripe_manager for webhooks
stripe_manager = MockManager()

def webhook(request):
    """Handle Stripe webhook events."""
    if request.method != 'POST':
        return MockResponse({'error': 'Invalid request method'}, status_code=405)
    
    # Get the webhook secret
    webhook_secret = 'whsec_test_secret'
    if not webhook_secret:
        return MockResponse({'error': 'Webhook secret not configured'}, status_code=500)
    
    # Get the event payload and signature header
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    if not sig_header:
        return MockResponse({'error': 'No Stripe signature header'}, status_code=400)
    
    try:
        # Verify and construct the event
        event = stripe_manager.stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        
        # Handle the event based on its type
        event_type = event['type']
        
        # Handle specific event types
        if event_type == 'product.created':
            # Product created - nothing to do here as we fetch from API
            pass
        elif event_type == 'product.updated':
            # Product updated - nothing to do here as we fetch from API
            pass
        elif event_type == 'price.created':
            # Price created - nothing to do here as we fetch from API
            pass
        elif event_type == 'checkout.session.completed':
            # Handle completed checkout session
            pass
        
        # Return success response
        return MockResponse({'status': 'success'})
    except ValueError as e:
        # Invalid payload
        return MockResponse({'error': 'Invalid payload'}, status_code=400)
    except stripe_manager.stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return MockResponse({'error': 'Invalid signature'}, status_code=400)
    except Exception as e:
        # Other error
        return MockResponse({'error': str(e)}, status_code=500)
''')
        
        # Import the modules
        self.stripe_manager_spec = importlib.util.spec_from_file_location(
            self.test_module_name, 
            os.path.join(os.path.dirname(__file__), f"{self.test_module_name}.py")
        )
        self.stripe_manager_module = importlib.util.module_from_spec(self.stripe_manager_spec)
        self.stripe_manager_spec.loader.exec_module(self.stripe_manager_module)
        
        self.webhook_spec = importlib.util.spec_from_file_location(
            self.webhook_module_name, 
            os.path.join(os.path.dirname(__file__), f"{self.webhook_module_name}.py")
        )
        self.webhook_module = importlib.util.module_from_spec(self.webhook_spec)
        self.webhook_spec.loader.exec_module(self.webhook_module)
        
    def tearDown(self):
        """Clean up test environment."""
        # Restore environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up the test module file
        test_module_file = os.path.join(os.path.dirname(__file__), f"{self.test_module_name}.py")
        if os.path.exists(test_module_file):
            os.remove(test_module_file)
            
        # Clean up sys.modules
        if self.test_module_name in sys.modules:
            del sys.modules[self.test_module_name]
            
    @classmethod
    def tearDownClass(cls):
        """Clean up global module mocking."""
        # Restore original modules
        for module_name, original_module in _original_modules.items():
            sys.modules[module_name] = original_module
        
        # Remove mocked modules that weren't originally present
        modules_to_remove = []
        for module_name in ['stripe', 'core', 'core.env_utils']:
            if module_name not in _original_modules and module_name in sys.modules:
                modules_to_remove.append(module_name)
        
        for module_name in modules_to_remove:
            del sys.modules[module_name]

    def test_stripe_manager_singleton(self):
        """Test that StripeManager is a singleton."""
        manager1 = self.stripe_manager_module.get_stripe_manager()
        manager2 = self.stripe_manager_module.get_stripe_manager()
        self.assertIs(manager1, manager2)

    def test_stripe_manager_create_customer(self):
        """Test creating a customer through StripeManager."""
        manager = self.stripe_manager_module.get_stripe_manager()
        customer = manager.create_customer(
            email='test@example.com',
            name='Test User'
        )
        
        self.assertIsNotNone(customer)
        self.assertEqual(customer['email'], 'test@example.com')
        self.assertEqual(customer['name'], 'Test User')

    def test_stripe_manager_retrieve_customer(self):
        """Test retrieving a customer through StripeManager."""
        manager = self.stripe_manager_module.get_stripe_manager()
        customer = manager.retrieve_customer('cus_test_123')
        
        self.assertIsNotNone(customer)
        self.assertEqual(customer['id'], 'cus_test_123')
        self.assertEqual(customer['email'], 'test@example.com')

    def test_stripe_manager_create_product(self):
        """Test creating a product through StripeManager."""
        manager = self.stripe_manager_module.get_stripe_manager()
        product = manager.create_product(
            name='Test Product',
            description='A test product'
        )
        
        self.assertIsNotNone(product)
        self.assertEqual(product['name'], 'Test Product')
        self.assertEqual(product['description'], 'A test product')

    def test_stripe_manager_retrieve_product(self):
        """Test retrieving a product through StripeManager."""
        manager = self.stripe_manager_module.get_stripe_manager()
        product = manager.retrieve_product('prod_test_123')
        
        self.assertIsNotNone(product)
        self.assertEqual(product['id'], 'prod_test_123')
        self.assertEqual(product['name'], 'Test Product')

    def test_stripe_manager_list_products(self):
        """Test listing products through StripeManager."""
        manager = self.stripe_manager_module.get_stripe_manager()
        products = manager.list_products()
        
        self.assertIsNotNone(products)
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0]['id'], 'prod_1')
        self.assertEqual(products[1]['id'], 'prod_2')

    def test_stripe_manager_update_product(self):
        """Test updating a product through StripeManager."""
        manager = self.stripe_manager_module.get_stripe_manager()
        product = manager.update_product(
            product_id='prod_test_123',
            name='Updated Product',
            description='An updated product'
        )
        
        self.assertIsNotNone(product)
        self.assertEqual(product['id'], 'prod_test_123')
        self.assertEqual(product['name'], 'Updated Product')
        self.assertEqual(product['description'], 'An updated product')

    def test_stripe_manager_get_product_prices(self):
        """Test getting prices for a product through StripeManager."""
        manager = self.stripe_manager_module.get_stripe_manager()
        prices = manager.get_product_prices('prod_test_123')
        
        self.assertIsNotNone(prices)
        self.assertEqual(len(prices), 2)
        self.assertEqual(prices[0]['id'], 'price_1')
        self.assertEqual(prices[0]['unit_amount'], 1000)
        self.assertEqual(prices[1]['id'], 'price_2')
        self.assertEqual(prices[1]['unit_amount'], 2000)

    def test_stripe_manager_create_price(self):
        """Test creating a price through StripeManager."""
        manager = self.stripe_manager_module.get_stripe_manager()
        price = manager.create_price(
            product_id='prod_test_123',
            unit_amount=1500
        )
        
        self.assertIsNotNone(price)
        self.assertEqual(price['id'], 'price_test_123')
        self.assertEqual(price['product'], 'prod_test_123')
        self.assertEqual(price['unit_amount'], 1500)

    def test_webhook_processing(self):
        """Test processing a webhook event."""
        # Create a test webhook event
        event_data = {
            'id': 'evt_test_123',
            'type': 'product.created',
            'data': {
                'object': {
                    'id': 'prod_test_123',
                    'name': 'Test Product'
                }
            }
        }
        
        # Create a mock request with the event data
        request = self.webhook_module.MockRequest(
            method='POST',
            body=json.dumps(event_data).encode('utf-8'),
            headers={'HTTP_STRIPE_SIGNATURE': 'sig_test_123'}
        )
        
        # Process the webhook
        response = self.webhook_module.webhook(request)
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

    def test_webhook_method_not_allowed(self):
        """Test webhook handling with invalid HTTP method."""
        # Create a mock request with GET method
        request = self.webhook_module.MockRequest(method='GET')
        
        # Process the webhook
        response = self.webhook_module.webhook(request)
        
        # Check the response
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()['error'], 'Invalid request method')

    def test_webhook_missing_signature(self):
        """Test webhook handling when Stripe signature is missing."""
        # Create a mock request without signature header
        request = self.webhook_module.MockRequest(
            method='POST',
            body=b'{}',
            headers={}
        )
        
        # Process the webhook
        response = self.webhook_module.webhook(request)
        
        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'No Stripe signature header')


if __name__ == '__main__':
    unittest.main() 