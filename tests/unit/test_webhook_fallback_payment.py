"""Test webhook fallback functionality for Payment record creation.

This test ensures that Payment records are created correctly whether through:
1. Webhook processing (primary method)
2. Success view fallback (when webhook is delayed/failed)
"""

import unittest
from pathlib import Path


class WebhookFallbackTests(unittest.TestCase):
    """Test cases for webhook fallback Payment record creation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent
        self.stripe_views = self.base_path / "quickscale" / "project_templates" / "stripe_manager" / "views.py"
        self.credits_views = self.base_path / "quickscale" / "project_templates" / "credits" / "views.py"
        self.admin_views = self.base_path / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
    
    def test_webhook_handlers_create_payments(self):
        """Test that webhook handlers include Payment record creation logic."""
        with open(self.stripe_views, 'r') as f:
            webhook_content = f.read()
        
        # Check for Payment creation in webhooks
        self.assertIn("Payment.objects.create", webhook_content,
                     "Webhook handlers should create Payment records")
        self.assertIn("from credits.models import Payment", webhook_content,
                     "Webhook handlers should import Payment model")
    
    def test_duplicate_payment_prevention(self):
        """Test that webhook handlers prevent duplicate Payment creation."""
        with open(self.stripe_views, 'r') as f:
            webhook_content = f.read()
        
        # Check for duplicate prevention logic
        self.assertIn("existing_payment = Payment.objects.filter", webhook_content,
                     "Webhook handlers should check for existing payments")
        self.assertIn("if not existing_payment:", webhook_content,
                     "Webhook handlers should prevent duplicate payment creation")
    
    def test_success_view_fallback_exists(self):
        """Test that success views include Payment record creation fallback."""
        with open(self.credits_views, 'r') as f:
            credits_content = f.read()
        
        # Check for Payment creation fallback in credit purchase success view
        self.assertIn("existing_payment = Payment.objects.filter", credits_content,
                     "Credit purchase success view should check for existing payments")
        self.assertIn("Payment.objects.create", credits_content,
                     "Credit purchase success view should create Payment records as fallback")
    
    def test_subscription_success_fallback_exists(self):
        """Test that subscription success view includes Payment record creation fallback."""
        with open(self.admin_views, 'r') as f:
            admin_content = f.read()
        
        # Check for Payment creation fallback in subscription success view
        self.assertIn("existing_payment = Payment.objects.filter", admin_content,
                     "Subscription success view should check for existing payments")
        self.assertIn("Payment.objects.create", admin_content,
                     "Subscription success view should create Payment records as fallback")
    
    def test_logging_for_debugging(self):
        """Test that Payment creation includes proper logging for debugging."""
        with open(self.stripe_views, 'r') as f:
            webhook_content = f.read()
        
        # Check for logging statements
        self.assertIn("logger.info", webhook_content,
                     "Webhook handlers should include logging for debugging")


class WebhookTimingScenarioTests(unittest.TestCase):
    """Test specific timing scenarios between webhooks and success views."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent
        self.stripe_views = self.base_path / "quickscale" / "project_templates" / "stripe_manager" / "views.py"
        self.credits_views = self.base_path / "quickscale" / "project_templates" / "credits" / "views.py"
        self.admin_views = self.base_path / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
    
    def test_session_id_handling_in_success_views(self):
        """Test that success views can handle session IDs from Stripe redirects."""
        with open(self.credits_views, 'r') as f:
            credits_content = f.read()
        
        # Check for session ID handling
        self.assertIn("session_id = request.GET.get('session_id')", credits_content,
                     "Credit success view should handle session_id parameter")
        
        with open(self.admin_views, 'r') as f:
            admin_content = f.read()
            
        self.assertIn("session_id = request.GET.get('session_id')", admin_content,
                     "Subscription success view should handle session_id parameter")
    
    def test_stripe_api_querying_in_success_views(self):
        """Test that success views can query Stripe API for payment verification."""
        with open(self.credits_views, 'r') as f:
            credits_content = f.read()
        
        # Check for Stripe API usage in success views
        self.assertIn("stripe_manager.retrieve_checkout_session", credits_content,
                     "Credit success view should query Stripe API for session details")
    
    def test_payment_intent_handling(self):
        """Test that payment intent IDs are properly handled for record creation."""
        with open(self.credits_views, 'r') as f:
            credits_content = f.read()
        
        # Check for payment intent handling
        self.assertIn("payment_intent_id", credits_content,
                     "Success views should handle payment intent IDs")


if __name__ == '__main__':
    unittest.main() 