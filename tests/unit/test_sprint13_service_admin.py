"""
Tests for Sprint 13: Service Management Admin Interface.

These tests verify that the Service Management Admin Interface features
are properly implemented in the QuickScale project generator templates.
This includes enhanced Django admin, admin dashboard pages, HTMX functionality,
Alpine.js integration, and service analytics.
"""

import os
import unittest
import re
from pathlib import Path


class ServiceAdminEnhancementsTests(unittest.TestCase):
    """Test cases for enhanced Service admin configuration."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'templates' / 'credits'
        self.admin_py = self.credits_app_path / 'admin.py'
        
    def test_service_admin_enhanced_list_display(self):
        """Test that Service admin has enhanced list display with analytics."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for enhanced list display with analytics fields
        expected_fields = [
            'name', 'credit_cost', 'is_active', 'usage_count', 
            'total_credits_consumed', 'unique_users_count', 'service_actions'
        ]
        
        for field in expected_fields:
            self.assertIn(field, admin_content,
                         f"Service admin list_display missing {field}")
        
        # Check for comprehensive analytics methods
        self.assertIn("def usage_count(self, obj):", admin_content,
                     "Service usage_count method not found")
        self.assertIn("def total_credits_consumed(self, obj):", admin_content,
                     "Service total_credits_consumed method not found")
        self.assertIn("def unique_users_count(self, obj):", admin_content,
                     "Service unique_users_count method not found")
    
    def test_service_admin_analytics_methods(self):
        """Test that Service admin has proper analytics calculation methods."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check usage_count method implementation
        self.assertIn("obj.usages.count()", admin_content,
                     "Service usage count calculation not found")
        
        # Check total_credits_consumed method implementation  
        self.assertIn("obj.usages.aggregate", admin_content,
                     "Service aggregate credit calculation not found")
        self.assertIn("Sum('credit_transaction__amount')", admin_content,
                     "Service credit sum calculation not found")
        
        # Check unique_users_count method implementation
        self.assertIn("obj.usages.values('user').distinct().count()", admin_content,
                     "Service unique users calculation not found")
    
    def test_service_admin_bulk_operations(self):
        """Test that Service admin has bulk enable/disable operations."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for bulk actions in admin configuration
        self.assertIn("actions = ['bulk_enable_services', 'bulk_disable_services'", admin_content,
                     "Service admin bulk actions not found")
        
        # Check for bulk enable method
        self.assertIn("def bulk_enable_services(self, request, queryset):", admin_content,
                     "Service bulk_enable_services method not found")
        self.assertIn("queryset.update(is_active=True)", admin_content,
                     "Service bulk enable implementation not found")
        
        # Check for bulk disable method
        self.assertIn("def bulk_disable_services(self, request, queryset):", admin_content,
                     "Service bulk_disable_services method not found")
        self.assertIn("queryset.update(is_active=False)", admin_content,
                     "Service bulk disable implementation not found")
    
    def test_service_admin_custom_analytics_view(self):
        """Test that Service admin has custom analytics view functionality."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for custom URL patterns
        self.assertIn("def get_urls(self):", admin_content,
                     "Service admin get_urls method not found")
        self.assertIn("service_usage_analytics_view", admin_content,
                     "Service analytics view reference not found")
        
        # Check for analytics view implementation
        self.assertIn("def service_usage_analytics_view(self, request, service_id):", admin_content,
                     "Service analytics view method not found")
        
        # Check for analytics data calculation
        self.assertIn("last_30_days = now - timedelta(days=30)", admin_content,
                     "Service analytics time range calculation not found")
        self.assertIn("last_7_days = now - timedelta(days=7)", admin_content,
                     "Service analytics 7-day calculation not found")


class ServiceUsageAdminEnhancementsTests(unittest.TestCase):
    """Test cases for enhanced ServiceUsage admin configuration."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'templates' / 'credits'
        self.admin_py = self.credits_app_path / 'admin.py'
        
    def test_service_usage_admin_enhanced_display(self):
        """Test that ServiceUsage admin has enhanced display with analytics."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for ServiceUsage admin registration
        self.assertIn("@admin.register(ServiceUsage)", admin_content,
                     "ServiceUsage admin registration not found")
        
        # Check for enhanced list display
        expected_fields = ['user', 'service', 'get_credit_cost', 'get_service_status', 'created_at']
        for field in expected_fields:
            self.assertIn(field, admin_content,
                         f"ServiceUsage admin list_display missing {field}")
    
    def test_service_usage_admin_helper_methods(self):
        """Test that ServiceUsage admin has proper helper methods."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for credit cost display method
        self.assertIn("def get_credit_cost(self, obj):", admin_content,
                     "ServiceUsage get_credit_cost method not found")
        self.assertIn("abs(obj.credit_transaction.amount)", admin_content,
                     "ServiceUsage credit cost calculation not found")
        
        # Check for service status display method
        self.assertIn("def get_service_status(self, obj):", admin_content,
                     "ServiceUsage get_service_status method not found")
        self.assertIn("obj.service.is_active", admin_content,
                     "ServiceUsage service status check not found")


class AdminDashboardServiceManagementTests(unittest.TestCase):
    """Test cases for admin dashboard service management pages."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.templates_path = self.base_path / 'quickscale' / 'templates'
        self.admin_dashboard_path = self.templates_path / 'admin_dashboard'
        self.admin_dashboard_views = self.admin_dashboard_path / 'views.py'
        self.admin_dashboard_urls = self.admin_dashboard_path / 'urls.py'
        
    def test_service_admin_view_exists(self):
        """Test that service_admin view is properly implemented."""
        with open(self.admin_dashboard_views, 'r') as f:
            views_content = f.read()
        
        # Check for service_admin view function
        self.assertIn("def service_admin(request: HttpRequest) -> HttpResponse:", views_content,
                     "service_admin view function not found")
        
        # Check for proper decorators
        self.assertIn("@login_required", views_content,
                     "service_admin login_required decorator not found")
        self.assertIn("@user_passes_test(lambda u: u.is_staff)", views_content,
                     "service_admin staff check not found")
        
        # Check for analytics calculation
        self.assertIn("services_with_stats = []", views_content,
                     "Service analytics data structure not found")
        self.assertIn("service.usages.count()", views_content,
                     "Service usage count calculation not found")
        self.assertIn("Sum('credit_transaction__amount')", views_content,
                     "Service credit consumption calculation not found")
    
    def test_service_detail_view_exists(self):
        """Test that service_detail view is properly implemented."""
        with open(self.admin_dashboard_views, 'r') as f:
            views_content = f.read()
        
        # Check for service_detail view function
        self.assertIn("def service_detail(request: HttpRequest, service_id: int) -> HttpResponse:", views_content,
                     "service_detail view function not found")
        
        # Check for proper service lookup
        self.assertIn("get_object_or_404(Service, id=service_id)", views_content,
                     "Service detail lookup not found")
    
    def test_service_toggle_status_view_exists(self):
        """Test that service_toggle_status HTMX view is properly implemented."""
        with open(self.admin_dashboard_views, 'r') as f:
            views_content = f.read()
        
        # Check for service toggle view function
        self.assertIn("def service_toggle_status(request: HttpRequest, service_id: int) -> JsonResponse:", views_content,
                     "service_toggle_status view function not found")
        
        # Check for POST method validation
        self.assertIn("if request.method != 'POST':", views_content,
                     "Service toggle POST validation not found")
        
        # Check for service toggle logic
        self.assertIn("service.is_active = not service.is_active", views_content,
                     "Service toggle logic not found")
        self.assertIn("service.save()", views_content,
                     "Service save operation not found")
        
        # Check for JSON response format
        self.assertIn("JsonResponse", views_content,
                     "JsonResponse import/usage not found")
        self.assertIn("'success': True", views_content,
                     "Service toggle success response not found")
    
    def test_service_management_urls_exist(self):
        """Test that service management URLs are properly configured."""
        with open(self.admin_dashboard_urls, 'r') as f:
            urls_content = f.read()
        
        # Check for service management URL patterns
        expected_urls = [
            "path('services/', views.service_admin, name='service_admin')",
            "path('services/<int:service_id>/', views.service_detail, name='service_detail')",
            "path('services/<int:service_id>/toggle/', views.service_toggle_status, name='service_toggle_status')"
        ]
        
        for url_pattern in expected_urls:
            self.assertIn(url_pattern, urls_content,
                         f"Service management URL pattern not found: {url_pattern}")


class ServiceAdminTemplateTests(unittest.TestCase):
    """Test cases for service admin templates with HTMX and Alpine.js integration."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.templates_path = self.base_path / 'quickscale' / 'templates' / 'templates' / 'admin_dashboard'
        self.service_admin_template = self.templates_path / 'service_admin.html'
        self.service_detail_template = self.templates_path / 'service_detail.html'
        
    def test_service_admin_template_structure(self):
        """Test that service admin template has proper structure and components."""
        with open(self.service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check template inheritance
        self.assertIn("{% extends \"base.html\" %}", template_content,
                     "Service admin template does not extend base.html")
        
        # Check for page title and structure
        self.assertIn("Service Management - Admin Dashboard", template_content,
                     "Service admin template title not found")
        
        # Check for service overview cards
        self.assertIn("{{ total_services }}", template_content,
                     "Total services display not found")
        self.assertIn("{{ active_services }}", template_content,
                     "Active services display not found")
        self.assertIn("{{ inactive_services }}", template_content,
                     "Inactive services display not found")
        
        # Check for services table
        self.assertIn("{% for item in services_with_stats %}", template_content,
                     "Services with stats loop not found")
        self.assertIn("{{ item.service.name }}", template_content,
                     "Service name display not found")
        self.assertIn("{{ item.service.credit_cost }}", template_content,
                     "Service credit cost display not found")
    
    def test_service_admin_template_alpine_js_integration(self):
        """Test that service admin template has proper Alpine.js integration."""
        with open(self.service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check for Alpine.js data binding
        self.assertIn("x-data=\"serviceAdminData()\"", template_content,
                     "Service admin Alpine.js data binding not found")
        
        # Check for filtering functionality
        self.assertIn("x-model=\"statusFilter\"", template_content,
                     "Status filter Alpine.js binding not found")
        self.assertIn("x-model=\"searchTerm\"", template_content,
                     "Search term Alpine.js binding not found")
        
        # Check for service row data binding
        self.assertIn("x-data=\"serviceRowData(", template_content,
                     "Service row Alpine.js data binding not found")
        
        # Check for Alpine.js functions
        self.assertIn("function serviceAdminData()", template_content,
                     "serviceAdminData Alpine.js function not found")
        self.assertIn("function serviceRowData(", template_content,
                     "serviceRowData Alpine.js function not found")
    
    def test_service_admin_template_htmx_integration(self):
        """Test that service admin template has proper HTMX integration."""
        with open(self.service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check for HTMX toggle functionality
        self.assertIn("hx-post=\"{% url 'admin_dashboard:service_toggle_status'", template_content,
                     "HTMX service toggle POST not found")
        self.assertIn("hx-headers='{\"X-CSRFToken\": \"{{ csrf_token }}\"}'", template_content,
                     "HTMX CSRF token header not found")
        self.assertIn("hx-swap=\"none\"", template_content,
                     "HTMX swap configuration not found")
        
        # Check for HTMX response handling
        self.assertIn("x-on:htmx:after-request=\"handleToggleResponse($event)\"", template_content,
                     "HTMX response handler not found")
    
    def test_service_detail_template_structure(self):
        """Test that service detail template has proper structure."""
        with open(self.service_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check template inheritance
        self.assertIn("{% extends \"base.html\" %}", template_content,
                     "Service detail template does not extend base.html")
        
        # Check for service information display
        self.assertIn("{{ service.name }}", template_content,
                     "Service name display not found")
        self.assertIn("{{ service.description }}", template_content,
                     "Service description display not found")
        self.assertIn("{{ service.credit_cost }}", template_content,
                     "Service credit cost display not found")
        
        # Check for analytics display
        self.assertIn("{{ analytics.total_usage }}", template_content,
                     "Service total usage analytics not found")
        self.assertIn("{{ analytics.unique_users }}", template_content,
                     "Service unique users analytics not found")
    
    def test_service_detail_template_alpine_js_integration(self):
        """Test that service detail template has proper Alpine.js integration."""
        with open(self.service_detail_template, 'r') as f:
            template_content = f.read()
        
        # Check for Alpine.js data binding
        self.assertIn("x-data=\"serviceDetailData(", template_content,
                     "Service detail Alpine.js data binding not found")
        
        # Check for service status management
        self.assertIn("getServiceStatusTagClass()", template_content,
                     "Service status tag class function not found")
        self.assertIn("getToggleButtonClass()", template_content,
                     "Toggle button class function not found")
        
        # Check for Alpine.js function definition
        self.assertIn("function serviceDetailData(", template_content,
                     "serviceDetailData Alpine.js function not found")
    
    def test_service_admin_template_visibility_fix(self):
        """Test that service rows are not hidden by problematic Alpine.js filtering."""
        with open(self.service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check that service rows don't have problematic x-show directive
        # that was causing visibility issues
        service_row_pattern = r'<tr x-data="serviceRowData\([^"]*\)"[^>]*>'
        matches = re.findall(service_row_pattern, template_content)
        
        self.assertGreater(len(matches), 0, "Should find service row patterns")
        
        for match in matches:
            # Ensure x-show with complex isVisible() is not present
            self.assertNotIn('x-show="isVisible()"', match,
                           "Service rows should not use problematic x-show directive")
    
    def test_service_admin_template_alpine_js_simplified(self):
        """Test that Alpine.js components are simplified and don't use problematic patterns."""
        with open(self.service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check that complex $root access patterns are not used in active code
        # (These were causing the visibility issues)
        problematic_patterns = [
            "this.$root.statusFilter",
            "this.$root.searchTerm",
            "$root.statusFilter",
            "$root.searchTerm"
        ]
        
        for pattern in problematic_patterns:
            if pattern in template_content:
                # Make sure they're commented out or not in active code
                lines_with_pattern = [line.strip() for line in template_content.split('\n') 
                                    if pattern in line]
                for line in lines_with_pattern:
                    # Allow if it's in a comment
                    if not (line.startswith('//') or line.startswith('*') or 
                           '<!--' in line or line.startswith('/*') or 
                           line.strip().startswith('//')):
                        self.fail(f"Problematic Alpine.js pattern found in active code: {pattern} in line: {line}")
    
    def test_service_admin_template_filtering_controls_safe(self):
        """Test that filtering controls don't break service visibility."""
        with open(self.service_admin_template, 'r') as f:
            template_content = f.read()
        
        # Check if filtering is commented out (acceptable fix)
        if "Filter and Search - Temporarily disabled" in template_content:
            # If filtering is disabled, ensure it's properly commented
            self.assertIn("<!--", template_content,
                         "Disabled filtering should be properly commented")
        else:
            # If filtering is active, ensure it doesn't use problematic event handlers
            self.assertNotIn('x-on:change="filterServices()"', template_content,
                           "Complex filtering event handlers should not be present")
            self.assertNotIn('x-on:input="filterServices()"', template_content,
                           "Complex search input handlers should not be present")


class ServiceAnalyticsTemplateTests(unittest.TestCase):
    """Test cases for service analytics template in Django admin."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.templates_path = self.base_path / 'quickscale' / 'templates' / 'templates' / 'admin' / 'credits'
        self.analytics_template = self.templates_path / 'service_usage_analytics.html'
        
    def test_service_analytics_template_exists(self):
        """Test that service analytics template exists and has proper structure."""
        self.assertTrue(self.analytics_template.exists(),
                       "Service usage analytics template not found")
        
        with open(self.analytics_template, 'r') as f:
            template_content = f.read()
        
        # Check template inheritance
        self.assertIn("{% extends \"admin/base_site.html\" %}", template_content,
                     "Analytics template does not extend admin base")
        
        # Check for breadcrumbs
        self.assertIn("{% block breadcrumbs %}", template_content,
                     "Analytics template breadcrumbs not found")
        
        # Check for service information display
        self.assertIn("{{ service.name }}", template_content,
                     "Service name not displayed in analytics")
        self.assertIn("{{ service.description }}", template_content,
                     "Service description not displayed in analytics")
        self.assertIn("{{ service.credit_cost }}", template_content,
                     "Service credit cost not displayed in analytics")
    
    def test_service_analytics_template_analytics_display(self):
        """Test that analytics template displays comprehensive analytics data."""
        with open(self.analytics_template, 'r') as f:
            template_content = f.read()
        
        # Check for analytics data display
        analytics_fields = [
            'analytics.total_uses',
            'analytics.uses_30_days',
            'analytics.uses_7_days',
            'analytics.unique_users',
            'analytics.total_credits',
            'analytics.credits_30_days'
        ]
        
        for field in analytics_fields:
            self.assertIn(f"{{{{ {field} }}}}", template_content,
                         f"Analytics field {field} not displayed")
        
        # Check for recent usage table
        self.assertIn("{% for usage in recent_usages %}", template_content,
                     "Recent usage loop not found")
        
        # Check for usage data display
        self.assertIn("{{ usage.user.email }}", template_content,
                     "Usage user email not displayed")
        self.assertIn("{{ usage.created_at|date:", template_content,
                     "Usage timestamp not displayed")
    
    def test_service_analytics_template_correct_admin_url_pattern(self):
        """Test that analytics template uses correct admin URL pattern for custom user model."""
        with open(self.analytics_template, 'r') as f:
            template_content = f.read()
        
        # Check that the correct admin URL pattern is used (fix for NoReverseMatch error)
        self.assertIn("admin:users_customuser_change", template_content,
                     "Template should use admin:users_customuser_change URL pattern")
        
        # Check that the incorrect pattern is NOT used
        self.assertNotIn("admin:auth_user_change", template_content,
                        "Template should NOT use admin:auth_user_change URL pattern")
        
        # Check for proper user link structure
        user_link_pattern = r'<a href="{% url \'admin:users_customuser_change\' usage\.user\.pk %}">'
        self.assertRegex(template_content, user_link_pattern,
                        "Template should have properly structured user links with correct URL pattern")
    
    def test_service_analytics_template_no_reverse_match_regression(self):
        """Test that template doesn't have any potential NoReverseMatch issues."""
        with open(self.analytics_template, 'r') as f:
            template_content = f.read()
        
        # Look for all URL tags that might cause issues
        problematic_patterns = [
            "admin:auth_user",  # Should use users_customuser instead
            "admin:user_",      # Another potential issue
        ]
        
        for pattern in problematic_patterns:
            self.assertNotIn(pattern, template_content,
                           f"Template should not contain potentially problematic URL pattern: {pattern}")
        
        # Verify known working patterns are present
        working_patterns = [
            "admin:index",
            "admin:app_list",
            "admin:credits_service_changelist",
            "admin:users_customuser_change",
            "admin:credits_service_change"
        ]
        
        found_patterns = []
        for pattern in working_patterns:
            if pattern in template_content:
                found_patterns.append(pattern)
        
        # At least some working patterns should be present
        self.assertGreater(len(found_patterns), 0,
                          "Template should contain at least some working URL patterns")


class AdminDashboardIndexIntegrationTests(unittest.TestCase):
    """Test cases for service management integration in admin dashboard index."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.templates_path = self.base_path / 'quickscale' / 'templates' / 'templates' / 'admin_dashboard'
        self.index_template = self.templates_path / 'index.html'
        
    def test_admin_dashboard_index_service_card(self):
        """Test that admin dashboard index includes service management card."""
        with open(self.index_template, 'r') as f:
            template_content = f.read()
        
        # Check for services card
        self.assertIn("Services", template_content,
                     "Services card title not found")
        self.assertIn("Service management & analytics", template_content,
                     "Services card subtitle not found")
        
        # Check for service features list
        service_features = [
            "Manage service status",
            "View usage analytics", 
            "Monitor credit consumption"
        ]
        
        for feature in service_features:
            self.assertIn(feature, template_content,
                         f"Service feature {feature} not listed")
        
        # Check for service admin link
        self.assertIn("{% url 'admin_dashboard:service_admin' %}", template_content,
                     "Service admin URL not found")
        self.assertIn("Manage Services", template_content,
                     "Manage Services link text not found")


if __name__ == '__main__':
    unittest.main() 