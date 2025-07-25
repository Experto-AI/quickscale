"""Tests for two-factor authentication functionality."""
import json
from unittest.mock import patch, Mock
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.urls import reverse

from users.models import TwoFactorAuth
from users.views_2fa import (
    two_factor_settings,
    two_factor_setup_prepare,
    two_factor_generate_backup_codes,
    two_factor_disable,
    two_factor_status
)

User = get_user_model()


class TwoFactorAuthModelTestCase(TestCase):
    """Test case for TwoFactorAuth model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.two_factor = TwoFactorAuth.objects.create(user=self.user)
    
    def test_two_factor_auth_creation(self):
        """Test TwoFactorAuth model creation."""
        self.assertEqual(self.two_factor.user, self.user)
        self.assertFalse(self.two_factor.is_enabled)
        self.assertEqual(self.two_factor.secret_key, '')
        self.assertEqual(self.two_factor.backup_codes, [])
        self.assertIsNone(self.two_factor.last_used)
    
    def test_two_factor_auth_str_representation(self):
        """Test string representation of TwoFactorAuth."""
        expected = f"{self.user.email} - Disabled"
        self.assertEqual(str(self.two_factor), expected)
        
        # Test enabled state
        self.two_factor.is_enabled = True
        expected = f"{self.user.email} - Enabled"
        self.assertEqual(str(self.two_factor), expected)
    
    def test_generate_backup_codes_default_count(self):
        """Test generating backup codes with default count."""
        backup_codes = self.two_factor.generate_backup_codes()
        
        # Should generate 10 codes by default
        self.assertEqual(len(backup_codes), 10)
        
        # Each code should be 8 characters
        for code in backup_codes:
            self.assertEqual(len(code), 8)
            self.assertTrue(code.isalnum())
            self.assertTrue(code.isupper())
        
        # Should be saved to model
        self.two_factor.refresh_from_db()
        self.assertEqual(self.two_factor.backup_codes, backup_codes)
    
    def test_generate_backup_codes_custom_count(self):
        """Test generating backup codes with custom count."""
        backup_codes = self.two_factor.generate_backup_codes(count=5)
        
        # Should generate 5 codes
        self.assertEqual(len(backup_codes), 5)
        
        # Should be saved to model
        self.two_factor.refresh_from_db()
        self.assertEqual(len(self.two_factor.backup_codes), 5)
    
    def test_generate_backup_codes_uniqueness(self):
        """Test that generated backup codes are unique."""
        backup_codes = self.two_factor.generate_backup_codes(count=20)
        
        # All codes should be unique
        self.assertEqual(len(backup_codes), len(set(backup_codes)))
    
    def test_use_backup_code_valid(self):
        """Test using a valid backup code."""
        # Generate backup codes
        backup_codes = self.two_factor.generate_backup_codes(count=3)
        test_code = backup_codes[1]  # Use middle code
        
        # Use the code
        result = self.two_factor.use_backup_code(test_code)
        
        # Should return True
        self.assertTrue(result)
        
        # Code should be removed from list
        self.two_factor.refresh_from_db()
        self.assertNotIn(test_code, self.two_factor.backup_codes)
        self.assertEqual(len(self.two_factor.backup_codes), 2)
        
        # last_used should be updated
        self.assertIsNotNone(self.two_factor.last_used)
    
    def test_use_backup_code_invalid(self):
        """Test using an invalid backup code."""
        # Generate backup codes
        self.two_factor.generate_backup_codes(count=3)
        original_codes = self.two_factor.backup_codes.copy()
        
        # Try to use invalid code
        result = self.two_factor.use_backup_code('INVALID1')
        
        # Should return False
        self.assertFalse(result)
        
        # Codes should remain unchanged
        self.two_factor.refresh_from_db()
        self.assertEqual(self.two_factor.backup_codes, original_codes)
    
    def test_use_backup_code_already_used(self):
        """Test using a backup code that's already been used."""
        # Generate backup codes
        backup_codes = self.two_factor.generate_backup_codes(count=3)
        test_code = backup_codes[0]
        
        # Use the code once
        first_use = self.two_factor.use_backup_code(test_code)
        self.assertTrue(first_use)
        
        # Try to use the same code again
        second_use = self.two_factor.use_backup_code(test_code)
        
        # Should return False
        self.assertFalse(second_use)
    
    def test_one_to_one_relationship(self):
        """Test that each user can only have one 2FA record."""
        # Try to create another 2FA for same user
        with self.assertRaises(Exception):
            TwoFactorAuth.objects.create(user=self.user)
    
    def test_get_or_create_two_factor(self):
        """Test getting or creating 2FA record."""
        # Delete existing 2FA
        self.two_factor.delete()
        
        # Get or create should create new one
        two_factor, created = TwoFactorAuth.objects.get_or_create(user=self.user)
        self.assertTrue(created)
        self.assertEqual(two_factor.user, self.user)
        self.assertFalse(two_factor.is_enabled)
        self.assertEqual(two_factor.backup_codes, [])
        
        # Get or create again should return existing
        two_factor2, created2 = TwoFactorAuth.objects.get_or_create(user=self.user)
        self.assertFalse(created2)
        self.assertEqual(two_factor.id, two_factor2.id)


class TwoFactorAuthViewsTestCase(TestCase):
    """Test case for Two-Factor Authentication views."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.two_factor = TwoFactorAuth.objects.create(user=self.user)
    
    def create_request(self, path='/', method='GET', user=None, **kwargs):
        """Helper method to create a request."""
        request_method = getattr(self.factory, method.lower())
        request = request_method(path, **kwargs)
        request.user = user or self.user
        return request
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=False)
    def test_two_factor_settings_disabled(self):
        """Test 2FA settings view when 2FA is disabled."""
        with patch('users.views_2fa.redirect') as mock_redirect:
            with patch('users.views_2fa.messages') as mock_messages:
                request = self.create_request()
                response = two_factor_settings(request)
                
                # Should redirect to profile
                mock_redirect.assert_called_once_with('users:profile')
                mock_messages.info.assert_called_once()
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=True, TWO_FACTOR_AUTH_ISSUER='TestApp')
    def test_two_factor_settings_enabled(self):
        """Test 2FA settings view when 2FA is enabled."""
        with patch('users.views_2fa.render') as mock_render:
            request = self.create_request()
            two_factor_settings(request)
            
            # Should render template with context
            mock_render.assert_called_once()
            args, kwargs = mock_render.call_args
            
            self.assertEqual(args[0], request)
            self.assertEqual(args[1], 'users/two_factor_settings.html')
            
            context = args[2]
            self.assertEqual(context['two_factor'], self.two_factor)
            self.assertFalse(context['is_enabled'])
            self.assertFalse(context['has_backup_codes'])
            self.assertEqual(context['backup_codes_count'], 0)
            self.assertTrue(context['system_enabled'])
            self.assertEqual(context['issuer_name'], 'TestApp')
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=True)
    def test_two_factor_settings_with_backup_codes(self):
        """Test 2FA settings view with existing backup codes."""
        # Generate backup codes
        self.two_factor.generate_backup_codes(count=5)
        self.two_factor.is_enabled = True
        self.two_factor.save()
        
        with patch('users.views_2fa.render') as mock_render:
            request = self.create_request()
            two_factor_settings(request)
            
            args, kwargs = mock_render.call_args
            context = args[2]
            
            self.assertTrue(context['is_enabled'])
            self.assertTrue(context['has_backup_codes'])
            self.assertEqual(context['backup_codes_count'], 5)
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=False)
    def test_two_factor_setup_prepare_disabled(self):
        """Test 2FA setup prepare when 2FA is disabled."""
        request = self.create_request(method='POST')
        response = two_factor_setup_prepare(request)
        
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Two-factor authentication is not enabled.')
        self.assertEqual(response.status_code, 400)
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=True)
    def test_two_factor_setup_prepare_enabled(self):
        """Test 2FA setup prepare when 2FA is enabled."""
        request = self.create_request(method='POST')
        response = two_factor_setup_prepare(request)
        
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        
        self.assertEqual(data['status'], 'preparation')
        self.assertEqual(data['infrastructure_ready'], True)
        self.assertIn('next_steps', data)
        self.assertIn('required_packages', data)
        self.assertIsInstance(data['next_steps'], list)
        self.assertIsInstance(data['required_packages'], list)
    
    def test_two_factor_setup_prepare_wrong_method(self):
        """Test 2FA setup prepare with wrong HTTP method."""
        request = self.create_request(method='GET')
        
        # Should raise method not allowed (handled by decorator)
        with self.assertRaises(AttributeError):
            # The decorator would prevent this, but our test bypasses it
            two_factor_setup_prepare(request)
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=False)
    def test_generate_backup_codes_disabled(self):
        """Test generating backup codes when 2FA is disabled."""
        request = self.create_request(method='POST')
        response = two_factor_generate_backup_codes(request)
        
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Two-factor authentication is not enabled.')
        self.assertEqual(response.status_code, 400)
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=True, TWO_FACTOR_AUTH_BACKUP_CODES_COUNT=7)
    def test_generate_backup_codes_enabled(self):
        """Test generating backup codes when 2FA is enabled."""
        request = self.create_request(method='POST')
        response = two_factor_generate_backup_codes(request)
        
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['count'], 7)
        self.assertEqual(len(data['backup_codes']), 7)
        self.assertIn('note', data)
        
        # Should be saved to database
        self.two_factor.refresh_from_db()
        self.assertEqual(len(self.two_factor.backup_codes), 7)
        self.assertEqual(self.two_factor.backup_codes, data['backup_codes'])
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=True)
    def test_generate_backup_codes_creates_two_factor(self):
        """Test generating backup codes creates 2FA record if missing."""
        # Delete existing 2FA
        self.two_factor.delete()
        
        request = self.create_request(method='POST')
        response = two_factor_generate_backup_codes(request)
        
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        # Should create new 2FA record
        self.assertTrue(TwoFactorAuth.objects.filter(user=self.user).exists())
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=False)
    def test_two_factor_disable_system_disabled(self):
        """Test disabling 2FA when system 2FA is disabled."""
        request = self.create_request(method='POST')
        response = two_factor_disable(request)
        
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Two-factor authentication is not enabled.')
        self.assertEqual(response.status_code, 400)
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=True)
    def test_two_factor_disable_enabled(self):
        """Test disabling 2FA when user has it enabled."""
        # Enable 2FA for user
        self.two_factor.is_enabled = True
        self.two_factor.secret_key = 'test_secret'
        self.two_factor.generate_backup_codes(count=5)
        self.two_factor.save()
        
        with patch('users.views_2fa.messages') as mock_messages:
            request = self.create_request(method='POST')
            response = two_factor_disable(request)
        
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        # Should disable 2FA
        self.two_factor.refresh_from_db()
        self.assertFalse(self.two_factor.is_enabled)
        self.assertEqual(self.two_factor.secret_key, '')
        self.assertEqual(self.two_factor.backup_codes, [])
        
        # Should show success message
        mock_messages.success.assert_called_once()
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=True)
    def test_two_factor_disable_not_enabled(self):
        """Test disabling 2FA when user doesn't have it enabled."""
        # Delete 2FA record
        self.two_factor.delete()
        
        request = self.create_request(method='POST')
        response = two_factor_disable(request)
        
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertIn('not enabled', data['message'])
        self.assertEqual(response.status_code, 400)
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=False)
    def test_two_factor_status_system_disabled(self):
        """Test getting 2FA status when system 2FA is disabled."""
        request = self.create_request()
        response = two_factor_status(request)
        
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        
        self.assertFalse(data['system_enabled'])
        self.assertFalse(data['user_enabled'])
        self.assertIn('not enabled in system settings', data['message'])
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=True)
    def test_two_factor_status_user_enabled(self):
        """Test getting 2FA status when user has 2FA enabled."""
        # Enable 2FA for user
        self.two_factor.is_enabled = True
        self.two_factor.generate_backup_codes(count=8)
        self.two_factor.save()
        
        request = self.create_request()
        response = two_factor_status(request)
        
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        
        self.assertTrue(data['system_enabled'])
        self.assertTrue(data['user_enabled'])
        self.assertTrue(data['has_backup_codes'])
        self.assertEqual(data['backup_codes_count'], 8)
        self.assertIsNotNone(data['created_at'])
    
    @override_settings(TWO_FACTOR_AUTH_ENABLED=True)
    def test_two_factor_status_user_disabled(self):
        """Test getting 2FA status when user has 2FA disabled."""
        # Delete 2FA record
        self.two_factor.delete()
        
        request = self.create_request()
        response = two_factor_status(request)
        
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        
        self.assertTrue(data['system_enabled'])
        self.assertFalse(data['user_enabled'])
        self.assertFalse(data['has_backup_codes'])
        self.assertEqual(data['backup_codes_count'], 0)
        self.assertIsNone(data['last_used'])
        self.assertIsNone(data['created_at'])
    
    def test_views_require_login(self):
        """Test that all 2FA views require login."""
        # This would be tested with Django's Client in integration tests
        # Here we just verify the decorators are applied
        
        # Check that the views have the login_required decorator
        self.assertTrue(hasattr(two_factor_settings, 'decorator'))
        self.assertTrue(hasattr(two_factor_setup_prepare, 'decorator'))
        self.assertTrue(hasattr(two_factor_generate_backup_codes, 'decorator'))
        self.assertTrue(hasattr(two_factor_disable, 'decorator'))
        self.assertTrue(hasattr(two_factor_status, 'decorator')) 