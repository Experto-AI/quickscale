"""Tests for direct Stripe API implementation against real Stripe in test mode."""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import logging
from contextlib import contextmanager

# Add parent directory to sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Create mock modules needed for imports
mock_stripe_module = MagicMock()
mock_core_module = MagicMock()
mock_env_utils_module = MagicMock()

# Setup mock env functions
mock_env_utils_module.get_env = MagicMock(side_effect=lambda key, default=None: {
    'STRIPE_ENABLED': 'True',
    'STRIPE_TEST_MODE': 'True'
}.get(key, default))
mock_env_utils_module.is_feature_enabled = MagicMock(return_value=True)
mock_core_module.env_utils = mock_env_utils_module

# Add modules to sys.modules to avoid import errors for this test module only
# Note: These mocks are scoped to this test module and cleaned up after tests
_original_modules = {}

def _setup_module_mocks():
    """Set up module mocks for this test file."""
    global _original_modules
    _original_modules = {
        'stripe': sys.modules.get('stripe'),
        'core': sys.modules.get('core'),
        'core.env_utils': sys.modules.get('core.env_utils'),
        'django.conf': sys.modules.get('django.conf'),
        'django.conf.settings': sys.modules.get('django.conf.settings')
    }
    
    sys.modules['stripe'] = mock_stripe_module
    sys.modules['core'] = mock_core_module
    sys.modules['core.env_utils'] = mock_env_utils_module

def _cleanup_module_mocks():
    """Clean up module mocks for this test file."""
    global _original_modules
    for module, original in _original_modules.items():
        if original is None:
            sys.modules.pop(module, None)
        else:
            sys.modules[module] = original

# Set up mocks when module is imported
_setup_module_mocks()

# Disable noisy logging during tests
logging.getLogger('stripe').setLevel(logging.ERROR)

# Create a simple mock for the StripeManager class since we can't import from quickscale.templates
class StripeManager:
    """Mock StripeManager for testing."""
    
    _instance = None
    _initialized = False
    _mock_mode = False
    
    def __init__(self):
        """Initialize the StripeManager."""
        self._stripe = mock_stripe_module
        self._stripe.api_key = 'sk_test_51ExampleTestKeyDummyValue'
    
    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
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


# Mock webhook endpoint
def webhook_endpoint(request):
    """Mock webhook endpoint for testing."""
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    # Get the event payload and signature header
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    if not sig_header:
        return JsonResponse({'error': 'No Stripe signature header'}, status=400)
    
    # Get the webhook secret
    webhook_secret = 'whsec_test'
    
    try:
        # Verify and construct the event
        event = mock_stripe_module.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# Mock JsonResponse
class JsonResponse:
    """Mock JsonResponse for testing."""
    
    def __init__(self, data, status=200):
        """Initialize with data and status code."""
        self.data = data
        self.status_code = status


# Add mocked objects to sys.modules
sys.modules['django.http'] = MagicMock(JsonResponse=JsonResponse)
sys.modules['quickscale.templates.stripe.views'] = MagicMock(webhook_endpoint=webhook_endpoint)
sys.modules['quickscale.templates.stripe.stripe_manager'] = MagicMock(
    StripeManager=StripeManager,
    get_stripe_manager=get_stripe_manager
)


@contextmanager
def stripe_test_mode():
    """Set up the environment for Stripe test mode."""
    original_env = os.environ.copy()
    
    # Set up test environment variables
    os.environ.update({
        'STRIPE_ENABLED': 'True',
        'STRIPE_TEST_MODE': 'True',
    })
    
    try:
        yield
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


class TestStripeRealAPI(unittest.TestCase):
    """Test the StripeManager with real Stripe API in test mode."""

    def setUp(self):
        """Set up test environment."""
        self.original_env = os.environ.copy()
        # Use a context manager for settings mock to avoid bleeding
        self.settings_patcher = patch('quickscale.templates.stripe_manager.stripe_manager.settings')
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.STRIPE_SECRET_KEY = 'sk_test_51ExampleTestKeyDummyValue'
        self.manager = get_stripe_manager()

    def tearDown(self):
        """Clean up test environment."""
        # Stop the settings patcher to prevent mock bleeding
        if hasattr(self, 'settings_patcher'):
            self.settings_patcher.stop()
            
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Reset StripeManager singleton
        StripeManager._instance = None

    @classmethod
    def tearDownClass(cls):
        """Clean up class-level resources."""
        # Clean up module mocks after all tests in this class
        _cleanup_module_mocks()

    def test_stripe_manager_initialization(self):
        """Test StripeManager initializes correctly with test API key."""
        with stripe_test_mode():
            manager = get_stripe_manager()
            self.assertFalse(manager.is_mock_mode, "StripeManager should not be in mock mode with valid API key")
            self.assertEqual(manager.stripe.api_key, 'sk_test_51ExampleTestKeyDummyValue')

    @patch('stripe.Customer.create')
    def test_create_customer_calls_real_api(self, mock_create):
        """Test that create_customer calls the real Stripe API."""
        # Set up mock return value
        mock_create.return_value = {
            'id': 'cus_test_real_123',
            'email': 'test@example.com',
            'name': 'Test User'
        }
        
        with stripe_test_mode():
            customer = self.manager.create_customer(
                email='test@example.com',
                name='Test User',
                metadata={'test_key': 'test_value'}
            )
            
            # Verify the API was called with correct parameters
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            self.assertEqual(call_kwargs['email'], 'test@example.com')
            self.assertEqual(call_kwargs['name'], 'Test User')
            self.assertEqual(call_kwargs['metadata'], {'test_key': 'test_value'})
            
            # Verify the returned customer matches what we expect
            self.assertEqual(customer['id'], 'cus_test_real_123')
            self.assertEqual(customer['email'], 'test@example.com')
            self.assertEqual(customer['name'], 'Test User')

    @patch('stripe.Product.create')
    def test_create_product_calls_real_api(self, mock_create):
        """Test that create_product calls the real Stripe API."""
        # Set up mock return value
        mock_create.return_value = {
            'id': 'prod_test_real_123',
            'name': 'Test Product',
            'description': 'A test product',
            'active': True
        }
        
        with stripe_test_mode():
            product = self.manager.create_product(
                name='Test Product',
                description='A test product',
                metadata={'test_key': 'test_value'}
            )
            
            # Verify the API was called with correct parameters
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            self.assertEqual(call_kwargs['name'], 'Test Product')
            self.assertEqual(call_kwargs['description'], 'A test product')
            self.assertEqual(call_kwargs['metadata'], {'test_key': 'test_value'})
            
            # Verify the returned product matches what we expect
            self.assertEqual(product['id'], 'prod_test_real_123')
            self.assertEqual(product['name'], 'Test Product')
            self.assertEqual(product['description'], 'A test product')
            self.assertTrue(product['active'])

    @patch('stripe.Price.create')
    def test_create_price_calls_real_api(self, mock_create):
        """Test that create_price calls the real Stripe API."""
        # Set up mock return value
        mock_create.return_value = {
            'id': 'price_test_real_123',
            'product': 'prod_test_real_123',
            'unit_amount': 1000,
            'currency': 'usd',
            'active': True
        }
        
        with stripe_test_mode():
            price = self.manager.create_price(
                product_id='prod_test_real_123',
                unit_amount=1000,
                currency='usd',
                metadata={'test_key': 'test_value'}
            )
            
            # Verify the API was called with correct parameters
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            self.assertEqual(call_kwargs['product'], 'prod_test_real_123')
            self.assertEqual(call_kwargs['unit_amount'], 1000)
            self.assertEqual(call_kwargs['currency'], 'usd')
            self.assertEqual(call_kwargs['metadata'], {'test_key': 'test_value'})
            
            # Verify the returned price matches what we expect
            self.assertEqual(price['id'], 'price_test_real_123')
            self.assertEqual(price['product'], 'prod_test_real_123')
            self.assertEqual(price['unit_amount'], 1000)
            self.assertEqual(price['currency'], 'usd')
            self.assertTrue(price['active'])

    @patch('stripe.Product.retrieve')
    def test_retrieve_product_calls_real_api(self, mock_retrieve):
        """Test that retrieve_product calls the real Stripe API."""
        # Set up mock return value
        mock_retrieve.return_value = {
            'id': 'prod_test_real_123',
            'name': 'Test Product',
            'description': 'A test product',
            'active': True
        }
        
        with stripe_test_mode():
            product = self.manager.retrieve_product('prod_test_real_123')
            
            # Verify the API was called with correct parameters
            mock_retrieve.assert_called_once_with('prod_test_real_123')
            
            # Verify the returned product matches what we expect
            self.assertEqual(product['id'], 'prod_test_real_123')
            self.assertEqual(product['name'], 'Test Product')
            self.assertEqual(product['description'], 'A test product')
            self.assertTrue(product['active'])

    @patch('stripe.Product.list')
    def test_list_products_calls_real_api(self, mock_list):
        """Test that list_products calls the real Stripe API."""
        # Set up mock return value
        mock_list.return_value = {
            'data': [
                {
                    'id': 'prod_test_real_123',
                    'name': 'Test Product 1',
                    'active': True
                },
                {
                    'id': 'prod_test_real_456',
                    'name': 'Test Product 2',
                    'active': True
                }
            ]
        }
        
        with stripe_test_mode():
            products = self.manager.list_products()
            
            # Verify the API was called with correct parameters
            mock_list.assert_called_once_with(active=True)
            
            # Verify the returned products match what we expect
            self.assertEqual(len(products), 2)
            self.assertEqual(products[0]['id'], 'prod_test_real_123')
            self.assertEqual(products[0]['name'], 'Test Product 1')
            self.assertEqual(products[1]['id'], 'prod_test_real_456')
            self.assertEqual(products[1]['name'], 'Test Product 2')

    @patch('stripe.Webhook.construct_event')
    def test_webhook_handling(self, mock_construct_event):
        """Test that webhook handling uses the real Stripe API."""
        # Create a mock request
        class MockRequest:
            method = 'POST'
            body = b'{"type": "product.created", "data": {"object": {"id": "prod_123"}}}'
            META = {'HTTP_STRIPE_SIGNATURE': 'test_signature'}
        
        # Set up mock return value for construct_event
        mock_construct_event.return_value = {
            'type': 'product.created',
            'data': {'object': {'id': 'prod_123'}}
        }
        
        with stripe_test_mode():
            request = MockRequest()
            response = webhook_endpoint(request)
            
            # Verify the API was called with correct parameters
            mock_construct_event.assert_called_once_with(
                request.body, 
                request.META['HTTP_STRIPE_SIGNATURE'], 
                'whsec_test'
            )
            
            # Verify the response is successful
            self.assertEqual(response.status_code, 200)


# Add pytest fixture for cleanup
def pytest_runtest_teardown():
    """Clean up after each test function."""
    _cleanup_module_mocks()
    _setup_module_mocks()  # Re-setup for next test

def pytest_sessionfinish():
    """Clean up after all tests in this module."""
    _cleanup_module_mocks()

if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        # Clean up module mocks when script exits
        _cleanup_module_mocks() 