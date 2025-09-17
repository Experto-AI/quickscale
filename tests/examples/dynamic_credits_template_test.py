"""
Example: Dynamic Credits Template Tests

This is a demonstration of how to migrate from static fixture-based testing
to dynamic project generation. Instead of testing against static template files,
this test generates a real QuickScale project and validates the templates
against the current, live template generation system.

This approach ensures:
1. Tests always validate current template state
2. No static fixtures that can become outdated
3. Real-world testing of the actual generation process
4. Automatic cleanup and isolation
"""

import unittest

from tests.utils import DynamicTemplateTestCase


class DynamicCreditsTemplateTests(DynamicTemplateTestCase):
    """Test cases for credits templates using dynamic project generation."""
    
    def test_dynamic_credits_app_structure_exists(self):
        """Test that all credits app files exist in generated project."""
        credits_app_path = self.get_app_path('credits')
        
        # Check that the credits app directory exists
        self.assertFileExists(credits_app_path, "Credits app directory should exist")
        
        # Check core app files
        core_files = ['apps.py', 'models.py', 'views.py', 'urls.py', 'admin.py']
        for file_name in core_files:
            file_path = credits_app_path / file_name
            self.assertFileExists(file_path, f"Credits {file_name} should exist")
        
        # Check migrations directory
        migrations_path = credits_app_path / 'migrations'
        self.assertFileExists(migrations_path, "Credits migrations directory should exist")
        
        # Check init migration exists
        init_migration = migrations_path / '0001_initial.py'
        self.assertFileExists(init_migration, "Credits initial migration should exist")
    
    def test_credits_models_configuration(self):
        """Test credits models are properly configured."""
        models_py = self.get_app_path('credits') / 'models.py'
        
        # Check for key model classes
        self.assertFileContains(models_py, "class CreditAccount", 
                              "CreditAccount model should be defined")
        self.assertFileContains(models_py, "class CreditTransaction", 
                              "CreditTransaction model should be defined")
        
        # Check for proper Django imports
        self.assertFileContains(models_py, "from django.db import models",
                              "Django models should be imported")
        self.assertFileContains(models_py, "from django.contrib.auth import get_user_model",
                              "User model should be imported")
    
    def test_dynamic_credits_admin_configuration(self):
        """Test credits admin configuration in dynamic template context."""
        admin_py = self.get_app_path('credits') / 'admin.py'
        
        # Check for admin registration
        self.assertFileContains(admin_py, "@admin.register(CreditAccount)",
                              "CreditAccount admin registration should exist")
        self.assertFileContains(admin_py, "@admin.register(CreditTransaction)",
                              "CreditTransaction admin registration should exist")
    
    def test_dynamic_credits_urls_configuration(self):
        """Test credits URL configuration in dynamic template context."""
        urls_py = self.get_app_path('credits') / 'urls.py'
        
        # Check for URL patterns
        self.assertFileContains(urls_py, "urlpatterns",
                              "URL patterns should be defined")
        self.assertFileContains(urls_py, "path('balance/', views.balance_view, name='balance')",
                              "Balance URL should be configured")
    
    def test_credits_views_configuration(self):
        """Test credits views configuration."""
        views_py = self.get_app_path('credits') / 'views.py'
        
        # Check for view functions
        self.assertFileContains(views_py, "def balance_view",
                              "Balance view should be defined")
        
        # Check for proper Django imports
        self.assertFileContains(views_py, "from django.shortcuts import render",
                              "Django render should be imported")
    
    def test_dynamic_credits_templates_exist(self):
        """Test that credits templates are properly generated."""
        credits_templates_path = self.get_app_path('credits') / 'templates' / 'credits'
        
        # Check templates directory exists
        self.assertFileExists(credits_templates_path, 
                            "Credits templates directory should exist")
        
        # Check for dashboard template
        dashboard_template = credits_templates_path / 'dashboard.html'
        self.assertFileExists(dashboard_template,
                            "Credits dashboard template should exist")
        
        # Check template content
        self.assertFileContains(dashboard_template, "{% extends",
                              "Template should extend base template")
    
    def test_dynamic_credits_app_configuration(self):
        """Test credits app configuration."""
        apps_py = self.get_app_path('credits') / 'apps.py'
        
        # Check app config class
        self.assertFileContains(apps_py, "class CreditsConfig",
                              "CreditsConfig class should be defined")
        self.assertFileContains(apps_py, "default_auto_field = 'django.db.models.BigAutoField'",
                              "Auto field should be configured")
    
    def test_credits_integration_with_main_project(self):
        """Test that credits app is properly integrated with main project."""
        # Check that credits is included in main settings
        settings_py = self.project_dir / 'core' / 'settings.py'
        self.assertFileExists(settings_py, "Main settings file should exist")
        self.assertFileContains(settings_py, "'credits'",
                              "Credits app should be in INSTALLED_APPS")
        
        # Check that credits URLs are included in main URLs
        main_urls_py = self.project_dir / 'core' / 'urls.py'
        self.assertFileExists(main_urls_py, "Main URLs file should exist")
        self.assertFileContains(main_urls_py, "path('credits/', include('credits.urls'))",
                              "Credits URLs should be included in main URL config")


if __name__ == '__main__':
    unittest.main()
