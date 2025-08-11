"""
Dynamic Test Base Classes

These base classes replace static fixture-based testing with dynamic project generation.
Tests now generate real QuickScale projects in temporary directories, ensuring they
always test against current template state rather than historical snapshots.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import os

from .dynamic_project_generator import DynamicProjectGenerator


class DynamicProjectTestCase(unittest.TestCase):
    """Base test case that provides dynamic project generation.
    
    This replaces the old static fixture approach with dynamic generation.
    Each test gets a fresh project generated from current templates.
    """
    
    def setUp(self):
        """Set up test with dynamic project generation capability."""
        super().setUp()
        self.generator = DynamicProjectGenerator(cleanup_on_exit=True)
        self.temp_projects = []
    
    def tearDown(self):
        """Clean up generated projects."""
        super().tearDown()
        self.generator.cleanup_all()
    
    def create_test_project(self, project_name: str = "test_project",
                           init_options: Optional[Dict[str, Any]] = None) -> Path:
        """Create a dynamic test project.
        
        Args:
            project_name: Name of the project
            init_options: Options for quickscale init
            
        Returns:
            Path to the project directory
        """
        project_dir = self.generator.generate_project(project_name, init_options=init_options)
        self.temp_projects.append(project_dir)
        return project_dir
    
    def create_service_in_project(self, project_dir: Path, 
                                service_name: str,
                                service_type: str = "text_processing") -> Path:
        """Create a service within a project.
        
        Args:
            project_dir: Path to the project
            service_name: Name of the service
            service_type: Type of service to generate
            
        Returns:
            Path to the service directory
        """
        return self.generator.generate_service_in_project(
            project_dir, service_name, service_type
        )


class DynamicDjangoTestCase(DynamicProjectTestCase):
    """Dynamic test case for Django component testing.
    
    This generates a real Django project and sets up the Django environment
    to test against actual generated templates, not static fixtures.
    """
    
    def setUp(self):
        """Set up Django test with dynamic project."""
        super().setUp()
        
        # Generate a test project for Django testing
        self.project_dir = self.create_test_project("django_test_project")
        
        # Add the project to Python path for imports
        self.original_sys_path = list(sys.path)
        sys.path.insert(0, str(self.project_dir))
        
        # Set up Django settings to point to our dynamic project
        self._setup_django_for_project()
    
    def tearDown(self):
        """Clean up Django test environment."""
        # Restore sys.path
        sys.path[:] = self.original_sys_path
        super().tearDown()
    
    def _setup_django_for_project(self):
        """Configure Django to use the dynamically generated project."""
        import django
        from django.conf import settings
        
        if not settings.configured:
            # Configure Django to use our dynamic project
            settings.configure(
                DEBUG=True,
                USE_TZ=True,
                SECRET_KEY="dynamic-test-secret-key",
                DATABASES={
                    'default': {
                        'ENGINE': 'django.db.backends.postgresql',
                        'NAME': 'quickscale_test',
                        'USER': 'test_user',
                        'PASSWORD': 'test_pass',
                        'HOST': 'localhost',
                        'PORT': '5433',
                        'TEST': {
                            'NAME': 'test_dynamic_quickscale',
                        },
                    }
                },
                INSTALLED_APPS=[
                    'django.contrib.auth',
                    'django.contrib.contenttypes',
                    'django.contrib.sessions',
                    'django.contrib.messages',
                    'django.contrib.admin',
                    'django.contrib.sites',
                    # Add the dynamically generated apps
                    'users',
                    'credits',
                    'stripe_manager',
                    'admin_dashboard',
                    'common',
                    'public',
                ],
                SITE_ID=1,
                MIDDLEWARE=[
                    'django.middleware.security.SecurityMiddleware',
                    'django.contrib.sessions.middleware.SessionMiddleware',
                    'django.middleware.common.CommonMiddleware',
                    'django.middleware.csrf.CsrfViewMiddleware',
                    'django.contrib.auth.middleware.AuthenticationMiddleware',
                    'django.contrib.messages.middleware.MessageMiddleware',
                ],
                AUTH_USER_MODEL='users.CustomUser',
                ROOT_URLCONF='core.urls',
                TEMPLATES=[{
                    'BACKEND': 'django.template.backends.django.DjangoTemplates',
                    'DIRS': [str(self.project_dir / 'templates')],
                    'APP_DIRS': True,
                    'OPTIONS': {
                        'context_processors': [
                            'django.template.context_processors.debug',
                            'django.template.context_processors.request',
                            'django.contrib.auth.context_processors.auth',
                            'django.contrib.messages.context_processors.messages',
                        ],
                    },
                }],
            )
            
            django.setup()


class DynamicTemplateTestCase(DynamicProjectTestCase):
    """Test case for template validation using dynamic projects.
    
    This replaces hardcoded path-based template testing with testing 
    against freshly generated projects.
    """
    
    def setUp(self):
        """Set up template test with fresh project generation."""
        super().setUp()
        
        # Generate a test project for template testing
        self.project_dir = self.create_test_project("template_test_project")
        
        # Set up convenient paths for testing
        self.templates_dir = self.project_dir / 'templates'
        self.static_dir = self.project_dir / 'static'
        self.apps_dir = self.project_dir
    
    def get_app_path(self, app_name: str) -> Path:
        """Get path to a specific Django app in the project.
        
        Args:
            app_name: Name of the Django app
            
        Returns:
            Path to the app directory
        """
        return self.project_dir / app_name
    
    def get_template_path(self, template_name: str, app_name: Optional[str] = None) -> Path:
        """Get path to a specific template.
        
        Args:
            template_name: Name of the template file
            app_name: Optional app name for app-specific templates
            
        Returns:
            Path to the template file
        """
        if app_name:
            return self.templates_dir / app_name / template_name
        else:
            return self.templates_dir / template_name
    
    def assertFileExists(self, file_path: Path, msg: Optional[str] = None):
        """Assert that a file exists in the generated project.
        
        Args:
            file_path: Path to the file
            msg: Optional custom error message
        """
        if not file_path.exists():
            error_msg = f"File does not exist: {file_path}"
            if msg:
                error_msg = f"{msg}: {error_msg}"
            self.fail(error_msg)
    
    def assertFileContains(self, file_path: Path, content: str, msg: Optional[str] = None):
        """Assert that a file contains specific content.
        
        Args:
            file_path: Path to the file
            content: Content that should be present
            msg: Optional custom error message
        """
        self.assertFileExists(file_path)
        
        file_content = file_path.read_text(encoding='utf-8')
        if content not in file_content:
            error_msg = f"Content '{content}' not found in {file_path}"
            if msg:
                error_msg = f"{msg}: {error_msg}"
            self.fail(error_msg)


# Import sys for path manipulation
import sys
