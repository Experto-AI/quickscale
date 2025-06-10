"""
Tests for Sprint 16: Simple Audit Logging.

These tests verify the functionality added in Sprint 16:
- AuditLog model for tracking admin actions
- Audit logging utility functions for user changes
- Audit log viewing with filtering (user, action, date)
- Admin integration with proper permissions
- Template rendering and functionality

Tests the QuickScale project generator template functionality, not Django-generated project.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import os

from tests.utils import ProjectTestMixin, create_test_project_structure


class TestSprint16AuditLogModelTemplate(unittest.TestCase):
    """Test Sprint 16 AuditLog model template generation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.project_name = "test_sprint16_project"
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_admin_dashboard_models_template_contains_audit_log(self):
        """Test that admin_dashboard models template contains AuditLog model."""
        # Get the path to the admin_dashboard models template
        models_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "models.py"
        
        # Check that the template file exists
        self.assertTrue(models_template_path.exists(), "Admin dashboard models template should exist")
        
        # Read the template content
        with open(models_template_path, 'r') as f:
            content = f.read()
        
        # Check for AuditLog model
        self.assertIn("class AuditLog(models.Model)", content, "Should contain AuditLog model")
        self.assertIn("ACTION_CHOICES", content, "Should have action choices")
        
        # Check for required fields
        self.assertIn("user = models.ForeignKey", content, "Should have user field")
        self.assertIn("action = models.CharField", content, "Should have action field")
        self.assertIn("description = models.TextField", content, "Should have description field")
        self.assertIn("timestamp = models.DateTimeField", content, "Should have timestamp field")
        
        # Check for optional fields
        self.assertIn("ip_address = models.GenericIPAddressField", content, "Should have ip_address field")
        self.assertIn("user_agent = models.TextField", content, "Should have user_agent field")
        
        # Check for model metadata
        self.assertIn("ordering = ['-timestamp']", content, "Should order by timestamp descending")
        self.assertIn("related_name='audit_logs'", content, "Should have proper related name")
    
    def test_audit_log_action_choices_completeness(self):
        """Test that AuditLog model has all required action choices."""
        # Get the path to the admin_dashboard models template
        models_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "models.py"
        
        # Read the template content
        with open(models_template_path, 'r') as f:
            content = f.read()
        
        # Check for all expected action choices
        expected_actions = [
            'USER_SEARCH', 'USER_VIEW', 'USER_EDIT', 'CREDIT_ADJUSTMENT',
            'SERVICE_TOGGLE', 'PRODUCT_SYNC', 'ADMIN_LOGIN', 'ADMIN_LOGOUT', 'OTHER'
        ]
        
        for action in expected_actions:
            self.assertIn(f"'{action}'", content, f"Should include {action} in action choices")
    
    def test_audit_log_model_str_method(self):
        """Test that AuditLog model has proper string representation."""
        # Get the path to the admin_dashboard models template
        models_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "models.py"
        
        # Read the template content
        with open(models_template_path, 'r') as f:
            content = f.read()
        
        # Check for __str__ method
        self.assertIn("def __str__(self)", content, "Should have __str__ method")
        self.assertIn("user_email = self.user.email if self.user else 'Unknown User'", content,
                     "Should handle missing user gracefully")
        self.assertIn("get_action_display()", content, "Should use human-readable action display")


class TestSprint16AuditLogUtilsTemplate(unittest.TestCase):
    """Test Sprint 16 audit logging utility functions template."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_admin_dashboard_utils_template_contains_log_function(self):
        """Test that admin_dashboard utils template contains log_admin_action function."""
        # Get the path to the admin_dashboard utils template
        utils_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "utils.py"
        
        # Check that the template file exists
        self.assertTrue(utils_template_path.exists(), "Admin dashboard utils template should exist")
        
        # Read the template content
        with open(utils_template_path, 'r') as f:
            content = f.read()
        
        # Check for log_admin_action function
        self.assertIn("def log_admin_action(", content, "Should contain log_admin_action function")
        self.assertIn("user,", content, "Should accept user parameter")
        self.assertIn("action: str,", content, "Should accept action parameter with type hint")
        self.assertIn("description: str,", content, "Should accept description parameter with type hint")
        self.assertIn("request: Optional[HttpRequest] = None", content, "Should accept optional request parameter")
        
        # Check for IP address extraction
        self.assertIn("HTTP_X_FORWARDED_FOR", content, "Should handle X-Forwarded-For header")
        self.assertIn("REMOTE_ADDR", content, "Should handle REMOTE_ADDR as fallback")
        
        # Check for user agent extraction
        self.assertIn("HTTP_USER_AGENT", content, "Should extract user agent")
        
        # Check for AuditLog creation
        self.assertIn("AuditLog.objects.create", content, "Should create AuditLog entry")
    
    def test_admin_dashboard_utils_template_contains_ip_helper(self):
        """Test that admin_dashboard utils template contains get_client_ip helper."""
        # Get the path to the admin_dashboard utils template
        utils_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "utils.py"
        
        # Read the template content
        with open(utils_template_path, 'r') as f:
            content = f.read()
        
        # Check for get_client_ip function
        self.assertIn("def get_client_ip(", content, "Should contain get_client_ip function")
        self.assertIn("request: HttpRequest", content, "Should accept HttpRequest parameter")
        self.assertIn("Optional[str]", content, "Should return Optional[str]")
        
        # Check for proper IP extraction logic
        self.assertIn("x_forwarded_for.split(',')[0].strip()", content, "Should extract first IP from X-Forwarded-For")


class TestSprint16AuditLogViewsTemplate(unittest.TestCase):
    """Test Sprint 16 audit log views template generation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_admin_dashboard_views_template_contains_audit_log_view(self):
        """Test that admin_dashboard views template contains audit_log view."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for audit_log function
        self.assertIn("def audit_log(", content, "Should contain audit_log function")
        self.assertIn("@user_passes_test(lambda u: u.is_staff)", content, "Should have staff permission decorator")
        
        # Check for filtering functionality
        self.assertIn("user_filter = request.GET.get('user')", content, "Should support user filtering")
        self.assertIn("action_filter = request.GET.get('action')", content, "Should support action filtering")
        self.assertIn("date_from = request.GET.get('date_from')", content, "Should support date from filtering")
        self.assertIn("date_to = request.GET.get('date_to')", content, "Should support date to filtering")
        
        # Check for pagination
        self.assertIn("Paginator(logs, 50)", content, "Should include pagination with 50 items per page")
        
        # Check for template rendering
        self.assertIn("render(request, 'admin_dashboard/audit_log.html'", content, "Should render audit_log template")
    
    def test_audit_log_view_filtering_implementation(self):
        """Test that audit log view implements proper filtering."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for filter implementations
        self.assertIn("logs.filter(user_id=user_id)", content, "Should filter by user ID")
        self.assertIn("logs.filter(action=action_filter)", content, "Should filter by action")
        self.assertIn("timestamp__date__gte=date_from_obj", content, "Should filter by date from")
        self.assertIn("timestamp__date__lte=date_to_obj", content, "Should filter by date to")
        
        # Check for error handling
        self.assertIn("try:", content, "Should include error handling")
        self.assertIn("except (ValueError, TypeError):", content, "Should handle invalid user ID")
        self.assertIn("except ValueError:", content, "Should handle invalid date format")
    
    def test_admin_dashboard_views_integration_with_audit_logging(self):
        """Test that admin dashboard views are integrated with audit logging."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check that audit logging is imported
        self.assertIn("from .utils import log_admin_action", content, "Should import log_admin_action")
        self.assertIn("from .models import AuditLog", content, "Should import AuditLog model")
        
        # Check that user_search logs audit entry
        if "def user_search(" in content:
            # Find the user_search function and verify it logs
            lines = content.split('\n')
            user_search_start = None
            for i, line in enumerate(lines):
                if "def user_search(" in line:
                    user_search_start = i
                    break
            
            if user_search_start:
                # Look for log_admin_action call in the next 50 lines
                user_search_section = '\n'.join(lines[user_search_start:user_search_start + 50])
                self.assertIn("log_admin_action(", user_search_section, "user_search should log audit entry")
                self.assertIn("'USER_SEARCH'", user_search_section, "Should log USER_SEARCH action")
        
        # Check that user_detail logs audit entry
        if "def user_detail(" in content:
            lines = content.split('\n')
            user_detail_start = None
            for i, line in enumerate(lines):
                if "def user_detail(" in line:
                    user_detail_start = i
                    break
            
            if user_detail_start:
                # Look for log_admin_action call in the next 50 lines
                user_detail_section = '\n'.join(lines[user_detail_start:user_detail_start + 50])
                self.assertIn("log_admin_action(", user_detail_section, "user_detail should log audit entry")
                self.assertIn("'USER_VIEW'", user_detail_section, "Should log USER_VIEW action")


class TestSprint16AuditLogUrlsTemplate(unittest.TestCase):
    """Test Sprint 16 audit log URLs template generation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_admin_dashboard_urls_template_contains_audit_routes(self):
        """Test that admin_dashboard URLs template contains audit log routes."""
        # Get the path to the admin_dashboard URLs template
        urls_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "urls.py"
        
        # Check that the template file exists
        self.assertTrue(urls_template_path.exists(), "Admin dashboard URLs template should exist")
        
        # Read the template content
        with open(urls_template_path, 'r') as f:
            content = f.read()
        
        # Check for audit log URL
        self.assertIn("path('audit/', views.audit_log, name='audit_log')", content,
                     "Should contain audit log URL")
        
        # Check for URL comments/organization
        if "# Audit log URLs" in content:
            self.assertIn("# Audit log URLs", content, "Should have organized URL comments")


class TestSprint16AuditLogAdminTemplate(unittest.TestCase):
    """Test Sprint 16 audit log admin interface template."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_admin_dashboard_admin_template_contains_audit_log_admin(self):
        """Test that admin_dashboard admin template contains AuditLog admin."""
        # Get the path to the admin_dashboard admin template
        admin_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "admin.py"
        
        # Check that the template file exists
        self.assertTrue(admin_template_path.exists(), "Admin dashboard admin template should exist")
        
        # Read the template content
        with open(admin_template_path, 'r') as f:
            content = f.read()
        
        # Check for AuditLog import and registration
        self.assertIn("from .models import AuditLog", content, "Should import AuditLog")
        self.assertIn("@admin.register(AuditLog)", content, "Should register AuditLog with admin")
        self.assertIn("class AuditLogAdmin(admin.ModelAdmin)", content, "Should have AuditLogAdmin class")
        
        # Check for proper admin configuration
        self.assertIn("list_display", content, "Should configure list_display")
        self.assertIn("list_filter", content, "Should configure list_filter")
        self.assertIn("search_fields", content, "Should configure search_fields")
        
        # Check for security measures
        self.assertIn("has_add_permission", content, "Should prevent manual creation")
        self.assertIn("has_change_permission", content, "Should prevent editing")
        self.assertIn("return False", content, "Should return False for add/change permissions")


class TestSprint16AuditLogTemplateFiles(unittest.TestCase):
    """Test Sprint 16 audit log template files."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_audit_log_template_exists_and_structure(self):
        """Test that audit log template exists and has proper structure."""
        # Get the path to the audit log template
        template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "templates" / "admin_dashboard" / "audit_log.html"
        
        # Check that the template file exists
        self.assertTrue(template_path.exists(), "Audit log template should exist")
        
        # Read the template content
        with open(template_path, 'r') as f:
            content = f.read()
        
        # Check for basic template structure
        self.assertIn("{% extends", content, "Should extend a base template")
        self.assertIn("{% block", content, "Should use template blocks")
        
        # Check for filtering form
        self.assertIn("form", content.lower(), "Should contain filtering form")
        self.assertIn("select", content.lower(), "Should contain select elements for filters")
        
        # Check for pagination
        self.assertIn("pagination", content.lower(), "Should include pagination")
        
        # Check for audit log display
        self.assertIn("logs", content, "Should display audit logs")
        self.assertIn("timestamp", content, "Should display timestamps")
        self.assertIn("action", content, "Should display actions")
        self.assertIn("description", content, "Should display descriptions")
    
    def test_audit_log_template_filtering_elements(self):
        """Test that audit log template includes proper filtering elements."""
        # Get the path to the audit log template
        template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "templates" / "admin_dashboard" / "audit_log.html"
        
        if template_path.exists():
            # Read the template content
            with open(template_path, 'r') as f:
                content = f.read()
            
            # Check for filter form elements
            self.assertIn("user", content.lower(), "Should have user filter")
            self.assertIn("action", content.lower(), "Should have action filter")
            self.assertIn("date", content.lower(), "Should have date filters")
            
            # Check for template variables
            self.assertIn("audit_users", content, "Should use audit_users context variable")
            self.assertIn("action_choices", content, "Should use action_choices context variable")


class TestSprint16MigrationTemplate(unittest.TestCase):
    """Test Sprint 16 migration template generation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_admin_dashboard_migration_contains_audit_log(self):
        """Test that admin_dashboard migration contains AuditLog model creation."""
        # Get the path to the admin_dashboard migrations directory
        migrations_dir = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "migrations"
        
        # Check that migrations directory exists
        self.assertTrue(migrations_dir.exists(), "Admin dashboard migrations directory should exist")
        
        # Look for migration files that contain AuditLog
        migration_files = list(migrations_dir.glob("*.py"))
        audit_log_migration_found = False
        
        for migration_file in migration_files:
            if migration_file.name == "__init__.py":
                continue
                
            with open(migration_file, 'r') as f:
                content = f.read()
                
            if "AuditLog" in content:
                audit_log_migration_found = True
                
                # Check for model creation
                self.assertIn("CreateModel", content, "Should create AuditLog model")
                self.assertIn("name='AuditLog'", content, "Should name the model AuditLog")
                
                # Check for field definitions
                self.assertIn("'action'", content, "Should include action field")
                self.assertIn("'description'", content, "Should include description field")
                self.assertIn("'timestamp'", content, "Should include timestamp field")
                self.assertIn("'user'", content, "Should include user field")
                self.assertIn("'ip_address'", content, "Should include ip_address field")
                self.assertIn("'user_agent'", content, "Should include user_agent field")
                
                break
        
        self.assertTrue(audit_log_migration_found, "Should find migration file containing AuditLog model")


class TestSprint16PermissionControlsTemplate(unittest.TestCase):
    """Test Sprint 16 permission control implementation in templates."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_audit_log_view_has_staff_permission_decorator(self):
        """Test that audit log view has proper staff permission decorator."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Find audit_log function and check it has permission decorator
        lines = content.split('\n')
        audit_log_line = None
        for i, line in enumerate(lines):
            if "def audit_log(" in line:
                audit_log_line = i
                break
        
        self.assertIsNotNone(audit_log_line, "audit_log function should exist")
        
        # Check that permission decorator exists before the function
        permission_found = False
        login_required_found = False
        for i in range(max(0, audit_log_line - 5), audit_log_line):
            if "@user_passes_test(lambda u: u.is_staff)" in lines[i]:
                permission_found = True
            if "@login_required" in lines[i]:
                login_required_found = True
        
        self.assertTrue(permission_found, "audit_log should have staff permission decorator")
        self.assertTrue(login_required_found, "audit_log should have login_required decorator")


class TestSprint16CodeQualityTemplate(unittest.TestCase):
    """Test Sprint 16 code quality in templates."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_proper_imports_in_models_template(self):
        """Test that models template has proper imports."""
        # Get the path to the admin_dashboard models template
        models_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "models.py"
        
        # Read the template content
        with open(models_template_path, 'r') as f:
            content = f.read()
        
        # Check for required imports
        self.assertIn("from django.db import models", content, "Should import models")
        self.assertIn("from django.contrib.auth import get_user_model", content, "Should import get_user_model")
        self.assertIn("from django.utils import timezone", content, "Should import timezone")
        
        # Check import organization (should be at the top)
        lines = content.split('\n')
        import_section_ended = False
        for line in lines:
            line = line.strip()
            # Skip empty lines, comments, docstrings, and variable assignments
            if (line and not line.startswith('#') and not line.startswith('from') and 
                not line.startswith('import') and not line.startswith('"""') and 
                not line.startswith("User = get_user_model()")):
                import_section_ended = True
            elif import_section_ended and (line.startswith('from') or line.startswith('import')):
                self.fail("Imports should be at the top of the file")
    
    def test_proper_imports_in_utils_template(self):
        """Test that utils template has proper imports."""
        # Get the path to the admin_dashboard utils template
        utils_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "utils.py"
        
        # Read the template content
        with open(utils_template_path, 'r') as f:
            content = f.read()
        
        # Check for required imports
        self.assertIn("from django.http import HttpRequest", content, "Should import HttpRequest")
        self.assertIn("from typing import Optional", content, "Should import Optional for type hints")
        self.assertIn("from .models import AuditLog", content, "Should import AuditLog")
    
    def test_proper_docstrings_in_functions(self):
        """Test that functions have proper docstrings."""
        # Get the path to the admin_dashboard utils template
        utils_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "utils.py"
        
        # Read the template content
        with open(utils_template_path, 'r') as f:
            content = f.read()
        
        # Check for function docstrings
        if "def log_admin_action(" in content:
            # Find the function and check for docstring
            lines = content.split('\n')
            function_start = None
            for i, line in enumerate(lines):
                if "def log_admin_action(" in line:
                    function_start = i
                    break
            
            if function_start:
                # Find the end of function signature (closing parenthesis and return type)
                function_end = function_start
                for i in range(function_start, min(function_start + 10, len(lines))):
                    if ') -> AuditLog:' in lines[i]:
                        function_end = i
                        break
                
                # Check next few lines after function signature for docstring
                docstring_found = False
                for i in range(function_end + 1, min(function_end + 5, len(lines))):
                    if '"""' in lines[i]:
                        docstring_found = True
                        break
                
                self.assertTrue(docstring_found, "log_admin_action should have docstring")
    
    def test_type_hints_usage(self):
        """Test that functions use proper type hints."""
        # Get the path to the admin_dashboard utils template
        utils_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "utils.py"
        
        # Read the template content
        with open(utils_template_path, 'r') as f:
            content = f.read()
        
        # Check for type hints in function signatures
        self.assertIn("action: str", content, "Should use type hints for string parameters")
        self.assertIn("description: str", content, "Should use type hints for string parameters")
        self.assertIn("Optional[HttpRequest]", content, "Should use type hints for optional parameters")
        self.assertIn("-> AuditLog", content, "Should use type hints for return values")


class TestSprint16IntegrationPointsTemplate(unittest.TestCase):
    """Test Sprint 16 integration points in templates."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_audit_logging_integration_with_existing_views(self):
        """Test that audit logging is properly integrated with existing admin views."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check that important admin actions are logged
        admin_actions_to_check = [
            ("user_search", "USER_SEARCH"),
            ("user_detail", "USER_VIEW"),
            ("service_toggle_status", "SERVICE_TOGGLE"),
            ("sync_products", "PRODUCT_SYNC")
        ]
        
        for function_name, expected_action in admin_actions_to_check:
            if f"def {function_name}(" in content:
                # Find the function and check for audit logging
                lines = content.split('\n')
                function_start = None
                for i, line in enumerate(lines):
                    if f"def {function_name}(" in line:
                        function_start = i
                        break
                
                if function_start:
                    # Look for log_admin_action call in the function (next 100 lines)
                    function_content = '\n'.join(lines[function_start:function_start + 100])
                    if "log_admin_action(" in function_content:
                        self.assertIn(f"'{expected_action}'", function_content, 
                                     f"{function_name} should log {expected_action} action")
    
    def test_user_model_relationship_in_audit_log(self):
        """Test that AuditLog model has proper relationship with User model."""
        # Get the path to the admin_dashboard models template
        models_template_path = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "admin_dashboard" / "models.py"
        
        # Read the template content
        with open(models_template_path, 'r') as f:
            content = f.read()
        
        # Check for proper user relationship
        self.assertIn("User = get_user_model()", content, "Should get User model dynamically")
        self.assertIn("models.ForeignKey(\n        User", content, "Should have ForeignKey to User")
        self.assertIn("on_delete=models.SET_NULL", content, "Should use SET_NULL on delete")
        self.assertIn("null=True, blank=True", content, "Should allow null user")
        self.assertIn("related_name='audit_logs'", content, "Should have proper related name")


if __name__ == '__main__':
    unittest.main() 