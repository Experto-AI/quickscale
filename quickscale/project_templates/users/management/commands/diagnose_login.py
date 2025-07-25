"""Management command to diagnose login issues with default accounts."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress
from django.conf import settings

User = get_user_model()


class Command(BaseCommand):
    """Diagnose login issues with default accounts."""
    
    help = 'Diagnose login issues with default accounts'
    
    def handle(self, *args, **kwargs):
        """Execute the diagnostic command."""
        self.stdout.write(self.style.SUCCESS('🔍 QUICKSCALE LOGIN DIAGNOSTIC\n'))
        
        # Check Django settings
        self.stdout.write('📋 CONFIGURATION:')
        self.stdout.write(f'  DEBUG: {settings.DEBUG}')
        self.stdout.write(f'  ACCOUNT_EMAIL_VERIFICATION: {getattr(settings, "ACCOUNT_EMAIL_VERIFICATION", "Not set")}')
        self.stdout.write(f'  LOGIN_REDIRECT_URL: {getattr(settings, "LOGIN_REDIRECT_URL", "Not set")}')
        self.stdout.write(f'  ACCOUNT_LOGIN_METHODS: {getattr(settings, "ACCOUNT_LOGIN_METHODS", "Not set")}')
        self.stdout.write('')
        
        # Check default accounts
        default_accounts = [
            {'email': 'user@test.com', 'expected_password': 'userpasswd'},
            {'email': 'admin@test.com', 'expected_password': 'adminpasswd'},
        ]
        
        self.stdout.write('👥 DEFAULT ACCOUNTS STATUS:')
        
        for account in default_accounts:
            email = account['email']
            try:
                user = User.objects.get(email=email)
                self.stdout.write(f'  ✅ User exists: {email}')
                self.stdout.write(f'     - is_active: {user.is_active}')
                self.stdout.write(f'     - is_staff: {user.is_staff}')
                self.stdout.write(f'     - is_superuser: {user.is_superuser}')
                
                # Check password
                if user.check_password(account['expected_password']):
                    self.stdout.write(f'     - ✅ Password is correct')
                else:
                    self.stdout.write(f'     - ❌ Password is INCORRECT')
                
                # Check EmailAddress record
                try:
                    email_obj = EmailAddress.objects.get(user=user, email=user.email)
                    self.stdout.write(f'     - EmailAddress record exists:')
                    self.stdout.write(f'       * verified: {email_obj.verified}')
                    self.stdout.write(f'       * primary: {email_obj.primary}')
                except EmailAddress.DoesNotExist:
                    self.stdout.write(f'     - ❌ NO EmailAddress record found!')
                    
            except User.DoesNotExist:
                self.stdout.write(f'  ❌ User does NOT exist: {email}')
            
            self.stdout.write('')
        
        # Check for common issues
        self.stdout.write('🚨 POTENTIAL ISSUES:')
        
        if settings.DEBUG == False and getattr(settings, 'ACCOUNT_EMAIL_VERIFICATION', None) == 'mandatory':
            self.stdout.write('  ⚠️  EMAIL VERIFICATION is MANDATORY in production mode')
            self.stdout.write('     This could prevent login even with verified EmailAddress records')
        
        # Count all users and EmailAddress records
        total_users = User.objects.count()
        total_emails = EmailAddress.objects.count()
        verified_emails = EmailAddress.objects.filter(verified=True).count()
        
        self.stdout.write(f'📊 DATABASE STATS:')
        self.stdout.write(f'  Total users: {total_users}')
        self.stdout.write(f'  Total EmailAddress records: {total_emails}')
        self.stdout.write(f'  Verified EmailAddress records: {verified_emails}')
        
        self.stdout.write('\n✅ Diagnostic complete!')
