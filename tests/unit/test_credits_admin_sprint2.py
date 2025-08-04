"""
Tests for Sprint 2: Manual Credit Management functionality.

These tests verify that the admin interface templates, forms, and functionality
have been properly generated in the credits app for manual credit management.
"""

import os
import unittest
import re
from pathlib import Path


class Sprint2AdminTemplateTests(unittest.TestCase):
    """Test cases for Sprint 2 admin templates and structure."""
    
    def setUp(self):
        """Set up test environment."""
        # Locate the template files
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.admin_templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates' / 'admin' / 'credits'
        
        # Admin template files
        self.credit_adjustment_template = self.admin_templates_path / 'credit_adjustment.html'
        self.bulk_credit_adjustment_template = self.admin_templates_path / 'bulk_credit_adjustment.html'
        
        # App configuration files
        self.admin_py = self.credits_app_path / 'admin.py'
        self.forms_py = self.credits_app_path / 'forms.py'
        self.models_py = self.credits_app_path / 'models.py'
    
    def test_admin_templates_exist(self):
        """Test that admin templates for credit management exist."""
        self.assertTrue(self.admin_templates_path.exists(),
                       f"Admin templates directory not found at {self.admin_templates_path}")
        
        self.assertTrue(self.credit_adjustment_template.exists(),
                       f"Credit adjustment template not found at {self.credit_adjustment_template}")
        
        self.assertTrue(self.bulk_credit_adjustment_template.exists(),
                       f"Bulk credit adjustment template not found at {self.bulk_credit_adjustment_template}")
    
    def test_forms_py_exists(self):
        """Test that forms.py file exists for admin forms."""
        self.assertTrue(self.forms_py.exists(),
                       f"forms.py not found at {self.forms_py}")
    
    def test_enhanced_admin_configuration(self):
        """Test that admin.py has been enhanced with Sprint 2 functionality."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for enhanced imports
        self.assertIn("from django.http import HttpResponseRedirect", admin_content,
                     "HttpResponseRedirect import not found")
        self.assertIn("from django.urls import path, reverse", admin_content,
                     "path and reverse imports not found")
        self.assertIn("from django.shortcuts import render, get_object_or_404", admin_content,
                     "render and get_object_or_404 imports not found")
        self.assertIn("from django.contrib import messages", admin_content,
                     "messages import not found")
        self.assertIn("from django.utils.html import format_html", admin_content,
                     "format_html import not found")
        
        # Check for form import
        self.assertIn("from .forms import AdminCreditAdjustmentForm", admin_content,
                     "AdminCreditAdjustmentForm import not found")
    
    def test_credit_account_admin_enhancements(self):
        """Test CreditAccountAdmin enhancements for Sprint 2."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for credit_actions in list_display
        self.assertIn("'credit_actions'", admin_content,
                     "credit_actions not in list_display")
        
        # Check for bulk_add_credits action
        self.assertIn("actions = ['bulk_add_credits']", admin_content,
                     "bulk_add_credits action not configured")
        
        # Check for credit_actions method
        self.assertIn("def credit_actions(self, obj):", admin_content,
                     "credit_actions method not found")
        
        # Check for custom URLs method
        self.assertIn("def get_urls(self):", admin_content,
                     "get_urls method not found")
        
        # Check for add_credits_view method
        self.assertIn("def add_credits_view(self, request, account_id):", admin_content,
                     "add_credits_view method not found")
        
        # Check for remove_credits_view method
        self.assertIn("def remove_credits_view(self, request, account_id):", admin_content,
                     "remove_credits_view method not found")
        
        # Check for bulk_add_credits method
        self.assertIn("def bulk_add_credits(self, request, queryset):", admin_content,
                     "bulk_add_credits method not found")
    
    def test_credit_transaction_admin_enhancements(self):
        """Test CreditTransactionAdmin enhancements for Sprint 2."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for transaction_type in list_display
        self.assertIn("'transaction_type'", admin_content,
                     "transaction_type not in list_display")
        
        # Check for transaction_type method
        self.assertIn("def transaction_type(self, obj):", admin_content,
                     "transaction_type method not found")
        
        # Check for read-only permissions
        self.assertIn("def has_add_permission(self, request):", admin_content,
                     "has_add_permission method not found")
        self.assertIn("def has_change_permission(self, request, obj=None):", admin_content,
                     "has_change_permission method not found")
        self.assertIn("def has_delete_permission(self, request, obj=None):", admin_content,
                     "has_delete_permission method not found")
        
        # Check for admin operation type detection
        self.assertIn("Admin Credit Addition", admin_content,
                     "Admin Credit Addition detection not found")
        self.assertIn("Admin Credit Removal", admin_content,
                     "Admin Credit Removal detection not found")
        self.assertIn("Bulk Admin Credit Addition", admin_content,
                     "Bulk Admin Credit Addition detection not found")
    
    def test_credit_adjustment_template_structure(self):
        """Test credit adjustment template structure."""
        with open(self.credit_adjustment_template, 'r') as f:
            template_content = f.read()
        
        # Check template extends admin base
        self.assertIn('{% extends "admin/base_site.html" %}', template_content,
                     "Template does not extend admin base template")
        
        # Check for breadcrumbs
        self.assertIn("{% block breadcrumbs %}", template_content,
                     "Breadcrumbs block not found")
        
        # Check for account information display
        self.assertIn("Account Information", template_content,
                     "Account Information section not found")
        self.assertIn("Current Balance", template_content,
                     "Current Balance display not found")
        
        # Check for form elements
        self.assertIn("{{ form.amount", template_content,
                     "Amount form field not found")
        self.assertIn("{{ form.reason", template_content,
                     "Reason form field not found")
        
        # Check for error handling
        self.assertIn("{% if form.errors %}", template_content,
                     "Form error handling not found")
        
        # Check for warning message for removal
        self.assertIn("Warning: This will remove credits", template_content,
                     "Warning message for credit removal not found")
        
        # Check for CSRF token
        self.assertIn("{% csrf_token %}", template_content,
                     "CSRF token not found")
    
    def test_bulk_credit_adjustment_template_structure(self):
        """Test bulk credit adjustment template structure."""
        with open(self.bulk_credit_adjustment_template, 'r') as f:
            template_content = f.read()
        
        # Check template extends admin base
        self.assertIn('{% extends "admin/base_site.html" %}', template_content,
                     "Template does not extend admin base template")
        
        # Check for selected accounts display
        self.assertIn("Selected Accounts", template_content,
                     "Selected Accounts section not found")
        self.assertIn("Number of accounts selected", template_content,
                     "Account count display not found")
        
        # Check for account list display
        self.assertIn("{% for account in queryset %}", template_content,
                     "Account iteration not found")
        self.assertIn("Current balance:", template_content,
                     "Current balance display not found")
        
        # Check for form elements
        self.assertIn("{{ form.amount", template_content,
                     "Amount form field not found")
        self.assertIn("{{ form.reason", template_content,
                     "Reason form field not found")
        
        # Check for hidden fields for bulk operation
        self.assertIn('name="_selected_action"', template_content,
                     "Selected action hidden fields not found")
        self.assertIn('name="post"', template_content,
                     "Post confirmation field not found")
    
    def test_credits_admin_url_patterns(self):
        """Test that admin URL patterns are properly configured."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for add-credits URL pattern
        self.assertIn("'<int:account_id>/add-credits/'", admin_content,
                     "Add credits URL pattern not found")
        
        # Check for remove-credits URL pattern
        self.assertIn("'<int:account_id>/remove-credits/'", admin_content,
                     "Remove credits URL pattern not found")
        
        # Check for URL names
        self.assertIn("name='credits_add_credits'", admin_content,
                     "Add credits URL name not found")
        self.assertIn("name='credits_remove_credits'", admin_content,
                     "Remove credits URL name not found")
    
    def test_form_validation_and_security(self):
        """Test form validation and security features."""
        with open(self.forms_py, 'r') as f:
            forms_content = f.read()
        
        # Check for minimum value validation
        self.assertIn("MinValueValidator(Decimal('0.01'))", forms_content,
                     "Minimum value validation not found")
        
        # Check for amount validation method
        self.assertIn("if amount is not None and amount <= 0:", forms_content,
                     "Amount validation logic not found")
        
        # Check for reason validation
        self.assertIn("reason = self.cleaned_data.get('reason', '').strip()", forms_content,
                     "Reason cleaning and validation not found")
        
        # Check for error messages
        self.assertIn("Amount must be greater than zero", forms_content,
                     "Amount validation error message not found")
        self.assertIn("Reason is required", forms_content,
                     "Reason validation error message not found")
    
    def test_admin_operation_attribution(self):
        """Test that admin operations are properly attributed."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for admin attribution in descriptions
        self.assertIn("(by {request.user.email})", admin_content,
                     "Admin user attribution not found")
        
        # Check for operation descriptions
        self.assertIn("Admin Credit Addition:", admin_content,
                     "Admin Credit Addition description not found")
        self.assertIn("Admin Credit Removal:", admin_content,
                     "Admin Credit Removal description not found")
        self.assertIn("Bulk Admin Credit Addition:", admin_content,
                     "Bulk Admin Credit Addition description not found")
    
    def test_balance_validation_logic(self):
        """Test balance validation for credit removal."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for insufficient balance validation
        self.assertIn("if amount > current_balance:", admin_content,
                     "Balance validation logic not found")
        
        # Check for error message
        self.assertIn("Cannot remove", admin_content,
                     "Insufficient balance error message not found")
        
        # Check for balance check before removal
        self.assertIn("current_balance = account.get_balance()", admin_content,
                     "Current balance retrieval not found")
    
    def test_success_message_configuration(self):
        """Test success message configuration."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for success messages
        self.assertIn("messages.success", admin_content,
                     "Success messages not found")
        
        # Check for error messages
        self.assertIn("messages.error", admin_content,
                     "Error messages not found")
        
        # Check for balance update in success message
        self.assertIn("New balance:", admin_content,
                     "New balance in success message not found")


class Sprint2IntegrationTests(unittest.TestCase):
    """Integration tests for Sprint 2 functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.admin_py = self.credits_app_path / 'admin.py'
        self.forms_py = self.credits_app_path / 'forms.py'
        self.models_py = self.credits_app_path / 'models.py'
    
    def test_admin_forms_integration(self):
        """Test that admin.py properly imports and uses the forms."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        with open(self.forms_py, 'r') as f:
            forms_content = f.read()
        
        # Verify form is imported in admin
        self.assertIn("from .forms import AdminCreditAdjustmentForm", admin_content,
                     "Form not imported in admin")
        
        # Verify form is used in views
        self.assertIn("AdminCreditAdjustmentForm(request.POST)", admin_content,
                     "Form not used in POST handling")
        self.assertIn("AdminCreditAdjustmentForm()", admin_content,
                     "Form not used in GET handling")
    
    def test_models_admin_integration(self):
        """Test that admin properly uses model methods."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Verify add_credits method exists in models
        self.assertIn("def add_credits", models_content,
                     "add_credits method not found in models")
        
        # Verify admin uses model methods
        self.assertIn("account.add_credits", admin_content,
                     "Admin doesn't use add_credits method")
        self.assertIn("account.get_balance", admin_content,
                     "Admin doesn't use get_balance method")
    
    def test_complete_sprint2_implementation(self):
        """Test that all Sprint 2 components are properly implemented."""
        # Check all required files exist
        self.assertTrue(self.admin_py.exists(), "admin.py missing")
        self.assertTrue(self.forms_py.exists(), "forms.py missing")
        
        # Check admin templates exist
        admin_templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates' / 'admin' / 'credits'
        self.assertTrue((admin_templates_path / 'credit_adjustment.html').exists(),
                       "Credit adjustment template missing")
        self.assertTrue((admin_templates_path / 'bulk_credit_adjustment.html').exists(),
                       "Bulk credit adjustment template missing")
        
        # Verify Sprint 2 validation criteria can be met
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Admin can add credits (add_credits_view exists)
        self.assertIn("def add_credits_view", admin_content,
                     "Add credits functionality missing")
        
        # Admin can remove credits (remove_credits_view exists)
        self.assertIn("def remove_credits_view", admin_content,
                     "Remove credits functionality missing")
        
        # Bulk operations available
        self.assertIn("def bulk_add_credits", admin_content,
                     "Bulk credit operations missing")
        
        # User can see updated balance (dashboard already exists from Sprint 1)
        dashboard_template = self.base_path / 'quickscale' / 'project_templates' / 'credits' / 'templates' / 'credits' / 'dashboard.html'
        self.assertTrue(dashboard_template.exists(),
                       "User dashboard missing for balance visibility")


if __name__ == '__main__':
    unittest.main() 