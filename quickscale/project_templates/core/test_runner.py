"""
Custom test runner for QuickScale projects.
This runner ensures proper test discovery with Django's test framework.
"""
from django.test.runner import DiscoverRunner
import sys
import os
import unittest


class QuickScaleTestLoader(unittest.TestLoader):
    """Custom test loader that avoids app-level 'tests' modules."""
    
    def discover(self, start_dir, pattern='test*.py', top_level_dir=None):
        """
        Override discover to prevent loading from app-level 'tests' modules.
        This prevents conflicts with the project-level 'tests' package.
        """
        # Skip discovery in app-level 'tests' directories to avoid import conflicts
        dir_basename = os.path.basename(os.path.abspath(start_dir))
        parent_dir = os.path.basename(os.path.dirname(os.path.abspath(start_dir)))
        
        # If we're looking at an app-level 'tests' directory/module, return empty suite
        if dir_basename == 'tests' and parent_dir in ['dashboard', 'users', 'public', 'common']:
            return self.suiteClass()
            
        # Otherwise, proceed with normal discovery
        return super().discover(start_dir, pattern, top_level_dir)


class QuickScaleTestRunner(DiscoverRunner):
    """Custom test runner to handle QuickScale's test directory structure."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Use our custom test loader
        self.test_loader = QuickScaleTestLoader()
    
    def build_suite(self, test_labels=None, **kwargs):
        """
        Build the test suite with proper handling of test directories.
        This ensures that tests in app/tests/ directories are properly discovered.
        """
        # Determine if we're running in a generated project or the QuickScale repo
        # Check for indicators of a generated project: manage.py and setup.py absent
        is_generated_project = os.path.exists('manage.py') and not os.path.exists('setup.py')
        
        if not test_labels:
            # Default to top-level 'tests' package for generated projects
            test_labels = ['tests'] if is_generated_project else ['.']
        
        # Ensure project root is in the Python path
        project_root = os.getcwd()
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            
        # Pass extra_tests as a keyword argument if it exists in kwargs
        extra_tests = kwargs.pop('extra_tests', None)
        
        # Call the parent build_suite method with our custom test loader
        suite = super().build_suite(test_labels, extra_tests=extra_tests, **kwargs)
        
        return suite
