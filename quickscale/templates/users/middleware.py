"""Account lockout middleware."""
from django.contrib.auth import logout
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.shortcuts import render
from django.core.exceptions import ValidationError
from django.db import DatabaseError
import logging
from .models import AccountLockout

logger = logging.getLogger(__name__)


class MiddlewareValidationError(Exception):
    """Raised when middleware validation fails."""
    pass


class AccountLockoutMiddleware:
    """Middleware to handle account lockout verification."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def validate_request(self, request):
        """Validate request data before processing lockout logic."""
        if not hasattr(request, 'user'):
            raise MiddlewareValidationError("Request missing user attribute")
        
        if not hasattr(request, 'META'):
            raise MiddlewareValidationError("Request missing META attribute")
        
        # Log warning for missing IP address but don't fail
        if not request.META.get('REMOTE_ADDR'):
            logger.warning("Request missing IP address for lockout tracking")
        
        return True
    
    def __call__(self, request):
        try:
            # Validate request structure before processing
            self.validate_request(request)
        except MiddlewareValidationError as e:
            logger.error(f"Middleware validation failed: {e}")
            # Return normal response for malformed requests to prevent exposure
            return self.get_response(request)
        
        # Account lockout only applies to authenticated users to prevent bypass attempts
        if request.user.is_authenticated:
            try:
                lockout = AccountLockout.objects.get(user=request.user)
                if lockout.is_locked:
                    # Automatic unlock check prevents users from being permanently locked
                    if lockout.check_lockout_expired():
                        # Lockout expired, allow normal request processing
                        pass
                    else:
                        # Force logout prevents bypassing lockout through session persistence
                        # This ensures the user must go through login flow when lockout expires
                        logout(request)
                        
                        # Time calculations provide user feedback on lockout duration
                        time_remaining = lockout.time_until_unlock
                        minutes_remaining = int(time_remaining.total_seconds() / 60) if time_remaining else 0
                        
                        context = {
                            'locked_until': lockout.locked_until,
                            'minutes_remaining': minutes_remaining,
                            'failed_attempts': lockout.failed_attempts,
                            'user_email': lockout.user.email
                        }
                        
                        return TemplateResponse(
                            request,
                            'users/account_locked.html',
                            context,
                            status=423  # HTTP 423 Locked standard for resource lockout
                        )
                        
            except AccountLockout.DoesNotExist:
                # Lazy initialization of lockout records reduces database overhead for new users
                # This ensures all users have lockout tracking without requiring migration
                try:
                    AccountLockout.objects.create(user=request.user)
                except DatabaseError as e:
                    logger.error(f"Failed to create AccountLockout record for user {request.user.id}: {e}")
                    # Continue without lockout protection rather than breaking the application
                except ValidationError as e:
                    logger.error(f"Invalid data when creating AccountLockout for user {request.user.id}: {e}")
            except DatabaseError as e:
                logger.error(f"Database error in lockout middleware for user {request.user.id}: {e}")
                # Graceful degradation ensures site remains functional even with database issues
            except Exception as e:
                logger.error(f"Unexpected error in lockout middleware for user {request.user.id}: {e}")
                # Security features should never break core application functionality
        
        response = self.get_response(request)
        return response 