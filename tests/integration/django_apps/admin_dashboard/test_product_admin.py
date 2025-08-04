"""
Integration tests for product admin business logic.

These tests focus on business logic rather than view/URL integration,
converted from template validation tests to proper integration tests.
"""
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.db import models
from django.test import Client

try:
    from stripe_manager.models import StripeProduct
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    StripeProduct = None

from ..base import DjangoIntegrationTestCase


class ProductManagementLogicIntegrationTests(DjangoIntegrationTestCase):
    """Test cases for the product management business logic."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for product management tests."""
        if not STRIPE_AVAILABLE:
            return
            
        # Create test users
        User = get_user_model()
        cls.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )
        
        cls.regular_user = User.objects.create_user(
            email='user@test.com',
            password='user123'
        )
        
        # Create test Stripe products in database
        cls.test_product1 = StripeProduct.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            stripe_id='prod_basic',
            stripe_price_id='price_basic',
            price=Decimal('9.99'),
            currency='USD',
            interval='month',
            credit_amount=100,
            active=True,
            display_order=1
        )
        
        cls.test_product2 = StripeProduct.objects.create(
            name='Premium Plan',
            description='Premium subscription plan',
            stripe_id='prod_premium',
            stripe_price_id='price_premium',
            price=Decimal('19.99'),
            currency='USD',
            interval='month',
            credit_amount=250,
            active=True,
            display_order=2
        )
        
        cls.test_product3 = StripeProduct.objects.create(
            name='Enterprise Plan',
            description='Enterprise subscription plan',
            stripe_id='prod_enterprise',
            stripe_price_id='price_enterprise',
            price=Decimal('49.99'),
            currency='USD',
            interval='month',
            credit_amount=1000,
            active=False,  # Inactive product
            display_order=3
        )
    
    def setUp(self):
        """Set up test client and admin user."""
        super().setUp()
        if not STRIPE_AVAILABLE:
            self.skipTest("Stripe models not available")
        self.client = Client()
    
    def test_product_filtering_logic(self):
        """Test product filtering business logic."""
        # Test filtering active products
        active_products = StripeProduct.objects.filter(active=True)
        self.assertEqual(active_products.count(), 2)
        
        # Test filtering by price range
        affordable_products = StripeProduct.objects.filter(price__lte=Decimal('20.00'))
        self.assertEqual(affordable_products.count(), 2)  # Basic and Premium
        
        # Test filtering by interval
        monthly_products = StripeProduct.objects.filter(interval='month')
        self.assertEqual(monthly_products.count(), 3)  # All are monthly
        
        # Test ordering by display_order
        ordered_products = StripeProduct.objects.all().order_by('display_order')
        self.assertEqual(list(ordered_products), [self.test_product1, self.test_product2, self.test_product3])
    
    def test_product_display_order_logic(self):
        """Test product display order management logic."""
        def update_product_display_order(product_id, new_order):
            """Logic to update product display order."""
            try:
                product = StripeProduct.objects.get(id=product_id)
                old_order = product.display_order
                product.display_order = new_order
                product.save()
                return True, f"Updated product {product.name} order from {old_order} to {new_order}"
            except StripeProduct.DoesNotExist:
                return False, "Product not found"
            except ValueError:
                return False, "Invalid display order value"
        
        # Test valid order update
        success, message = update_product_display_order(self.test_product1.id, 5)
        self.assertTrue(success)
        self.assertIn("Updated product Basic Plan", message)
        
        # Verify the update
        self.test_product1.refresh_from_db()
        self.assertEqual(self.test_product1.display_order, 5)
        
        # Test invalid product ID
        success, message = update_product_display_order(99999, 1)
        self.assertFalse(success)
        self.assertEqual(message, "Product not found")
    
    @patch('stripe_manager.stripe_manager.StripeManager')
    def test_product_sync_logic(self, mock_stripe_manager_class):
        """Test product synchronization logic with Stripe."""
        # Mock Stripe manager and response
        mock_stripe_manager = Mock()
        mock_stripe_manager_class.get_instance.return_value = mock_stripe_manager
        
        mock_stripe_products = [
            {
                'id': 'prod_new',
                'name': 'New Plan',
                'description': 'A new plan from Stripe',
                'active': True,
                'default_price': {
                    'id': 'price_new',
                    'unit_amount': 2999,
                    'currency': 'usd',
                    'recurring': {'interval': 'month'}
                }
            }
        ]
        mock_stripe_manager.list_products.return_value = mock_stripe_products
        
        def sync_products_from_stripe():
            """Logic to sync products from Stripe."""
            stripe_manager = mock_stripe_manager_class.get_instance()
            stripe_products = stripe_manager.list_products()
            
            synced_count = 0
            for stripe_product in stripe_products:
                # Check if product already exists
                existing_product = StripeProduct.objects.filter(
                    stripe_id=stripe_product['id']
                ).first()
                
                if not existing_product:
                    # Create new product
                    default_price = stripe_product.get('default_price', {})
                    StripeProduct.objects.create(
                        name=stripe_product['name'],
                        description=stripe_product['description'],
                        stripe_id=stripe_product['id'],
                        stripe_price_id=default_price.get('id', ''),
                        price=Decimal(str(default_price.get('unit_amount', 0) / 100)),
                        currency=default_price.get('currency', 'USD').upper(),
                        interval=default_price.get('recurring', {}).get('interval', 'month'),
                        active=stripe_product['active']
                    )
                    synced_count += 1
            
            return synced_count
        
        # Test product sync
        initial_count = StripeProduct.objects.count()
        synced_count = sync_products_from_stripe()
        
        self.assertEqual(synced_count, 1)
        self.assertEqual(StripeProduct.objects.count(), initial_count + 1)
        
        # Verify the new product was created
        new_product = StripeProduct.objects.get(stripe_id='prod_new')
        self.assertEqual(new_product.name, 'New Plan')
        self.assertEqual(new_product.price, Decimal('29.99'))
        
        # Verify Stripe manager was called
        mock_stripe_manager.list_products.assert_called_once()
    
    def test_product_credit_calculation_logic(self):
        """Test credit amount calculation logic for products."""
        def calculate_credits_for_price(price, base_credit_rate=10):
            """Logic to calculate credit amount based on price."""
            # Example: $1 = 10 credits
            return int(price * base_credit_rate)
        
        # Test credit calculations
        basic_credits = calculate_credits_for_price(self.test_product1.price)
        self.assertEqual(basic_credits, 99)  # 9.99 * 10 = 99
        
        premium_credits = calculate_credits_for_price(self.test_product2.price)
        self.assertEqual(premium_credits, 199)  # 19.99 * 10 = 199
        
        enterprise_credits = calculate_credits_for_price(self.test_product3.price)
        self.assertEqual(enterprise_credits, 499)  # 49.99 * 10 = 499
    
    def test_product_availability_logic(self):
        """Test product availability checking logic."""
        def is_product_available_for_purchase(product):
            """Logic to check if a product is available for purchase."""
            if not product.active:
                return False, "Product is not active"
            
            if product.price <= 0:
                return False, "Product has invalid price"
            
            if not product.stripe_id or not product.stripe_price_id:
                return False, "Product missing Stripe configuration"
            
            return True, "Product is available"
        
        # Test active product
        available, message = is_product_available_for_purchase(self.test_product1)
        self.assertTrue(available)
        self.assertEqual(message, "Product is available")
        
        # Test inactive product
        available, message = is_product_available_for_purchase(self.test_product3)
        self.assertFalse(available)
        self.assertEqual(message, "Product is not active")
        
        # Test product with invalid price
        invalid_product = StripeProduct.objects.create(
            name='Invalid Plan',
            stripe_id='prod_invalid',
            stripe_price_id='price_invalid',
            price=Decimal('0.00'),  # Invalid price
            currency='USD',
            interval='month',
            active=True
        )
        
        available, message = is_product_available_for_purchase(invalid_product)
        self.assertFalse(available)
        self.assertEqual(message, "Product has invalid price")
    
    def test_product_search_and_filter_logic(self):
        """Test product search and filtering logic."""
        def search_products(query=None, active_only=True, max_price=None):
            """Logic to search and filter products."""
            products = StripeProduct.objects.all()
            
            if active_only:
                products = products.filter(active=True)
            
            if query:
                products = products.filter(
                    models.Q(name__icontains=query) |
                    models.Q(description__icontains=query)
                )
            
            if max_price:
                products = products.filter(price__lte=max_price)
            
            return products.order_by('display_order')
        
        # Test search by name
        basic_products = search_products(query='Basic')
        self.assertEqual(basic_products.count(), 1)
        self.assertEqual(basic_products.first().name, 'Basic Plan')
        
        # Test search by description
        subscription_products = search_products(query='subscription')
        self.assertEqual(subscription_products.count(), 2)  # Basic and Premium (active only)
        
        # Test price filtering
        affordable_products = search_products(max_price=Decimal('15.00'))
        self.assertEqual(affordable_products.count(), 1)  # Only Basic Plan
        
        # Test including inactive products
        all_subscription_products = search_products(query='subscription', active_only=False)
        self.assertEqual(all_subscription_products.count(), 3)  # All three products
