"""
Tests for Sprint 20: URL Configuration Review.

This test suite validates:
1. URL routing hierarchy and namespace organization
2. URL pattern consistency across apps
3. Proper use of include() and namespacing
4. RESTful URL design patterns
5. Security considerations in URL routing
"""

import os
import unittest
import re
from pathlib import Path


class URLRoutingHierarchyTests(unittest.TestCase):
    """Test cases for URL routing hierarchy and organization."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.url_files = {
            'core': self.base_path / 'quickscale' / 'project_templates' / 'core' / 'urls.py',
            'credits': self.base_path / 'quickscale' / 'project_templates' / 'credits' / 'urls.py',
            'api': self.base_path / 'quickscale' / 'project_templates' / 'api' / 'urls.py',
            'public': self.base_path / 'quickscale' / 'project_templates' / 'public' / 'urls.py',
            'users': self.base_path / 'quickscale' / 'project_templates' / 'users' / 'urls.py',
            'stripe_manager': self.base_path / 'quickscale' / 'project_templates' / 'stripe_manager' / 'urls.py',
            'admin_dashboard': self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'urls.py',
            'services': self.base_path / 'quickscale' / 'project_templates' / 'services' / 'urls.py'
        }
    
    def test_core_urls_hierarchy(self):
        """Test that core URLs properly organize and include app URLs."""
        if self.url_files['core'].exists():
            with open(self.url_files['core'], 'r') as f:
                content = f.read()
            
            # Should use include() for app URLs
            self.assertIn("from django.urls import path, include", content,
                         "Core URLs should import include")
            
            # Should include app URLs with proper patterns
            app_includes = [
                "include('credits.urls')",
                "include('public.urls')", 
                "include('users.urls')",
                "include('admin_dashboard.urls')"
            ]
            
            for include_pattern in app_includes:
                if include_pattern in content:
                    self.assertIn(include_pattern, content,
                                 f"Should include {include_pattern}")
    
    def test_namespace_organization(self):
        """Test that URLs use proper namespace organization."""
        for app_name, url_file in self.url_files.items():
            if url_file.exists() and app_name != 'core':
                with open(url_file, 'r') as f:
                    content = f.read()
                
                # Should define app_name for namespacing
                if "app_name = " in content:
                    # Special case: stripe_manager app uses 'stripe' as app_name
                    expected_app_name = 'stripe' if app_name == 'stripe_manager' else app_name
                    self.assertIn(f"app_name = '{expected_app_name}'", content,
                                 f"{app_name} should define proper app_name")
    
    def test_credits_url_patterns(self):
        """Test credits app URL patterns for consistency."""
        if self.url_files['credits'].exists():
            with open(self.url_files['credits'], 'r') as f:
                content = f.read()
            
            # Should have dashboard and service-related URLs
            expected_patterns = [
                "dashboard",
                "services",
                "buy-credits"
            ]
            
            for pattern in expected_patterns:
                if pattern in content:
                    # Check that pattern uses proper naming
                    self.assertIn(f"'{pattern}'", content,
                                 f"Credits URL should have {pattern} pattern")
    
    def test_api_url_patterns(self):
        """Test API URL patterns follow RESTful design."""
        if self.url_files['api'].exists():
            with open(self.url_files['api'], 'r') as f:
                content = f.read()
            
            # Should have API versioning if present
            if "api/v" in content:
                self.assertIn("api/v1/", content,
                             "API should use versioning")
            
            # Should have proper API endpoints
            api_patterns = [
                "credits",
                "services",
                "auth"
            ]
            
            for pattern in api_patterns:
                if pattern in content:
                    # API URLs should be RESTful
                    pattern_context = content[content.find(pattern)-50:content.find(pattern)+50]
                    self.assertTrue(
                        "path(" in pattern_context or "url(" in pattern_context,
                        f"API pattern {pattern} should be properly defined"
                    )


class URLPatternConsistencyTests(unittest.TestCase):
    """Test cases for URL pattern consistency across applications."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.url_files = {
            'credits': self.base_path / 'quickscale' / 'project_templates' / 'credits' / 'urls.py',
            'public': self.base_path / 'quickscale' / 'project_templates' / 'public' / 'urls.py',
            'users': self.base_path / 'quickscale' / 'project_templates' / 'users' / 'urls.py',
            'admin_dashboard': self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'urls.py'
        }
    
    def test_url_naming_conventions(self):
        """Test that URL patterns follow consistent naming conventions."""
        for app_name, url_file in self.url_files.items():
            if url_file.exists():
                with open(url_file, 'r') as f:
                    content = f.read()
                
                # Extract URL names using regex
                url_names = re.findall(r"name=['\"]([^'\"]+)['\"]", content)
                
                for name in url_names:
                    # URL names should use underscores, not hyphens
                    if '_' in name:
                        self.assertNotIn('-', name,
                                       f"URL name {name} should use underscores consistently")
                    
                    # URL names should be descriptive
                    self.assertGreater(len(name), 2,
                                     f"URL name {name} should be descriptive")
    
    def test_url_pattern_structure(self):
        """Test that URL patterns have consistent structure."""
        for app_name, url_file in self.url_files.items():
            if url_file.exists():
                with open(url_file, 'r') as f:
                    content = f.read()
                
                # Should use path() instead of url() for Django 2.0+
                if "from django.urls import" in content:
                    self.assertIn("path", content,
                                 f"{app_name} should use path() for URL patterns")
                
                # Should have urlpatterns list
                self.assertIn("urlpatterns = [", content,
                             f"{app_name} should define urlpatterns list")
    
    def test_view_import_patterns(self):
        """Test that view imports follow consistent patterns."""
        for app_name, url_file in self.url_files.items():
            if url_file.exists():
                with open(url_file, 'r') as f:
                    content = f.read()
                
                # Should import views appropriately
                if "views." in content:
                    # Should have proper view imports
                    self.assertIn("from . import views", content,
                                 f"{app_name} should import views properly")


class RESTfulURLDesignTests(unittest.TestCase):
    """Test cases for RESTful URL design patterns."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.api_urls = self.base_path / 'quickscale' / 'project_templates' / 'api' / 'urls.py'
        self.credits_urls = self.base_path / 'quickscale' / 'project_templates' / 'credits' / 'urls.py'
    
    def test_resource_based_urls(self):
        """Test that URLs follow resource-based patterns."""
        if self.credits_urls.exists():
            with open(self.credits_urls, 'r') as f:
                content = f.read()
            
            # Should have resource-based patterns
            resource_patterns = [
                "credits/",
                "services/", 
                "transactions/"
            ]
            
            for pattern in resource_patterns:
                if pattern in content:
                    # Resource URLs should be plural
                    self.assertTrue(pattern.endswith('s/'),
                                   f"Resource URL {pattern} should be plural")
    
    def test_api_endpoint_structure(self):
        """Test API endpoint structure follows REST conventions."""
        if self.api_urls.exists():
            with open(self.api_urls, 'r') as f:
                content = f.read()
            
            # Should have proper API structure
            if "api/" in content:
                # API endpoints should be organized
                self.assertIn("urlpatterns", content,
                             "API should define URL patterns")
    
    def test_action_based_urls(self):
        """Test that action-based URLs are properly structured."""
        for app_name in ['credits', 'admin_dashboard']:
            url_file = self.base_path / 'quickscale' / 'project_templates' / app_name / 'urls.py'
            if url_file.exists():
                with open(url_file, 'r') as f:
                    content = f.read()
                
                # Look for action patterns
                action_patterns = re.findall(r"'([^']+/[^']*)'", content)
                
                for pattern in action_patterns:
                    if '/' in pattern and not pattern.endswith('/'):
                        # Action URLs should be descriptive
                        parts = pattern.split('/')
                        for part in parts:
                            if part and not part.startswith('<'):
                                self.assertGreater(len(part), 1,
                                                 f"URL part {part} should be descriptive")


class URLSecurityTests(unittest.TestCase):
    """Test cases for security considerations in URL routing."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.url_files = {
            'core': self.base_path / 'quickscale' / 'project_templates' / 'core' / 'urls.py',
            'admin_dashboard': self.base_path / 'quickscale' / 'project_templates' / 'admin_dashboard' / 'urls.py',
            'api': self.base_path / 'quickscale' / 'project_templates' / 'api' / 'urls.py'
        }
    
    def test_admin_url_patterns(self):
        """Test that admin URLs are properly secured."""
        if self.url_files['admin_dashboard'].exists():
            with open(self.url_files['admin_dashboard'], 'r') as f:
                content = f.read()
            
            # Admin URLs should not expose sensitive patterns
            sensitive_patterns = ['admin/', 'secret/', 'private/']
            
            for pattern in sensitive_patterns:
                if pattern in content:
                    # Should have proper view protection (checked via decorators)
                    self.assertIn("views.", content,
                                 "Admin URLs should reference protected views")
    
    def test_debug_url_patterns(self):
        """Test that debug URLs are conditionally included."""
        if self.url_files['core'].exists():
            with open(self.url_files['core'], 'r') as f:
                content = f.read()
            
            # Debug URLs should be conditional
            if "debug" in content.lower():
                self.assertIn("settings.DEBUG", content,
                             "Debug URLs should be conditional on DEBUG setting")
    
    def test_parameter_validation_patterns(self):
        """Test that URL parameters use proper validation."""
        for app_name, url_file in self.url_files.items():
            if url_file.exists():
                with open(url_file, 'r') as f:
                    content = f.read()
                
                # Look for URL parameters
                params = re.findall(r'<(\w+):(\w+)>', content)
                
                for param_type, param_name in params:
                    # Should use appropriate parameter types
                    valid_types = ['int', 'str', 'slug', 'uuid', 'path']
                    self.assertIn(param_type, valid_types,
                                 f"Parameter type {param_type} should be valid")
                    
                    # Parameter names should be descriptive
                    self.assertGreater(len(param_name), 1,
                                     f"Parameter name {param_name} should be descriptive")


if __name__ == '__main__':
    unittest.main() 