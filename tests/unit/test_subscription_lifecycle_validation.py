"""
Validation tests for Sprint 24 Subscription Management Review.
Tests that subscription lifecycle management and plan change handling templates are properly implemented.
"""

import os
import re
import ast
from pathlib import Path
from django.test import TestCase


class SubscriptionLifecycleTemplateValidationTest(TestCase):
    """Validate that subscription lifecycle functionality exists in templates."""
    
    def setUp(self):
        """Set up paths to template files."""
        self.base_path = Path(__file__).parent.parent.parent / "quickscale" / "templates"
        self.credits_models_path = self.base_path / "credits" / "models.py"
        self.stripe_models_path = self.base_path / "stripe_manager" / "models.py"
    
    def test_user_subscription_model_exists(self):
        """Test that UserSubscription model exists with all required fields."""
        self.assertTrue(self.credits_models_path.exists(), "Credits models.py template should exist")
        
        content = self.credits_models_path.read_text()
        
        # Check UserSubscription model exists
        self.assertIn("class UserSubscription(models.Model):", content)
        
        # Check required status choices
        self.assertIn("STATUS_CHOICES", content)
        self.assertIn("'active'", content)
        self.assertIn("'canceled'", content)
        self.assertIn("'past_due'", content)
        self.assertIn("'unpaid'", content)
        self.assertIn("'incomplete'", content)
        self.assertIn("'trialing'", content)
        
        # Check required fields
        self.assertIn("stripe_subscription_id", content)
        self.assertIn("stripe_product_id", content)
        self.assertIn("current_period_start", content)
        self.assertIn("current_period_end", content)
        self.assertIn("cancel_at_period_end", content)
        self.assertIn("canceled_at", content)
    
    def test_payment_model_exists(self):
        """Test that Payment model exists with all required fields."""
        content = self.credits_models_path.read_text()
        
        # Check Payment model exists
        self.assertIn("class Payment(models.Model):", content)
        
        # Check payment types
        self.assertIn("PAYMENT_TYPE_CHOICES", content)
        self.assertIn("'CREDIT_PURCHASE'", content)
        self.assertIn("'SUBSCRIPTION'", content)
        self.assertIn("'REFUND'", content)
        
        # Check status choices
        self.assertIn("STATUS_CHOICES", content)
        self.assertIn("'pending'", content)
        self.assertIn("'succeeded'", content)
        self.assertIn("'failed'", content)
        self.assertIn("'refunded'", content)
        
        # Check required fields
        self.assertIn("stripe_payment_intent_id", content)
        self.assertIn("stripe_subscription_id", content)
        self.assertIn("stripe_invoice_id", content)
        self.assertIn("receipt_number", content)
        self.assertIn("receipt_data", content)
    
    def test_credit_account_model_exists(self):
        """Test that CreditAccount model exists with balance methods."""
        content = self.credits_models_path.read_text()
        
        # Check CreditAccount model exists
        self.assertIn("class CreditAccount(models.Model):", content)
        
        # Check balance calculation methods
        self.assertIn("def get_balance(self)", content)
        self.assertIn("def get_balance_by_type(self)", content)
        
        # Check OneToOne relationship with User
        self.assertIn("models.OneToOneField", content)
        self.assertIn("related_name='credit_account'", content)
    
    def test_credit_transaction_model_exists(self):
        """Test that CreditTransaction model exists with credit types."""
        content = self.credits_models_path.read_text()
        
        # Check CreditTransaction model exists
        self.assertIn("class CreditTransaction(models.Model):", content)
        
        # Check credit types
        self.assertIn("CREDIT_TYPE_CHOICES", content)
        self.assertIn("'PURCHASE'", content)
        self.assertIn("'SUBSCRIPTION'", content)
        self.assertIn("'CONSUMPTION'", content)
        
        # Check required fields
        self.assertIn("amount", content)
        self.assertIn("credit_type", content)
        self.assertIn("expires_at", content)
        self.assertIn("description", content)
    
    def test_stripe_product_model_exists(self):
        """Test that StripeProduct model exists with subscription support."""
        self.assertTrue(self.stripe_models_path.exists(), "Stripe models.py template should exist")
        
        content = self.stripe_models_path.read_text()
        
        # Check StripeProduct model exists
        self.assertIn("class StripeProduct(models.Model):", content)
        
        # Check billing interval choices
        self.assertIn("interval", content)
        self.assertIn("'month'", content)
        self.assertIn("'year'", content)
        self.assertIn("'one-time'", content)
        
        # Check credit configuration
        self.assertIn("credit_amount", content)
        
        # Check utility methods
        self.assertIn("def price_per_credit(self)", content)
        self.assertIn("def is_subscription(self)", content)
        self.assertIn("def is_one_time(self)", content)
    
    def test_stripe_customer_model_exists(self):
        """Test that StripeCustomer model exists with user linking."""
        content = self.stripe_models_path.read_text()
        
        # Check StripeCustomer model exists
        self.assertIn("class StripeCustomer(models.Model):", content)
        
        # Check user relationship
        self.assertIn("models.OneToOneField", content)
        self.assertIn("related_name='stripe_customer'", content)
        
        # Check required fields
        self.assertIn("stripe_id", content)
        self.assertIn("email", content)


class PlanChangeTemplateValidationTest(TestCase):
    """Validate that plan change functionality exists in templates."""
    
    def setUp(self):
        """Set up paths to template files."""
        self.base_path = Path(__file__).parent.parent.parent / "quickscale" / "templates"
        self.credits_models_path = self.base_path / "credits" / "models.py"
    
    def test_subscription_credit_allocation_method_exists(self):
        """Test that UserSubscription has allocate_monthly_credits method."""
        content = self.credits_models_path.read_text()
        
        # Check allocate_monthly_credits method exists
        self.assertIn("def allocate_monthly_credits(self)", content)
        
        # Check it handles Stripe product lookup
        self.assertIn("StripeProduct", content)
        
        # Check credit transaction creation
        self.assertIn("CreditTransaction.objects.create", content)
    
    def test_credit_transfer_functionality_exists(self):
        """Test that credit transfer functionality exists."""
        content = self.credits_models_path.read_text()
        
        # Check for credit transfer function or method
        # This might be a standalone function or method
        self.assertTrue(
            "def handle_plan_change_credit_transfer" in content or
            "credit_transfer" in content,
            "Credit transfer functionality should exist"
        )
    
    def test_balance_calculation_methods_exist(self):
        """Test that sophisticated balance calculation methods exist."""
        content = self.credits_models_path.read_text()
        
        # Check for advanced balance calculations
        self.assertIn("def get_balance_by_type(self)", content)
        
        # Check for subscription vs pay-as-you-go distinction
        self.assertIn("subscription", content.lower())
        self.assertIn("pay_as_you_go", content.lower())
    
    def test_credit_expiration_handling_exists(self):
        """Test that credit expiration handling exists."""
        content = self.credits_models_path.read_text()
        
        # Check for expiration date field
        self.assertIn("expires_at", content)
        
        # Check for expiration handling logic  
        self.assertIn("expires_at", content)
        self.assertTrue(
            "expiration" in content.lower() or
            "expire" in content.lower(),
            "Credit expiration handling should exist"
        )


class WebhookProcessingTemplateValidationTest(TestCase):
    """Validate that webhook processing functionality exists in templates."""
    
    def setUp(self):
        """Set up paths to template files."""
        self.base_path = Path(__file__).parent.parent.parent / "quickscale" / "templates"
        self.stripe_views_path = self.base_path / "stripe_manager" / "views.py"
    
    def test_webhook_views_exist(self):
        """Test that webhook processing views exist."""
        if not self.stripe_views_path.exists():
            self.skipTest("Stripe views.py template not found")
        
        content = self.stripe_views_path.read_text()
        
        # Check for webhook endpoint
        self.assertTrue(
            "webhook" in content.lower() or
            "stripe_webhook" in content.lower(),
            "Webhook processing should exist"
        )
    
    def test_subscription_event_handling_exists(self):
        """Test that subscription event handling exists."""
        if not self.stripe_views_path.exists():
            self.skipTest("Stripe views.py template not found")
        
        content = self.stripe_views_path.read_text()
        
        # Check for subscription event handling
        self.assertTrue(
            "subscription" in content.lower() and
            ("updated" in content.lower() or "created" in content.lower()),
            "Subscription event handling should exist"
        )


class IntegrationTemplateValidationTest(TestCase):
    """Validate that integration components exist in templates."""
    
    def setUp(self):
        """Set up paths to template files."""
        self.base_path = Path(__file__).parent.parent.parent / "quickscale" / "templates"
    
    def test_admin_dashboard_integration_exists(self):
        """Test that admin dashboard integration exists."""
        admin_views_path = self.base_path / "admin_dashboard" / "views.py"
        
        if admin_views_path.exists():
            content = admin_views_path.read_text()
            
            # Check for credit management views
            self.assertTrue(
                "credit" in content.lower() or
                "subscription" in content.lower() or
                "payment" in content.lower(),
                "Admin dashboard should have credit/payment integration"
            )
    
    def test_template_files_exist(self):
        """Test that required template files exist."""
        template_dirs = [
            self.base_path / "templates" / "credits",
            self.base_path / "templates" / "stripe_manager",
            self.base_path / "templates" / "admin_dashboard"
        ]
        
        for template_dir in template_dirs:
            if template_dir.exists():
                # Check that template directory has some HTML files
                html_files = list(template_dir.glob("*.html"))
                self.assertTrue(
                    len(html_files) > 0,
                    f"Template directory {template_dir} should contain HTML files"
                )
    
    def test_stripe_integration_exists(self):
        """Test that Stripe integration components exist."""
        stripe_manager_path = self.base_path / "stripe_manager" / "stripe_manager.py"
        
        if stripe_manager_path.exists():
            content = stripe_manager_path.read_text()
            
            # Check for StripeManager class
            self.assertIn("class StripeManager", content)
            
            # Check for key Stripe operations
            self.assertTrue(
                "create_customer" in content.lower() or
                "customer" in content.lower(),
                "StripeManager should handle customer operations"
            ) 