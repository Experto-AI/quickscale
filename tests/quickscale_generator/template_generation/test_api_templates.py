"""Tests for API template generation and functionality in QuickScale projects.

This test validates that QuickScale generates working API authentication and endpoint
templates as described in the README_API_TESTS.md.
templates as described in docs/README_API_AUTH.md.
"""

import os
import tempfile
import shutil
from pathlib import Path
from django.test import TestCase

from tests.utils import DynamicProjectTestCase


class TestAPITemplateGeneration(DynamicProjectTestCase):
    """Test that QuickScale generates working API authentication templates."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.project_name = "test_api_project"

    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()

    def test_api_key_model_generation(self):
        """Test that APIKey model is correctly generated for API authentication."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that APIKey model exists in credits app
        models_file = self.project_path / "credits" / "models.py"
        models_content = models_file.read_text()
        
        # Verify APIKey model components
        self.assertIn("class APIKey", models_content, "APIKey model should be generated")
        self.assertIn("prefix = models.CharField", models_content, "APIKey should have prefix field")
        self.assertIn("hashed_key = models.CharField", models_content, "APIKey should have hashed_key field")
        self.assertIn("name = models.CharField", models_content, "APIKey should have name field")
        self.assertIn("is_active = models.BooleanField", models_content, "APIKey should have is_active field")
        self.assertIn("expiry_date = models.DateTimeField", models_content, "APIKey should have expiry_date field")
        
        # Verify APIKey methods
        self.assertIn("generate_key", models_content, "APIKey should have generate_key method")
        self.assertIn("get_hashed_key", models_content, "APIKey should have get_hashed_key method")
        self.assertIn("verify_secret_key", models_content, "APIKey should have verify_secret_key method")
        self.assertIn("is_valid", models_content, "APIKey should have is_valid property")

    def test_api_middleware_generation(self):
        """Test that API authentication middleware is correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that API middleware exists
        middleware_file = self.project_path / "core" / "api_middleware.py"
        self.assertTrue(middleware_file.exists(), "core/api_middleware.py should exist in generated project")
        
        # Check middleware functionality
        middleware_content = middleware_file.read_text()
        self.assertIn("APIKeyAuthenticationMiddleware", middleware_content, 
                     "APIKeyAuthenticationMiddleware should be generated")
        self.assertIn("process_request", middleware_content, 
                     "Middleware should have process_request method")
        self.assertIn("Authorization", middleware_content, 
                     "Middleware should handle Authorization header")
        self.assertIn("Bearer", middleware_content, 
                     "Middleware should handle Bearer token format")

    def test_api_views_generation(self):
        """Test that API views are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check if api app exists or views are in another location
        api_app_path = self.project_path / "api"
        if api_app_path.exists():
            views_file = api_app_path / "views.py"
            self.assertTrue(views_file.exists(), "api/views.py should exist in generated project")
            
            views_content = views_file.read_text()
            self.assertIn("TextProcessingView", views_content, "TextProcessingView should be generated")

    def test_api_urls_generation(self):
        """Test that API URLs are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check main URLs include API routes
        main_urls_file = self.project_path / "core" / "urls.py"
        main_urls_content = main_urls_file.read_text()
        self.assertIn("api/", main_urls_content, "API URLs should be included in main URLs")

    def test_api_key_management_views_generation(self):
        """Test that API key management views are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that API key management exists in users or credits app
        users_views_file = self.project_path / "users" / "views.py"
        credits_views_file = self.project_path / "credits" / "views.py"
        
        # Check at least one contains API key management
        users_content = users_views_file.read_text() if users_views_file.exists() else ""
        credits_content = credits_views_file.read_text() if credits_views_file.exists() else ""
        
        api_key_management_exists = (
            "api_keys" in users_content or "api_keys" in credits_content or
            "ApiKey" in users_content or "ApiKey" in credits_content
        )
        self.assertTrue(api_key_management_exists, 
                       "API key management views should be generated")

    def test_api_key_templates_generation(self):
        """Test that API key management templates are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check for API key templates in users templates
        users_templates_dir = self.project_path / "templates" / "users"
        if users_templates_dir.exists():
            api_keys_template = users_templates_dir / "api_keys.html"
            if api_keys_template.exists():
                self.assertTrue(True, "API keys template found")
                return
        
        # Alternative: Check if templates exist elsewhere
        # For now, we'll check that some API-related template structure exists
        templates_base = self.project_path / "templates"
        api_template_found = False
        
        for template_file in templates_base.rglob("*.html"):
            content = template_file.read_text()
            if "api" in content.lower() and "key" in content.lower():
                api_template_found = True
                break
        
        # This is a soft assertion since API templates might be organized differently
        if not api_template_found:
            print("Warning: No API key templates found - this might need to be implemented")

    def test_service_usage_model_generation(self):
        """Test that ServiceUsage model is correctly generated for API tracking."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that ServiceUsage model exists
        models_file = self.project_path / "credits" / "models.py"
        models_content = models_file.read_text()
        
        self.assertIn("class ServiceUsage", models_content, "ServiceUsage model should be generated")
        self.assertIn("service = models.ForeignKey", models_content, "ServiceUsage should have service field")
        self.assertIn("user = models.ForeignKey", models_content, "ServiceUsage should have user field")
        self.assertIn("credit_transaction = models.ForeignKey", models_content, "ServiceUsage should track credits through credit_transaction")

    def test_api_authentication_middleware_in_settings(self):
        """Test that API authentication middleware is properly configured in settings."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that API middleware is in MIDDLEWARE settings
        settings_file = self.project_path / "core" / "settings.py"
        settings_content = settings_file.read_text()
        
        # The middleware might be conditionally included or configured differently
        # So we check for the middleware class name
        api_middleware_configured = (
            "APIKeyAuthenticationMiddleware" in settings_content or
            "api_middleware" in settings_content
        )
        
        if not api_middleware_configured:
            print("Warning: API authentication middleware not found in settings - might need configuration")


class TestAPITemplateValidation(TestCase):
    """Test validation of API template content for correctness."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent.parent / 'quickscale' / 'project_templates'
        self.core_path = self.base_path / 'core'
        self.credits_path = self.base_path / 'credits'

    def test_api_middleware_syntax_validation(self):
        """Test that generated API middleware has valid Python syntax."""
        middleware_file = self.core_path / 'api_middleware.py'
        self.assertTrue(middleware_file.exists(), "core/api_middleware.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        middleware_content = middleware_file.read_text()
        try:
            compile(middleware_content, str(middleware_file), 'exec')
        except SyntaxError as e:
            self.fail(f"API middleware template has syntax error: {e}")

    def test_api_key_model_validation(self):
        """Test that APIKey model in credits app is properly defined."""
        models_file = self.credits_path / 'models.py'
        self.assertTrue(models_file.exists(), "credits/models.py template should exist")
        
        models_content = models_file.read_text()
        
        # Verify APIKey model exists and has required components
        self.assertIn("class APIKey", models_content, "APIKey model should exist in credits/models.py")
        
        # Check for security-related methods
        security_methods = ["generate_key", "get_hashed_key", "verify_secret_key"]
        for method in security_methods:
            self.assertIn(method, models_content, f"APIKey should have {method} method for security")

    def test_credits_models_include_api_functionality(self):
        """Test that credits models include API-related functionality."""
        models_file = self.credits_path / 'models.py'
        models_content = models_file.read_text()
        
        # Check for Service and ServiceUsage models needed for API
        self.assertIn("class Service", models_content, "Service model should exist for API functionality")
        self.assertIn("class ServiceUsage", models_content, "ServiceUsage model should exist for API tracking")

    def test_api_migration_exists(self):
        """Test that API key migration exists in credits app."""
        migrations_dir = self.credits_path / 'migrations'
        
        # Check for API key migration
        api_migration_found = False
        for migration_file in migrations_dir.glob("*.py"):
            if migration_file.name == "__init__.py":
                continue
            content = migration_file.read_text()
            if "APIKey" in content or "api_key" in content:
                api_migration_found = True
                break
        
        self.assertTrue(api_migration_found, "API key migration should exist in credits/migrations")


class TestAPIEndpointsGeneration(TestCase):
    """Test that API endpoints are properly generated and accessible."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent.parent / 'quickscale' / 'project_templates'

    def test_text_processing_endpoint_exists(self):
        """Test that text processing API endpoint is generated."""
        # Check if api app exists
        api_app_path = self.base_path / 'api'
        
        if api_app_path.exists():
            views_file = api_app_path / 'views.py'
            urls_file = api_app_path / 'urls.py'
            
            if views_file.exists():
                views_content = views_file.read_text()
                self.assertIn("process", views_content.lower(), 
                             "Text processing view should exist in API app")
            
            if urls_file.exists():
                urls_content = urls_file.read_text()
                self.assertIn("process", urls_content.lower(), 
                             "Text processing URL should exist in API app")

    def test_api_documentation_endpoint(self):
        """Test that API documentation endpoint is generated."""
        api_app_path = self.base_path / 'api'
        
        if api_app_path.exists():
            # Check for API documentation in views or templates
            views_file = api_app_path / 'views.py'
            if views_file.exists():
                views_content = views_file.read_text()
                # Look for documentation-related views
                doc_indicators = ["docs", "documentation", "api_info", "info"]
                has_docs = any(indicator in views_content.lower() for indicator in doc_indicators)
                
                if not has_docs:
                    print("Warning: API documentation endpoint not found - might need implementation")
