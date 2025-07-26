"""
Tests for the user flows in the plan selection process.
"""
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from stripe_manager.models import StripeProduct


class UserFlowsTest(TestCase):
    """Test the user flows in the plan selection process."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for the test case."""
        # Create test user
        User = get_user_model()
        cls.user = User.objects.create_user(
            email='test@example.com',
            password='testpassword'
        )
        
        # Create a test plan
        cls.plan = StripeProduct.objects.create(
            name="Test Plan",
            price=19.99,
            currency="usd",
            interval="month",
            description="Test plan for integration testing",
            stripe_id="prod_test",
            active=True,
            display_order=1
        )
    
    @override_settings(STRIPE_ENABLED=True)
    def test_authenticated_user_can_view_plans(self):
        """Test that an authenticated user can view the plans."""
        # Log in the user
        self.client.login(email='test@example.com', password='testpassword')
        
        # Access the plan comparison page
        response = self.client.get(reverse('stripe:plan_comparison'))
        
        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)
        
        # Check that the context contains the plans
        self.assertIn('plans', response.context)
        
        # Check that the plan is displayed
        plans = response.context['plans']
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].name, "Test Plan")
    
    @override_settings(STRIPE_ENABLED=True)
    def test_unauthenticated_user_can_view_plans(self):
        """Test that an unauthenticated user can view the plans."""
        # Access the plan comparison page without logging in
        response = self.client.get(reverse('stripe:plan_comparison'))
        
        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)
        
        # Check that the context contains the plans
        self.assertIn('plans', response.context)
        
        # Check that the plan is displayed
        plans = response.context['plans']
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].name, "Test Plan")
    
    # TODO: Additional tests for user flows will be implemented when the 
    # complete user flow is implemented in Sprint 1
