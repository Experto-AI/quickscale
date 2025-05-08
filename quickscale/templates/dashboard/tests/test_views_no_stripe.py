"""
Tests for dashboard views when Stripe is disabled.

These tests verify that the dashboard works correctly
even when STRIPE_ENABLED is set to False.
"""

from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.env_utils import get_env, is_feature_enabled


class DashboardWithoutStripeTestCase(TestCase):
    """Test dashboard functionality when Stripe is disabled."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        super().setUpClass()
        
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
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        super().tearDownClass()
        
        # Clean up test data
        get_user_model().objects.all().delete()
    
    @patch('dashboard.views.is_feature_enabled', return_value=False)
    def test_dashboard_index_loads_without_stripe(self, mock_is_feature_enabled):
        """Test that dashboard index loads when Stripe is disabled."""
        # Login as admin
        self.client.login(email='admin@test.com', password='adminpassword')
        
        # Access the dashboard index
        response = self.client.get(reverse('dashboard:index'))
        
        # Should load successfully
        self.assertEqual(response.status_code, 200)
    
    @patch('dashboard.views.is_feature_enabled', return_value=False)
    def test_product_admin_loads_without_stripe(self, mock_is_feature_enabled):
        """Test that product admin page loads when Stripe is disabled."""
        # Login as admin
        self.client.login(email='admin@test.com', password='adminpassword')
        
        # Access the product admin page
        response = self.client.get(reverse('dashboard:product_admin'))
        
        # Should load successfully
        self.assertEqual(response.status_code, 200)
        
        # Check context
        self.assertIn('stripe_enabled', response.context)
        self.assertFalse(response.context['stripe_enabled'])
        self.assertIn('stripe_available', response.context)
        self.assertFalse(response.context['stripe_available'])
        self.assertIn('products', response.context)
        self.assertEqual(len(response.context['products']), 0)
    
    @patch('dashboard.views.is_feature_enabled', return_value=False)
    def test_product_admin_refresh_error_without_stripe(self, mock_is_feature_enabled):
        """Test that product admin refresh returns error when Stripe is disabled."""
        # Login as admin
        self.client.login(email='admin@test.com', password='adminpassword')
        
        # Try to refresh products
        response = self.client.post(
            reverse('dashboard:product_admin_refresh'),
            content_type='application/json'
        )
        
        # Should return error
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {
                'success': False,
                'error': 'Stripe integration is not enabled or available'
            }
        )