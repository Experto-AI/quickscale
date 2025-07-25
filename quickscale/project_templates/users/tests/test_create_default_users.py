"""Tests for create_default_users management command."""
from io import StringIO
from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model

User = get_user_model()


class CreateDefaultUsersTest(TestCase):
    """Tests for create_default_users management command."""
    
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
        # Create users
        User.objects.create_user(email='user@test.com', password='differentpassword')
        User.objects.create_superuser(email='admin@test.com', password='differentpassword')
        
        # Call the command
        out = StringIO()
        call_command('create_default_users', stdout=out)
        output = out.getvalue()
        
        # Check output
        self.assertIn('Regular user already exists', output)
        self.assertIn('Admin user already exists', output)
        
        # Check that users weren't changed
        user = User.objects.get(email='user@test.com')
        self.assertFalse(user.check_password('userpasswd'))
        self.assertTrue(user.check_password('differentpassword'))
        
    def test_command_force_recreates_users(self):
        """Test that the command recreates users with the --force flag."""
        # Create users
        User.objects.create_user(email='user@test.com', password='differentpassword')
        User.objects.create_superuser(email='admin@test.com', password='differentpassword')
        
        # Call the command with force
        out = StringIO()
        call_command('create_default_users', force=True, stdout=out)
        output = out.getvalue()
        
        # Check output
        self.assertIn('Created regular user', output)
        self.assertIn('Created admin user', output)
        
        # Check that users were updated
        user = User.objects.get(email='user@test.com')
        self.assertTrue(user.check_password('userpasswd'))
        
        admin = User.objects.get(email='admin@test.com')
        self.assertTrue(admin.check_password('adminpasswd'))
