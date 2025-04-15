"""
Tests for Stripe signal handlers.

These tests verify that the Stripe signal handlers work correctly.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

User = get_user_model()


@override_settings(STRIPE_TEST_MODE=True)
class StripeCustomerSignalTest(TestCase):
    """Test the signal handler for creating Stripe customers."""
    
    def setUp(self):
        """Set up test case with environment variables and mocks."""
        # Set up environment variables for test
        self.env_patcher = patch.dict(os.environ, {
            'STRIPE_ENABLED': 'true',
            'STRIPE_TEST_MODE': 'true'
        })
        self.env_patcher.start()
        
        # Mock the stripe module
        self.stripe_mock = MagicMock()
        self.stripe_mock.customers.create.return_value = MagicMock(id='cus_mock_12345')
        self.stripe_mock.api_key = None
        
        self.stripe_patcher = patch('djstripe.utils.get_stripe', return_value=self.stripe_mock)
        self.get_stripe_mock = self.stripe_patcher.start()
        
        # Mock the settings
        self.settings_patcher = patch('django.conf.settings')
        self.settings_mock = self.settings_patcher.start()
        self.settings_mock.STRIPE_SECRET_KEY = 'sk_test_mock'
    
    def tearDown(self):
        """Clean up patchers."""
        self.env_patcher.stop()
        self.stripe_patcher.stop()
        self.settings_patcher.stop()
    
    def test_customer_created_on_user_creation(self):
        """Test that a Stripe customer is created when a new user is created."""
        # Create a new user to trigger the signal
        user = User.objects.create_user(
            email='testuser@example.com',
            password='testpassword'
        )
        
        # Check that stripe.customers.create was called with the right arguments
        self.stripe_mock.customers.create.assert_called_once()
        args, kwargs = self.stripe_mock.customers.create.call_args
        
        # Check that the customer was created with the right email
        self.assertEqual(kwargs['email'], 'testuser@example.com')
        self.assertIn('user_id', kwargs['metadata'])
        
        # Check that the API key was set
        self.assertEqual(self.stripe_mock.api_key, 'sk_test_mock')
    
    @patch.dict(os.environ, {'STRIPE_ENABLED': 'false'})
    def test_customer_not_created_when_stripe_disabled(self):
        """Test that a Stripe customer is not created when Stripe is disabled."""
        # Create a new user
        user = User.objects.create_user(
            email='disabledtest@example.com',
            password='testpassword'
        )
        
        # Check that stripe.customers.create was not called
        self.stripe_mock.customers.create.assert_not_called()
    
    @patch('djstripe.utils.get_stripe', return_value=None)
    def test_customer_not_created_when_stripe_unavailable(self, mock_get_stripe):
        """Test that a Stripe customer is not created when Stripe is unavailable."""
        # Create a new user
        user = User.objects.create_user(
            email='unavailabletest@example.com',
            password='testpassword'
        )
        
        # Check that stripe.customers.create was not called (using our original mock)
        self.stripe_mock.customers.create.assert_not_called()
    
    def test_customer_links_to_user(self):
        """Test that the created Stripe customer is linked to the user."""
        # Create a mock for the StripeCustomer model
        stripe_customer_mock = MagicMock()
        
        with patch('users.models.StripeCustomer.objects.create', 
                   return_value=stripe_customer_mock) as create_mock:
            # Create a new user to trigger the signal
            user = User.objects.create_user(
                email='linkedtest@example.com',
                password='testpassword'
            )
            
            # Check that StripeCustomer.objects.create was called with right arguments
            create_mock.assert_called_once()
            args, kwargs = create_mock.call_args
            
            # Check that the customer was created for the right user
            self.assertEqual(kwargs['user'], user)
            self.assertEqual(kwargs['stripe_id'], 'cus_mock_12345') 