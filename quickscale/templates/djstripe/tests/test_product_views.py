"""
Tests for the Product views.
"""

from django.test import TestCase
from django.urls import reverse
from decimal import Decimal
from ..models import Product
from django.contrib.auth import get_user_model

User = get_user_model()


class ProductViewsTests(TestCase):
    """
    Tests for the Product views.
    """
    
    def setUp(self):
        """Set up test data."""
        # Create test products
        self.active_product = Product.objects.create(
            name="Active Product",
            description="This is an active product",
            base_price=Decimal("19.99"),
            currency="USD",
            status=Product.ACTIVE
        )
        
        self.inactive_product = Product.objects.create(
            name="Inactive Product",
            description="This is an inactive product",
            base_price=Decimal("29.99"),
            currency="USD",
            status=Product.INACTIVE
        )
        
        # Create a test user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpassword"
        )
    
    def test_product_list_view(self):
        """Test the product list view."""
        url = reverse('djstripe:product_list')
        response = self.client.get(url)
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check template used
        self.assertTemplateUsed(response, 'djstripe/product_list.html')
        
        # Check that only active products are shown by default
        self.assertIn(self.active_product, response.context['products'])
        self.assertNotIn(self.inactive_product, response.context['products'])
        
        # Check show_inactive context variable
        self.assertFalse(response.context['show_inactive'])
    
    def test_product_list_view_with_inactive(self):
        """Test the product list view with inactive products shown."""
        url = reverse('djstripe:product_list')
        response = self.client.get(f"{url}?show_inactive=true")
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check that both active and inactive products are shown
        self.assertIn(self.active_product, response.context['products'])
        self.assertIn(self.inactive_product, response.context['products'])
        
        # Check show_inactive context variable
        self.assertTrue(response.context['show_inactive'])
    
    def test_product_detail_view(self):
        """Test the product detail view."""
        url = reverse('djstripe:product_detail', args=[self.active_product.id])
        response = self.client.get(url)
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check template used
        self.assertTemplateUsed(response, 'djstripe/product_detail.html')
        
        # Check product in context
        self.assertEqual(response.context['product'], self.active_product)
        
        # Check purchase options for anonymous user
        purchase_options = response.context['purchase_options']
        self.assertFalse(purchase_options['can_purchase'])
        self.assertTrue(purchase_options['login_required'])
    
    def test_product_detail_view_authenticated(self):
        """Test the product detail view for an authenticated user."""
        # Log in the user
        self.client.login(email="test@example.com", password="testpassword")
        
        url = reverse('djstripe:product_detail', args=[self.active_product.id])
        response = self.client.get(url)
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check purchase options for authenticated user
        purchase_options = response.context['purchase_options']
        self.assertTrue(purchase_options['can_purchase'])
        self.assertFalse(purchase_options['login_required'])
        self.assertFalse(purchase_options['has_customer'])
    
    def test_inactive_product_detail_view(self):
        """Test the detail view for an inactive product."""
        url = reverse('djstripe:product_detail', args=[self.inactive_product.id])
        response = self.client.get(url)
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check template used
        self.assertTemplateUsed(response, 'djstripe/product_detail.html')
        
        # Check product in context
        self.assertEqual(response.context['product'], self.inactive_product)
    
    def test_nonexistent_product_detail_view(self):
        """Test the detail view for a nonexistent product."""
        url = reverse('djstripe:product_detail', args=[999])  # Nonexistent ID
        response = self.client.get(url)
        
        # Check for 404 response
        self.assertEqual(response.status_code, 404) 