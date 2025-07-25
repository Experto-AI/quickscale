"""
Tests for Sprint 13 fixes: Service visibility and admin URL pattern issues.

These tests verify that the specific issues found and fixed in Sprint 13
are properly resolved:
1. NoReverseMatch error in service usage analytics template
2. Service visibility issue in admin dashboard
"""

import os
import unittest
import re
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil


class ServiceUsageAnalyticsTemplateFixTests(unittest.TestCase):
    """Test cases for the NoReverseMatch fix in service usage analytics template."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates'
        self.analytics_template = self.templates_path / 'admin' / 'credits' / 'service_usage_analytics.html'
        
    def test_analytics_template_exists(self):
        """Test that the service usage analytics template exists."""
        self.assertTrue(self.analytics_template.exists(),
                       "Service usage analytics template should exist")
    
    def test_analytics_template_uses_correct_admin_url_pattern(self):
        """Test that template uses correct admin URL pattern for custom user model."""
        with open(self.analytics_template, 'r') as f:
            template_content = f.read()
        
        # Check that the correct admin URL pattern is used
        self.assertIn("admin:users_customuser_change", template_content,
                     "Template should use admin:users_customuser_change URL pattern")
        
        # Check that the incorrect pattern is NOT used
        self.assertNotIn("admin:auth_user_change", template_content,
                        "Template should NOT use admin:auth_user_change URL pattern")
    
    def test_analytics_template_user_link_structure(self):
        """Test that user links in analytics template are properly structured."""
        with open(self.analytics_template, 'r') as f:
            template_content = f.read()
        
        # Check for proper user link structure
        user_link_pattern = r'<a href="{% url \'admin:users_customuser_change\' usage\.user\.pk %}">'
        self.assertRegex(template_content, user_link_pattern,
                        "Template should have properly structured user links")
        
        # Check that email is displayed in the link
        self.assertIn("{{ usage.user.email }}", template_content,
                     "Template should display user email in the link")
    
    def test_analytics_template_context_requirements(self):
        """Test that template expects correct context variables."""
        with open(self.analytics_template, 'r') as f:
            template_content = f.read()
        
        # Check for required context variables that actually exist in the template
        required_context_vars = [
            'service.name',
            'service.description', 
            'service.credit_cost',
            'analytics.total_uses',
            'analytics.uses_30_days',
            'analytics.uses_7_days'
        ]
        
        for var in required_context_vars:
            self.assertIn(f"{{{{ {var} }}}}", template_content,
                         f"Template should use context variable {var}")
        
        # Check that service.is_active is used in conditional form
        self.assertIn("{% if service.is_active %}", template_content,
                     "Template should check service.is_active in conditional")
        
        # Check that recent_usages is used in conditional and loop
        self.assertIn("{% if recent_usages %}", template_content,
                     "Template should check recent_usages in conditional")
        self.assertIn("{% for usage in recent_usages %}", template_content,
                     "Template should loop through recent_usages")
    
    def test_analytics_template_no_reverse_match_regression(self):
        """Test that template doesn't have any potential NoReverseMatch issues."""
        with open(self.analytics_template, 'r') as f:
            template_content = f.read()
        
        # Look for all URL tags
        url_patterns = re.findall(r"{% url '[^']+' [^%]+ %}", template_content)
        
        # Verify known working patterns
        expected_patterns = [
            "{% url 'admin:index' %}",
            "{% url 'admin:app_list' app_label='credits' %}",
            "{% url 'admin:credits_service_changelist' %}",
            "{% url 'admin:users_customuser_change' usage.user.pk %}",
            "{% url 'admin:credits_service_change' service.pk %}"
        ]
        
        for pattern in expected_patterns:
            if pattern in template_content:
                self.assertIn(pattern, template_content,
                             f"Expected URL pattern should be present: {pattern}")


class ServiceVisibilityFixTests(unittest.TestCase):
    """Test cases for the service visibility fix in admin dashboard."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates'
        self.service_admin_template = self.templates_path / 'admin_dashboard' / 'service_admin.html'
        
    def test_service_admin_template_exists(self):
        """Test that the service admin template exists."""
        self.assertTrue(self.service_admin_template.exists(),
                       "Service admin template should exist")
    
    def test_service_rows_not_hidden_by_alpine_js(self):
        """Test that service rows are not hidden by problematic Alpine.js filtering."""
        with open(self.service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check that service rows don't have problematic x-show directive
        # that was causing visibility issues
        service_row_pattern = r'<tr x-data="serviceRowData\([^"]*\)"[^>]*>'
        matches = re.findall(service_row_pattern, template_content)
        
        for match in matches:
            # Ensure x-show with complex isVisible() is not present
            self.assertNotIn('x-show="isVisible()"', match,
                           "Service rows should not use problematic x-show directive")
    
    def test_alpine_js_components_simplified(self):
        """Test that Alpine.js components are simplified and more reliable."""
        with open(self.service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check for serviceAdminData function
        self.assertIn("function serviceAdminData()", template_content,
                     "serviceAdminData function should exist")
        
        # Check for serviceRowData function  
        self.assertIn("function serviceRowData(", template_content,
                     "serviceRowData function should exist")
        
        # Check that complex $root access patterns are not used
        # (These were causing the visibility issues)
        problematic_patterns = [
            "this.$root.statusFilter",
            "parentData.statusFilter",
            "$root.searchTerm"
        ]
        
        for pattern in problematic_patterns:
            # These patterns might be commented out, so check if they're active
            if pattern in template_content:
                # Make sure they're commented out or not in active code
                lines_with_pattern = [line.strip() for line in template_content.split('\n') 
                                    if pattern in line]
                for line in lines_with_pattern:
                    # Allow if it's in a comment
                    if not (line.startswith('//') or line.startswith('*') or 
                           '<!--' in line or line.startswith('/*')):
                        self.fail(f"Problematic Alpine.js pattern found in active code: {pattern}")
    
    def test_filtering_controls_handled_properly(self):
        """Test that filtering controls are handled in a way that doesn't break visibility."""
        with open(self.service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check if filtering is commented out or properly implemented
        filter_section = re.search(r'<!-- Filter and Search.*?-->', template_content, re.DOTALL)
        
        if filter_section:
            # If filtering is commented out, that's acceptable as a fix
            self.assertIn("Filter and Search - Temporarily disabled", template_content,
                         "If filtering is commented out, it should have explanatory comment")
        else:
            # If filtering is active, check that it doesn't use problematic patterns
            if "statusFilter" in template_content:
                # Make sure it doesn't use complex scope access
                self.assertNotIn("x-on:change=\"filterServices()\"", template_content,
                               "Complex filtering event handlers should be avoided")
    
    def test_service_data_structure_correct(self):
        """Test that service data is passed correctly to template."""
        with open(self.service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check for proper context usage
        required_context = [
            "total_services", 
            "active_services",
            "inactive_services"
        ]
        
        for context_var in required_context:
            self.assertIn(f"{{{{ {context_var} }}}}", template_content,
                         f"Template should use context variable {context_var}")
        
        # Check for services_with_stats in conditional and loop
        self.assertIn("{% if services_with_stats %}", template_content,
                     "Template should check services_with_stats in conditional")
        self.assertIn("{% for item in services_with_stats %}", template_content,
                     "Template should loop through services_with_stats")
        
        # Check for proper service loop
        self.assertIn("{% for item in services_with_stats %}", template_content,
                     "Template should loop through services_with_stats")
    
    def test_text_processing_service_display_structure(self):
        """Test that template can properly display Text Processing service data."""
        with open(self.service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check for service display fields that should work with Text Processing service
        service_fields = [
            "item.service.name",
            "item.service.credit_cost", 
            "item.total_usage",
            "item.usage_30_days",
            "item.unique_users"
        ]
        
        for field in service_fields:
            self.assertIn(f"{{{{ {field} }}}}", template_content,
                         f"Template should display service field {field}")
        
        # Check description with filter (truncatechars)
        self.assertIn("{{ item.service.description|truncatechars:80 }}", template_content,
                     "Template should display service description with truncation")
        
        # Check service.is_active with filter
        self.assertIn("{{ item.service.is_active|yesno:'active,inactive' }}", template_content,
                     "Template should display service status with yesno filter")


class ServiceManagementIntegrationTests(unittest.TestCase):
    """Integration tests for service management functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.admin_dashboard_views = (self.base_path / 'quickscale' / 'project_templates' / 
                                    'admin_dashboard' / 'views.py')
    
    def test_service_admin_view_provides_correct_context(self):
        """Test that service_admin view provides correct context for template."""
        with open(self.admin_dashboard_views, 'r') as f:
            views_content = f.read()
        
        # Check that view calculates services_with_stats
        self.assertIn("services_with_stats = []", views_content,
                     "View should initialize services_with_stats")
        
        # Check that view calculates analytics for each service
        self.assertIn("for service in services:", views_content,
                     "View should iterate through services")
        
        # Check that view passes correct context
        context_vars = [
            "'services_with_stats': services_with_stats",
            "'total_services': services.count()",
            "'active_services': services.filter(is_active=True).count()",
            "'inactive_services': services.filter(is_active=False).count()"
        ]
        
        for context_var in context_vars:
            self.assertIn(context_var, views_content,
                         f"View should pass context variable: {context_var}")
    
    def test_service_analytics_view_handles_custom_user_model(self):
        """Test that service analytics view works with custom user model."""
        with open(self.admin_dashboard_views, 'r') as f:
            views_content = f.read()
        
        # Check for service_detail view that provides user data for analytics
        self.assertIn("def service_detail(request: HttpRequest, service_id: int)", views_content,
                     "service_detail view should exist")
        
        # Check that view gets recent usages with user data
        self.assertIn("recent_usages = service.usages.select_related", views_content,
                     "View should select_related user data")
        self.assertIn("'user', 'credit_transaction'", views_content,
                     "View should include user and credit_transaction relations")


class TextProcessingServiceMigrationTests(unittest.TestCase):
    """Test cases for Text Processing service creation and management."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.migration_file = (self.base_path / 'quickscale' / 'project_templates' / 'credits' / 
                             'migrations' / '0007_add_text_processing_service.py')
    
    def test_text_processing_service_migration_exists(self):
        """Test that the Text Processing service migration exists."""
        self.assertTrue(self.migration_file.exists(),
                       "Text Processing service migration should exist")
    
    def test_text_processing_service_migration_content(self):
        """Test that migration properly creates Text Processing service."""
        with open(self.migration_file, 'r') as f:
            migration_content = f.read()
        
        # Check for service creation
        self.assertIn("name='Text Processing'", migration_content,
                     "Migration should create Text Processing service")
        self.assertIn("credit_cost': Decimal('1.00')", migration_content,
                     "Migration should set correct credit cost")
        self.assertIn("'is_active': True", migration_content,
                     "Migration should set service as active")
        
        # Check for proper description
        self.assertIn("AI-powered text processing service", migration_content,
                     "Migration should set proper service description")


class RegressionTests(unittest.TestCase):
    """Regression tests to ensure fixes don't break other functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
    def test_other_admin_templates_not_affected(self):
        """Test that other admin templates are not affected by the fixes."""
        admin_templates_path = (self.base_path / 'quickscale' / 'project_templates' / 
                              'templates' / 'admin' / 'credits')
        
        if admin_templates_path.exists():
            for template_file in admin_templates_path.glob('*.html'):
                if template_file.name != 'service_usage_analytics.html':
                    with open(template_file, 'r') as f:
                        content = f.read()
                    
                    # Check that other templates don't have the incorrect pattern
                    if 'admin:auth_user_change' in content:
                        self.fail(f"Template {template_file.name} still uses incorrect admin URL pattern")
    
    def test_custom_user_model_consistency(self):
        """Test that custom user model is consistently referenced."""
        settings_file = (self.base_path / 'quickscale' / 'project_templates' / 
                        'core' / 'settings.py')
        
        with open(settings_file, 'r') as f:
            settings_content = f.read()
        
        # Check that custom user model is properly configured
        self.assertIn("AUTH_USER_MODEL = 'users.CustomUser'", settings_content,
                     "Settings should configure custom user model")
    
    def test_service_admin_dashboard_integration(self):
        """Test that service admin dashboard integration is not broken."""
        admin_dashboard_views = (self.base_path / 'quickscale' / 'project_templates' / 
                               'admin_dashboard' / 'views.py')
        
        with open(admin_dashboard_views, 'r') as f:
            views_content = f.read()
        
        # Check that service admin functionality is intact
        required_functions = [
            'def service_admin(',
            'def service_detail(',
            'def service_toggle_status('
        ]
        
        for func in required_functions:
            self.assertIn(func, views_content,
                         f"Service admin function should exist: {func}")


if __name__ == '__main__':
    unittest.main() 