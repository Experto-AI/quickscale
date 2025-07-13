"""Tests for security event logging functionality."""
import json
import logging
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from allauth.account.signals import email_confirmed
from allauth.account.models import EmailAddress

from users.security_logger import (
    AuthenticationEventLogger,
    get_client_ip,
    log_login_success,
    log_logout,
    log_login_failure,
    log_account_lockout,
    log_account_unlock,
    log_password_change,
    log_email_verification
)
from users.signals import (
    log_successful_login,
    log_user_logout,
    log_failed_login_attempt,
    log_email_confirmation,
    log_user_creation
)

User = get_user_model()


class SecurityLoggerTestCase(TestCase):
    """Test case for security logging functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.request = self.factory.get('/')
        self.request.META = {
            'REMOTE_ADDR': '192.168.1.100',
            'HTTP_USER_AGENT': 'Test Browser',
            'HTTP_X_FORWARDED_FOR': '203.0.113.195, 192.168.1.100',
            'HTTP_X_REAL_IP': '203.0.113.195'
        }
        self.request.session = {'session_key': 'test_session_key'}
        self.request.path = '/test-path/'
        self.request.method = 'GET'
    
    def test_get_client_ip_with_forwarded_for(self):
        """Test IP extraction with X-Forwarded-For header."""
        ip = get_client_ip(self.request)
        self.assertEqual(ip, '203.0.113.195')
    
    def test_get_client_ip_with_real_ip(self):
        """Test IP extraction with X-Real-IP header."""
        # Remove X-Forwarded-For to test X-Real-IP fallback
        del self.request.META['HTTP_X_FORWARDED_FOR']
        ip = get_client_ip(self.request)
        self.assertEqual(ip, '203.0.113.195')
    
    def test_get_client_ip_with_remote_addr(self):
        """Test IP extraction with REMOTE_ADDR fallback."""
        # Remove proxy headers to test REMOTE_ADDR fallback
        del self.request.META['HTTP_X_FORWARDED_FOR']
        del self.request.META['HTTP_X_REAL_IP']
        ip = get_client_ip(self.request)
        self.assertEqual(ip, '192.168.1.100')
    
    def test_get_client_ip_unknown(self):
        """Test IP extraction when no IP available."""
        # Remove all IP headers
        del self.request.META['HTTP_X_FORWARDED_FOR']
        del self.request.META['HTTP_X_REAL_IP']
        del self.request.META['REMOTE_ADDR']
        ip = get_client_ip(self.request)
        self.assertEqual(ip, 'unknown')
    
    @patch('users.security_logger.security_logger')
    def test_authentication_event_logger_with_request(self, mock_logger):
        """Test logging security events with request context."""
        AuthenticationEventLogger.log_security_event(
            event_type='TEST_EVENT',
            user_email='test@example.com',
            request=self.request,
            details={'test': 'data'}
        )
        
        # Verify logger was called
        mock_logger.info.assert_called_once()
        
        # Parse the logged JSON to verify content
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        self.assertEqual(logged_data['event_type'], 'TEST_EVENT')
        self.assertEqual(logged_data['user_email'], 'test@example.com')
        self.assertEqual(logged_data['ip_address'], '203.0.113.195')
        self.assertEqual(logged_data['user_agent'], 'Test Browser')
        self.assertEqual(logged_data['path'], '/test-path/')
        self.assertEqual(logged_data['method'], 'GET')
        self.assertEqual(logged_data['details']['test'], 'data')
        self.assertIn('timestamp', logged_data)
    
    @patch('users.security_logger.security_logger')
    def test_authentication_event_logger_without_request(self, mock_logger):
        """Test logging security events without request context."""
        AuthenticationEventLogger.log_security_event(
            event_type='TEST_EVENT',
            user_email='test@example.com',
            request=None,
            details={'test': 'data'}
        )
        
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        self.assertEqual(logged_data['event_type'], 'TEST_EVENT')
        self.assertEqual(logged_data['user_email'], 'test@example.com')
        self.assertEqual(logged_data['details']['test'], 'data')
        # Should not have request-specific fields
        self.assertNotIn('ip_address', logged_data)
        self.assertNotIn('user_agent', logged_data)
    
    @patch('users.security_logger.security_logger')
    def test_log_login_success(self, mock_logger):
        """Test successful login logging."""
        log_login_success('test@example.com', self.request, 123, True)
        
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        self.assertEqual(logged_data['event_type'], 'LOGIN_SUCCESS')
        self.assertEqual(logged_data['details']['user_id'], 123)
        self.assertEqual(logged_data['details']['is_staff'], True)
        self.assertEqual(logged_data['details']['login_method'], 'email_password')
    
    @patch('users.security_logger.security_logger')
    def test_log_login_failure(self, mock_logger):
        """Test failed login logging."""
        log_login_failure('test@example.com', self.request, 'invalid_credentials')
        
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        self.assertEqual(logged_data['event_type'], 'LOGIN_FAILED')
        self.assertEqual(logged_data['details']['failure_reason'], 'invalid_credentials')
        self.assertEqual(logged_data['details']['login_method'], 'email_password')
    
    @patch('users.security_logger.security_logger')
    def test_log_logout(self, mock_logger):
        """Test logout logging."""
        log_logout('test@example.com', self.request, 123)
        
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        self.assertEqual(logged_data['event_type'], 'LOGOUT')
        self.assertEqual(logged_data['details']['user_id'], 123)
        self.assertEqual(logged_data['details']['logout_method'], 'manual')
    
    @patch('users.security_logger.security_logger')
    def test_log_account_lockout(self, mock_logger):
        """Test account lockout logging."""
        log_account_lockout('test@example.com', self.request, 300, 5)
        
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        self.assertEqual(logged_data['event_type'], 'ACCOUNT_LOCKED')
        self.assertEqual(logged_data['details']['lockout_duration_seconds'], 300)
        self.assertEqual(logged_data['details']['failed_attempts'], 5)
        self.assertEqual(logged_data['details']['security_action'], 'automatic_lockout')
    
    @patch('users.security_logger.security_logger')
    def test_log_account_unlock(self, mock_logger):
        """Test account unlock logging."""
        log_account_unlock('test@example.com', 123, 'manual_admin')
        
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        self.assertEqual(logged_data['event_type'], 'ACCOUNT_UNLOCKED')
        self.assertEqual(logged_data['details']['user_id'], 123)
        self.assertEqual(logged_data['details']['unlock_method'], 'manual_admin')
        self.assertEqual(logged_data['details']['security_action'], 'account_restored')
    
    @patch('users.security_logger.security_logger')
    def test_log_password_change(self, mock_logger):
        """Test password change logging."""
        log_password_change('test@example.com', self.request, 123, 'user_initiated')
        
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        self.assertEqual(logged_data['event_type'], 'PASSWORD_CHANGED')
        self.assertEqual(logged_data['details']['user_id'], 123)
        self.assertEqual(logged_data['details']['change_method'], 'user_initiated')
        self.assertEqual(logged_data['details']['security_action'], 'credential_update')
    
    @patch('users.security_logger.security_logger')
    def test_log_email_verification(self, mock_logger):
        """Test email verification logging."""
        log_email_verification('test@example.com', self.request, 123, 'confirmed')
        
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])
        
        self.assertEqual(logged_data['event_type'], 'EMAIL_VERIFICATION')
        self.assertEqual(logged_data['details']['user_id'], 123)
        self.assertEqual(logged_data['details']['verification_status'], 'confirmed')
        self.assertEqual(logged_data['details']['security_action'], 'email_confirmed')


class SecuritySignalsTestCase(TestCase):
    """Test case for security logging signal handlers."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.request = self.factory.get('/')
        self.request.META = {'REMOTE_ADDR': '192.168.1.100'}
        self.request.session = {}
    
    @patch('users.signals.log_login_success')
    def test_user_logged_in_signal(self, mock_log):
        """Test user_logged_in signal handler."""
        # Trigger the signal
        user_logged_in.send(sender=User, request=self.request, user=self.user)
        
        # Verify the logging function was called
        mock_log.assert_called_once_with(
            user_email=self.user.email,
            request=self.request,
            user_id=self.user.id,
            is_staff=self.user.is_staff
        )
    
    @patch('users.signals.log_logout')
    def test_user_logged_out_signal(self, mock_log):
        """Test user_logged_out signal handler."""
        # Trigger the signal
        user_logged_out.send(sender=User, request=self.request, user=self.user)
        
        # Verify the logging function was called
        mock_log.assert_called_once_with(
            user_email=self.user.email,
            request=self.request,
            user_id=self.user.id
        )
    
    @patch('users.signals.log_logout')
    def test_user_logged_out_signal_no_user(self, mock_log):
        """Test user_logged_out signal handler with no user."""
        # Trigger the signal with None user
        user_logged_out.send(sender=User, request=self.request, user=None)
        
        # Verify the logging function was not called
        mock_log.assert_not_called()
    
    @patch('users.signals.log_login_failure')
    def test_user_login_failed_signal(self, mock_log):
        """Test user_login_failed signal handler."""
        credentials = {'login': 'test@example.com', 'password': 'wrong'}
        
        # Trigger the signal
        user_login_failed.send(
            sender=User, 
            credentials=credentials, 
            request=self.request
        )
        
        # Verify the logging function was called
        mock_log.assert_called_once_with(
            user_email='test@example.com',
            request=self.request,
            reason='invalid_credentials'
        )
    
    @patch('users.signals.log_login_failure')
    def test_user_login_failed_signal_email_fallback(self, mock_log):
        """Test user_login_failed signal handler with email fallback."""
        credentials = {'email': 'test@example.com', 'password': 'wrong'}
        
        # Trigger the signal
        user_login_failed.send(
            sender=User, 
            credentials=credentials, 
            request=self.request
        )
        
        # Verify the logging function was called
        mock_log.assert_called_once_with(
            user_email='test@example.com',
            request=self.request,
            reason='invalid_credentials'
        )
    
    @patch('users.signals.log_login_failure')
    def test_user_login_failed_signal_unknown_email(self, mock_log):
        """Test user_login_failed signal handler with unknown email."""
        credentials = {'password': 'wrong'}
        
        # Trigger the signal
        user_login_failed.send(
            sender=User, 
            credentials=credentials, 
            request=self.request
        )
        
        # Verify the logging function was called with unknown email
        mock_log.assert_called_once_with(
            user_email='unknown',
            request=self.request,
            reason='invalid_credentials'
        )
    
    @patch('users.signals.log_email_verification')
    def test_email_confirmed_signal(self, mock_log):
        """Test email_confirmed signal handler."""
        # Create email address
        email_address = EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            verified=True,
            primary=True
        )
        
        # Trigger the signal
        email_confirmed.send(
            sender=EmailAddress,
            request=self.request,
            email_address=email_address
        )
        
        # Verify the logging function was called
        mock_log.assert_called_once_with(
            user_email=email_address.email,
            request=self.request,
            user_id=email_address.user.id,
            verification_status='confirmed'
        )
    
    @patch('users.signals.log_email_verification')
    def test_email_confirmed_signal_no_user(self, mock_log):
        """Test email_confirmed signal handler with no user."""
        # Create email address without user
        email_address = EmailAddress(email='test@example.com', verified=True)
        
        # Trigger the signal
        email_confirmed.send(
            sender=EmailAddress,
            request=self.request,
            email_address=email_address
        )
        
        # Verify the logging function was not called
        mock_log.assert_not_called()
    
    @patch('users.security_logger.AuthenticationEventLogger.log_security_event')
    def test_user_creation_signal(self, mock_log):
        """Test user creation signal handler."""
        # Create a new user to trigger post_save signal
        new_user = User.objects.create_user(
            email='newuser@example.com',
            password='testpass123'
        )
        
        # Verify the logging function was called
        mock_log.assert_called_once_with(
            event_type='ACCOUNT_CREATED',
            user_email=new_user.email,
            request=None,
            details={
                'user_id': new_user.id,
                'is_staff': new_user.is_staff,
                'is_active': new_user.is_active,
                'security_action': 'new_account'
            }
        ) 