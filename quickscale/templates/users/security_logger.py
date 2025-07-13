"""Security event logging for authentication events."""
import logging
import json
from django.utils import timezone
from django.http import HttpRequest
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from typing import Optional, Dict, Any


class SecurityLoggingError(Exception):
    """Raised when security logging operations fail."""
    pass


class SecurityValidationError(Exception):
    """Raised when security event data validation fails."""
    pass

# Get security logger (already configured in logging_settings.py)
security_logger = logging.getLogger('django.security')


class AuthenticationEventLogger:
    """Class to handle authentication event logging."""
    
    @staticmethod
    def log_security_event(
        event_type: str, 
        user_email: str, 
        request: Optional[HttpRequest] = None, 
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log security events in JSON format."""
        # Validate required parameters to prevent incomplete security logs
        if not event_type or not isinstance(event_type, str):
            raise SecurityValidationError("event_type must be a non-empty string")
        
        if not user_email or not isinstance(user_email, str):
            raise SecurityValidationError("user_email must be a non-empty string")
        
        try:
            event_data = {
                'event_type': event_type,
                'user_email': user_email,
                'timestamp': timezone.now().isoformat(),
                'details': details or {}
            }
        except (TypeError, ValueError) as e:
            raise SecurityValidationError(f"Invalid security event data: {e}")
        
        if request:
            # Session key tracking enables correlation of security events across user sessions
            # Defensive programming prevents errors when session middleware is not loaded
            session_key = None
            if hasattr(request, 'session'):
                if hasattr(request.session, 'session_key'):
                    session_key = request.session.session_key
                elif hasattr(request.session, 'get'):
                    session_key = request.session.get('session_key')
            
            event_data.update({
                'ip_address': get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'path': request.path,
                'method': request.method,
                'session_key': session_key,
            })
        
        # JSON format enables structured log analysis and SIEM integration for security monitoring
        try:
            json_data = json.dumps(event_data)
            security_logger.info(json_data)
        except (TypeError, ValueError) as e:
            # JSON serialization failure could indicate malicious data injection
            raise SecurityLoggingError(f"Failed to serialize security event data: {e}")
        except Exception as e:
            # Logging system failure should not break application but must be reported
            raise SecurityLoggingError(f"Failed to write security log: {e}")


def get_client_ip(request: HttpRequest) -> str:
    """Extract client IP address from request."""
    # Priority order for IP detection ensures accurate logging in various deployment scenarios
    # X-Forwarded-For is checked first as it contains the original client IP in proxy setups
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the first IP in the chain to get original client IP, not proxy IPs
        return x_forwarded_for.split(',')[0].strip()
    
    # X-Real-IP is an alternative header used by some reverse proxies (like nginx)
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip.strip()
    
    # REMOTE_ADDR is used for direct connections without proxies
    return request.META.get('REMOTE_ADDR', 'unknown')


# Convenience functions for common authentication events
def log_login_success(user_email: str, request: HttpRequest, user_id: int, is_staff: bool = False) -> None:
    """Log successful login attempt."""
    try:
        AuthenticationEventLogger.log_security_event(
            event_type='LOGIN_SUCCESS',
            user_email=user_email,
            request=request,
            details={
                'user_id': user_id,
                'is_staff': is_staff,
                'login_method': 'email_password'
            }
        )
    except (SecurityLoggingError, SecurityValidationError) as e:
        # Re-raise security-specific errors to maintain explicit error handling
        raise
    except Exception as e:
        # Convert unexpected errors to security logging errors for consistent handling
        raise SecurityLoggingError(f"Unexpected error logging login success: {e}")


def log_login_failure(user_email: str, request: HttpRequest, reason: str = 'invalid_credentials') -> None:
    """Log failed login attempt."""
    AuthenticationEventLogger.log_security_event(
        event_type='LOGIN_FAILED',
        user_email=user_email,
        request=request,
        details={
            'failure_reason': reason,
            'login_method': 'email_password'
        }
    )


def log_logout(user_email: str, request: HttpRequest, user_id: int) -> None:
    """Log logout event."""
    AuthenticationEventLogger.log_security_event(
        event_type='LOGOUT',
        user_email=user_email,
        request=request,
        details={
            'user_id': user_id,
            'logout_method': 'manual'
        }
    )


def log_account_lockout(user_email: str, request: HttpRequest, lockout_duration: int, failed_attempts: int) -> None:
    """Log account lockout event."""
    # Validate critical security parameters to ensure accurate audit trails
    if lockout_duration <= 0:
        raise SecurityValidationError("lockout_duration must be positive")
    
    if failed_attempts <= 0:
        raise SecurityValidationError("failed_attempts must be positive")
    
    try:
        AuthenticationEventLogger.log_security_event(
            event_type='ACCOUNT_LOCKED',
            user_email=user_email,
            request=request,
            details={
                'lockout_duration_seconds': lockout_duration,
                'failed_attempts': failed_attempts,
                'security_action': 'automatic_lockout'
            }
        )
    except (SecurityLoggingError, SecurityValidationError) as e:
        # Account lockout logging is critical for security audits
        raise
    except Exception as e:
        raise SecurityLoggingError(f"Critical error logging account lockout: {e}")


def log_account_unlock(user_email: str, user_id: int, unlock_method: str = 'automatic_expiry') -> None:
    """Log account unlock event."""
    AuthenticationEventLogger.log_security_event(
        event_type='ACCOUNT_UNLOCKED',
        user_email=user_email,
        request=None,
        details={
            'user_id': user_id,
            'unlock_method': unlock_method,
            'security_action': 'account_restored'
        }
    )


def log_password_change(user_email: str, request: HttpRequest, user_id: int, change_method: str = 'user_initiated') -> None:
    """Log password change event."""
    AuthenticationEventLogger.log_security_event(
        event_type='PASSWORD_CHANGED',
        user_email=user_email,
        request=request,
        details={
            'user_id': user_id,
            'change_method': change_method,
            'security_action': 'credential_update'
        }
    )


def log_email_verification(user_email: str, request: HttpRequest, user_id: int, verification_status: str) -> None:
    """Log email verification event."""
    AuthenticationEventLogger.log_security_event(
        event_type='EMAIL_VERIFICATION',
        user_email=user_email,
        request=request,
        details={
            'user_id': user_id,
            'verification_status': verification_status,
            'security_action': 'email_confirmed'
        }
    ) 