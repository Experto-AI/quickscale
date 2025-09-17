"""Tests for User authentication template generation in QuickScale projects.

This test validates that QuickScale generates working user authentication templates
including models, views, forms, and security features.
"""

from pathlib import Path

from django.test import TestCase

from tests.utils import DynamicProjectTestCase


class TestUserTemplateGeneration(DynamicProjectTestCase):
    """Test that QuickScale generates working User authentication templates."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.project_name = "test_user_project"

    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()

    def test_user_models_template_generation(self):
        """Test that User models are correctly generated in project templates."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that users models.py exists
        models_file = self.project_path / "users" / "models.py"
        self.assertTrue(models_file.exists(), "users/models.py should exist in generated project")
        
        # Check that models.py contains User model
        models_content = models_file.read_text()
        self.assertIn("class CustomUser", models_content, "CustomUser model should be generated")
        self.assertIn("AbstractUser", models_content, "User should extend AbstractUser")
        self.assertIn("email", models_content, "User should have email field")

    def test_user_forms_template_generation(self):
        """Test that User forms are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that users forms.py exists
        forms_file = self.project_path / "users" / "forms.py"
        self.assertTrue(forms_file.exists(), "users/forms.py should exist in generated project")
        
        # Check that forms.py contains required forms
        forms_content = forms_file.read_text()
        self.assertIn("CustomSignupForm", forms_content, "CustomSignupForm should be generated")

    def test_user_views_template_generation(self):
        """Test that User views are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that users views.py exists
        views_file = self.project_path / "users" / "views.py"
        self.assertTrue(views_file.exists(), "users/views.py should exist in generated project")
        
        # Check that views.py contains required views
        views_content = views_file.read_text()
        self.assertIn("profile", views_content, "profile view should be generated")

    def test_user_urls_template_generation(self):
        """Test that User URLs are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that users urls.py exists
        urls_file = self.project_path / "users" / "urls.py"
        self.assertTrue(urls_file.exists(), "users/urls.py should exist in generated project")
        
        # Check that urls.py contains required patterns
        urls_content = urls_file.read_text()
        self.assertIn("profile", urls_content, "profile URL should be generated")

    def test_user_admin_template_generation(self):
        """Test that User admin interface is correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that users admin.py exists
        admin_file = self.project_path / "users" / "admin.py"
        self.assertTrue(admin_file.exists(), "users/admin.py should exist in generated project")
        
        # Check that admin.py contains UserAdmin
        admin_content = admin_file.read_text()
        self.assertIn("UserAdmin", admin_content, "UserAdmin should be generated")

    def test_user_migrations_template_generation(self):
        """Test that User migrations are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that users migrations directory exists
        migrations_dir = self.project_path / "users" / "migrations"
        self.assertTrue(migrations_dir.exists(), "users/migrations should exist in generated project")
        
        # Check for initial migration
        initial_migration = migrations_dir / "0001_initial.py"
        self.assertTrue(initial_migration.exists(), "Initial migration should be generated")

    def test_user_templates_generation(self):
        """Test that User templates are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that user templates exist in main templates directory
        templates_dir = self.project_path / "templates" / "users"
        self.assertTrue(templates_dir.exists(), "users templates should exist in generated project")
        
        # Check for profile template
        profile_template = templates_dir / "profile.html"
        self.assertTrue(profile_template.exists(), "profile.html template should be generated")

    def test_auth_templates_generation(self):
        """Test that authentication templates are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that account templates exist
        account_templates_dir = self.project_path / "templates" / "account"
        self.assertTrue(account_templates_dir.exists(), "account templates should exist in generated project")
        
        # Check for login template
        login_template = account_templates_dir / "login.html"
        self.assertTrue(login_template.exists(), "login.html template should be generated")
        
        # Check for signup template
        signup_template = account_templates_dir / "signup.html"
        self.assertTrue(signup_template.exists(), "signup.html template should be generated")

    def test_user_middleware_generation(self):
        """Test that user security middleware is correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that users middleware.py exists
        middleware_file = self.project_path / "users" / "middleware.py"
        self.assertTrue(middleware_file.exists(), "users/middleware.py should exist in generated project")
        
        # Check that middleware contains security features
        middleware_content = middleware_file.read_text()
        self.assertIn("AccountLockoutMiddleware", middleware_content, "Account lockout middleware should be generated")

    def test_user_management_commands_generation(self):
        """Test that user management commands are correctly generated."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that management commands directory exists
        commands_dir = self.project_path / "users" / "management" / "commands"
        self.assertTrue(commands_dir.exists(), "users management commands should exist in generated project")
        
        # Check for create_default_users command
        create_users_cmd = commands_dir / "create_default_users.py"
        self.assertTrue(create_users_cmd.exists(), "create_default_users command should be generated")

    def test_user_app_registration(self):
        """Test that users app is properly registered in settings."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that users is in INSTALLED_APPS (using modern AppConfig format)
        settings_file = self.project_path / "core" / "settings.py"
        settings_content = settings_file.read_text()
        self.assertIn("'users.apps.UsersConfig'", settings_content, "users should be in INSTALLED_APPS")
        
        # Check that AUTH_USER_MODEL is set
        self.assertIn("AUTH_USER_MODEL", settings_content, "AUTH_USER_MODEL should be configured")
        self.assertIn("users.CustomUser", settings_content, "AUTH_USER_MODEL should point to users.CustomUser")

    def test_allauth_configuration(self):
        """Test that django-allauth is properly configured."""
        # Create test project
        self.project_path = self.create_test_project(self.project_name)
        
        # Check that allauth is configured in settings
        settings_file = self.project_path / "core" / "settings.py"
        settings_content = settings_file.read_text()
        self.assertIn("'allauth'", settings_content, "allauth should be in INSTALLED_APPS")
        self.assertIn("'allauth.account'", settings_content, "allauth.account should be in INSTALLED_APPS")


class TestUserTemplateValidation(TestCase):
    """Test validation of User template content for correctness."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent.parent / 'quickscale' / 'project_templates'
        self.users_path = self.base_path / 'users'

    def test_user_models_syntax_validation(self):
        """Test that generated User models have valid Python syntax."""
        models_file = self.users_path / 'models.py'
        self.assertTrue(models_file.exists(), "users/models.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        models_content = models_file.read_text()
        try:
            compile(models_content, str(models_file), 'exec')
        except SyntaxError as e:
            self.fail(f"User models template has syntax error: {e}")

    def test_user_forms_syntax_validation(self):
        """Test that generated User forms have valid Python syntax."""
        forms_file = self.users_path / 'forms.py'
        self.assertTrue(forms_file.exists(), "users/forms.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        forms_content = forms_file.read_text()
        try:
            compile(forms_content, str(forms_file), 'exec')
        except SyntaxError as e:
            self.fail(f"User forms template has syntax error: {e}")

    def test_user_views_syntax_validation(self):
        """Test that generated User views have valid Python syntax."""
        views_file = self.users_path / 'views.py'
        self.assertTrue(views_file.exists(), "users/views.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        views_content = views_file.read_text()
        try:
            compile(views_content, str(views_file), 'exec')
        except SyntaxError as e:
            self.fail(f"User views template has syntax error: {e}")

    def test_user_admin_syntax_validation(self):
        """Test that generated User admin has valid Python syntax."""
        admin_file = self.users_path / 'admin.py'
        self.assertTrue(admin_file.exists(), "users/admin.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        admin_content = admin_file.read_text()
        try:
            compile(admin_content, str(admin_file), 'exec')
        except SyntaxError as e:
            self.fail(f"User admin template has syntax error: {e}")

    def test_user_middleware_syntax_validation(self):
        """Test that generated User middleware has valid Python syntax."""
        middleware_file = self.users_path / 'middleware.py'
        self.assertTrue(middleware_file.exists(), "users/middleware.py template should exist")
        
        # Check that the file can be compiled (basic syntax check)
        middleware_content = middleware_file.read_text()
        try:
            compile(middleware_content, str(middleware_file), 'exec')
        except SyntaxError as e:
            self.fail(f"User middleware template has syntax error: {e}")

    def test_user_templates_valid_html(self):
        """Test that User HTML templates are valid."""
        templates_dir = self.base_path / 'templates' / 'users'
        
        if templates_dir.exists():
            for template_file in templates_dir.glob('*.html'):
                content = template_file.read_text()
                # Skip partial templates and form templates (they don't need full HTML structure)
                if 'partial' in template_file.name.lower() or 'form' in template_file.name.lower():
                    continue
                # Basic HTML validation - check for Django template syntax
                self.assertTrue(
                    '{% extends' in content or '<!DOCTYPE' in content or '<html>' in content.lower(),
                    f"Template {template_file.name} should contain valid HTML or extend a base template"
                )
