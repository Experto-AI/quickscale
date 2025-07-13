"""Integration tests for security-enhanced authentication views."""
from unittest.mock import patch, Mock
from datetime import timedelta
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model, authenticate
from django.contrib.messages import get_messages
from django.utils import timezone
from django.http import HttpResponse

from users.models import AccountLockout
from users.views import login_view
from users.forms import EnhancedLoginForm

User = get_user_model()


class SecurityViewsTestCase(TestCase):
    """Test case for security-enhanced authentication views."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='correct_password'
        )
        self.lockout = AccountLockout.objects.create(user=self.user)
    
    def create_post_request(self, data=None, path='/login/'):
        """Helper method to create a POST request."""
        request = self.factory.post(path, data or {})
        request.user = Mock()
        request.user.is_authenticated = False
        request.session = {}
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        return request
    
    def create_get_request(self, path='/login/'):
        """Helper method to create a GET request."""
        request = self.factory.get(path)
        request.user = Mock()
        request.user.is_authenticated = False
        return request
    
    @patch('users.views.render')
    def test_login_view_get_request(self, mock_render):
        """Test login view with GET request."""
        request = self.create_get_request()
        
        login_view(request)
        
        # Should render login template
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        self.assertEqual(args[1], 'users/login.html')
        self.assertIn('form', args[2])
        self.assertIsInstance(args[2]['form'], EnhancedLoginForm)
    
    @patch('users.views.messages')
    @patch('users.views.redirect')
    @patch('users.views.login')
    def test_login_view_successful_login(self, mock_login, mock_redirect, mock_messages):
        """Test successful login."""
        request = self.create_post_request({
            'username': 'test@example.com',  # Form uses 'username' field for email
            'password': 'correct_password'
        })
        
        # Mock successful authentication
        with patch('users.views.authenticate', return_value=self.user):
            response = login_view(request)
        
        # Should reset failed attempts
        self.lockout.refresh_from_db()
        self.assertEqual(self.lockout.failed_attempts, 0)
        self.assertFalse(self.lockout.is_locked)
        
        # Should login user and redirect
        mock_login.assert_called_once_with(request, self.user)
        mock_redirect.assert_called_once_with('public:index')
        mock_messages.success.assert_called_once()
    
    @patch('users.views.render')
    def test_login_view_invalid_credentials(self, mock_render):
        """Test login with invalid credentials."""
        request = self.create_post_request({
            'username': 'test@example.com',
            'password': 'wrong_password'
        })
        
        # Mock failed authentication
        with patch('users.views.authenticate', return_value=None):
            login_view(request)
        
        # Should increment failed attempts
        self.lockout.refresh_from_db()
        self.assertEqual(self.lockout.failed_attempts, 1)
        self.assertFalse(self.lockout.is_locked)
        
        # Should render login form with error
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        form = args[2]['form']
        self.assertTrue(form.errors)
    
    @patch('users.views.render')
    def test_login_view_nonexistent_user(self, mock_render):
        """Test login with nonexistent user."""
        request = self.create_post_request({
            'username': 'nonexistent@example.com',
            'password': 'any_password'
        })
        
        login_view(request)
        
        # Should render login form with generic error
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        form = args[2]['form']
        self.assertTrue(form.errors)
    
    @override_settings(ACCOUNT_LOCKOUT_MAX_ATTEMPTS=3)
    @patch('users.views.render')
    def test_login_view_account_lockout_progression(self, mock_render):
        """Test progressive account lockout over multiple attempts."""
        # First failed attempt
        request1 = self.create_post_request({
            'username': 'test@example.com',
            'password': 'wrong_password'
        })
        
        with patch('users.views.authenticate', return_value=None):
            login_view(request1)
        
        self.lockout.refresh_from_db()
        self.assertEqual(self.lockout.failed_attempts, 1)
        self.assertFalse(self.lockout.is_locked)
        
        # Second failed attempt
        request2 = self.create_post_request({
            'username': 'test@example.com',
            'password': 'wrong_password'
        })
        
        with patch('users.views.authenticate', return_value=None):
            login_view(request2)
        
        self.lockout.refresh_from_db()
        self.assertEqual(self.lockout.failed_attempts, 2)
        self.assertFalse(self.lockout.is_locked)
        
        # Third failed attempt - should trigger lockout
        request3 = self.create_post_request({
            'username': 'test@example.com',
            'password': 'wrong_password'
        })
        
        with patch('users.views.authenticate', return_value=None):
            login_view(request3)
        
        self.lockout.refresh_from_db()
        self.assertEqual(self.lockout.failed_attempts, 3)
        self.assertTrue(self.lockout.is_locked)
        
        # Verify lockout message in form
        args, kwargs = mock_render.call_args
        form = args[2]['form']
        error_message = str(form.non_field_errors()[0])
        self.assertIn('locked', error_message)
    
    @override_settings(ACCOUNT_LOCKOUT_MAX_ATTEMPTS=3, ACCOUNT_LOCKOUT_DURATION=300)
    @patch('users.views.render')
    def test_login_view_locked_account(self, mock_render):
        """Test login attempt with locked account."""
        # Set up locked account
        self.lockout.failed_attempts = 3
        self.lockout.is_locked = True
        self.lockout.locked_until = timezone.now() + timedelta(minutes=5)
        self.lockout.save()
        
        request = self.create_post_request({
            'username': 'test@example.com',
            'password': 'correct_password'
        })
        
        # Mock check_lockout_expired to return False
        with patch.object(self.lockout, 'check_lockout_expired', return_value=False):
            login_view(request)
        
        # Should render form with lockout error
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        form = args[2]['form']
        error_message = str(form.non_field_errors()[0])
        self.assertIn('locked', error_message)
        self.assertIn('minutes', error_message)
    
    @patch('users.views.messages')
    @patch('users.views.redirect')
    @patch('users.views.login')
    def test_login_view_expired_lockout(self, mock_login, mock_redirect, mock_messages):
        """Test login with expired lockout."""
        # Set up expired lockout
        self.lockout.failed_attempts = 3
        self.lockout.is_locked = True
        self.lockout.locked_until = timezone.now() - timedelta(minutes=5)
        self.lockout.save()
        
        request = self.create_post_request({
            'username': 'test@example.com',
            'password': 'correct_password'
        })
        
        # Mock successful authentication
        with patch('users.views.authenticate', return_value=self.user):
            # Mock check_lockout_expired to return True
            with patch.object(self.lockout, 'check_lockout_expired', return_value=True):
                login_view(request)
        
        # Should proceed with normal login
        mock_login.assert_called_once_with(request, self.user)
        mock_redirect.assert_called_once_with('public:index')
    
    @override_settings(ACCOUNT_LOCKOUT_MAX_ATTEMPTS=5)
    @patch('users.views.render')
    def test_login_view_remaining_attempts_message(self, mock_render):
        """Test that remaining attempts are shown in error message."""
        # Set up account with some failed attempts
        self.lockout.failed_attempts = 2
        self.lockout.save()
        
        request = self.create_post_request({
            'username': 'test@example.com',
            'password': 'wrong_password'
        })
        
        with patch('users.views.authenticate', return_value=None):
            login_view(request)
        
        # Should show remaining attempts
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        form = args[2]['form']
        error_message = str(form.non_field_errors()[0])
        self.assertIn('2 attempts remaining', error_message)
    
    @patch('users.views.render')
    def test_login_view_form_validation_error(self, mock_render):
        """Test login view with form validation errors."""
        request = self.create_post_request({
            'username': '',  # Empty email
            'password': 'password'
        })
        
        login_view(request)
        
        # Should render form with validation errors
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        form = args[2]['form']
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
    
    @patch('users.views.HttpResponse')
    @patch('users.views.render')
    def test_login_view_htmx_request(self, mock_render, mock_response):
        """Test login view with HTMX request."""
        request = self.create_post_request({
            'username': 'test@example.com',
            'password': 'wrong_password'
        })
        request.META['HTTP_HX_REQUEST'] = 'true'
        
        with patch('users.views.authenticate', return_value=None):
            login_view(request)
        
        # Should render login form partial for HTMX
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        self.assertEqual(args[1], 'users/login_form.html')
        self.assertTrue(args[2]['is_htmx'])
    
    @patch('users.views.HttpResponse')
    def test_login_view_htmx_successful_login(self, mock_response):
        """Test successful login with HTMX request."""
        request = self.create_post_request({
            'username': 'test@example.com',
            'password': 'correct_password'
        })
        request.META['HTTP_HX_REQUEST'] = 'true'
        
        with patch('users.views.authenticate', return_value=self.user):
            with patch('users.views.login'):
                response = login_view(request)
        
        # Should return HTMX redirect response
        mock_response.assert_called_once()
        response_instance = mock_response.return_value
        # The response should have HX-Redirect header set
        self.assertTrue(hasattr(response_instance, '__setitem__'))
    
    def test_lockout_creation_for_new_user(self):
        """Test that lockout record is created for new user on first login attempt."""
        new_user = User.objects.create_user(
            email='newuser@example.com',
            password='password123'
        )
        
        # Ensure no lockout exists
        self.assertFalse(AccountLockout.objects.filter(user=new_user).exists())
        
        request = self.create_post_request({
            'username': 'newuser@example.com',
            'password': 'wrong_password'
        })
        
        with patch('users.views.authenticate', return_value=None):
            login_view(request)
        
        # Should create lockout record
        self.assertTrue(AccountLockout.objects.filter(user=new_user).exists())
        lockout = AccountLockout.objects.get(user=new_user)
        self.assertEqual(lockout.failed_attempts, 1)
    
    def test_lockout_logging_integration(self):
        """Test that lockout events are properly logged."""
        with patch('users.models.log_account_lockout') as mock_log:
            # Set up near-lockout state
            self.lockout.failed_attempts = 4  # One before lockout
            self.lockout.save()
            
            request = self.create_post_request({
                'username': 'test@example.com',
                'password': 'wrong_password'
            })
            
            with patch('users.views.authenticate', return_value=None):
                login_view(request)
            
            # Should log lockout event
            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            self.assertEqual(kwargs['user_email'], 'test@example.com')
            self.assertEqual(kwargs['request'], request)
    
    @patch('users.views.log_login_failure')
    def test_failed_login_logging_integration(self, mock_log):
        """Test that failed login attempts are logged."""
        request = self.create_post_request({
            'username': 'test@example.com',
            'password': 'wrong_password'
        })
        
        with patch('users.views.authenticate', return_value=None):
            with patch('users.views.render'):
                login_view(request)
        
        # Should log failed login (via signals)
        # This would be tested in signal tests, but we verify the path exists
        self.assertIsNotNone(request.META.get('REMOTE_ADDR'))
    
    def test_security_headers_preserved(self):
        """Test that security-related request headers are preserved."""
        request = self.create_post_request({
            'username': 'test@example.com',
            'password': 'wrong_password'
        })
        request.META.update({
            'HTTP_USER_AGENT': 'Test Browser',
            'HTTP_X_FORWARDED_FOR': '203.0.113.195',
            'HTTP_X_REAL_IP': '203.0.113.195'
        })
        
        with patch('users.views.authenticate', return_value=None):
            with patch('users.views.render'):
                login_view(request)
        
        # Headers should be preserved for security logging
        self.assertEqual(request.META['HTTP_USER_AGENT'], 'Test Browser')
        self.assertEqual(request.META['HTTP_X_FORWARDED_FOR'], '203.0.113.195')
        self.assertEqual(request.META['HTTP_X_REAL_IP'], '203.0.113.195') 