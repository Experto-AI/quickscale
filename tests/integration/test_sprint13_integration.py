"""
Integration tests for Sprint 13: Service Management Admin Interface.

These tests verify that the Sprint 13 Service Management Admin Interface features
work correctly in generated QuickScale projects, including Django admin enhancements,
admin dashboard pages, HTMX/Alpine.js integration, and service analytics.
"""

import os
import unittest
import tempfile
import shutil
from pathlib import Path
from tests.utils import ProjectTestMixin


class Sprint13ServiceAdminIntegrationTests(ProjectTestMixin, unittest.TestCase):
    """Integration tests for Sprint 13 service admin features in generated projects."""
    
    def setUp(self):
        """Set up test environment with a generated project."""
        super().setUp()
        self.create_test_project()
        
    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()
        
    def test_service_admin_enhanced_configuration_in_generated_project(self):
        """Test that enhanced service admin is properly configured in generated project."""
        admin_file = self.project_path / 'credits' / 'admin.py'
        
        with open(admin_file, 'r') as f:
            admin_content = f.read()
        
        # Check for enhanced Service admin configuration
        self.assertIn("@admin.register(Service)", admin_content,
                     "Service admin registration not found in generated project")
        self.assertIn("class ServiceAdmin(admin.ModelAdmin)", admin_content,
                     "ServiceAdmin class not found in generated project")
        
        # Check for analytics fields in list display
        enhanced_fields = [
            'usage_count', 'total_credits_consumed', 'unique_users_count', 'service_actions'
        ]
        for field in enhanced_fields:
            self.assertIn(field, admin_content,
                         f"Enhanced field {field} not found in generated Service admin")
        
        # Check for analytics methods implementation
        self.assertIn("def usage_count(self, obj):", admin_content,
                     "Service usage_count method not found in generated project")
        self.assertIn("def total_credits_consumed(self, obj):", admin_content,
                     "Service total_credits_consumed method not found in generated project")
        self.assertIn("def unique_users_count(self, obj):", admin_content,
                     "Service unique_users_count method not found in generated project")
        
        # Check for bulk operations
        self.assertIn("def bulk_enable_services(self, request, queryset):", admin_content,
                     "Service bulk_enable_services method not found in generated project")
        self.assertIn("def bulk_disable_services(self, request, queryset):", admin_content,
                     "Service bulk_disable_services method not found in generated project")
        
        # Check for custom analytics view
        self.assertIn("def service_usage_analytics_view(self, request, service_id):", admin_content,
                     "Service analytics view not found in generated project")
    
    def test_service_usage_admin_enhanced_configuration_in_generated_project(self):
        """Test that enhanced ServiceUsage admin is properly configured in generated project."""
        admin_file = self.project_path / 'credits' / 'admin.py'
        
        with open(admin_file, 'r') as f:
            admin_content = f.read()
        
        # Check for enhanced ServiceUsage admin configuration
        self.assertIn("@admin.register(ServiceUsage)", admin_content,
                     "ServiceUsage admin registration not found in generated project")
        self.assertIn("class ServiceUsageAdmin(admin.ModelAdmin)", admin_content,
                     "ServiceUsageAdmin class not found in generated project")
        
        # Check for enhanced display fields
        enhanced_fields = ['get_credit_cost', 'get_service_status', 'get_user_info']
        for field in enhanced_fields:
            self.assertIn(field, admin_content,
                         f"Enhanced field {field} not found in generated ServiceUsage admin")
        
        # Check for helper methods
        self.assertIn("def get_credit_cost(self, obj):", admin_content,
                     "ServiceUsage get_credit_cost method not found in generated project")
        self.assertIn("def get_service_status(self, obj):", admin_content,
                     "ServiceUsage get_service_status method not found in generated project")
    
    def test_admin_dashboard_service_views_in_generated_project(self):
        """Test that admin dashboard service management views are properly implemented."""
        views_file = self.project_path / 'admin_dashboard' / 'views.py'
        
        with open(views_file, 'r') as f:
            views_content = f.read()
        
        # Check for service admin view
        self.assertIn("def service_admin(request: HttpRequest) -> HttpResponse:", views_content,
                     "service_admin view not found in generated project")
        
        # Check for service detail view
        self.assertIn("def service_detail(request: HttpRequest, service_id: int) -> HttpResponse:", views_content,
                     "service_detail view not found in generated project")
        
        # Check for service toggle status view (HTMX endpoint)
        self.assertIn("def service_toggle_status(request: HttpRequest, service_id: int) -> JsonResponse:", views_content,
                     "service_toggle_status view not found in generated project")
        
        # Check for proper decorators
        self.assertIn("@login_required", views_content,
                     "login_required decorator not found on service views")
        self.assertIn("@user_passes_test(lambda u: u.is_staff)", views_content,
                     "Staff check not found on service views")
        
        # Check for analytics calculation in service_admin view
        self.assertIn("services_with_stats = []", views_content,
                     "Service analytics data structure not found")
        self.assertIn("service.usages.count()", views_content,
                     "Service usage count calculation not found")
        self.assertIn("Sum('credit_transaction__amount')", views_content,
                     "Service credit sum calculation not found")
    
    def test_admin_dashboard_service_urls_in_generated_project(self):
        """Test that admin dashboard service URLs are properly configured."""
        urls_file = self.project_path / 'admin_dashboard' / 'urls.py'
        
        with open(urls_file, 'r') as f:
            urls_content = f.read()
        
        # Check for service management URL patterns
        expected_urls = [
            "path('services/', views.service_admin, name='service_admin')",
            "path('services/<int:service_id>/', views.service_detail, name='service_detail')",
            "path('services/<int:service_id>/toggle/', views.service_toggle_status, name='service_toggle_status')"
        ]
        
        for url_pattern in expected_urls:
            self.assertIn(url_pattern, urls_content,
                         f"Service URL pattern not found in generated project: {url_pattern}")
    
    def test_service_admin_template_in_generated_project(self):
        """Test that service admin template is properly implemented in generated project."""
        template_file = self.project_path / 'templates' / 'admin_dashboard' / 'service_admin.html'
        
        self.assertTrue(template_file.exists(),
                       "Service admin template not found in generated project")
        
        with open(template_file, 'r') as f:
            template_content = f.read()
        
        # Check template structure
        self.assertIn("{% extends \"base.html\" %}", template_content,
                     "Service admin template inheritance not found")
        self.assertIn("Service Management - Admin Dashboard", template_content,
                     "Service admin template title not found")
        
        # Check for Alpine.js integration
        self.assertIn("x-data=\"serviceAdminData()\"", template_content,
                     "Alpine.js data binding not found in service admin template")
        self.assertIn("function serviceAdminData()", template_content,
                     "Alpine.js function not found in service admin template")
        
        # Check for HTMX integration
        self.assertIn("hx-post=\"{% url 'admin_dashboard:service_toggle_status'", template_content,
                     "HTMX service toggle not found in service admin template")
        self.assertIn("x-on:htmx:after-request=\"handleToggleResponse($event)\"", template_content,
                     "HTMX response handler not found in service admin template")
        
        # Check for service statistics display
        self.assertIn("{{ total_services }}", template_content,
                     "Total services display not found")
        self.assertIn("{{ active_services }}", template_content,
                     "Active services display not found")
        self.assertIn("{% for item in services_with_stats %}", template_content,
                     "Services loop not found")
    
    def test_service_detail_template_in_generated_project(self):
        """Test that service detail template is properly implemented in generated project."""
        template_file = self.project_path / 'templates' / 'admin_dashboard' / 'service_detail.html'
        
        self.assertTrue(template_file.exists(),
                       "Service detail template not found in generated project")
        
        with open(template_file, 'r') as f:
            template_content = f.read()
        
        # Check template structure
        self.assertIn("{% extends \"base.html\" %}", template_content,
                     "Service detail template inheritance not found")
        self.assertIn("Service Details", template_content,
                     "Service detail template title not found")
        
        # Check for Alpine.js integration
        self.assertIn("x-data=\"serviceDetailData(", template_content,
                     "Alpine.js data binding not found in service detail template")
        self.assertIn("function serviceDetailData(", template_content,
                     "Alpine.js function not found in service detail template")
        
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
    
    def test_service_analytics_admin_template_in_generated_project(self):
        """Test that service analytics admin template is properly implemented."""
        template_file = self.project_path / 'templates' / 'admin' / 'credits' / 'service_usage_analytics.html'
        
        self.assertTrue(template_file.exists(),
                       "Service analytics admin template not found in generated project")
        
        with open(template_file, 'r') as f:
            template_content = f.read()
        
        # Check template structure
        self.assertIn("{% extends \"admin/base_site.html\" %}", template_content,
                     "Service analytics template inheritance not found")
        self.assertIn("{% block breadcrumbs %}", template_content,
                     "Service analytics breadcrumbs not found")
        
        # Check for service information display
        self.assertIn("{{ service.name }}", template_content,
                     "Service name not displayed in analytics template")
        self.assertIn("{{ service.description }}", template_content,
                     "Service description not displayed in analytics template")
        
        # Check for analytics data display
        analytics_fields = [
            'analytics.total_uses',
            'analytics.uses_30_days', 
            'analytics.unique_users',
            'analytics.total_credits'
        ]
        for field in analytics_fields:
            self.assertIn(f"{{{{ {field} }}}}", template_content,
                         f"Analytics field {field} not found in template")
        
        # Check for usage table
        self.assertIn("{% for usage in recent_usages %}", template_content,
                     "Recent usage table not found in analytics template")
    
    def test_admin_dashboard_index_service_integration_in_generated_project(self):
        """Test that admin dashboard index properly integrates service management."""
        template_file = self.project_path / 'templates' / 'admin_dashboard' / 'index.html'
        
        with open(template_file, 'r') as f:
            template_content = f.read()
        
        # Check for services management card
        self.assertIn("Services", template_content,
                     "Services card not found in admin dashboard index")
        self.assertIn("Service management & analytics", template_content,
                     "Services card description not found")
        
        # Check for service features
        service_features = [
            "Manage service status",
            "View usage analytics",
            "Monitor credit consumption"
        ]
        for feature in service_features:
            self.assertIn(feature, template_content,
                         f"Service feature {feature} not found in dashboard")
        
        # Check for service admin link
        self.assertIn("{% url 'admin_dashboard:service_admin' %}", template_content,
                     "Service admin URL not found in dashboard")
        self.assertIn("Services", template_content,
                     "Services title not found in dashboard")
    
    def test_service_models_support_sprint13_features_in_generated_project(self):
        """Test that Service and ServiceUsage models support Sprint 13 analytics features."""
        models_file = self.project_path / 'credits' / 'models.py'
        
        with open(models_file, 'r') as f:
            models_content = f.read()
        
        # Check that Service model exists with required fields
        self.assertIn("class Service(models.Model)", models_content,
                     "Service model not found in generated project")
        
        # Check for required fields that support analytics
        required_fields = ['name', 'description', 'credit_cost', 'is_active', 'created_at', 'updated_at']
        for field in required_fields:
            self.assertIn(f"{field} = models.", models_content,
                         f"Service field {field} not found in generated project")
        
        # Check that ServiceUsage model exists
        self.assertIn("class ServiceUsage(models.Model)", models_content,
                     "ServiceUsage model not found in generated project")
        
        # Check for ServiceUsage relationships
        self.assertIn("user = models.ForeignKey", models_content,
                     "ServiceUsage user relationship not found")
        self.assertIn("service = models.ForeignKey", models_content,
                     "ServiceUsage service relationship not found")
        self.assertIn("credit_transaction = models.ForeignKey", models_content,
                     "ServiceUsage credit_transaction relationship not found")
    
    def test_django_admin_service_analytics_url_configuration(self):
        """Test that Django admin has proper URL configuration for service analytics."""
        admin_file = self.project_path / 'credits' / 'admin.py'
        
        with open(admin_file, 'r') as f:
            admin_content = f.read()
        
        # Check for custom URL patterns in ServiceAdmin
        self.assertIn("def get_urls(self):", admin_content,
                     "ServiceAdmin get_urls method not found")
        self.assertIn("'<int:service_id>/usage-analytics/'", admin_content,
                     "Service analytics URL pattern not found")
        self.assertIn("name='credits_service_usage_analytics'", admin_content,
                     "Service analytics URL name not found")
        
        # Check for service actions column
        self.assertIn("def service_actions(self, obj):", admin_content,
                     "Service actions method not found")
        self.assertIn("reverse('admin:credits_service_usage_analytics'", admin_content,
                     "Service analytics URL reverse not found")


class Sprint13ServiceManagementWorkflowTests(ProjectTestMixin, unittest.TestCase):
    """Test complete service management workflows in generated projects."""
    
    def setUp(self):
        """Set up test environment with a generated project."""
        super().setUp()
        self.create_test_project()
        
    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()
    
    def test_service_management_complete_workflow_integration(self):
        """Test that complete service management workflow is properly integrated."""
        # Check that all required components exist
        required_files = [
            'admin_dashboard/views.py',
            'admin_dashboard/urls.py',
            'templates/admin_dashboard/service_admin.html',
            'templates/admin_dashboard/service_detail.html',
            'templates/admin/credits/service_usage_analytics.html'
        ]
        
        for file_path in required_files:
            full_path = self.project_path / file_path
            self.assertTrue(full_path.exists(),
                           f"Required Sprint 13 file not found: {file_path}")
    
    def test_service_admin_dashboard_navigation_integration(self):
        """Test that service management is properly integrated in navigation."""
        # Check admin dashboard index includes service management
        index_template = self.project_path / 'templates' / 'admin_dashboard' / 'index.html'
        
        with open(index_template, 'r') as f:
            content = f.read()
        
        # Should have service management section
        self.assertIn("{% url 'admin_dashboard:service_admin' %}", content,
                     "Service admin navigation not found in dashboard")
        
        # Check that service admin view includes proper navigation back
        service_admin_template = self.project_path / 'templates' / 'admin_dashboard' / 'service_admin.html'
        
        with open(service_admin_template, 'r') as f:
            content = f.read()
        
        # Should have link to Django admin for creating services
        self.assertIn("/admin/credits/service/", content,
                     "Django admin service link not found")
    
    def test_service_analytics_data_consistency(self):
        """Test that service analytics data calculations are consistent across views."""
        admin_file = self.project_path / 'credits' / 'admin.py'
        views_file = self.project_path / 'admin_dashboard' / 'views.py'
        
        # Check that both admin and dashboard views use consistent analytics calculations
        with open(admin_file, 'r') as f:
            admin_content = f.read()
        
        with open(views_file, 'r') as f:
            views_content = f.read()
        
        # Both should use similar analytics calculations
        common_calculations = [
            "Sum('credit_transaction__amount')",
            "values('user').distinct().count()",
            "timedelta(days=30)",
            "timedelta(days=7)"
        ]
        
        for calculation in common_calculations:
            self.assertIn(calculation, admin_content,
                         f"Analytics calculation {calculation} not found in admin")
            self.assertIn(calculation, views_content,
                         f"Analytics calculation {calculation} not found in views")


if __name__ == '__main__':
    unittest.main() 