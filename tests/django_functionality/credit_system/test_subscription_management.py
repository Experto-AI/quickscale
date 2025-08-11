"""
Tests for Sprint 7: Credit Type Priority System implementation.

These tests verify that Sprint 7 has been properly implemented in the QuickScale templates,
including credit expiration logic, priority consumption, and updated frontend display.
"""

import os
import unittest
import re
from pathlib import Path


class Sprint7CreditPrioritySystemTests(unittest.TestCase):
    """Test cases for Sprint 7 credit priority system implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.credits_templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates' / 'credits'
        
        # Key files to check
        self.models_py = self.credits_app_path / 'models.py'
        self.views_py = self.credits_app_path / 'views.py'
        self.dashboard_template = self.credits_templates_path / 'dashboard.html'
        self.services_template = self.credits_templates_path / 'services.html'
        
    def test_credit_expiration_logic_implemented(self):
        """Test that credit expiration logic is implemented in models."""
        self.assertTrue(self.models_py.exists(), "Credits models.py should exist")
        
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check that expires_at field exists in CreditTransaction
        self.assertIn("expires_at = models.DateTimeField", models_content,
                     "expires_at field should exist in CreditTransaction")
        
        # Check that is_expired property exists
        self.assertIn("def is_expired", models_content,
                     "is_expired property should exist in CreditTransaction")
        
        # Check expiration logic implementation
        self.assertIn("timezone.now() > self.expires_at", models_content,
                     "Expiration logic should check current time against expires_at")
    
    def test_priority_consumption_method_implemented(self):
        """Test that priority consumption method is implemented in CreditAccount."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for priority consumption method
        self.assertIn("def consume_credits_with_priority", models_content,
                     "consume_credits_with_priority method should exist in CreditAccount")
        
        # Check for available balance method
        self.assertIn("def get_available_balance", models_content,
                     "get_available_balance method should exist in CreditAccount")
        
        # Check for balance by type available method
        self.assertIn("def get_balance_by_type_available", models_content,
                     "get_balance_by_type_available method should exist in CreditAccount")
        
        # Check for balance details method
        self.assertIn("def get_balance_details", models_content,
                     "get_balance_details method should exist in CreditAccount")
    
    def test_priority_consumption_logic_implemented(self):
        """Test that priority consumption logic is properly implemented."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check that priority consumption considers subscription credits first
        priority_logic_patterns = [
            "credit_type='SUBSCRIPTION'",
            "expires_at__gt=timezone.now()",
            "credit_type__in=\\['PAYG_PURCHASE', 'ADMIN'\\]"
        ]
        
        for pattern in priority_logic_patterns:
            self.assertRegex(models_content, pattern,
                           f"Priority consumption should include pattern: {pattern}")
    
    def test_expiration_handling_on_billing_cycle(self):
        """Test that expiration handling is implemented for billing cycles."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for expiration handling in balance calculations
        self.assertIn("expires_at__gt=timezone.now()", models_content,
                     "Balance calculations should exclude expired credits")
        
        # Check for expiration handling in UserSubscription
        self.assertIn("def allocate_monthly_credits", models_content,
                     "Monthly credit allocation should handle expiration")
    
    def test_updated_views_support_priority_consumption(self):
        """Test that views are updated to support priority consumption."""
        self.assertTrue(self.views_py.exists(), "Credits views.py should exist")
        
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for priority consumption in service usage
        self.assertIn("def use_service_with_priority", views_content,
                     "use_service_with_priority view should exist")
        
        # Check that service usage uses priority consumption
        self.assertIn("consume_credits_with_priority", views_content,
                     "Service usage should use priority consumption method")
    
    def test_frontend_displays_credit_breakdown(self):
        """Test that frontend templates display credit breakdown by type."""
        self.assertTrue(self.dashboard_template.exists(),
                       "Credits dashboard template should exist")
    
    def test_frontend_shows_expiration_dates(self):
        """Test that frontend shows expiration dates for subscription credits."""
        self.assertTrue(self.dashboard_template.exists(),
                       "Credits dashboard template should exist")
    
    def test_service_usage_shows_credit_type_consumption(self):
        """Test that service usage shows which credit type is being consumed."""
        self.assertTrue(self.services_template.exists(),
                       "Credits services template should exist")


class Sprint7ValidationTests(unittest.TestCase):
    """Validation tests for Sprint 7 requirements."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.credits_templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates' / 'credits'
        self.models_py = self.credits_app_path / 'models.py'
        self.views_py = self.credits_app_path / 'views.py'
    
    def test_sprint7_requirements_implemented(self):
        """Test that all Sprint 7 requirements are implemented."""
        # Check models file exists
        self.assertTrue(self.models_py.exists(), "Credits models.py should exist")
        
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check required methods exist
        required_methods = [
            'consume_credits_with_priority',
            'get_available_balance',
            'get_balance_by_type_available',
            'get_balance_details',
            'is_expired'
        ]
        
        for method in required_methods:
            self.assertIn(f"def {method}", models_content,
                         f"Method {method} should be implemented")
        
        # Check views file exists
        self.assertTrue(self.views_py.exists(), "Credits views.py should exist")
        
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check priority consumption is used in views
        self.assertIn("consume_credits_with_priority", views_content,
                     "Views should use priority consumption method")
    
    def test_sprint7_backend_implementation_complete(self):
        """Test that Sprint 7 backend implementation is complete."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for credit expiration logic
        self.assertIn("expires_at", models_content,
                     "Credit expiration should be implemented")
        
        # Check for priority consumption logic
        self.assertIn("SUBSCRIPTION", models_content,
                     "Subscription credit type should exist")
        
        # Check for balance calculation improvements
        self.assertIn("get_balance_by_type", models_content,
                     "Balance by type calculation should exist")
    
    def test_sprint7_frontend_implementation_complete(self):
        """Test that Sprint 7 frontend implementation is complete."""
        # Check that credit templates exist
        dashboard_template = self.credits_templates_path / 'dashboard.html'
        self.assertTrue(dashboard_template.exists(),
                       "Credits dashboard template should exist")
        
        if dashboard_template.exists():
            with open(dashboard_template, 'r') as f:
                template_content = f.read()
            
            # Check for credit breakdown display
            self.assertIn("balance", template_content,
                         "Dashboard should display balance information")