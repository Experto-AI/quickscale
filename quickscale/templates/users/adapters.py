"""Custom adapter for django-allauth."""
from django.conf import settings
from django.urls import reverse
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

class AccountAdapter(DefaultAccountAdapter):
    """Custom adapter for django-allauth to handle custom functionality."""
    
    def is_open_for_signup(self, request):
        """Check if registration is currently open."""
        # Allow signup by default, can be controlled via settings
        return getattr(settings, 'ACCOUNT_ALLOW_REGISTRATION', True)
    
    def get_email_confirmation_url(self, request, emailconfirmation):
        """Return URL for email confirmation."""
        # Custom URL for email confirmation
        url = super().get_email_confirmation_url(request, emailconfirmation)
        # You can customize the URL here if needed
        return url
    
    def get_login_redirect_url(self, request):
        """Return the URL to redirect to after successful login."""
        # You can customize the redirect URL based on user or other conditions
        if request.user.is_staff:
            return reverse('dashboard:admin')
        return settings.LOGIN_REDIRECT_URL
    
    def send_mail(self, template_prefix, email, context):
        """Send an email using custom email templates."""
        # Custom email sending logic can be added here
        # For example, you can add additional context variables
        context.update({
            'site_name': 'QuickScale',
            'support_email': 'support@example.com',
        })
        return super().send_mail(template_prefix, email, context)
    
    def populate_username(self, request, user):
        """Set username to None since we're using email-only authentication."""
        # This is called when a new user is created
        # We're not using usernames, so just leave it empty
        # The username field is nullable in our CustomUser model
        user.username = None
        return user


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter for social account integration."""
    
    def is_open_for_signup(self, request, sociallogin):
        """Explicitly disable social account registration."""
        # We're using email-only authentication, so social logins are disabled
        return False
    
    def pre_social_login(self, request, sociallogin):
        """Prevent social login completely."""
        # This method is called before a social login attempt
        # We're blocking all social login attempts
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Social authentication is not supported.")
    
    def populate_user(self, request, sociallogin, data):
        """Disable user creation from social accounts."""
        # This would normally create a user from social account data
        # Since we're disabling social auth, this should never be called
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Social authentication is not supported.")
