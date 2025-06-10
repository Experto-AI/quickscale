"""Signal handlers for admin dashboard audit logging."""
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .utils import log_admin_action


@receiver(user_logged_in)
def log_admin_login(sender, request, user, **kwargs):
    """Log admin login events for staff users."""
    if user.is_staff:
        log_admin_action(
            user=user,
            action='ADMIN_LOGIN',
            description=f'Admin user {user.email} logged in',
            request=request
        )


@receiver(user_logged_out)
def log_admin_logout(sender, request, user, **kwargs):
    """Log admin logout events for staff users."""
    if user and user.is_staff:
        log_admin_action(
            user=user,
            action='ADMIN_LOGOUT',
            description=f'Admin user {user.email} logged out',
            request=request
        ) 