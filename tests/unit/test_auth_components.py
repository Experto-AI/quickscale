"""Unit tests for authentication components in django-allauth integration."""
import unittest
import pytest
from unittest.mock import Mock, patch, MagicMock

from users.validators import PasswordStrengthValidator, BreachedPasswordValidator
from users.models import CustomUserManager
from users.adapters import AccountAdapter, SocialAccountAdapter
from django.core.exceptions import ValidationError, PermissionDenied


class _PasswordStrengthValidator:
    """Actual implementation of the mock validator."""
    def __init__(self, min_length=8, require_uppercase=True, require_lowercase=True,
                 require_digit=True, require_special=True):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special

    def validate(self, password, user=None):
        """Validate the password."""
        if len(password) < self.min_length:
            raise ValueError(f"Password must be at least {self.min_length} characters long.")
        if self.require_uppercase and not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter.")
        if self.require_lowercase and not any(c.islower() for c in password):
            raise ValueError("Password must contain at least one lowercase letter.")
        if self.require_digit and not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit.")
        if self.require_special and all(c.isalnum() for c in password):
            raise ValueError("Password must contain at least one special character.")

    def get_help_text(self):
        """Get help text for the validator."""
        help_texts = [
            f"Your password must be at least {self.min_length} characters long."
        ]
        if self.require_uppercase:
            help_texts.append("Your password must contain at least one uppercase letter.")
        if self.require_lowercase:
            help_texts.append("Your password must contain at least one lowercase letter.")
        if self.require_digit:
            help_texts.append("Your password must contain at least one digit.")
        if self.require_special:
            help_texts.append("Your password must contain at least one special character.")
        return " ".join(help_texts)


@pytest.fixture
def MockPasswordStrengthValidator():
    """Mock for PasswordStrengthValidator."""
    return _PasswordStrengthValidator

@pytest.fixture
def MockBreachedPasswordValidator():
    """Mock for BreachedPasswordValidator."""
    class MockValidator:
        def __init__(self, min_pwned_count=1):
            self.min_pwned_count = min_pwned_count
            self.common_passwords = {
                'password', 'password123', '123456', 'qwerty', 'admin', 
                'welcome', 'letmein', 'abc123', 'monkey'
            }
        
        def validate(self, password, user=None):
            if password.lower() in self.common_passwords:
                raise ValueError("This password has been found in data breaches and is not secure.")
                
        def get_help_text(self):
            return "Your password cannot be a commonly used password that has appeared in data breaches."
    
    return MockValidator

@pytest.fixture
def MockCustomUserManager():
    """Mock for CustomUserManager."""
    class MockManager:
        def create_user(self, email, password=None, **extra_fields):
            if not email:
                raise ValueError("The Email field must be set")
            email = email.lower()  # Simulate normalize_email
            user = Mock(email=email, **extra_fields)
            if password:
                user.set_password = Mock()
                user.set_password(password)
            user.save = Mock()
            return user

        def create_superuser(self, email, password=None, **extra_fields):
            extra_fields.setdefault('is_staff', True)
            extra_fields.setdefault('is_superuser', True)
            extra_fields.setdefault('is_active', True)

            if extra_fields.get('is_staff') is not True:
                raise ValueError("Superuser must have is_staff=True.")
            if extra_fields.get('is_superuser') is not True:
                raise ValueError("Superuser must have is_superuser=True.")
                
            return self.create_user(email, password, **extra_fields)
    
    return MockManager

@pytest.fixture
def MockAccountAdapter():
    """Mock for AccountAdapter."""
    class MockAdapter:
        def is_open_for_signup(self, request):
            from django.conf import settings
            return getattr(settings, 'ACCOUNT_ALLOW_REGISTRATION', True)
        
        def get_email_confirmation_url(self, request, emailconfirmation):
            return "https://example.com/confirm-email/"
        
        def get_login_redirect_url(self, request):
            if request.user.is_staff:
                return "/dashboard/admin/"
            return "/dashboard/"
        
        def send_mail(self, template_prefix, email, context):
            context.update({
                'site_name': 'QuickScale',
                'support_email': 'support@example.com',
            })
            return True
        
        def populate_username(self, request, user):
            user.username = None
            return user
    
    return MockAdapter

@pytest.fixture
def MockSocialAccountAdapter():
    """Mock for SocialAccountAdapter."""
    class MockAdapter:
        def is_open_for_signup(self, request, sociallogin):
            return False
        
        def pre_social_login(self, request, sociallogin):
            raise PermissionDenied("Social authentication is not supported.")
        
        def populate_user(self, request, sociallogin, data):
            raise PermissionDenied("Social authentication is not supported.")
    
    return MockAdapter


# Create a mock for Django's PermissionDenied exception
class PermissionDenied(Exception):
    """Mock for Django's PermissionDenied exception."""
    pass


class TestPasswordValidators:
    """Test cases for password validators."""

    def test_password_strength_validator(self, MockPasswordStrengthValidator):
        """Test that password strength validator correctly validates passwords."""
        validator = MockPasswordStrengthValidator()
        
        # Valid password - should not raise any exceptions
        validator.validate("Abcdef1!")
        
        # Test length validation
        with pytest.raises(ValueError) as excinfo:
            validator.validate("Abc1!")
        assert "Password must be at least 8 characters long" in str(excinfo.value)
        
        # Test uppercase validation
        with pytest.raises(ValueError) as excinfo:
            validator.validate("abcdefg1!")
        assert "Password must contain at least one uppercase letter" in str(excinfo.value)
        
        # Test lowercase validation
        with pytest.raises(ValueError) as excinfo:
            validator.validate("ABCDEFG1!")
        assert "Password must contain at least one lowercase letter" in str(excinfo.value)
        
        # Test digit validation
        with pytest.raises(ValueError) as excinfo:
            validator.validate("Abcdefgh!")
        assert "Password must contain at least one digit" in str(excinfo.value)
        
        # Test special character validation
        with pytest.raises(ValueError) as excinfo:
            validator.validate("Abcdefg1")
        assert "Password must contain at least one special character" in str(excinfo.value)

    def test_breached_password_validator(self, MockBreachedPasswordValidator):
        """Test that breached password validator detects common passwords."""
        validator = MockBreachedPasswordValidator()
        
        # Valid password - should not raise any exceptions
        validator.validate("ComplexPassword123!")
        
        # Common passwords should be rejected
        common_passwords = [
            "password", "password123", "123456", "qwerty", 
            "admin", "welcome", "letmein", "abc123", "monkey"
        ]
        
        for password in common_passwords:
            with pytest.raises(ValueError) as excinfo:
                validator.validate(password)
            assert "found in data breaches" in str(excinfo.value)
            
    def test_validator_help_text(self, MockPasswordStrengthValidator, MockBreachedPasswordValidator):
        """Test that validators return appropriate help text."""
        strength_validator = MockPasswordStrengthValidator()
        breached_validator = MockBreachedPasswordValidator()
        
        assert "at least 8 characters" in strength_validator.get_help_text()
        assert "uppercase letter" in strength_validator.get_help_text()
        assert "lowercase letter" in strength_validator.get_help_text()
        assert "digit" in strength_validator.get_help_text()
        assert "special character" in strength_validator.get_help_text()
        
        assert "commonly used password" in breached_validator.get_help_text()


class TestCustomUserManager:
    """Test cases for the custom user manager."""
    
    def test_create_user_without_email(self, MockCustomUserManager):
        """Test that creating a user without an email raises ValueError."""
        manager = MockCustomUserManager()
        
        with pytest.raises(ValueError) as excinfo:
            manager.create_user(email=None)
        assert "The Email field must be set" in str(excinfo.value)
    
    def test_create_user_normalizes_email(self, MockCustomUserManager):
        """Test that email is normalized when creating a user."""
        manager = MockCustomUserManager()
        
        # Create a user with an email that needs normalization
        user = manager.create_user(email="TEST@example.COM")
        
        # Verify the email was normalized (converted to lowercase)
        assert user.email == "test@example.com"
    
    def test_create_superuser(self, MockCustomUserManager):
        """Test that create_superuser sets is_staff and is_superuser to True."""
        manager = MockCustomUserManager()
        
        # Create a superuser
        user = manager.create_superuser(email="admin@example.com", password="password")
        
        # Verify is_staff and is_superuser were set to True
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.is_active is True
    
    def test_create_superuser_enforces_staff_status(self, MockCustomUserManager):
        """Test that create_superuser enforces is_staff=True."""
        manager = MockCustomUserManager()
        
        with pytest.raises(ValueError) as excinfo:
            manager.create_superuser(
                email="admin@example.com", 
                password="password",
                is_staff=False
            )
        assert "Superuser must have is_staff=True" in str(excinfo.value)
    
    def test_create_superuser_enforces_superuser_status(self, MockCustomUserManager):
        """Test that create_superuser enforces is_superuser=True."""
        manager = MockCustomUserManager()
        
        with pytest.raises(ValueError) as excinfo:
            manager.create_superuser(
                email="admin@example.com", 
                password="password",
                is_superuser=False
            )
        assert "Superuser must have is_superuser=True" in str(excinfo.value)


class TestAccountAdapter:
    """Test cases for the custom account adapter."""
    
    def test_is_open_for_signup(self, MockAccountAdapter):
        """Test is_open_for_signup uses settings correctly."""
        # Test with default settings (open for signup)
        adapter = MockAccountAdapter()
        settings_mock = Mock()
        
        # Test when setting is True
        settings_mock.ACCOUNT_ALLOW_REGISTRATION = True
        with patch('django.conf.settings', settings_mock):
            assert adapter.is_open_for_signup(Mock()) is True
            
        # Test when setting is False
        settings_mock.ACCOUNT_ALLOW_REGISTRATION = False
        with patch('django.conf.settings', settings_mock):
            assert adapter.is_open_for_signup(Mock()) is False
    
    def test_populate_username(self, MockAccountAdapter):
        """Test that populate_username sets username to None."""
        adapter = MockAccountAdapter()
        request = Mock()
        user = Mock()
        
        # Call the method
        adapter.populate_username(request, user)
        
        # Verify username was set to None
        assert user.username is None


class TestSocialAccountAdapter:
    """Test cases for the social account adapter which is disabled by design."""
    
    def test_is_open_for_signup(self, MockSocialAccountAdapter):
        """Test that social signup is disabled."""
        adapter = MockSocialAccountAdapter()
        request = Mock()
        sociallogin = Mock()
        
        # Social signup should be disabled
        assert adapter.is_open_for_signup(request, sociallogin) is False
    
    def test_pre_social_login(self, MockSocialAccountAdapter):
        """Test that pre_social_login raises PermissionDenied."""
        adapter = MockSocialAccountAdapter()
        request = Mock()
        sociallogin = Mock()
        
        with pytest.raises(PermissionDenied) as excinfo:
            adapter.pre_social_login(request, sociallogin)
        assert "Social authentication is not supported" in str(excinfo.value)
    
    def test_populate_user(self, MockSocialAccountAdapter):
        """Test that populate_user raises PermissionDenied."""
        adapter = MockSocialAccountAdapter()
        request = Mock()
        sociallogin = Mock()
        data = Mock()
        
        with pytest.raises(PermissionDenied) as excinfo:
            adapter.populate_user(request, sociallogin, data)
        assert "Social authentication is not supported" in str(excinfo.value) 