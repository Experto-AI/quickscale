"""Tests for Django user models and utilities."""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

# Set up Django for testing
from ..base import (
    DjangoModelTestCase,
    setup_core_env_utils_mock,
    setup_django_settings,
    setup_django_template_path,
)

# Set up template path and environment
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()

# Import Django and initialize
import django

django.setup()

User = get_user_model()


@pytest.mark.django_component
@pytest.mark.unit
class UserModelTests(DjangoModelTestCase):
    """Unit tests for user models."""
    
    def test_user_creation(self):
        """Test creating a regular user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('testpass123'))
    
    def test_superuser_creation(self):
        """Test creating a superuser."""
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.assertEqual(admin.email, 'admin@example.com')
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password('adminpass123'))
    
    def test_user_str_representation(self):
        """Test string representation of user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.assertEqual(str(user), 'test@example.com')
    
    def test_user_email_uniqueness(self):
        """Test that user emails must be unique."""
        User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        with self.assertRaises(Exception):
            User.objects.create_user(
                email='test@example.com',
                password='anotherpass123'
            )


@pytest.mark.django_component
@pytest.mark.unit  
class CreateDefaultUsersCommandTests(DjangoModelTestCase):
    """Unit tests for create_default_users management command."""
    
    def test_command_creates_users(self):
        """Test that the command creates default users correctly."""
        # Ensure users don't exist
        User.objects.all().delete()
        
        # Call the command
        out = StringIO()
        call_command('create_default_users', stdout=out)
        output = out.getvalue()
        
        # Check output
        self.assertIn('Created regular user', output)
        self.assertIn('Created admin user', output)
        
        # Check that users were created
        user = User.objects.get(email='user@test.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('userpasswd'))
        
        admin = User.objects.get(email='admin@test.com')
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password('adminpasswd'))
    
    def test_command_skips_existing_users(self):
        """Test that the command skips users that already exist."""
        # Create users first
        User.objects.create_user(email='user@test.com', password='existing')
        User.objects.create_superuser(email='admin@test.com', password='existing')
        
        # Call the command
        out = StringIO()
        call_command('create_default_users', stdout=out)
        output = out.getvalue()
        
        # Check output indicates users already exist
        self.assertIn('already exists', output)
        
        # Verify passwords weren't changed
        user = User.objects.get(email='user@test.com')
        admin = User.objects.get(email='admin@test.com')
        
        self.assertTrue(user.check_password('existing'))
        self.assertTrue(admin.check_password('existing'))
