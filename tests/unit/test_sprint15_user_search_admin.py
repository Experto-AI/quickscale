"""
Tests for Sprint 15: Basic User Search & Admin Foundation.

These tests verify the functionality added in Sprint 15:
- User search functionality (email, name) with pagination
- User detail view with comprehensive info
- Admin navigation structure
- Permission control (staff-only access)

Tests the QuickScale project generator template functionality, not Django-generated project.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import os

from tests.utils import ProjectTestMixin, create_test_project_structure


class TestSprint15UserSearchTemplates(unittest.TestCase):
    """Test Sprint 15 user search template generation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.project_name = "test_sprint15_project"
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_admin_dashboard_views_template_contains_user_search(self):
        """Test that admin_dashboard views template contains user search functionality."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Check that the template file exists
        self.assertTrue(views_template_path.exists(), "Admin dashboard views template should exist")
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for user search function
        self.assertIn("def user_search(", content, "Should contain user_search function")
        self.assertIn("@user_passes_test(lambda u: u.is_staff)", content, "Should have staff permission decorator")
        
        # Check for search functionality
        self.assertIn("Q(email__icontains=query)", content, "Should search by email")
        self.assertIn("Q(first_name__icontains=query)", content, "Should search by first name")
        self.assertIn("Q(last_name__icontains=query)", content, "Should search by last name")
        
        # Check for pagination
        self.assertIn("Paginator(users, 20)", content, "Should include pagination with 20 items per page")
    
    def test_admin_dashboard_views_template_contains_user_detail(self):
        """Test that admin_dashboard views template contains user detail functionality."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for user detail function
        self.assertIn("def user_detail(", content, "Should contain user_detail function")
        self.assertIn("@user_passes_test(lambda u: u.is_staff)", content, "Should have staff permission decorator")
        
        # Check for comprehensive user information
        self.assertIn("get_object_or_404(CustomUser, id=user_id)", content, "Should get user by ID")
        self.assertIn("credit_account", content, "Should get credit account info")
        self.assertIn("subscription", content, "Should get subscription info")
        self.assertIn("recent_transactions", content, "Should get recent transactions")
        self.assertIn("recent_payments", content, "Should get recent payments")
        self.assertIn("recent_service_usage", content, "Should get recent service usage")
    
    def test_admin_dashboard_urls_template_contains_user_management_routes(self):
        """Test that admin_dashboard URLs template contains user management routes."""
        # Get the path to the admin_dashboard URLs template
        urls_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "urls.py"
        
        # Check that the template file exists
        self.assertTrue(urls_template_path.exists(), "Admin dashboard URLs template should exist")
        
        # Read the template content
        with open(urls_template_path, 'r') as f:
            content = f.read()
        
        # Check for user management URLs
        self.assertIn("path('users/search/', views.user_search, name='user_search')", content, 
                     "Should contain user search URL")
        self.assertIn("path('users/<int:user_id>/', views.user_detail, name='user_detail')", content,
                     "Should contain user detail URL")
    
    def test_user_search_template_structure(self):
        """Test that user search template has proper structure."""
        # Get the path to the user search template
        template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "templates" / "admin_dashboard" / "user_search.html"
        
        # Check that the template file exists (if it does, test its content)
        if template_path.exists():
            with open(template_path, 'r') as f:
                content = f.read()
            
            # Check for basic template structure
            self.assertIn("{% extends", content, "Should extend a base template")
            self.assertIn("{% block", content, "Should use template blocks")
            
            # Check for search form
            self.assertIn("form", content.lower(), "Should contain a search form")
            self.assertIn("input", content.lower(), "Should contain input field")
    
    def test_user_detail_template_structure(self):
        """Test that user detail template has proper structure."""
        # Get the path to the user detail template
        template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "templates" / "admin_dashboard" / "user_detail.html"
        
        # Check that the template file exists (if it does, test its content)
        if template_path.exists():
            with open(template_path, 'r') as f:
                content = f.read()
            
            # Check for basic template structure
            self.assertIn("{% extends", content, "Should extend a base template")
            self.assertIn("{% block", content, "Should use template blocks")
            
            # Check for user information display
            self.assertIn("selected_user", content, "Should display selected user info")


class TestSprint15PermissionControls(unittest.TestCase):
    """Test Sprint 15 permission control implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_admin_views_have_staff_permission_decorators(self):
        """Test that admin views have proper staff permission decorators."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Find user_search function and check it has permission decorator
        lines = content.split('\n')
        user_search_line = None
        for i, line in enumerate(lines):
            if "def user_search(" in line:
                user_search_line = i
                break
        
        self.assertIsNotNone(user_search_line, "user_search function should exist")
        
        # Check that permission decorator exists before the function
        permission_found = False
        for i in range(max(0, user_search_line - 5), user_search_line):
            if "@user_passes_test(lambda u: u.is_staff)" in lines[i]:
                permission_found = True
                break
        
        self.assertTrue(permission_found, "user_search should have staff permission decorator")
        
        # Find user_detail function and check it has permission decorator
        user_detail_line = None
        for i, line in enumerate(lines):
            if "def user_detail(" in line:
                user_detail_line = i
                break
        
        self.assertIsNotNone(user_detail_line, "user_detail function should exist")
        
        # Check that permission decorator exists before the function
        permission_found = False
        for i in range(max(0, user_detail_line - 5), user_detail_line):
            if "@user_passes_test(lambda u: u.is_staff)" in lines[i]:
                permission_found = True
                break
        
        self.assertTrue(permission_found, "user_detail should have staff permission decorator")
    
    def test_login_required_decorators_present(self):
        """Test that login required decorators are present."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for login_required import
        self.assertIn("from django.contrib.auth.decorators import login_required", content,
                     "Should import login_required decorator")
        
        # Check that user management functions have login_required decorator
        self.assertIn("@login_required", content, "Should use login_required decorator")


class TestSprint15SearchFunctionality(unittest.TestCase):
    """Test Sprint 15 search functionality implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_search_query_implementation(self):
        """Test that search query implementation is correct."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for proper Django Q object usage
        self.assertIn("from django.db.models import Q", content, "Should import Q for complex queries")
        
        # Check for search implementation
        self.assertIn("CustomUser.objects.filter(", content, "Should filter CustomUser objects")
        self.assertIn("icontains", content, "Should use case-insensitive search")
        
        # Check for full name search support
        self.assertIn("query_parts = query.split()", content, "Should split query for full name search")
    
    def test_pagination_implementation(self):
        """Test that pagination implementation is correct."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for pagination import and usage
        self.assertIn("from django.core.paginator import Paginator", content,
                     "Should import Paginator")
        self.assertIn("Paginator(users, 20)", content,
                     "Should paginate with 20 items per page")
        self.assertIn("paginator.get_page(page)", content,
                     "Should get page from paginator")


class TestSprint15UserDetailImplementation(unittest.TestCase):
    """Test Sprint 15 user detail view implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_user_detail_error_handling(self):
        """Test that user detail view has proper error handling."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for error handling
        self.assertIn("try:", content, "Should have try/except blocks for error handling")
        self.assertIn("except Exception as e:", content, "Should catch exceptions")
        self.assertIn("logger.error", content, "Should log errors")
        
        # Check for get_object_or_404 usage
        self.assertIn("get_object_or_404", content, "Should use get_object_or_404 for user lookup")
    
    def test_user_detail_context_variables(self):
        """Test that user detail view provides comprehensive context."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for context variables
        expected_context_vars = [
            "'selected_user': user",
            "'credit_account':",
            "'current_balance':",
            "'balance_breakdown':",
            "'subscription':",
            "'recent_transactions':",
            "'recent_payments':",
            "'recent_service_usage':",
            "'total_payments':",
            "'total_service_usage':",
            "'total_credits_purchased':",
            "'total_credits_consumed':"
        ]
        
        for context_var in expected_context_vars:
            self.assertIn(context_var, content, f"Should include {context_var} in context")


class TestSprint15TemplateGeneration(ProjectTestMixin, unittest.TestCase):
    """Test Sprint 15 template generation and structure."""
    
    def test_project_structure_includes_user_management(self):
        """Test that generated project structure includes user management components."""
        # Create test project using the mixin's method
        self.create_test_project()
        
        # Check that admin_dashboard app exists in the generated project
        admin_dashboard_path = self.project_path / "admin_dashboard"
        self.assertTrue(admin_dashboard_path.exists(), "admin_dashboard app should exist")
        
        # Check for views.py
        views_path = admin_dashboard_path / "views.py"
        self.assertTrue(views_path.exists(), "admin_dashboard views.py should exist")
        
        # Check for urls.py
        urls_path = admin_dashboard_path / "urls.py"
        self.assertTrue(urls_path.exists(), "admin_dashboard urls.py should exist")
    
    def test_admin_dashboard_app_configuration(self):
        """Test that admin_dashboard app is properly configured."""
        # Check for apps.py
        apps_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "apps.py"
        
        if apps_path.exists():
            with open(apps_path, 'r') as f:
                content = f.read()
            
            # Check app configuration
            self.assertIn("class AdminDashboardConfig", content, "Should have AdminDashboardConfig class")
            self.assertIn("name = 'admin_dashboard'", content, "Should set app name")


class TestSprint15IntegrationPoints(unittest.TestCase):
    """Test Sprint 15 integration with existing system."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_user_model_integration(self):
        """Test that user search integrates with CustomUser model."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for CustomUser model import and usage
        self.assertIn("from users.models import CustomUser", content,
                     "Should import CustomUser model")
        self.assertIn("CustomUser.objects.filter(", content,
                     "Should query CustomUser objects")
    
    def test_credit_system_integration(self):
        """Test that user detail integrates with credit system."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for credit system integration
        self.assertIn("from credits.models import CreditAccount", content,
                     "Should import CreditAccount model")
        self.assertIn("CreditAccount.get_or_create_for_user", content,
                     "Should get or create credit account for user")
        self.assertIn("get_balance()", content,
                     "Should get current balance")
        self.assertIn("get_balance_by_type_available()", content,
                     "Should get balance breakdown")
    
    def test_subscription_system_integration(self):
        """Test that user detail integrates with subscription system."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for subscription system integration
        self.assertIn("UserSubscription", content, "Should reference UserSubscription model")
        self.assertIn("user.subscription", content, "Should access user subscription")


class TestSprint15CodeQuality(unittest.TestCase):
    """Test Sprint 15 code quality and best practices."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_proper_imports_organization(self):
        """Test that imports are properly organized."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for proper import organization
        lines = content.split('\n')
        
        # Find import sections
        django_imports = []
        local_imports = []
        
        for line in lines:
            if line.strip().startswith('from django'):
                django_imports.append(line)
            elif line.strip().startswith('from users') or line.strip().startswith('from credits'):
                local_imports.append(line)
        
        self.assertTrue(len(django_imports) > 0, "Should have Django imports")
        self.assertTrue(len(local_imports) > 0, "Should have local imports")
    
    def test_proper_docstrings(self):
        """Test that functions have proper docstrings."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for docstrings on main functions
        self.assertIn('"""Search for users by email or name."""', content,
                     "user_search should have docstring")
        self.assertIn('"""Display detailed information for a specific user."""', content,
                     "user_detail should have docstring")
    
    def test_proper_logging_usage(self):
        """Test that proper logging is used."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check for logging import and usage
        self.assertIn("import logging", content, "Should import logging")
        self.assertIn("logger = logging.getLogger(__name__)", content, "Should create logger")
        self.assertIn("logger.error", content, "Should use logger for error logging")


class TestSprint15SearchLogic(unittest.TestCase):
    """Test Sprint 15 search logic implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_search_filter_logic_correctness(self):
        """Test that search filter logic only returns matching users."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Check that search filter is built properly with Q objects
        self.assertIn("search_filter = Q()", content, "Should initialize empty Q object")
        self.assertIn("search_filter |=", content, "Should use OR operator to build filter")
        self.assertIn("Q(email__icontains=query)", content, "Should search by email")
        self.assertIn("Q(first_name__icontains=query)", content, "Should search by first name")
        self.assertIn("Q(last_name__icontains=query)", content, "Should search by last name")
        
        # Check for proper full name search logic
        self.assertIn("if ' ' in query:", content, "Should handle full name search")
        self.assertIn("query_parts = query.split()", content, "Should split query for full name")
        self.assertIn("first_name__icontains=first_part, last_name__icontains=last_part", content, 
                     "Should search first+last name combination")
        
        # Check that filter is applied correctly
        self.assertIn("CustomUser.objects.filter(search_filter)", content, 
                     "Should apply the search_filter to CustomUser objects")
        
        # Ensure empty queryset is returned when no query
        self.assertIn("CustomUser.objects.none()", content, 
                     "Should return empty queryset when no query")

    def test_empty_string_search_bug_fixed(self):
        """Test that empty string search bug is fixed for single-word queries."""
        # Get the path to the admin_dashboard views template
        views_template_path = Path(__file__).parent.parent.parent / "quickscale" / "project_templates" / "admin_dashboard" / "views.py"
        
        # Read the template content
        with open(views_template_path, 'r') as f:
            content = f.read()
        
        # Ensure old buggy logic is not present
        self.assertNotIn("query_parts[-1] if len(query_parts) > 1 else ''", content,
                        "Should not have the old buggy logic that creates empty last_part")
        
        # Ensure new logic only adds full name search when there are multiple parts
        self.assertIn("if ' ' in query:", content, "Should check for space in query")
        self.assertIn("if len(query_parts) >= 2:", content, 
                     "Should only add full name search when there are at least 2 parts")
        
        # Ensure we don't accidentally search with empty strings
        search_filter_section = content[content.find("search_filter = Q()"):content.find("users = CustomUser.objects.filter")]
        self.assertNotIn("__icontains=''", search_filter_section,
                        "Should not search with empty strings that match all records")


if __name__ == '__main__':
    unittest.main() 