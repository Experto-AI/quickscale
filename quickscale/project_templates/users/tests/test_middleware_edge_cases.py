"""Tests for AccountLockoutMiddleware edge cases and error conditions."""
from unittest.mock import patch, Mock
from datetime import timedelta
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.contrib.auth.models import AnonymousUser
from django.db import DatabaseError
from django.core.exceptions import ValidationError

from users.middleware import AccountLockoutMiddleware, MiddlewareValidationError
from users.models import AccountLockout

User = get_user_model()


class AccountLockoutMiddlewareEdgeCasesTestCase(TestCase):
    """Test case for AccountLockoutMiddleware edge cases."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='middleware@example.com',
            password='testpass123'
        )
        self.get_response = Mock(return_value=HttpResponse("OK"))
        self.middleware = AccountLockoutMiddleware(self.get_response)
    
    def test_malformed_request_without_user(self):
        """Test handling of malformed requests without user attribute."""
        request = Mock()
        # Remove user attribute to simulate malformed request
        if hasattr(request, 'user'):
            delattr(request, 'user')
        
        # Should handle gracefully and return normal response
        with self.assertLogs(level='ERROR'):
            response = self.middleware(request)
        
        # Should call get_response despite validation error
        self.get_response.assert_called_once()
        self.assertEqual(response.status_code, 200)
    
    def test_malformed_request_without_meta(self):
        """Test handling of malformed requests without META attribute."""
        request = Mock()
        request.user = self.user
        # Remove META attribute
        if hasattr(request, 'META'):
            delattr(request, 'META')
        
        # Should handle gracefully
        with self.assertLogs(level='ERROR'):
            response = self.middleware(request)
        
        self.get_response.assert_called_once()
        self.assertEqual(response.status_code, 200)
    
    def test_missing_remote_addr(self):
        """Test handling of requests without REMOTE_ADDR."""
        request = self.factory.get('/')
        request.user = self.user
        request.META = {}  # No REMOTE_ADDR
        
        # Should log warning but continue
        with self.assertLogs(level='WARNING'):
            response = self.middleware(request)
        
        self.get_response.assert_called_once()
        self.assertEqual(response.status_code, 200)
    
    def test_anonymous_user_bypass(self):
        """Test that anonymous users bypass lockout checks."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        response = self.middleware(request)
        
        # Should proceed normally without lockout checks
        self.get_response.assert_called_once()
        self.assertEqual(response.status_code, 200)
    
    def test_lockout_record_creation_database_error(self):
        """Test handling of database errors during lockout record creation."""
        request = self.factory.get('/')
        request.user = self.user
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        # Ensure no existing lockout record
        AccountLockout.objects.filter(user=self.user).delete()
        
        with patch('users.models.AccountLockout.objects.create') as mock_create:
            mock_create.side_effect = DatabaseError("Database connection failed")
            
            # Should handle database error gracefully
            with self.assertLogs(level='ERROR'):
                response = self.middleware(request)
            
            # Should continue without lockout protection
            self.get_response.assert_called_once()
            self.assertEqual(response.status_code, 200)
    
    def test_lockout_record_creation_validation_error(self):
        """Test handling of validation errors during lockout record creation."""
        request = self.factory.get('/')
        request.user = self.user
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        # Ensure no existing lockout record
        AccountLockout.objects.filter(user=self.user).delete()
        
        with patch('users.models.AccountLockout.objects.create') as mock_create:
            mock_create.side_effect = ValidationError("Invalid user data")
            
            # Should handle validation error gracefully
            with self.assertLogs(level='ERROR'):
                response = self.middleware(request)
            
            self.get_response.assert_called_once()
            self.assertEqual(response.status_code, 200)
    
    def test_lockout_get_database_error(self):
        """Test handling of database errors when retrieving lockout record."""
        request = self.factory.get('/')
        request.user = self.user
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        with patch('users.models.AccountLockout.objects.get') as mock_get:
            mock_get.side_effect = DatabaseError("Database query failed")
            
            # Should handle database error gracefully
            with self.assertLogs(level='ERROR'):
                response = self.middleware(request)
            
            self.get_response.assert_called_once()
            self.assertEqual(response.status_code, 200)
    
    def test_unexpected_error_handling(self):
        """Test handling of unexpected errors in middleware."""
        request = self.factory.get('/')
        request.user = self.user
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        with patch('users.models.AccountLockout.objects.get') as mock_get:
            mock_get.side_effect = Exception("Unexpected error")
            
            # Should handle unexpected error gracefully
            with self.assertLogs(level='ERROR'):
                response = self.middleware(request)
            
            self.get_response.assert_called_once()
            self.assertEqual(response.status_code, 200)
    
    def test_locked_account_response_structure(self):
        """Test the structure of locked account response."""
        request = self.factory.get('/')
        request.user = self.user
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        # Create locked account
        lockout = AccountLockout.objects.create(
            user=self.user,
            is_locked=True,
            locked_until=timezone.now() + timedelta(minutes=5),
            failed_attempts=5
        )
        
        response = self.middleware(request)
        
        # Should return 423 Locked status
        self.assertIsInstance(response, TemplateResponse)
        self.assertEqual(response.status_code, 423)
        self.assertEqual(response.template_name, 'users/account_locked.html')
        
        # Check context variables
        context = response.context_data
        self.assertIn('locked_until', context)
        self.assertIn('minutes_remaining', context)
        self.assertIn('failed_attempts', context)
        self.assertIn('user_email', context)
        self.assertEqual(context['user_email'], self.user.email)
        self.assertEqual(context['failed_attempts'], 5)
    
    def test_lockout_expiry_during_request(self):
        """Test lockout expiring during request processing."""
        request = self.factory.get('/')
        request.user = self.user
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        # Create expired lockout
        lockout = AccountLockout.objects.create(
            user=self.user,
            is_locked=True,
            locked_until=timezone.now() - timedelta(minutes=1),  # Already expired
            failed_attempts=5
        )
        
        response = self.middleware(request)
        
        # Should detect expiry and allow normal processing
        self.get_response.assert_called_once()
        self.assertEqual(response.status_code, 200)
        
        # Verify lockout was reset
        lockout.refresh_from_db()
        self.assertFalse(lockout.is_locked)
        self.assertEqual(lockout.failed_attempts, 0)
    
    def test_time_calculation_edge_cases(self):
        """Test time calculation edge cases in locked account response."""
        request = self.factory.get('/')
        request.user = self.user
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        # Test with very short remaining time
        lockout = AccountLockout.objects.create(
            user=self.user,
            is_locked=True,
            locked_until=timezone.now() + timedelta(seconds=30),  # 30 seconds
            failed_attempts=3
        )
        
        response = self.middleware(request)
        
        context = response.context_data
        # Should show 0 minutes for less than 60 seconds
        self.assertEqual(context['minutes_remaining'], 0)
    
    def test_middleware_with_none_response(self):
        """Test middleware when get_response returns None."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        # Mock get_response to return None
        self.get_response.return_value = None
        
        response = self.middleware(request)
        
        # Should handle None response gracefully
        self.assertIsNone(response)
        self.get_response.assert_called_once()


class AccountLockoutMiddlewarePerformanceTestCase(TestCase):
    """Test case for middleware performance scenarios."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.users = []
        self.get_response = Mock(return_value=HttpResponse("OK"))
        self.middleware = AccountLockoutMiddleware(self.get_response)
        
        # Create multiple users
        for i in range(10):
            user = User.objects.create_user(
                email=f'perf_{i}@example.com',
                password='testpass123'
            )
            AccountLockout.objects.create(user=user)
            self.users.append(user)
    
    def test_middleware_performance_with_multiple_users(self):
        """Test middleware performance with multiple concurrent users."""
        import time
        
        start_time = time.time()
        
        # Process requests for all users
        for user in self.users:
            request = self.factory.get('/')
            request.user = user
            request.META = {'REMOTE_ADDR': f'192.168.1.{user.id}'}
            
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)
        
        end_time = time.time()
        
        # Should process all requests quickly (less than 0.1 seconds)
        self.assertLess(end_time - start_time, 0.1)
    
    def test_middleware_performance_with_locked_accounts(self):
        """Test middleware performance with locked accounts."""
        import time
        
        # Lock half the accounts
        for i, user in enumerate(self.users[:5]):
            lockout = AccountLockout.objects.get(user=user)
            lockout.is_locked = True
            lockout.locked_until = timezone.now() + timedelta(minutes=5)
            lockout.failed_attempts = 5
            lockout.save()
        
        start_time = time.time()
        
        # Process requests for all users
        for user in self.users:
            request = self.factory.get('/')
            request.user = user
            request.META = {'REMOTE_ADDR': f'192.168.1.{user.id}'}
            
            response = self.middleware(request)
            # Some will be locked (423), others normal (200)
            self.assertIn(response.status_code, [200, 423])
        
        end_time = time.time()
        
        # Should still process quickly even with locked accounts
        self.assertLess(end_time - start_time, 0.2)


class AccountLockoutMiddlewareIntegrationTestCase(TestCase):
    """Integration tests for middleware with other components."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='integration@example.com',
            password='testpass123'
        )
        self.get_response = Mock(return_value=HttpResponse("OK"))
        self.middleware = AccountLockoutMiddleware(self.get_response)
    
    @patch('django.contrib.auth.logout')
    def test_logout_integration(self, mock_logout):
        """Test middleware integration with Django's logout function."""
        request = self.factory.get('/')
        request.user = self.user
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        # Create locked account
        AccountLockout.objects.create(
            user=self.user,
            is_locked=True,
            locked_until=timezone.now() + timedelta(minutes=5),
            failed_attempts=5
        )
        
        response = self.middleware(request)
        
        # Should call Django's logout function
        mock_logout.assert_called_once_with(request)
        self.assertEqual(response.status_code, 423)
    
    def test_template_rendering_integration(self):
        """Test integration with Django's template rendering system."""
        request = self.factory.get('/')
        request.user = self.user
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        # Create locked account
        lockout = AccountLockout.objects.create(
            user=self.user,
            is_locked=True,
            locked_until=timezone.now() + timedelta(minutes=10),
            failed_attempts=7
        )
        
        response = self.middleware(request)
        
        # Verify template response structure
        self.assertIsInstance(response, TemplateResponse)
        self.assertEqual(response.template_name, 'users/account_locked.html')
        
        # Verify all required context is available for template
        required_context_keys = ['locked_until', 'minutes_remaining', 'failed_attempts', 'user_email']
        for key in required_context_keys:
            self.assertIn(key, response.context_data)
    
    def test_middleware_chain_integration(self):
        """Test middleware working within a chain of middleware."""
        # Simulate middleware chain by calling multiple times
        request = self.factory.get('/')
        request.user = self.user
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        
        # First call - normal processing
        response1 = self.middleware(request)
        self.assertEqual(response1.status_code, 200)
        
        # Lock the account
        lockout = AccountLockout.objects.create(
            user=self.user,
            is_locked=True,
            locked_until=timezone.now() + timedelta(minutes=5),
            failed_attempts=5
        )
        
        # Second call - should detect lockout
        response2 = self.middleware(request)
        self.assertEqual(response2.status_code, 423)
        
        # Should maintain consistent behavior across calls
        self.assertNotEqual(response1.status_code, response2.status_code) 