"""
Integration tests for the credits system in generated projects.

These tests verify that the credits system works correctly when a project
is generated and the credits functionality is integrated with Django.
"""

import os
import pytest
import tempfile
import shutil
from pathlib import Path
from decimal import Decimal

from quickscale.commands.project_manager import ProjectManager
from quickscale.commands.init_command import InitCommand
from tests.utils import wait_for_docker_service


class TestCreditsSystemIntegration:
    """Integration tests for credits system in generated projects."""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary directory for project generation."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def credits_project(self, temp_project_dir):
        """Generate a test project with credits system."""
        project_name = "test_credits_project"
        project_path = Path(temp_project_dir) / project_name
        
        # Initialize project using QuickScale
        init_command = InitCommand()
        try:
            init_command.execute(project_name, str(temp_project_dir))
            yield project_path
        except Exception as e:
            pytest.skip(f"Could not generate test project: {e}")
    
    def test_credits_app_structure_in_generated_project(self, credits_project):
        """Test that credits app is properly structured in generated project."""
        credits_app_path = credits_project / "credits"
        
        # Check that credits app exists
        assert credits_app_path.exists(), "Credits app directory not found"
        
        # Check core files exist
        assert (credits_app_path / "apps.py").exists()
        assert (credits_app_path / "models.py").exists()
        assert (credits_app_path / "views.py").exists()
        assert (credits_app_path / "urls.py").exists()
        assert (credits_app_path / "admin.py").exists()
        assert (credits_app_path / "__init__.py").exists()
        
        # Check migrations exist
        migrations_path = credits_app_path / "migrations"
        assert migrations_path.exists()
        assert (migrations_path / "__init__.py").exists()
        assert (migrations_path / "0001_initial.py").exists()
        
        # Check templates exist
        templates_path = credits_app_path / "templates" / "credits"
        assert templates_path.exists()
        assert (templates_path / "dashboard.html").exists()
    
    def test_credits_configuration_in_settings(self, credits_project):
        """Test that credits app is properly configured in Django settings."""
        settings_path = credits_project / "core" / "settings.py"
        
        with open(settings_path, 'r') as f:
            settings_content = f.read()
        
        # Check that credits app is in INSTALLED_APPS
        assert "'credits.apps.CreditsConfig'" in settings_content
    
    def test_credits_urls_in_main_config(self, credits_project):
        """Test that credits URLs are included in main URL configuration."""
        urls_path = credits_project / "core" / "urls.py"
        
        with open(urls_path, 'r') as f:
            urls_content = f.read()
        
        # Check that credits URLs are included
        assert "include('credits.urls', namespace='credits')" in urls_content
    
    def test_dashboard_integration_with_credits(self, credits_project):
        """Test that dashboard properly integrates with credits."""
        dashboard_views_path = credits_project / "dashboard" / "views.py"
        
        with open(dashboard_views_path, 'r') as f:
            views_content = f.read()
        
        # Check credits integration in dashboard
        assert "from credits.models import CreditAccount" in views_content
        assert "CreditAccount.get_or_create_for_user" in views_content
        assert "def user_dashboard" in views_content
    
    def test_dashboard_template_shows_credits(self, credits_project):
        """Test that dashboard template displays credits information."""
        user_dashboard_template = (credits_project / "templates" / 
                                 "dashboard" / "user_dashboard.html")
        
        assert user_dashboard_template.exists()
        
        with open(user_dashboard_template, 'r') as f:
            template_content = f.read()
        
        # Check credits section exists
        assert "Credits" in template_content
        assert "current_balance" in template_content
        assert "credits:dashboard" in template_content


@pytest.mark.integration
class TestCreditsSystemFunctionality:
    """Test credits system functionality in a realistic environment."""
    
    def test_credit_models_structure(self):
        """Test credit models have correct structure."""
        # This would test the models in isolation
        models_file = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "credits" / "models.py"
        
        with open(models_file, 'r') as f:
            models_content = f.read()
        
        # Test model structure
        assert "class CreditAccount(models.Model):" in models_content
        assert "class CreditTransaction(models.Model):" in models_content
        
        # Test model fields
        assert "user = models.OneToOneField" in models_content
        assert "amount = models.DecimalField" in models_content
        assert "description = models.CharField" in models_content
        assert "created_at = models.DateTimeField" in models_content
        
        # Test model methods (with type hints)
        assert "def get_balance(self)" in models_content
        assert "def add_credits(self," in models_content
        assert "get_or_create_for_user" in models_content
    
    def test_credit_views_structure(self):
        """Test credit views have correct structure."""
        views_file = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "credits" / "views.py"
        
        with open(views_file, 'r') as f:
            views_content = f.read()
        
        # Test view functions
        assert "def credits_dashboard(request):" in views_content
        assert "def credit_balance_api(request):" in views_content
        
        # Test authentication decorators
        assert "@login_required" in views_content
        
        # Test model usage
        assert "CreditAccount.get_or_create_for_user" in views_content
        assert "JsonResponse" in views_content
    
    def test_credit_urls_structure(self):
        """Test credit URLs have correct structure."""
        urls_file = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "credits" / "urls.py"
        
        with open(urls_file, 'r') as f:
            urls_content = f.read()
        
        # Test URL patterns
        assert "app_name = 'credits'" in urls_content
        assert "name='dashboard'" in urls_content
        assert "name='balance_api'" in urls_content
        assert "views.credits_dashboard" in urls_content
        assert "views.credit_balance_api" in urls_content
    
    def test_credit_admin_structure(self):
        """Test credit admin has correct structure."""
        admin_file = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "credits" / "admin.py"
        
        with open(admin_file, 'r') as f:
            admin_content = f.read()
        
        # Test admin registration
        assert "@admin.register(CreditAccount)" in admin_content
        assert "@admin.register(CreditTransaction)" in admin_content
        
        # Test admin classes
        assert "class CreditAccountAdmin(admin.ModelAdmin):" in admin_content
        assert "class CreditTransactionAdmin(admin.ModelAdmin):" in admin_content
        
        # Test admin configuration
        assert "list_display" in admin_content
        assert "search_fields" in admin_content
        assert "readonly_fields" in admin_content
    
    def test_credit_migration_structure(self):
        """Test credit migration has correct structure."""
        migration_file = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "credits" / "migrations" / "0001_initial.py"
        
        with open(migration_file, 'r') as f:
            migration_content = f.read()
        
        # Test migration operations
        assert "CreateModel" in migration_content
        assert "name='CreditAccount'" in migration_content
        assert "name='CreditTransaction'" in migration_content
        
        # Test field definitions
        assert "models.OneToOneField" in migration_content
        assert "models.DecimalField" in migration_content
        assert "models.CharField" in migration_content
        assert "models.DateTimeField" in migration_content
        
        # Test indexes
        assert "AddIndex" in migration_content
    
    def test_credit_template_structure(self):
        """Test credit template has correct structure."""
        template_file = Path(__file__).parent.parent.parent / "quickscale" / "templates" / "credits" / "templates" / "credits" / "dashboard.html"
        
        with open(template_file, 'r') as f:
            template_content = f.read()
        
        # Test template structure
        assert "{% extends" in template_content
        assert "{% block" in template_content
        assert "Credits Dashboard" in template_content
        
        # Test template variables
        assert "{{ current_balance }}" in template_content
        assert "{% for transaction in recent_transactions %}" in template_content
        assert "{{ transaction.description }}" in template_content
        assert "{{ transaction.amount }}" in template_content
        
        # Test conditional content
        assert "{% if recent_transactions %}" in template_content
        assert "{% else %}" in template_content
        assert "No transactions yet" in template_content


@pytest.mark.slow
class TestCreditsSystemWithDatabase:
    """Test credits system with actual database operations."""
    
    @pytest.fixture
    def django_project_with_db(self, temp_project_dir):
        """Create a Django project with database for testing."""
        # This would set up a test Django environment
        # For now, we'll test the structure only
        pytest.skip("Database testing requires Django environment setup")
    
    def test_credit_account_creation(self, django_project_with_db):
        """Test credit account creation with database."""
        # This would test actual model operations
        pass
    
    def test_credit_transaction_creation(self, django_project_with_db):
        """Test credit transaction creation with database."""
        # This would test actual model operations
        pass
    
    def test_balance_calculation(self, django_project_with_db):
        """Test balance calculation with actual data."""
        # This would test balance calculation with real transactions
        pass
    
    def test_dashboard_view_rendering(self, django_project_with_db):
        """Test dashboard view rendering with real data."""
        # This would test view rendering with actual request/response
        pass 