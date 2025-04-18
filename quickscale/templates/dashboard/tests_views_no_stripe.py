"""
Tests for dashboard views when Stripe is disabled.

These tests verify that the dashboard works correctly
even when STRIPE_ENABLED is set to False.
"""

from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model


class DashboardWithoutStripeTestCase(TestCase):
    """Test dashboard functionality when Stripe is disabled."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for the test case."""
        User = get_user_model()
        cls.user = User.objects.create_user(
            email='test@example.com',
            password='password123',
            is_active=True
        )
    
    def setUp(self):
        """Set up before each test."""
        self.client.force_login(self.user)
    
    @override_settings(STRIPE_ENABLED=False)
    def test_dashboard_loads_without_stripe(self):
        """Test that the dashboard loads properly without Stripe."""
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/home.html')
        # Check that Stripe elements are not in the response
        self.assertNotContains(response, 'stripe-')
    
    @override_settings(STRIPE_ENABLED=False)
    def test_subscription_page_without_stripe(self):
        """Test that the subscription page works properly without Stripe."""
        response = self.client.get(reverse('dashboard:subscription'))
        self.assertEqual(response.status_code, 200)
        # Should display a message that subscriptions are not available
        self.assertContains(response, 'not available')
