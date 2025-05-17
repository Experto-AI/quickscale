"""Tests for product management admin functionality."""

import os
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings

from core.env_utils import get_env, is_feature_enabled
from users.models import CustomUser
from stripe_manager.stripe_manager import StripeManager

# Check if Stripe is enabled using the same logic as in settings.py
stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
STRIPE_AVAILABLE = False

try:
    from stripe.stripe_manager import get_stripe_manager
    stripe_manager = get_stripe_manager()
    STRIPE_AVAILABLE = not stripe_manager.is_mock_mode
except ImportError:
    STRIPE_AVAILABLE = False

# Skip tests if Stripe is not available
if STRIPE_AVAILABLE:
    class ProductAdminTestCase(TestCase):
        """Test cases for product management in the admin."""
        
        @classmethod
        def setUpTestData(cls) -> None:
            """Set up test data for all test methods."""
            User = get_user_model()
            cls.admin_user = User.objects.create_superuser(
                email='admin@example.com',
                password='adminpassword',
                is_active=True
            )
            
            # Mock Stripe product using StripeManager
            cls.product = stripe_manager.create_product(
                name='Test Product',
                description='A test product',
                metadata={'price': '9.99'}
            )
        
        def setUp(self) -> None:
            """Set up before each test."""
            self.client.force_login(self.admin_user)
        
        @patch('stripe.stripe_manager.StripeManager.list_products')
        def test_product_list_view(self, mock_list_products) -> None:
            """Test the product list view in admin."""
            # Mock the list_products method to return our test product
            mock_list_products.return_value = [{
                'id': self.product['id'],
                'name': 'Test Product',
                'description': 'A test product',
                'active': True,
                'metadata': {'price': '9.99'}
            }]
            
            url = reverse('stripe:product_list')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Test Product')
        
        @patch('stripe.stripe_manager.StripeManager.retrieve_product')
        @patch('stripe.stripe_manager.StripeManager.get_product_prices')
        def test_product_detail_view(self, mock_get_prices, mock_retrieve_product) -> None:
            """Test the product detail view in admin."""
            # Mock the retrieve_product method
            mock_retrieve_product.return_value = {
                'id': self.product['id'],
                'name': 'Test Product',
                'description': 'A test product',
                'active': True,
                'metadata': {'price': '9.99'}
            }
            
            # Mock the get_product_prices method
            mock_get_prices.return_value = [{
                'id': 'price_123',
                'product': self.product['id'],
                'unit_amount': 999,
                'currency': 'usd',
                'active': True
            }]
            
            url = reverse('stripe:product_detail', args=[self.product['id']])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Test Product')
            self.assertContains(response, 'A test product')
