"""Tests for Stripe template generation in QuickScale projects.

This test validates that QuickScale generates working Stripe integration templates
including models, admin interface, and views.
"""

from pathlib import Path

from django.test import TestCase

from tests.utils import DynamicProjectTestCase


class TestStripeTemplateGeneration(DynamicProjectTestCase):
    """Test that QuickScale generates working Stripe integration templates."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.project_name = "test_stripe_project"

    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()

    def test_stripe_models_template_generation(self):
        """Test that Stripe models are correctly generated in project templates."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that stripe_manager models.py exists
        models_file = self.project_path / "stripe_manager" / "models.py"
        self.assertTrue(models_file.exists(), "stripe_manager/models.py should exist in generated project")
        
        # Check that models.py contains StripeProduct class
        models_content = models_file.read_text()
        self.assertIn("class StripeProduct", models_content, "StripeProduct model should be generated")
        self.assertIn("class StripeCustomer", models_content, "StripeCustomer model should be generated")
        
        # Check required fields in StripeProduct model
        self.assertIn("name = models.CharField", models_content)
        self.assertIn("price = models.DecimalField", models_content)
        self.assertIn("currency = models.CharField", models_content)
        self.assertIn("stripe_id = models.CharField", models_content)
        self.assertIn("active = models.BooleanField", models_content)

    def test_stripe_admin_template_generation(self):
        """Test that Stripe admin interface is correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that stripe_manager admin.py exists
        admin_file = self.project_path / "stripe_manager" / "admin.py"
        self.assertTrue(admin_file.exists(), "stripe_manager/admin.py should exist in generated project")
        
        # Check that admin.py contains StripeProduct admin
        admin_content = admin_file.read_text()
        self.assertIn("StripeProductAdmin", admin_content, "StripeProductAdmin should be generated")
        self.assertIn("@admin.register", admin_content, "Admin registration should be generated using modern decorator approach")

    def test_stripe_urls_template_generation(self):
        """Test that Stripe URLs are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that stripe_manager urls.py exists
        urls_file = self.project_path / "stripe_manager" / "urls.py"
        self.assertTrue(urls_file.exists(), "stripe_manager/urls.py should exist in generated project")
        
        # Check that urls.py contains plan_comparison pattern
        urls_content = urls_file.read_text()
        self.assertIn("plan_comparison", urls_content, "plan_comparison URL should be generated")
        
    def test_stripe_views_template_generation(self):
        """Test that Stripe views are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that stripe_manager views.py exists
        views_file = self.project_path / "stripe_manager" / "views.py"
        self.assertTrue(views_file.exists(), "stripe_manager/views.py should exist in generated project")
        
        # Check that views.py contains plan comparison view
        views_content = views_file.read_text()
        self.assertIn("plan_comparison", views_content, "plan_comparison view should be generated")

    def test_stripe_migrations_template_generation(self):
        """Test that Stripe migrations are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that stripe_manager migrations directory exists
        migrations_dir = self.project_path / "stripe_manager" / "migrations"
        self.assertTrue(migrations_dir.exists(), "stripe_manager/migrations should exist in generated project")
        
        # Check for initial migration
        initial_migration = migrations_dir / "0001_initial.py"
        self.assertTrue(initial_migration.exists(), "Initial migration should be generated")

    def test_stripe_templates_generation(self):
        """Test that Stripe templates are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that stripe_manager templates exist
        templates_dir = self.project_path / "stripe_manager" / "templates" / "stripe_manager"
        self.assertTrue(templates_dir.exists(), "stripe_manager templates should exist in generated project")
        
        # Check for plan comparison template
        plan_template = templates_dir / "plan_comparison.html"
        self.assertTrue(plan_template.exists(), "plan_comparison.html template should be generated")
        
        # Check for checkout templates
        checkout_success = templates_dir / "checkout_success.html"
        checkout_error = templates_dir / "checkout_error.html"
        self.assertTrue(checkout_success.exists(), "checkout_success.html template should be generated")
        self.assertTrue(checkout_error.exists(), "checkout_error.html template should be generated")

    def test_stripe_app_registration(self):
        """Test that stripe_manager app is properly registered in settings."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that stripe_manager is in INSTALLED_APPS (using modern AppConfig format)
        settings_file = self.project_path / "core" / "settings.py"
        settings_content = settings_file.read_text()
        self.assertIn("'stripe_manager.apps.StripeConfig'", settings_content, "stripe_manager should be in INSTALLED_APPS")

    def test_stripe_url_inclusion(self):
        """Test that stripe_manager URLs are included in main URL config."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that stripe URLs are included in main urls.py
        main_urls_file = self.project_path / "core" / "urls.py"
        main_urls_content = main_urls_file.read_text()
        self.assertIn("stripe_manager.urls", main_urls_content, "stripe_manager URLs should be included")


class TestStripeTemplateValidation(TestCase):
    """Test validation of Stripe template content for correctness."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent.parent / 'quickscale' / 'project_templates'
        self.stripe_manager_path = self.base_path / 'stripe_manager'

    def test_stripe_models_syntax_validation(self):
        """Test that generated Stripe models have valid Python syntax."""
        models_file = self.stripe_manager_path / 'models.py'
        self.assertTrue(models_file.exists(), "stripe_manager/models.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        models_content = models_file.read_text()
        try:
            compile(models_content, str(models_file), 'exec')
        except SyntaxError as e:
            self.fail(f"Stripe models template has syntax error: {e}")

    def test_stripe_admin_syntax_validation(self):
        """Test that generated Stripe admin has valid Python syntax."""
        admin_file = self.stripe_manager_path / 'admin.py'
        self.assertTrue(admin_file.exists(), "stripe_manager/admin.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        admin_content = admin_file.read_text()
        try:
            compile(admin_content, str(admin_file), 'exec')
        except SyntaxError as e:
            self.fail(f"Stripe admin template has syntax error: {e}")

    def test_stripe_views_syntax_validation(self):
        """Test that generated Stripe views have valid Python syntax."""
        views_file = self.stripe_manager_path / 'views.py'
        self.assertTrue(views_file.exists(), "stripe_manager/views.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        views_content = views_file.read_text()
        try:
            compile(views_content, str(views_file), 'exec')
        except SyntaxError as e:
            self.fail(f"Stripe views template has syntax error: {e}")

    def test_stripe_urls_syntax_validation(self):
        """Test that generated Stripe URLs have valid Python syntax."""
        urls_file = self.stripe_manager_path / 'urls.py'
        self.assertTrue(urls_file.exists(), "stripe_manager/urls.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        urls_content = urls_file.read_text()
        try:
            compile(urls_content, str(urls_file), 'exec')
        except SyntaxError as e:
            self.fail(f"Stripe URLs template has syntax error: {e}")

    def test_stripe_templates_valid_html(self):
        """Test that Stripe HTML templates are valid."""
        templates_dir = self.stripe_manager_path / 'templates' / 'stripe_manager'
        
        if templates_dir.exists():
            for template_file in templates_dir.glob('*.html'):
                content = template_file.read_text()
                # Basic HTML validation - check for balanced tags or extends base template
                has_html_tag = '<html>' in content.lower()
                extends_base = 'extends' in content.lower() and 'base' in content.lower()
                self.assertTrue(has_html_tag or extends_base, 
                             f"Template {template_file.name} should contain <html> or extend a base template")
