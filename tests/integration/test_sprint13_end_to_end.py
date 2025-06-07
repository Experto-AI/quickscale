"""
End-to-End integration tests for Sprint 13: Service Management Admin Interface.

These tests verify complete workflows and user journeys for service management
in generated QuickScale projects, ensuring all components work together properly.
"""

import os
import unittest
import tempfile
import shutil
from pathlib import Path
from tests.utils import ProjectTestMixin


class Sprint13EndToEndWorkflowTests(ProjectTestMixin, unittest.TestCase):
    """End-to-end tests for complete service management workflows."""
    
    def setUp(self):
        """Set up test environment with a generated project."""
        super().setUp()
        self.create_test_project()
        
    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()
    
    def test_complete_service_admin_workflow(self):
        """Test complete service admin workflow from dashboard to analytics."""
        # Check dashboard index has service management card
        dashboard_index = self.project_path / 'templates' / 'admin_dashboard' / 'index.html'
        with open(dashboard_index, 'r') as f:
            dashboard_content = f.read()
        
        # Dashboard should link to service admin
        self.assertIn("{% url 'admin_dashboard:service_admin' %}", dashboard_content,
                     "Dashboard missing service admin link")
        
        # Service admin page should exist and have all components
        service_admin_template = self.project_path / 'templates' / 'admin_dashboard' / 'service_admin.html'
        with open(service_admin_template, 'r') as f:
            service_admin_content = f.read()
        
        # Should have filtering, table, and toggle functionality
        workflow_components = [
            'x-data="serviceAdminData()"',  # Alpine.js data
            '{% for item in services_with_stats %}',  # Service listing
            'hx-post="{% url \'admin_dashboard:service_toggle_status\'',  # HTMX toggle
            '{% url \'admin_dashboard:service_detail\'',  # Detail view link
            'statusFilter',  # Filtering
            'searchTerm'  # Search
        ]
        
        for component in workflow_components:
            self.assertIn(component, service_admin_content,
                         f"Service admin workflow component missing: {component}")
    
    def test_service_detail_workflow_integration(self):
        """Test service detail page workflow integration."""
        service_detail_template = self.project_path / 'templates' / 'admin_dashboard' / 'service_detail.html'
        
        with open(service_detail_template, 'r') as f:
            detail_content = f.read()
        
        # Should have complete service information and actions
        detail_components = [
            '{{ service.name }}',  # Service info
            '{{ service.description }}',
            '{{ service.credit_cost }}',
            '{{ analytics.total_usage }}',  # Analytics
            '{{ analytics.unique_users }}',
            'hx-post="{% url \'admin_dashboard:service_toggle_status\'',  # Toggle
            'href="{% url \'admin_dashboard:service_admin\' %}"',  # Back navigation
            '/admin/credits/service/{{ service.id }}/change/'  # Edit link
        ]
        
        for component in detail_components:
            self.assertIn(component, detail_content,
                         f"Service detail workflow component missing: {component}")
    
    def test_django_admin_analytics_integration(self):
        """Test Django admin analytics integration workflow."""
        admin_file = self.project_path / 'credits' / 'admin.py'
        
        with open(admin_file, 'r') as f:
            admin_content = f.read()
        
        # Should have complete analytics workflow
        analytics_workflow = [
            'def service_usage_analytics_view',  # Analytics view
            'credits_service_usage_analytics',  # URL name
            'service_usage_analytics.html',  # Template
            'def service_actions',  # Action buttons
            'View Analytics'  # Button text
        ]
        
        for component in analytics_workflow:
            self.assertIn(component, admin_content,
                         f"Django admin analytics workflow component missing: {component}")
        
        # Check analytics template exists
        analytics_template = self.project_path / 'templates' / 'admin' / 'credits' / 'service_usage_analytics.html'
        self.assertTrue(analytics_template.exists(),
                       "Service analytics template missing")
    
    def test_service_management_url_workflow(self):
        """Test complete URL workflow for service management."""
        urls_file = self.project_path / 'admin_dashboard' / 'urls.py'
        
        with open(urls_file, 'r') as f:
            urls_content = f.read()
        
        # Should have complete URL workflow
        url_patterns = [
            "path('services/', views.service_admin, name='service_admin')",
            "path('services/<int:service_id>/', views.service_detail, name='service_detail')",
            "path('services/<int:service_id>/toggle/', views.service_toggle_status, name='service_toggle_status')"
        ]
        
        for pattern in url_patterns:
            self.assertIn(pattern, urls_content,
                         f"URL pattern missing from workflow: {pattern}")
    
    def test_service_management_view_workflow(self):
        """Test complete view workflow for service management."""
        views_file = self.project_path / 'admin_dashboard' / 'views.py'
        
        with open(views_file, 'r') as f:
            views_content = f.read()
        
        # Should have complete view workflow with proper data flow
        view_workflow = [
            'def service_admin(request: HttpRequest) -> HttpResponse:',  # Main view
            'services_with_stats = []',  # Data structure
            'service.usages.count()',  # Analytics calculation
            'def service_detail(request: HttpRequest, service_id: int)',  # Detail view
            'def service_toggle_status(request: HttpRequest, service_id: int)',  # Toggle endpoint
            'JsonResponse',  # AJAX response
            '@login_required',  # Security
            '@user_passes_test(lambda u: u.is_staff)'  # Staff check
        ]
        
        for component in view_workflow:
            self.assertIn(component, views_content,
                         f"View workflow component missing: {component}")


class Sprint13DataConsistencyTests(ProjectTestMixin, unittest.TestCase):
    """Test data consistency across all Sprint 13 components."""
    
    def setUp(self):
        """Set up test environment with a generated project."""
        super().setUp()
        self.create_test_project()
        
    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()
    
    def test_analytics_calculation_consistency(self):
        """Test that analytics calculations are consistent across all components."""
        admin_file = self.project_path / 'credits' / 'admin.py'
        views_file = self.project_path / 'admin_dashboard' / 'views.py'
        
        with open(admin_file, 'r') as f:
            admin_content = f.read()
        
        with open(views_file, 'r') as f:
            views_content = f.read()
        
        # Analytics calculations should be consistent
        consistent_calculations = [
            "Sum('credit_transaction__amount')",  # Credit sum
            "values('user').distinct().count()",  # Unique users
            "timedelta(days=30)",  # 30-day period
            "timedelta(days=7)",  # 7-day period
            "abs(",  # Absolute values for credits
            "or 0"  # Null handling
        ]
        
        for calc in consistent_calculations:
            admin_has_calc = calc in admin_content
            views_has_calc = calc in views_content
            
            # Both should have the calculation or neither (but at least one should)
            self.assertTrue(admin_has_calc or views_has_calc,
                           f"Analytics calculation {calc} not found in either admin or views")
    
    def test_service_status_display_consistency(self):
        """Test that service status display is consistent across templates."""
        templates_to_check = [
            'templates/admin_dashboard/service_admin.html',
            'templates/admin_dashboard/service_detail.html'
        ]
        
        status_patterns = [
            'is_active',  # Status field reference
            'Active',  # Status text
            'Inactive',  # Status text
            'is-success',  # Success styling
            'is-warning'  # Warning styling
        ]
        
        for template_path in templates_to_check:
            full_path = self.project_path / template_path
            
            with open(full_path, 'r') as f:
                template_content = f.read()
            
            for pattern in status_patterns:
                self.assertIn(pattern, template_content,
                             f"Status pattern {pattern} not found in {template_path}")
    
    def test_credit_cost_display_consistency(self):
        """Test that credit cost display is consistent across components."""
        files_to_check = [
            ('credits/admin.py', ['credit_cost', 'credits']),
            ('templates/admin_dashboard/service_admin.html', ['credit_cost', 'credits']),
            ('templates/admin_dashboard/service_detail.html', ['credit_cost', 'credits'])
        ]
        
        for file_path, patterns in files_to_check:
            full_path = self.project_path / file_path
            
            with open(full_path, 'r') as f:
                content = f.read()
            
            for pattern in patterns:
                self.assertIn(pattern, content,
                             f"Credit pattern {pattern} not found in {file_path}")


class Sprint13SecurityIntegrationTests(ProjectTestMixin, unittest.TestCase):
    """Test security integration across all Sprint 13 components."""
    
    def setUp(self):
        """Set up test environment with a generated project."""
        super().setUp()
        self.create_test_project()
        
    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()
    
    def test_staff_access_enforcement(self):
        """Test that staff access is enforced across all service management views."""
        views_file = self.project_path / 'admin_dashboard' / 'views.py'
        
        with open(views_file, 'r') as f:
            views_content = f.read()
        
        # All service management views should have staff checks
        service_views = [
            'def service_admin(request: HttpRequest)',
            'def service_detail(request: HttpRequest, service_id: int)',
            'def service_toggle_status(request: HttpRequest, service_id: int)'
        ]
        
        for view in service_views:
            view_start = views_content.find(view)
            self.assertNotEqual(view_start, -1, f"View not found: {view}")
            
            # Look for staff check before the view definition
            view_section = views_content[max(0, view_start-200):view_start+100]
            self.assertIn("@user_passes_test(lambda u: u.is_staff)", view_section,
                         f"Staff check not found for view: {view}")
    
    def test_csrf_protection_integration(self):
        """Test that CSRF protection is properly integrated in HTMX calls."""
        templates_to_check = [
            'templates/admin_dashboard/service_admin.html',
            'templates/admin_dashboard/service_detail.html'
        ]
        
        for template_path in templates_to_check:
            full_path = self.project_path / template_path
            
            with open(full_path, 'r') as f:
                template_content = f.read()
            
            # Should have CSRF protection in HTMX calls
            csrf_patterns = [
                'hx-headers',
                'X-CSRFToken',
                '{{ csrf_token }}'
            ]
            
            has_htmx = 'hx-post' in template_content
            if has_htmx:  # Only check CSRF if HTMX is used
                for pattern in csrf_patterns:
                    self.assertIn(pattern, template_content,
                                 f"CSRF pattern {pattern} not found in {template_path}")
    
    def test_method_validation_integration(self):
        """Test that HTTP method validation is properly integrated."""
        views_file = self.project_path / 'admin_dashboard' / 'views.py'
        
        with open(views_file, 'r') as f:
            views_content = f.read()
        
        # service_toggle_status should validate POST method
        toggle_view_section = views_content[views_content.find('def service_toggle_status'):]
        
        method_validation_patterns = [
            "if request.method != 'POST':",
            "return JsonResponse({'error': 'Method not allowed'}, status=405)"
        ]
        
        for pattern in method_validation_patterns:
            self.assertIn(pattern, toggle_view_section,
                         f"Method validation pattern not found: {pattern}")


class Sprint13PerformanceIntegrationTests(ProjectTestMixin, unittest.TestCase):
    """Test performance considerations in Sprint 13 implementation."""
    
    def setUp(self):
        """Set up test environment with a generated project."""
        super().setUp()
        self.create_test_project()
        
    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()
    
    def test_efficient_database_queries(self):
        """Test that analytics queries are efficiently structured."""
        admin_file = self.project_path / 'credits' / 'admin.py'
        views_file = self.project_path / 'admin_dashboard' / 'views.py'
        
        with open(admin_file, 'r') as f:
            admin_content = f.read()
        
        with open(views_file, 'r') as f:
            views_content = f.read()
        
        # Should use efficient query patterns
        efficient_patterns = [
            'select_related',  # Efficient joins
            'aggregate',  # Database-level aggregation
            'values(',  # Efficient field selection
            'distinct()'  # Efficient counting
        ]
        
        all_content = admin_content + views_content
        
        for pattern in efficient_patterns:
            self.assertIn(pattern, all_content,
                         f"Efficient query pattern {pattern} not found")
    
    def test_analytics_caching_considerations(self):
        """Test that analytics are structured for potential caching."""
        views_file = self.project_path / 'admin_dashboard' / 'views.py'
        
        with open(views_file, 'r') as f:
            views_content = f.read()
        
        # Analytics calculations should be structured for caching
        # (e.g., using consistent time periods, structured data)
        caching_friendly_patterns = [
            'last_30_days = now - timedelta(days=30)',  # Consistent time periods
            'last_7_days = now - timedelta(days=7)',
            'services_with_stats = []',  # Structured data format
        ]
        
        for pattern in caching_friendly_patterns:
            self.assertIn(pattern, views_content,
                         f"Caching-friendly pattern {pattern} not found")


if __name__ == '__main__':
    unittest.main() 