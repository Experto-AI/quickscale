"""Signal handlers for authentication security logging."""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from allauth.account.signals import email_confirmed
from .security_logger import (
    log_login_success, 
    log_logout, 
    log_login_failure,
    log_email_verification
)
from .models import AccountLockout

User = get_user_model()


@receiver(user_logged_in)
def log_successful_login(sender, request, user, **kwargs):
    """Log successful login attempts."""
    log_login_success(
        user_email=user.email,
        request=request,
        user_id=user.id,
        is_staff=user.is_staff
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log logout events."""
    if user and hasattr(user, 'email'):
        log_logout(
            user_email=user.email,
            request=request,
            user_id=user.id
        )


@receiver(user_login_failed)
def log_failed_login_attempt(sender, credentials, request, **kwargs):
    """Log failed login attempts and handle account lockout."""
    # Extract email from credentials (django-allauth uses 'login' field for email)
    user_email = credentials.get('login') or credentials.get('email') or 'unknown'
    
    log_login_failure(
        user_email=user_email,
        request=request,
        reason='invalid_credentials'
    )
    
    # Handle account lockout logic
    try:
        user = User.objects.get(email=user_email)
        lockout, created = AccountLockout.objects.get_or_create(user=user)
        lockout.record_failed_attempt()
    except User.DoesNotExist:
        # User doesn't exist, no lockout needed
        pass
    except Exception as e:
        # Log error but don't crash the login process
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error handling account lockout for {user_email}: {e}")


@receiver(email_confirmed)
def log_email_confirmation(sender, request, email_address, **kwargs):
    """Log email verification events."""
    if email_address and hasattr(email_address, 'user_id') and email_address.user_id:
        try:
            log_email_verification(
                user_email=email_address.email,
                request=request,
                user_id=email_address.user.id,
                verification_status='confirmed'
            )
        except AttributeError:
            # EmailAddress might not have a user assigned
            pass


@receiver(post_save, sender=User)
def log_user_creation(sender, instance, created, **kwargs):
    """Log new user account creation."""
    if created:
        from .security_logger import AuthenticationEventLogger
        AuthenticationEventLogger.log_security_event(
            event_type='ACCOUNT_CREATED',
            user_email=instance.email,
            request=None,  # No request context available in post_save
            details={
                'user_id': instance.id,
                'is_staff': instance.is_staff,
                'is_active': instance.is_active,
                'security_action': 'new_account'
            }
        ) 