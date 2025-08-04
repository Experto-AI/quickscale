"""Tests for Credits system template generation in QuickScale projects.

This test validates that QuickScale generates working credits system templates
including models, admin interface, views, and API functionality.
"""

import os
import tempfile
import shutil
from pathlib import Path
from django.test import TestCase

from tests.utils import ProjectTestMixin


class TestCreditsTemplateGeneration(ProjectTestMixin, TestCase):
    """Test that QuickScale generates working Credits system templates."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        # Create a temporary directory for the test project
        self.test_dir = Path(tempfile.mkdtemp())
        self.project_name = "test_credits_project"
        self.project_path = self.test_dir / self.project_name

    def tearDown(self):
        """Clean up test environment."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        super().tearDown()

    def test_credits_models_template_generation(self):
        """Test that Credits models are correctly generated in project templates."""
        # Create test project
        self.create_test_project()
        
        # Check that credits models.py exists
        models_file = self.project_path / "credits" / "models.py"
        self.assertTrue(models_file.exists(), "credits/models.py should exist in generated project")
        
        # Check that models.py contains required classes
        models_content = models_file.read_text()
        self.assertIn("class CreditAccount", models_content, "CreditAccount model should be generated")
        self.assertIn("class CreditTransaction", models_content, "CreditTransaction model should be generated")
        self.assertIn("class Service", models_content, "Service model should be generated")
        self.assertIn("class ServiceUsage", models_content, "ServiceUsage model should be generated")
        self.assertIn("class APIKey", models_content, "APIKey model should be generated")

    def test_credits_admin_template_generation(self):
        """Test that Credits admin interface is correctly generated."""
        # Create test project
        self.create_test_project()
        
        # Check that credits admin.py exists
        admin_file = self.project_path / "credits" / "admin.py"
        self.assertTrue(admin_file.exists(), "credits/admin.py should exist in generated project")
        
        # Check that admin.py contains required admin classes
        admin_content = admin_file.read_text()
        self.assertIn("CreditAccountAdmin", admin_content, "CreditAccountAdmin should be generated")
        self.assertIn("ServiceAdmin", admin_content, "ServiceAdmin should be generated")
        self.assertIn("@admin.register", admin_content, "Admin registration decorators should be generated")

    def test_credits_urls_template_generation(self):
        """Test that Credits URLs are correctly generated."""
        # Create test project
        self.create_test_project()
        
        # Check that credits urls.py exists
        urls_file = self.project_path / "credits" / "urls.py"
        self.assertTrue(urls_file.exists(), "credits/urls.py should exist in generated project")
        
        # Check that urls.py contains required patterns
        urls_content = urls_file.read_text()
        self.assertIn("dashboard", urls_content, "dashboard URL should be generated")
        self.assertIn("buy_credits", urls_content, "buy_credits URL should be generated")

    def test_credits_views_template_generation(self):
        """Test that Credits views are correctly generated."""
        # Create test project
        self.create_test_project()
        
        # Check that credits views.py exists
        views_file = self.project_path / "credits" / "views.py"
        self.assertTrue(views_file.exists(), "credits/views.py should exist in generated project")
        
        # Check that views.py contains required views
        views_content = views_file.read_text()
        self.assertIn("dashboard", views_content, "dashboard view should be generated")
        self.assertIn("buy_credits", views_content, "buy_credits view should be generated")

    def test_credits_migrations_template_generation(self):
        """Test that Credits migrations are correctly generated."""
        # Create test project
        self.create_test_project()
        
        # Check that credits migrations directory exists
        migrations_dir = self.project_path / "credits" / "migrations"
        self.assertTrue(migrations_dir.exists(), "credits/migrations should exist in generated project")
        
        # Check for initial migration
        initial_migration = migrations_dir / "0001_initial.py"
        self.assertTrue(initial_migration.exists(), "Initial migration should be generated")

    def test_credits_templates_generation(self):
        """Test that Credits templates are correctly generated."""
        # Create test project
        self.create_test_project()
        
        # Check that credits templates exist
        templates_dir = self.project_path / "credits" / "templates" / "credits"
        self.assertTrue(templates_dir.exists(), "credits templates should exist in generated project")
        
        # Check for dashboard template
        dashboard_template = templates_dir / "dashboard.html"
        self.assertTrue(dashboard_template.exists(), "dashboard.html template should be generated")
        
        # Check for buy_credits template
        buy_credits_template = templates_dir / "buy_credits.html"
        self.assertTrue(buy_credits_template.exists(), "buy_credits.html template should be generated")

    def test_api_middleware_template_generation(self):
        """Test that API middleware is correctly generated."""
        # Create test project
        self.create_test_project()
        
        # Check that API middleware exists
        middleware_file = self.project_path / "core" / "api_middleware.py"
        self.assertTrue(middleware_file.exists(), "core/api_middleware.py should exist in generated project")
        
        # Check that middleware contains APIKeyAuthenticationMiddleware
        middleware_content = middleware_file.read_text()
        self.assertIn("APIKeyAuthenticationMiddleware", middleware_content, 
                     "APIKeyAuthenticationMiddleware should be generated")

    def test_credits_app_registration(self):
        """Test that credits app is properly registered in settings."""
        # Create test project
        self.create_test_project()
        
        # Check that credits is in INSTALLED_APPS (using modern AppConfig format)
        settings_file = self.project_path / "core" / "settings.py"
        settings_content = settings_file.read_text()
        self.assertIn("'credits.apps.CreditsConfig'", settings_content, "credits should be in INSTALLED_APPS")

    def test_api_key_model_functionality(self):
        """Test that APIKey model has required functionality in template."""
        # Create test project
        self.create_test_project()
        
        # Check APIKey model functionality
        models_file = self.project_path / "credits" / "models.py"
        models_content = models_file.read_text()
        
        # Check for key generation method
        self.assertIn("generate_key", models_content, "APIKey should have generate_key method")
        self.assertIn("get_hashed_key", models_content, "APIKey should have get_hashed_key method")
        self.assertIn("verify_secret_key", models_content, "APIKey should have verify_secret_key method")


class TestCreditsTemplateValidation(TestCase):
    """Test validation of Credits template content for correctness."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent / 'quickscale' / 'project_templates'
        self.credits_path = self.base_path / 'credits'

    def test_credits_models_syntax_validation(self):
        """Test that generated Credits models have valid Python syntax."""
        models_file = self.credits_path / 'models.py'
        self.assertTrue(models_file.exists(), "credits/models.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        models_content = models_file.read_text()
        try:
            compile(models_content, str(models_file), 'exec')
        except SyntaxError as e:
            self.fail(f"Credits models template has syntax error: {e}")

    def test_credits_admin_syntax_validation(self):
        """Test that generated Credits admin has valid Python syntax."""
        admin_file = self.credits_path / 'admin.py'
        self.assertTrue(admin_file.exists(), "credits/admin.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        admin_content = admin_file.read_text()
        try:
            compile(admin_content, str(admin_file), 'exec')
        except SyntaxError as e:
            self.fail(f"Credits admin template has syntax error: {e}")

    def test_credits_views_syntax_validation(self):
        """Test that generated Credits views have valid Python syntax."""
        views_file = self.credits_path / 'views.py'
        self.assertTrue(views_file.exists(), "credits/views.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        views_content = views_file.read_text()
        try:
            compile(views_content, str(views_file), 'exec')
        except SyntaxError as e:
            self.fail(f"Credits views template has syntax error: {e}")

    def test_credits_templates_valid_html(self):
        """Test that Credits HTML templates are valid."""
        templates_dir = self.credits_path / 'templates' / 'credits'
        
        if templates_dir.exists():
            for template_file in templates_dir.glob('*.html'):
                content = template_file.read_text()
                # Basic HTML validation - check for Django template syntax
                self.assertTrue(
                    '{% extends' in content or '<!DOCTYPE' in content or '<html>' in content.lower(),
                    f"Template {template_file.name} should contain valid HTML or extend a base template"
                )
