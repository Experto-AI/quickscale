"""Management command to create default users for QuickScale."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

User = get_user_model()


class Command(BaseCommand):
    """Create default users for QuickScale if they don't exist."""
    
    help = 'Create default users for QuickScale'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreate users even if they already exist',
        )
    
    def handle(self, *args, **kwargs):
        """Execute the command to create default users."""
        force = kwargs['force']
        
        # Create regular user
        if force or not User.objects.filter(email='user@test.com').exists():
            user, created = User.objects.update_or_create(
                email='user@test.com',
                defaults={
                    'is_active': True,
                    'username': None,  # Use email-only authentication
                }
            )
            user.set_password('userpasswd')
            user.save()
            
            # Ensure email is verified for the test user
            EmailAddress.objects.update_or_create(
                user=user, 
                email=user.email,
                defaults={
                    'verified': True,
                    'primary': True
                }
            )
            
            self.stdout.write(self.style.SUCCESS('Created regular user: user@test.com'))
        else:
            self.stdout.write('Regular user already exists')
            # Ensure existing user's email is verified
            user = User.objects.get(email='user@test.com')
            EmailAddress.objects.update_or_create(
                user=user, 
                email=user.email,
                defaults={
                    'verified': True,
                    'primary': True
                }
            )
            
        # Create admin user
        if force or not User.objects.filter(email='admin@test.com').exists():
            admin, created = User.objects.update_or_create(
                email='admin@test.com',
                defaults={
                    'is_staff': True,
                    'is_superuser': True,
                    'is_active': True,
                    'username': None,  # Use email-only authentication
                }
            )
            admin.set_password('adminpasswd')
            admin.save()
            
            # Ensure email is verified for the admin user
            EmailAddress.objects.update_or_create(
                user=admin, 
                email=admin.email,
                defaults={
                    'verified': True,
                    'primary': True
                }
            )
            
            self.stdout.write(self.style.SUCCESS('Created admin user: admin@test.com'))
        else:
            self.stdout.write('Admin user already exists')
            # Ensure existing admin's email is verified
            admin = User.objects.get(email='admin@test.com')
            EmailAddress.objects.update_or_create(
                user=admin, 
                email=admin.email,
                defaults={
                    'verified': True,
                    'primary': True
                }
            )
