"""
Tests for product management admin functionality.
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings
import os

# Check if Stripe is enabled using the same logic as in settings.py
stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))= None

# Only attempt to import from djstripe if Stripe is enabled
if stripe_enabled:
    try:
        from djstripe.models import Product
        STRIPE_AVAILABLE = True
    except ImportError:
        pass

# Skip tests if Stripe is not available
if STRIPE_AVAILABLE:
    class ProductAdminTestCase(TestCase):
        """Test cases for product management in the admin."""
        
        @classmethod
        def setUpTestData(cls):
            """Set up test data for all test methods."""
            User = get_user_model()
            cls.admin_user = User.objects.create_superuser(
                email='admin@example.com',
                password='adminpassword',
                is_active=True
            )
            
            # Mock Stripe product
            cls.product = Product.objects.create(
                id='prod_test123',
                name='Test Product',
                description='A test product',
                active=True,
                metadata={'price': '9.99'}
            )
        
        def setUp(self):
            """Set up before each test."""
            self.client.force_login(self.admin_user)
        
        def test_product_list_view(self):
            """Test the product list view in admin."""
            url = reverse('admin:djstripe_product_changelist')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Test Product')
        
        def test_product_detail_view(self):
            """Test the product detail view in admin."""
            url = reverse('admin:djstripe_product_change', args=[self.product.id])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Test Product')
            self.assertContains(response, 'A test product')
