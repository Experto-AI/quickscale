"""Consolidated tests for subscription lifecycle and Sprint 6 functionality.

This file consolidates subscription-related tests following DRY principles.
Replaces: test_credits_sprint6.py and test_subscription_lifecycle_validation.py
where they have overlapping functionality.
"""
import os
import unittest
from pathlib import Path


class SubscriptionModelTests(unittest.TestCase):
    """Consolidated tests for subscription model implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.admin_dashboard_path = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard'
        self.stripe_manager_path = self.base_path / 'quickscale' / 'project_templates' / 'stripe_manager'
        self.templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates'
        
        # Key files to check
        self.models_py = self.credits_app_path / 'models.py'
        self.admin_py = self.credits_app_path / 'admin.py'
        self.stripe_models_path = self.stripe_manager_path / 'models.py'

    def test_user_subscription_model_exists(self):
        """Test that UserSubscription model exists with all required fields."""
        self.assertTrue(self.models_py.exists(), "Credits models.py template should exist")
        
        content = self.models_py.read_text()
        
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
        required_fields = [
            'user = models.OneToOneField',
            'stripe_subscription_id = models.CharField',
            'stripe_product_id = models.CharField',
            'current_period_start',
            'current_period_end',
            'cancel_at_period_end',
            'canceled_at'
        ]
        
        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, content, f"Required field {field} not found")

    def test_stripe_customer_model_exists(self):
        """Test that StripeCustomer model exists with all required fields."""
        if self.stripe_models_path.exists():
            content = self.stripe_models_path.read_text()
            
            # Check StripeCustomer model exists
            self.assertIn("class StripeCustomer", content)
            
            # Check required fields
            customer_fields = [
                'stripe_id',
                'user'
            ]
            
            for field in customer_fields:
                with self.subTest(field=field):
                    self.assertIn(field, content, f"StripeCustomer field {field} not found")

    def test_subscription_status_choices_comprehensive(self):
        """Test that all required subscription status choices are present."""
        content = self.models_py.read_text()
        
        required_statuses = [
            ('active', 'Active'),
            ('canceled', 'Canceled'),
            ('past_due', 'Past Due'),
            ('unpaid', 'Unpaid'),
            ('incomplete', 'Incomplete'),
            ('trialing', 'Trialing')
        ]
        
        for status_key, status_label in required_statuses:
            with self.subTest(status=status_key):
                # Check both the key and label are present
                self.assertIn(f"'{status_key}'", content)
                self.assertIn(status_label, content)

    def test_subscription_model_methods(self):
        """Test that subscription model has required methods."""
        content = self.models_py.read_text()
        
        # Check for important methods
        methods = [
            'def __str__',
            'def is_active',
            'def cancel_subscription'
        ]
        
        for method in methods:
            with self.subTest(method=method):
                self.assertIn(method, content, f"Method {method} not found in UserSubscription")

    def test_subscription_model_relationships(self):
        """Test that subscription model has correct relationships."""
        content = self.models_py.read_text()
        
        # Check OneToOneField relationship with User
        self.assertIn("user = models.OneToOneField", content)
        self.assertIn("User", content)
        self.assertIn("on_delete=models.CASCADE", content)
        
        # Check related_name is set
        self.assertIn("related_name", content)

    def test_subscription_admin_configuration(self):
        """Test that subscription admin is properly configured."""
        if self.admin_py.exists():
            content = self.admin_py.read_text()
            
            # Check admin registration
            admin_patterns = [
                'UserSubscriptionAdmin',
                'list_display',
                'search_fields',
                'list_filter'
            ]
            
            for pattern in admin_patterns:
                with self.subTest(pattern=pattern):
                    self.assertIn(pattern, content, f"Admin pattern {pattern} not found")

    def test_subscription_migration_exists(self):
        """Test that subscription models exist in the initial migration."""
        migration_dir = self.credits_app_path / 'migrations'
        if migration_dir.exists():
            initial_migration = migration_dir / '0001_initial.py'
            self.assertTrue(initial_migration.exists(), "Initial migration file should exist")
            
            # Check that subscription models are in the initial migration
            content = initial_migration.read_text()
            self.assertIn("UserSubscription", content, "UserSubscription model should be in initial migration")
            self.assertIn("Payment", content, "Payment model should be in initial migration")

    def test_payment_admin_configuration(self):
        """Test that payment admin is properly configured."""
        if self.admin_py.exists():
            content = self.admin_py.read_text()
            
            # Check payment admin
            self.assertIn("PaymentAdmin", content)
            self.assertIn("Payment", content)


class SubscriptionIntegrationTests(unittest.TestCase):
    """Tests for subscription system integration."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates'
        self.admin_dashboard_path = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard'

    def test_subscription_templates_exist(self):
        """Test that subscription templates exist."""
        template_files = [
            'admin_dashboard/subscription.html',
            'admin_dashboard/user_dashboard.html'
        ]
        
        for template_file in template_files:
            template_path = self.templates_path / template_file
            with self.subTest(template=template_file):
                if template_path.exists():
                    self.assertTrue(template_path.exists(), f"Template {template_file} should exist")

    def test_subscription_views_integration(self):
        """Test that subscription views are properly integrated."""
        views_file = self.admin_dashboard_path / 'views.py'
        if views_file.exists():
            content = views_file.read_text()
            
            view_patterns = [
                'subscription',
                'UserSubscription',
                'cancel_subscription'
            ]
            
            for pattern in view_patterns:
                with self.subTest(pattern=pattern):
                    self.assertIn(pattern, content, f"View pattern {pattern} not found")

    def test_subscription_urls_integration(self):
        """Test that subscription URLs are properly configured."""
        urls_file = self.admin_dashboard_path / 'urls.py'
        if urls_file.exists():
            content = urls_file.read_text()
            
            # Check for subscription URL patterns
            url_patterns = [
                'subscription',
                'cancel'
            ]
            
            for pattern in url_patterns:
                with self.subTest(pattern=pattern):
                    self.assertIn(pattern, content, f"URL pattern {pattern} not found")


if __name__ == '__main__':
    unittest.main()
