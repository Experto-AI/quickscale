"""Two-factor authentication preparation views."""
import json
import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError
from django.utils import timezone
from datetime import timedelta
from .models import TwoFactorAuth

logger = logging.getLogger(__name__)


class TwoFactorValidationError(Exception):
    """Raised when 2FA validation fails."""
    pass


def validate_2fa_request(request):
    """Validate common requirements for 2FA requests."""
    # Check if user is authenticated
    if not request.user.is_authenticated:
        raise TwoFactorValidationError("Authentication required")
    
    # Check if 2FA is enabled in system settings
    if not getattr(settings, 'TWO_FACTOR_AUTH_ENABLED', False):
        raise TwoFactorValidationError("Two-factor authentication is not enabled in system settings")
    
    # Check request method and content type for JSON requests
    if request.method == 'POST' and request.content_type == 'application/json':
        try:
            request.json = json.loads(request.body)
        except json.JSONDecodeError as e:
            raise TwoFactorValidationError(f"Invalid JSON in request body: {e}")
    
    return True


def validate_backup_codes_request(request):
    """Validate backup codes generation request."""
    validate_2fa_request(request)
    
    # Check for recent backup code generation to prevent abuse
    try:
        two_factor = TwoFactorAuth.objects.get(user=request.user)
        if two_factor.updated_at and two_factor.updated_at > timezone.now() - timedelta(minutes=5):
            # Allow regeneration only if there are no backup codes or if explicitly requested
            if two_factor.backup_codes and len(two_factor.backup_codes) > 0:
                logger.warning(f"User {request.user.id} attempting frequent backup code generation")
                raise TwoFactorValidationError("Backup codes were recently generated. Please wait before generating new codes.")
    except TwoFactorAuth.DoesNotExist:
        pass  # New user, allow generation
    
    return True


def create_error_response(message, status=400, extra_data=None):
    """Create standardized error response."""
    response_data = {
        'status': 'error',
        'message': message,
        'timestamp': timezone.now().isoformat()
    }
    
    if extra_data:
        response_data.update(extra_data)
    
    return JsonResponse(response_data, status=status)


@login_required
def two_factor_settings(request):
    """Display 2FA settings page with preparation status."""
    # Check if 2FA is enabled in settings
    if not getattr(settings, 'TWO_FACTOR_AUTH_ENABLED', False):
        messages.info(request, 'Two-factor authentication is not currently enabled in system settings.')
        return redirect('users:profile')
    
    # Get or create 2FA settings
    two_factor, created = TwoFactorAuth.objects.get_or_create(user=request.user)
    
    context = {
        'two_factor': two_factor,
        'is_enabled': two_factor.is_enabled,
        'has_backup_codes': bool(two_factor.backup_codes),
        'backup_codes_count': len(two_factor.backup_codes) if two_factor.backup_codes else 0,
        'system_enabled': getattr(settings, 'TWO_FACTOR_AUTH_ENABLED', False),
        'issuer_name': getattr(settings, 'TWO_FACTOR_AUTH_ISSUER', 'QuickScale'),
    }
    
    return render(request, 'users/two_factor_settings.html', context)


@login_required
@require_http_methods(["POST"])
@csrf_protect
def two_factor_setup_prepare(request):
    """Prepare 2FA setup with comprehensive validation."""
    try:
        # Validate request
        validate_2fa_request(request)
        
        # Check if user already has 2FA enabled
        try:
            two_factor = TwoFactorAuth.objects.get(user=request.user)
            if two_factor.is_enabled:
                return create_error_response(
                    "Two-factor authentication is already enabled for this account",
                    status=409,
                    extra_data={'user_2fa_enabled': True}
                )
        except TwoFactorAuth.DoesNotExist:
            pass  # User doesn't have 2FA yet, proceed
        
        # Log setup preparation attempt
        logger.info(f"User {request.user.id} ({request.user.email}) initiated 2FA setup preparation")
        
        # This is a preparation endpoint - actual implementation would:
        # 1. Generate TOTP secret using pyotp
        # 2. Create QR code using qrcode library
        # 3. Return setup instructions and QR code data
        
        return JsonResponse({
            'status': 'preparation',
            'message': 'Two-factor authentication setup is prepared but not yet implemented.',
            'infrastructure_ready': True,
            'timestamp': timezone.now().isoformat(),
            'next_steps': [
                'Install pyotp library for TOTP generation',
                'Install qrcode library for QR code generation', 
                'Implement TOTP verification logic',
                'Create setup and verification templates',
                'Add middleware for 2FA verification'
            ],
            'required_packages': [
                'pyotp>=2.8.0',
                'qrcode>=7.4.0',
                'Pillow>=10.0.0'  # Required for QR code image generation
            ],
            'validation': {
                'user_authenticated': True,
                'system_enabled': True,
                'user_2fa_enabled': False
            }
        })
        
    except TwoFactorValidationError as e:
        logger.warning(f"2FA setup validation failed for user {request.user.id}: {e}")
        return create_error_response(str(e))
    except Exception as e:
        logger.error(f"Unexpected error in 2FA setup preparation for user {request.user.id}: {e}")
        return create_error_response(
            "An unexpected error occurred during setup preparation",
            status=500,
            extra_data={'error_type': 'internal_error'}
        )


@login_required
@require_http_methods(["POST"])
@csrf_protect
def two_factor_generate_backup_codes(request):
    """Generate backup codes with comprehensive validation."""
    try:
        # Validate request with rate limiting check
        validate_backup_codes_request(request)
        
        # Parse request parameters
        force_regenerate = False
        if hasattr(request, 'json') and isinstance(request.json, dict):
            force_regenerate = request.json.get('force_regenerate', False)
        
        # Validate count parameter if provided
        backup_codes_count = getattr(settings, 'TWO_FACTOR_AUTH_BACKUP_CODES_COUNT', 10)
        
        if backup_codes_count < 5 or backup_codes_count > 20:
            logger.warning(f"Invalid backup codes count in settings: {backup_codes_count}")
            backup_codes_count = 10  # Use safe default
        
        with transaction.atomic():
            two_factor, created = TwoFactorAuth.objects.get_or_create(user=request.user)
            
            # Check if regeneration is appropriate
            existing_codes_count = len(two_factor.backup_codes) if two_factor.backup_codes else 0
            
            if existing_codes_count > 0 and not force_regenerate:
                logger.info(f"User {request.user.id} has {existing_codes_count} existing backup codes")
                return create_error_response(
                    f"You already have {existing_codes_count} backup codes. Use force_regenerate=true to create new ones.",
                    status=409,
                    extra_data={
                        'existing_codes_count': existing_codes_count,
                        'force_regenerate_required': True
                    }
                )
            
            # Generate backup codes using the model method
            try:
                backup_codes = two_factor.generate_backup_codes(count=backup_codes_count)
                
                # Log successful generation
                logger.info(f"User {request.user.id} ({request.user.email}) generated {len(backup_codes)} backup codes")
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Backup codes generated successfully.',
                    'backup_codes': backup_codes,
                    'count': len(backup_codes),
                    'timestamp': timezone.now().isoformat(),
                    'regenerated': existing_codes_count > 0,
                    'previous_count': existing_codes_count,
                    'security_note': 'Store these codes in a secure location. Each code can only be used once.',
                    'usage_instructions': [
                        'Download and store codes securely',
                        'Each code can only be used once',
                        'Use codes only when your 2FA device is unavailable',
                        'Generate new codes if you lose access to these'
                    ]
                })
                
            except Exception as e:
                logger.error(f"Failed to generate backup codes for user {request.user.id}: {e}")
                raise TwoFactorValidationError("Failed to generate backup codes due to internal error")
        
    except TwoFactorValidationError as e:
        logger.warning(f"Backup codes validation failed for user {request.user.id}: {e}")
        return create_error_response(str(e))
    except DatabaseError as e:
        logger.error(f"Database error generating backup codes for user {request.user.id}: {e}")
        return create_error_response(
            "Database error occurred while generating backup codes",
            status=500,
            extra_data={'error_type': 'database_error'}
        )
    except Exception as e:
        logger.error(f"Unexpected error generating backup codes for user {request.user.id}: {e}")
        return create_error_response(
            "An unexpected error occurred while generating backup codes",
            status=500,
            extra_data={'error_type': 'internal_error'}
        )


@login_required
@require_http_methods(["POST"])
@csrf_protect
def two_factor_disable(request):
    """Disable 2FA for user account with comprehensive validation."""
    try:
        # Validate request
        validate_2fa_request(request)
        
        # Parse confirmation parameter
        confirmed = False
        if hasattr(request, 'json') and isinstance(request.json, dict):
            confirmed = request.json.get('confirmed', False)
        
        if not confirmed:
            return create_error_response(
                "Disabling 2FA requires explicit confirmation",
                status=400,
                extra_data={
                    'confirmation_required': True,
                    'security_warning': 'Disabling 2FA will reduce your account security'
                }
            )
        
        with transaction.atomic():
            try:
                two_factor = TwoFactorAuth.objects.get(user=request.user)
                
                if not two_factor.is_enabled:
                    return create_error_response(
                        "Two-factor authentication is not currently enabled for this account",
                        status=409,
                        extra_data={'user_2fa_enabled': False}
                    )
                
                # Store previous state for logging
                had_backup_codes = bool(two_factor.backup_codes)
                backup_codes_count = len(two_factor.backup_codes) if two_factor.backup_codes else 0
                
                # Disable 2FA and clear sensitive data
                two_factor.is_enabled = False
                two_factor.secret_key = ''  # Clear the secret for security
                two_factor.backup_codes = []  # Clear backup codes
                two_factor.save()
                
                # Log security action
                logger.warning(f"User {request.user.id} ({request.user.email}) disabled 2FA - had {backup_codes_count} backup codes")
                
                messages.success(request, 'Two-factor authentication has been disabled.')
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Two-factor authentication disabled successfully.',
                    'timestamp': timezone.now().isoformat(),
                    'previous_state': {
                        'had_backup_codes': had_backup_codes,
                        'backup_codes_count': backup_codes_count
                    },
                    'security_reminder': 'Your account security has been reduced. Consider re-enabling 2FA.'
                })
                
            except TwoFactorAuth.DoesNotExist:
                return create_error_response(
                    "Two-factor authentication is not configured for this account",
                    status=404,
                    extra_data={'user_2fa_configured': False}
                )
            
    except TwoFactorValidationError as e:
        logger.warning(f"2FA disable validation failed for user {request.user.id}: {e}")
        return create_error_response(str(e))
    except DatabaseError as e:
        logger.error(f"Database error disabling 2FA for user {request.user.id}: {e}")
        return create_error_response(
            "Database error occurred while disabling 2FA",
            status=500,
            extra_data={'error_type': 'database_error'}
        )
    except Exception as e:
        logger.error(f"Unexpected error disabling 2FA for user {request.user.id}: {e}")
        return create_error_response(
            "An unexpected error occurred while disabling 2FA",
            status=500,
            extra_data={'error_type': 'internal_error'}
        )


@login_required
def two_factor_status(request):
    """Get current 2FA status for user with comprehensive information."""
    try:
        # Basic validation
        if not request.user.is_authenticated:
            return create_error_response("Authentication required", status=401)
        
        system_enabled = getattr(settings, 'TWO_FACTOR_AUTH_ENABLED', False)
        
        if not system_enabled:
            return JsonResponse({
                'status': 'success',
                'system_enabled': False,
                'user_enabled': False,
                'message': 'Two-factor authentication is not enabled in system settings.',
                'timestamp': timezone.now().isoformat()
            })
        
        try:
            two_factor = TwoFactorAuth.objects.get(user=request.user)
            
            # Calculate status information
            backup_codes_count = len(two_factor.backup_codes) if two_factor.backup_codes else 0
            backup_codes_low = backup_codes_count > 0 and backup_codes_count < 3
            
            # Check if codes are recently generated
            codes_recently_generated = (
                two_factor.updated_at and 
                two_factor.updated_at > timezone.now() - timedelta(hours=24)
            )
            
            status = {
                'status': 'success',
                'system_enabled': True,
                'user_enabled': two_factor.is_enabled,
                'has_backup_codes': bool(two_factor.backup_codes),
                'backup_codes_count': backup_codes_count,
                'backup_codes_low': backup_codes_low,
                'codes_recently_generated': codes_recently_generated,
                'last_used': two_factor.last_used.isoformat() if two_factor.last_used else None,
                'created_at': two_factor.created_at.isoformat(),
                'updated_at': two_factor.updated_at.isoformat(),
                'timestamp': timezone.now().isoformat(),
                'security_recommendations': []
            }
            
            # Add security recommendations
            if not two_factor.is_enabled:
                status['security_recommendations'].append('Enable 2FA for enhanced account security')
            
            if two_factor.is_enabled and not two_factor.backup_codes:
                status['security_recommendations'].append('Generate backup codes for emergency access')
            
            if backup_codes_low:
                status['security_recommendations'].append('Consider generating new backup codes - you have few remaining')
            
            if two_factor.last_used and two_factor.last_used < timezone.now() - timedelta(days=30):
                status['security_recommendations'].append('2FA has not been used recently - verify it is working')
            
        except TwoFactorAuth.DoesNotExist:
            status = {
                'status': 'success',
                'system_enabled': True,
                'user_enabled': False,
                'has_backup_codes': False,
                'backup_codes_count': 0,
                'backup_codes_low': False,
                'codes_recently_generated': False,
                'last_used': None,
                'created_at': None,
                'updated_at': None,
                'timestamp': timezone.now().isoformat(),
                'security_recommendations': [
                    'Set up 2FA for enhanced account security',
                    'Generate backup codes after enabling 2FA'
                ]
            }
        
        return JsonResponse(status)
        
    except Exception as e:
        logger.error(f"Error getting 2FA status for user {request.user.id}: {e}")
        return create_error_response(
            "An error occurred while retrieving 2FA status",
            status=500,
            extra_data={'error_type': 'internal_error'}
        ) 