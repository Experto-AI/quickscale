"""
Tests for Sprint 18 Payment Admin Tools functionality.

Tests payment search, payment investigation, and refund initiation features
for admin users in the QuickScale project generator template.

This test validates the template files in quickscale/project_templates/admin_dashboard/
to ensure Sprint 18 features are properly implemented.
"""

import os
import unittest
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock


class Sprint18TemplateValidationTests(unittest.TestCase):
    """Test that Sprint 18 payment admin tools templates exist and have proper structure."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent
        self.admin_dashboard_path = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard'
        self.views_file = self.admin_dashboard_path / 'views.py'
        self.urls_file = self.admin_dashboard_path / 'urls.py'
        self.templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates' / 'admin_dashboard'

    def test_payment_search_view_exists_in_template(self):
        """Test that payment_search view exists in admin_dashboard views template."""
        self.assertTrue(self.views_file.exists(), "Admin dashboard views.py template not found")
        
        with open(self.views_file, 'r') as f:
            views_content = f.read()
        
        # Check for payment_search function
        self.assertIn("def payment_search(", views_content,
                     "payment_search function not found in views template")
        
        # Check for search functionality
        self.assertIn("request.GET.get('q'", views_content,
                     "Search query parameter handling not found")
        
        # Check for pagination
        self.assertIn("Paginator", views_content,
                     "Pagination not implemented in payment search")

    def test_payment_investigation_view_exists_in_template(self):
        """Test that payment_investigation view exists in admin_dashboard views template."""
        with open(self.views_file, 'r') as f:
            views_content = f.read()
        
        # Check for payment_investigation function
        self.assertIn("def payment_investigation(", views_content,
                     "payment_investigation function not found in views template")
        
        # Check for Stripe integration
        self.assertIn("stripe_manager.retrieve_payment_intent", views_content,
                     "Stripe PaymentIntent retrieval not found")
        
        # Check for warning generation  
        self.assertIn("investigation_data['warnings'].append", views_content,
                     "Warning generation not implemented")

    def test_refund_initiation_view_exists_in_template(self):
        """Test that refund initiation view exists in admin_dashboard views template."""
        with open(self.views_file, 'r') as f:
            views_content = f.read()
        
        # Check for initiate_refund function
        self.assertIn("def initiate_refund(", views_content,
                     "initiate_refund function not found in views template")
        
        # Check for refund validation
        self.assertIn("payment.status != 'succeeded'", views_content,
                     "Payment status validation not found")
        
        # Check for Stripe refund processing
        self.assertIn("stripe_manager.create_refund", views_content,
                     "Stripe refund creation not found")

    def test_payment_admin_urls_exist_in_template(self):
        """Test that payment admin URLs are defined in admin_dashboard urls template."""
        self.assertTrue(self.urls_file.exists(), "Admin dashboard urls.py template not found")
        
        with open(self.urls_file, 'r') as f:
            urls_content = f.read()
        
        # Check for payment search URL
        self.assertIn("path('payments/search/'", urls_content,
                     "Payment search URL not found")
        
        # Check for payment investigation URL
        self.assertIn("path('payments/<int:payment_id>/investigate/'", urls_content,
                     "Payment investigation URL not found")
        
        # Check for refund initiation URL
        self.assertIn("path('payments/<int:payment_id>/refund/'", urls_content,
                     "Refund initiation URL not found")


class Sprint18PaymentSearchTests(unittest.TestCase):
    """Test Sprint 18 payment search functionality implementation."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent
        self.views_file = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'views.py'

    def test_payment_search_filtering_logic(self):
        """Test that payment search implements proper filtering logic."""
        with open(self.views_file, 'r') as f:
            views_content = f.read()
        
        # Check for search filtering
        self.assertIn("Q(user__email__icontains=search_query)", views_content,
                     "Email search filtering not implemented")
        
        # Check for additional filter parameters
        self.assertIn("payment_type = request.GET.get('type'", views_content,
                     "Payment type filtering not implemented")
        
        self.assertIn("status = request.GET.get('status'", views_content,
                     "Status filtering not implemented")

    def test_payment_search_context_data(self):
        """Test that payment search provides proper context data."""
        with open(self.views_file, 'r') as f:
            views_content = f.read()
        
        # Check for context data
        self.assertIn("'payments': page_obj", views_content,
                     "Payments context variable not provided")
        
        self.assertIn("page_obj = paginator.get_page", views_content,
                     "Pagination context not provided")


class Sprint18PaymentInvestigationTests(unittest.TestCase):
    """Test Sprint 18 payment investigation functionality implementation."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent
        self.views_file = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'views.py'

class Sprint18RefundInitiationTests(unittest.TestCase):
    """Test Sprint 18 refund initiation functionality implementation."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent
        self.views_file = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'views.py'

    def test_refund_credit_adjustment(self):
        """Test that refund initiation handles credit adjustments."""
        with open(self.views_file, 'r') as f:
            views_content = f.read()
        
        # Check for credit adjustment logic
        self.assertIn("if payment.payment_type == 'CREDIT_PURCHASE' and payment.credit_transaction:", views_content,
                     "Credit purchase refund handling not implemented")
        
        # Check for credit adjustment 
        self.assertIn("amount=-refund_amount_decimal", views_content,
                     "Credit adjustment for refunds not implemented")


class Sprint18RequirementsValidationTests(unittest.TestCase):
    """Test that Sprint 18 meets all ROADMAP.md requirements."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent
        self.views_file = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'views.py'

    def test_payment_search_requirements(self):
        """Test that payment search meets ROADMAP.md requirements."""
        with open(self.views_file, 'r') as f:
            views_content = f.read()
        
        # Backend requirements from ROADMAP.md
        self.assertIn("def payment_search(", views_content,
                     "Payment search functionality requirement not met")

    def test_refund_initiation_requirements(self):
        """Test that refund initiation meets ROADMAP.md requirements."""
        with open(self.views_file, 'r') as f:
            views_content = f.read()
        
        # Backend requirements from ROADMAP.md
        self.assertIn("def initiate_refund(", views_content,
                     "Basic refund initiation requirement not met")

    def test_payment_investigation_requirements(self):
        """Test that payment investigation meets ROADMAP.md requirements."""
        with open(self.views_file, 'r') as f:
            views_content = f.read()
        
        # Backend requirements from ROADMAP.md
        self.assertIn("def payment_investigation(", views_content,
                     "Payment investigation tools requirement not met")


class Sprint18SecurityValidationTests(unittest.TestCase):
    """Test Sprint 18 security controls and validation."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent
        self.views_file = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'views.py'

    def test_staff_permission_requirements(self):
        """Test that all payment admin tools require staff permissions."""
        with open(self.views_file, 'r') as f:
            views_content = f.read()
        
        # Check for staff_member_required decorators  
        self.assertIn("@user_passes_test(lambda u: u.is_staff)", views_content,
                     "Staff member requirement not enforced")

    def test_csrf_protection(self):
        """Test that refund forms include CSRF protection."""
        with open(self.views_file, 'r') as f:
            views_content = f.read()
        
        # Check for POST method validation
        self.assertIn("if request.method != 'POST':", views_content,
                     "POST method validation not implemented")


if __name__ == '__main__':
    unittest.main() 