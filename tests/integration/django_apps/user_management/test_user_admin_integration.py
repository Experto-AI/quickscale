"""Migrated from template validation tests."""

"""Tests for user admin grouping functionality."""
import pytest
from django.test import TestCase, override_settings

# Set up template path and Django settings
from ..base import DjangoIntegrationTestCase, setup_django_template_path, setup_core_env_utils_mock, setup_django_settings
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()


@pytest.mark.django_component
@pytest.mark.integration
@override_settings(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    INSTALLED_APPS=[
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.sites',
        'django.contrib.messages',
        'users',
        'allauth',
        'allauth.account',
        'allauth.socialaccount',
    ]
)
class UserAdminGroupingTests(TestCase):
    """Test that admin classes are properly defined."""
    
    def test_admin_classes_exist(self):
        """Test that CustomUserAdmin and EmailAddressInline classes exist and can be imported."""
        try:
            from users.admin import CustomUserAdmin, EmailAddressInline
            
            # Test that classes exist
            self.assertTrue(hasattr(CustomUserAdmin, '__name__'))
            self.assertTrue(hasattr(EmailAddressInline, '__name__'))
            
            # Test that they are classes
            self.assertTrue(callable(CustomUserAdmin))
            self.assertTrue(callable(EmailAddressInline))
            
        except ImportError as e:
            self.fail(f"Failed to import admin classes: {e}")
    
    def test_email_address_inline_configuration(self):
        """Test EmailAddressInline has correct configuration attributes."""
        from users.admin import EmailAddressInline
        
        # Test that it has the expected attributes
        self.assertTrue(hasattr(EmailAddressInline, 'model'))
        self.assertTrue(hasattr(EmailAddressInline, 'extra'))
        self.assertTrue(hasattr(EmailAddressInline, 'readonly_fields'))
        self.assertTrue(hasattr(EmailAddressInline, 'fields'))
    
    def test_custom_user_admin_has_inlines(self):
        """Test CustomUserAdmin has inlines attribute."""
        from users.admin import CustomUserAdmin, EmailAddressInline
        
        # Test that it has inlines attribute
        self.assertTrue(hasattr(CustomUserAdmin, 'inlines'))
        
        # Test that EmailAddressInline is in inlines (if it's a class attribute)
        if hasattr(CustomUserAdmin, 'inlines'):
            self.assertIn(EmailAddressInline, CustomUserAdmin.inlines)