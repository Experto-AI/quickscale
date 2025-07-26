"""Tests for account lockout middleware."""
from unittest.mock import Mock, patch
from datetime import timedelta
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.template.response import TemplateResponse

from users.middleware import AccountLockoutMiddleware
from users.models import AccountLockout

User = get_user_model()


class AccountLockoutMiddlewareTestCase(TestCase):
    """Test case for AccountLockoutMiddleware functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a mock get_response function
        self.get_response = Mock()
        self.get_response.return_value = Mock()
        
        # Initialize middleware
        self.middleware = AccountLockoutMiddleware(self.get_response)
    
    def test_middleware_anonymous_user(self):
        """Test middleware with anonymous user."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        
        # Process request
        response = self.middleware(request)
        
        # Should call get_response normally
        self.get_response.assert_called_once_with(request)
        self.assertEqual(response, self.get_response.return_value)
    
    def test_middleware_authenticated_user_no_lockout(self):
        """Test middleware with authenticated user who has no lockout record."""
        request = self.factory.get('/')
        request.user = self.user
        
        # Process request
        response = self.middleware(request)
        
        # Should call get_response normally
        self.get_response.assert_called_once_with(request)
        self.assertEqual(response, self.get_response.return_value)
        
        # Should create lockout record
        self.assertTrue(AccountLockout.objects.filter(user=self.user).exists())
    
    def test_middleware_authenticated_user_not_locked(self):
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
    def test_middleware_locked_user_expired(self, mock_logout):
        """Test middleware with locked user whose lockout has expired."""
        # Create expired lockout
        lockout = AccountLockout.objects.create(
            user=self.user,
            failed_attempts=5,
            is_locked=True,
            locked_until=timezone.now() - timedelta(minutes=5)
        )
        
        request = self.factory.get('/')
        request.user = self.user
        
        # Mock check_lockout_expired to return True
        with patch.object(lockout, 'check_lockout_expired', return_value=True):
            # Process request
            response = self.middleware(request)
        
        # Should call get_response normally (lockout expired)
        self.get_response.assert_called_once_with(request)
        self.assertEqual(response, self.get_response.return_value)
        
        # Should not logout user since lockout expired
        mock_logout.assert_not_called()
    
    @patch('users.middleware.logout')
    def test_middleware_locked_user_active(self, mock_logout):
        """Test middleware with actively locked user."""
        # Create active lockout
        future_time = timezone.now() + timedelta(minutes=5)
        lockout = AccountLockout.objects.create(
            user=self.user,
            failed_attempts=5,
            is_locked=True,
            locked_until=future_time,
            last_failed_attempt=timezone.now()
        )
        
        request = self.factory.get('/')
        request.user = self.user
        
        # Mock check_lockout_expired to return False
        with patch.object(lockout, 'check_lockout_expired', return_value=False):
            # Process request
            response = self.middleware(request)
        
        # Should logout user
        mock_logout.assert_called_once_with(request)
        
        # Should return locked account template
        self.assertIsInstance(response, TemplateResponse)
        self.assertEqual(response.template_name, 'users/account_locked.html')
        self.assertEqual(response.status_code, 423)  # HTTP 423 Locked
        
        # Should not call get_response
        self.get_response.assert_not_called()
    
    @patch('users.middleware.logout')
    def test_middleware_locked_user_context(self, mock_logout):
        """Test middleware context data for locked user."""
        # Create active lockout
        future_time = timezone.now() + timedelta(minutes=10)
        lockout = AccountLockout.objects.create(
            user=self.user,
            failed_attempts=5,
            is_locked=True,
            locked_until=future_time,
            last_failed_attempt=timezone.now()
        )
        
        request = self.factory.get('/')
        request.user = self.user
        
        # Mock check_lockout_expired to return False
        with patch.object(lockout, 'check_lockout_expired', return_value=False):
            # Process request
            response = self.middleware(request)
        
        # Verify context data
        self.assertIn('locked_until', response.context_data)
        self.assertIn('minutes_remaining', response.context_data)
        self.assertIn('failed_attempts', response.context_data)
        self.assertIn('user_email', response.context_data)
        
        self.assertEqual(response.context_data['locked_until'], future_time)
        self.assertEqual(response.context_data['minutes_remaining'], 10)
        self.assertEqual(response.context_data['failed_attempts'], 5)
        self.assertEqual(response.context_data['user_email'], self.user.email)
    
    @patch('users.middleware.logout')
    def test_middleware_locked_user_no_time_remaining(self, mock_logout):
        """Test middleware with locked user but no time remaining."""
        # Create lockout without locked_until
        lockout = AccountLockout.objects.create(
            user=self.user,
            failed_attempts=5,
            is_locked=True,
            locked_until=None
        )
        
        request = self.factory.get('/')
        request.user = self.user
        
        # Mock check_lockout_expired to return False
        with patch.object(lockout, 'check_lockout_expired', return_value=False):
            # Set locked_until to None so time_until_unlock returns None
            lockout.locked_until = None
            lockout.save()
            # Process request
            response = self.middleware(request)
        
        # Should still logout and show lockout page
        mock_logout.assert_called_once_with(request)
        self.assertIsInstance(response, TemplateResponse)
        
        # Verify context data handles None time
        self.assertEqual(response.context_data['minutes_remaining'], 0)
    
    def test_middleware_creates_missing_lockout(self):
        """Test that middleware creates lockout record if missing."""
        request = self.factory.get('/')
        request.user = self.user
        
        # Ensure no lockout exists
        AccountLockout.objects.filter(user=self.user).delete()
        self.assertFalse(AccountLockout.objects.filter(user=self.user).exists())
        
        # Process request
        response = self.middleware(request)
        
        # Should create lockout record
        self.assertTrue(AccountLockout.objects.filter(user=self.user).exists())
        lockout = AccountLockout.objects.get(user=self.user)
        self.assertEqual(lockout.failed_attempts, 0)
        self.assertFalse(lockout.is_locked)
    
    def test_middleware_initialization(self):
        """Test middleware initialization."""
        get_response = Mock()
        middleware = AccountLockoutMiddleware(get_response)
        
        self.assertEqual(middleware.get_response, get_response)
    
    def test_middleware_call_method(self):
        """Test middleware __call__ method delegation."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        
        # Ensure __call__ delegates properly
        response = self.middleware(request)
        
        # Should call get_response
        self.get_response.assert_called_once_with(request)
        self.assertEqual(response, self.get_response.return_value)
    
    @patch('users.middleware.logout')
    def test_middleware_preserves_request_attributes(self, mock_logout):
        """Test that middleware preserves request attributes."""
        # Create active lockout
        future_time = timezone.now() + timedelta(minutes=5)
        lockout = AccountLockout.objects.create(
            user=self.user,
            failed_attempts=5,
            is_locked=True,
            locked_until=future_time
        )
        
        request = self.factory.get('/test-path/?param=value')
        request.user = self.user
        request.META['HTTP_USER_AGENT'] = 'Test Browser'
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        
        # Mock check_lockout_expired to return False
        with patch.object(lockout, 'check_lockout_expired', return_value=False):
            # Process request
            response = self.middleware(request)
        
        # Should preserve request for template rendering
        self.assertIsInstance(response, TemplateResponse)
        # The request should be used for logout and template rendering
        mock_logout.assert_called_once_with(request)
    
    def test_middleware_edge_case_database_error(self):
        """Test middleware behavior when database error occurs."""
        request = self.factory.get('/')
        request.user = self.user
        
        # Mock database error
        with patch('users.models.AccountLockout.objects.get', 
                  side_effect=Exception("Database error")):
            # Process request - should handle gracefully
            response = self.middleware(request)
        
        # Should call get_response normally despite error
        self.get_response.assert_called_once_with(request)
        self.assertEqual(response, self.get_response.return_value) 