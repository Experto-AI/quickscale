"""Sample test file for QuickScale projects.

This file provides a starting point for writing tests in your QuickScale project.
You can replace or extend these tests with your own application-specific tests.

For comprehensive testing examples, see the QuickScale documentation.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse


class SampleTestCase(TestCase):
    """Sample test case to verify the test runner is working correctly."""

    def test_sample(self):
        """A simple passing test to verify the test runner works."""
        self.assertEqual(1 + 1, 2)

    def test_project_urls_accessible(self):
        """Test that basic project URLs are accessible."""
        client = Client()
        
        # Test home page
        response = client.get('/')
        self.assertIn(response.status_code, [200, 302], "Home page should be accessible")
        
        # Test login page
        try:
            login_url = reverse('account_login')
            response = client.get(login_url)
            self.assertEqual(response.status_code, 200, "Login page should be accessible")
        except:
            # Login URL might not be available yet
            pass

    def test_user_model_works(self):
        """Test that the custom User model works correctly."""
        User = get_user_model()
        
        # Test user creation
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertFalse(user.is_staff)
        self.assertTrue(user.is_active)


class HealthCheckTestCase(TestCase):
    """Health check tests to verify basic project functionality."""

    def test_database_connection(self):
        """Test that database connection works."""
        User = get_user_model()
        
        # This should not raise an exception
        count = User.objects.count()
        self.assertIsInstance(count, int)

    def test_settings_loaded(self):
        """Test that Django settings are properly loaded."""
        from django.conf import settings
        
        # Check that required settings exist
        self.assertTrue(hasattr(settings, 'SECRET_KEY'))
        self.assertTrue(hasattr(settings, 'DATABASES'))
        self.assertTrue(hasattr(settings, 'INSTALLED_APPS'))
        
        # Check that our apps are installed
        self.assertIn('users', settings.INSTALLED_APPS)
        self.assertIn('credits', settings.INSTALLED_APPS)
