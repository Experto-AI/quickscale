"""
Enhanced tests for Sprint 13: Service Management Admin Interface - Edge Cases and Advanced Features.

These tests verify additional functionality and edge cases for the Service Management
Admin Interface that extend beyond the basic implementation tests.
"""

import os
import unittest
import re
from pathlib import Path


class ServiceAdminSecurityTests(unittest.TestCase):
    """Test cases for service admin security and validation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.admin_dashboard_path = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard'
        self.admin_dashboard_views = self.admin_dashboard_path / 'views.py'
        
    def test_service_toggle_csrf_protection(self):
        """Test that service toggle view has proper CSRF protection."""
        with open(self.admin_dashboard_views, 'r') as f:
            views_content = f.read()
        
        # Check for CSRF token validation in HTMX integration
        templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates' / 'admin_dashboard'
        service_admin_template = templates_path / 'service_admin.html'
        
        with open(service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check for CSRF token in HTMX headers
        self.assertIn("X-CSRFToken", template_content,
                     "CSRF token not found in HTMX headers")
        self.assertIn("{{ csrf_token }}", template_content,
                     "CSRF token template variable not found")
    
    def test_service_views_staff_only_access(self):
        """Test that service management views require staff access."""
        with open(self.admin_dashboard_views, 'r') as f:
            views_content = f.read()
        
        # Check for staff requirement decorators
        service_view_functions = [
            'service_admin', 'service_detail', 'service_toggle_status'
        ]
        
        for view_func in service_view_functions:
            # Each view should have both login_required and staff check
            view_pattern = rf'@user_passes_test\(lambda u: u\.is_staff\)[\s\S]*?def {view_func}'
            self.assertRegex(views_content, view_pattern,
                           f"Staff requirement not found for {view_func} view")
    
    def test_service_toggle_method_validation(self):
        """Test that service toggle view validates HTTP method."""
        with open(self.admin_dashboard_views, 'r') as f:
            views_content = f.read()
        
        # Check for POST method validation
        self.assertIn("if request.method != 'POST':", views_content,
                     "Service toggle POST method validation not found")
        self.assertIn("return JsonResponse({'error': 'Method not allowed'}, status=405)", views_content,
                     "Service toggle method validation error response not found")


class ServiceAdminErrorHandlingTests(unittest.TestCase):
    """Test cases for service admin error handling and edge cases."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.admin_dashboard_path = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard'
        self.admin_dashboard_views = self.admin_dashboard_path / 'views.py'
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.admin_py = self.credits_app_path / 'admin.py'
        
    def test_service_toggle_error_handling(self):
        """Test that service toggle view has proper error handling."""
        with open(self.admin_dashboard_views, 'r') as f:
            views_content = f.read()
        
        # Check for try-catch block in service toggle
        self.assertIn("try:", views_content,
                     "Service toggle error handling try block not found")
        self.assertIn("except Exception as e:", views_content,
                     "Service toggle exception handling not found")
        self.assertIn("return JsonResponse({", views_content,
                     "Service toggle error response not found")
    
    def test_service_analytics_view_error_handling(self):
        """Test that service analytics view has proper error handling."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for get_object_or_404 usage in analytics view
        self.assertIn("get_object_or_404(Service, pk=service_id)", admin_content,
                     "Service analytics view 404 handling not found")
    
    def test_service_admin_empty_state_handling(self):
        """Test that service admin handles empty state properly."""
        templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates' / 'admin_dashboard'
        service_admin_template = templates_path / 'service_admin.html'
        
        with open(service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check for empty state message
        self.assertIn("{% if services_with_stats %}", template_content,
                     "Service admin empty state condition not found")
        self.assertIn("No services found!", template_content,
                     "Service admin empty state message not found")
        self.assertIn("/admin/credits/service/", template_content,
                     "Service admin empty state Django admin link not found")


class ServiceAdminUIConsistencyTests(unittest.TestCase):
    """Test cases for service admin UI consistency and user experience."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates' / 'admin_dashboard'
        
    def test_service_admin_bulma_css_consistency(self):
        """Test that service admin templates use consistent Bulma CSS classes."""
        service_admin_template = self.templates_path / 'service_admin.html'
        
        with open(service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check for consistent Bulma button classes
        bulma_button_classes = ['button is-info', 'button is-success', 'button is-warning']
        for button_class in bulma_button_classes:
            self.assertIn(button_class, template_content,
                         f"Bulma button class {button_class} not found")
        
        # Check for consistent card structure
        self.assertIn("class=\"card\"", template_content,
                     "Bulma card class not found")
        self.assertIn("card-content", template_content,
                     "Bulma card-content class not found")
    
    def test_service_detail_template_navigation_consistency(self):
        """Test that service detail template has consistent navigation."""
        service_detail_template = self.templates_path / 'service_detail.html'
        
        with open(service_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for back navigation
        self.assertIn("{% url 'admin_dashboard:service_admin' %}", template_content,
                     "Service detail back navigation not found")
        self.assertIn("Back to Services", template_content,
                     "Service detail back button text not found")
        
        # Check for edit navigation
        self.assertIn("/admin/credits/service/", template_content,
                     "Service detail Django admin edit link not found")
        self.assertIn("Edit in Admin", template_content,
                     "Service detail edit button text not found")
    
    def test_service_templates_responsive_design(self):
        """Test that service templates use responsive Bulma classes."""
        templates = ['service_admin.html', 'service_detail.html']
        
        for template_name in templates:
            template_path = self.templates_path / template_name
            
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # Check for responsive column classes
            responsive_classes = ['columns', 'column', 'is-multiline']
            for responsive_class in responsive_classes:
                self.assertIn(responsive_class, template_content,
                             f"Responsive class {responsive_class} not found in {template_name}")


class ServiceAdminAlpineJSFunctionalityTests(unittest.TestCase):
    """Test cases for Alpine.js functionality in service admin."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates' / 'admin_dashboard'
        
   
    def test_service_row_alpine_functionality(self):
        """Test that service row has proper Alpine.js functionality."""
        service_admin_template = self.templates_path / 'service_admin.html'
        
        with open(service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check for service row Alpine.js functions
        row_functions = [
            'getStatusClass()', 'getStatusText()', 'getToggleButtonClass()',
            'getToggleIconClass()', 'getToggleText()', 'toggleServiceStatus()',
            'handleToggleResponse($event)'
        ]
        for func in row_functions:
            self.assertIn(func, template_content,
                         f"Service row Alpine.js function {func} not found")
    
    def test_service_detail_alpine_functionality(self):
        """Test that service detail has proper Alpine.js functionality."""
        service_detail_template = self.templates_path / 'service_detail.html'
        
        with open(service_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for service detail Alpine.js functions
        detail_functions = [
            'getServiceStatusTagClass()', 'getServiceStatusText()',
            'showNotification(', 'hideNotification()'
        ]
        for func in detail_functions:
            self.assertIn(func, template_content,
                         f"Service detail Alpine.js function {func} not found")


class ServiceAdminHTMXIntegrationTests(unittest.TestCase):
    """Test cases for HTMX integration in service admin."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.templates_path = self.base_path / 'quickscale' / 'project_templates' / 'templates' / 'admin_dashboard'
        
    def test_service_admin_htmx_configuration(self):
        """Test that service admin has proper HTMX configuration."""
        service_admin_template = self.templates_path / 'service_admin.html'
        
        with open(service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check for HTMX attributes
        htmx_attributes = [
            'hx-post', 'hx-headers', 'hx-swap', 'x-on:htmx:after-request'
        ]
        for attr in htmx_attributes:
            self.assertIn(attr, template_content,
                         f"HTMX attribute {attr} not found")
        
        # Check for proper HTMX endpoint
        self.assertIn("{% url 'admin_dashboard:service_toggle_status'", template_content,
                     "HTMX service toggle URL not found")
    
    def test_service_detail_htmx_configuration(self):
        """Test that service detail has proper HTMX configuration."""
        service_detail_template = self.templates_path / 'service_detail.html'
        
        with open(service_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for HTMX toggle functionality
        self.assertIn("hx-post=\"{% url 'admin_dashboard:service_toggle_status'", template_content,
                     "Service detail HTMX toggle not found")
        self.assertIn("hx-swap=\"none\"", template_content,
                     "Service detail HTMX swap configuration not found")


class ServiceAnalyticsDataIntegrityTests(unittest.TestCase):
    """Test cases for service analytics data integrity and calculations."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.admin_py = self.credits_app_path / 'admin.py'
        self.admin_dashboard_path = self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard'
        self.admin_dashboard_views = self.admin_dashboard_path / 'views.py'
        
    def test_service_analytics_time_range_consistency(self):
        """Test that analytics time ranges are consistent across admin and dashboard."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        with open(self.admin_dashboard_views, 'r') as f:
            views_content = f.read()
        
        # Check for consistent time range calculations
        time_ranges = ['timedelta(days=30)', 'timedelta(days=7)']
        for time_range in time_ranges:
            self.assertIn(time_range, admin_content,
                         f"Time range {time_range} not found in admin")
            self.assertIn(time_range, views_content,
                         f"Time range {time_range} not found in views")
    
    def test_service_analytics_credit_calculation_consistency(self):
        """Test that credit calculations are consistent and handle edge cases."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for absolute value usage (credits stored as negative)
        self.assertIn("abs(", admin_content,
                     "Absolute value calculation not found for credits")
        
        # Check for null/empty handling
        self.assertIn("or 0", admin_content,
                     "Null/empty credit handling not found")
    
    def test_service_analytics_aggregation_safety(self):
        """Test that analytics aggregations handle edge cases safely."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for safe aggregation handling
        aggregation_patterns = [
            r"aggregate\(.*?\)\[.*?\]\s+or\s+0",
            r"Sum\('credit_transaction__amount'\)"
        ]
        
        for pattern in aggregation_patterns:
            # Use re.compile with DOTALL flag for multiline pattern matching
            compiled_pattern = re.compile(pattern, re.DOTALL)
            self.assertRegex(admin_content, compiled_pattern,
                           f"Safe aggregation pattern {pattern} not found")


class ServiceAdminMigrationAndModelTests(unittest.TestCase):
    """Test cases for service admin migration and model consistency."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        
    def test_service_model_admin_field_consistency(self):
        """Test that admin configuration matches model fields."""
        models_py = self.credits_app_path / 'models.py'
        admin_py = self.credits_app_path / 'admin.py'
        
        with open(models_py, 'r') as f:
            models_content = f.read()
        
        with open(admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check that admin references match model fields
        service_fields = ['name', 'description', 'credit_cost', 'is_active', 'created_at', 'updated_at']
        for field in service_fields:
            self.assertIn(f"{field} = models.", models_content,
                         f"Service model field {field} not found")
            # Admin should reference these fields (directly or in methods)
            field_referenced = (field in admin_content or 
                              f"obj.{field}" in admin_content or
                              f"'{field}'" in admin_content)
            self.assertTrue(field_referenced,
                           f"Service admin does not reference field {field}")
    
    def test_service_usage_model_admin_relationship_consistency(self):
        """Test that ServiceUsage admin properly handles relationships."""
        models_py = self.credits_app_path / 'models.py'
        admin_py = self.credits_app_path / 'admin.py'
        
        with open(models_py, 'r') as f:
            models_content = f.read()
        
        with open(admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for relationship fields in model
        relationships = ['user', 'service', 'credit_transaction']
        for rel in relationships:
            self.assertIn(f"{rel} = models.ForeignKey", models_content,
                         f"ServiceUsage relationship {rel} not found in model")
            # Admin should reference these relationships
            self.assertIn(f"obj.{rel}", admin_content,
                         f"ServiceUsage admin does not reference relationship {rel}")


if __name__ == '__main__':
    unittest.main() 