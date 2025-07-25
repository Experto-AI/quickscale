"""Utility functions for admin dashboard."""
from django.http import HttpRequest
from typing import Optional
from .models import AuditLog


def log_admin_action(
    user,
    action: str,
    description: str,
    request: Optional[HttpRequest] = None
) -> AuditLog:
    """Log an admin action for audit purposes."""
    ip_address = None
    user_agent = None
    
    if request:
        # Get IP address from request
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        
        # Get user agent
        user_agent = request.META.get('HTTP_USER_AGENT')
    
    audit_log = AuditLog.objects.create(
        user=user,
        action=action,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    return audit_log


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') 