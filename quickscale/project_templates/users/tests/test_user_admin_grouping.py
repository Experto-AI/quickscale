"""Tests for user admin grouping functionality."""
from django.test import TestCase
from django.contrib import admin
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

from users.admin import CustomUserAdmin, EmailAddressInline

User = get_user_model()


class UserAdminGroupingTest(TestCase):
    """Test that EmailAddress is properly grouped with CustomUser in admin."""
    
    def test_email_address_not_registered_separately(self):
        """EmailAddress should not be registered as a separate admin model."""
        # EmailAddress should not be in the registered models list
        self.assertNotIn(EmailAddress, admin.site._registry)
    
    def test_custom_user_admin_has_email_inline(self):
        """CustomUser admin should include EmailAddress as an inline."""
        user_admin = admin.site._registry[User]
        self.assertIsInstance(user_admin, CustomUserAdmin)
        self.assertIn(EmailAddressInline, user_admin.inlines)
    
    def test_email_address_inline_configuration(self):
        """EmailAddressInline should have correct configuration."""
        inline = EmailAddressInline(EmailAddress, admin.site)
        
        # Check basic configuration
        self.assertEqual(inline.model, EmailAddress)
        self.assertEqual(inline.extra, 0)
        self.assertIn('verified', inline.readonly_fields)
        self.assertIn('primary', inline.readonly_fields)
        self.assertEqual(inline.fields, ('email', 'verified', 'primary'))
    
    def test_custom_user_admin_includes_email_status(self):
        """CustomUser admin should display email verification status."""
        user_admin = admin.site._registry[User]
        self.assertIn('email_verified_status', user_admin.list_display)
    
    def test_email_verified_status_method(self):
        """Test the email_verified_status method works correctly."""
        # Create test user
        user = User.objects.create_user(
            email='test@example.com',
            password='testpassword'
        )
        
        # Create EmailAddress record
        email_address = EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=True,
            primary=True
        )
        
        user_admin = admin.site._registry[User]
        status = user_admin.email_verified_status(user)
        self.assertEqual(status, '✓ Verified')
        
        # Test unverified status
        email_address.verified = False
        email_address.save()
        status = user_admin.email_verified_status(user)
        self.assertEqual(status, '✗ Unverified')
        
        # Test no email record
        email_address.delete()
        status = user_admin.email_verified_status(user)
        self.assertEqual(status, '? No record')
    
    def test_admin_fieldsets_include_all_user_fields(self):
        """Admin fieldsets should include all CustomUser model fields."""
        user_admin = admin.site._registry[User]
        
        # Collect all fields from fieldsets
        all_fields = []
        for fieldset in user_admin.fieldsets:
            all_fields.extend(fieldset[1]['fields'])
        
        # Check that key user fields are included
        expected_fields = [
            'email', 'password', 'first_name', 'last_name', 'bio',
            'phone_number', 'profile_picture', 'job_title', 'company',
            'website', 'location', 'twitter', 'linkedin', 'github',
            'email_notifications', 'is_active', 'is_staff', 'is_superuser'
        ]
        
        for field in expected_fields:
            self.assertIn(field, all_fields, f"Field '{field}' missing from admin fieldsets") 