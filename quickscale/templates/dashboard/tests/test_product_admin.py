"""
Tests for product management admin functionality.
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings
from core.env_utils import get_env, is_feature_enabled

# Check if Stripe is enabled using the same logic as in settings.py
stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
STRIPE_AVAILABLE = False
Product = None

# Only attempt to import from djstripe if Stripe is enabled
if stripe_enabled:
    try:
        from djstripe.models import Product
        STRIPE_AVAILABLE = True
    except ImportError:
        STRIPE_AVAILABLE = False


@patch('dashboard.views.get_env', return_value='true')
class ProductAdminTestCase(TestCase):
    """
    Test cases for the product management admin functionality.
    
    These tests verify that:
    1. The product admin page loads correctly
    2. Only staff users can access the admin page
    3. Products are displayed correctly
    4. The refresh functionality works
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        super().setUpClass()
        
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            return
        
        # Create test users
        User = get_user_model()
        
        # Admin user
        cls.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='adminpassword',
            is_staff=True
        )
        
        # Regular user
        cls.regular_user = User.objects.create_user(
            email='user@test.com',
            password='userpassword'
        )
        
        # Create test products
        cls.product1 = Product.objects.create(
            name='Test Product 1',
            description='This is test product 1',
            base_price=Decimal('19.99'),
            currency='USD',
            status=Product.ACTIVE,
            stripe_product_id='prod_test1'
        )
        
        cls.product2 = Product.objects.create(
            name='Test Product 2',
            description='This is test product 2',
            base_price=Decimal('29.99'),
            currency='USD',
            status=Product.INACTIVE,
            stripe_product_id='prod_test2'
        )
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        super().tearDownClass()
        
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            return
        
        # Clean up test data
        Product.objects.all().delete()
        get_user_model().objects.all().delete()
    
    def test_product_admin_page_requires_staff(self, mock_getenv):
        """Test that only staff users can access the product admin page."""
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            self.skipTest("Stripe is not available")
        
        # Try accessing as regular user
        self.client.login(email='user@test.com', password='userpassword')
        response = self.client.get(reverse('dashboard:product_admin'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login
        
        # Try accessing as admin user
        self.client.login(email='admin@test.com', password='adminpassword')
        response = self.client.get(reverse('dashboard:product_admin'))
        self.assertEqual(response.status_code, 200)  # Should load successfully
    
    def test_product_admin_displays_products(self, mock_getenv):
        """Test that products are displayed correctly on the admin page."""
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            self.skipTest("Stripe is not available")
        
        # Login as admin
        self.client.login(email='admin@test.com', password='adminpassword')
        
        # Access the product admin page
        response = self.client.get(reverse('dashboard:product_admin'))
        
        # Check that products are in the context
        self.assertIn('products', response.context)
        self.assertEqual(len(response.context['products']), 2)
        
        # Check that both products are displayed
        self.assertContains(response, 'Test Product 1')
        self.assertContains(response, 'Test Product 2')
        self.assertContains(response, '$19.99')
        self.assertContains(response, '$29.99')
        
        # Check that Stripe IDs are displayed
        self.assertContains(response, 'prod_test1')
        self.assertContains(response, 'prod_test2')
    
    @patch('djstripe.services.ProductService.sync_all_from_stripe')
    def test_product_admin_refresh_functionality(self, mock_sync, mock_getenv):
        """Test that the refresh functionality works correctly."""
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            self.skipTest("Stripe is not available")
        
        # Set up mock
        mock_sync.return_value = 3  # Pretend we synced 3 products
        
        # Login as admin
        self.client.login(email='admin@test.com', password='adminpassword')
        
        # Test the refresh endpoint
        response = self.client.post(
            reverse('dashboard:product_admin_refresh'),
            content_type='application/json'
        )
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {'success': True, 'message': 'Successfully synced 3 products from Stripe'}
        )
        
        # Verify the mock was called
        mock_sync.assert_called_once()
    
    def test_product_admin_refresh_requires_post(self, mock_getenv):
        """Test that refresh endpoint only accepts POST requests."""
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            self.skipTest("Stripe is not available")
        
        # Login as admin
        self.client.login(email='admin@test.com', password='adminpassword')
        
        # Try a GET request
        response = self.client.get(reverse('dashboard:product_admin_refresh'))
        
        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)
        self.assertJSONEqual(
            response.content,
            {'error': 'Method not allowed'}
        )