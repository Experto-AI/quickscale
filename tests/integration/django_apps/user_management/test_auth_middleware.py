"""Tests for user authentication middleware integration."""

import pytest
from unittest.mock import Mock, patch
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse

# Set up Django for testing
from ..base import DjangoIntegrationTestCase, setup_django_template_path, setup_core_env_utils_mock, setup_django_settings

# Set up template path and environment
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()

# Import Django and initialize
import django
django.setup()

# Import the modules we're testing
from users.middleware import AccountLockoutMiddleware
from users.models import AccountLockout

User = get_user_model()


@pytest.mark.django_component
@pytest.mark.integration
class AuthMiddlewareIntegrationTests(DjangoIntegrationTestCase):
    """Integration tests for authentication middleware."""
    
    def setUp(self):
        """Set up test environment for middleware tests."""
        super().setUp()
        
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='middleware@example.com',
            password='testpass123'
        )
        
        # Create a mock get_response function
        self.get_response = Mock()
        self.get_response.return_value = Mock()
        
        # Initialize middleware
        self.middleware = AccountLockoutMiddleware(self.get_response)
    
    def test_middleware_with_anonymous_user(self):
        """Test middleware processing with anonymous user."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        
        # Process request
        response = self.middleware(request)
        
        # Should call get_response normally
        self.get_response.assert_called_once_with(request)
        self.assertEqual(response, self.get_response.return_value)
    
    def test_middleware_with_authenticated_user_no_lockout(self):
        """Test middleware with authenticated user who has no lockout record."""
        request = self.factory.get('/')
        request.user = self.user
        
        # Process request
        response = self.middleware(request)
        
        # Should call get_response normally
        self.get_response.assert_called_once_with(request)
        self.assertEqual(response, self.get_response.return_value)
        
        # Should create lockout record if it doesn't exist
        self.assertTrue(AccountLockout.objects.filter(user=self.user).exists())
    
    def test_middleware_with_unlocked_user(self):
        """Test middleware with authenticated user who is not locked."""
        # Create unlocked account lockout
        lockout = AccountLockout.objects.create(
            user=self.user,
            failed_attempts=2,
            is_locked=False
        )
        
        request = self.factory.get('/')
        request.user = self.user
        
        # Process request
        response = self.middleware(request)
        
        # Should call get_response normally
        self.get_response.assert_called_once_with(request)
        self.assertEqual(response, self.get_response.return_value)
    
    @patch('users.middleware.logout')
    def test_middleware_with_locked_user(self, mock_logout):
        """Test middleware with locked user."""
        # Create locked account lockout
        lockout = AccountLockout.objects.create(
            user=self.user,
            failed_attempts=5,
            is_locked=True
        )
        
        request = self.factory.get('/')
        request.user = self.user
        request.session = {}
        
        # Process request
        response = self.middleware(request)
        
        # Should logout user and return locked page
        mock_logout.assert_called_once_with(request)
        self.assertIsInstance(response, TemplateResponse)
        self.assertEqual(response.status_code, 423)
    
    def test_middleware_creates_lockout_record(self):
        """Test that middleware creates lockout record for new users."""
        # Ensure no lockout record exists
        self.assertFalse(AccountLockout.objects.filter(user=self.user).exists())
        
        request = self.factory.get('/')
        request.user = self.user
        
        # Process request
        self.middleware(request)
        
        # Should create lockout record
        lockout = AccountLockout.objects.get(user=self.user)
        self.assertEqual(lockout.failed_attempts, 0)
        self.assertFalse(lockout.is_locked)
    
    def test_middleware_with_multiple_requests(self):
        """Test middleware behavior with multiple requests from same user."""
        request = self.factory.get('/')
        request.user = self.user
        
        # First request
        self.middleware(request)
        
        # Reset mock
        self.get_response.reset_mock()
        
        # Second request
        self.middleware(request)
        
        # Should still process normally
        self.get_response.assert_called_once_with(request)
        
        # Should still have only one lockout record
        self.assertEqual(AccountLockout.objects.filter(user=self.user).count(), 1)


@pytest.mark.django_component
@pytest.mark.integration
class AccountLockoutModelIntegrationTests(DjangoIntegrationTestCase):
    """Integration tests for AccountLockout model with middleware."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        
        self.user = User.objects.create_user(
            email='lockout@example.com',
            password='testpass123'
        )
    
    def test_lockout_threshold_integration(self):
        """Test lockout threshold behavior in middleware context."""
        # Create lockout record near threshold
        lockout = AccountLockout.objects.create(
            user=self.user,
            failed_attempts=4,  # Just below threshold (assuming 5 is max)
            is_locked=False
        )
        
        # Simulate failed login
        lockout.record_failed_attempt()
        
        # Should be locked now
        lockout.refresh_from_db()
        self.assertTrue(lockout.is_locked)
        self.assertEqual(lockout.failed_attempts, 5)
    
    def test_lockout_reset_integration(self):
        """Test lockout reset functionality."""
        # Create locked account
        lockout = AccountLockout.objects.create(
            user=self.user,
            failed_attempts=5,
            is_locked=True
        )
        
        # Reset lockout
        lockout.reset_lockout()
        
        # Should be unlocked
        lockout.refresh_from_db()
        self.assertFalse(lockout.is_locked)
        self.assertEqual(lockout.failed_attempts, 0)
