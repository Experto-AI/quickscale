"""
Tests for credits templates and app structure.

These tests verify that the credits app templates have proper structure,
URL configuration, and that all necessary files exist for the credit system.
"""

import os
import unittest
import re
from pathlib import Path


class CreditsTemplateTests(unittest.TestCase):
    """Test cases for credits templates."""
    
    def setUp(self):
        """Set up test environment."""
        # Locate the template files
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'templates' / 'credits'
        self.credits_templates_path = self.credits_app_path / 'templates' / 'credits'
        
        # Template files
        self.dashboard_template = self.credits_templates_path / 'dashboard.html'
        
        # App configuration files
        self.apps_py = self.credits_app_path / 'apps.py'
        self.models_py = self.credits_app_path / 'models.py'
        self.views_py = self.credits_app_path / 'views.py'
        self.urls_py = self.credits_app_path / 'urls.py'
        self.admin_py = self.credits_app_path / 'admin.py'
        
        # Migration files
        self.migrations_path = self.credits_app_path / 'migrations'
        self.init_migration = self.migrations_path / '0001_initial.py'
        
        # Main Django settings file
        self.settings_path = self.base_path / 'quickscale' / 'templates' / 'core' / 'settings.py'
        self.main_urls_path = self.base_path / 'quickscale' / 'templates' / 'core' / 'urls.py'
    
    def test_credits_app_structure_exists(self):
        """Test that all credits app files exist."""
        self.assertTrue(self.credits_app_path.exists(), 
                       f"Credits app directory not found at {self.credits_app_path}")
        
        # Check core app files
        self.assertTrue(self.apps_py.exists(), 
                       f"apps.py not found at {self.apps_py}")
        self.assertTrue(self.models_py.exists(), 
                       f"models.py not found at {self.models_py}")
        self.assertTrue(self.views_py.exists(), 
                       f"views.py not found at {self.views_py}")
        self.assertTrue(self.urls_py.exists(), 
                       f"urls.py not found at {self.urls_py}")
        self.assertTrue(self.admin_py.exists(), 
                       f"admin.py not found at {self.admin_py}")
    
    def test_credits_templates_exist(self):
        """Test that credits templates exist."""
        self.assertTrue(self.credits_templates_path.exists(),
                       f"Credits templates directory not found at {self.credits_templates_path}")
        self.assertTrue(self.dashboard_template.exists(),
                       f"Credits dashboard template not found at {self.dashboard_template}")
    
    def test_credits_migrations_exist(self):
        """Test that credits migrations exist."""
        self.assertTrue(self.migrations_path.exists(),
                       f"Migrations directory not found at {self.migrations_path}")
        self.assertTrue(self.init_migration.exists(),
                       f"Initial migration not found at {self.init_migration}")
    
    def test_credits_app_configuration(self):
        """Test credits app configuration in apps.py."""
        with open(self.apps_py, 'r') as f:
            apps_content = f.read()
        
        self.assertIn("class CreditsConfig", apps_content,
                     "CreditsConfig class not found in apps.py")
        self.assertIn("name = 'credits'", apps_content,
                     "App name not properly configured")
        self.assertIn("verbose_name = 'Credits'", apps_content,
                     "Verbose name not properly configured")
    
    def test_credit_models_exist(self):
        """Test that credit models are defined."""
        with open(self.models_py, 'r') as f:
            models_content = f.read()
        
        # Check for CreditAccount model
        self.assertIn("class CreditAccount", models_content,
                     "CreditAccount model not found")
        
        # Check for CreditTransaction model
        self.assertIn("class CreditTransaction", models_content,
                     "CreditTransaction model not found")
        
        # Check for balance calculation method
        self.assertIn("def get_balance", models_content,
                     "get_balance method not found")
        
        # Check for add_credits method
        self.assertIn("def add_credits", models_content,
                     "add_credits method not found")
    
    def test_credit_views_exist(self):
        """Test that credit views are defined."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for credits dashboard view
        self.assertIn("def credits_dashboard", views_content,
                     "credits_dashboard view not found")
        
        # Check for balance API view
        self.assertIn("def credit_balance_api", views_content,
                     "credit_balance_api view not found")
        
        # Check for login required decorators
        self.assertIn("@login_required", views_content,
                     "login_required decorator not found")
    
    def test_credit_urls_configuration(self):
        """Test credits URL configuration."""
        with open(self.urls_py, 'r') as f:
            urls_content = f.read()
        
        # Check app name
        self.assertIn("app_name = 'credits'", urls_content,
                     "App name not configured in URLs")
        
        # Check dashboard URL
        self.assertIn("name='dashboard'", urls_content,
                     "Dashboard URL name not found")
        
        # Check balance API URL
        self.assertIn("name='balance_api'", urls_content,
                     "Balance API URL name not found")
    
    def test_credit_admin_configuration(self):
        """Test credits admin configuration."""
        with open(self.admin_py, 'r') as f:
            admin_content = f.read()
        
        # Check for admin registration
        self.assertIn("@admin.register(CreditAccount)", admin_content,
                     "CreditAccount admin registration not found")
        self.assertIn("@admin.register(CreditTransaction)", admin_content,
                     "CreditTransaction admin registration not found")
        
        # Check for admin classes
        self.assertIn("class CreditAccountAdmin", admin_content,
                     "CreditAccountAdmin class not found")
        self.assertIn("class CreditTransactionAdmin", admin_content,
                     "CreditTransactionAdmin class not found")
    
    def test_credits_app_in_settings(self):
        """Test that credits app is included in Django settings."""
        with open(self.settings_path, 'r') as f:
            settings_content = f.read()
        
        self.assertIn("'credits.apps.CreditsConfig'", settings_content,
                     "Credits app not included in INSTALLED_APPS")
    
    def test_credits_urls_in_main_urls(self):
        """Test that credits URLs are included in main URL configuration."""
        with open(self.main_urls_path, 'r') as f:
            urls_content = f.read()
        
        self.assertIn("include('credits.urls', namespace='credits')", urls_content,
                     "Credits URLs not included in main URL configuration")
    
    def test_credits_dashboard_template_structure(self):
        """Test credits dashboard template structure."""
        with open(self.dashboard_template, 'r') as f:
            template_content = f.read()
        
        # Check template extends base
        self.assertIn("{% extends", template_content,
                     "Template does not extend a base template")
        
        # Check for balance display
        self.assertIn("current_balance", template_content,
                     "Current balance not displayed in template")
        
        # Check for transactions display
        self.assertIn("recent_transactions", template_content,
                     "Recent transactions not displayed in template")
        
        # Check for credits dashboard title
        self.assertIn("Credits Dashboard", template_content,
                     "Credits Dashboard title not found")
        
        # Check for no transactions message
        self.assertIn("No transactions yet", template_content,
                     "No transactions message not found")
    
    def test_migration_structure(self):
        """Test initial migration structure."""
        with open(self.init_migration, 'r') as f:
            migration_content = f.read()
        
        # Check for CreditAccount model creation
        self.assertIn("'CreditAccount'", migration_content,
                     "CreditAccount model not found in migration")
        
        # Check for CreditTransaction model creation
        self.assertIn("'CreditTransaction'", migration_content,
                     "CreditTransaction model not found in migration")
        
        # Check for user foreign key
        self.assertIn("settings.AUTH_USER_MODEL", migration_content,
                     "User foreign key not properly configured")
        
        # Check for indexes
        self.assertIn("AddIndex", migration_content,
                     "Database indexes not found in migration")


class CreditsIntegrationTests(unittest.TestCase):
    """Integration tests for credits system structure."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.credits_app_path = self.base_path / 'quickscale' / 'templates' / 'credits'
        self.dashboard_app_path = self.base_path / 'quickscale' / 'templates' / 'dashboard'
    
    def test_dashboard_integration_with_credits(self):
        """Test that dashboard views integrate with credits."""
        dashboard_views_path = self.dashboard_app_path / 'views.py'
        
        with open(dashboard_views_path, 'r') as f:
            views_content = f.read()
        
        # Check for credits import
        self.assertIn("from credits.models import CreditAccount", views_content,
                     "Credits models not imported in dashboard views")
        
        # Check for user dashboard view
        self.assertIn("def user_dashboard", views_content,
                     "User dashboard view not found")
        
        # Check for credit account creation
        self.assertIn("CreditAccount.get_or_create_for_user", views_content,
                     "Credit account creation not found in user dashboard")
    
    def test_dashboard_urls_include_user_dashboard(self):
        """Test that dashboard URLs include user dashboard."""
        dashboard_urls_path = self.dashboard_app_path / 'urls.py'
        
        with open(dashboard_urls_path, 'r') as f:
            urls_content = f.read()
        
        self.assertIn("name='user_dashboard'", urls_content,
                     "User dashboard URL not found")
    
    def test_user_dashboard_template_exists(self):
        """Test that user dashboard template exists."""
        user_dashboard_template = (self.base_path / 'quickscale' / 'templates' / 
                                 'templates' / 'dashboard' / 'user_dashboard.html')
        
        self.assertTrue(user_dashboard_template.exists(),
                       f"User dashboard template not found at {user_dashboard_template}")
        
        with open(user_dashboard_template, 'r') as f:
            template_content = f.read()
        
        # Check for credits section
        self.assertIn("Credits", template_content,
                     "Credits section not found in user dashboard template")
        
        # Check for balance display
        self.assertIn("current_balance", template_content,
                     "Current balance not displayed in user dashboard")
        
        # Check for credits dashboard link
        self.assertIn("credits:dashboard", template_content,
                     "Link to credits dashboard not found")


if __name__ == '__main__':
    unittest.main() 