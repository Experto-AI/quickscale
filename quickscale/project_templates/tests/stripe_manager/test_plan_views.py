"""
Tests for the plan selection views.
"""
from django.test import TestCase, override_settings
from django.urls import reverse
from stripe_manager.models import StripeProduct


class PlanViewsTest(TestCase):
    """Test the plan selection views."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for the test case."""
        # Create three test plans
        cls.plan_1 = StripeProduct.objects.create(
            name="Basic Plan",
            price=9.99,
            currency="usd",
            interval="month",
            description="Basic features for starters",
            stripe_id="prod_basic",
            active=True,
            display_order=1
        )
        
        cls.plan_2 = StripeProduct.objects.create(
            name="Pro Plan",
            price=19.99,
            currency="usd",
            interval="month",
            description="Advanced features for professionals",
            stripe_id="prod_pro",
            active=True,
            display_order=2
        )
        
        cls.plan_3 = StripeProduct.objects.create(
            name="Premium Plan",
            price=49.99,
            currency="usd",
            interval="month",
            description="All features for enterprise",
            stripe_id="prod_premium",
            active=True,
            display_order=3
        )
        
        # Create an inactive plan (should not be displayed)
        cls.inactive_plan = StripeProduct.objects.create(
            name="Hidden Plan",
            price=99.99,
            currency="usd",
            interval="month",
            description="This plan should not be visible",
            stripe_id="prod_hidden",
            active=False,
            display_order=4
        )
    
    @override_settings(STRIPE_ENABLED=True)
    def test_plan_comparison_view_displays_active_plans(self):
        """Test that the plan comparison view displays only active plans."""
        response = self.client.get(reverse('stripe:plan_comparison'))
        
        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)
        
        # Check that the context contains the plans
        self.assertIn('plans', response.context)
        
        # Check that only active plans are displayed
        plans = response.context['plans']
        self.assertEqual(len(plans), 3)
        
        # Check that plans are ordered by display_order
        self.assertEqual(plans[0].name, "Basic Plan")
        self.assertEqual(plans[1].name, "Pro Plan")
        self.assertEqual(plans[2].name, "Premium Plan")
        
        # Make sure the inactive plan is not included
        plan_names = [plan.name for plan in plans]
        self.assertNotIn("Hidden Plan", plan_names)
    
    @override_settings(STRIPE_ENABLED=False)
    def test_plan_comparison_view_when_stripe_disabled(self):
        """Test the plan comparison view when Stripe is disabled."""
        response = self.client.get(reverse('stripe:plan_comparison'))
        
        # Check that the response is 200 OK
        self.assertEqual(response.status_code, 200)
        
        # Check that the context contains the plans (should be empty)
        self.assertIn('plans', response.context)
        
        # Check that the warning message is displayed
        self.assertContains(response, "Stripe integration is currently disabled")
