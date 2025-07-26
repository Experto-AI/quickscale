"""API utility functions for standardized responses and validation."""
import json
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from decimal import Decimal


class APIResponse:
    """Utility class for creating standardized API responses."""
    
    @staticmethod
    def success(data=None, message=None, status=200):
        """Create a successful API response."""
        response_data = {
            'success': True,
            'status': status
        }
        
        if message:
            response_data['message'] = message
            
        if data is not None:
            response_data['data'] = data
            
        return JsonResponse(response_data, status=status)
    
    @staticmethod
    def error(message, status=400, error_code=None, details=None):
        """Create an error API response."""
        response_data = {
            'success': False,
            'status': status,
            'error': message
        }
        
        if error_code:
            response_data['error_code'] = error_code
            
        if details:
            response_data['details'] = details
            
        return JsonResponse(response_data, status=status)
    
    @staticmethod
    def validation_error(errors):
        """Create a validation error response."""
        return APIResponse.error(
            message='Validation failed',
            status=400,
            error_code='VALIDATION_ERROR',
            details=errors
        )
    
    @staticmethod
    def unauthorized(message="Authentication required"):
        """Create an unauthorized response."""
        return APIResponse.error(
            message=message,
            status=401,
            error_code='UNAUTHORIZED'
        )
    
    @staticmethod
    def forbidden(message="Access denied"):
        """Create a forbidden response."""
        return APIResponse.error(
            message=message,
            status=403,
            error_code='FORBIDDEN'
        )
    
    @staticmethod
    def not_found(message="Resource not found"):
        """Create a not found response."""
        return APIResponse.error(
            message=message,
            status=404,
            error_code='NOT_FOUND'
        )
    
    @staticmethod
    def server_error(message="Internal server error"):
        """Create a server error response."""
        return APIResponse.error(
            message=message,
            status=500,
            error_code='SERVER_ERROR'
        )


def validate_json_request(request):
    """Validate that request contains valid JSON data."""
    if request.content_type != 'application/json':
        raise ValidationError('Content-Type must be application/json')
    
    try:
        data = json.loads(request.body)
        return data
    except json.JSONDecodeError:
        raise ValidationError('Invalid JSON format')


def validate_required_fields(data, required_fields):
    """Validate that all required fields are present in the data."""
    missing_fields = []
    
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            missing_fields.append(field)
    
    if missing_fields:
        raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")


def validate_text_length(text, min_length=1, max_length=10000):
    """Validate text length constraints."""
    if len(text) < min_length:
        raise ValidationError(f"Text must be at least {min_length} characters long")
    
    if len(text) > max_length:
        raise ValidationError(f"Text must not exceed {max_length} characters")


def consume_service_credits(user, service_name, credit_cost):
    """Consume credits for a service and handle insufficient credits."""
    from credits.models import CreditAccount, Service, ServiceUsage, InsufficientCreditsError
    from django.db import transaction
    
    try:
        # Get the service
        service = Service.objects.get(name=service_name, is_active=True)
        
        # Get user's credit account
        credit_account = CreditAccount.get_or_create_for_user(user)
        
        # Check if user has sufficient credits
        available_balance = credit_account.get_available_balance()
        if available_balance < credit_cost:
            raise InsufficientCreditsError(
                f"Insufficient credits. Required: {credit_cost}, Available: {available_balance}"
            )
        
        # Consume credits and create usage record
        with transaction.atomic():
            credit_transaction = credit_account.consume_credits_with_priority(
                amount=credit_cost,
                description=f"Used {service_name} service"
            )
            
            # Record service usage
            ServiceUsage.objects.create(
                user=user,
                service=service,
                credit_transaction=credit_transaction
            )
        
        return credit_transaction
        
    except Service.DoesNotExist:
        raise ValidationError(f"Service '{service_name}' not found or inactive")
    except InsufficientCreditsError as e:
        raise ValidationError(str(e))