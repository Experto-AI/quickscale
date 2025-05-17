"""Tests for StripeManager class."""

import os
import sys
from unittest.mock import patch, MagicMock, PropertyMock

# Configure Django settings first with non-database settings
from django.conf import settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        USE_TZ=True,
        SECRET_KEY="test-key",
        # Stripe-specific settings
        STRIPE_SECRET_KEY="sk_test_123",
        STRIPE_PUBLIC_KEY="pk_test_123",
        STRIPE_WEBHOOK_SECRET="whsec_test_123",
        STRIPE_ENABLED=True,
        # Add database settings at configuration time, not dynamically
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

# Import mock_env_utils before importing StripeManager
from quickscale.templates.stripe.tests.mock_env_utils import get_env, is_feature_enabled

# Create a mock for 'core.env_utils' module
mock_env_utils = MagicMock()
mock_env_utils.get_env = get_env
mock_env_utils.is_feature_enabled = is_feature_enabled
sys.modules['core.env_utils'] = mock_env_utils

# Now import Django test utilities
from django.test import TestCase

# Now import the module directly
# from quickscale.templates.stripe import stripe_manager as stripe_manager_module # Removed redundant import
# from quickscale.templates.stripe.stripe_manager import StripeManager, get_stripe_manager, StripeConfigurationError # Removed incorrect imports
from quickscale.templates.stripe_manager.stripe_manager import StripeManager, StripeConfigurationError # Corrected import


class StripeManagerTest(TestCase):
    """Test the StripeManager class functionality."""
    
    def setUp(self) -> None:
        """Set up test environment."""
        # Patch environment settings - do this first before getting manager
        self.env_patcher = patch.dict(os.environ, {
            'STRIPE_ENABLED': 'true',
            'STRIPE_SECRET_KEY': 'sk_test_123',
            'STRIPE_PUBLIC_KEY': 'pk_test_123',
            'STRIPE_WEBHOOK_SECRET': 'whsec_test_123'
        })
        self.env_patcher.start()
        
        # Mock the stripe module before getting manager
        self.stripe_mock = MagicMock()
        self.stripe_mock.api_key = None
        
        # Patch the stripe import in StripeManager
        self.stripe_import_patcher = patch.object(stripe_manager_module, 'stripe', self.stripe_mock)
        self.stripe_import_mock = self.stripe_import_patcher.start()

        # Patch settings.STRIPE_SECRET_KEY to ensure it's available
        self.settings_patcher = patch.object(settings, 'STRIPE_SECRET_KEY', 'sk_test_123')
        self.settings_patcher.start()
        
        # Reset StripeManager singleton state for each test
        StripeManager._instance = None
        StripeManager._initialized = False
        
        # Get a fresh instance using the corrected method
        # self.manager = get_stripe_manager() # Removed incorrect call
        self.manager = StripeManager.get_instance() # Corrected call
    
    def tearDown(self) -> None:
        """Clean up patchers and mocks."""
        self.env_patcher.stop()
        self.stripe_import_patcher.stop()
        self.settings_patcher.stop()
        
        # Reset StripeManager singleton state after each test
        StripeManager._instance = None
        StripeManager._initialized = False
    
    def test_get_instance_singleton(self) -> None:
        """Test that StripeManager is a singleton."""
        # manager1 = get_stripe_manager() # Removed incorrect call
        # manager2 = get_stripe_manager() # Removed incorrect call
        manager1 = StripeManager.get_instance() # Corrected call
        manager2 = StripeManager.get_instance() # Corrected call
        
        self.assertIs(manager1, manager2)
    
    def test_stripe_disabled_raises_error(self) -> None:
        """Test that StripeManager raises StripeConfigurationError when Stripe is disabled."""
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'false'}):
            # Reset StripeManager singleton state
            StripeManager._instance = None
            StripeManager._initialized = False
            
            with self.assertRaises(StripeConfigurationError):
                # get_stripe_manager() # Removed incorrect call
                StripeManager.get_instance() # Corrected call
    
    def test_api_key_missing_raises_error(self) -> None:
        """Test that StripeManager raises StripeConfigurationError when API key is missing."""
        # Mock settings with no API key and patch environment
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}), \
             patch.object(stripe_manager_module, 'settings', MagicMock(spec=['STRIPE_SECRET_KEY'])):
            # Remove the STRIPE_SECRET_KEY attribute
            if hasattr(stripe_manager_module.settings, 'STRIPE_SECRET_KEY'):
                del stripe_manager_module.settings.STRIPE_SECRET_KEY
            
            # Reset StripeManager singleton state
            StripeManager._instance = None
            StripeManager._initialized = False
            
            with self.assertRaises(StripeConfigurationError):
                # get_stripe_manager() # Removed incorrect call
                StripeManager.get_instance() # Corrected call
    
    def test_stripe_package_not_available_raises_error(self) -> None:
        """Test that StripeManager raises StripeConfigurationError when stripe package is not available."""
        # Patch STRIPE_AVAILABLE to False
        with patch.object(stripe_manager_module, 'STRIPE_AVAILABLE', False):
            # Reset StripeManager singleton state
            StripeManager._instance = None
            StripeManager._initialized = False
            
            with self.assertRaises(StripeConfigurationError):
                # get_stripe_manager() # Removed incorrect call
                StripeManager.get_instance() # Corrected call
    
    def test_stripe_property(self) -> None:
        """Test the stripe property."""
        self.assertEqual(self.manager.stripe, self.stripe_mock)
    
    def test_create_customer(self) -> None:
        """Test creating a customer."""
        # Mock the Stripe Customer.create method
        self.stripe_mock.customers.create.return_value = {
            'id': 'cus_test_123',
            'email': 'test@example.com',
            'name': 'Test User'
        }
        
        # Create a customer
        customer = self.manager.create_customer(
            email='test@example.com', 
            name='Test User'
        )
        
        # Check that the Stripe API was called correctly
        self.stripe_mock.customers.create.assert_called_once_with(
            params={'email': 'test@example.com', 'name': 'Test User'}
        )
        
        # Check the returned customer object
        self.assertEqual(customer['id'], 'cus_test_123')
        self.assertEqual(customer['email'], 'test@example.com')
        self.assertEqual(customer['name'], 'Test User')
    
    def test_retrieve_customer(self) -> None:
        """Test retrieving a customer."""
        # Mock the Stripe Customer.retrieve method
        self.stripe_mock.customers.retrieve.return_value = {
            'id': 'cus_test_123',
            'email': 'test@example.com',
            'name': 'Test User'
        }
        
        # Retrieve a customer
        customer = self.manager.retrieve_customer('cus_test_123')
        
        # Check that the Stripe API was called correctly
        self.stripe_mock.customers.retrieve.assert_called_once_with('cus_test_123')
        
        # Check the returned customer object
        self.assertEqual(customer['id'], 'cus_test_123')
        self.assertEqual(customer['email'], 'test@example.com')
        self.assertEqual(customer['name'], 'Test User')
    
    def test_create_product(self) -> None:
        """Test creating a product."""
        # Mock the Stripe Product.create method
        self.stripe_mock.Product.create.return_value = {
            'id': 'prod_test_123',
            'name': 'Test Product',
            'description': 'A test product',
            'active': True
        }
        
        # Create a product
        product = self.manager.create_product(
            name='Test Product',
            description='A test product'
        )
        
        # Check that the Stripe API was called correctly
        self.stripe_mock.Product.create.assert_called_once_with(
            name='Test Product',
            description='A test product'
        )
        
        # Check the returned product object
        self.assertEqual(product['id'], 'prod_test_123')
        self.assertEqual(product['name'], 'Test Product')
        self.assertEqual(product['description'], 'A test product')
        self.assertEqual(product['active'], True)
    
    def test_retrieve_product(self) -> None:
        """Test retrieving a product."""
        # Mock the Stripe Product.retrieve method
        self.stripe_mock.Product.retrieve.return_value = {
            'id': 'prod_test_123',
            'name': 'Test Product',
            'description': 'A test product',
            'active': True
        }
        
        # Retrieve a product
        product = self.manager.retrieve_product('prod_test_123')
        
        # Check that the Stripe API was called correctly
        self.stripe_mock.Product.retrieve.assert_called_once_with('prod_test_123')
        
        # Check the returned product object
        self.assertEqual(product['id'], 'prod_test_123')
        self.assertEqual(product['name'], 'Test Product')
        self.assertEqual(product['description'], 'A test product')
        self.assertEqual(product['active'], True)
    
    def test_list_products(self) -> None:
        """Test listing products."""
        # Mock the Stripe Product.list method
        self.stripe_mock.Product.list.return_value = {
            'data': [
                {
                    'id': 'prod_test_1',
                    'name': 'Product 1',
                    'active': True
                },
                {
                    'id': 'prod_test_2',
                    'name': 'Product 2',
                    'active': False
                }
            ]
        }
        
        # List active products
        products = self.manager.list_products(active=True)
        
        # Check that the Stripe API was called correctly
        self.stripe_mock.Product.list.assert_called_once_with(active=True)
        
        # Check the returned product list
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0]['id'], 'prod_test_1')
        self.assertEqual(products[1]['id'], 'prod_test_2')
    
    def test_update_product(self) -> None:
        """Test updating a product."""
        # Mock the Stripe products.update method
        self.stripe_mock.products.update.return_value = {
            'id': 'prod_test_123',
            'name': 'Updated Product',
            'description': 'An updated product',
            'active': False
        }
        
        # Update a product
        product = self.manager.update_product(
            product_id='prod_test_123',
            name='Updated Product',
            description='An updated product',
            active=False
        )
        
        # Check that the Stripe API was called correctly
        self.stripe_mock.products.update.assert_called_once_with(
            'prod_test_123', 
            params={
                'name': 'Updated Product',
                'description': 'An updated product',
                'active': False
            }
        )
        
        # Check the returned product object
        self.assertEqual(product['id'], 'prod_test_123')
        self.assertEqual(product['name'], 'Updated Product')
        self.assertEqual(product['description'], 'An updated product')
        self.assertEqual(product['active'], False)
    
    def test_get_product_prices(self) -> None:
        """Test getting prices for a product."""
        # Mock the Stripe prices.list method
        self.stripe_mock.prices.list.return_value = {
            'data': [
                {
                    'id': 'price_test_1',
                    'product': 'prod_test_123',
                    'unit_amount': 1000,
                    'currency': 'usd',
                    'active': True
                },
                {
                    'id': 'price_test_2',
                    'product': 'prod_test_123',
                    'unit_amount': 2000,
                    'currency': 'eur',
                    'active': True
                }
            ]
        }
        
        # Get prices for a product
        prices = self.manager.get_product_prices('prod_test_123')
        
        # Check that the Stripe API was called correctly
        self.stripe_mock.prices.list.assert_called_once_with(
            params={'product': 'prod_test_123', 'active': True}
        )
        
        # Check the returned price list
        self.assertEqual(len(prices), 2)
        self.assertEqual(prices[0]['id'], 'price_test_1')
        self.assertEqual(prices[0]['unit_amount'], 1000)
        self.assertEqual(prices[1]['id'], 'price_test_2')
        self.assertEqual(prices[1]['unit_amount'], 2000)
    
    def test_create_price(self) -> None:
        """Test creating a price."""
        # Mock the Stripe prices.create method
        self.stripe_mock.prices.create.return_value = {
            'id': 'price_test_123',
            'product': 'prod_test_123',
            'unit_amount': 1500,
            'currency': 'usd',
            'active': True
        }
        
        # Create a price
        price = self.manager.create_price(
            product_id='prod_test_123',
            unit_amount=1500,
            currency='usd'
        )
        
        # Check that the Stripe API was called correctly
        self.stripe_mock.prices.create.assert_called_once_with(
            params={
                'product': 'prod_test_123',
                'unit_amount': 1500,
                'currency': 'usd'
            }
        )
        
        # Check the returned price object
        self.assertEqual(price['id'], 'price_test_123')
        self.assertEqual(price['product'], 'prod_test_123')
        self.assertEqual(price['unit_amount'], 1500)
        self.assertEqual(price['currency'], 'usd')
    
    def test_error_handling(self) -> None:
        """Test error handling when API calls fail."""
        # Make create_customer method raise an exception
        self.stripe_mock.customers.create.side_effect = Exception("API Error")
        
        # Check that the method properly raises the exception
        with self.assertRaises(Exception):
            self.manager.create_customer(email="test@example.com")
    
    def test_initialization_exceptions(self) -> None:
        """Test that initialization properly raises exceptions for invalid configurations."""
        # Test initializing without API key
        with patch.dict(os.environ, {'STRIPE_ENABLED': 'true'}), \
             patch.object(stripe_manager_module, 'settings', MagicMock(spec=['STRIPE_SECRET_KEY'])):
            # Remove the STRIPE_SECRET_KEY attribute
            if hasattr(stripe_manager_module.settings, 'STRIPE_SECRET_KEY'):
                del stripe_manager_module.settings.STRIPE_SECRET_KEY
            
            # Reset StripeManager singleton state
            StripeManager._instance = None
            StripeManager._initialized = False
            
            # Check that initialization fails due to missing API key
            with self.assertRaises(StripeConfigurationError):
                # get_stripe_manager() # Removed incorrect call
                StripeManager.get_instance() # Corrected call
    
    def test_double_initialization(self) -> None:
        """Test that calling initialize multiple times does nothing after the first."""
        # Ensure singleton is initialized
        # get_stripe_manager() # Removed incorrect call
        StripeManager.get_instance() # Corrected call
        
        # Mock the _initialize method to count calls
        original_initialize = StripeManager._initialize
        
        # Create a spy for the initialize method
        initialize_called = False
        
        def mock_initialize(self):
            nonlocal initialize_called
            initialize_called = True
            return original_initialize(self)
        
        StripeManager._initialize = mock_initialize
        
        # Call get_instance again, initialize should not be called again
        # get_stripe_manager() # Removed incorrect call
        StripeManager.get_instance() # Corrected call
        
        # Assert that _initialize was only called once
        self.assertTrue(initialize_called)
        
        # Call get_instance again, initialize should not be called again
        # manager2 = get_stripe_manager() # Removed incorrect call
        manager2 = StripeManager.get_instance() # Corrected call
        
        # Assert that _initialize was only called once
        self.assertFalse(initialize_called) 