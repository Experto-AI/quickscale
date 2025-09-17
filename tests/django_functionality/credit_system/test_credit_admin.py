"""
Tests for Sprint 17: Admin Credit Management functionality.

These tests verify that the admin credit adjustment functionality, validation,
and audit logging have been properly generated in the QuickScale project templates.
"""

import os
import unittest
from pathlib import Path


class TestSprint17CreditAdjustmentForms(unittest.TestCase):
    """Test cases for Sprint 17 credit adjustment forms."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.forms_py = self.credits_app_path / 'forms.py'
    
    def test_admin_credit_adjustment_form_exists(self):
        """Test that AdminCreditAdjustmentForm exists and has proper validation."""
        self.assertTrue(self.forms_py.exists(), 
                       f"forms.py not found at {self.forms_py}")
        
        with open(self.forms_py, 'r') as f:
            forms_content = f.read()
        
        # Check for AdminCreditAdjustmentForm class
        self.assertIn("class AdminCreditAdjustmentForm", forms_content,
                     "AdminCreditAdjustmentForm class not found")
        
        # Check for amount field with proper validation
        self.assertIn("amount = forms.DecimalField", forms_content,
                     "Amount field not found")
        self.assertIn("MinValueValidator", forms_content,
                     "MinValueValidator not imported or used")
        self.assertIn("max_digits=10", forms_content,
                     "Amount field should have max_digits=10")
        self.assertIn("decimal_places=2", forms_content,
                     "Amount field should have decimal_places=2")
        
        # Check for reason field
        self.assertIn("reason = forms.CharField", forms_content,
                     "Reason field not found")
        self.assertIn("max_length=255", forms_content,
                     "Reason field should have max_length=255")
        
        # Check for validation methods
        self.assertIn("def clean_amount", forms_content,
                     "clean_amount validation method not found")
        self.assertIn("def clean_reason", forms_content,
                     "clean_reason validation method not found")
        
        # Check for positive amount validation
        self.assertIn("amount <= 0", forms_content,
                     "Positive amount validation not found")
        self.assertIn("Amount must be greater than zero", forms_content,
                     "Amount validation error message not found")
        
        # Check for reason validation
        self.assertIn(".strip()", forms_content,
                     "Reason field should be stripped")
        self.assertIn("Reason is required", forms_content,
                     "Reason validation error message not found")


class TestSprint17CreditAdjustmentViews(unittest.TestCase):
    """Test cases for Sprint 17 credit adjustment views."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.admin_dashboard_path = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard'
        self.views_py = self.admin_dashboard_path / 'views.py'
    
    def test_user_credit_adjustment_view_exists(self):
        """Test that user_credit_adjustment view exists with proper functionality."""
        self.assertTrue(self.views_py.exists(),
                       f"views.py not found at {self.views_py}")
        
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for user_credit_adjustment function
        self.assertIn("def user_credit_adjustment", views_content,
                     "user_credit_adjustment function not found")
        
        # Check for proper decorators
        self.assertIn("@login_required", views_content,
                     "login_required decorator not found")
        self.assertIn("@user_passes_test(lambda u: u.is_staff)", views_content,
                     "staff user test decorator not found")
        
        # Check for HTMX handling
        self.assertIn("request.method == 'POST'", views_content,
                     "POST method handling not found")
        
        # Check for action parameter handling
        self.assertIn("action = request.POST.get('action')", views_content,
                     "Action parameter handling not found")
        
        # Check for balance validation
        self.assertIn("amount > current_balance", views_content,
                     "Balance validation logic not found")
        self.assertIn("Cannot remove", views_content,
                     "Insufficient balance error message not found")
        
        # Check for audit logging integration
        self.assertIn("log_admin_action", views_content,
                     "Audit logging not integrated")
        self.assertIn("'CREDIT_ADJUSTMENT'", views_content,
                     "Credit adjustment action type not found")
    
    def test_credit_adjustment_response_format(self):
        """Test that credit adjustment view returns proper JSON responses."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for JsonResponse usage
        self.assertIn("JsonResponse", views_content,
                     "JsonResponse not imported or used")
        
        # Check for success response format
        self.assertIn("'success': True", views_content,
                     "Success response format not found")
        self.assertIn("'new_balance'", views_content,
                     "New balance in response not found")
        self.assertIn("'balance_breakdown'", views_content,
                     "Balance breakdown in response not found")
        
        # Check for error response format
        self.assertIn("'success': False", views_content,
                     "Error response format not found")
        self.assertIn("'error'", views_content,
                     "Error message in response not found")
        
        # Check for form validation error handling
        self.assertIn("form.errors", views_content,
                     "Form validation error handling not found")


class TestSprint17AuditLoggingIntegration(unittest.TestCase):
    """Test cases for Sprint 17 audit logging integration."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.admin_dashboard_path = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard'
        self.credits_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        
        self.utils_py = self.admin_dashboard_path / 'utils.py'
        self.models_py = self.admin_dashboard_path / 'models.py'
        self.admin_py = self.credits_path / 'admin.py'
    
    def test_log_admin_action_utility_exists(self):
        """Test that log_admin_action utility function exists."""
        self.assertTrue(self.utils_py.exists(),
                       f"utils.py not found at {self.utils_py}")
        
        with open(self.utils_py, 'r') as f:
            utils_content = f.read()
        
        # Check for log_admin_action function
        self.assertIn("def log_admin_action", utils_content,
                     "log_admin_action function not found")
        
        # Check for proper parameters
        self.assertIn("user,", utils_content,
                     "User parameter not found")
        self.assertIn("action: str,", utils_content,
                     "Action parameter with type hint not found")
        self.assertIn("description: str,", utils_content,
                     "Description parameter with type hint not found")
        self.assertIn("request: Optional[HttpRequest] = None", utils_content,
                     "Optional request parameter not found")
        
        # Check for IP address extraction
        self.assertIn("HTTP_X_FORWARDED_FOR", utils_content,
                     "X-Forwarded-For header handling not found")
        self.assertIn("REMOTE_ADDR", utils_content,
                     "REMOTE_ADDR fallback not found")
        
        # Check for AuditLog creation
        self.assertIn("AuditLog.objects.create", utils_content,
                     "AuditLog creation not found")
    
    def test_audit_log_model_exists(self):
        """Test that AuditLog model exists with proper fields."""
        self.assertTrue(self.models_py.exists(),
                       f"models.py not found at {self.models_py}")
        
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for AuditLog model
        self.assertIn("class AuditLog(models.Model)", models_content,
                     "AuditLog model not found")
        
        # Check for action choices
        self.assertIn("ACTION_CHOICES", models_content,
                     "ACTION_CHOICES not found")
        self.assertIn("'CREDIT_ADJUSTMENT'", models_content,
                     "CREDIT_ADJUSTMENT action choice not found")
        
        # Check for required fields
        required_fields = ['user', 'action', 'description', 'timestamp']
        for field in required_fields:
            self.assertIn(f"{field} = models.", models_content,
                         f"{field} field not found in AuditLog model")
        
        # Check for optional fields
        optional_fields = ['ip_address', 'user_agent']
        for field in optional_fields:
            self.assertIn(f"{field} = models.", models_content,
                         f"{field} field not found in AuditLog model")
    
    def test_credit_admin_audit_integration(self):
        """Test that credit admin views integrate with audit logging."""
        self.assertTrue(self.admin_py.exists(),
                       f"admin.py not found at {self.admin_py}")
        
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for audit logging import
        self.assertIn("log_admin_action", admin_content,
                     "log_admin_action import not found")
        
        # Check for audit logging in add_credits_view
        self.assertIn("def add_credits_view", admin_content,
                     "add_credits_view not found")
        
        # Check for audit logging calls in credit operations
        credit_operations = ["add_credits_view", "remove_credits_view", "bulk_add_credits"]
        for operation in credit_operations:
            if f"def {operation}" in admin_content:
                # Find the operation function and check for audit logging
                lines = admin_content.split('\n')
                operation_start = None
                for i, line in enumerate(lines):
                    if f"def {operation}" in line:
                        operation_start = i
                        break
                
                if operation_start:
                    # Look for log_admin_action call in the function
                    operation_content = '\n'.join(lines[operation_start:operation_start + 100])
                    self.assertIn("log_admin_action(", operation_content,
                                 f"{operation} should include audit logging")
                    self.assertIn("'CREDIT_ADJUSTMENT'", operation_content,
                                 f"{operation} should log CREDIT_ADJUSTMENT action")


class TestSprint17CreditHistoryTemplate(unittest.TestCase):
    """Test cases for Sprint 17 credit history template."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates'
        self.credit_history_template = (
            self.templates_path / 'admin_dashboard' / 'partials' / 'credit_history.html'
        )
    
    def test_credit_history_template_exists(self):
        """Test that credit history template exists."""
        self.assertTrue(self.credit_history_template.exists(),
                       f"Credit history template not found at {self.credit_history_template}")
    
    def test_credit_history_template_structure(self):
        """Test credit history template has proper structure."""
        with open(self.credit_history_template, 'r') as f:
            template_content = f.read()
        
        # Check for proper template structure
        self.assertIn("{% load static %}", template_content,
                     "Static files loading not found")
        
        # Check for credit history container
        self.assertIn('id="credit-history"', template_content,
                     "Credit history container not found")
        
        # Check for table structure
        self.assertIn("<table", template_content,
                     "Table structure not found")
        self.assertIn("<thead>", template_content,
                     "Table header not found")
        self.assertIn("<tbody>", template_content,
                     "Table body not found")
        
        # Check for adjustment iteration
        self.assertIn("{% for adjustment in credit_adjustments %}", template_content,
                     "Credit adjustment iteration not found")
        
        # Check for amount display logic
        self.assertIn("{% if adjustment.amount > 0 %}", template_content,
                     "Amount sign logic not found")
        self.assertIn("tag is-success", template_content,
                     "Positive amount styling not found")
        self.assertIn("tag is-warning", template_content,
                     "Negative amount styling not found")
        
        # Check for date formatting
        self.assertIn("adjustment.created_at|date", template_content,
                     "Date formatting not found")
        self.assertIn("adjustment.created_at|time", template_content,
                     "Time formatting not found")


class TestSprint17CreditAdjustmentFormTemplate(unittest.TestCase):
    """Test cases for Sprint 17 credit adjustment form template."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates'
        self.credit_form_template = (
            self.templates_path / 'admin_dashboard' / 'partials' / 'credit_adjustment_form.html'
        )
    
    def test_credit_adjustment_form_template_exists(self):
        """Test that credit adjustment form template exists."""
        self.assertTrue(self.credit_form_template.exists(),
                       f"Credit adjustment form template not found at {self.credit_form_template}")
    
    def test_credit_adjustment_form_structure(self):
        """Test credit adjustment form template has proper structure."""
        with open(self.credit_form_template, 'r') as f:
            template_content = f.read()
        
        # Check for HTMX integration
        self.assertIn("hx-post=", template_content,
                     "HTMX post directive not found")
        self.assertIn("hx-swap=", template_content,
                     "HTMX swap directive not found")
        self.assertIn("hx-on::", template_content,
                     "HTMX event handling not found")
        
        # Check for Alpine.js integration
        self.assertIn("x-data=", template_content,
                     "Alpine.js data directive not found")
        self.assertIn("x-model=", template_content,
                     "Alpine.js model directive not found")
        
        # Check for form fields
        self.assertIn('name="action"', template_content,
                     "Action field not found")
        self.assertIn('name="amount"', template_content,
                     "Amount field not found")
        self.assertIn('name="reason"', template_content,
                     "Reason field not found")
        
        # Check for CSRF protection
        self.assertIn("{% csrf_token %}", template_content,
                     "CSRF token not found")
        
        # Check for balance display
        self.assertIn("Current Balance:", template_content,
                     "Current balance display not found")
        self.assertIn("balance_breakdown", template_content,
                     "Balance breakdown display not found")
        
        # Check for JavaScript response handling
        self.assertIn("handleCreditAdjustmentResponse", template_content,
                     "Response handling function not found")
    
    def test_credit_adjustment_form_validation(self):
        """Test credit adjustment form has proper validation."""
        with open(self.credit_form_template, 'r') as f:
            template_content = f.read()
        
        # Check for HTML5 validation attributes
        self.assertIn('required', template_content,
                     "Required attribute not found")
        self.assertIn('step="0.01"', template_content,
                     "Decimal step validation not found")
        self.assertIn('min="0.01"', template_content,
                     "Minimum value validation not found")
        
        # Check for maxlength validation
        self.assertIn('maxlength="255"', template_content,
                     "Reason field maxlength validation not found")


class TestSprint17UserDetailIntegration(unittest.TestCase):
    """Test cases for Sprint 17 user detail view integration."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates'
        self.user_detail_template = self.templates_path / 'admin_dashboard' / 'user_detail.html'
    
    def test_user_detail_credit_integration(self):
        """Test that user detail template integrates credit adjustment functionality."""
        self.assertTrue(self.user_detail_template.exists(),
                       f"User detail template not found at {self.user_detail_template}")
        
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for credit adjustment button
        self.assertIn("Adjust Credits", template_content,
                     "Adjust Credits button not found")
        
        # Check for credit information section
        self.assertIn("Credit Information", template_content,
                     "Credit Information section not found")
        
        # Check for Alpine.js integration for credit form toggle
        self.assertIn("showCreditForm", template_content,
                     "Credit form toggle variable not found")
        self.assertIn("showCreditHistory", template_content,
                     "Credit history toggle variable not found")
        
        # Check for event handling
        self.assertIn("@close-credit-form.window", template_content,
                     "Credit form close event handling not found")


class TestSprint17ValidationCriteria(unittest.TestCase):
    """Test cases to verify Sprint 17 validation criteria are met."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    def test_admin_can_adjust_credits_functionality(self):
        """Test that admin credit adjustment functionality is complete."""
        # Check that all required components exist
        required_files = [
            'quickscale/project_templates/credits/forms.py',
            'quickscale/project_templates/admin_dashboard/views.py',
            'quickscale/project_templates/admin_dashboard/utils.py',
            'quickscale/project_templates/admin_dashboard/models.py',
            'quickscale/project_templates/templates/admin_dashboard/partials/credit_adjustment_form.html',
            'quickscale/project_templates/templates/admin_dashboard/partials/credit_history.html'
        ]
        
        for file_path in required_files:
            full_path = self.base_path / file_path
            self.assertTrue(full_path.exists(),
                           f"Required file not found: {file_path}")
    
    def test_credit_adjustment_validation_complete(self):
        """Test that credit adjustment validation is properly implemented."""
        forms_py = self.base_path / 'quickscale' / 'project_templates' / 'credits' / 'forms.py'
        
        with open(forms_py, 'r') as f:
            forms_content = f.read()
        
        # Check for comprehensive validation
        validation_checks = [
            "MinValueValidator",  # Amount validation
            "def clean_amount",   # Custom amount validation
            "def clean_reason",   # Reason validation
            "amount <= 0",        # Positive amount check
            "strip()",            # Reason trimming
        ]
        
        for check in validation_checks:
            self.assertIn(check, forms_content,
                         f"Validation check missing: {check}")
    
    def test_audit_logging_complete(self):
        """Test that audit logging for credit adjustments is complete."""
        utils_py = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'utils.py'
        models_py = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'models.py'
        
        # Check utils.py for logging function
        with open(utils_py, 'r') as f:
            utils_content = f.read()
        
        self.assertIn("def log_admin_action", utils_content,
                     "log_admin_action function not found")
        self.assertIn("AuditLog.objects.create", utils_content,
                     "AuditLog creation not found")
        
        # Check models.py for AuditLog model
        with open(models_py, 'r') as f:
            models_content = f.read()
        
        self.assertIn("class AuditLog", models_content,
                     "AuditLog model not found")
        self.assertIn("'CREDIT_ADJUSTMENT'", models_content,
                     "CREDIT_ADJUSTMENT action type not found")
    
    def test_credit_history_display_complete(self):
        """Test that credit history display functionality is complete."""
        history_template = (
            self.base_path / 'quickscale' / 'project_templates' / 'templates' / 
            'admin_dashboard' / 'partials' / 'credit_history.html'
        )
        
        with open(history_template, 'r') as f:
            template_content = f.read()
        
        # Check for essential credit history elements
        history_elements = [
            "{% for adjustment in credit_adjustments %}",
            "adjustment.amount",
            "adjustment.created_at",
            "adjustment.description",
            "{% if adjustment.amount > 0 %}",  # Positive/negative handling
        ]
        
        for element in history_elements:
            self.assertIn(element, template_content,
                         f"Credit history element missing: {element}")


class TestSprint17IntegrationPoints(unittest.TestCase):
    """Test cases for Sprint 17 integration with existing functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    def test_integration_with_existing_credit_system(self):
        """Test that Sprint 17 integrates properly with existing credit system."""
        admin_py = self.base_path / 'quickscale' / 'project_templates' / 'credits' / 'admin.py'
        
        with open(admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check that credit adjustment uses existing model methods
        self.assertIn("account.add_credits", admin_content,
                     "Should use existing add_credits method")
        self.assertIn("account.get_balance", admin_content,
                     "Should use existing get_balance method")
        
        # Check that proper credit types are used
        self.assertIn("credit_type='ADMIN'", admin_content,
                     "Should use ADMIN credit type")
    
    def test_integration_with_admin_dashboard(self):
        """Test that Sprint 17 integrates with existing admin dashboard."""
        views_py = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'views.py'
        
        with open(views_py, 'r') as f:
            views_content = f.read()
        
        # Check for proper authentication decorators
        self.assertIn("@login_required", views_content,
                     "Should use login_required decorator")
        self.assertIn("@user_passes_test(lambda u: u.is_staff)", views_content,
                     "Should check for staff users")
        
        # Check for HTMX integration
        self.assertIn("JsonResponse", views_content,
                     "Should return JSON responses for HTMX")


class TestUserDetailTemplateRendering(unittest.TestCase):
    """Test cases for user detail template rendering fixes."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.user_detail_template = (
            self.base_path / 'quickscale' / 'project_templates' / 'templates' / 
            'admin_dashboard' / 'user_detail.html'
        )
    
    def test_template_does_not_contain_literal_newlines(self):
        """Test that template does not contain literal \\n characters in conditionals."""
        self.assertTrue(self.user_detail_template.exists(),
                       f"User detail template not found at {self.user_detail_template}")
        
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check that Django template tags are on single lines to prevent whitespace issues
        problematic_patterns = [
            "{% if selected_user.first_name or selected_user.last_name %}\n                                    {{ selected_user.first_name }}",
            "{% else %}\n                                    <span",
            "{% endif %}\n                            </p>",
            "{% if selected_user.last_login %}\n                                    {{ selected_user.last_login",
            "{% if selected_user.is_active %}\n                                    <span"
        ]
        
        for pattern in problematic_patterns:
            self.assertNotIn(pattern, template_content,
                           f"Template contains problematic whitespace pattern: {pattern[:50]}...")
    
    def test_conditional_tags_are_condensed(self):
        """Test that conditional Django template tags are properly condensed."""
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for properly condensed conditional patterns
        condensed_patterns = [
            "{% if selected_user.first_name or selected_user.last_name %}{{ selected_user.first_name }} {{ selected_user.last_name }}{% else %}<span class=\"has-text-grey-light\">Not set</span>{% endif %}",
            "{% if selected_user.last_login %}{{ selected_user.last_login|date:\"M d, Y H:i\" }}{% else %}<span class=\"has-text-grey-light\">Never</span>{% endif %}",
            "{% if selected_user.is_active %}<span class=\"tag is-success\">Active</span>{% else %}<span class=\"tag is-danger\">Inactive</span>{% endif %}"
        ]
        
        for pattern in condensed_patterns:
            self.assertIn(pattern, template_content,
                         f"Template should contain condensed pattern: {pattern[:50]}...")
    
    def test_template_has_proper_html_structure(self):
        """Test that template has proper HTML structure without broken tags."""
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for proper card structure
        self.assertIn('<div class="card-content">', template_content,
                     "Should have card-content div")
        self.assertIn('<div class="content">', template_content,
                     "Should have content div inside card-content")
        
        # Ensure no broken div structure
        card_content_count = template_content.count('<div class="card-content">')
        content_div_count = template_content.count('<div class="content">')
        
        # Basic sanity check - there should be multiple card-content divs
        self.assertGreater(card_content_count, 0, "Should have at least one card-content div")
        self.assertGreater(content_div_count, 0, "Should have at least one content div")


class TestHTMXIntegrationFixes(unittest.TestCase):
    """Test cases for HTMX integration fixes."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.user_detail_template = (
            self.base_path / 'quickscale' / 'project_templates' / 'templates' / 
            'admin_dashboard' / 'user_detail.html'
        )
    
    def test_htmx_trigger_mechanism_fixed(self):
        """Test that HTMX trigger mechanism is properly implemented."""
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check that revealed trigger is replaced with htmx:trigger
        self.assertIn('hx-trigger="htmx:trigger"', template_content,
                     "Should use htmx:trigger instead of revealed")
        
        # Should not contain the problematic revealed trigger
        self.assertNotIn('hx-trigger="revealed"', template_content,
                        "Should not use revealed trigger with Alpine.js")
    
    def test_alpine_js_htmx_integration(self):
        """Test that Alpine.js properly triggers HTMX requests."""
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for manual HTMX triggering in Alpine.js click handlers
        manual_trigger_patterns = [
            "setTimeout(() => htmx.trigger('#credit-adjustment-container div', 'htmx:trigger'), 100)",
            "setTimeout(() => htmx.trigger('#credit-history-container div', 'htmx:trigger'), 100)"
        ]
        
        for pattern in manual_trigger_patterns:
            self.assertIn(pattern, template_content,
                         f"Should contain manual HTMX trigger: {pattern}")
    
    def test_button_click_handlers_updated(self):
        """Test that button click handlers properly integrate Alpine.js and HTMX."""
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for updated click handlers that trigger HTMX after showing modals
        credit_form_handler = (
            "@click=\"showCreditForm = !showCreditForm; showCreditHistory = false; "
            "if(showCreditForm) { setTimeout(() => htmx.trigger('#credit-adjustment-container div', 'htmx:trigger'), 100); }\""
        )
        
        credit_history_handler = (
            "@click=\"showCreditHistory = !showCreditHistory; showCreditForm = false; "
            "if(showCreditHistory) { setTimeout(() => htmx.trigger('#credit-history-container div', 'htmx:trigger'), 100); }\""
        )
        
        self.assertIn(credit_form_handler, template_content,
                     "Credit form button should have updated click handler")
        self.assertIn(credit_history_handler, template_content,
                     "Credit history button should have updated click handler")
    
    def test_htmx_endpoints_accessibility(self):
        """Test that HTMX endpoints are properly configured."""
        # Check URLs are properly configured
        urls_py = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'urls.py'
        
        with open(urls_py, 'r') as f:
            urls_content = f.read()
        
        # Check for credit adjustment and history endpoints
        required_urls = [
            "path('users/<int:user_id>/credit-adjustment/', views.user_credit_adjustment, name='user_credit_adjustment')",
            "path('users/<int:user_id>/credit-history/', views.user_credit_history, name='user_credit_history')"
        ]
        
        for url_pattern in required_urls:
            self.assertIn(url_pattern, urls_content,
                         f"URL pattern should be present: {url_pattern}")
    
    def test_htmx_response_format(self):
        """Test that HTMX endpoints return proper HTML responses."""
        views_py = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'views.py'
        
        with open(views_py, 'r') as f:
            views_content = f.read()
        
        # Check for HttpResponse usage in credit adjustment and history views (not JsonResponse)
        self.assertIn("def user_credit_adjustment(request: HttpRequest, user_id: int) -> HttpResponse:",
                     views_content, "Credit adjustment view should return HttpResponse")
        self.assertIn("def user_credit_history(request: HttpRequest, user_id: int) -> HttpResponse:",
                     views_content, "Credit history view should return HttpResponse")
        
        # Check for proper response structure - views should use render() directly
        response_patterns = [
            "return render(request, 'admin_dashboard/partials/credit_adjustment_form.html', context)",
            "return render(request, 'admin_dashboard/partials/credit_history.html', context)"
        ]
        
        for pattern in response_patterns:
            self.assertIn(pattern, views_content,
                         f"Views should include direct render pattern: {pattern}")
        
        # Ensure that JSON wrapping is not used for GET requests
        self.assertNotIn("return JsonResponse({\n        'success': True,\n        'html': html", 
                         views_content, "Views should not wrap HTML in JSON for HTMX requests")


class TestTemplateUIConsistency(unittest.TestCase):
    """Test cases for template UI consistency after fixes."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.user_detail_template = (
            self.base_path / 'quickscale' / 'project_templates' / 'templates' / 
            'admin_dashboard' / 'user_detail.html'
        )
        self.credit_form_template = (
            self.base_path / 'quickscale' / 'project_templates' / 'templates' / 
            'admin_dashboard' / 'partials' / 'credit_adjustment_form.html'
        )
        self.credit_history_template = (
            self.base_path / 'quickscale' / 'project_templates' / 'templates' / 
            'admin_dashboard' / 'partials' / 'credit_history.html'
        )
    
    def test_modal_functionality_elements(self):
        """Test that modal functionality elements are properly implemented."""
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for Alpine.js modal state variables
        modal_variables = [
            "showCreditForm: false",
            "showCreditHistory: false"
        ]
        
        for variable in modal_variables:
            self.assertIn(variable, template_content,
                         f"Modal variable should be present: {variable}")
        
        # Check for transition effects
        transition_attributes = [
            "x-transition:enter",
            "x-transition:leave"
        ]
        
        for attribute in transition_attributes:
            self.assertIn(attribute, template_content,
                         f"Transition attribute should be present: {attribute}")
    
    def test_button_accessibility_and_styling(self):
        """Test that buttons have proper accessibility and styling."""
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for proper button classes and icons
        button_elements = [
            'class="button is-small is-success"',  # Adjust Credits button
            'class="button is-small is-info"',     # History button
            '<i class="fas fa-coins"></i>',        # Credits icon
            '<i class="fas fa-history"></i>'       # History icon
        ]
        
        for element in button_elements:
            self.assertIn(element, template_content,
                         f"Button element should be present: {element}")
    
    def test_credit_form_integration(self):
        """Test that credit form is properly integrated."""
        # Check that credit form template exists
        self.assertTrue(self.credit_form_template.exists(),
                       f"Credit form template should exist at {self.credit_form_template}")
        
        with open(self.credit_form_template, 'r') as f:
            form_content = f.read()
        
        # Check for essential form elements
        form_elements = [
            'hx-post="{% url \'admin_dashboard:user_credit_adjustment\'',
            'hx-on::after-request="handleCreditAdjustmentResponse(event)"',
            'name="action"',
            'name="amount"',
            'name="reason"'
        ]
        
        for element in form_elements:
            self.assertIn(element, form_content,
                         f"Form element should be present: {element}")
    
    def test_credit_history_integration(self):
        """Test that credit history is properly integrated."""
        # Check that credit history template exists
        self.assertTrue(self.credit_history_template.exists(),
                       f"Credit history template should exist at {self.credit_history_template}")
        
        with open(self.credit_history_template, 'r') as f:
            history_content = f.read()
        
        # Check for essential history elements
        history_elements = [
            "{% for adjustment in credit_adjustments %}",
            "adjustment.amount",
            "adjustment.created_at",
            "adjustment.description"
        ]
        
        for element in history_elements:
            self.assertIn(element, history_content,
                         f"History element should be present: {element}")


class TestRegressionPrevention(unittest.TestCase):
    """Test cases to prevent regression of the fixed issues."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.user_detail_template = (
            self.base_path / 'quickscale' / 'project_templates' / 'templates' / 
            'admin_dashboard' / 'user_detail.html'
        )
    
    def test_no_literal_newline_artifacts(self):
        """Test that template does not render literal \\n characters."""
        with open(self.user_detail_template, 'r') as f:
            template_lines = f.readlines()
        
        # Check that template tags with conditionals are properly formatted
        # Look for patterns that would cause literal \n to appear
        for i, line in enumerate(template_lines):
            # If line contains a Django conditional start
            if "{% if " in line and not line.strip().endswith("%}"):
                # The next line should not be indented Django template content
                # This prevents whitespace from being rendered literally
                if i + 1 < len(template_lines):
                    next_line = template_lines[i + 1]
                    # If next line has significant indentation and template content,
                    # it could cause whitespace issues
                    if (next_line.startswith("                                    ") and 
                        ("{{" in next_line or "{%" in next_line)):
                        self.fail(f"Line {i+1}: Potential whitespace issue detected. "
                                f"Template conditionals should be on single lines to prevent "
                                f"literal newlines: {line.strip()}")
    
    def test_htmx_triggers_are_functional(self):
        """Test that HTMX triggers are configured to work with Alpine.js."""
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Ensure 'revealed' trigger is not used (doesn't work well with Alpine.js)
        self.assertNotIn('hx-trigger="revealed"', template_content,
                        "Should not use 'revealed' trigger which doesn't work with Alpine.js")
        
        # Ensure manual triggering is implemented
        self.assertIn('htmx.trigger(', template_content,
                     "Should use manual htmx.trigger() for Alpine.js integration")
        
        # Ensure timeout is used to allow Alpine.js to finish showing elements
        self.assertIn('setTimeout(', template_content,
                     "Should use setTimeout to ensure proper timing with Alpine.js")
    
    def test_button_functionality_preserved(self):
        """Test that button functionality is preserved after fixes."""
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check that buttons still toggle the modals
        self.assertIn("showCreditForm = !showCreditForm", template_content,
                     "Credit form button should toggle modal state")
        self.assertIn("showCreditHistory = !showCreditHistory", template_content,
                     "Credit history button should toggle modal state")
        
        # Check that buttons also hide the other modal
        self.assertIn("showCreditHistory = false", template_content,
                     "Credit form button should hide history modal")
        self.assertIn("showCreditForm = false", template_content,
                     "Credit history button should hide form modal")
    
    def test_event_handling_preserved(self):
        """Test that event handling functionality is preserved."""
        with open(self.user_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for credit form close event handling
        self.assertIn("@close-credit-form.window", template_content,
                     "Should handle credit form close events")
        
        # Check for JavaScript function to handle responses
        self.assertIn("handleCreditAdjustmentResponse", template_content,
                     "Should have function to handle credit adjustment responses")


class TestCreditAdjustmentFormFix(unittest.TestCase):
    """Test cases for the credit adjustment form submission fix."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.form_template = self.base_path / 'quickscale' / 'project_templates' / 'templates' / 'admin_dashboard' / 'partials' / 'credit_adjustment_form.html'
    
    def test_form_submission_state_management(self):
        """Test that form submission state is properly managed to prevent infinite processing."""
        with open(self.form_template, 'r') as f:
            form_content = f.read()
        
        # Check that isSubmitting is set correctly on before-request
        self.assertIn('hx-on::before-request="isSubmitting = true"', form_content,
                     "Form should set isSubmitting to true on before-request")
        
        # Check that submit button doesn't have manual click handler that could interfere
        self.assertNotIn('x-on:click="isSubmitting = true"', form_content,
                        "Submit button should not have manual click handler that sets isSubmitting")
        
        # Check that after-request handler exists to reset state
        self.assertIn('hx-on::after-request="handleCreditAdjustmentResponse(event)"', form_content,
                     "Form should have after-request handler to reset state")
        
    def test_response_handler_resets_state(self):
        """Test that the response handler properly resets the submitting state."""
        with open(self.form_template, 'r') as f:
            form_content = f.read()
        
        # Check that the response handler resets isSubmitting state immediately
        state_reset_patterns = [
            "alpineData.isSubmitting = false;",
            "const alpineData = Alpine.$data(form);",
            "// Reset submitting state immediately"
        ]
        
        for pattern in state_reset_patterns:
            self.assertIn(pattern, form_content, f"Response handler should include: {pattern}")
        
    def test_form_validation_prevents_infinite_submissions(self):
        """Test that form validation prevents submission with invalid data."""
        with open(self.form_template, 'r') as f:
            form_content = f.read()
        
        # Check that submit button is properly disabled during submission and validation
        button_disabled_pattern = ':disabled="isSubmitting || !amount || !reason"'
        self.assertIn(button_disabled_pattern, form_content,
                     "Submit button should be disabled during submission and when form is invalid")
        
        # Check that form fields have proper validation
        required_patterns = [
            'name="amount"',
            'name="reason"', 
            'required',
            'min="0.01"'
        ]
        
        for pattern in required_patterns:
            self.assertIn(pattern, form_content, f"Form should have proper validation: {pattern}")
    
    def test_alpine_js_data_structure(self):
        """Test that Alpine.js data structure is correctly defined."""
        with open(self.form_template, 'r') as f:
            form_content = f.read()
        
        # Check Alpine.js data structure
        alpine_data_patterns = [
            "x-data=\"{",
            "action: 'add',",
            "amount: '',",
            "reason: '',",
            "isSubmitting: false"
        ]
        
        for pattern in alpine_data_patterns:
            self.assertIn(pattern, form_content, f"Alpine.js data should include: {pattern}")
    
    def test_success_response_handling(self):
        """Test that success responses properly reset form and update UI."""
        with open(self.form_template, 'r') as f:
            form_content = f.read()
        
        # Check that success handling resets form data
        success_reset_patterns = [
            "alpineData.amount = '';",
            "alpineData.reason = '';", 
            "alpineData.action = 'add';",
            "data.new_balance.toFixed(1)"
        ]
        
        for pattern in success_reset_patterns:
            self.assertIn(pattern, form_content, f"Success handler should include: {pattern}")


if __name__ == '__main__':
    unittest.main() 
