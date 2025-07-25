"""Management command to fix login issues with default accounts."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress
from django.conf import settings

User = get_user_model()


class Command(BaseCommand):
    """Fix login issues with default accounts."""
    
    help = 'Fix login issues with default accounts'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset and recreate default accounts',
        )
    
    def handle(self, *args, **kwargs):
        """Execute the fix command."""
        reset = kwargs['reset']
        
        self.stdout.write(self.style.SUCCESS('🔧 QUICKSCALE LOGIN FIX\n'))
        
        # Default accounts
        default_accounts = [
            {
                'email': 'user@test.com', 
                'password': 'userpasswd',
                'is_staff': False,
                'is_superuser': False
            },
            {
                'email': 'admin@test.com', 
                'password': 'adminpasswd',
                'is_staff': True,
                'is_superuser': True
            },
        ]
        
        for account in default_accounts:
            email = account['email']
            
            if reset:
                # Delete existing user and EmailAddress if reset is requested
                try:
                    user = User.objects.get(email=email)
                    user.delete()
                    self.stdout.write(f'  🗑️  Deleted existing user: {email}')
                except User.DoesNotExist:
                    pass
            
            # Create or update user
            user, created = User.objects.update_or_create(
                email=email,
                defaults={
                    'is_active': True,
                    'is_staff': account['is_staff'],
                    'is_superuser': account['is_superuser'],
                    'username': None,  # Use email-only authentication
                }
            )
            
            # Set password
            user.set_password(account['password'])
            user.save()
            
            # Ensure email is verified for django-allauth
            email_obj, created = EmailAddress.objects.update_or_create(
                user=user, 
                email=user.email,
                defaults={
                    'verified': True,
                    'primary': True
                }
            )
            
            action = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(f'  ✅ {action} user: {email}'))
            self.stdout.write(f'     - is_active: {user.is_active}')
            self.stdout.write(f'     - is_staff: {user.is_staff}')
            self.stdout.write(f'     - EmailAddress verified: {email_obj.verified}')
        
        self.stdout.write('\n📋 CURRENT CONFIGURATION:')
        self.stdout.write(f'  DEBUG: {settings.DEBUG}')
        self.stdout.write(f'  ACCOUNT_EMAIL_VERIFICATION: {getattr(settings, "ACCOUNT_EMAIL_VERIFICATION", "Not set")}')
        self.stdout.write(f'  LOGIN_REDIRECT_URL: {getattr(settings, "LOGIN_REDIRECT_URL", "Not set")}')
        
        self.stdout.write('\n🧪 TEST INSTRUCTIONS:')
        self.stdout.write('  1. Try logging in with:')
        self.stdout.write('     - User: user@test.com / userpasswd')
        self.stdout.write('     - Admin: admin@test.com / adminpasswd')
        self.stdout.write('  2. If login still fails, check the container logs')
        self.stdout.write('  3. Run "quickscale manage diagnose_login" for detailed diagnostics')
        
        self.stdout.write('\n✅ Login fix complete!')
