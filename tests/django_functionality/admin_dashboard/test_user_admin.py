"""Unit tests for user admin components."""

import unittest
import os
import sys


class UserAdminComponentTests(unittest.TestCase):
    """Simple unit tests for user admin components without Django dependencies."""
    
    def test_admin_file_exists(self):
        """Test that the admin.py file exists in the users template."""
        admin_file_path = os.path.join(
            os.path.dirname(__file__),
            '../../../quickscale/project_templates/users/admin.py'
        )
        self.assertTrue(
            os.path.exists(admin_file_path),
            f"Admin file should exist at {admin_file_path}"
        )
    
    def test_admin_file_contains_expected_classes(self):
        """Test that admin.py contains the expected class definitions."""
        admin_file_path = os.path.join(
            os.path.dirname(__file__),
            '../../../quickscale/project_templates/users/admin.py'
        )
        
        if os.path.exists(admin_file_path):
            with open(admin_file_path, 'r') as f:
                content = f.read()
                
            # Check for expected class definitions
            self.assertIn('class CustomUserAdmin', content)
            self.assertIn('class EmailAddressInline', content)
            self.assertIn('inlines = [EmailAddressInline]', content)
    
    def test_admin_imports(self):
        """Test that admin.py imports necessary modules."""
        admin_file_path = os.path.join(
            os.path.dirname(__file__),
            '../../../quickscale/project_templates/users/admin.py'
        )
        
        if os.path.exists(admin_file_path):
            with open(admin_file_path, 'r') as f:
                content = f.read()
                
            # Check for expected imports
            self.assertIn('from django.contrib', content)
            self.assertIn('from allauth.account.models import EmailAddress', content)


if __name__ == '__main__':
    unittest.main()